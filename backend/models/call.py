"""
Call model
"""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from core.database import Base


class Call(Base):
    """Call recording model"""
    __tablename__ = "calls"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    external_meeting_id = Column(String(255), nullable=True)
    meeting_platform = Column(String(50), nullable=True)  # zoom, teams, meet, manual
    recording_url = Column(String, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    participants = Column(JSON, default=[])
    metadata = Column(JSON, default={})
    status = Column(String(20), default="processing")  # processing, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    organization = relationship("Organization", back_populates="calls")
    user = relationship("User", back_populates="calls")
    transcript = relationship("Transcript", back_populates="call", uselist=False, cascade="all, delete-orphan")
    insight = relationship("Insight", back_populates="call", uselist=False, cascade="all, delete-orphan")
    quality_metric = relationship("QualityMetric", back_populates="call", uselist=False, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Call {self.id} - {self.status}>"
