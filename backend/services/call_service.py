"""
Call Processing Service
Handles the complete lifecycle of call analysis
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timedelta
import asyncio
import logging

from backend.models.database import (
    Call,
    CallCreate,
    CallAnalysis,
    CallAnalysisCreate,
    ProcessingStatus,
    CRMSyncLog,
    Job,
    JobCreate
)
from backend.core.exceptions import NotFoundException, ValidationException
from backend.integrations.crm.base import CRMConnectorFactory, CRMContact, CRMActivity
from backend.services.ai_service import AIService
from backend.services.rag_service import RAGService
from backend.services.transcription_service import TranscriptionService
from backend.database import Database

logger = logging.getLogger(__name__)


class CallProcessingService:
    """
    Service for processing sales calls through the entire pipeline:
    1. Transcription (if audio)
    2. AI Analysis
    3. RAG Enhancement
    4. CRM Sync
    5. Recommendations
    """
    
    def __init__(self):
        self.ai_service = AIService()
        self.rag_service = RAGService()
        self.transcription_service = TranscriptionService()
    
    async def create_call(
        self,
        call_data: CallCreate,
        audio_file_path: Optional[str] = None,
        transcript: Optional[str] = None
    ) -> Call:
        """
        Create a new call record and queue for processing
        
        Args:
            call_data: Call creation data
            audio_file_path: Path to audio file (if uploaded)
            transcript: Pre-existing transcript (if available)
            
        Returns:
            Created Call object
        """
        db = await Database.get_session()
        
        try:
            # Create call record
            call = await db.create_call(call_data)
            
            # If audio file is provided, store URL
            if audio_file_path:
                await db.update_call(
                    call.id,
                    {"audio_file_url": audio_file_path}
                )
            
            # If transcript is provided, store it
            if transcript:
                await db.update_call(
                    call.id,
                    {
                        "raw_transcript": transcript,
                        "processing_status": ProcessingStatus.ANALYZING
                    }
                )
            
            # Queue job for async processing
            job = JobCreate(
                organization_id=call_data.organization_id,
                job_type="process_call",
                payload={
                    "call_id": str(call.id),
                    "has_audio": audio_file_path is not None,
                    "has_transcript": transcript is not None
                },
                priority=7  # Higher priority for user-initiated uploads
            )
            
            await db.create_job(job)
            logger.info(f"Created call {call.id} and queued for processing")
            
            return call
            
        except Exception as e:
            logger.error(f"Error creating call: {e}")
            raise
    
    async def process_call(self, call_id: UUID) -> CallAnalysis:
        """
        Main processing pipeline for a call
        
        This is typically called by a background worker (Celery task)
        
        Pipeline:
        1. Transcribe (if needed)
        2. Basic AI Analysis
        3. RAG Enhancement (find relevant knowledge)
        4. Methodology Scoring
        5. Generate Recommendations
        6. Sync to CRM
        
        Args:
            call_id: ID of call to process
            
        Returns:
            CallAnalysis object with complete analysis
        """
        db = await Database.get_session()
        call = await db.get_call(call_id)
        
        if not call:
            raise NotFoundException(f"Call {call_id} not found")
        
        try:
            # Update status
            await db.update_call(
                call_id,
                {
                    "processing_status": ProcessingStatus.ANALYZING,
                    "processing_started_at": datetime.utcnow()
                }
            )
            
            # Step 1: Get transcript
            transcript = await self._ensure_transcript(call)
            
            # Step 2: Basic AI analysis
            logger.info(f"Analyzing call {call_id}")
            analysis_data = await self.ai_service.analyze_call(transcript, call)
            
            # Step 3: RAG Enhancement
            if analysis_data.get('pain_points'):
                logger.info(f"Enhancing analysis with RAG for call {call_id}")
                rag_insights = await self.rag_service.enhance_analysis(
                    pain_points=analysis_data['pain_points'],
                    objections=analysis_data.get('objections', []),
                    organization_id=call.organization_id
                )
                analysis_data['rag_insights'] = rag_insights
            
            # Step 4: Methodology scoring (if playbook configured)
            playbook = await db.get_organization_default_playbook(call.organization_id)
            if playbook:
                logger.info(f"Scoring call {call_id} with playbook {playbook.id}")
                methodology_score = await self.ai_service.score_methodology(
                    transcript,
                    playbook.criteria
                )
                analysis_data['methodology_score'] = methodology_score
            
            # Step 5: Generate strategic recommendations
            logger.info(f"Generating recommendations for call {call_id}")
            recommendations = await self.ai_service.generate_recommendations(
                analysis_data,
                call
            )
            analysis_data['strategic_advice'] = recommendations['advice']
            analysis_data['recommended_actions'] = recommendations['actions']
            analysis_data['deal_risk_level'] = recommendations['risk_level']
            
            # Step 6: Create analysis record
            analysis_create = CallAnalysisCreate(
                call_id=call_id,
                organization_id=call.organization_id,
                **analysis_data
            )
            
            analysis = await db.create_call_analysis(analysis_create)
            
            # Step 7: Sync to CRM (async, don't wait)
            asyncio.create_task(
                self._sync_to_crm(call, analysis)
            )
            
            # Step 8: Update call status
            await db.update_call(
                call_id,
                {
                    "processing_status": ProcessingStatus.COMPLETED,
                    "processing_completed_at": datetime.utcnow()
                }
            )
            
            logger.info(f"✅ Successfully processed call {call_id}")
            return analysis
            
        except Exception as e:
            logger.error(f"Error processing call {call_id}: {e}")
            
            # Update call with error
            await db.update_call(
                call_id,
                {
                    "processing_status": ProcessingStatus.FAILED,
                    "error_message": str(e),
                    "processing_completed_at": datetime.utcnow()
                }
            )
            raise
    
    async def _ensure_transcript(self, call: Call) -> str:
        """
        Ensure call has a transcript, transcribe if needed
        
        Args:
            call: Call object
            
        Returns:
            Transcript text
        """
        if call.raw_transcript:
            return call.raw_transcript
        
        if not call.audio_file_url:
            raise ValidationException("Call has no transcript or audio file")
        
        logger.info(f"Transcribing audio for call {call.id}")
        
        # Update status
        db = await Database.get_session()
        await db.update_call(
            call.id,
            {"processing_status": ProcessingStatus.TRANSCRIBING}
        )
        
        # Transcribe
        transcript = await self.transcription_service.transcribe(
            audio_url=call.audio_file_url,
            enable_diarization=True  # Speaker separation
        )
        
        # Save transcript
        await db.update_call(
            call.id,
            {
                "raw_transcript": transcript.text,
                "duration_seconds": transcript.duration_seconds
            }
        )
        
        return transcript.text
    
    async def _sync_to_crm(self, call: Call, analysis: CallAnalysis):
        """
        Sync call data to CRM
        
        This runs asynchronously and logs results
        """
        db = await Database.get_session()
        
        try:
            # Get CRM connection for organization
            crm_connection = await db.get_active_crm_connection(call.organization_id)
            
            if not crm_connection:
                logger.info(f"No CRM connection for organization {call.organization_id}")
                return
            
            # Create CRM connector
            connector = CRMConnectorFactory.create(
                crm_type=crm_connection.crm_type,
                access_token=crm_connection.access_token_decrypted,  # Decrypt in production
                refresh_token=crm_connection.refresh_token_decrypted,
                instance_url=crm_connection.instance_url,
                field_mappings=crm_connection.field_mappings
            )
            
            # Authenticate
            auth_success = await connector.authenticate()
            if not auth_success:
                logger.error(f"CRM authentication failed for {crm_connection.crm_type}")
                return
            
            # 1. Upsert contact
            if analysis.prospect_email:
                contact = CRMContact(
                    first_name=analysis.prospect_name.split()[0] if analysis.prospect_name else None,
                    last_name=' '.join(analysis.prospect_name.split()[1:]) if analysis.prospect_name and len(analysis.prospect_name.split()) > 1 else 'Unknown',
                    email=analysis.prospect_email,
                    phone=analysis.prospect_phone,
                    title=analysis.prospect_title,
                    company=analysis.prospect_company
                )
                
                contact_result = await connector.upsert_contact(contact)
                
                # Log sync
                await db.create_crm_sync_log(
                    call_id=call.id,
                    crm_connection_id=crm_connection.id,
                    action="upsert_contact",
                    crm_entity_type="Contact",
                    crm_entity_id=contact_result.entity_id,
                    status="success" if contact_result.success else "failed",
                    error_message=contact_result.error_message
                )
                
                # 2. Log activity
                if contact_result.success and contact_result.entity_id:
                    activity = CRMActivity(
                        subject=f"Sales Call - {analysis.prospect_company}",
                        description=analysis.summary,
                        activity_type="call",
                        activity_date=call.call_date or datetime.utcnow(),
                        duration_minutes=call.duration_seconds // 60 if call.duration_seconds else None,
                        status="Completed",
                        related_to_id=contact_result.entity_id
                    )
                    
                    activity_result = await connector.create_activity(activity)
                    
                    await db.create_crm_sync_log(
                        call_id=call.id,
                        crm_connection_id=crm_connection.id,
                        action="create_activity",
                        crm_entity_type="Activity",
                        crm_entity_id=activity_result.entity_id,
                        status="success" if activity_result.success else "failed",
                        error_message=activity_result.error_message
                    )
                
                logger.info(f"✅ Synced call {call.id} to CRM")
            
        except Exception as e:
            logger.error(f"CRM sync failed for call {call.id}: {e}")
            
            # Log failure
            await db.create_crm_sync_log(
                call_id=call.id,
                crm_connection_id=crm_connection.id if crm_connection else None,
                action="sync_failed",
                status="failed",
                error_message=str(e)
            )
    
    async def get_call_with_analysis(self, call_id: UUID) -> Dict[str, Any]:
        """
        Get call with full analysis data
        
        Args:
            call_id: Call ID
            
        Returns:
            Complete call data with analysis
        """
        db = await Database.get_session()
        
        call = await db.get_call(call_id)
        if not call:
            raise NotFoundException(f"Call {call_id} not found")
        
        analysis = await db.get_call_analysis(call_id)
        crm_logs = await db.get_crm_sync_logs(call_id)
        
        return {
            "call": call,
            "analysis": analysis,
            "crm_sync_logs": crm_logs,
            "processing_complete": call.processing_status == ProcessingStatus.COMPLETED
        }
    
    async def reprocess_call(self, call_id: UUID) -> CallAnalysis:
        """
        Reprocess a call (useful if analysis failed or needs updating)
        
        Args:
            call_id: Call ID
            
        Returns:
            New analysis
        """
        db = await Database.get_session()
        
        # Reset status
        await db.update_call(
            call_id,
            {
                "processing_status": ProcessingStatus.PENDING,
                "error_message": None
            }
        )
        
        # Queue for reprocessing
        job = JobCreate(
            job_type="process_call",
            payload={"call_id": str(call_id)},
            priority=8  # Higher priority for reprocessing
        )
        
        await db.create_job(job)
        
        logger.info(f"Queued call {call_id} for reprocessing")
        
        # In development, process synchronously
        # In production, this would be picked up by Celery
        from backend.config import settings
        if settings.ENVIRONMENT == "development":
            return await self.process_call(call_id)
        
        # Return pending call
        call = await db.get_call(call_id)
        return call
    
    async def get_calls_for_organization(
        self,
        organization_id: UUID,
        limit: int = 50,
        offset: int = 0,
        status: Optional[ProcessingStatus] = None
    ) -> List[Call]:
        """Get calls for an organization"""
        db = await Database.get_session()
        return await db.get_calls_for_organization(
            organization_id,
            limit=limit,
            offset=offset,
            status=status
        )
    
    async def get_calls_for_user(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0
    ) -> List[Call]:
        """Get calls for a specific user/rep"""
        db = await Database.get_session()
        return await db.get_calls_for_user(user_id, limit=limit, offset=offset)