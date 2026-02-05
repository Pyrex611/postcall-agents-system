"""
Webhook and CRM sync workers
"""
from workers.celery_app import celery_app
from core.database import SessionLocal
from models.__init__ import Webhook, CRMIntegration
from models.call import Call
import httpx
import logging

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def trigger_webhooks(self, organization_id: str, event_type: str, data: dict):
    """
    Trigger webhooks for an event
    
    Args:
        organization_id: Organization UUID
        event_type: Event type (e.g., 'call.completed')
        data: Event data
    """
    db = SessionLocal()
    
    try:
        # Get active webhooks for this organization and event
        webhooks = db.query(Webhook).filter(
            Webhook.organization_id == organization_id,
            Webhook.is_active == True
        ).all()
        
        for webhook in webhooks:
            # Check if webhook is configured for this event
            if event_type not in webhook.events:
                continue
            
            # Prepare payload
            payload = {
                "event": event_type,
                "data": data,
                "organization_id": organization_id
            }
            
            # Send webhook
            try:
                response = httpx.post(
                    webhook.url,
                    json=payload,
                    headers={"X-Webhook-Secret": webhook.secret} if webhook.secret else {},
                    timeout=30.0
                )
                response.raise_for_status()
                logger.info(f"Webhook sent: {webhook.url} for {event_type}")
            except Exception as e:
                logger.error(f"Webhook failed: {webhook.url} - {e}")
                raise self.retry(exc=e, countdown=60)
        
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def sync_call_to_crm(self, organization_id: str, call_id: str):
    """
    Sync call data to CRM
    
    Supports Salesforce, HubSpot, and other CRMs
    """
    db = SessionLocal()
    
    try:
        # Get CRM integrations
        integrations = db.query(CRMIntegration).filter(
            CRMIntegration.organization_id == organization_id,
            CRMIntegration.sync_enabled == True
        ).all()
        
        if not integrations:
            logger.info(f"No CRM integrations enabled for org {organization_id}")
            return
        
        # Get call data
        call = db.query(Call).filter(Call.id == call_id).first()
        if not call or not call.insight:
            logger.warning(f"Call {call_id} not ready for CRM sync")
            return
        
        insight = call.insight
        
        for integration in integrations:
            try:
                if integration.provider == "salesforce":
                    sync_to_salesforce(integration, call, insight)
                elif integration.provider == "hubspot":
                    sync_to_hubspot(integration, call, insight)
                elif integration.provider == "pipedrive":
                    sync_to_pipedrive(integration, call, insight)
                
                # Update last sync time
                from datetime import datetime
                integration.last_sync = datetime.utcnow()
                db.commit()
                
                logger.info(f"Synced call {call_id} to {integration.provider}")
                
            except Exception as e:
                logger.error(f"CRM sync failed for {integration.provider}: {e}")
                raise self.retry(exc=e, countdown=120)
    
    finally:
        db.close()


def sync_to_salesforce(integration, call, insight):
    """Sync to Salesforce"""
    from simple_salesforce import Salesforce
    
    credentials = integration.credentials
    sf = Salesforce(
        username=credentials.get("username"),
        password=credentials.get("password"),
        security_token=credentials.get("security_token"),
        domain=credentials.get("domain", "login")
    )
    
    # Create or update contact
    if insight.company_name:
        contact_data = {
            "FirstName": insight.prospect_name.split()[0] if insight.prospect_name else "",
            "LastName": insight.prospect_name.split()[-1] if insight.prospect_name else "Unknown",
            "Company": insight.company_name,
            "Description": insight.summary
        }
        sf.Contact.create(contact_data)


def sync_to_hubspot(integration, call, insight):
    """Sync to HubSpot"""
    credentials = integration.credentials
    api_key = credentials.get("api_key")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Create contact
    contact_data = {
        "properties": {
            "firstname": insight.prospect_name.split()[0] if insight.prospect_name else "",
            "lastname": insight.prospect_name.split()[-1] if insight.prospect_name else "",
            "company": insight.company_name,
            "notes": insight.summary
        }
    }
    
    response = httpx.post(
        "https://api.hubapi.com/crm/v3/objects/contacts",
        json=contact_data,
        headers=headers
    )
    response.raise_for_status()


def sync_to_pipedrive(integration, call, insight):
    """Sync to Pipedrive"""
    credentials = integration.credentials
    api_token = credentials.get("api_token")
    
    # Create person
    person_data = {
        "name": insight.prospect_name,
        "org_name": insight.company_name
    }
    
    response = httpx.post(
        f"https://api.pipedrive.com/v1/persons?api_token={api_token}",
        json=person_data
    )
    response.raise_for_status()
