"""
Call model for storing call recordings and analysis.
"""
import enum
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    Column, String, Integer, DateTime, Float, 
    JSON, Boolean, Text, Enum, ForeignKey, Index, BigInteger
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func

from app.models.base import Base, TimestampMixin

class CallStatus(str, enum.Enum):
    """Call processing status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    TRANSCRIBING = "transcribing"
    ANALYZING = "analyzing"
    UPDATING_CRM = "updating_crm"
    SENDING_EMAIL = "sending_email"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class CallType(str, enum.Enum):
    """Call type enumeration."""
    SALES = "sales"
    DISCOVERY = "discovery"
    DEMO = "demo"
    NEGOTIATION = "negotiation"
    ONBOARDING = "onboarding"
    SUPPORT = "support"
    INTERNAL = "internal"
    OTHER = "other"

class Call(Base, TimestampMixin):
    """
    Call model representing a sales call recording and its analysis.
    """
    __tablename__ = "calls"
    
    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Tenant and user
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    
    # Call metadata
    title = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    call_type = Column(Enum(CallType), default=CallType.SALES, index=True)
    meeting_platform = Column(String(100), nullable=True)  # Zoom, Teams, etc.
    meeting_id = Column(String(255), nullable=True, index=True)
    
    # File information
    file_name = Column(String(500), nullable=True)
    file_url = Column(String(1000), nullable=True)
    file_size_bytes = Column(BigInteger, nullable=True)
    file_format = Column(String(50), nullable=True)
    file_hash = Column(String(64), nullable=True, index=True)  # SHA256
    
    # Call details
    call_start_time = Column(DateTime(timezone=True), nullable=True)
    call_end_time = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True)
    participants = Column(JSON, nullable=True)  # List of participants
    
    # Transcription
    original_transcript = Column(Text, nullable=True)  # User-provided transcript
    processed_transcript = Column(Text, nullable=True)  # AI-generated transcript
    transcript_confidence = Column(Float, nullable=True)
    speaker_labels = Column(JSON, nullable=True)  # Speaker diarization data
    word_timestamps = Column(JSON, nullable=True)  # Word-level timestamps
    
    # Processing status
    status = Column(Enum(CallStatus), default=CallStatus.PENDING, index=True)
    processing_started_at = Column(DateTime(timezone=True), nullable=True)
    processing_completed_at = Column(DateTime(timezone=True), nullable=True)
    processing_error = Column(Text, nullable=True)
    processing_attempts = Column(Integer, default=0)
    
    # AI Analysis results
    insights = Column(JSON, nullable=True)  # Structured insights from Analyst agent
    quality_metrics = Column(JSON, nullable=True)  # Quality assessment from Quality agent
    strategic_advice = Column(JSON, nullable=True)  # Strategic advice from Advisor agent
    follow_up_email = Column(Text, nullable=True)  # Generated follow-up email
    
    # CRM Integration
    crm_update_result = Column(JSON, nullable=True)  # CRM update status and data
    crm_record_id = Column(String(255), nullable=True, index=True)  # External CRM record ID
    crm_synced_at = Column(DateTime(timezone=True), nullable=True)
    
    # Call participants (extracted from analysis)
    prospect_name = Column(String(200), nullable=True, index=True)
    prospect_email = Column(String(200), nullable=True, index=True)
    prospect_phone = Column(String(50), nullable=True)
    prospect_title = Column(String(200), nullable=True)
    company_name = Column(String(200), nullable=True, index=True)
    company_website = Column(String(500), nullable=True)
    company_industry = Column(String(200), nullable=True)
    
    # Tags and categories
    tags = Column(JSON, nullable=True)  # User-defined tags
    categories = Column(JSON, nullable=True)  # AI-generated categories
    sentiment_score = Column(Float, nullable=True, index=True)  # -1 to 1
    urgency_score = Column(Float, nullable=True, index=True)  # 0 to 1
    
    # Privacy and compliance
    is_private = Column(Boolean, default=False, index=True)
    is_confidential = Column(Boolean, default=False, index=True)
    consent_recorded = Column(Boolean, default=False)
    data_retention_date = Column(DateTime(timezone=True), nullable=True)
    
    # Performance metrics
    analysis_time_seconds = Column(Float, nullable=True)
    transcription_time_seconds = Column(Float, nullable=True)
    crm_sync_time_seconds = Column(Float, nullable=True)
    total_processing_time_seconds = Column(Float, nullable=True)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="calls")
    user = relationship("User", back_populates="calls")
    
    # Indexes for common queries
    __table_args__ = (
        Index('ix_calls_tenant_user_status', 'tenant_id', 'user_id', 'status'),
        Index('ix_calls_tenant_created_at', 'tenant_id', 'created_at'),
        Index('ix_calls_user_created_at', 'user_id', 'created_at'),
        Index('ix_calls_prospect_company', 'prospect_name', 'company_name'),
        Index('ix_calls_status_created_at', 'status', 'created_at'),
        Index('ix_calls_call_type_created_at', 'call_type', 'created_at'),
        Index('ix_calls_sentiment_created_at', 'sentiment_score', 'created_at'),
        Index('ix_calls_file_hash', 'file_hash'),  # For deduplication
    )
    
    @validates('duration_seconds')
    def validate_duration(self, key, duration):
        """Validate duration is positive."""
        if duration is not None and duration < 0:
            raise ValueError("Duration cannot be negative")
        return duration
    
    @validates('sentiment_score')
    def validate_sentiment(self, key, score):
        """Validate sentiment score is between -1 and 1."""
        if score is not None and not -1 <= score <= 1:
            raise ValueError("Sentiment score must be between -1 and 1")
        return score
    
    def to_dict(self, include_transcript: bool = False) -> Dict[str, Any]:
        """Convert call to dictionary."""
        data = {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "title": self.title,
            "description": self.description,
            "call_type": self.call_type.value if self.call_type else None,
            "meeting_platform": self.meeting_platform,
            "meeting_id": self.meeting_id,
            "file_name": self.file_name,
            "file_size_bytes": self.file_size_bytes,
            "file_format": self.file_format,
            "call_start_time": self.call_start_time.isoformat() if self.call_start_time else None,
            "call_end_time": self.call_end_time.isoformat() if self.call_end_time else None,
            "duration_seconds": self.duration_seconds,
            "participants": self.participants,
            "status": self.status.value if self.status else None,
            "processing_started_at": self.processing_started_at.isoformat() if self.processing_started_at else None,
            "processing_completed_at": self.processing_completed_at.isoformat() if self.processing_completed_at else None,
            "processing_error": self.processing_error,
            "insights": self.insights,
            "quality_metrics": self.quality_metrics,
            "strategic_advice": self.strategic_advice,
            "follow_up_email": self.follow_up_email,
            "crm_update_result": self.crm_update_result,
            "crm_record_id": self.crm_record_id,
            "crm_synced_at": self.crm_synced_at.isoformat() if self.crm_synced_at else None,
            "prospect_name": self.prospect_name,
            "prospect_email": self.prospect_email,
            "prospect_phone": self.prospect_phone,
            "prospect_title": self.prospect_title,
            "company_name": self.company_name,
            "company_website": self.company_website,
            "company_industry": self.company_industry,
            "tags": self.tags,
            "categories": self.categories,
            "sentiment_score": self.sentiment_score,
            "urgency_score": self.urgency_score,
            "is_private": self.is_private,
            "is_confidential": self.is_confidential,
            "consent_recorded": self.consent_recorded,
            "analysis_time_seconds": self.analysis_time_seconds,
            "transcription_time_seconds": self.transcription_time_seconds,
            "crm_sync_time_seconds": self.crm_sync_time_seconds,
            "total_processing_time_seconds": self.total_processing_time_seconds,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_transcript and self.processed_transcript:
            data["processed_transcript"] = self.processed_transcript
            data["transcript_confidence"] = self.transcript_confidence
            data["speaker_labels"] = self.speaker_labels
        
        return data
    
    def get_quality_score(self) -> Optional[float]:
        """Get call quality score from quality metrics."""
        if self.quality_metrics and isinstance(self.quality_metrics, dict):
            return self.quality_metrics.get("call_quality_score")
        return None
    
    def get_sentiment_label(self) -> str:
        """Get human-readable sentiment label."""
        if self.sentiment_score is None:
            return "neutral"
        elif self.sentiment_score >= 0.3:
            return "positive"
        elif self.sentiment_score <= -0.3:
            return "negative"
        else:
            return "neutral"
    
    def get_processing_time(self) -> Optional[float]:
        """Get total processing time in seconds."""
        if self.processing_started_at and self.processing_completed_at:
            return (self.processing_completed_at - self.processing_started_at).total_seconds()
        return None
    
    def mark_as_processing(self) -> None:
        """Mark call as processing."""
        self.status = CallStatus.PROCESSING
        self.processing_started_at = datetime.utcnow()
        self.processing_error = None
        self.processing_attempts += 1
    
    def mark_as_completed(self, 
                         insights: Dict = None,
                         quality_metrics: Dict = None,
                         strategic_advice: Dict = None,
                         follow_up_email: str = None) -> None:
        """Mark call as completed with results."""
        self.status = CallStatus.COMPLETED
        self.processing_completed_at = datetime.utcnow()
        
        if insights:
            self.insights = insights
            # Extract sentiment score if available
            if isinstance(insights, dict):
                self.sentiment_score = insights.get("sentiment_score")
        
        if quality_metrics:
            self.quality_metrics = quality_metrics
        
        if strategic_advice:
            self.strategic_advice = strategic_advice
        
        if follow_up_email:
            self.follow_up_email = follow_up_email
        
        # Calculate processing times
        self.total_processing_time_seconds = self.get_processing_time()
    
    def mark_as_failed(self, error: str) -> None:
        """Mark call as failed with error."""
        self.status = CallStatus.FAILED
        self.processing_completed_at = datetime.utcnow()
        self.processing_error = error
    
    def update_crm_status(self, result: Dict[str, Any], record_id: str = None) -> None:
        """Update CRM sync status."""
        self.crm_update_result = result
        if record_id:
            self.crm_record_id = record_id
        self.crm_synced_at = datetime.utcnow()
        
        # Calculate CRM sync time if processing completed
        if self.processing_completed_at:
            self.crm_sync_time_seconds = (datetime.utcnow() - self.processing_completed_at).total_seconds()
    
    def is_processed(self) -> bool:
        """Check if call has been processed."""
        return self.status == CallStatus.COMPLETED
    
    def is_failed(self) -> bool:
        """Check if call processing failed."""
        return self.status == CallStatus.FAILED
    
    def can_retry(self, max_attempts: int = 3) -> bool:
        """Check if call can be retried."""
        return (self.status == CallStatus.FAILED and 
                self.processing_attempts < max_attempts)
    
    def reset_for_retry(self) -> None:
        """Reset call for retry."""
        self.status = CallStatus.PENDING
        self.processing_started_at = None
        self.processing_completed_at = None
        self.processing_error = None
        # Keep existing processing_attempts
    
    def extract_key_entities(self) -> Dict[str, Any]:
        """Extract key entities from call data."""
        entities = {
            "people": [],
            "companies": [],
            "products": [],
            "dates": [],
            "topics": []
        }
        
        # Extract from insights
        if self.insights and isinstance(self.insights, dict):
            if self.insights.get("prospect_name"):
                entities["people"].append(self.insights["prospect_name"])
            if self.insights.get("company_name"):
                entities["companies"].append(self.insights["company_name"])
            if self.insights.get("product_mentions"):
                entities["products"].extend(self.insights.get("product_mentions", []))
            if self.insights.get("key_topics"):
                entities["topics"].extend(self.insights.get("key_topics", []))
        
        # Extract from transcript (simplified)
        if self.processed_transcript:
            # Basic entity extraction - in production, use NLP library
            import re
            # Extract email addresses
            emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', 
                               self.processed_transcript)
            entities["people"].extend(emails)
        
        return entities
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the call."""
        quality_score = self.get_quality_score()
        
        return {
            "id": self.id,
            "title": self.title or f"Call with {self.prospect_name or 'Unknown'}",
            "prospect_name": self.prospect_name,
            "company_name": self.company_name,
            "call_type": self.call_type.value if self.call_type else None,
            "status": self.status.value if self.status else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "duration_seconds": self.duration_seconds,
            "quality_score": quality_score,
            "sentiment_score": self.sentiment_score,
            "sentiment_label": self.get_sentiment_label(),
            "has_crm_sync": bool(self.crm_record_id),
            "has_follow_up": bool(self.follow_up_email),
            "is_processed": self.is_processed()
        }