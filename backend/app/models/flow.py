"""Modelos Flow y Adapter — equivalentes a Production items en IRIS."""

import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TenantMixin, TimestampMixin


class AdapterType(str, enum.Enum):
    mllp_in = "mllp_in"
    mllp_out = "mllp_out"
    soap_in = "soap_in"
    soap_out = "soap_out"
    rest_in = "rest_in"
    rest_out = "rest_out"
    fhir_in = "fhir_in"
    fhir_out = "fhir_out"
    file_in = "file_in"
    file_out = "file_out"


class Flow(TenantMixin, TimestampMixin, Base):
    """Un flujo de integración (equivale a un Production item en IRIS)."""

    __tablename__ = "flows"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="flows")
    adapters = relationship("Adapter", back_populates="flow", cascade="all, delete-orphan")
    routing_rules = relationship("RoutingRuleModel", back_populates="flow", cascade="all, delete-orphan")
    transforms = relationship("Transform", back_populates="flow", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"Flow(id={self.id}, name={self.name})"


class Adapter(TimestampMixin, Base):
    """Configuración de un adapter (inbound o outbound)."""

    __tablename__ = "adapters"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    flow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("flows.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    adapter_type: Mapped[AdapterType] = mapped_column(
        Enum(AdapterType, name="adapter_type_enum"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    host: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    flow = relationship("Flow", back_populates="adapters")

    def __repr__(self) -> str:
        return f"Adapter(id={self.id}, name={self.name}, type={self.adapter_type})"
