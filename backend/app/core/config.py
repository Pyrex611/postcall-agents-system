import os
from pydantic_settings import BaseSettings
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # Application
    PROJECT_NAME: str = "SalesIntel AI"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = os.getenv(
        "BACKEND_CORS_ORIGINS", 
        "http://localhost:3000,http://localhost:8000"
    ).split(",")
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql+asyncpg://user:password@localhost/salesintel"
    )
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD", None)
    
    # AI/ML Services
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY", None)
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY", None)
    
    # Transcription
    GOOGLE_SPEECH_TO_TEXT_API_KEY: Optional[str] = os.getenv("GOOGLE_SPEECH_TO_TEXT_API_KEY", None)
    AWS_ACCESS_KEY_ID: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID", None)
    AWS_SECRET_ACCESS_KEY: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY", None)
    AWS_REGION: Optional[str] = os.getenv("AWS_REGION", "us-east-1")
    
    # Email
    SMTP_HOST: Optional[str] = os.getenv("SMTP_HOST", None)
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: Optional[str] = os.getenv("SMTP_USER", None)
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD", None)
    
    # File Storage
    AWS_S3_BUCKET: Optional[str] = os.getenv("AWS_S3_BUCKET", None)
    STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "local")  # local, s3, gcs
    
    @property
    def database_url_async(self) -> str:
        """Get async database URL."""
        return self.DATABASE_URL
    
    @property
    def database_url_sync(self) -> str:
        """Get sync database URL (for migrations)."""
        return self.DATABASE_URL.replace("+asyncpg", "")
    
    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()