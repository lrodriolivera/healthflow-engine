"""Modelo Tenant para multi-tenancy."""

import uuid

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class Tenant(TimestampMixin, Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    settings: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    flows = relationship("Flow", back_populates="tenant", cascade="all, delete-orphan")
    lookup_tables = relationship("LookupTable", back_populates="tenant", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"Tenant(id={self.id}, slug={self.slug})"
