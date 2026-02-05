"""
Calls API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
from datetime import datetime

from core.database import get_db
from core.security import get_current_user_id, get_current_organization_id
from models.call import Call
from models.__init__ import Transcript, Insight, QualityMetric
from schemas import (
    CallCreate,
    CallUpdate,
    CallResponse,
    CallAnalysisResponse,
    TranscriptResponse,
    InsightResponse,
    QualityMetricResponse
)
from workers.call_processing import process_call_recording, process_text_transcript
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=CallResponse, status_code=status.HTTP_201_CREATED)
async def create_call(
    call_data: CallCreate,
    user_id: str = Depends(get_current_user_id),
    org_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db)
):
    """
    Create new call record
    
    Can be created with:
    - recording_url (will be transcribed)
    - No recording (transcript can be added later)
    """
    try:
        call = Call(
            organization_id=org_id,
            user_id=user_id,
            recording_url=call_data.recording_url,
            meeting_platform=call_data.meeting_platform,
            external_meeting_id=call_data.external_meeting_id,
            participants=call_data.participants,
            metadata=call_data.metadata,
            status="pending"
        )
        
        db.add(call)
        db.commit()
        db.refresh(call)
        
        # Trigger background processing if recording exists
        if call.recording_url:
            process_call_recording.delay(str(call.id))
            call.status = "queued"
            db.commit()
        
        logger.info(f"Call created: {call.id}")
        
        return call
        
    except Exception as e:
        db.rollback()
        logger.error(f"Call creation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create call"
        )


@router.post("/{call_id}/transcript", response_model=CallResponse)
async def upload_transcript(
    call_id: str,
    transcript_text: str,
    user_id: str = Depends(get_current_user_id),
    org_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db)
):
    """
    Upload text transcript for a call
    
    Useful for manual transcript entry without audio
    """
    call = db.query(Call).filter(
        Call.id == call_id,
        Call.organization_id == org_id
    ).first()
    
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )
    
    # Trigger processing with text transcript
    process_text_transcript.delay(call_id, transcript_text)
    
    call.status = "queued"
    db.commit()
    
    return call


@router.get("/", response_model=List[CallResponse])
async def list_calls(
    skip: int = 0,
    limit: int = 50,
    status_filter: Optional[str] = None,
    org_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db)
):
    """
    List calls for organization
    
    Supports pagination and filtering
    """
    query = db.query(Call).filter(Call.organization_id == org_id)
    
    if status_filter:
        query = query.filter(Call.status == status_filter)
    
    calls = query.order_by(Call.created_at.desc()).offset(skip).limit(limit).all()
    
    return calls


@router.get("/{call_id}", response_model=CallAnalysisResponse)
async def get_call(
    call_id: str,
    org_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db)
):
    """
    Get call with complete analysis
    
    Includes transcript, insights, and quality metrics
    """
    call = db.query(Call).filter(
        Call.id == call_id,
        Call.organization_id == org_id
    ).first()
    
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )
    
    return CallAnalysisResponse(
        call=call,
        transcript=call.transcript,
        insight=call.insight,
        quality_metric=call.quality_metric
    )


@router.patch("/{call_id}", response_model=CallResponse)
async def update_call(
    call_id: str,
    update_data: CallUpdate,
    org_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db)
):
    """Update call details"""
    call = db.query(Call).filter(
        Call.id == call_id,
        Call.organization_id == org_id
    ).first()
    
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )
    
    if update_data.status:
        call.status = update_data.status
    if update_data.duration_seconds:
        call.duration_seconds = update_data.duration_seconds
    
    db.commit()
    db.refresh(call)
    
    return call


@router.delete("/{call_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_call(
    call_id: str,
    org_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db)
):
    """Delete a call and all associated data"""
    call = db.query(Call).filter(
        Call.id == call_id,
        Call.organization_id == org_id
    ).first()
    
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )
    
    db.delete(call)
    db.commit()
    
    logger.info(f"Call deleted: {call_id}")


@router.post("/{call_id}/reprocess", response_model=CallResponse)
async def reprocess_call(
    call_id: str,
    org_id: str = Depends(get_current_organization_id),
    db: Session = Depends(get_db)
):
    """
    Reprocess a call
    
    Re-runs transcription and analysis
    """
    call = db.query(Call).filter(
        Call.id == call_id,
        Call.organization_id == org_id
    ).first()
    
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )
    
    # Trigger reprocessing
    process_call_recording.delay(call_id)
    
    call.status = "queued"
    db.commit()
    
    return call
