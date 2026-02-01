"""
Abstract Base Class for CRM integrations
Allows pluggable CRM connectors (Salesforce, HubSpot, Pipedrive)
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel
from enum import Enum


class CRMEntityType(str, Enum):
    """Standard CRM entity types"""
    CONTACT = "contact"
    LEAD = "lead"
    ACCOUNT = "account"
    OPPORTUNITY = "opportunity"
    ACTIVITY = "activity"
    TASK = "task"


class CRMSyncAction(str, Enum):
    """Types of sync operations"""
    CREATE = "create"
    UPDATE = "update"
    UPSERT = "upsert"  # Update if exists, create otherwise
    READ = "read"
    SEARCH = "search"


class CRMContact(BaseModel):
    """Standardized contact model"""
    first_name: Optional[str]
    last_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    title: Optional[str]
    company: Optional[str]
    # CRM-specific ID
    crm_id: Optional[str]
    # Custom fields
    custom_fields: Dict[str, Any] = {}


class CRMActivity(BaseModel):
    """Standardized activity/task model"""
    subject: str
    description: Optional[str]
    activity_type: str  # 'call', 'email', 'meeting'
    activity_date: datetime
    duration_minutes: Optional[int]
    status: Optional[str]
    related_to_id: Optional[str]  # Contact/Lead/Opportunity ID
    custom_fields: Dict[str, Any] = {}


class CRMOpportunity(BaseModel):
    """Standardized opportunity/deal model"""
    name: str
    amount: Optional[float]
    stage: str
    probability: Optional[int]  # 0-100
    close_date: Optional[datetime]
    account_id: Optional[str]
    contact_id: Optional[str]
    description: Optional[str]
    custom_fields: Dict[str, Any] = {}


class CRMSyncResult(BaseModel):
    """Result of a CRM sync operation"""
    success: bool
    action: CRMSyncAction
    entity_type: CRMEntityType
    entity_id: Optional[str]  # CRM's ID for the entity
    error_message: Optional[str]
    warnings: List[str] = []
    metadata: Dict[str, Any] = {}


class BaseCRMConnector(ABC):
    """
    Abstract base class for all CRM connectors.
    Each CRM (Salesforce, HubSpot, etc.) implements this interface.
    """
    
    def __init__(
        self,
        access_token: str,
        refresh_token: Optional[str] = None,
        instance_url: Optional[str] = None,
        field_mappings: Optional[Dict[str, str]] = None
    ):
        """
        Initialize CRM connector
        
        Args:
            access_token: OAuth access token
            refresh_token: OAuth refresh token (for token renewal)
            instance_url: CRM instance URL (e.g., Salesforce domain)
            field_mappings: Map standard fields to CRM-specific fields
        """
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.instance_url = instance_url
        self.field_mappings = field_mappings or {}
        self._client = None
    
    @abstractmethod
    async def authenticate(self) -> bool:
        """
        Authenticate with the CRM.
        Returns True if successful.
        """
        pass
    
    @abstractmethod
    async def refresh_access_token(self) -> str:
        """
        Refresh the access token using refresh token.
        Returns new access token.
        """
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """
        Test if the connection to CRM is working.
        Returns True if successful.
        """
        pass
    
    # ========================================================================
    # CONTACT OPERATIONS
    # ========================================================================
    
    @abstractmethod
    async def create_contact(self, contact: CRMContact) -> CRMSyncResult:
        """Create a new contact in the CRM"""
        pass
    
    @abstractmethod
    async def update_contact(self, contact_id: str, contact: CRMContact) -> CRMSyncResult:
        """Update an existing contact"""
        pass
    
    @abstractmethod
    async def get_contact(self, contact_id: str) -> Optional[CRMContact]:
        """Retrieve a contact by ID"""
        pass
    
    @abstractmethod
    async def search_contact(self, email: str) -> Optional[CRMContact]:
        """Search for a contact by email"""
        pass
    
    async def upsert_contact(self, contact: CRMContact) -> CRMSyncResult:
        """
        Create contact if doesn't exist, update if exists.
        Default implementation - can be overridden for CRM-specific optimization.
        """
        if contact.email:
            existing = await self.search_contact(contact.email)
            if existing and existing.crm_id:
                return await self.update_contact(existing.crm_id, contact)
        
        return await self.create_contact(contact)
    
    # ========================================================================
    # ACTIVITY OPERATIONS
    # ========================================================================
    
    @abstractmethod
    async def create_activity(self, activity: CRMActivity) -> CRMSyncResult:
        """Log an activity (call, meeting, email) in the CRM"""
        pass
    
    @abstractmethod
    async def get_recent_activities(
        self,
        contact_id: str,
        limit: int = 10
    ) -> List[CRMActivity]:
        """Get recent activities for a contact"""
        pass
    
    # ========================================================================
    # OPPORTUNITY OPERATIONS
    # ========================================================================
    
    @abstractmethod
    async def create_opportunity(self, opportunity: CRMOpportunity) -> CRMSyncResult:
        """Create a new opportunity/deal"""
        pass
    
    @abstractmethod
    async def update_opportunity(
        self,
        opportunity_id: str,
        opportunity: CRMOpportunity
    ) -> CRMSyncResult:
        """Update an existing opportunity"""
        pass
    
    @abstractmethod
    async def get_opportunities_for_contact(
        self,
        contact_id: str
    ) -> List[CRMOpportunity]:
        """Get all opportunities associated with a contact"""
        pass
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def map_field(self, standard_field: str) -> str:
        """
        Map a standard field name to CRM-specific field name.
        
        Example:
            standard: "first_name" -> Salesforce: "FirstName"
        """
        return self.field_mappings.get(standard_field, standard_field)
    
    def apply_field_mappings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply field mappings to a data dictionary"""
        if not self.field_mappings:
            return data
        
        mapped_data = {}
        for key, value in data.items():
            mapped_key = self.map_field(key)
            mapped_data[mapped_key] = value
        
        return mapped_data
    
    @abstractmethod
    async def get_field_schema(self, entity_type: CRMEntityType) -> Dict[str, Any]:
        """
        Get the field schema for an entity type.
        Useful for dynamic field mapping UI.
        
        Returns: Dict of field_name -> field_metadata
        """
        pass
    
    async def validate_required_fields(
        self,
        entity_type: CRMEntityType,
        data: Dict[str, Any]
    ) -> List[str]:
        """
        Validate that all required fields are present.
        Returns list of missing required fields.
        """
        schema = await self.get_field_schema(entity_type)
        missing_fields = []
        
        for field_name, field_meta in schema.items():
            if field_meta.get('required') and field_name not in data:
                missing_fields.append(field_name)
        
        return missing_fields
    
    def __str__(self):
        return f"{self.__class__.__name__}(instance_url={self.instance_url})"


class CRMConnectorFactory:
    """
    Factory to create appropriate CRM connector based on CRM type.
    This allows the system to dynamically instantiate the correct connector.
    """
    
    _connectors: Dict[str, type] = {}
    
    @classmethod
    def register(cls, crm_type: str, connector_class: type):
        """Register a CRM connector class"""
        cls._connectors[crm_type.lower()] = connector_class
    
    @classmethod
    def create(
        cls,
        crm_type: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        instance_url: Optional[str] = None,
        field_mappings: Optional[Dict[str, str]] = None
    ) -> BaseCRMConnector:
        """
        Create a CRM connector instance
        
        Args:
            crm_type: 'salesforce', 'hubspot', 'pipedrive'
            access_token: OAuth access token
            refresh_token: OAuth refresh token
            instance_url: CRM instance URL
            field_mappings: Custom field mappings
            
        Returns:
            Instance of the appropriate CRM connector
            
        Raises:
            ValueError: If CRM type is not supported
        """
        connector_class = cls._connectors.get(crm_type.lower())
        
        if not connector_class:
            raise ValueError(
                f"Unsupported CRM type: {crm_type}. "
                f"Supported types: {', '.join(cls._connectors.keys())}"
            )
        
        return connector_class(
            access_token=access_token,
            refresh_token=refresh_token,
            instance_url=instance_url,
            field_mappings=field_mappings
        )
    
    @classmethod
    def get_supported_crms(cls) -> List[str]:
        """Get list of supported CRM types"""
        return list(cls._connectors.keys())