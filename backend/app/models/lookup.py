"""Modelos LookupTable y LookupEntry — equivalentes a globals en IRIS."""

import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TenantMixin, TimestampMixin


class LookupTable(TenantMixin, TimestampMixin, Base):
    """Tabla de lookup clave-valor, cacheada en Redis."""

    __tablename__ = "lookup_tables"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    tenant = relationship("Tenant", back_populates="lookup_tables")
    entries = relationship("LookupEntry", back_populates="table", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"LookupTable(id={self.id}, name={self.name})"


class LookupEntry(TimestampMixin, Base):
    """Entrada individual de una lookup table."""

    __tablename__ = "lookup_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    table_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lookup_tables.id", ondelete="CASCADE"),
        nullable=False,
    )
    key: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    table = relationship("LookupTable", back_populates="entries")

    def __repr__(self) -> str:
        return f"LookupEntry(key={self.key})"
