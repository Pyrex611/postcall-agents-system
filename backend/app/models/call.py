from sqlalchemy import Column, String, Integer, DateTime, Float, JSON, Boolean, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum

from app.core.database import Base

class CallStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class Call(Base):
    __tablename__ = "calls"
    
    id = Column(String(36), primary_key=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    
    # Call metadata
    file_name = Column(String(500), nullable=True)
    file_url = Column(String(1000), nullable=True)
    file_size = Column(Integer, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    
    # Transcript
    original_transcript = Column(Text, nullable=True)
    processed_transcript = Column(Text, nullable=True)
    
    # Processing status
    status = Column(Enum(CallStatus), default=CallStatus.PENDING)
    processing_started_at = Column(DateTime(timezone=True), nullable=True)
    processing_completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # AI Analysis results (stored as JSON for flexibility)
    insights = Column(JSON, nullable=True)
    quality_metrics = Column(JSON, nullable=True)
    strategic_advice = Column(JSON, nullable=True)
    crm_update_result = Column(JSON, nullable=True)
    follow_up_email = Column(Text, nullable=True)
    
    # Call participants
    prospect_name = Column(String(200), nullable=True)
    prospect_email = Column(String(200), nullable=True)
    company_name = Column(String(200), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    tenant = relationship("Tenant", back_populates="calls")
    user = relationship("User", back_populates="calls")
    
    def to_dict(self):
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "file_name": self.file_name,
            "status": self.status.value if self.status else None,
            "prospect_name": self.prospect_name,
            "company_name": self.company_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "processing_completed_at": self.processing_completed_at.isoformat() if self.processing_completed_at else None,
            "insights": self.insights,
            "quality_metrics": self.quality_metrics,
            "duration_seconds": self.duration_seconds
        }