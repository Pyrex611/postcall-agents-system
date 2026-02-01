"""
CRM configuration model for storing integration settings.
"""
import enum
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, JSON, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base, TimestampMixin

class CRMType(str, enum.Enum):
    """CRM system types."""
    SALESFORCE = "salesforce"
    HUBSPOT = "hubspot"
    PIPEDRIVE = "pipedrive"
    ZOHO = "zoho"
    DYNAMICS365 = "dynamics365"
    GOOGLE_SHEETS = "google_sheets"
    CUSTOM = "custom"

class CRMConfig(Base, TimestampMixin):
    """
    CRM configuration model for tenant-specific CRM integrations.
    """
    __tablename__ = "crm_configs"
    
    # Primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Tenant reference
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    
    # CRM type and identification
    crm_type = Column(Enum(CRMType), nullable=False, index=True)
    name = Column(String(255), nullable=False)  # User-friendly name
    is_primary = Column(Boolean, default=False, index=True)  # Primary CRM for tenant
    is_active = Column(Boolean, default=True, index=True)
    
    # Authentication and connection
    auth_type = Column(String(50), default="oauth2")  # oauth2, api_key, basic
    config_data = Column(JSON, nullable=False)  # Encrypted credentials and settings
    
    # Field mappings
    field_mappings = Column(JSON, nullable=True)  # Field mappings between systems
    custom_fields = Column(JSON, nullable=True)  # Custom field definitions
    sync_rules = Column(JSON, nullable=True)  # Sync rules and filters
    
    # Sync settings
    auto_sync = Column(Boolean, default=True)  # Auto-sync after call processing
    sync_direction = Column(String(20), default="both")  # to_crm, from_crm, both
    sync_frequency = Column(String(20), default="realtime")  # realtime, daily, weekly
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    last_sync_status = Column(String(50), nullable=True)
    last_sync_result = Column(JSON, nullable=True)
    
    # Test and validation
    last_tested_at = Column(DateTime(timezone=True), nullable=True)
    last_test_result = Column(JSON, nullable=True)
    connection_status = Column(String(50), default="disconnected")  # connected, disconnected, error
    connection_error = Column(Text, nullable=True)
    
    # Rate limiting and quotas
    rate_limit_remaining = Column(Integer, nullable=True)
    rate_limit_reset = Column(DateTime(timezone=True), nullable=True)
    quota_used = Column(Integer, default=0)
    quota_limit = Column(Integer, nullable=True)
    
    # Advanced settings
    webhook_url = Column(String(500), nullable=True)
    webhook_secret = Column(String(255), nullable=True)
    custom_headers = Column(JSON, nullable=True)
    timeout_seconds = Column(Integer, default=30)
    retry_attempts = Column(Integer, default=3)
    
    # Audit
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    updated_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="crm_configs")
    created_by_user = relationship("User", foreign_keys=[created_by], back_populates="crm_configs")
    updated_by_user = relationship("User", foreign_keys=[updated_by])
    
    # Indexes
    __table_args__ = (
        Index('ix_crm_configs_tenant_type_active', 'tenant_id', 'crm_type', 'is_active'),
        Index('ix_crm_configs_primary', 'tenant_id', 'is_primary'),
        Index('ix_crm_configs_connection_status', 'tenant_id', 'connection_status'),
    )
    
    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """Convert CRM config to dictionary."""
        data = {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "crm_type": self.crm_type.value if self.crm_type else None,
            "name": self.name,
            "is_primary": self.is_primary,
            "is_active": self.is_active,
            "auth_type": self.auth_type,
            "field_mappings": self.field_mappings,
            "custom_fields": self.custom_fields,
            "sync_rules": self.sync_rules,
            "auto_sync": self.auto_sync,
            "sync_direction": self.sync_direction,
            "sync_frequency": self.sync_frequency,
            "last_sync_at": self.last_sync_at.isoformat() if self.last_sync_at else None,
            "last_sync_status": self.last_sync_status,
            "last_sync_result": self.last_sync_result,
            "last_tested_at": self.last_tested_at.isoformat() if self.last_tested_at else None,
            "last_test_result": self.last_test_result,
            "connection_status": self.connection_status,
            "connection_error": self.connection_error,
            "rate_limit_remaining": self.rate_limit_remaining,
            "rate_limit_reset": self.rate_limit_reset.isoformat() if self.rate_limit_reset else None,
            "quota_used": self.quota_used,
            "quota_limit": self.quota_limit,
            "webhook_url": self.webhook_url,
            "custom_headers": self.custom_headers,
            "timeout_seconds": self.timeout_seconds,
            "retry_attempts": self.retry_attempts,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": self.created_by,
            "updated_by": self.updated_by
        }
        
        if include_sensitive:
            data["config_data"] = self.config_data
            data["webhook_secret"] = self.webhook_secret
        else:
            # Mask sensitive data
            data["config_data"] = self._mask_sensitive_data(self.config_data)
            data["webhook_secret"] = "***" + self.webhook_secret[-4:] if self.webhook_secret else None
        
        return data
    
    def _mask_sensitive_data(self, config_data: Dict) -> Dict:
        """Mask sensitive fields in config data."""
        if not isinstance(config_data, dict):
            return config_data
        
        masked = config_data.copy()
        sensitive_keys = [
            "api_key", "access_token", "refresh_token", 
            "client_secret", "password", "private_key"
        ]
        
        for key in sensitive_keys:
            if key in masked and masked[key]:
                if isinstance(masked[key], str):
                    masked[key] = "***" + masked[key][-4:] if len(masked[key]) > 4 else "***"
        
        return masked
    
    def get_credential(self, key: str, default: Any = None) -> Any:
        """Get a credential from config data."""
        if not self.config_data or not isinstance(self.config_data, dict):
            return default
        
        return self.config_data.get(key, default)
    
    def update_credential(self, key: str, value: Any) -> None:
        """Update a credential in config data."""
        if not self.config_data or not isinstance(self.config_data, dict):
            self.config_data = {}
        
        self.config_data[key] = value
    
    def test_connection(self, success: bool, result: Dict = None, error: str = None) -> None:
        """Update connection test results."""
        self.last_tested_at = datetime.utcnow()
        self.last_test_result = result
        
        if success:
            self.connection_status = "connected"
            self.connection_error = None
        else:
            self.connection_status = "error"
            self.connection_error = error
    
    def update_sync_status(self, status: str, result: Dict = None) -> None:
        """Update sync status."""
        self.last_sync_at = datetime.utcnow()
        self.last_sync_status = status
        self.last_sync_result = result
        
        if status == "success":
            self.connection_status = "connected"
        elif status == "failed":
            self.connection_status = "error"
    
    def update_rate_limits(self, remaining: int = None, reset: datetime = None) -> None:
        """Update rate limit information."""
        if remaining is not None:
            self.rate_limit_remaining = remaining
        
        if reset is not None:
            self.rate_limit_reset = reset
    
    def is_connected(self) -> bool:
        """Check if CRM is connected."""
        return self.connection_status == "connected" and self.is_active
    
    def can_sync(self) -> bool:
        """Check if CRM can sync."""
        if not self.is_connected():
            return False
        
        # Check rate limits
        if (self.rate_limit_remaining is not None and 
            self.rate_limit_remaining <= 0):
            if self.rate_limit_reset and datetime.utcnow() < self.rate_limit_reset:
                return False
        
        # Check quotas
        if (self.quota_limit is not None and 
            self.quota_used >= self.quota_limit):
            return False
        
        return True
    
    def increment_quota(self) -> None:
        """Increment quota usage."""
        self.quota_used += 1
    
    def get_field_mapping(self, our_field: str) -> Optional[str]:
        """Get CRM field mapping for our field."""
        if not self.field_mappings or not isinstance(self.field_mappings, dict):
            return None
        
        return self.field_mappings.get(our_field)
    
    def set_field_mapping(self, our_field: str, crm_field: str) -> None:
        """Set field mapping."""
        if not self.field_mappings or not isinstance(self.field_mappings, dict):
            self.field_mappings = {}
        
        self.field_mappings[our_field] = crm_field
    
    def get_required_fields(self) -> List[str]:
        """Get list of required fields for this CRM."""
        # CRM-specific required fields
        required_fields_map = {
            CRMType.SALESFORCE: ["FirstName", "LastName", "Company"],
            CRMType.HUBSPOT: ["firstname", "lastname", "company"],
            CRMType.PIPEDRIVE: ["name", "org_id"],
            CRMType.ZOHO: ["First_Name", "Last_Name", "Company"],
            CRMType.DYNAMICS365: ["firstname", "lastname", "companyname"],
            CRMType.GOOGLE_SHEETS: []  # No required fields
        }
        
        return required_fields_map.get(self.crm_type, [])
    
    def should_auto_sync(self) -> bool:
        """Check if auto-sync is enabled."""
        return self.auto_sync and self.is_connected() and self.can_sync()
    
    @property
    def api_endpoint(self) -> Optional[str]:
        """Get API endpoint for this CRM."""
        if not self.config_data:
            return None
        
        endpoints = {
            CRMType.SALESFORCE: "https://{instance}.salesforce.com",
            CRMType.HUBSPOT: "https://api.hubapi.com",
            CRMType.PIPEDRIVE: "https://api.pipedrive.com/v1",
            CRMType.ZOHO: "https://www.zohoapis.com/crm/v2",
            CRMType.DYNAMICS365: "https://{instance}.crm.dynamics.com/api/data/v9.1",
            CRMType.GOOGLE_SHEETS: "https://sheets.googleapis.com/v4"
        }
        
        base_url = endpoints.get(self.crm_type)
        if not base_url:
            return None
        
        # Replace placeholders with actual values
        if "{instance}" in base_url:
            instance = self.get_credential("instance_url") or self.get_credential("instance")
            if instance:
                base_url = base_url.replace("{instance}", instance)
        
        return base_url