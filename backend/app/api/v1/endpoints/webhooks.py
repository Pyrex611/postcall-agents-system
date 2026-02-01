"""
Webhook endpoints for external integrations
"""
import logging
import hashlib
import hmac
import json
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, status, Header, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.api.dependencies import get_current_admin
from app.models.user import User
from app.services.webhook_service import WebhookService

logger = logging.getLogger(__name__)
router = APIRouter()
webhook_service = WebhookService()

@router.post("/incoming/{webhook_id}")
async def handle_incoming_webhook(
    webhook_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature: Optional[str] = Header(None),
    x_signature: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Handle incoming webhooks from external services.
    """
    try:
        # Get webhook payload
        payload = await request.body()
        payload_str = payload.decode('utf-8')
        payload_data = json.loads(payload_str) if payload_str else {}
        
        # Get headers
        headers = dict(request.headers)
        
        # Process webhook in background
        background_tasks.add_task(
            webhook_service.process_incoming_webhook,
            webhook_id=webhook_id,
            payload=payload_data,
            headers=headers,
            signature=x_hub_signature or x_signature,
            db=db
        )
        
        logger.info(f"Received webhook {webhook_id}, processing in background")
        
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={"message": "Webhook received and processing"}
        )
        
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in webhook {webhook_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )
    except Exception as e:
        logger.error(f"Failed to handle webhook {webhook_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process webhook: {str(e)}"
        )

@router.post("/call-completed")
async def handle_call_completed_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Webhook for call recording services (Zoom, Google Meet, etc.)
    """
    try:
        payload = await request.json()
        
        # Validate required fields
        required_fields = ["call_id", "recording_url", "participants"]
        for field in required_fields:
            if field not in payload:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing required field: {field}"
                )
        
        # Process call completion in background
        background_tasks.add_task(
            webhook_service.process_call_completion,
            call_data=payload,
            db=db
        )
        
        logger.info(f"Call completed webhook received for call {payload.get('call_id')}")
        
        return {"message": "Call completion webhook received"}
        
    except Exception as e:
        logger.error(f"Call completed webhook failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process call completion: {str(e)}"
        )

@router.post("/crm-update")
async def handle_crm_update_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Webhook for CRM update notifications.
    """
    try:
        payload = await request.json()
        
        # Process CRM update in background
        background_tasks.add_task(
            webhook_service.process_crm_update,
            crm_data=payload,
            db=db
        )
        
        logger.info("CRM update webhook received")
        
        return {"message": "CRM update webhook received"}
        
    except Exception as e:
        logger.error(f"CRM update webhook failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process CRM update: {str(e)}"
        )

@router.get("/outgoing")
async def list_outgoing_webhooks(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    List configured outgoing webhooks.
    """
    try:
        webhooks = await webhook_service.get_webhooks(
            tenant_id=current_user.tenant_id,
            db=db
        )
        
        return {
            "webhooks": webhooks,
            "count": len(webhooks)
        }
        
    except Exception as e:
        logger.error(f"Failed to list webhooks: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list webhooks: {str(e)}"
        )

@router.post("/outgoing")
async def create_outgoing_webhook(
    webhook_data: Dict[str, Any],
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new outgoing webhook.
    """
    try:
        required_fields = ["url", "events", "name"]
        for field in required_fields:
            if field not in webhook_data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing required field: {field}"
                )
        
        webhook = await webhook_service.create_webhook(
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            webhook_data=webhook_data,
            db=db
        )
        
        logger.info(f"Webhook created: {webhook_data.get('name')}")
        
        return {
            "message": "Webhook created successfully",
            "webhook_id": webhook.id,
            "secret_key": webhook.secret_key
        }
        
    except Exception as e:
        logger.error(f"Failed to create webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create webhook: {str(e)}"
        )

@router.delete("/outgoing/{webhook_id}")
async def delete_outgoing_webhook(
    webhook_id: str,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete an outgoing webhook.
    """
    try:
        success = await webhook_service.delete_webhook(
            webhook_id=webhook_id,
            tenant_id=current_user.tenant_id,
            db=db
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook not found"
            )
        
        logger.info(f"Webhook deleted: {webhook_id}")
        
        return {"message": "Webhook deleted successfully"}
        
    except Exception as e:
        logger.error(f"Failed to delete webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete webhook: {str(e)}"
        )

@router.post("/test/{webhook_id}")
async def test_webhook(
    webhook_id: str,
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Test a webhook configuration.
    """
    try:
        result = await webhook_service.test_webhook(
            webhook_id=webhook_id,
            tenant_id=current_user.tenant_id,
            db=db
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Webhook test failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Webhook test failed: {str(e)}"
        )

@router.get("/events")
async def get_available_events():
    """
    Get list of available webhook events.
    """
    return {
        "events": [
            {
                "id": "call.completed",
                "name": "Call Completed",
                "description": "Triggered when a call analysis is completed",
                "payload_example": {
                    "call_id": "uuid",
                    "status": "completed",
                    "insights": {},
                    "quality_metrics": {}
                }
            },
            {
                "id": "crm.updated",
                "name": "CRM Updated",
                "description": "Triggered when CRM is successfully updated",
                "payload_example": {
                    "call_id": "uuid",
                    "crm_type": "salesforce",
                    "record_id": "record_id",
                    "status": "success"
                }
            },
            {
                "id": "call.failed",
                "name": "Call Failed",
                "description": "Triggered when call processing fails",
                "payload_example": {
                    "call_id": "uuid",
                    "error": "Error message",
                    "status": "failed"
                }
            },
            {
                "id": "user.activity",
                "name": "User Activity",
                "description": "Triggered on user login/logout/call upload",
                "payload_example": {
                    "user_id": "uuid",
                    "activity_type": "login",
                    "timestamp": "2024-01-01T00:00:00Z"
                }
            }
        ]
    }