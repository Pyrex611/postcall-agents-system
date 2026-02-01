"""
Database models for SalesIntel AI.
"""
from .base import Base
from .user import User, UserRole
from .tenant import Tenant
from .call import Call, CallStatus
from .crm_config import CRMConfig
from .webhook import Webhook

__all__ = [
    "Base",
    "User",
    "UserRole", 
    "Tenant",
    "Call",
    "CallStatus",
    "CRMConfig",
    "Webhook"
]

# Import all models to ensure they're registered with Base
from . import user, tenant, call, crm_config, webhook