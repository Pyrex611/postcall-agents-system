"""
SalesOps AI Platform - FastAPI Backend
Enterprise-grade API with async support, authentication, and task queuing
"""

from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
import logging
from typing import Optional
import time

from backend.config import settings
from backend.database import Database, get_db
from backend.models.database import (
    Organization,
    User,
    Call,
    CallAnalysis,
    DashboardMetrics
)
from backend.api.v1 import (
    auth,
    calls,
    organizations,
    crm,
    analytics,
    playbooks
)
from backend.core.exceptions import (
    AppException,
    NotFoundException,
    UnauthorizedException,
    ForbiddenException
)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan events for startup and shutdown
    """
    # Startup
    logger.info("🚀 Starting SalesOps AI Platform API")
    
    # Initialize database connection pool
    await Database.connect()
    logger.info("✅ Database connected")
    
    # Initialize Redis for task queue
    # await TaskQueue.connect()
    # logger.info("✅ Task queue connected")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down SalesOps AI Platform API")
    await Database.disconnect()
    # await TaskQueue.disconnect()
    logger.info("✅ Cleanup complete")


# Create FastAPI app
app = FastAPI(
    title="SalesOps AI Platform API",
    description="Enterprise sales call intelligence and automation platform",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
)


# ============================================================================
# MIDDLEWARE
# ============================================================================

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add processing time to response headers"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all API requests"""
    logger.info(f"{request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"Status: {response.status_code}")
    return response


# ============================================================================
# EXCEPTION HANDLERS
# ============================================================================

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """Handle custom application exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "message": exc.message,
            "details": exc.details
        }
    )


@app.exception_handler(NotFoundException)
async def not_found_handler(request: Request, exc: NotFoundException):
    """Handle not found exceptions"""
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error": "not_found",
            "message": exc.message
        }
    )


@app.exception_handler(UnauthorizedException)
async def unauthorized_handler(request: Request, exc: UnauthorizedException):
    """Handle unauthorized exceptions"""
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "error": "unauthorized",
            "message": exc.message
        }
    )


@app.exception_handler(ForbiddenException)
async def forbidden_handler(request: Request, exc: ForbiddenException):
    """Handle forbidden exceptions"""
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            "error": "forbidden",
            "message": exc.message
        }
    )


# ============================================================================
# ROOT ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "name": "SalesOps AI Platform API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/api/docs"
    }


@app.get("/health")
async def health_check(db=Depends(get_db)):
    """Health check endpoint"""
    try:
        # Test database connection
        await db.execute("SELECT 1")
        
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )


@app.get("/metrics")
async def metrics():
    """Prometheus-compatible metrics endpoint"""
    # TODO: Implement actual metrics collection
    return {
        "calls_processed_total": 0,
        "api_requests_total": 0,
        "active_users": 0
    }


# ============================================================================
# API ROUTERS
# ============================================================================

# Include all API route modules
app.include_router(
    auth.router,
    prefix="/api/v1/auth",
    tags=["Authentication"]
)

app.include_router(
    organizations.router,
    prefix="/api/v1/organizations",
    tags=["Organizations"]
)

app.include_router(
    calls.router,
    prefix="/api/v1/calls",
    tags=["Calls"]
)

app.include_router(
    crm.router,
    prefix="/api/v1/crm",
    tags=["CRM Integrations"]
)

app.include_router(
    analytics.router,
    prefix="/api/v1/analytics",
    tags=["Analytics"]
)

app.include_router(
    playbooks.router,
    prefix="/api/v1/playbooks",
    tags=["Playbooks"]
)


# ============================================================================
# WEBSOCKET ENDPOINTS (for real-time updates)
# ============================================================================

from fastapi import WebSocket, WebSocketDisconnect
from backend.core.websocket import ConnectionManager

manager = ConnectionManager()


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """
    WebSocket endpoint for real-time call processing updates
    """
    await manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle incoming messages if needed
            await manager.send_personal_message(f"Echo: {data}", client_id)
    except WebSocketDisconnect:
        manager.disconnect(client_id)


# ============================================================================
# STARTUP MESSAGE
# ============================================================================

@app.on_event("startup")
async def startup_message():
    """Log startup information"""
    logger.info("="*60)
    logger.info("SalesOps AI Platform API")
    logger.info("="*60)
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug Mode: {settings.DEBUG}")
    logger.info(f"Database: {settings.DATABASE_URL}")
    logger.info(f"API Docs: http://localhost:8000/api/docs")
    logger.info("="*60)


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info"
    )