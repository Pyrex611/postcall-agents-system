"""
Custom middleware for the application.
"""
import time
import uuid
import logging
from typing import Callable, Dict, Any
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
import redis
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import settings

logger = logging.getLogger(__name__)

class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add request context (ID, timing) and log requests.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Log request start
        start_time = time.time()
        logger.info(
            f"Request started: {request.method} {request.url.path} "
            f"ID: {request_id} Client: {request.client.host if request.client else 'unknown'}"
        )
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate processing time
            process_time = time.time() - start_time
            
            # Add custom headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.4f}"
            
            # Log request completion
            logger.info(
                f"Request completed: {request.method} {request.url.path} "
                f"Status: {response.status_code} "
                f"Time: {process_time:.2f}s "
                f"ID: {request_id}"
            )
            
            return response
            
        except Exception as e:
            # Log error
            process_time = time.time() - start_time
            logger.error(
                f"Request failed: {request.method} {request.url.path} "
                f"Error: {str(e)} "
                f"Time: {process_time:.2f}s "
                f"ID: {request_id}",
                exc_info=True
            )
            raise

class RateLimitMiddleware:
    """
    Rate limiting middleware using Redis.
    """
    
    def __init__(self):
        self.redis_client = None
        if settings.RATE_LIMIT_ENABLED:
            try:
                self.redis_client = redis.Redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                # Test connection
                self.redis_client.ping()
                logger.info("Rate limiting enabled with Redis")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis for rate limiting: {str(e)}")
                self.redis_client = None
    
    async def __call__(self, request: Request, call_next: Callable) -> Response:
        if not settings.RATE_LIMIT_ENABLED or not self.redis_client:
            return await call_next(request)
        
        # Get client identifier
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        client_id = f"{client_ip}:{user_agent}"
        
        # Create rate limit key
        key = f"rate_limit:{client_id}"
        
        try:
            # Use Redis pipeline for atomic operations
            pipe = self.redis_client.pipeline()
            pipe.incr(key)
            pipe.expire(key, settings.RATE_LIMIT_PERIOD)
            results = pipe.execute()
            
            request_count = results[0]
            
            # Check if limit exceeded
            if request_count > settings.RATE_LIMIT_REQUESTS:
                # Add retry-after header
                ttl = self.redis_client.ttl(key)
                response = Response(
                    content="Rate limit exceeded",
                    status_code=429,
                    headers={
                        "Retry-After": str(ttl),
                        "X-RateLimit-Limit": str(settings.RATE_LIMIT_REQUESTS),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(time.time()) + ttl)
                    }
                )
                return response
            
            # Add rate limit headers
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(settings.RATE_LIMIT_REQUESTS)
            response.headers["X-RateLimit-Remaining"] = str(max(0, settings.RATE_LIMIT_REQUESTS - request_count))
            response.headers["X-RateLimit-Reset"] = str(int(time.time()) + self.redis_client.ttl(key))
            
            return response
            
        except Exception as e:
            # If Redis fails, allow the request (fail open)
            logger.error(f"Rate limiting error: {str(e)}")
            return await call_next(request)

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Add security headers
        security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Content-Security-Policy": "default-src 'self'",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains" if settings.is_production else "",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()"
        }
        
        for header, value in security_headers.items():
            if value:  # Only add non-empty headers
                response.headers[header] = value
        
        return response

class DatabaseSessionMiddleware(BaseHTTPMiddleware):
    """
    Middleware to manage database sessions per request.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        from app.core.database import async_session_factory
        
        async with async_session_factory() as session:
            request.state.db = session
            try:
                response = await call_next(request)
                await session.commit()
                return response
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for detailed request logging.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip logging for health checks
        if request.url.path in ["/health", "/health/"]:
            return await call_next(request)
        
        # Log request details
        request_body = await self._get_request_body(request)
        
        logger.debug(
            f"Request details - "
            f"Method: {request.method}, "
            f"Path: {request.url.path}, "
            f"Query: {dict(request.query_params)}, "
            f"Headers: {dict(request.headers)}, "
            f"Body: {request_body}"
        )
        
        response = await call_next(request)
        
        # Log response details (excluding body for performance)
        logger.debug(
            f"Response details - "
            f"Status: {response.status_code}, "
            f"Headers: {dict(response.headers)}"
        )
        
        return response
    
    async def _get_request_body(self, request: Request) -> str:
        """Extract request body for logging."""
        try:
            body = await request.body()
            if body:
                # Limit body size for logging
                max_body_size = 1024  # 1KB
                if len(body) > max_body_size:
                    return f"[Body truncated to {max_body_size} bytes] {body[:max_body_size].decode('utf-8', errors='ignore')}"
                return body.decode('utf-8', errors='ignore')
            return ""
        except Exception:
            return "[Unable to read body]"

class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for centralized error handling.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            return await call_next(request)
        except HTTPException:
            # Let FastAPI handle HTTP exceptions
            raise
        except Exception as e:
            # Log unexpected errors
            logger.error(
                f"Unhandled exception: {str(e)} "
                f"Path: {request.url.path} "
                f"Method: {request.method}",
                exc_info=True
            )
            
            # Return generic error response in production
            if settings.is_production:
                return Response(
                    content='{"detail": "Internal server error"}',
                    status_code=500,
                    media_type="application/json"
                )
            # In development, let the error propagate
            raise

# Configure CORS middleware
cors_middleware = CORSMiddleware(
    app=None,  # Will be set in main.py
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Process-Time", "X-RateLimit-*"],
    max_age=600,
)

# Configure rate limiter using slowapi
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.RATE_LIMIT_REQUESTS}/{settings.RATE_LIMIT_PERIOD}second"],
    storage_uri=settings.REDIS_URL if settings.RATE_LIMIT_ENABLED else "memory://",
)

# Export middleware
middleware_classes = [
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
    RequestLoggingMiddleware,
    ErrorHandlingMiddleware,
]

if settings.RATE_LIMIT_ENABLED:
    middleware_classes.append(RateLimitMiddleware)