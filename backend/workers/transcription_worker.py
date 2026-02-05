from celery import Task
from workers.celery_app import celery_app
from services.transcription_service import transcription_service
from services.ai_service import ai_service
from core.database import SessionLocal
from models.call import Call
from models.transcript import Transcript
from models.insight import Insight
from models.quality_metric import QualityMetric
import logging

logger = logging.getLogger(__name__)

class CallbackTask(Task):
    """Task with callback on success/failure"""
    
    def on_success(self, retval, task_id, args, kwargs):
        logger.info(f"Task {task_id} succeeded")
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(f"Task {task_id} failed: {exc}")

@celery_app.task(base=CallbackTask, bind=True, max_retries=3)
def process_call_recording(self, call_id: str):
    """
    Complete pipeline: transcribe → analyze → store
    
    This is the main worker task that processes uploaded call recordings
    """
    db = SessionLocal()
    
    try:
        # 1. Get call from database
        call = db.query(Call).filter(Call.id == call_id).first()
        if not call:
            raise ValueError(f"Call {call_id} not found")
        
        call.status = "processing"
        db.commit()
        
        # 2. Transcribe audio
        logger.info(f"Transcribing call {call_id}")
        transcription_result = await transcription_service.transcribe_audio(
            audio_url=call.recording_url,
            language="en",
            diarization=True
        )
        
        # 3. Save transcript
        transcript = Transcript(
            call_id=call_id,
            content=transcription_result["transcript"],
            confidence=transcription_result["confidence"],
            speaker_labels=transcription_result["speakers"],
            provider=transcription_result["provider"]
        )
        db.add(transcript)
        db.commit()
        
        # 4. AI analysis
        logger.info(f"Analyzing call {call_id}")
        analysis_result = await ai_service.analyze_call(
            transcript=transcription_result["transcript"]
        )
        
        # 5. Save insights
        insight = Insight(
            call_id=call_id,
            prospect_name=analysis_result.get("prospect_name"),
            company_name=analysis_result.get("company_name"),
            summary=analysis_result.get("summary"),
            pain_points=analysis_result.get("pain_points", []),
            sentiment_score=analysis_result.get("sentiment_score"),
            next_steps=analysis_result.get("next_steps", []),
            follow_up_email=analysis_result.get("follow_up_email"),
            competitors_mentioned=analysis_result.get("competitors_mentioned", []),
            objections=analysis_result.get("objections", [])
        )
        db.add(insight)
        
        # 6. Save quality metrics
        quality_data = analysis_result.get("quality_metrics", {})
        quality = QualityMetric(
            call_id=call_id,
            quality_score=quality_data.get("quality_score"),
            asked_for_meeting=quality_data.get("asked_for_meeting", False),
            talk_ratio=quality_data.get("talk_ratio"),
            questions_asked=quality_data.get("questions_asked", 0),
            strengths=quality_data.get("strengths", []),
            improvements=quality_data.get("improvements", [])
        )
        db.add(quality)
        
        # 7. Update call status
        call.status = "completed"
        db.commit()
        
        logger.info(f"Successfully processed call {call_id}")
        
        # 8. Trigger webhook notifications
        from workers.webhook_worker import trigger_webhooks
        trigger_webhooks.delay(call.organization_id, "call.completed", {"call_id": call_id})
        
        # 9. Sync to CRM if enabled
        from workers.sync_worker import sync_to_crm
        sync_to_crm.delay(call.organization_id, call_id)
        
        return {"status": "success", "call_id": call_id}
        
    except Exception as e:
        logger.error(f"Error processing call {call_id}: {e}")
        call.status = "failed"
        db.commit()
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
    
    finally:
        db.close()