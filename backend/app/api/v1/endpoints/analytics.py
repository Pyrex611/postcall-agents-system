"""
Analytics and reporting endpoints
"""
import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_, or_, case, text
import datetime
import statistics

from app.core.database import get_db
from app.api.dependencies import get_current_user, get_current_manager
from app.models.call import Call, CallStatus
from app.models.user import User
from app.schemas.analytics import (
    TeamMetricsResponse,
    UserPerformanceResponse,
    CallTrendsResponse,
    QualityMetricsResponse,
    SentimentTrendsResponse
)

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/team", response_model=TeamMetricsResponse)
async def get_team_metrics(
    start_date: Optional[str] = Query(None, description="Start date in ISO format (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date in ISO format (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_manager)
):
    """
    Get team-wide analytics and metrics.
    """
    try:
        # Parse dates
        if start_date:
            try:
                start_dt = datetime.datetime.fromisoformat(start_date + "T00:00:00")
            except ValueError:
                start_dt = datetime.datetime.strptime(start_date, "%Y-%m-%d")
        else:
            # Default to 30 days ago
            start_dt = datetime.datetime.utcnow() - datetime.timedelta(days=30)
        
        if end_date:
            try:
                end_dt = datetime.datetime.fromisoformat(end_date + "T23:59:59")
            except ValueError:
                end_dt = datetime.datetime.strptime(end_date, "%Y-%m-%d") + datetime.timedelta(days=1)
        else:
            end_dt = datetime.datetime.utcnow()
        
        # Get team calls within date range
        stmt = select(Call).where(
            Call.tenant_id == current_user.tenant_id,
            Call.created_at >= start_dt,
            Call.created_at <= end_dt
        )
        result = await db.execute(stmt)
        calls = result.scalars().all()
        
        # Get team users
        user_stmt = select(User).where(
            User.tenant_id == current_user.tenant_id,
            User.is_active == True
        )
        user_result = await db.execute(user_stmt)
        users = user_result.scalars().all()
        
        # Calculate metrics
        total_calls = len(calls)
        completed_calls = [c for c in calls if c.status == CallStatus.COMPLETED]
        failed_calls = [c for c in calls if c.status == CallStatus.FAILED]
        
        # Calculate quality scores
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
        
        avg_quality_score = statistics.mean(quality_scores) if quality_scores else 0
        avg_sentiment_score = statistics.mean(sentiment_scores) if sentiment_scores else 0
        avg_call_duration = statistics.mean(call_durations) if call_durations else 0
        
        # Calculate by call type
        call_types = {}
        for call in calls:
            call_type = call.call_type or "unknown"
            call_types[call_type] = call_types.get(call_type, 0) + 1
        
        # Calculate by user
        user_metrics = []
        for user in users:
            user_calls = [c for c in calls if c.user_id == user.id]
            user_completed = [c for c in user_calls if c.status == CallStatus.COMPLETED]
            
            if user_calls:
                user_quality_scores = []
                user_sentiment_scores = []
                
                for call in user_completed:
                    if call.quality_metrics and call.quality_metrics.get("call_quality_score"):
                        user_quality_scores.append(call.quality_metrics.get("call_quality_score"))
                    if call.insights and call.insights.get("sentiment_score"):
                        user_sentiment_scores.append(call.insights.get("sentiment_score"))
                
                user_metrics.append({
                    "user_id": user.id,
                    "user_name": user.full_name,
                    "total_calls": len(user_calls),
                    "completed_calls": len(user_completed),
                    "avg_quality_score": statistics.mean(user_quality_scores) if user_quality_scores else 0,
                    "avg_sentiment_score": statistics.mean(user_sentiment_scores) if user_sentiment_scores else 0,
                    "completion_rate": (len(user_completed) / len(user_calls)) * 100 if user_calls else 0
                })
        
        # Calculate trends (daily for last 30 days)
        daily_trends = {}
        for i in range(30):
            date = (datetime.datetime.utcnow() - datetime.timedelta(days=i)).date()
            daily_trends[date.isoformat()] = {
                "total_calls": 0,
                "completed_calls": 0,
                "avg_quality": 0,
                "avg_sentiment": 0
            }
        
        # Aggregate daily data
        for call in completed_calls:
            if call.created_at:
                date_key = call.created_at.date().isoformat()
                if date_key in daily_trends:
                    daily_trends[date_key]["total_calls"] += 1
                    daily_trends[date_key]["completed_calls"] += 1
                    
                    # Update averages
                    if call.quality_metrics and call.quality_metrics.get("call_quality_score"):
                        current_avg = daily_trends[date_key]["avg_quality"]
                        count = daily_trends[date_key]["completed_calls"]
                        daily_trends[date_key]["avg_quality"] = (
                            (current_avg * (count - 1) + call.quality_metrics.get("call_quality_score")) / count
                            if count > 0 else 0
                        )
                    
                    if call.insights and call.insights.get("sentiment_score"):
                        current_avg = daily_trends[date_key]["avg_sentiment"]
                        count = daily_trends[date_key]["completed_calls"]
                        daily_trends[date_key]["avg_sentiment"] = (
                            (current_avg * (count - 1) + call.insights.get("sentiment_score")) / count
                            if count > 0 else 0
                        )
        
        # Sort trends by date
        sorted_trends = sorted(
            [{"date": k, **v} for k, v in daily_trends.items()],
            key=lambda x: x["date"]
        )
        
        logger.info(f"Team metrics retrieved for tenant {current_user.tenant_id}")
        
        return TeamMetricsResponse(
            period_start=start_dt.isoformat(),
            period_end=end_dt.isoformat(),
            total_calls=total_calls,
            completed_calls=len(completed_calls),
            failed_calls=len(failed_calls),
            completion_rate=(len(completed_calls) / total_calls * 100) if total_calls > 0 else 0,
            avg_quality_score=round(avg_quality_score, 2),
            avg_sentiment_score=round(avg_sentiment_score, 2),
            avg_call_duration=round(avg_call_duration, 2),
            total_users=len(users),
            call_types=call_types,
            user_metrics=user_metrics,
            daily_trends=sorted_trends
        )
        
    except Exception as e:
        logger.error(f"Failed to get team metrics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get team metrics: {str(e)}"
        )

@router.get("/user/{user_id}/performance", response_model=UserPerformanceResponse)
async def get_user_performance(
    user_id: str,
    period: str = Query("month", regex="^(week|month|quarter|year)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_manager)
):
    """
    Get performance metrics for a specific user.
    """
    try:
        # Check if current user has permission to view this user's metrics
        if current_user.role not in ["admin", "super_admin"] and user_id != current_user.id:
            # Managers can only view their team members
            # This would require a team structure table - simplified for now
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to view this user's metrics"
            )
        
        # Get user
        user_stmt = select(User).where(
            User.id == user_id,
            User.tenant_id == current_user.tenant_id,
            User.is_active == True
        )
        user_result = await db.execute(user_stmt)
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Calculate date range based on period
        end_dt = datetime.datetime.utcnow()
        if period == "week":
            start_dt = end_dt - datetime.timedelta(days=7)
        elif period == "month":
            start_dt = end_dt - datetime.timedelta(days=30)
        elif period == "quarter":
            start_dt = end_dt - datetime.timedelta(days=90)
        else:  # year
            start_dt = end_dt - datetime.timedelta(days=365)
        
        # Get user's calls within date range
        stmt = select(Call).where(
            Call.tenant_id == current_user.tenant_id,
            Call.user_id == user_id,
            Call.created_at >= start_dt,
            Call.created_at <= end_dt
        ).order_by(desc(Call.created_at))
        
        result = await db.execute(stmt)
        calls = result.scalars().all()
        
        completed_calls = [c for c in calls if c.status == CallStatus.COMPLETED]
        
        # Calculate metrics
        quality_scores = []
        sentiment_scores = []
        call_durations = []
        strengths = []
        improvements = []
        
        for call in completed_calls:
            if call.quality_metrics:
                if call.quality_metrics.get("call_quality_score"):
                    quality_scores.append(call.quality_metrics.get("call_quality_score"))
                if call.quality_metrics.get("strengths"):
                    strengths.extend(call.quality_metrics.get("strengths", []))
                if call.quality_metrics.get("improvements"):
                    improvements.extend(call.quality_metrics.get("improvements", []))
            
            if call.insights and call.insights.get("sentiment_score"):
                sentiment_scores.append(call.insights.get("sentiment_score"))
            
            if call.duration_seconds:
                call_durations.append(call.duration_seconds)
        
        # Get most common strengths and improvements
        from collections import Counter
        top_strengths = [item for item, count in Counter(strengths).most_common(5)]
        top_improvements = [item for item, count in Counter(improvements).most_common(5)]
        
        # Calculate trends by week
        weekly_trends = {}
        for i in range(12):  # Last 12 weeks
            week_start = end_dt - datetime.timedelta(weeks=i+1)
            week_end = end_dt - datetime.timedelta(weeks=i)
            week_key = week_start.strftime("%Y-%W")
            
            week_calls = [
                c for c in completed_calls 
                if week_start <= c.created_at <= week_end
            ]
            
            week_quality_scores = [
                c.quality_metrics.get("call_quality_score")
                for c in week_calls
                if c.quality_metrics and c.quality_metrics.get("call_quality_score")
            ]
            
            weekly_trends[week_key] = {
                "week_start": week_start.isoformat(),
                "total_calls": len(week_calls),
                "avg_quality": statistics.mean(week_quality_scores) if week_quality_scores else 0,
                "avg_sentiment": 0  # Could add sentiment if needed
            }
        
        # Get recent calls for details
        recent_calls = []
        for call in calls[:10]:  # Last 10 calls
            recent_calls.append({
                "call_id": call.id,
                "prospect_name": call.prospect_name,
                "company_name": call.company_name,
                "created_at": call.created_at.isoformat() if call.created_at else None,
                "quality_score": call.quality_metrics.get("call_quality_score") if call.quality_metrics else None,
                "sentiment_score": call.insights.get("sentiment_score") if call.insights else None,
                "status": call.status.value
            })
        
        logger.info(f"User performance retrieved for user {user_id}")
        
        return UserPerformanceResponse(
            user_id=user_id,
            user_name=user.full_name,
            user_email=user.email,
            period=period,
            period_start=start_dt.isoformat(),
            period_end=end_dt.isoformat(),
            total_calls=len(calls),
            completed_calls=len(completed_calls),
            completion_rate=(len(completed_calls) / len(calls) * 100) if calls else 0,
            avg_quality_score=round(statistics.mean(quality_scores), 2) if quality_scores else 0,
            avg_sentiment_score=round(statistics.mean(sentiment_scores), 2) if sentiment_scores else 0,
            avg_call_duration=round(statistics.mean(call_durations), 2) if call_durations else 0,
            top_strengths=top_strengths,
            top_improvements=top_improvements,
            weekly_trends=list(weekly_trends.values()),
            recent_calls=recent_calls
        )
        
    except Exception as e:
        logger.error(f"Failed to get user performance: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user performance: {str(e)}"
        )

@router.get("/call-trends", response_model=CallTrendsResponse)
async def get_call_trends(
    metric: str = Query("count", regex="^(count|quality|sentiment|duration)$"),
    group_by: str = Query("day", regex="^(day|week|month)$"),
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_manager)
):
    """
    Get call trends over time.
    """
    try:
        end_dt = datetime.datetime.utcnow()
        start_dt = end_dt - datetime.timedelta(days=days)
        
        # Get calls in date range
        stmt = select(Call).where(
            Call.tenant_id == current_user.tenant_id,
            Call.created_at >= start_dt,
            Call.created_at <= end_dt,
            Call.status == CallStatus.COMPLETED
        )
        
        result = await db.execute(stmt)
        calls = result.scalars().all()
        
        # Initialize time buckets
        trends = []
        
        if group_by == "day":
            # Group by day
            current_date = start_dt.date()
            while current_date <= end_dt.date():
                day_calls = [
                    c for c in calls 
                    if c.created_at and c.created_at.date() == current_date
                ]
                
                if metric == "count":
                    value = len(day_calls)
                elif metric == "quality":
                    scores = [
                        c.quality_metrics.get("call_quality_score")
                        for c in day_calls
                        if c.quality_metrics and c.quality_metrics.get("call_quality_score")
                    ]
                    value = statistics.mean(scores) if scores else 0
                elif metric == "sentiment":
                    scores = [
                        c.insights.get("sentiment_score")
                        for c in day_calls
                        if c.insights and c.insights.get("sentiment_score")
                    ]
                    value = statistics.mean(scores) if scores else 0
                else:  # duration
                    durations = [c.duration_seconds for c in day_calls if c.duration_seconds]
                    value = statistics.mean(durations) if durations else 0
                
                trends.append({
                    "period": current_date.isoformat(),
                    "value": round(value, 2),
                    "label": current_date.strftime("%b %d")
                })
                
                current_date += datetime.timedelta(days=1)
        
        elif group_by == "week":
            # Group by week
            current_week = start_dt.isocalendar()[1]
            current_year = start_dt.isocalendar()[0]
            
            while True:
                week_calls = [
                    c for c in calls 
                    if c.created_at and c.created_at.isocalendar()[:2] == (current_year, current_week)
                ]
                
                if metric == "count":
                    value = len(week_calls)
                elif metric == "quality":
                    scores = [
                        c.quality_metrics.get("call_quality_score")
                        for c in week_calls
                        if c.quality_metrics and c.quality_metrics.get("call_quality_score")
                    ]
                    value = statistics.mean(scores) if scores else 0
                elif metric == "sentiment":
                    scores = [
                        c.insights.get("sentiment_score")
                        for c in week_calls
                        if c.insights and c.insights.get("sentiment_score")
                    ]
                    value = statistics.mean(scores) if scores else 0
                else:  # duration
                    durations = [c.duration_seconds for c in week_calls if c.duration_seconds]
                    value = statistics.mean(durations) if durations else 0
                
                week_start = datetime.datetime.fromisocalendar(current_year, current_week, 1)
                trends.append({
                    "period": f"{current_year}-W{current_week:02d}",
                    "value": round(value, 2),
                    "label": f"Week {current_week}"
                })
                
                # Move to next week
                current_week += 1
                if current_week > 52:
                    current_week = 1
                    current_year += 1
                
                week_end = datetime.datetime.fromisocalendar(current_year, current_week, 1)
                if week_end > end_dt:
                    break
        
        else:  # month
            # Group by month
            current_month = start_dt.month
            current_year = start_dt.year
            
            while True:
                month_calls = [
                    c for c in calls 
                    if c.created_at and c.created_at.month == current_month and c.created_at.year == current_year
                ]
                
                if metric == "count":
                    value = len(month_calls)
                elif metric == "quality":
                    scores = [
                        c.quality_metrics.get("call_quality_score")
                        for c in month_calls
                        if c.quality_metrics and c.quality_metrics.get("call_quality_score")
                    ]
                    value = statistics.mean(scores) if scores else 0
                elif metric == "sentiment":
                    scores = [
                        c.insights.get("sentiment_score")
                        for c in month_calls
                        if c.insights and c.insights.get("sentiment_score")
                    ]
                    value = statistics.mean(scores) if scores else 0
                else:  # duration
                    durations = [c.duration_seconds for c in month_calls if c.duration_seconds]
                    value = statistics.mean(durations) if durations else 0
                
                trends.append({
                    "period": f"{current_year}-{current_month:02d}",
                    "value": round(value, 2),
                    "label": datetime.date(current_year, current_month, 1).strftime("%b %Y")
                })
                
                # Move to next month
                current_month += 1
                if current_month > 12:
                    current_month = 1
                    current_year += 1
                
                month_end = datetime.datetime(current_year, current_month, 1)
                if month_end > end_dt:
                    break
        
        logger.info(f"Call trends retrieved for tenant {current_user.tenant_id}")
        
        return CallTrendsResponse(
            metric=metric,
            group_by=group_by,
            period_days=days,
            trends=trends,
            summary={
                "average": statistics.mean([t["value"] for t in trends]) if trends else 0,
                "min": min([t["value"] for t in trends]) if trends else 0,
                "max": max([t["value"] for t in trends]) if trends else 0,
                "total": sum([t["value"] for t in trends]) if trends else 0
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to get call trends: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get call trends: {str(e)}"
        )

@router.get("/quality-metrics", response_model=QualityMetricsResponse)
async def get_quality_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_manager)
):
    """
    Get detailed quality metrics analysis.
    """
    try:
        # Get completed calls from last 90 days
        start_dt = datetime.datetime.utcnow() - datetime.timedelta(days=90)
        
        stmt = select(Call).where(
            Call.tenant_id == current_user.tenant_id,
            Call.created_at >= start_dt,
            Call.status == CallStatus.COMPLETED,
            Call.quality_metrics.isnot(None)
        )
        
        result = await db.execute(stmt)
        calls = result.scalars().all()
        
        # Extract quality metrics
        quality_scores = []
        strengths = []
        improvements = []
        
        for call in calls:
            if call.quality_metrics:
                score = call.quality_metrics.get("call_quality_score")
                if score:
                    quality_scores.append(score)
                
                # Collect strengths and improvements
                call_strengths = call.quality_metrics.get("strengths", [])
                if isinstance(call_strengths, list):
                    strengths.extend(call_strengths)
                elif isinstance(call_strengths, str):
                    strengths.append(call_strengths)
                
                call_improvements = call.quality_metrics.get("improvements", [])
                if isinstance(call_improvements, list):
                    improvements.extend(call_improvements)
                elif isinstance(call_improvements, str):
                    improvements.append(call_improvements)
        
        # Calculate score distribution
        score_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for score in quality_scores:
            if 1 <= score <= 5:
                rounded = round(score)
                score_distribution[rounded] = score_distribution.get(rounded, 0) + 1
        
        # Get most common strengths and improvements
        from collections import Counter
        top_strengths = Counter(strengths).most_common(10)
        top_improvements = Counter(improvements).most_common(10)
        
        # Calculate by call type
        quality_by_type = {}
        for call in calls:
            call_type = call.call_type or "unknown"
            score = call.quality_metrics.get("call_quality_score") if call.quality_metrics else None
            
            if score:
                if call_type not in quality_by_type:
                    quality_by_type[call_type] = {"scores": [], "count": 0}
                quality_by_type[call_type]["scores"].append(score)
                quality_by_type[call_type]["count"] += 1
        
        # Calculate averages by type
        type_metrics = {}
        for call_type, data in quality_by_type.items():
            if data["scores"]:
                type_metrics[call_type] = {
                    "average_score": statistics.mean(data["scores"]),
                    "call_count": data["count"],
                    "score_distribution": {}
                }
                
                # Distribution for this type
                for i in range(1, 6):
                    type_metrics[call_type]["score_distribution"][i] = sum(
                        1 for score in data["scores"] if round(score) == i
                    )
        
        logger.info(f"Quality metrics retrieved for tenant {current_user.tenant_id}")
        
        return QualityMetricsResponse(
            total_calls_analyzed=len(calls),
            average_quality_score=round(statistics.mean(quality_scores), 2) if quality_scores else 0,
            median_quality_score=statistics.median(quality_scores) if quality_scores else 0,
            quality_score_std=round(statistics.stdev(quality_scores), 2) if len(quality_scores) > 1 else 0,
            score_distribution=[
                {"score": score, "count": count, "percentage": (count / len(quality_scores) * 100) if quality_scores else 0}
                for score, count in score_distribution.items()
            ],
            top_strengths=[
                {"strength": item, "count": count, "percentage": (count / len(strengths) * 100) if strengths else 0}
                for item, count in top_strengths
            ],
            top_improvements=[
                {"improvement": item, "count": count, "percentage": (count / len(improvements) * 100) if improvements else 0}
                for item, count in top_improvements
            ],
            quality_by_type=type_metrics,
            recommendations=[
                {
                    "title": "Focus on Top Improvements",
                    "description": f"Address '{top_improvements[0][0]}' which appears in {top_improvements[0][1]} calls",
                    "priority": "high"
                },
                {
                    "title": "Leverage Top Strengths",
                    "description": f"Reinforce '{top_strengths[0][0]}' across all sales conversations",
                    "priority": "medium"
                }
            ]
        )
        
    except Exception as e:
        logger.error(f"Failed to get quality metrics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get quality metrics: {str(e)}"
        )

@router.get("/dashboard")
async def get_dashboard_data(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get comprehensive dashboard data.
    """
    try:
        # Get recent 30 days data
        start_dt = datetime.datetime.utcnow() - datetime.timedelta(days=30)
        
        # Get calls
        call_stmt = select(Call).where(
            Call.tenant_id == current_user.tenant_id,
            Call.created_at >= start_dt
        )
        call_result = await db.execute(call_stmt)
        calls = call_result.scalars().all()
        
        completed_calls = [c for c in calls if c.status == CallStatus.COMPLETED]
        
        # Calculate quick stats
        quick_stats = {
            "total_calls": len(calls),
            "completed_calls": len(completed_calls),
            "avg_processing_time": 0,
            "crm_sync_success_rate": 0
        }
        
        # Calculate average processing time
        processing_times = []
        for call in completed_calls:
            if call.processing_started_at and call.processing_completed_at:
                processing_time = (call.processing_completed_at - call.processing_started_at).total_seconds()
                processing_times.append(processing_time)
        
        if processing_times:
            quick_stats["avg_processing_time"] = statistics.mean(processing_times)
        
        # Calculate CRM sync success rate
        crm_success_count = 0
        for call in completed_calls:
            if call.crm_update_result and call.crm_update_result.get("status") == "success":
                crm_success_count += 1
        
        if completed_calls:
            quick_stats["crm_sync_success_rate"] = (crm_success_count / len(completed_calls)) * 100
        
        # Get recent calls
        recent_calls = []
        for call in sorted(calls, key=lambda x: x.created_at, reverse=True)[:5]:
            recent_calls.append({
                "id": call.id,
                "prospect_name": call.prospect_name,
                "company_name": call.company_name,
                "status": call.status.value,
                "created_at": call.created_at.isoformat() if call.created_at else None,
                "quality_score": call.quality_metrics.get("call_quality_score") if call.quality_metrics else None
            })
        
        # Get user stats (if manager/admin)
        user_stats = []
        if current_user.role in ["manager", "admin", "super_admin"]:
            user_stmt = select(User).where(
                User.tenant_id == current_user.tenant_id,
                User.is_active == True
            )
            user_result = await db.execute(user_stmt)
            users = user_result.scalars().all()
            
            for user in users:
                user_calls = [c for c in calls if c.user_id == user.id]
                user_completed = [c for c in user_calls if c.status == CallStatus.COMPLETED]
                
                user_stats.append({
                    "user_id": user.id,
                    "user_name": user.full_name,
                    "total_calls": len(user_calls),
                    "completed_calls": len(user_completed),
                    "completion_rate": (len(user_completed) / len(user_calls) * 100) if user_calls else 0
                })
        
        # Get system status
        system_status = {
            "api_health": "healthy",
            "database_health": "healthy",
            "queue_health": "healthy",
            "storage_health": "healthy"
        }
        
        logger.info(f"Dashboard data retrieved for user {current_user.id}")
        
        return {
            "quick_stats": quick_stats,
            "recent_calls": recent_calls,
            "user_stats": user_stats,
            "system_status": system_status,
            "last_updated": datetime.datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get dashboard data: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get dashboard data: {str(e)}"
        )