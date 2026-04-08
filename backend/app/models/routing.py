"""Modelo RoutingRuleModel — persiste reglas del engine determinista."""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class RoutingRuleModel(TimestampMixin, Base):
    """Regla de routing persistida en DB.

    Se carga en memoria al iniciar el RoutingEngine.
    Puede ser generada por el AI Router agent.
    """

    __tablename__ = "routing_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    flow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("flows.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    conditions: Mapped[dict] = mapped_column(JSONB, nullable=False)
    destinations: Mapped[dict] = mapped_column(JSONB, nullable=False)
    stop_on_match: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # "human" or "ai_router"

    # Relationships
    flow = relationship("Flow", back_populates="routing_rules")

    def __repr__(self) -> str:
        return f"RoutingRuleModel(id={self.id}, name={self.name}, priority={self.priority})"
