"""
Pydantic schemas for API request/response validation
"""
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


# Auth Schemas
class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str
    organization_name: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: Optional[str]
    role: str
    organization_id: UUID
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


# Organization Schemas
class OrganizationCreate(BaseModel):
    name: str
    slug: str
    plan: str = "starter"


class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    plan: str
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


# Call Schemas
class CallCreate(BaseModel):
    recording_url: Optional[str] = None
    meeting_platform: Optional[str] = None
    external_meeting_id: Optional[str] = None
    participants: List[Dict[str, Any]] = []
    metadata: Dict[str, Any] = {}


class CallUpdate(BaseModel):
    status: Optional[str] = None
    duration_seconds: Optional[int] = None


class CallResponse(BaseModel):
    id: UUID
    organization_id: UUID
    user_id: Optional[UUID]
    meeting_platform: Optional[str]
    recording_url: Optional[str]
    duration_seconds: Optional[int]
    participants: List[Dict[str, Any]]
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


# Transcript Schemas
class TranscriptResponse(BaseModel):
    id: UUID
    call_id: UUID
    content: str
    language: str
    confidence: Optional[float]
    speaker_labels: List[Dict[str, Any]]
    provider: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


# Insight Schemas
class InsightResponse(BaseModel):
    id: UUID
    call_id: UUID
    prospect_name: Optional[str]
    company_name: Optional[str]
    summary: Optional[str]
    pain_points: List[str]
    sentiment_score: Optional[int]
    next_steps: List[str]
    follow_up_email: Optional[str]
    competitors_mentioned: List[str]
    objections: List[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


# Quality Metric Schemas
class QualityMetricResponse(BaseModel):
    id: UUID
    call_id: UUID
    quality_score: Optional[int]
    asked_for_meeting: bool
    talk_ratio: Optional[float]
    questions_asked: int
    strengths: List[str]
    improvements: List[str]
    playbook_adherence: Optional[float]
    created_at: datetime
    
    class Config:
        from_attributes = True


# Complete Call Analysis Response
class CallAnalysisResponse(BaseModel):
    call: CallResponse
    transcript: Optional[TranscriptResponse] = None
    insight: Optional[InsightResponse] = None
    quality_metric: Optional[QualityMetricResponse] = None


# Integration Schemas
class CRMIntegrationCreate(BaseModel):
    provider: str  # salesforce, hubspot, pipedrive
    credentials: Dict[str, Any]
    field_mapping: Dict[str, str] = {}


class CRMIntegrationResponse(BaseModel):
    id: UUID
    organization_id: UUID
    provider: str
    sync_enabled: bool
    last_sync: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


# Webhook Schemas
class WebhookCreate(BaseModel):
    url: str
    events: List[str]
    secret: Optional[str] = None


class WebhookResponse(BaseModel):
    id: UUID
    organization_id: UUID
    url: str
    events: List[str]
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


# Analytics Schemas
class AnalyticsQuery(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    metrics: List[str] = ["calls_count", "avg_quality", "avg_sentiment"]
    group_by: Optional[str] = None  # day, week, month, user


class AnalyticsResponse(BaseModel):
    period: str
    total_calls: int
    avg_quality_score: Optional[float]
    avg_sentiment_score: Optional[float]
    avg_duration_minutes: Optional[float]
    top_performers: List[Dict[str, Any]]
    insights: Dict[str, Any]


# Error Response
class ErrorResponse(BaseModel):
    detail: str
    type: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
