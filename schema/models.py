from pydantic import BaseModel, Field
from typing import List, Optional

class SalesInsights(BaseModel):
    """Structured output schema for sales call analysis"""
    prospect_name: str = Field(..., description="Full name of the prospect")
    company_name: str = Field(..., description="Organization the prospect represents")
    summary: str = Field(..., description="Concise executive summary of the call")
    pain_points: List[str] = Field(default_factory=list, description="Categorized business challenges")
    sentiment_score: int = Field(..., ge=1, le=10, description="1-10 interest level")
    next_steps: List[str] = Field(default_factory=list, description="Actionable follow-ups")
    follow_up_email: str = Field(..., description="A drafted follow-up email ready for review")
    
class QualityMetrics(BaseModel):
    """Quality assessment of the sales call"""
    call_quality_score: int = Field(..., ge=1, le=5, description="Overall call quality rating")
    asked_for_meeting: bool = Field(..., description="Whether rep requested next meeting")
    strengths: List[str] = Field(default_factory=list, description="Call strengths")
    improvements: List[str] = Field(default_factory=list, description="Areas for improvement")
    
class CRMData(BaseModel):
    """Formatted data for CRM insertion"""
    prospect_name: str
    company_name: str
    summary: str
    pain_points: str  # Comma-separated
    sentiment_score: int
    next_steps: str  # Comma-separated
    call_quality: int
    follow_up_email: str
    timestamp: str