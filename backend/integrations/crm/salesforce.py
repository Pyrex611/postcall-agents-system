"""
Salesforce CRM Connector Implementation
Uses simple-salesforce library for API interactions
"""

import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime
from simple_salesforce import Salesforce as SFClient
from simple_salesforce.exceptions import SalesforceAuthenticationFailed, SalesforceError

from .base import (
    BaseCRMConnector,
    CRMContact,
    CRMActivity,
    CRMOpportunity,
    CRMSyncResult,
    CRM EntityType,
    CRMSyncAction,
    CRMConnectorFactory
)


class SalesforceConnector(BaseCRMConnector):
    """Salesforce-specific CRM connector"""
    
    # Default field mappings (standard -> Salesforce)
    DEFAULT_FIELD_MAPPINGS = {
        'first_name': 'FirstName',
        'last_name': 'LastName',
        'email': 'Email',
        'phone': 'Phone',
        'title': 'Title',
        'company': 'Account.Name'
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Merge default mappings with custom ones
        self.field_mappings = {**self.DEFAULT_FIELD_MAPPINGS, **self.field_mappings}
    
    async def authenticate(self) -> bool:
        """Authenticate with Salesforce"""
        try:
            loop = asyncio.get_event_loop()
            self._client = await loop.run_in_executor(
                None,
                lambda: SFClient(
                    instance_url=self.instance_url,
                    session_id=self.access_token,
                    version='58.0'
                )
            )
            return True
        except SalesforceAuthenticationFailed:
            return False
    
    async def refresh_access_token(self) -> str:
        """
        Refresh Salesforce access token.
        Note: Salesforce OAuth refresh should be handled by OAuth flow.
        """
        # This would typically call Salesforce OAuth token endpoint
        # For now, raise NotImplementedError as it requires OAuth client setup
        raise NotImplementedError(
            "Token refresh should be handled by OAuth provider. "
            "Use Salesforce Connected App refresh token flow."
        )
    
    async def test_connection(self) -> bool:
        """Test Salesforce connection"""
        try:
            if not self._client:
                await self.authenticate()
            
            # Simple query to test connection
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._client.query("SELECT Id FROM User LIMIT 1")
            )
            return result['totalSize'] > 0
        except Exception:
            return False
    
    async def create_contact(self, contact: CRMContact) -> CRMSyncResult:
        """Create contact in Salesforce"""
        try:
            if not self._client:
                await self.authenticate()
            
            # Build Salesforce Contact object
            sf_data = {
                'FirstName': contact.first_name or '',
                'LastName': contact.last_name or 'Unknown',  # Required in SF
                'Email': contact.email,
                'Phone': contact.phone,
                'Title': contact.title
            }
            
            # Add custom fields
            if contact.custom_fields:
                sf_data.update(contact.custom_fields)
            
            # Remove None values
            sf_data = {k: v for k, v in sf_data.items() if v is not None}
            
            # Create contact
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._client.Contact.create(sf_data)
            )
            
            return CRMSyncResult(
                success=result['success'],
                action=CRMSyncAction.CREATE,
                entity_type=CRMEntityType.CONTACT,
                entity_id=result.get('id'),
                metadata={'salesforce_response': result}
            )
            
        except SalesforceError as e:
            return CRMSyncResult(
                success=False,
                action=CRMSyncAction.CREATE,
                entity_type=CRMEntityType.CONTACT,
                error_message=str(e)
            )
    
    async def update_contact(self, contact_id: str, contact: CRMContact) -> CRMSyncResult:
        """Update Salesforce contact"""
        try:
            if not self._client:
                await self.authenticate()
            
            # Build update data
            sf_data = {}
            if contact.first_name:
                sf_data['FirstName'] = contact.first_name
            if contact.last_name:
                sf_data['LastName'] = contact.last_name
            if contact.email:
                sf_data['Email'] = contact.email
            if contact.phone:
                sf_data['Phone'] = contact.phone
            if contact.title:
                sf_data['Title'] = contact.title
            
            if contact.custom_fields:
                sf_data.update(contact.custom_fields)
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._client.Contact.update(contact_id, sf_data)
            )
            
            return CRMSyncResult(
                success=True,
                action=CRMSyncAction.UPDATE,
                entity_type=CRMEntityType.CONTACT,
                entity_id=contact_id
            )
            
        except SalesforceError as e:
            return CRMSyncResult(
                success=False,
                action=CRMSyncAction.UPDATE,
                entity_type=CRMEntityType.CONTACT,
                error_message=str(e)
            )
    
    async def get_contact(self, contact_id: str) -> Optional[CRMContact]:
        """Get Salesforce contact by ID"""
        try:
            if not self._client:
                await self.authenticate()
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._client.Contact.get(contact_id)
            )
            
            return CRMContact(
                crm_id=result['Id'],
                first_name=result.get('FirstName'),
                last_name=result.get('LastName'),
                email=result.get('Email'),
                phone=result.get('Phone'),
                title=result.get('Title'),
                company=result.get('Account', {}).get('Name') if result.get('Account') else None
            )
            
        except SalesforceError:
            return None
    
    async def search_contact(self, email: str) -> Optional[CRMContact]:
        """Search Salesforce contact by email"""
        try:
            if not self._client:
                await self.authenticate()
            
            query = f"SELECT Id, FirstName, LastName, Email, Phone, Title FROM Contact WHERE Email = '{email}' LIMIT 1"
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._client.query(query)
            )
            
            if result['totalSize'] == 0:
                return None
            
            record = result['records'][0]
            return CRMContact(
                crm_id=record['Id'],
                first_name=record.get('FirstName'),
                last_name=record.get('LastName'),
                email=record.get('Email'),
                phone=record.get('Phone'),
                title=record.get('Title')
            )
            
        except SalesforceError:
            return None
    
    async def create_activity(self, activity: CRMActivity) -> CRMSyncResult:
        """Create a Task in Salesforce (logged call/activity)"""
        try:
            if not self._client:
                await self.authenticate()
            
            # Salesforce uses Task object for activities
            task_data = {
                'Subject': activity.subject,
                'Description': activity.description,
                'ActivityDate': activity.activity_date.strftime('%Y-%m-%d'),
                'Status': activity.status or 'Completed',
                'TaskSubtype': 'Call',  # 'Call', 'Email', etc.
                'WhoId': activity.related_to_id  # Contact or Lead ID
            }
            
            if activity.custom_fields:
                task_data.update(activity.custom_fields)
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._client.Task.create(task_data)
            )
            
            return CRMSyncResult(
                success=result['success'],
                action=CRMSyncAction.CREATE,
                entity_type=CRMEntityType.ACTIVITY,
                entity_id=result.get('id')
            )
            
        except SalesforceError as e:
            return CRMSyncResult(
                success=False,
                action=CRMSyncAction.CREATE,
                entity_type=CRMEntityType.ACTIVITY,
                error_message=str(e)
            )
    
    async def get_recent_activities(self, contact_id: str, limit: int = 10) -> List[CRMActivity]:
        """Get recent activities for a contact"""
        try:
            if not self._client:
                await self.authenticate()
            
            query = f"""
                SELECT Id, Subject, Description, ActivityDate, Status, TaskSubtype
                FROM Task
                WHERE WhoId = '{contact_id}'
                ORDER BY ActivityDate DESC
                LIMIT {limit}
            """
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._client.query(query)
            )
            
            activities = []
            for record in result.get('records', []):
                activities.append(CRMActivity(
                    subject=record['Subject'],
                    description=record.get('Description'),
                    activity_type=record.get('TaskSubtype', 'Call'),
                    activity_date=datetime.strptime(record['ActivityDate'], '%Y-%m-%d'),
                    status=record.get('Status')
                ))
            
            return activities
            
        except SalesforceError:
            return []
    
    async def create_opportunity(self, opportunity: CRMOpportunity) -> CRMSyncResult:
        """Create Salesforce Opportunity"""
        try:
            if not self._client:
                await self.authenticate()
            
            opp_data = {
                'Name': opportunity.name,
                'StageName': opportunity.stage,
                'CloseDate': opportunity.close_date.strftime('%Y-%m-%d') if opportunity.close_date else None,
                'Amount': opportunity.amount,
                'Probability': opportunity.probability,
                'Description': opportunity.description
            }
            
            if opportunity.account_id:
                opp_data['AccountId'] = opportunity.account_id
            
            if opportunity.custom_fields:
                opp_data.update(opportunity.custom_fields)
            
            # Remove None values
            opp_data = {k: v for k, v in opp_data.items() if v is not None}
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._client.Opportunity.create(opp_data)
            )
            
            return CRMSyncResult(
                success=result['success'],
                action=CRMSyncAction.CREATE,
                entity_type=CRMEntityType.OPPORTUNITY,
                entity_id=result.get('id')
            )
            
        except SalesforceError as e:
            return CRMSyncResult(
                success=False,
                action=CRMSyncAction.CREATE,
                entity_type=CRMEntityType.OPPORTUNITY,
                error_message=str(e)
            )
    
    async def update_opportunity(self, opportunity_id: str, opportunity: CRMOpportunity) -> CRMSyncResult:
        """Update Salesforce Opportunity"""
        try:
            if not self._client:
                await self.authenticate()
            
            opp_data = {}
            if opportunity.name:
                opp_data['Name'] = opportunity.name
            if opportunity.stage:
                opp_data['StageName'] = opportunity.stage
            if opportunity.amount is not None:
                opp_data['Amount'] = opportunity.amount
            if opportunity.close_date:
                opp_data['CloseDate'] = opportunity.close_date.strftime('%Y-%m-%d')
            if opportunity.probability is not None:
                opp_data['Probability'] = opportunity.probability
            
            if opportunity.custom_fields:
                opp_data.update(opportunity.custom_fields)
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._client.Opportunity.update(opportunity_id, opp_data)
            )
            
            return CRMSyncResult(
                success=True,
                action=CRMSyncAction.UPDATE,
                entity_type=CRMEntityType.OPPORTUNITY,
                entity_id=opportunity_id
            )
            
        except SalesforceError as e:
            return CRMSyncResult(
                success=False,
                action=CRMSyncAction.UPDATE,
                entity_type=CRMEntityType.OPPORTUNITY,
                error_message=str(e)
            )
    
    async def get_opportunities_for_contact(self, contact_id: str) -> List[CRMOpportunity]:
        """Get opportunities for a contact"""
        try:
            if not self._client:
                await self.authenticate()
            
            # Query through OpportunityContactRole junction
            query = f"""
                SELECT Opportunity.Id, Opportunity.Name, Opportunity.StageName, 
                       Opportunity.Amount, Opportunity.CloseDate, Opportunity.Probability
                FROM OpportunityContactRole
                WHERE ContactId = '{contact_id}'
            """
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._client.query(query)
            )
            
            opportunities = []
            for record in result.get('records', []):
                opp = record.get('Opportunity', {})
                opportunities.append(CRMOpportunity(
                    name=opp.get('Name', ''),
                    stage=opp.get('StageName', ''),
                    amount=opp.get('Amount'),
                    probability=opp.get('Probability'),
                    close_date=datetime.strptime(opp['CloseDate'], '%Y-%m-%d') if opp.get('CloseDate') else None
                ))
            
            return opportunities
            
        except SalesforceError:
            return []
    
    async def get_field_schema(self, entity_type: CRMEntityType) -> Dict[str, Any]:
        """Get Salesforce field schema for an object"""
        try:
            if not self._client:
                await self.authenticate()
            
            # Map entity type to Salesforce object name
            object_map = {
                CRMEntityType.CONTACT: 'Contact',
                CRMEntityType.LEAD: 'Lead',
                CRMEntityType.OPPORTUNITY: 'Opportunity',
                CRMEntityType.ACTIVITY: 'Task'
            }
            
            sf_object_name = object_map.get(entity_type)
            if not sf_object_name:
                return {}
            
            loop = asyncio.get_event_loop()
            describe = await loop.run_in_executor(
                None,
                lambda: getattr(self._client, sf_object_name).describe()
            )
            
            schema = {}
            for field in describe['fields']:
                schema[field['name']] = {
                    'label': field['label'],
                    'type': field['type'],
                    'required': not field['nillable'],
                    'updateable': field['updateable'],
                    'createable': field['createable']
                }
            
            return schema
            
        except SalesforceError:
            return {}


# Register Salesforce connector with factory
CRMConnectorFactory.register('salesforce', SalesforceConnector)