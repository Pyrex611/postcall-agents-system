"""
API v1 Router Configuration
"""
from fastapi import APIRouter
from .endpoints import (
    auth, 
    calls, 
    crm, 
    analytics, 
    health, 
    webhooks,
    users
)

# Create main API router
api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(calls.router, prefix="/calls", tags=["calls"])
api_router.include_router(crm.router, prefix="/crm", tags=["crm"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(users.router, prefix="/users", tags=["users"])