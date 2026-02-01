"""
Dependencies for API endpoints
"""
from typing import Optional, Dict, Any, List
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from app.core.database import get_db
from app.core.security import (
    verify_token, 
    get_current_active_user, 
    get_current_active_superuser
)
from app.models.user import User, UserRole
from app.core.config import settings

logger = logging.getLogger(__name__)

security = HTTPBearer()

# Dependency to get current user from token
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Get current authenticated user.
    """
    token = credentials.credentials
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    
    # Get user from database
    stmt = select(User).where(User.id == user_id, User.is_active == True)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    
    return user

# Dependency to get current user with optional token (for public endpoints)
async def get_current_user_optional(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    Get current authenticated user (optional).
    Returns None if no valid token provided.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    
    token = authorization.replace("Bearer ", "")
    try:
        payload = verify_token(token)
        if payload is None:
            return None
        
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
        
        stmt = select(User).where(User.id == user_id, User.is_active == True)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        return user
    except Exception as e:
        logger.warning(f"Optional auth failed: {str(e)}")
        return None

# Dependency to check if user is admin
async def get_current_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current user only if they are an admin.
    """
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    return current_user

# Dependency to check if user is manager or admin
async def get_current_manager(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current user only if they are a manager or admin.
    """
    if current_user.role not in [UserRole.MANAGER, UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    return current_user

# Dependency to get tenant ID from user
async def get_current_tenant(
    current_user: User = Depends(get_current_user)
) -> str:
    """
    Get current user's tenant ID.
    """
    return current_user.tenant_id

# Dependency for pagination parameters
class PaginationParams:
    def __init__(
        self,
        skip: int = 0,
        limit: int = 100,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ):
        self.skip = max(0, skip)
        self.limit = min(1000, max(1, limit))  # Cap at 1000 for safety
        self.sort_by = sort_by
        self.sort_order = sort_order