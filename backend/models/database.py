"""
Enterprise-grade Pydantic models for SalesOps AI Platform
Follows the database schema with proper validation and type safety
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Literal
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, validator
from enum import Enum


# ============================================================================
# ENUMS
# ============================================================================

class SubscriptionTier(str, Enum):
    TRIAL = "trial"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"


class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    REP = "rep"


class CallType(str, Enum):
    SALES = "sales"
    SUPPORT = "support"
    DISCOVERY = "discovery"
    DEMO = "demo"
    FOLLOW_UP = "follow_up"


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    TRANSCRIBING = "transcribing"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


class CRMType(str, Enum):
    SALESFORCE = "salesforce"
    HUBSPOT = "hubspot"
    PIPEDRIVE = "pipedrive"
    NONE = "none"


class DealRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SalesMethodology(str, Enum):
    MEDDIC = "MEDDIC"
    SPIN = "SPIN"
    BANT = "BANT"
    CHALLENGER = "Challenger"
    CUSTOM = "custom"


# ============================================================================
# BASE MODELS
# ============================================================================

class BaseDBModel(BaseModel):
    """Base model with common fields"""
    id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


# ============================================================================
# ORGANIZATION MODELS
# ============================================================================

class OrganizationBase(BaseModel):
    name: str = Field(..., max_length=255)
    slug: str = Field(..., max_length=100)
    domain: Optional[str] = Field(None, max_length=255)
    industry: Optional[str] = Field(None, max_length=100)
    company_size: Optional[str] = Field(None, max_length=50)
    subscription_tier: SubscriptionTier = SubscriptionTier.TRIAL
    primary_crm: CRMType = CRMType.NONE


class OrganizationCreate(OrganizationBase):
    pass


class Organization(BaseDBModel, OrganizationBase):
    subscription_status: SubscriptionStatus
    subscription_start_date: Optional[datetime]
    subscription_end_date: Optional[datetime]
    monthly_call_limit: int
    monthly_calls_used: int
    crm_connected: bool
    settings: Dict[str, Any] = {}
    deleted_at: Optional[datetime]


class OrganizationUpdate(BaseModel):
    name: Optional[str]
    domain: Optional[str]
    industry: Optional[str]
    company_size: Optional[str]
    subscription_tier: Optional[SubscriptionTier]
    primary_crm: Optional[CRMType]
    settings: Optional[Dict[str, Any]]


# ============================================================================
# USER MODELS
# ============================================================================

class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., max_length=255)
    role: UserRole = UserRole.REP
    avatar_url: Optional[str]


class UserCreate(UserBase):
    organization_id: UUID
    password: Optional[str] = Field(None, min_length=8)


class User(BaseDBModel, UserBase):
    organization_id: UUID
    email_verified: bool
    is_active: bool
    last_login_at: Optional[datetime]
    permissions: List[str] = []
    preferences: Dict[str, Any] = {}
    deleted_at: Optional[datetime]


class UserUpdate(BaseModel):
    full_name: Optional[str]
    avatar_url: Optional[str]
    role: Optional[UserRole]
    preferences: Optional[Dict[str, Any]]
    is_active: Optional[bool]


class UserInDB(User):
    password_hash: Optional[str]


# ============================================================================
# CALL MODELS
# ============================================================================

class CallParticipant(BaseModel):
    name: str
    email: Optional[EmailStr]
    role: Literal["rep", "prospect"]


class CallBase(BaseModel):
    call_type: CallType = CallType.SALES
    call_date: Optional[datetime]
    duration_seconds: Optional[int]
    source: Optional[str] = Field(None, max_length=50)
    external_id: Optional[str]


class CallCreate(CallBase):
    organization_id: UUID
    user_id: UUID
    participants: List[CallParticipant] = []
    metadata: Dict[str, Any] = {}


class Call(BaseDBModel, CallBase):
    organization_id: UUID
    user_id: UUID
    audio_file_url: Optional[str]
    audio_file_size_bytes: Optional[int]
    transcript_url: Optional[str]
    raw_transcript: Optional[str]
    processing_status: ProcessingStatus
    processing_started_at: Optional[datetime]
    processing_completed_at: Optional[datetime]
    error_message: Optional[str]
    participants: List[CallParticipant] = []
    metadata: Dict[str, Any] = {}
    deleted_at: Optional[datetime]


class CallUpdate(BaseModel):
    call_type: Optional[CallType]
    call_date: Optional[datetime]
    duration_seconds: Optional[int]
    audio_file_url: Optional[str]
    raw_transcript: Optional[str]
    processing_status: Optional[ProcessingStatus]
    error_message: Optional[str]


# ============================================================================
# CALL ANALYSIS MODELS
# ============================================================================

class Objection(BaseModel):
    objection: str
    response: Optional[str]
    handled_well: bool = False


class MethodologyScore(BaseModel):
    """Flexible scoring based on methodology"""
    overall: int = Field(..., ge=1, le=10)
    criteria_scores: Dict[str, int] = {}  # e.g., {"Metrics": 8, "Economic Buyer": 6}


class CallAnalysisBase(BaseModel):
    prospect_name: Optional[str]
    prospect_company: Optional[str]
    prospect_email: Optional[EmailStr]
    prospect_phone: Optional[str]
    prospect_title: Optional[str]
    summary: Optional[str]
    pain_points: List[str] = []
    next_steps: List[str] = []
    objections: List[Objection] = []
    sentiment_score: Optional[int] = Field(None, ge=1, le=10)
    engagement_score: Optional[int] = Field(None, ge=1, le=10)
    buying_intent_score: Optional[int] = Field(None, ge=1, le=10)
    call_quality_score: Optional[int] = Field(None, ge=1, le=5)
    asked_for_meeting: Optional[bool]
    rep_talk_ratio: Optional[float] = Field(None, ge=0, le=100)
    prospect_talk_ratio: Optional[float] = Field(None, ge=0, le=100)
    dead_air_ratio: Optional[float] = Field(None, ge=0, le=100)
    strengths: List[str] = []
    improvements: List[str] = []
    follow_up_email: Optional[str]
    meeting_notes: Optional[str]
    strategic_advice: Optional[str]
    deal_risk_level: Optional[DealRiskLevel]
    recommended_actions: List[str] = []
    
    @validator('prospect_talk_ratio', 'rep_talk_ratio', 'dead_air_ratio')
    def validate_ratios_sum(cls, v, values):
        """Ensure talk ratios sum to ~100%"""
        if v is not None:
            total = sum(filter(None, [
                values.get('rep_talk_ratio'),
                values.get('prospect_talk_ratio'),
                values.get('dead_air_ratio')
            ])) + (v or 0)
            if total > 101:  # Allow 1% tolerance
                raise ValueError("Talk ratios cannot exceed 100%")
        return v


class CallAnalysisCreate(CallAnalysisBase):
    call_id: UUID
    organization_id: UUID
    methodology_score: Optional[MethodologyScore]


class CallAnalysis(BaseDBModel, CallAnalysisBase):
    call_id: UUID
    organization_id: UUID
    methodology_score: Optional[MethodologyScore]


# ============================================================================
# CRM INTEGRATION MODELS
# ============================================================================

class CRMConnectionBase(BaseModel):
    crm_type: CRMType
    instance_url: Optional[str]
    field_mappings: Dict[str, str] = {}
    sync_settings: Dict[str, Any] = {}


class CRMConnectionCreate(CRMConnectionBase):
    organization_id: UUID
    access_token: str  # Will be encrypted before storage
    refresh_token: Optional[str]


class CRMConnection(BaseDBModel, CRMConnectionBase):
    organization_id: UUID
    is_active: bool
    token_expires_at: Optional[datetime]
    last_sync_at: Optional[datetime]
    last_sync_status: Optional[str]


class CRMSyncLog(BaseDBModel):
    call_id: UUID
    crm_connection_id: UUID
    action: str
    crm_entity_type: Optional[str]
    crm_entity_id: Optional[str]
    status: str
    error_message: Optional[str]
    request_payload: Optional[Dict[str, Any]]
    response_payload: Optional[Dict[str, Any]]


# ============================================================================
# PLAYBOOK MODELS
# ============================================================================

class PlaybookCriteria(BaseModel):
    """Structured criteria for methodology scoring"""
    criteria: Dict[str, Dict[str, Any]]
    # Example: {"Metrics": {"weight": 20, "questions": ["Are metrics quantified?"]}}


class PlaybookBase(BaseModel):
    name: str = Field(..., max_length=255)
    methodology: SalesMethodology
    description: Optional[str]
    criteria: PlaybookCriteria
    is_active: bool = True
    is_default: bool = False


class PlaybookCreate(PlaybookBase):
    organization_id: UUID


class Playbook(BaseDBModel, PlaybookBase):
    organization_id: UUID
    created_by: Optional[UUID]


# ============================================================================
# KNOWLEDGE BASE MODELS
# ============================================================================

class KnowledgeBaseBase(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    content: str
    content_type: Literal["best_practice", "objection_handler", "product_info", "competitor_analysis"]
    tags: List[str] = []
    category: Optional[str]


class KnowledgeBaseCreate(KnowledgeBaseBase):
    organization_id: UUID


class KnowledgeBase(BaseDBModel, KnowledgeBaseBase):
    organization_id: UUID
    usage_count: int
    last_used_at: Optional[datetime]
    created_by: Optional[UUID]
    deleted_at: Optional[datetime]


# ============================================================================
# JOB QUEUE MODELS
# ============================================================================

class JobBase(BaseModel):
    job_type: str = Field(..., max_length=100)
    payload: Dict[str, Any]
    priority: int = Field(5, ge=1, le=10)
    max_attempts: int = 3


class JobCreate(JobBase):
    organization_id: Optional[UUID]


class Job(BaseDBModel, JobBase):
    organization_id: Optional[UUID]
    status: str
    attempts: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]
    result: Optional[Dict[str, Any]]
    worker_id: Optional[str]


# ============================================================================
# ANALYTICS MODELS
# ============================================================================

class TeamMetrics(BaseDBModel):
    organization_id: UUID
    user_id: Optional[UUID]
    period_start: datetime
    period_end: datetime
    total_calls: int
    avg_call_duration: Optional[int]
    avg_sentiment_score: Optional[float]
    avg_quality_score: Optional[float]
    meetings_scheduled: int
    opportunities_created: int
    win_rate: Optional[float]
    avg_rep_talk_ratio: Optional[float]


# ============================================================================
# API REQUEST/RESPONSE MODELS
# ============================================================================

class CallAnalysisRequest(BaseModel):
    """Request to analyze a call"""
    call_id: UUID
    playbook_id: Optional[UUID]
    use_rag: bool = True


class CallUploadRequest(BaseModel):
    """Request to upload and process a call"""
    organization_id: UUID
    user_id: UUID
    call_type: CallType = CallType.SALES
    source: str
    transcript: Optional[str]  # If already transcribed
    participants: List[CallParticipant] = []


class DashboardMetrics(BaseModel):
    """Organization dashboard overview"""
    total_calls: int
    calls_this_month: int
    avg_sentiment: float
    avg_quality: float
    active_users: int
    calls_by_status: Dict[str, int]
    recent_calls: List[Call]


class RAGSearchRequest(BaseModel):
    """Request to search knowledge base"""
    query: str
    content_types: Optional[List[str]]
    limit: int = Field(5, ge=1, le=20)


class RAGSearchResult(BaseModel):
    """Knowledge base search result"""
    id: UUID
    title: Optional[str]
    content: str
    content_type: str
    relevance_score: float
    usage_count: int