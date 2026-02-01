import logging
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks, Depends, status
from fastapi.responses import JSONResponse
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
import datetime

from app.schemas.call import CallCreate, CallResponse, CallListResponse, CallDetailResponse
from app.tasks.process_call import process_sales_call_task
from app.core.database import get_db
from app.models.call import Call, CallStatus
from app.models.user import User
from app.core.security import get_current_user
from app.services.file_storage import FileStorageService
from app.services.transcription import AudioTranscriber

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/upload", response_model=CallResponse, status_code=status.HTTP_201_CREATED)
async def upload_call(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    transcript: Optional[str] = Form(None),
    prospect_name: Optional[str] = Form(None),
    prospect_email: Optional[str] = Form(None),
    company_name: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload a call (audio file or transcript) for processing.
    """
    # Validate input
    if not file and not transcript:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either audio file or transcript must be provided."
        )
    
    if file:
        # Validate file type
        allowed_types = ['audio/mpeg', 'audio/wav', 'audio/mp4', 'audio/x-m4a', 'audio/webm']
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type. Allowed types: {', '.join(allowed_types)}"
            )
    
    call_id = str(uuid.uuid4())
    
    try:
        # Step 1: Save file to storage if provided
        file_url = None
        file_size = None
        
        if file:
            storage_service = FileStorageService()
            file_url = await storage_service.upload_file(
                file=file,
                tenant_id=current_user.tenant_id,
                call_id=call_id
            )
            file_size = file.size
        
        # Step 2: Create call record in database
        call = Call(
            id=call_id,
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            file_name=file.filename if file else None,
            file_url=file_url,
            file_size=file_size,
            original_transcript=transcript,
            prospect_name=prospect_name,
            prospect_email=prospect_email,
            company_name=company_name,
            status=CallStatus.PENDING,
            created_at=datetime.datetime.utcnow()
        )
        
        db.add(call)
        await db.commit()
        await db.refresh(call)
        
        # Step 3: Trigger background processing
        background_tasks.add_task(
            process_sales_call_task.delay,
            call_id=call_id,
            file_url=file_url,
            transcript_text=transcript,
            tenant_id=current_user.tenant_id,
            user_id=current_user.id
        )
        
        logger.info(f"Call {call_id} uploaded successfully for user {current_user.id}")
        
        return CallResponse(
            id=call_id,
            status="processing",
            message="Call is being processed. You will be notified when it's ready.",
            created_at=call.created_at.isoformat() if call.created_at else None
        )
        
    except Exception as e:
        logger.error(f"Failed to upload call: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload call: {str(e)}"
        )

@router.get("/{call_id}/status", response_model=CallResponse)
async def get_call_status(
    call_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get the processing status of a call.
    """
    try:
        stmt = select(Call).where(
            Call.id == call_id,
            Call.tenant_id == current_user.tenant_id
        )
        result = await db.execute(stmt)
        call = result.scalar_one_or_none()
        
        if not call:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Call not found"
            )
        
        return CallResponse(
            id=call.id,
            status=call.status.value,
            message=f"Call is {call.status.value}",
            created_at=call.created_at.isoformat() if call.created_at else None,
            processing_completed_at=call.processing_completed_at.isoformat() if call.processing_completed_at else None
        )
        
    except Exception as e:
        logger.error(f"Failed to get call status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get call status: {str(e)}"
        )

@router.get("/{call_id}/analysis", response_model=CallDetailResponse)
async def get_call_analysis(
    call_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get the complete analysis results for a call.
    """
    try:
        stmt = select(Call).where(
            Call.id == call_id,
            Call.tenant_id == current_user.tenant_id
        )
        result = await db.execute(stmt)
        call = result.scalar_one_or_none()
        
        if not call:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Call not found"
            )
        
        if call.status != CallStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Call analysis is not yet complete"
            )
        
        return CallDetailResponse(
            id=call.id,
            status=call.status.value,
            insights=call.insights or {},
            quality_metrics=call.quality_metrics or {},
            strategic_advice=call.strategic_advice or {},
            crm_update_result=call.crm_update_result or {},
            follow_up_email=call.follow_up_email,
            prospect_name=call.prospect_name,
            company_name=call.company_name,
            duration_seconds=call.duration_seconds,
            created_at=call.created_at.isoformat() if call.created_at else None,
            processing_completed_at=call.processing_completed_at.isoformat() if call.processing_completed_at else None
        )
        
    except Exception as e:
        logger.error(f"Failed to get call analysis: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get call analysis: {str(e)}"
        )

@router.get("/", response_model=List[CallListResponse])
async def list_calls(
    skip: int = 0,
    limit: int = 50,
    status_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all calls for the current user.
    """
    try:
        stmt = select(Call).where(
            Call.tenant_id == current_user.tenant_id,
            Call.user_id == current_user.id
        )
        
        if status_filter:
            stmt = stmt.where(Call.status == CallStatus(status_filter))
        
        stmt = stmt.offset(skip).limit(limit).order_by(Call.created_at.desc())
        
        result = await db.execute(stmt)
        calls = result.scalars().all()
        
        return [
            CallListResponse(
                id=call.id,
                prospect_name=call.prospect_name,
                company_name=call.company_name,
                status=call.status.value,
                created_at=call.created_at.isoformat() if call.created_at else None,
                quality_score=call.quality_metrics.get("call_quality_score") if call.quality_metrics else None,
                sentiment_score=call.insights.get("sentiment_score") if call.insights else None
            )
            for call in calls
        ]
        
    except Exception as e:
        logger.error(f"Failed to list calls: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list calls: {str(e)}"
        )