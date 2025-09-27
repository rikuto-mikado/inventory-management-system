"""
Base model classes for the Inventory Management System.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, String, Boolean, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, mapped_column

# Create the declarative base
Base = declarative_base()


class BaseModel(Base):
    """
    Abstract base model class with common fields and methods.
    """

    __abstract__ = True

    # Primary key using UUID
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("uuid_generate_v4()"),
    )

    # Timestamp fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        """String representation of the model."""
        class_name = self.__class__.__name__
        return f"<{class_name}(id={self.id})>"

    def to_dict(self, include_relationships: bool = False) -> Dict[str, Any]:
        """
        Convert model instance to dictionary.

        Args:
            include_relationships: Whether to include relationship data

        Returns:
            Dictionary representation of the model
        """
        result = {}

        # Include column attributes
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            # Convert UUID and datetime to string for JSON serialization
            if isinstance(value, uuid.UUID):
                value = str(value)
            elif isinstance(value, datetime):
                value = value.isoformat()
            result[column.name] = value

        # Include relationships if requested
        if include_relationships:
            for relationship in self.__mapper__.relationships:
                rel_name = relationship.key
                rel_value = getattr(self, rel_name)

                if rel_value is None:
                    result[rel_name] = None
                elif hasattr(rel_value, "to_dict"):
                    # Single relationship
                    result[rel_name] = rel_value.to_dict(include_relationships=False)
                elif hasattr(rel_value, "__iter__"):
                    # Collection relationship
                    result[rel_name] = [
                        item.to_dict(include_relationships=False)
                        for item in rel_value
                        if hasattr(item, "to_dict")
                    ]

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaseModel":
        """
        Create model instance from dictionary.

        Args:
            data: Dictionary with model data

        Returns:
            Model instance
        """
        # Filter out non-column attributes
        column_names = {column.name for column in cls.__table__.columns}
        filtered_data = {k: v for k, v in data.items() if k in column_names}

        # Convert string UUIDs back to UUID objects
        if "id" in filtered_data and isinstance(filtered_data["id"], str):
            filtered_data["id"] = uuid.UUID(filtered_data["id"])

        return cls(**filtered_data)

    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """
        Update model instance from dictionary.

        Args:
            data: Dictionary with updated data
        """
        column_names = {column.name for column in self.__table__.columns}

        for key, value in data.items():
            if key in column_names and key not in ("id", "created_at"):
                setattr(self, key, value)


class TimestampMixin:
    """
    Mixin class for models that need timestamp tracking.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ActiveRecordMixin:
    """
    Mixin class that adds active/inactive status tracking.
    """

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("TRUE")
    )

    def activate(self) -> None:
        """Mark the record as active."""
        self.is_active = True

    def deactivate(self) -> None:
        """Mark the record as inactive."""
        self.is_active = False


class SoftDeleteMixin:
    """
    Mixin class for soft delete functionality.
    """

    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    @property
    def is_deleted(self) -> bool:
        """Check if the record is soft deleted."""
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """Soft delete the record."""
        self.deleted_at = datetime.utcnow()

    def restore(self) -> None:
        """Restore a soft deleted record."""
        self.deleted_at = None


# Utility functions for working with models


def get_model_by_table_name(table_name: str) -> Optional[type]:
    """
    Get model class by table name.

    Args:
        table_name: Name of the database table

    Returns:
        Model class or None if not found
    """
    for cls in Base.registry._class_registry.values():
        if hasattr(cls, "__tablename__") and cls.__tablename__ == table_name:
            return cls
    return None


def get_all_models() -> list:
    """
    Get all model classes that inherit from BaseModel.

    Returns:
        List of model classes
    """
    models = []
    for cls in Base.registry._class_registry.values():
        if (
            hasattr(cls, "__tablename__")
            and hasattr(cls, "__table__")
            and issubclass(cls, BaseModel)
        ):
            models.append(cls)
    return models


def create_all_tables(engine):
    """
    Create all tables in the database.

    Args:
        engine: SQLAlchemy engine
    """
    Base.metadata.create_all(bind=engine)


def drop_all_tables(engine):
    """
    Drop all tables from the database.

    Args:
        engine: SQLAlchemy engine
    """
    Base.metadata.drop_all(bind=engine)


# Export the base class and mixins
__all__ = [
    "Base",
    "BaseModel",
    "TimestampMixin",
    "ActiveRecordMixin",
    "SoftDeleteMixin",
    "get_model_by_table_name",
    "get_all_models",
    "create_all_tables",
    "drop_all_tables",
]
