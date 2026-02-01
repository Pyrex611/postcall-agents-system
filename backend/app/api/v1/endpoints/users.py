"""
User management endpoints
"""
import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_
from sqlalchemy.orm import joinedload

from app.core.database import get_db
from app.api.dependencies import get_current_user, get_current_admin, PaginationParams
from app.models.user import User, UserCreate, UserUpdate, UserResponse, UserRole
from app.schemas.user import User as UserSchema
from app.core.security import get_password_hash

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/", response_model=List[UserResponse])
async def list_users(
    pagination: PaginationParams = Depends(),
    role_filter: Optional[str] = Query(None, regex="^(user|manager|admin|super_admin)$"),
    active_only: bool = Query(True),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    List users in current tenant (admin only).
    """
    try:
        # Build query conditions
        conditions = [User.tenant_id == current_user.tenant_id]
        
        if active_only:
            conditions.append(User.is_active == True)
        
        if role_filter:
            conditions.append(User.role == role_filter)
        
        if search:
            search_conditions = [
                User.email.ilike(f"%{search}%"),
                User.full_name.ilike(f"%{search}%"),
                User.username.ilike(f"%{search}%")
            ]
            conditions.append(or_(*search_conditions))
        
        # Build query
        stmt = select(User).where(and_(*conditions))
        
        # Apply sorting
        sort_column = getattr(User, pagination.sort_by, User.created_at)
        if pagination.sort_order == "desc":
            stmt = stmt.order_by(desc(sort_column))
        else:
            stmt = stmt.order_by(sort_column)
        
        # Apply pagination
        stmt = stmt.offset(pagination.skip).limit(pagination.limit)
        
        result = await db.execute(stmt)
        users = result.scalars().all()
        
        return [UserResponse.from_orm(user) for user in users]
        
    except Exception as e:
        logger.error(f"Failed to list users: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list users: {str(e)}"
        )

@router.post("/", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Create a new user (admin only).
    """
    try:
        # Check if user already exists
        existing_stmt = select(User).where(
            User.email == user_data.email,
            User.tenant_id == current_user.tenant_id
        )
        existing_result = await db.execute(existing_stmt)
        existing_user = existing_result.scalar_one_or_none()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )
        
        # Hash password
        hashed_password = get_password_hash(user_data.password)
        
        # Create user
        user = User(
            email=user_data.email,
            username=user_data.username or user_data.email.split('@')[0],
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            role=user_data.role or UserRole.USER,
            is_active=True,
            tenant_id=current_user.tenant_id,
            created_by=current_user.id
        )
        
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        logger.info(f"User created: {user.email} by {current_user.email}")
        
        return UserResponse.from_orm(user)
        
    except Exception as e:
        logger.error(f"Failed to create user: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
        )

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get user details by ID (admin only).
    """
    try:
        stmt = select(User).where(
            User.id == user_id,
            User.tenant_id == current_user.tenant_id
        )
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return UserResponse.from_orm(user)
        
    except Exception as e:
        logger.error(f"Failed to get user: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user: {str(e)}"
        )

@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Update user details (admin only).
    """
    try:
        # Get user
        stmt = select(User).where(
            User.id == user_id,
            User.tenant_id == current_user.tenant_id
        )
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Prevent modifying super_admin unless current user is super_admin
        if user.role == UserRole.SUPER_ADMIN and current_user.role != UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot modify super admin user"
            )
        
        # Update fields
        update_data = user_update.dict(exclude_unset=True)
        
        if "password" in update_data and update_data["password"]:
            update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
        
        # Remove fields that shouldn't be updated
        update_data.pop("id", None)
        update_data.pop("tenant_id", None)
        update_data.pop("created_at", None)
        
        # Apply updates
        for field, value in update_data.items():
            if hasattr(user, field):
                setattr(user, field, value)
        
        user.updated_at = datetime.datetime.utcnow()
        user.updated_by = current_user.id
        
        await db.commit()
        await db.refresh(user)
        
        logger.info(f"User updated: {user.email} by {current_user.email}")
        
        return UserResponse.from_orm(user)
        
    except Exception as e:
        logger.error(f"Failed to update user: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user: {str(e)}"
        )

@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Delete a user (admin only - soft delete).
    """
    try:
        # Don't allow deleting yourself
        if user_id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own account"
            )
        
        # Get user
        stmt = select(User).where(
            User.id == user_id,
            User.tenant_id == current_user.tenant_id,
            User.is_active == True
        )
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Prevent deleting super_admin unless current user is super_admin
        if user.role == UserRole.SUPER_ADMIN and current_user.role != UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot delete super admin user"
            )
        
        # Soft delete
        user.is_active = False
        user.deactivated_at = datetime.datetime.utcnow()
        user.deactivated_by = current_user.id
        
        await db.commit()
        
        logger.info(f"User deactivated: {user.email} by {current_user.email}")
        
        return {"message": "User deactivated successfully"}
        
    except Exception as e:
        logger.error(f"Failed to delete user: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete user: {str(e)}"
        )

@router.post("/{user_id}/activate")
async def activate_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Activate a deactivated user (admin only).
    """
    try:
        stmt = select(User).where(
            User.id == user_id,
            User.tenant_id == current_user.tenant_id,
            User.is_active == False
        )
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found or already active"
            )
        
        # Reactivate user
        user.is_active = True
        user.deactivated_at = None
        user.deactivated_by = None
        user.reactivated_at = datetime.datetime.utcnow()
        user.reactivated_by = current_user.id
        
        await db.commit()
        
        logger.info(f"User activated: {user.email} by {current_user.email}")
        
        return {"message": "User activated successfully"}
        
    except Exception as e:
        logger.error(f"Failed to activate user: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to activate user: {str(e)}"
        )

@router.post("/{user_id}/reset-password")
async def admin_reset_password(
    user_id: str,
    new_password: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Reset user password (admin only).
    """
    try:
        stmt = select(User).where(
            User.id == user_id,
            User.tenant_id == current_user.tenant_id
        )
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Update password
        hashed_password = get_password_hash(new_password)
        user.hashed_password = hashed_password
        user.password_reset_at = datetime.datetime.utcnow()
        user.password_reset_by = current_user.id
        
        await db.commit()
        
        logger.info(f"Password reset for user: {user.email} by {current_user.email}")
        
        return {"message": "Password reset successfully"}
        
    except Exception as e:
        logger.error(f"Failed to reset password: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset password: {str(e)}"
        )

@router.get("/{user_id}/stats")
async def get_user_stats(
    user_id: str,
    period_days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Get detailed statistics for a user.
    """
    try:
        # Verify user exists and belongs to tenant
        user_stmt = select(User).where(
            User.id == user_id,
            User.tenant_id == current_user.tenant_id
        )
        user_result = await db.execute(user_stmt)
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Calculate date range
        end_dt = datetime.datetime.utcnow()
        start_dt = end_dt - datetime.timedelta(days=period_days)
        
        # Get user's calls
        from app.models.call import Call
        call_stmt = select(Call).where(
            Call.tenant_id == current_user.tenant_id,
            Call.user_id == user_id,
            Call.created_at >= start_dt,
            Call.created_at <= end_dt
        )
        call_result = await db.execute(call_stmt)
        calls = call_result.scalars().all()
        
        completed_calls = [c for c in calls if c.status == CallStatus.COMPLETED]
        
        # Calculate statistics
        quality_scores = []
        sentiment_scores = []
        call_durations = []
        
        for call in completed_calls:
            if call.quality_metrics and call.quality_metrics.get("call_quality_score"):
                quality_scores.append(call.quality_metrics.get("call_quality_score"))
            if call.insights and call.insights.get("sentiment_score"):
                sentiment_scores.append(call.insights.get("sentiment_score"))
            if call.duration_seconds:
                call_durations.append(call.duration_seconds)
        
        # Calculate trends by week
        weekly_stats = {}
        for i in range(min(period_days // 7, 12)):  # Last 12 weeks max
            week_start = end_dt - datetime.timedelta(weeks=i+1)
            week_end = end_dt - datetime.timedelta(weeks=i)
            
            week_calls = [
                c for c in completed_calls 
                if week_start <= c.created_at <= week_end
            ]
            
            week_quality = [
                c.quality_metrics.get("call_quality_score")
                for c in week_calls
                if c.quality_metrics and c.quality_metrics.get("call_quality_score")
            ]
            
            weekly_stats[f"Week {i+1}"] = {
                "week_start": week_start.isoformat(),
                "total_calls": len(week_calls),
                "avg_quality": statistics.mean(week_quality) if week_quality else 0,
                "avg_sentiment": 0  # Could add
            }
        
        return {
            "user_id": user_id,
            "user_name": user.full_name,
            "period_days": period_days,
            "total_calls": len(calls),
            "completed_calls": len(completed_calls),
            "completion_rate": (len(completed_calls) / len(calls) * 100) if calls else 0,
            "avg_quality_score": round(statistics.mean(quality_scores), 2) if quality_scores else 0,
            "avg_sentiment_score": round(statistics.mean(sentiment_scores), 2) if sentiment_scores else 0,
            "avg_call_duration": round(statistics.mean(call_durations), 2) if call_durations else 0,
            "weekly_stats": weekly_stats,
            "first_call_date": min([c.created_at for c in calls], default=None),
            "last_call_date": max([c.created_at for c in calls], default=None)
        }
        
    except Exception as e:
        logger.error(f"Failed to get user stats: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user stats: {str(e)}"
        )

@router.get("/search/email")
async def search_user_by_email(
    email: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Search for a user by email.
    """
    try:
        stmt = select(User).where(
            User.email.ilike(f"%{email}%"),
            User.tenant_id == current_user.tenant_id,
            User.is_active == True
        ).limit(10)
        
        result = await db.execute(stmt)
        users = result.scalars().all()
        
        return [UserResponse.from_orm(user) for user in users]
        
    except Exception as e:
        logger.error(f"Failed to search users: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search users: {str(e)}"
        )