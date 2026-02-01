"""
Application configuration settings.
"""
import os
from typing import List, Optional, Dict, Any
from pydantic import Field
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import secrets

# Load environment variables
load_dotenv()

class Settings(BaseSettings):
    # Application
    PROJECT_NAME: str = "SalesIntel AI"
    PROJECT_VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = Field(
        default_factory=lambda: os.getenv(
            "BACKEND_CORS_ORIGINS", 
            "http://localhost:3000,http://localhost:8000"
        ).split(",")
    )
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql+asyncpg://postgres:postgres@localhost:5432/salesintel"
    )
    DATABASE_POOL_SIZE: int = int(os.getenv("DATABASE_POOL_SIZE", "20"))
    DATABASE_MAX_OVERFLOW: int = int(os.getenv("DATABASE_MAX_OVERFLOW", "40"))
    DATABASE_POOL_RECYCLE: int = int(os.getenv("DATABASE_POOL_RECYCLE", "3600"))
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD")
    REDIS_MAX_CONNECTIONS: int = int(os.getenv("REDIS_MAX_CONNECTIONS", "100"))
    
    # AI/ML Services
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    AZURE_OPENAI_API_KEY: Optional[str] = os.getenv("AZURE_OPENAI_API_KEY")
    AZURE_OPENAI_ENDPOINT: Optional[str] = os.getenv("AZURE_OPENAI_ENDPOINT")
    
    # Transcription
    GOOGLE_SPEECH_TO_TEXT_API_KEY: Optional[str] = os.getenv("GOOGLE_SPEECH_TO_TEXT_API_KEY")
    AWS_TRANSCRIBE_REGION: Optional[str] = os.getenv("AWS_TRANSCRIBE_REGION", "us-east-1")
    AWS_ACCESS_KEY_ID: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY")
    
    # File Storage
    STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "local")  # local, s3, gcs, azure
    LOCAL_STORAGE_PATH: str = os.getenv("LOCAL_STORAGE_PATH", "./storage")
    AWS_S3_BUCKET: Optional[str] = os.getenv("AWS_S3_BUCKET")
    AWS_S3_REGION: Optional[str] = os.getenv("AWS_S3_REGION", "us-east-1")
    GCS_BUCKET_NAME: Optional[str] = os.getenv("GCS_BUCKET_NAME")
    AZURE_STORAGE_CONNECTION_STRING: Optional[str] = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    AZURE_STORAGE_CONTAINER: Optional[str] = os.getenv("AZURE_STORAGE_CONTAINER")
    
    # File Limits
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "500"))
    ALLOWED_AUDIO_TYPES: List[str] = Field(
        default_factory=lambda: os.getenv(
            "ALLOWED_AUDIO_TYPES",
            "audio/mpeg,audio/wav,audio/mp4,audio/x-m4a,audio/webm,video/mp4,video/webm"
        ).split(",")
    )
    
    # Email
    SMTP_HOST: Optional[str] = os.getenv("SMTP_HOST")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: Optional[str] = os.getenv("SMTP_USER")
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD")
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "noreply@salesintel.ai")
    EMAIL_FROM_NAME: str = os.getenv("EMAIL_FROM_NAME", "SalesIntel AI")
    
    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "True").lower() == "true"
    RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    RATE_LIMIT_PERIOD: int = int(os.getenv("RATE_LIMIT_PERIOD", "60"))  # seconds
    
    # Monitoring
    SENTRY_DSN: Optional[str] = os.getenv("SENTRY_DSN")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # CRM Integrations
    SALESFORCE_CLIENT_ID: Optional[str] = os.getenv("SALESFORCE_CLIENT_ID")
    SALESFORCE_CLIENT_SECRET: Optional[str] = os.getenv("SALESFORCE_CLIENT_SECRET")
    HUBSPOT_CLIENT_ID: Optional[str] = os.getenv("HUBSPOT_CLIENT_ID")
    HUBSPOT_CLIENT_SECRET: Optional[str] = os.getenv("HUBSPOT_CLIENT_SECRET")
    
    # External Services
    SLACK_WEBHOOK_URL: Optional[str] = os.getenv("SLACK_WEBHOOK_URL")
    MS_TEAMS_WEBHOOK_URL: Optional[str] = os.getenv("MS_TEAMS_WEBHOOK_URL")
    
    # Feature Flags
    FEATURE_EMAIL_NOTIFICATIONS: bool = os.getenv("FEATURE_EMAIL_NOTIFICATIONS", "True").lower() == "true"
    FEATURE_CRM_SYNC: bool = os.getenv("FEATURE_CRM_SYNC", "True").lower() == "true"
    FEATURE_REAL_TIME_PROCESSING: bool = os.getenv("FEATURE_REAL_TIME_PROCESSING", "True").lower() == "true"
    
    # Performance
    WORKER_CONCURRENCY: int = int(os.getenv("WORKER_CONCURRENCY", "4"))
    MAX_WORKERS: int = int(os.getenv("MAX_WORKERS", "10"))
    
    @property
    def database_url_async(self) -> str:
        """Get async database URL."""
        return self.DATABASE_URL
    
    @property
    def database_url_sync(self) -> str:
        """Get sync database URL for migrations."""
        if "+asyncpg" in self.DATABASE_URL:
            return self.DATABASE_URL.replace("+asyncpg", "")
        return self.DATABASE_URL
    
    @property
    def max_file_size_bytes(self) -> int:
        """Get max file size in bytes."""
        return self.MAX_FILE_SIZE_MB * 1024 * 1024
    
    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.ENVIRONMENT.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.ENVIRONMENT.lower() == "development"
    
    @property
    def is_testing(self) -> bool:
        """Check if running in testing."""
        return self.ENVIRONMENT.lower() == "testing"
    
    class Config:
        case_sensitive = True
        env_file = ".env"
        env_file_encoding = "utf-8"

# Create settings instance
settings = Settings()