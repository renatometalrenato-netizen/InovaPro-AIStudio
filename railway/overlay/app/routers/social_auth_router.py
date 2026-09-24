"""Social sign-in and business-source enrichment for InovaPro.

OAuth happens on the backend so provider secrets never ship in the APK.
The app receives only a short-lived one-time login code through its custom URL
scheme and exchanges it for the normal InovaPro JWT.
"""
from __future__ import annotations

import base64
import hashlib
import os
import secrets
from datetime import timedelta
from typing import Any, Optional
from urllib.parse import urlencode, urlparse

import httpx
from bson import ObjectId
from cryptography.fernet import Fernet
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.auth import create_token, hash_password
from app.db import db
from app.models import BusinessProfile, Company, User, utcnow

router = APIRouter(prefix="/auth/social", tags=["auth-social"])

STATE_TTL_MINUTES = 10
LOGIN_CODE_TTL_MINUTES = 5


def _allowed_return_urls() -> list[str]:
    raw = os.environ.get("SOCIAL_ALLOWED_RETURN_URLS", "inovapro://oauth/callback")
    return [item.strip() for item in raw.split(",") if item.strip()]


def _validate_return_url(value: str) -> str:
    allowed = _allowed_return_urls()
    parsed = urlparse(value)
    if parsed.scheme == "inovapro" and any(urlparse(x).scheme == "inovapro" for x in allowed):
        return value
    if value in allowed:
        return value
    raise HTTPException(status_code=400, detail="URL de retorno não permitida")


def _redirect_with(return_url: str, **params: str) -> RedirectResponse:
    sep = "&" if "?" in return_url else "?"
    return RedirectResponse(return_url + sep + urlencode(params))


def _fernet() -> Fernet:
    secret = os.environ.get("JWT_SECRET", "")
    if not secret:
        raise RuntimeError("JWT_SECRET ausente")
    key = base64.urlsafe_b64encode(hashlib.sha256((secret + ":social-oauth").encode()).digest())
    return Fernet(key)


def _encrypt_optional(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return _fernet().encrypt(value.encode()).decode()


async def _new_state(provider: str, return_url: str) -> str:
    state = secrets.token_urlsafe(32)
    await db.oauth_states.insert_one({
        "state": state,
        "provider": provider,
        "return_url": return_url,
        "created_at": utcnow(),
        "expires_at": utcnow() + timedelta(minutes=STATE_TTL_MINUTES),
    })
    return state


async def _consume_state(provider: str, state: str) -> dict:
    doc = await db.oauth_states.find_one_and_delete({"state": state, "provider": provider})
    if not doc or doc.get("expires_at") < utcnow():
        raise HTTPException(status_code=400, detail="Sessão de login expirada. Tente novamente.")
    return doc


async def _issue_login_code(user_doc: dict, provider: str) -> str:
    code = secrets.token_urlsafe(36)
    await db.social_login_codes.insert_one({
        "code": code,
        "user_id": str(user_doc["_id"]),
        "provider": provider,
        "created_at": utcnow(),
        "expires_at": utcnow() + timedelta(minutes=LOGIN_CODE_TTL_MINUTES),
    })
    return code


async def _upsert_user(email: str, name: str) -> dict:
    email = email.lower().strip()
    existing = await db.users.find_one({"email": email})
    if existing:
        updates: dict[str, Any] = {}
        if name and not existing.get("name"):
            updates["name"] = name
        if updates:
            await db.users.update_one({"_id": existing["_id"]}, {"$set": updates})
            existing.update(updates)
        return existing

    random_password = secrets.token_urlsafe(32)
    user = User(
        email=email,
        name=(name or "Cliente InovaPro")[:100],
        hashed_password=hash_password(random_password),
        role="owner",
        company_id=None,
    )
    result = await db.users.insert_one(user.to_mongo())
    return await db.users.find_one({"_id": result.inserted_id})


async def _ensure_company_from_source(user_doc: dict, source: dict) -> dict:
    company_id = user_doc.get("company_id")
    if company_id:
        profile = await db.business_profiles.find_one({"company_id": company_id}) or {}
        updates = {}
        for key in ("name", "segment", "description", "location", "channels"):
            value = source.get(key)
            if value and not profile.get(key):
                updates[key] = value
        if updates:
            updates["updated_at"] = utcnow()
            await db.business_profiles.update_one({"company_id": company_id}, {"$set": updates}, upsert=True)
        return {"company_id": company_id, "created": False}

    name = (source.get("name") or "").strip()
    if not name:
        return {"company_id": None, "created": False}

    segment = (source.get("segment") or "Negócio").strip()[:80]
    company = Company(name=name[:120], segment=segment, owner_user_id=str(user_doc["_id"]))
    result = await db.companies.insert_one(company.to_mongo())
    company_id = str(result.inserted_id)
    profile = BusinessProfile(
        company_id=company_id,
        name=name[:120],
        segment=segment,
        description=source.get("description"),
        location=source.get("location"),
        channels=source.get("channels"),
    )
    await db.business_profiles.insert_one(profile.to_mongo())
    await db.users.update_one({"_id": user_doc["_id"]}, {"$set": {"company_id": company_id, "role": "owner"}})
    user_doc["company_id"] = company_id
    return {"company_id": company_id, "created": True}


async def _save_integration(user_doc: dict, provider: str, profile: dict, tokens: dict, extra: Optional[dict] = None):
    doc = {
        "user_id": str(user_doc["_id"]),
        "company_id": user_doc.get("company_id"),
        "provider": provider,
        "provider_user_id": str(profile.get("id") or profile.get("sub") or ""),
        "username": profile.get("username"),
        "display_name": profile.get("name"),
        "profile": profile,
        "extra": extra or {},
        "access_token": _encrypt_optional(tokens.get("access_token")),
        "refresh_token": _encrypt_optional(tokens.get("refresh_token")),
        "expires_in": tokens.get("expires_in"),
        "updated_at": utcnow(),
    }
    await db.social_integrations.update_one(
        {"user_id": doc["user_id"], "provider": provider},
        {"$set": doc, "$setOnInsert": {"created_at": utcnow()}},
        upsert=True,
    )


async def _google_business_snapshot(access_token: str) -> dict:
    if os.environ.get("GOOGLE_BUSINESS_PROFILE_ENABLED", "false").lower() != "true":
        return {"enabled": False, "accounts": [], "locations": []}

    headers = {"Authorization": f"Bearer {access_token}", "X-GOOG-API-FORMAT-VERSION": "2"}
    async with httpx.AsyncClient(timeout=20) as client:
        accounts_res = await client.get("https://mybusinessaccountmanagement.googleapis.com/v1/accounts", headers=headers)
        if accounts_res.status_code >= 400:
            return {"enabled": True, "accounts": [], "locations": [], "error": f"GBP {accounts_res.status_code}"}
        accounts = accounts_res.json().get("accounts", [])
        locations: list[dict] = []
        read_mask = "name,title,storeCode,phoneNumbers,categories,storefrontAddress,websiteUri,regularHours,metadata"
        for account in accounts[:5]:
            account_name = account.get("name")
            if not account_name:
                continue
            url = f"https://mybusinessbusinessinformation.googleapis.com/v1/{account_name}/locations"
            res = await client.get(url, headers=headers, params={"readMask": read_mask, "pageSize": 100})
            if res.status_code < 400:
                locations.extend(res.json().get("locations", []))
        return {"enabled": True, "accounts": accounts, "locations": locations}


def _address_text(location: dict) -> Optional[str]:
    address = location.get("storefrontAddress") or {}
    pieces = []
    pieces.extend(address.get("addressLines") or [])
    for key in ("locality", "administrativeArea", "postalCode", "regionCode"):
        if address.get(key):
            pieces.append(str(address[key]))
    return ", ".join(dict.fromkeys(pieces)) or None


def _source_from_google(snapshot: dict) -> dict:
    locations = snapshot.get("locations") or []
    if not locations:
        return {}
    loc = locations[0]
    categories = loc.get("categories") or {}
    primary = categories.get("primaryCategory") or {}
    phones = loc.get("phoneNumbers") or {}
    channel_parts = ["Google Business Profile"]
    if loc.get("websiteUri"):
        channel_parts.append(f"Site: {loc['websiteUri']}")
    if phones.get("primaryPhone"):
        channel_parts.append(f"Telefone: {phones['primaryPhone']}")
    return {
        "name": loc.get("title"),
        "segment": primary.get("displayName") or primary.get("name") or "Negócio",
        "location": _address_text(loc),
        "channels": " | ".join(channel_parts),
    }


@router.get("/google/start")
async def google_start(return_url: str = Query(...)):
    return_url = _validate_return_url(return_url)
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    redirect_uri = os.environ.get("GOOGLE_OAUTH_REDIRECT_URI")
    if not client_id or not redirect_uri:
        raise HTTPException(status_code=503, detail="Login com Google ainda não foi configurado no servidor.")
    state = await _new_state("google", return_url)
    scopes = ["openid", "email", "profile"]
    if os.environ.get("GOOGLE_BUSINESS_PROFILE_ENABLED", "false").lower() == "true":
        scopes.append("https://www.googleapis.com/auth/business.manage")
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    return RedirectResponse("https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params))


@router.get("/google/callback")
async def google_callback(code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    if not state:
        raise HTTPException(status_code=400, detail="Estado OAuth ausente")
    state_doc = await _consume_state("google", state)
    return_url = state_doc["return_url"]
    if error or not code:
        return _redirect_with(return_url, error="google_cancelled")

    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
    redirect_uri = os.environ.get("GOOGLE_OAUTH_REDIRECT_URI")
    if not client_id or not client_secret or not redirect_uri:
        return _redirect_with(return_url, error="google_not_configured")

    async with httpx.AsyncClient(timeout=20) as client:
        token_res = await client.post("https://oauth2.googleapis.com/token", data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        })
        if token_res.status_code >= 400:
            return _redirect_with(return_url, error="google_token_failed")
        tokens = token_res.json()
        access_token = tokens.get("access_token")
        info_res = await client.get("https://openidconnect.googleapis.com/v1/userinfo", headers={"Authorization": f"Bearer {access_token}"})
        if info_res.status_code >= 400:
            return _redirect_with(return_url, error="google_profile_failed")
        profile = info_res.json()

    email = profile.get("email")
    if not email:
        return _redirect_with(return_url, error="google_email_missing")
    user_doc = await _upsert_user(email, profile.get("name") or email.split("@")[0])
    business_snapshot = await _google_business_snapshot(access_token)
    source = _source_from_google(business_snapshot)
    if source:
        await _ensure_company_from_source(user_doc, source)
        user_doc = await db.users.find_one({"_id": user_doc["_id"]})
    await _save_integration(user_doc, "google", profile, tokens, {"business_profile": business_snapshot})
    login_code = await _issue_login_code(user_doc, "google")
    return _redirect_with(return_url, code=login_code, provider="google")


@router.get("/instagram/start")
async def instagram_start(return_url: str = Query(...)):
    return_url = _validate_return_url(return_url)
    app_id = os.environ.get("INSTAGRAM_APP_ID")
    redirect_uri = os.environ.get("INSTAGRAM_OAUTH_REDIRECT_URI")
    if not app_id or not redirect_uri:
        raise HTTPException(status_code=503, detail="Login com Instagram ainda não foi configurado no servidor.")
    state = await _new_state("instagram", return_url)
    params = {
        "client_id": app_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "instagram_business_basic",
        "state": state,
        "force_reauth": "true",
    }
    authorize_url = os.environ.get("INSTAGRAM_OAUTH_AUTHORIZE_URL", "https://www.instagram.com/oauth/authorize")
    return RedirectResponse(authorize_url + "?" + urlencode(params))


@router.get("/instagram/callback")
async def instagram_callback(code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    if not state:
        raise HTTPException(status_code=400, detail="Estado OAuth ausente")
    state_doc = await _consume_state("instagram", state)
    return_url = state_doc["return_url"]
    if error or not code:
        return _redirect_with(return_url, error="instagram_cancelled")

    app_id = os.environ.get("INSTAGRAM_APP_ID")
    app_secret = os.environ.get("INSTAGRAM_APP_SECRET")
    redirect_uri = os.environ.get("INSTAGRAM_OAUTH_REDIRECT_URI")
    if not app_id or not app_secret or not redirect_uri:
        return _redirect_with(return_url, error="instagram_not_configured")

    async with httpx.AsyncClient(timeout=20) as client:
        token_res = await client.post("https://api.instagram.com/oauth/access_token", data={
            "client_id": app_id,
            "client_secret": app_secret,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "code": code,
        })
        if token_res.status_code >= 400:
            return _redirect_with(return_url, error="instagram_token_failed")
        tokens = token_res.json()
        access_token = tokens.get("access_token")
        fields = "id,username,name,account_type,media_count,profile_picture_url,followers_count,follows_count,website,biography"
        profile_res = await client.get("https://graph.instagram.com/me", params={"fields": fields, "access_token": access_token})
        if profile_res.status_code >= 400:
            profile_res = await client.get("https://graph.instagram.com/me", params={"fields": "id,username,name,account_type,media_count", "access_token": access_token})
        if profile_res.status_code >= 400:
            return _redirect_with(return_url, error="instagram_profile_failed")
        profile = profile_res.json()

    provider_id = str(profile.get("id") or "")
    if not provider_id:
        return _redirect_with(return_url, error="instagram_id_missing")
    synthetic_email = f"instagram.{provider_id}@social.inovapro.local"
    display = profile.get("name") or profile.get("username") or "Instagram"
    user_doc = await _upsert_user(synthetic_email, display)
    channels = f"Instagram: @{profile.get('username')}" if profile.get("username") else "Instagram"
    source = {
        "name": display,
        "segment": "Negócio no Instagram",
        "description": profile.get("biography"),
        "channels": channels,
    }
    await _ensure_company_from_source(user_doc, source)
    user_doc = await db.users.find_one({"_id": user_doc["_id"]})
    await _save_integration(user_doc, "instagram", profile, tokens)
    login_code = await _issue_login_code(user_doc, "instagram")
    return _redirect_with(return_url, code=login_code, provider="instagram")


class ExchangeIn(BaseModel):
    code: str = Field(min_length=20, max_length=200)


@router.post("/exchange")
async def exchange_social_code(data: ExchangeIn):
    doc = await db.social_login_codes.find_one_and_delete({"code": data.code})
    if not doc or doc.get("expires_at") < utcnow():
        raise HTTPException(status_code=400, detail="Código de login expirado. Tente novamente.")
    user_doc = await db.users.find_one({"_id": ObjectId(doc["user_id"])})
    if not user_doc:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    token = create_token(str(user_doc["_id"]), user_doc.get("company_id"), user_doc.get("role", "owner"))
    return {
        "access_token": token,
        "token_type": "bearer",
        "provider": doc.get("provider"),
        "has_company": bool(user_doc.get("company_id")),
    }


@router.get("/status")
async def social_status():
    return {
        "google": {
            "login_configured": bool(os.environ.get("GOOGLE_OAUTH_CLIENT_ID") and os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET") and os.environ.get("GOOGLE_OAUTH_REDIRECT_URI")),
            "business_profile_enabled": os.environ.get("GOOGLE_BUSINESS_PROFILE_ENABLED", "false").lower() == "true",
        },
        "instagram": {
            "login_configured": bool(os.environ.get("INSTAGRAM_APP_ID") and os.environ.get("INSTAGRAM_APP_SECRET") and os.environ.get("INSTAGRAM_OAUTH_REDIRECT_URI")),
        },
    }
