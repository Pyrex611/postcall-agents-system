"""
Tenant model for multi-tenant architecture.
"""
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Integer, JSON, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base, TimestampMixin, AuditMixin

class TenantPlan(str, enum.Enum):
    """Tenant subscription plans."""
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"
    CUSTOM = "custom"

class Tenant(Base, TimestampMixin, AuditMixin):
    """
    Tenant model for multi-tenancy.
    """
    __tablename__ = "tenants"
    
    # Identification
    name = Column(String(255), nullable=False, index=True)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # Contact information
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    website = Column(String(500), nullable=True)
    
    # Subscription
    plan = Column(Enum(TenantPlan), default=TenantPlan.FREE, index=True)
    subscription_id = Column(String(255), nullable=True, index=True)
    subscription_status = Column(String(50), default="active")
    subscription_start = Column(DateTime(timezone=True), nullable=True)
    subscription_end = Column(DateTime(timezone=True), nullable=True)
    trial_ends_at = Column(DateTime(timezone=True), nullable=True)
    
    # Limits and usage
    max_users = Column(Integer, default=5)
    max_calls_per_month = Column(Integer, default=100)
    max_storage_gb = Column(Integer, default=10)
    current_month_calls = Column(Integer, default=0)
    current_storage_bytes = Column(BigInteger, default=0)
    
    # Features
    features = Column(JSON, default={
        "crm_integrations": True,
        "email_notifications": True,
        "api_access": False,
        "custom_branding": False,
        "advanced_analytics": False,
        "priority_support": False
    })
    
    # Settings
    settings = Column(JSON, default={
        "timezone": "UTC",
        "locale": "en-US",
        "date_format": "MM/DD/YYYY",
        "time_format": "12h",
        "auto_process_calls": True,
        "auto_crm_sync": True,
        "data_retention_days": 365,
        "compliance_mode": "standard"
    })
    
    # Status
    is_active = Column(Boolean, default=True, index=True)
    is_suspended = Column(Boolean, default=False, index=True)
    suspended_reason = Column(Text, nullable=True)
    suspended_at = Column(DateTime(timezone=True), nullable=True)
    
    # Billing
    billing_address = Column(JSON, nullable=True)
    payment_method = Column(JSON, nullable=True)
    invoice_prefix = Column(String(50), default="INV")
    
    # Customization
    logo_url = Column(String(500), nullable=True)
    primary_color = Column(String(7), default="#3B82F6")  # Blue 500
    secondary_color = Column(String(7), default="#1E40AF")  # Blue 800
    custom_css = Column(Text, nullable=True)
    custom_js = Column(Text, nullable=True)
    
    # Relationships
    users = relationship("User", backref="tenant", cascade="all, delete-orphan")
    calls = relationship("Call", backref="tenant", cascade="all, delete-orphan")
    crm_configs = relationship("CRMConfig", backref="tenant", cascade="all, delete-orphan")
    webhooks = relationship("Webhook", backref="tenant", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('ix_tenants_plan_active', 'plan', 'is_active'),
        Index('ix_tenants_subscription_status', 'subscription_status'),
        Index('ix_tenants_created_at', 'created_at'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert tenant to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "plan": self.plan.value if self.plan else None,
            "subscription_status": self.subscription_status,
            "subscription_start": self.subscription_start.isoformat() if self.subscription_start else None,
            "subscription_end": self.subscription_end.isoformat() if self.subscription_end else None,
            "trial_ends_at": self.trial_ends_at.isoformat() if self.trial_ends_at else None,
            "max_users": self.max_users,
            "max_calls_per_month": self.max_calls_per_month,
            "max_storage_gb": self.max_storage_gb,
            "current_month_calls": self.current_month_calls,
            "current_storage_gb": round(self.current_storage_bytes / (1024**3), 2),
            "features": self.features,
            "settings": self.settings,
            "is_active": self.is_active,
            "is_suspended": self.is_suspended,
            "suspended_reason": self.suspended_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "contact_email": self.contact_email,
            "website": self.website,
            "logo_url": self.logo_url,
            "primary_color": self.primary_color,
            "secondary_color": self.secondary_color
        }
    
    def can_add_user(self) -> bool:
        """Check if tenant can add another user."""
        if not self.is_active or self.is_suspended:
            return False
        
        # Get current active user count
        from app.models.user import User
        # This would require a query - simplified for now
        # active_users = User.query.filter_by(tenant_id=self.id, is_active=True).count()
        # return active_users < self.max_users
        
        # For now, assume limit not reached
        return True
    
    def can_process_call(self) -> bool:
        """Check if tenant can process another call this month."""
        if not self.is_active or self.is_suspended:
            return False
        
        # Reset monthly count if new month
        now = datetime.utcnow()
        if self.current_month_reset and now.month != self.current_month_reset.month:
            self.current_month_calls = 0
            self.current_month_reset = now
        
        return self.current_month_calls < self.max_calls_per_month
    
    def increment_call_count(self) -> None:
        """Increment monthly call count."""
        self.current_month_calls += 1
    
    def can_store_data(self, size_bytes: int) -> bool:
        """Check if tenant can store additional data."""
        if not self.is_active or self.is_suspended:
            return False
        
        new_total = self.current_storage_bytes + size_bytes
        max_bytes = self.max_storage_gb * (1024**3)
        
        return new_total <= max_bytes
    
    def add_storage_usage(self, size_bytes: int) -> None:
        """Add to storage usage."""
        self.current_storage_bytes += size_bytes
    
    def remove_storage_usage(self, size_bytes: int) -> None:
        """Remove from storage usage."""
        self.current_storage_bytes = max(0, self.current_storage_bytes - size_bytes)
    
    def is_trial_active(self) -> bool:
        """Check if trial period is active."""
        if not self.trial_ends_at:
            return False
        return datetime.utcnow() < self.trial_ends_at
    
    def days_until_trial_end(self) -> Optional[int]:
        """Get days until trial ends."""
        if not self.trial_ends_at:
            return None
        
        delta = self.trial_ends_at - datetime.utcnow()
        return max(0, delta.days)
    
    def suspend(self, reason: str = None) -> None:
        """Suspend the tenant."""
        self.is_suspended = True
        self.suspended_reason = reason
        self.suspended_at = datetime.utcnow()
    
    def unsuspend(self) -> None:
        """Unsuspend the tenant."""
        self.is_suspended = False
        self.suspended_reason = None
        self.suspended_at = None
    
    def has_feature(self, feature: str) -> bool:
        """Check if tenant has a specific feature enabled."""
        return self.features.get(feature, False)
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a tenant setting."""
        return self.settings.get(key, default)
    
    def update_setting(self, key: str, value: Any) -> None:
        """Update a tenant setting."""
        settings = self.settings or {}
        settings[key] = value
        self.settings = settings
    
    @property
    def storage_usage_percent(self) -> float:
        """Get storage usage percentage."""
        if self.max_storage_gb == 0:
            return 0
        
        max_bytes = self.max_storage_gb * (1024**3)
        return (self.current_storage_bytes / max_bytes) * 100
    
    @property
    def call_usage_percent(self) -> float:
        """Get call usage percentage."""
        if self.max_calls_per_month == 0:
            return 0
        
        return (self.current_month_calls / self.max_calls_per_month) * 100
    
    @property
    def usage_summary(self) -> Dict[str, Any]:
        """Get usage summary."""
        return {
            "calls": {
                "used": self.current_month_calls,
                "limit": self.max_calls_per_month,
                "percent": self.call_usage_percent
            },
            "storage": {
                "used_gb": round(self.current_storage_bytes / (1024**3), 2),
                "limit_gb": self.max_storage_gb,
                "percent": self.storage_usage_percent
            },
            "users": {
                "limit": self.max_users,
                "percent": 0  # Would need current user count
            }
        }