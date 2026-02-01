"""
Call management endpoints
"""
import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks, Depends, status, Query
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_, or_, func
import uuid
import datetime
import json
import csv
from io import StringIO

from app.core.database import get_db
from app.api.dependencies import (
    get_current_user, 
    get_current_manager, 
    get_current_admin,
    PaginationParams
)
from app.models.call import Call, CallStatus
from app.models.user import User
from app.schemas.call import (
    CallCreate, 
    CallResponse, 
    CallListResponse, 
    CallDetailResponse,
    CallUpdate,
    CallBulkDelete
)
from app.tasks.process_call import process_sales_call_task
from app.services.file_storage import FileStorageService
from app.services.transcription import AudioTranscriber
from app.services.call_processing import SalesCallProcessor

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
    call_type: Optional[str] = Form("sales"),
    meeting_platform: Optional[str] = Form(None),
    call_duration: Optional[float] = Form(None),
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
        allowed_types = [
            'audio/mpeg', 'audio/wav', 'audio/mp4', 
            'audio/x-m4a', 'audio/webm', 'video/mp4',
            'video/webm', 'video/x-msvideo'
        ]
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type. Allowed types: {', '.join(allowed_types)}"
            )
        
        # Validate file size (max 500MB)
        max_size = 500 * 1024 * 1024  # 500MB
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to beginning
        
        if file_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size is 500MB."
            )
    
    call_id = str(uuid.uuid4())
    created_at = datetime.datetime.utcnow()
    
    try:
        # Step 1: Save file to storage if provided
        file_url = None
        file_size = None
        
        if file:
            storage_service = FileStorageService()
            file_url = await storage_service.upload_file(
                file=file,
                tenant_id=current_user.tenant_id,
                user_id=current_user.id,
                call_id=call_id
            )
            file_size = file_size  # Use the calculated size
            
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
            call_type=call_type,
            meeting_platform=meeting_platform,
            duration_seconds=call_duration,
            status=CallStatus.PENDING,
            created_at=created_at,
            processing_started_at=None,
            processing_completed_at=None
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
        
        # Update call with processing started time
        call.processing_started_at = datetime.datetime.utcnow()
        await db.commit()
        
        logger.info(f"Call {call_id} uploaded successfully for user {current_user.id}")
        
        return CallResponse(
            id=call_id,
            status="processing",
            message="Call is being processed. You will be notified when it's ready.",
            created_at=call.created_at.isoformat() if call.created_at else None,
            prospect_name=call.prospect_name,
            company_name=call.company_name
        )
        
    except Exception as e:
        logger.error(f"Failed to upload call: {str(e)}", exc_info=True)
        
        # Clean up failed call record if it exists
        try:
            stmt = select(Call).where(Call.id == call_id)
            result = await db.execute(stmt)
            call = result.scalar_one_or_none()
            if call:
                await db.delete(call)
                await db.commit()
        except:
            pass
        
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
            Call.tenant_id == current_user.tenant_id,
            or_(
                Call.user_id == current_user.id,
                current_user.role.in_(["manager", "admin", "super_admin"])
            )
        )
        result = await db.execute(stmt)
        call = result.scalar_one_or_none()
        
        if not call:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Call not found or access denied"
            )
        
        return CallResponse(
            id=call.id,
            status=call.status.value,
            message=f"Call is {call.status.value}",
            created_at=call.created_at.isoformat() if call.created_at else None,
            processing_started_at=call.processing_started_at.isoformat() if call.processing_started_at else None,
            processing_completed_at=call.processing_completed_at.isoformat() if call.processing_completed_at else None,
            prospect_name=call.prospect_name,
            company_name=call.company_name
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
    include_transcript: bool = Query(False, description="Include full transcript in response"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get the complete analysis results for a call.
    """
    try:
        stmt = select(Call).where(
            Call.id == call_id,
            Call.tenant_id == current_user.tenant_id,
            or_(
                Call.user_id == current_user.id,
                current_user.role.in_(["manager", "admin", "super_admin"])
            )
        )
        result = await db.execute(stmt)
        call = result.scalar_one_or_none()
        
        if not call:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Call not found or access denied"
            )
        
        if call.status != CallStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Call analysis is not yet complete"
            )
        
        # Prepare response
        response_data = {
            "id": call.id,
            "status": call.status.value,
            "insights": call.insights or {},
            "quality_metrics": call.quality_metrics or {},
            "strategic_advice": call.strategic_advice or {},
            "crm_update_result": call.crm_update_result or {},
            "follow_up_email": call.follow_up_email,
            "prospect_name": call.prospect_name,
            "prospect_email": call.prospect_email,
            "company_name": call.company_name,
            "call_type": call.call_type,
            "meeting_platform": call.meeting_platform,
            "duration_seconds": call.duration_seconds,
            "created_at": call.created_at.isoformat() if call.created_at else None,
            "processing_completed_at": call.processing_completed_at.isoformat() if call.processing_completed_at else None
        }
        
        # Include transcript if requested and user has permission
        if include_transcript and call.processed_transcript:
            response_data["transcript"] = call.processed_transcript
        
        return CallDetailResponse(**response_data)
        
    except Exception as e:
        logger.error(f"Failed to get call analysis: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get call analysis: {str(e)}"
        )

@router.get("/", response_model=List[CallListResponse])
async def list_calls(
    pagination: PaginationParams = Depends(),
    status_filter: Optional[str] = Query(None, regex="^(pending|processing|completed|failed)$"),
    call_type: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None, description="Start date in ISO format"),
    end_date: Optional[str] = Query(None, description="End date in ISO format"),
    search: Optional[str] = Query(None, description="Search in prospect name or company"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all calls for the current user with filtering.
    """
    try:
        # Build query conditions
        conditions = [Call.tenant_id == current_user.tenant_id]
        
        # If not admin/manager, only show user's own calls
        if current_user.role not in ["manager", "admin", "super_admin"]:
            conditions.append(Call.user_id == current_user.id)
        
        # Apply filters
        if status_filter:
            conditions.append(Call.status == CallStatus(status_filter))
        
        if call_type:
            conditions.append(Call.call_type == call_type)
        
        if start_date:
            try:
                start_dt = datetime.datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                conditions.append(Call.created_at >= start_dt)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid start_date format. Use ISO format (YYYY-MM-DDTHH:MM:SSZ)"
                )
        
        if end_date:
            try:
                end_dt = datetime.datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                conditions.append(Call.created_at <= end_dt)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid end_date format. Use ISO format (YYYY-MM-DDTHH:MM:SSZ)"
                )
        
        if search:
            search_conditions = or_(
                Call.prospect_name.ilike(f"%{search}%"),
                Call.company_name.ilike(f"%{search}%"),
                Call.prospect_email.ilike(f"%{search}%")
            )
            conditions.append(search_conditions)
        
        # Build query
        stmt = select(Call).where(and_(*conditions))
        
        # Apply sorting
        sort_column = getattr(Call, pagination.sort_by, Call.created_at)
        if pagination.sort_order == "desc":
            stmt = stmt.order_by(desc(sort_column))
        else:
            stmt = stmt.order_by(sort_column)
        
        # Apply pagination
        stmt = stmt.offset(pagination.skip).limit(pagination.limit)
        
        result = await db.execute(stmt)
        calls = result.scalars().all()
        
        return [
            CallListResponse(
                id=call.id,
                prospect_name=call.prospect_name,
                company_name=call.company_name,
                status=call.status.value,
                created_at=call.created_at.isoformat() if call.created_at else None,
                processing_completed_at=call.processing_completed_at.isoformat() if call.processing_completed_at else None,
                quality_score=call.quality_metrics.get("call_quality_score") if call.quality_metrics else None,
                sentiment_score=call.insights.get("sentiment_score") if call.insights else None,
                call_type=call.call_type,
                duration_seconds=call.duration_seconds,
                user_id=call.user_id
            )
            for call in calls
        ]
        
    except Exception as e:
        logger.error(f"Failed to list calls: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list calls: {str(e)}"
        )

@router.delete("/{call_id}")
async def delete_call(
    call_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a call and its associated data.
    """
    try:
        stmt = select(Call).where(
            Call.id == call_id,
            Call.tenant_id == current_user.tenant_id,
            or_(
                Call.user_id == current_user.id,
                current_user.role.in_(["admin", "super_admin"])
            )
        )
        result = await db.execute(stmt)
        call = result.scalar_one_or_none()
        
        if not call:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Call not found or access denied"
            )
        
        # Delete associated files from storage
        if call.file_url:
            try:
                storage_service = FileStorageService()
                await storage_service.delete_file(call.file_url)
            except Exception as e:
                logger.warning(f"Failed to delete file from storage: {str(e)}")
        
        # Delete call from database
        await db.delete(call)
        await db.commit()
        
        logger.info(f"Call {call_id} deleted by user {current_user.id}")
        
        return {"message": "Call deleted successfully"}
        
    except Exception as e:
        logger.error(f"Failed to delete call: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete call: {str(e)}"
        )

@router.post("/bulk-delete")
async def bulk_delete_calls(
    call_ids: List[str],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete multiple calls at once.
    """
    try:
        if not call_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No call IDs provided"
            )
        
        # Check permissions and get calls to delete
        conditions = [
            Call.id.in_(call_ids),
            Call.tenant_id == current_user.tenant_id
        ]
        
        # Regular users can only delete their own calls
        if current_user.role not in ["admin", "super_admin"]:
            conditions.append(Call.user_id == current_user.id)
        
        stmt = select(Call).where(and_(*conditions))
        result = await db.execute(stmt)
        calls = result.scalars().all()
        
        deleted_count = 0
        storage_service = FileStorageService()
        
        for call in calls:
            # Delete associated files
            if call.file_url:
                try:
                    await storage_service.delete_file(call.file_url)
                except Exception as e:
                    logger.warning(f"Failed to delete file from storage: {str(e)}")
            
            # Delete call from database
            await db.delete(call)
            deleted_count += 1
        
        await db.commit()
        
        logger.info(f"Bulk deleted {deleted_count} calls by user {current_user.id}")
        
        return {
            "message": f"Successfully deleted {deleted_count} calls",
            "deleted_count": deleted_count
        }
        
    except Exception as e:
        logger.error(f"Failed to bulk delete calls: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to bulk delete calls: {str(e)}"
        )

@router.get("/{call_id}/transcript")
async def get_call_transcript(
    call_id: str,
    format: str = Query("text", regex="^(text|json)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get the transcript for a call.
    """
    try:
        stmt = select(Call).where(
            Call.id == call_id,
            Call.tenant_id == current_user.tenant_id,
            or_(
                Call.user_id == current_user.id,
                current_user.role.in_(["manager", "admin", "super_admin"])
            )
        )
        result = await db.execute(stmt)
        call = result.scalar_one_or_none()
        
        if not call:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Call not found or access denied"
            )
        
        if not call.processed_transcript:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transcript not available for this call"
            )
        
        if format == "json":
            return {
                "call_id": call.id,
                "transcript": call.processed_transcript,
                "prospect_name": call.prospect_name,
                "company_name": call.company_name,
                "created_at": call.created_at.isoformat() if call.created_at else None
            }
        else:
            # Return as plain text
            transcript_text = f"Call Transcript - {call.prospect_name} ({call.company_name})\n"
            transcript_text += f"Date: {call.created_at.strftime('%Y-%m-%d %H:%M') if call.created_at else 'N/A'}\n"
            transcript_text += f"Duration: {call.duration_seconds:.0f}s\n" if call.duration_seconds else "Duration: N/A\n"
            transcript_text += "=" * 50 + "\n\n"
            transcript_text += call.processed_transcript
            
            return transcript_text
        
    except Exception as e:
        logger.error(f"Failed to get call transcript: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get call transcript: {str(e)}"
        )

@router.post("/{call_id}/reprocess")
async def reprocess_call(
    call_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Reprocess a call analysis.
    """
    try:
        stmt = select(Call).where(
            Call.id == call_id,
            Call.tenant_id == current_user.tenant_id,
            or_(
                Call.user_id == current_user.id,
                current_user.role.in_(["admin", "super_admin"])
            )
        )
        result = await db.execute(stmt)
        call = result.scalar_one_or_none()
        
        if not call:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Call not found or access denied"
            )
        
        # Reset call status
        call.status = CallStatus.PENDING
        call.processing_started_at = datetime.datetime.utcnow()
        call.processing_completed_at = None
        call.insights = None
        call.quality_metrics = None
        call.strategic_advice = None
        call.crm_update_result = None
        call.follow_up_email = None
        
        await db.commit()
        
        # Trigger reprocessing
        background_tasks.add_task(
            process_sales_call_task.delay,
            call_id=call_id,
            file_url=call.file_url,
            transcript_text=call.original_transcript or call.processed_transcript,
            tenant_id=current_user.tenant_id,
            user_id=current_user.id
        )
        
        logger.info(f"Call {call_id} reprocessing triggered by user {current_user.id}")
        
        return {"message": "Call is being reprocessed"}
        
    except Exception as e:
        logger.error(f"Failed to reprocess call: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reprocess call: {str(e)}"
        )

@router.get("/export/csv")
async def export_calls_csv(
    start_date: Optional[str] = Query(None, description="Start date in ISO format"),
    end_date: Optional[str] = Query(None, description="End date in ISO format"),
    call_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_manager)
):
    """
    Export calls to CSV format.
    """
    try:
        # Build query conditions
        conditions = [Call.tenant_id == current_user.tenant_id]
        
        if start_date:
            try:
                start_dt = datetime.datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                conditions.append(Call.created_at >= start_dt)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid start_date format"
                )
        
        if end_date:
            try:
                end_dt = datetime.datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                conditions.append(Call.created_at <= end_dt)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid end_date format"
                )
        
        if call_type:
            conditions.append(Call.call_type == call_type)
        
        # Get calls
        stmt = select(Call).where(and_(*conditions)).order_by(desc(Call.created_at))
        result = await db.execute(stmt)
        calls = result.scalars().all()
        
        # Create CSV
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            "Call ID",
            "Prospect Name",
            "Company",
            "Email",
            "Call Type",
            "Platform",
            "Duration (s)",
            "Status",
            "Quality Score",
            "Sentiment Score",
            "Created Date",
            "Completed Date"
        ])
        
        # Write data
        for call in calls:
            quality_score = call.quality_metrics.get("call_quality_score") if call.quality_metrics else "N/A"
            sentiment_score = call.insights.get("sentiment_score") if call.insights else "N/A"
            
            writer.writerow([
                call.id,
                call.prospect_name or "",
                call.company_name or "",
                call.prospect_email or "",
                call.call_type or "",
                call.meeting_platform or "",
                call.duration_seconds or "",
                call.status.value,
                quality_score,
                sentiment_score,
                call.created_at.strftime('%Y-%m-%d %H:%M:%S') if call.created_at else "",
                call.processing_completed_at.strftime('%Y-%m-%d %H:%M:%S') if call.processing_completed_at else ""
            ])
        
        # Prepare response
        output.seek(0)
        filename = f"sales_calls_export_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        
        logger.info(f"CSV export generated by user {current_user.id} with {len(calls)} calls")
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"Failed to export calls to CSV: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export calls: {str(e)}"
        )