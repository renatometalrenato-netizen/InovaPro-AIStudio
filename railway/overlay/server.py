"""InovaPro Systems — platform API (FastAPI + MongoDB)."""
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from app.db import client, db  # noqa: E402  (env must load first)
from app.routers import (  # noqa: E402
    auth_router,
    business_router,
    crm_router,
    dashboard_router,
    diagnostics_router,
    nova_router,
    social_auth_router,
)
from app.seed import seed  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("inovapro")

app = FastAPI(title="InovaPro Systems API", version="0.1.0")

api_router = APIRouter(prefix="/api")
api_router.include_router(auth_router)
api_router.include_router(social_auth_router)
api_router.include_router(business_router)
api_router.include_router(crm_router)
api_router.include_router(nova_router)
api_router.include_router(dashboard_router)
api_router.include_router(diagnostics_router)
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    try:
        await db.users.create_index("email", unique=True)
        await db.nova_pending_actions.create_index("expires_at")
        await db.diagnostic_results.create_index([("company_id", 1), ("created_at", -1)])
        await db.oauth_states.create_index("expires_at", expireAfterSeconds=0)
        await db.social_login_codes.create_index("expires_at", expireAfterSeconds=0)
        await db.social_integrations.create_index([("user_id", 1), ("provider", 1)], unique=True)
    except Exception:
        logger.warning("Índices não puderam ser recriados (já existem?)", exc_info=True)
    try:
        if os.environ.get("ENABLE_DEMO_SEED") == "true":
            await seed()
    except Exception:
        logger.exception("Seed falhou")

@app.get("/api/health")
async def health():
    await db.command("ping")
    return {"status": "ok", "service": "inovapro-api"}

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
