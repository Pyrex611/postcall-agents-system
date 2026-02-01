"""
Authentication endpoints
"""
import logging
from datetime import timedelta
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
import secrets

from app.core.database import get_db
from app.core.security import (
    create_access_token, 
    verify_password, 
    get_password_hash,
    create_refresh_token,
    verify_refresh_token
)
from app.core.config import settings
from app.models.user import User, UserCreate, UserLogin, Token, RefreshToken, UserResponse
from app.schemas.user import User as UserSchema
from app.api.dependencies import get_current_user, get_current_admin
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """
    OAuth2 compatible token login.
    """
    # Find user by email or username
    stmt = select(User).where(
        or_(
            User.email == form_data.username,
            User.username == form_data.username
        ),
        User.is_active == True
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email/username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.id, "email": user.email, "role": user.role.value},
        expires_delta=access_token_expires
    )
    
    # Create refresh token
    refresh_token = create_refresh_token(data={"sub": user.id})
    
    # Update last login
    user.last_login = datetime.datetime.utcnow()
    await db.commit()
    
    logger.info(f"User {user.email} logged in successfully")
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": UserResponse.from_orm(user)
    }

@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user account.
    """
    # Check if user already exists
    stmt = select(User).where(User.email == user_data.email)
    result = await db.execute(stmt)
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    user = User(
        email=user_data.email,
        username=user_data.email.split('@')[0],  # Use email prefix as username
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        role=user_data.role if user_data.role else "user",
        is_active=True,
        tenant_id=secrets.token_urlsafe(16)  # Generate initial tenant ID
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # Create access token for immediate login
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.id, "email": user.email, "role": user.role.value},
        expires_delta=access_token_expires
    )
    
    # Send welcome email in background
    email_service = EmailService()
    if email_service.is_configured():
        background_tasks.add_task(
            email_service.send_welcome_email,
            to_email=user.email,
            user_name=user.full_name
        )
    
    logger.info(f"New user registered: {user.email}")
    
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "access_token": access_token
    }

@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_data: RefreshToken,
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh access token using refresh token.
    """
    token = refresh_data.refresh_token
    payload = verify_refresh_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Get user from database
    stmt = select(User).where(User.id == user_id, User.is_active == True)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # Create new access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.id, "email": user.email, "role": user.role.value},
        expires_delta=access_token_expires
    )
    
    # Optionally create new refresh token (rotate)
    new_refresh_token = create_refresh_token(data={"sub": user.id})
    
    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "user": UserResponse.from_orm(user)
    }

@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Logout user (invalidate token on client side).
    """
    # In a stateless JWT system, logout is handled client-side
    # We could implement a token blacklist here if needed
    logger.info(f"User {current_user.email} logged out")
    
    return {"message": "Successfully logged out"}

@router.post("/forgot-password")
async def forgot_password(
    email: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Request password reset.
    """
    # Find user by email
    stmt = select(User).where(User.email == email, User.is_active == True)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        # Don't reveal that user doesn't exist for security
        return {"message": "If an account exists with this email, you will receive a password reset link"}
    
    # Generate reset token
    reset_token = create_access_token(
        data={"sub": user.id, "type": "password_reset"},
        expires_delta=timedelta(hours=24)
    )
    
    # Store reset token in database (simplified - could use a separate table)
    user.reset_token = reset_token
    await db.commit()
    
    # Send reset email in background
    email_service = EmailService()
    if email_service.is_configured():
        background_tasks.add_task(
            email_service.send_password_reset_email,
            to_email=user.email,
            reset_token=reset_token,
            user_name=user.full_name
        )
    
    logger.info(f"Password reset requested for user: {user.email}")
    
    return {"message": "Password reset email sent"}

@router.post("/reset-password")
async def reset_password(
    token: str,
    new_password: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Reset password using token.
    """
    payload = verify_token(token)
    if payload is None or payload.get("type") != "password_reset":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset token"
        )
    
    # Get user from database
    stmt = select(User).where(User.id == user_id, User.is_active == True)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user or user.reset_token != token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    # Update password
    hashed_password = get_password_hash(new_password)
    user.hashed_password = hashed_password
    user.reset_token = None
    await db.commit()
    
    logger.info(f"Password reset for user: {user.email}")
    
    return {"message": "Password has been reset successfully"}

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user information.
    """
    return UserResponse.from_orm(current_user)

@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update current user information.
    """
    # Only allow updating certain fields
    allowed_fields = ["full_name", "avatar_url", "phone_number"]
    
    for field, value in user_update.items():
        if field in allowed_fields and hasattr(current_user, field):
            setattr(current_user, field, value)
    
    await db.commit()
    await db.refresh(current_user)
    
    logger.info(f"User {current_user.email} updated their profile")
    
    return UserResponse.from_orm(current_user)

@router.post("/change-password")
async def change_password(
    current_password: str,
    new_password: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Change password for current user.
    """
    # Verify current password
    if not verify_password(current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Update to new password
    hashed_password = get_password_hash(new_password)
    current_user.hashed_password = hashed_password
    await db.commit()
    
    logger.info(f"User {current_user.email} changed their password")
    
    return {"message": "Password changed successfully"}