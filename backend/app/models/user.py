"""
User model for authentication and authorization.
"""
import enum
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Enum, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base, TimestampMixin, AuditMixin, SoftDeleteMixin

class UserRole(str, enum.Enum):
    """User roles enumeration."""
    USER = "user"
    MANAGER = "manager"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"

class User(Base, TimestampMixin, AuditMixin, SoftDeleteMixin):
    """
    User model representing application users.
    """
    __tablename__ = "users"
    
    # Identification
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=True, index=True)
    full_name = Column(String(255), nullable=True)
    
    # Authentication
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, index=True)
    is_verified = Column(Boolean, default=False)
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    
    # Roles and permissions
    role = Column(Enum(UserRole), default=UserRole.USER, index=True)
    permissions = Column(JSON, default=list)  # Additional permissions beyond role
    
    # Profile
    avatar_url = Column(String(500), nullable=True)
    phone_number = Column(String(50), nullable=True)
    timezone = Column(String(100), default="UTC")
    locale = Column(String(10), default="en-US")
    
    # Security
    last_login = Column(DateTime(timezone=True), nullable=True)
    last_password_change = Column(DateTime(timezone=True), nullable=True)
    password_reset_token = Column(String(255), nullable=True)
    password_reset_expires = Column(DateTime(timezone=True), nullable=True)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    
    # API Access
    api_key = Column(String(255), nullable=True, index=True)
    api_key_expires = Column(DateTime(timezone=True), nullable=True)
    
    # Tenant
    tenant_id = Column(String(36), nullable=False, index=True)
    
    # Preferences
    preferences = Column(JSON, default=dict)
    notification_settings = Column(JSON, default={
        "email": True,
        "push": False,
        "slack": False,
        "teams": False
    })
    
    # Relationships
    calls = relationship("Call", back_populates="user", cascade="all, delete-orphan")
    crm_configs = relationship("CRMConfig", back_populates="created_by_user", cascade="all, delete-orphan")
    webhooks = relationship("Webhook", back_populates="created_by_user", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('ix_users_email_tenant', 'email', 'tenant_id', unique=True),
        Index('ix_users_username_tenant', 'username', 'tenant_id', unique=True),
        Index('ix_users_tenant_active', 'tenant_id', 'is_active'),
        Index('ix_users_created_at', 'created_at'),
    )
    
    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """Convert user to dictionary, optionally including sensitive data."""
        data = {
            "id": self.id,
            "email": self.email,
            "username": self.username,
            "full_name": self.full_name,
            "role": self.role.value if self.role else None,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "avatar_url": self.avatar_url,
            "phone_number": self.phone_number,
            "timezone": self.timezone,
            "locale": self.locale,
            "tenant_id": self.tenant_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "preferences": self.preferences,
            "notification_settings": self.notification_settings
        }
        
        if include_sensitive:
            data.update({
                "api_key": self.api_key,
                "api_key_expires": self.api_key_expires.isoformat() if self.api_key_expires else None,
                "failed_login_attempts": self.failed_login_attempts,
                "locked_until": self.locked_until.isoformat() if self.locked_until else None
            })
        
        return data
    
    def lock_account(self, minutes: int = 30) -> None:
        """Lock user account for specified minutes."""
        self.locked_until = datetime.utcnow() + timedelta(minutes=minutes)
        self.failed_login_attempts = 0
    
    def unlock_account(self) -> None:
        """Unlock user account."""
        self.locked_until = None
        self.failed_login_attempts = 0
    
    def increment_failed_attempts(self, max_attempts: int = 5) -> bool:
        """
        Increment failed login attempts.
        Returns True if account should be locked.
        """
        self.failed_login_attempts += 1
        
        if self.failed_login_attempts >= max_attempts:
            self.lock_account()
            return True
        return False
    
    def reset_failed_attempts(self) -> None:
        """Reset failed login attempts."""
        self.failed_login_attempts = 0
        self.locked_until = None
    
    def is_locked(self) -> bool:
        """Check if account is locked."""
        if not self.locked_until:
            return False
        return datetime.utcnow() < self.locked_until
    
    def can_login(self) -> bool:
        """Check if user can login."""
        return self.is_active and not self.is_locked()
    
    def generate_api_key(self, expires_days: int = 365) -> str:
        """Generate a new API key."""
        from app.core.security import generate_api_key, hash_api_key
        
        api_key = generate_api_key()
        self.api_key = hash_api_key(api_key)
        self.api_key_expires = datetime.utcnow() + timedelta(days=expires_days)
        
        return api_key
    
    def verify_api_key(self, api_key: str) -> bool:
        """Verify an API key."""
        from app.core.security import verify_api_key
        
        if not self.api_key or not self.api_key_expires:
            return False
        
        # Check expiration
        if datetime.utcnow() > self.api_key_expires:
            return False
        
        return verify_api_key(api_key, self.api_key)
    
    def revoke_api_key(self) -> None:
        """Revoke the API key."""
        self.api_key = None
        self.api_key_expires = None
    
    @property
    def display_name(self) -> str:
        """Get display name (full name or email)."""
        return self.full_name or self.email.split('@')[0]
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has specific permission."""
        if self.role == UserRole.SUPER_ADMIN:
            return True
        
        # Check role-based permissions
        role_permissions = {
            UserRole.USER: [
                "call:create",
                "call:read:own",
                "call:update:own",
                "call:delete:own",
                "profile:read",
                "profile:update"
            ],
            UserRole.MANAGER: [
                "call:create",
                "call:read:team",
                "call:update:team",
                "call:delete:team",
                "analytics:read:team",
                "user:read:team",
                "crm:read",
                "crm:update"
            ],
            UserRole.ADMIN: [
                "call:*",
                "user:*",
                "crm:*",
                "analytics:*",
                "settings:*",
                "webhook:*"
            ]
        }
        
        base_permissions = role_permissions.get(self.role, [])
        
        # Check additional permissions
        additional_permissions = self.permissions or []
        
        # Check wildcard permissions
        if "*" in base_permissions + additional_permissions:
            return True
        
        # Check exact permission
        if permission in base_permissions + additional_permissions:
            return True
        
        # Check wildcard pattern (e.g., "call:*" matches "call:create")
        for perm in base_permissions + additional_permissions:
            if perm.endswith("*") and permission.startswith(perm[:-1]):
                return True
        
        return False
    
    def can_access_tenant(self, tenant_id: str) -> bool:
        """Check if user can access a specific tenant."""
        return self.tenant_id == tenant_id or self.role == UserRole.SUPER_ADMIN