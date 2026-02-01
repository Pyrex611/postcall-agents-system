"""
CRM integration endpoints
"""
import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends, status, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json

from app.core.database import get_db
from app.api.dependencies import get_current_user, get_current_admin
from app.models.crm_config import CRMConfig
from app.schemas.crm import CRMConfigCreate, CRMConfigUpdate, CRMConfigResponse, CRMTestResponse
from app.services.crm_integration import CRMIntegrationService

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/settings", response_model=CRMConfigResponse)
async def get_crm_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get CRM settings for current tenant.
    """
    try:
        # Get CRM config for tenant
        stmt = select(CRMConfig).where(
            CRMConfig.tenant_id == current_user.tenant_id,
            CRMConfig.is_active == True
        )
        result = await db.execute(stmt)
        crm_config = result.scalar_one_or_none()
        
        if not crm_config:
            return CRMConfigResponse(
                is_configured=False,
                crm_type=None,
                last_sync_at=None,
                message="No CRM configured"
            )
        
        # Mask sensitive fields for response
        config_data = crm_config.to_dict()
        if "api_key" in config_data:
            config_data["api_key"] = "***" + config_data["api_key"][-4:] if config_data["api_key"] else None
        if "access_token" in config_data:
            config_data["access_token"] = "***" + config_data["access_token"][-4:] if config_data["access_token"] else None
        
        return CRMConfigResponse(
            is_configured=True,
            crm_type=crm_config.crm_type,
            config=config_data,
            last_sync_at=crm_config.last_sync_at.isoformat() if crm_config.last_sync_at else None,
            created_at=crm_config.created_at.isoformat() if crm_config.created_at else None,
            updated_at=crm_config.updated_at.isoformat() if crm_config.updated_at else None
        )
        
    except Exception as e:
        logger.error(f"Failed to get CRM settings: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get CRM settings: {str(e)}"
        )

@router.post("/settings", response_model=CRMConfigResponse)
async def update_crm_settings(
    crm_data: CRMConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Update CRM settings for current tenant.
    """
    try:
        # Validate CRM type
        supported_crms = ["salesforce", "hubspot", "pipedrive", "zoho", "dynamics365", "google_sheets"]
        if crm_data.crm_type not in supported_crms:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported CRM type. Supported: {', '.join(supported_crms)}"
            )
        
        # Check if config already exists
        stmt = select(CRMConfig).where(
            CRMConfig.tenant_id == current_user.tenant_id,
            CRMConfig.is_active == True
        )
        result = await db.execute(stmt)
        existing_config = result.scalar_one_or_none()
        
        if existing_config:
            # Update existing config
            existing_config.crm_type = crm_data.crm_type
            existing_config.config_data = crm_data.config_data
            existing_config.field_mappings = crm_data.field_mappings
            existing_config.is_active = True
            existing_config.updated_at = datetime.datetime.utcnow()
            
            config = existing_config
        else:
            # Create new config
            config = CRMConfig(
                tenant_id=current_user.tenant_id,
                crm_type=crm_data.crm_type,
                config_data=crm_data.config_data,
                field_mappings=crm_data.field_mappings,
                is_active=True,
                created_by=current_user.id
            )
            db.add(config)
        
        await db.commit()
        await db.refresh(config)
        
        # Test the connection
        crm_service = CRMIntegrationService()
        test_result = await crm_service.test_connection_async(
            tenant_id=current_user.tenant_id
        )
        
        # Update last test result
        config.last_test_result = test_result
        config.last_tested_at = datetime.datetime.utcnow()
        await db.commit()
        
        logger.info(f"CRM settings updated for tenant {current_user.tenant_id}: {crm_data.crm_type}")
        
        # Prepare response
        response_config = config.to_dict()
        if "api_key" in response_config:
            response_config["api_key"] = "***" + response_config["api_key"][-4:] if response_config["api_key"] else None
        
        return CRMConfigResponse(
            is_configured=True,
            crm_type=config.crm_type,
            config=response_config,
            test_result=test_result,
            last_sync_at=config.last_sync_at.isoformat() if config.last_sync_at else None,
            created_at=config.created_at.isoformat() if config.created_at else None,
            updated_at=config.updated_at.isoformat() if config.updated_at else None
        )
        
    except Exception as e:
        logger.error(f"Failed to update CRM settings: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update CRM settings: {str(e)}"
        )

@router.post("/test", response_model=CRMTestResponse)
async def test_crm_connection(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Test CRM connection for current tenant.
    """
    try:
        crm_service = CRMIntegrationService()
        test_result = await crm_service.test_connection_async(
            tenant_id=current_user.tenant_id
        )
        
        # Update last test result in database
        stmt = select(CRMConfig).where(
            CRMConfig.tenant_id == current_user.tenant_id,
            CRMConfig.is_active == True
        )
        result = await db.execute(stmt)
        crm_config = result.scalar_one_or_none()
        
        if crm_config:
            crm_config.last_test_result = test_result
            crm_config.last_tested_at = datetime.datetime.utcnow()
            await db.commit()
        
        logger.info(f"CRM connection test for tenant {current_user.tenant_id}: {test_result.get('status')}")
        
        return test_result
        
    except Exception as e:
        logger.error(f"CRM connection test failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"CRM connection test failed: {str(e)}"
        )

@router.delete("/settings")
async def delete_crm_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """
    Delete CRM configuration for current tenant.
    """
    try:
        # Find active CRM config
        stmt = select(CRMConfig).where(
            CRMConfig.tenant_id == current_user.tenant_id,
            CRMConfig.is_active == True
        )
        result = await db.execute(stmt)
        crm_config = result.scalar_one_or_none()
        
        if not crm_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No CRM configuration found"
            )
        
        # Soft delete (deactivate)
        crm_config.is_active = False
        crm_config.deactivated_at = datetime.datetime.utcnow()
        crm_config.deactivated_by = current_user.id
        
        await db.commit()
        
        logger.info(f"CRM settings deleted for tenant {current_user.tenant_id}")
        
        return {"message": "CRM configuration deleted successfully"}
        
    except Exception as e:
        logger.error(f"Failed to delete CRM settings: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete CRM settings: {str(e)}"
        )

@router.get("/sync-history")
async def get_crm_sync_history(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get CRM sync history for current tenant.
    """
    try:
        # In a real implementation, you would have a separate SyncHistory table
        # For now, we'll use the call records with CRM updates
        from app.models.call import Call
        from sqlalchemy import desc
        
        stmt = select(Call).where(
            Call.tenant_id == current_user.tenant_id,
            Call.crm_update_result.isnot(None),
            Call.status == "completed"
        ).order_by(desc(Call.processing_completed_at)).limit(limit)
        
        result = await db.execute(stmt)
        calls = result.scalars().all()
        
        sync_history = []
        for call in calls:
            if call.crm_update_result:
                sync_history.append({
                    "call_id": call.id,
                    "prospect_name": call.prospect_name,
                    "company_name": call.company_name,
                    "sync_time": call.processing_completed_at.isoformat() if call.processing_completed_at else None,
                    "sync_result": call.crm_update_result,
                    "status": call.crm_update_result.get("status", "unknown")
                })
        
        return {
            "total_count": len(sync_history),
            "sync_history": sync_history
        }
        
    except Exception as e:
        logger.error(f"Failed to get CRM sync history: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get CRM sync history: {str(e)}"
        )

@router.post("/manual-sync/{call_id}")
async def manual_crm_sync(
    call_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Manually trigger CRM sync for a specific call.
    """
    try:
        # Get the call
        from app.models.call import Call
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
        
        if not call.insights:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Call analysis not available for sync"
            )
        
        # Trigger CRM sync
        crm_service = CRMIntegrationService()
        sync_result = await crm_service.update_record_async(
            data=call.insights,
            tenant_id=current_user.tenant_id,
            user_id=current_user.id
        )
        
        # Update call with sync result
        call.crm_update_result = sync_result
        await db.commit()
        
        logger.info(f"Manual CRM sync for call {call_id}: {sync_result.get('status')}")
        
        return sync_result
        
    except Exception as e:
        logger.error(f"Manual CRM sync failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Manual CRM sync failed: {str(e)}"
        )

@router.get("/available-crms")
async def get_available_crms():
    """
    Get list of available CRM integrations.
    """
    return {
        "available_crms": [
            {
                "id": "salesforce",
                "name": "Salesforce",
                "description": "Salesforce CRM integration",
                "icon_url": "https://cdn.worldvectorlogo.com/logos/salesforce-1.svg",
                "features": ["Contacts", "Leads", "Opportunities", "Custom Objects"],
                "auth_type": "oauth2",
                "docs_url": "https://developer.salesforce.com/docs"
            },
            {
                "id": "hubspot",
                "name": "HubSpot",
                "description": "HubSpot CRM integration",
                "icon_url": "https://cdn.worldvectorlogo.com/logos/hubspot-1.svg",
                "features": ["Contacts", "Companies", "Deals", "Tasks"],
                "auth_type": "oauth2",
                "docs_url": "https://developers.hubspot.com/docs"
            },
            {
                "id": "pipedrive",
                "name": "Pipedrive",
                "description": "Pipedrive sales CRM",
                "icon_url": "https://cdn.worldvectorlogo.com/logos/pipedrive.svg",
                "features": ["Deals", "Persons", "Activities", "Products"],
                "auth_type": "api_key",
                "docs_url": "https://developers.pipedrive.com/docs"
            },
            {
                "id": "zoho",
                "name": "Zoho CRM",
                "description": "Zoho CRM integration",
                "icon_url": "https://cdn.worldvectorlogo.com/logos/zoho-crm.svg",
                "features": ["Leads", "Contacts", "Accounts", "Deals"],
                "auth_type": "oauth2",
                "docs_url": "https://www.zoho.com/crm/developer/docs"
            },
            {
                "id": "dynamics365",
                "name": "Microsoft Dynamics 365",
                "description": "Dynamics 365 CRM integration",
                "icon_url": "https://cdn.worldvectorlogo.com/logos/microsoft-dynamics-365.svg",
                "features": ["Accounts", "Contacts", "Leads", "Opportunities"],
                "auth_type": "oauth2",
                "docs_url": "https://docs.microsoft.com/en-us/dynamics365/"
            },
            {
                "id": "google_sheets",
                "name": "Google Sheets",
                "description": "Google Sheets as simple CRM",
                "icon_url": "https://cdn.worldvectorlogo.com/logos/google-sheets.svg",
                "features": ["Custom Sheets", "Flexible Structure", "Easy Setup"],
                "auth_type": "oauth2",
                "docs_url": "https://developers.google.com/sheets/api"
            }
        ]
    }