"""Authenticated API for the InovaPro 360° diagnostic."""
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from app.auth import require_company
from app.db import db
from app.diagnostic_engine import (
    ANSWER_OPTIONS,
    PILLARS,
    QUESTIONS,
    SMART_QUESTIONS,
    calculate_result,
    calculate_smart_result,
)
from app.models import Activity, utcnow

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


class DiagnosticSubmit(BaseModel):
    answers: Dict[str, int]

    @field_validator("answers")
    @classmethod
    def validate_answers(cls, value: Dict[str, int]):
        expected = {q["id"] for q in QUESTIONS}
        if set(value.keys()) != expected:
            missing = sorted(expected - set(value.keys()))
            extra = sorted(set(value.keys()) - expected)
            detail = []
            if missing:
                detail.append(f"faltam: {', '.join(missing)}")
            if extra:
                detail.append(f"não reconhecidas: {', '.join(extra)}")
            raise ValueError("Responda todas as perguntas do diagnóstico (" + "; ".join(detail) + ")")
        if any(not isinstance(v, int) or isinstance(v, bool) or v < 1 or v > 5 for v in value.values()):
            raise ValueError("Cada resposta deve estar entre 1 e 5")
        return value


def public_result(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "overall_score": doc["overall_score"],
        "level": doc["level"],
        "pillar_scores": doc["pillar_scores"],
        "strengths": doc.get("strengths", []),
        "priorities": doc.get("priorities", []),
        "recommendations": doc.get("recommendations", []),
        "created_at": doc["created_at"],
    }


@router.get("/360/questions")
async def get_questions(user=Depends(require_company)):
    return {
        "version": 1,
        "pillars": PILLARS,
        "questions": QUESTIONS,
        "answer_options": ANSWER_OPTIONS,
    }


@router.post("/360/submit", status_code=201)
async def submit_diagnostic(data: DiagnosticSubmit, user=Depends(require_company)):
    result = calculate_result(data.answers)
    now = utcnow()
    doc = {
        "company_id": user.company_id,
        "user_id": user.id,
        "version": 1,
        "answers": data.answers,
        **result,
        "created_at": now,
    }
    inserted = await db.diagnostic_results.insert_one(doc)
    saved = {**doc, "_id": inserted.inserted_id}
    await db.activities.insert_one(
        Activity(
            company_id=user.company_id,
            type="diagnostic_360",
            description=f"Diagnóstico InovaPro 360° concluído: {result['overall_score']}/100 ({result['level']})",
            user_id=user.id,
        ).to_mongo()
    )
    return public_result(saved)


@router.get("/360/latest")
async def latest_diagnostic(user=Depends(require_company)):
    doc = await db.diagnostic_results.find_one(
        {"company_id": user.company_id}, sort=[("created_at", -1)]
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Nenhum diagnóstico concluído ainda")
    return public_result(doc)


@router.get("/360/history")
async def diagnostic_history(limit: int = 10, user=Depends(require_company)):
    safe_limit = max(1, min(limit, 30))
    docs = await db.diagnostic_results.find({"company_id": user.company_id}).sort("created_at", -1).to_list(safe_limit)
    return [public_result(doc) for doc in docs]


class SmartDiagnosticSubmit(BaseModel):
    answers: Dict[str, int]

    @field_validator("answers")
    @classmethod
    def validate_smart_answers(cls, value: Dict[str, int]):
        expected = {q["id"] for q in SMART_QUESTIONS}
        if set(value.keys()) != expected:
            raise ValueError("Responda as 7 perguntas essenciais do diagnóstico inteligente")
        if any(not isinstance(v, int) or isinstance(v, bool) or v < 1 or v > 5 for v in value.values()):
            raise ValueError("Cada resposta deve estar entre 1 e 5")
        return value


@router.get("/360/smart/questions")
async def get_smart_questions(user=Depends(require_company)):
    integrations = await db.social_integrations.find({"company_id": user.company_id}).to_list(10)
    sources = []
    for doc in integrations:
        sources.append({
            "provider": doc.get("provider"),
            "display_name": doc.get("display_name") or doc.get("username"),
            "connected": True,
        })
    return {
        "version": 2,
        "mode": "smart",
        "pillars": PILLARS,
        "questions": SMART_QUESTIONS,
        "answer_options": ANSWER_OPTIONS,
        "connected_sources": sources,
        "note": "Dados conectados enriquecem o contexto; as 7 respostas cobrem fatores internos que redes sociais não conseguem observar com segurança.",
    }


@router.post("/360/smart/submit", status_code=201)
async def submit_smart_diagnostic(data: SmartDiagnosticSubmit, user=Depends(require_company)):
    result = calculate_smart_result(data.answers)
    integrations = await db.social_integrations.find({"company_id": user.company_id}).to_list(10)
    source_names = [doc.get("provider") for doc in integrations if doc.get("provider")]
    now = utcnow()
    doc = {
        "company_id": user.company_id,
        "user_id": user.id,
        "version": 2,
        "mode": "smart",
        "answers": data.answers,
        "connected_sources": source_names,
        **result,
        "created_at": now,
    }
    inserted = await db.diagnostic_results.insert_one(doc)
    saved = {**doc, "_id": inserted.inserted_id}
    await db.activities.insert_one(
        Activity(
            company_id=user.company_id,
            type="diagnostic_360_smart",
            description=f"Diagnóstico InovaPro 360° inteligente concluído: {result['overall_score']}/100 ({result['level']})",
            user_id=user.id,
        ).to_mongo()
    )
    return public_result(saved)
