"""
Core module for SalesIntel AI application.
Contains configuration, database, security, and middleware.
"""

from .config import settings
from .database import Base, engine, get_db, async_session_factory
from .security import (
    create_access_token, 
    verify_token, 
    create_refresh_token,
    verify_refresh_token,
    get_password_hash,
    verify_password,
    get_current_user,
    get_current_active_user
)
from .middleware import RequestContextMiddleware, RateLimitMiddleware

__all__ = [
    "settings",
    "Base", 
    "engine", 
    "get_db", 
    "async_session_factory",
    "create_access_token",
    "verify_token",
    "create_refresh_token",
    "verify_refresh_token",
    "get_password_hash",
    "verify_password",
    "get_current_user",
    "get_current_active_user",
    "RequestContextMiddleware",
    "RateLimitMiddleware"
]