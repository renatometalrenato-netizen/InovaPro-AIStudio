from app.routers.auth_router import router as auth_router
from app.routers.business_router import router as business_router
from app.routers.crm_router import router as crm_router
from app.routers.dashboard_router import router as dashboard_router
from app.routers.diagnostics_router import router as diagnostics_router
from app.routers.nova_router import router as nova_router
from app.routers.social_auth_router import router as social_auth_router

__all__ = ["auth_router", "business_router", "crm_router", "dashboard_router", "diagnostics_router", "nova_router", "social_auth_router"]
