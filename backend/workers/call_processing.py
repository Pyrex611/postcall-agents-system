"""
Background worker for call processing: transcription → analysis → storage
"""
from celery import Task
from workers.celery_app import celery_app
from services.transcription_service import transcription_service
from services.ai_service import ai_service
from core.database import SessionLocal
from models.call import Call
from models.__init__ import Transcript, Insight, QualityMetric
import logging

logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    """Base task with database session management"""
    _db = None
    
    @property
    def db(self):
        if self._db is None:
            self._db = SessionLocal()
        return self._db
    
    def after_return(self, *args, **kwargs):
        if self._db is not None:
            self._db.close()
            self._db = None


@celery_app.task(base=DatabaseTask, bind=True, max_retries=3, default_retry_delay=60)
def process_call_recording(self, call_id: str):
    """
    Main processing pipeline for call recordings
    
    Steps:
    1. Fetch call from database
    2. Transcribe audio
    3. AI analysis
    4. Save insights and metrics
    5. Trigger webhooks
    """
    logger.info(f"Processing call {call_id}")
    db = self.db
    
    try:
        # 1. Get call
        call = db.query(Call).filter(Call.id == call_id).first()
        if not call:
            logger.error(f"Call {call_id} not found")
            return {"status": "error", "message": "Call not found"}
        
        call.status = "processing"
        db.commit()
        
        # 2. Transcribe (if recording URL exists)
        transcript_data = None
        if call.recording_url:
            logger.info(f"Transcribing call {call_id}")
            transcript_data = transcription_service.transcribe_audio(
                audio_url=call.recording_url,
                language="en",
                diarization=True
            )
            
            # Save transcript
            transcript = Transcript(
                call_id=call_id,
                content=transcript_data["transcript"],
                confidence=transcript_data["confidence"],
                speaker_labels=transcript_data["speakers"],
                provider=transcript_data["provider"]
            )
            db.add(transcript)
            
            # Update call duration if available
            if transcript_data.get("duration"):
                call.duration_seconds = int(transcript_data["duration"])
            
            db.commit()
            logger.info(f"Transcript saved for call {call_id}")
        else:
            # For manual transcript input (uploaded text)
            transcript_obj = db.query(Transcript).filter(Transcript.call_id == call_id).first()
            if transcript_obj:
                transcript_data = {"transcript": transcript_obj.content}
        
        if not transcript_data:
            raise ValueError("No transcript available for analysis")
        
        # 3. AI Analysis
        logger.info(f"Analyzing call {call_id}")
        analysis = ai_service.analyze_call(
            transcript=transcript_data["transcript"]
        )
        
        # 4. Save insights
        insight = Insight(
            call_id=call_id,
            prospect_name=analysis.get("prospect_name"),
            company_name=analysis.get("company_name"),
            summary=analysis.get("summary"),
            pain_points=analysis.get("pain_points", []),
            sentiment_score=analysis.get("sentiment_score"),
            next_steps=analysis.get("next_steps", []),
            follow_up_email=analysis.get("follow_up_email"),
            competitors_mentioned=analysis.get("competitors_mentioned", []),
            objections=analysis.get("objections", [])
        )
        db.add(insight)
        
        # 5. Save quality metrics
        quality_data = analysis.get("quality_metrics", {})
        quality = QualityMetric(
            call_id=call_id,
            quality_score=quality_data.get("quality_score"),
            asked_for_meeting=quality_data.get("asked_for_meeting", False),
            talk_ratio=quality_data.get("talk_ratio"),
            questions_asked=quality_data.get("questions_asked", 0),
            strengths=quality_data.get("strengths", []),
            improvements=quality_data.get("improvements", []),
            playbook_adherence=quality_data.get("playbook_adherence")
        )
        db.add(quality)
        
        # 6. Update call status
        call.status = "completed"
        db.commit()
        
        logger.info(f"Successfully processed call {call_id}")
        
        # 7. Trigger async tasks
        from workers.webhooks import trigger_webhooks
        from workers.crm_sync import sync_call_to_crm
        
        trigger_webhooks.delay(str(call.organization_id), "call.completed", {"call_id": call_id})
        sync_call_to_crm.delay(str(call.organization_id), call_id)
        
        return {
            "status": "success",
            "call_id": call_id,
            "transcript_length": len(transcript_data["transcript"]),
            "sentiment_score": analysis.get("sentiment_score"),
            "quality_score": quality_data.get("quality_score")
        }
        
    except Exception as e:
        logger.error(f"Error processing call {call_id}: {e}", exc_info=True)
        
        # Update call status
        call = db.query(Call).filter(Call.id == call_id).first()
        if call:
            call.status = "failed"
            db.commit()
        
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@celery_app.task(bind=True)
def process_text_transcript(self, call_id: str, transcript_text: str):
    """
    Process text-only transcript (no audio)
    
    Useful for manual transcript uploads
    """
    logger.info(f"Processing text transcript for call {call_id}")
    db = SessionLocal()
    
    try:
        call = db.query(Call).filter(Call.id == call_id).first()
        if not call:
            return {"status": "error", "message": "Call not found"}
        
        # Save transcript
        transcript = Transcript(
            call_id=call_id,
            content=transcript_text,
            language="en",
            provider="manual"
        )
        db.add(transcript)
        db.commit()
        
        # Delegate to main processing
        process_call_recording.delay(call_id)
        
        return {"status": "queued", "call_id": call_id}
        
    except Exception as e:
        logger.error(f"Error processing text transcript: {e}")
        raise
    finally:
        db.close()
