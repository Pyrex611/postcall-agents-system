"""
SalesIntel AI API Package
"""
from fastapi import APIRouter

from .v1.api import api_router as v1_router

# Main API router that can be included in the main app
api_router = APIRouter()
api_router.include_router(v1_router, prefix="/api/v1")