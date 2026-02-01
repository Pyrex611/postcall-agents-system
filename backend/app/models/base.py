"""
Base model class with common functionality.
"""
from datetime import datetime
from typing import Any, Dict
from sqlalchemy import Column, DateTime
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.sql import func

class CustomBase:
    """
    Custom base class for all models.
    """
    
    @declared_attr
    def __tablename__(cls) -> str:
        """Generate table name from class name."""
        return cls.__name__.lower()
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary."""
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            
            # Handle special types
            if isinstance(value, datetime):
                value = value.isoformat()
            elif isinstance(value, uuid.UUID):
                value = str(value)
            
            result[column.name] = value
        
        return result
    
    def update(self, **kwargs) -> None:
        """Update model attributes."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    @classmethod
    def get_columns(cls) -> List[str]:
        """Get list of column names."""
        return [column.name for column in cls.__table__.columns]

# Create declarative base
Base = declarative_base(cls=CustomBase)

class TimestampMixin:
    """Mixin for timestamp fields."""
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

class SoftDeleteMixin:
    """Mixin for soft delete functionality."""
    is_deleted = Column(Boolean, default=False, index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(String(36), nullable=True)
    
    def soft_delete(self, user_id: str = None) -> None:
        """Soft delete the record."""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
        if user_id:
            self.deleted_by = user_id
    
    def restore(self) -> None:
        """Restore a soft-deleted record."""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None

class AuditMixin:
    """Mixin for audit fields."""
    created_by = Column(String(36), nullable=True)
    updated_by = Column(String(36), nullable=True)
    deleted_by = Column(String(36), nullable=True)