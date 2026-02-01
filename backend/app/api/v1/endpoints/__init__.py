"""
API v1 Endpoints Package
"""
from .auth import router as auth_router
from .calls import router as calls_router
from .crm import router as crm_router
from .analytics import router as analytics_router
from .health import router as health_router
from .webhooks import router as webhooks_router
from .users import router as users_router

__all__ = [
    "auth_router",
    "calls_router", 
    "crm_router",
    "analytics_router",
    "health_router",
    "webhooks_router",
    "users_router"
]