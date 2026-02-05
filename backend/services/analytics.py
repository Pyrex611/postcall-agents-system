"""
Analytics API endpoints
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import Optional, List
from datetime import datetime, timedelta

from core.database import get_db
from core.security import get_current_organization_id
from models.call import Call
from models.__init__ import Insight, QualityMetric
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/dashboard")
async def get_dashboard_stats(
    days: int = Query(30, description="Number of days to analyze"),
    org_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db)
):
    """
    Get dashboard statistics
    
    Returns key metrics for the specified time period
    """
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Total calls
    total_calls = db.query(func.count(Call.id)).filter(
        and_(
            Call.organization_id == org_id,
            Call.created_at >= start_date,
            Call.status == "completed"
        )
    ).scalar()
    
    # Average sentiment
    avg_sentiment = db.query(func.avg(Insight.sentiment_score)).join(
        Call
    ).filter(
        and_(
            Call.organization_id == org_id,
            Call.created_at >= start_date,
            Call.status == "completed"
        )
    ).scalar()
    
    # Average quality
    avg_quality = db.query(func.avg(QualityMetric.quality_score)).join(
        Call
    ).filter(
        and_(
            Call.organization_id == org_id,
            Call.created_at >= start_date,
            Call.status == "completed"
        )
    ).scalar()
    
    # Average duration
    avg_duration = db.query(func.avg(Call.duration_seconds)).filter(
        and_(
            Call.organization_id == org_id,
            Call.created_at >= start_date,
            Call.status == "completed",
            Call.duration_seconds.isnot(None)
        )
    ).scalar()
    
    # Meeting requests
    meetings_requested = db.query(func.count(QualityMetric.id)).join(
        Call
    ).filter(
        and_(
            Call.organization_id == org_id,
            Call.created_at >= start_date,
            QualityMetric.asked_for_meeting == True
        )
    ).scalar()
    
    return {
        "period_days": days,
        "total_calls": total_calls or 0,
        "avg_sentiment_score": round(float(avg_sentiment), 2) if avg_sentiment else None,
        "avg_quality_score": round(float(avg_quality), 2) if avg_quality else None,
        "avg_duration_minutes": round(float(avg_duration) / 60, 2) if avg_duration else None,
        "meetings_requested": meetings_requested or 0,
        "meeting_request_rate": round(
            (meetings_requested / total_calls * 100) if total_calls else 0,
            2
        )
    }


@router.get("/trends")
async def get_trends(
    days: int = Query(30, description="Number of days to analyze"),
    org_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db)
):
    """
    Get trend data over time
    
    Returns daily aggregates
    """
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Daily call counts
    daily_calls = db.query(
        func.date(Call.created_at).label('date'),
        func.count(Call.id).label('count')
    ).filter(
        and_(
            Call.organization_id == org_id,
            Call.created_at >= start_date,
            Call.status == "completed"
        )
    ).group_by(
        func.date(Call.created_at)
    ).order_by(
        func.date(Call.created_at)
    ).all()
    
    return {
        "daily_calls": [
            {"date": str(date), "count": count}
            for date, count in daily_calls
        ]
    }


@router.get("/top-performers")
async def get_top_performers(
    limit: int = Query(10, description="Number of performers to return"),
    org_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db)
):
    """
    Get top performers by quality score
    """
    from models.user import User
    
    performers = db.query(
        User.full_name,
        User.email,
        func.count(Call.id).label('total_calls'),
        func.avg(QualityMetric.quality_score).label('avg_quality'),
        func.avg(Insight.sentiment_score).label('avg_sentiment')
    ).join(
        Call, Call.user_id == User.id
    ).join(
        QualityMetric, QualityMetric.call_id == Call.id
    ).join(
        Insight, Insight.call_id == Call.id
    ).filter(
        Call.organization_id == org_id,
        Call.status == "completed"
    ).group_by(
        User.id, User.full_name, User.email
    ).order_by(
        func.avg(QualityMetric.quality_score).desc()
    ).limit(limit).all()
    
    return {
        "top_performers": [
            {
                "name": p.full_name,
                "email": p.email,
                "total_calls": p.total_calls,
                "avg_quality_score": round(float(p.avg_quality), 2),
                "avg_sentiment_score": round(float(p.avg_sentiment), 2)
            }
            for p in performers
        ]
    }
