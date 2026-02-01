"""
Health check endpoints
"""
import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import redis
import datetime

from app.core.database import get_db
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/")
async def health_check():
    """
    Basic health check endpoint.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "service": "SalesIntel AI API",
        "version": "1.0.0"
    }

@router.get("/detailed")
async def detailed_health_check(
    db: AsyncSession = Depends(get_db)
):
    """
    Detailed health check with dependencies.
    """
    checks = {}
    
    # API service check
    checks["api_service"] = {
        "status": "healthy",
        "timestamp": datetime.datetime.utcnow().isoformat()
    }
    
    # Database check
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = {
            "status": "healthy",
            "response_time_ms": 0,  # Could measure this
            "message": "Database connection successful"
        }
    except Exception as e:
        checks["database"] = {
            "status": "unhealthy",
            "error": str(e),
            "message": "Database connection failed"
        }
    
    # Redis check
    try:
        redis_client = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        redis_client.ping()
        checks["redis"] = {
            "status": "healthy",
            "message": "Redis connection successful"
        }
        redis_client.close()
    except Exception as e:
        checks["redis"] = {
            "status": "unhealthy",
            "error": str(e),
            "message": "Redis connection failed"
        }
    
    # External services (optional checks)
    checks["external_services"] = {
        "google_ai": "configured" if settings.GOOGLE_API_KEY else "not_configured",
        "openai": "configured" if settings.OPENAI_API_KEY else "not_configured",
        "email": "configured" if settings.SMTP_HOST else "not_configured",
        "storage": settings.STORAGE_BACKEND
    }
    
    # Determine overall status
    unhealthy_services = [
        service for service, check in checks.items() 
        if check.get("status") == "unhealthy"
    ]
    
    overall_status = "healthy" if not unhealthy_services else "degraded"
    
    return {
        "status": overall_status,
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "checks": checks,
        "unhealthy_services": unhealthy_services,
        "environment": settings.ENVIRONMENT if hasattr(settings, "ENVIRONMENT") else "unknown"
    }

@router.get("/database")
async def database_health_check(
    db: AsyncSession = Depends(get_db)
):
    """
    Database-specific health check.
    """
    try:
        # Test connection
        start_time = datetime.datetime.utcnow()
        result = await db.execute(text("SELECT 1 as test, NOW() as db_time"))
        end_time = datetime.datetime.utcnow()
        
        row = result.fetchone()
        response_time_ms = (end_time - start_time).total_seconds() * 1000
        
        return {
            "status": "healthy",
            "database_time": str(row["db_time"]) if row else None,
            "response_time_ms": round(response_time_ms, 2),
            "connection_test": "successful"
        }
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail=f"Database connection failed: {str(e)}"
        )

@router.get("/redis")
async def redis_health_check():
    """
    Redis-specific health check.
    """
    try:
        redis_client = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        
        # Test connection and basic operations
        start_time = datetime.datetime.utcnow()
        redis_client.ping()
        end_time = datetime.datetime.utcnow()
        
        # Get Redis info
        info = redis_client.info()
        
        response_time_ms = (end_time - start_time).total_seconds() * 1000
        
        redis_client.close()
        
        return {
            "status": "healthy",
            "response_time_ms": round(response_time_ms, 2),
            "redis_version": info.get("redis_version"),
            "used_memory_human": info.get("used_memory_human"),
            "connected_clients": info.get("connected_clients"),
            "uptime_days": info.get("uptime_in_days")
        }
    except Exception as e:
        logger.error(f"Redis health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "message": "Redis connection failed"
        }

@router.get("/storage")
async def storage_health_check():
    """
    Storage service health check.
    """
    try:
        from app.services.file_storage import FileStorageService
        
        storage_service = FileStorageService()
        result = await storage_service.health_check()
        
        return {
            "status": "healthy" if result.get("healthy") else "unhealthy",
            "backend": settings.STORAGE_BACKEND,
            "details": result
        }
    except Exception as e:
        logger.error(f"Storage health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "backend": settings.STORAGE_BACKEND,
            "error": str(e),
            "message": "Storage service check failed"
        }

@router.get("/queue")
async def queue_health_check():
    """
    Task queue health check.
    """
    try:
        import redis
        from app.tasks.process_call import celery_app
        
        # Check Redis queue connection
        redis_client = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        
        # Get queue stats
        inspector = celery_app.control.inspect()
        active_tasks = inspector.active() or {}
        scheduled_tasks = inspector.scheduled() or {}
        reserved_tasks = inspector.reserved() or {}
        
        # Count tasks by status
        total_active = sum(len(tasks) for tasks in active_tasks.values())
        total_scheduled = sum(len(tasks) for tasks in scheduled_tasks.values())
        total_reserved = sum(len(tasks) for tasks in reserved_tasks.values())
        
        redis_client.close()
        
        return {
            "status": "healthy",
            "workers_available": len(active_tasks) > 0,
            "active_tasks": total_active,
            "scheduled_tasks": total_scheduled,
            "reserved_tasks": total_reserved,
            "total_tasks": total_active + total_scheduled + total_reserved
        }
    except Exception as e:
        logger.error(f"Queue health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "message": "Queue health check failed"
        }

@router.get("/version")
async def version_info():
    """
    Get API version information.
    """
    return {
        "service": "SalesIntel AI",
        "version": "1.0.0",
        "api_version": "v1",
        "build_date": "2024-01-01",  # Should be set from environment
        "git_commit": "unknown",      # Should be set from environment
        "environment": settings.ENVIRONMENT if hasattr(settings, "ENVIRONMENT") else "development"
    }

@router.get("/metrics")
async def service_metrics():
    """
    Get service metrics for monitoring.
    """
    # This would integrate with Prometheus metrics
    # For now, return basic metrics
    
    return {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "metrics": {
            "requests": {
                "total": 0,  # Would come from middleware
                "last_hour": 0,
                "by_endpoint": {}
            },
            "processing": {
                "calls_processed": 0,
                "avg_processing_time": 0,
                "failed_calls": 0
            },
            "system": {
                "memory_usage_mb": 0,  # Would use psutil
                "cpu_percent": 0
            }
        }
    }