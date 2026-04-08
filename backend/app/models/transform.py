"""Modelo Transform — código de transformación versionado."""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class Transform(TimestampMixin, Base):
    """Transformación compilada de mensajes HL7.

    Generada por el TransformDesigner agent o escrita manualmente.
    El source_code sigue el contrato:
        def transform(msg: HL7Message, lookup) -> HL7Message
    """

    __tablename__ = "transforms"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    flow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("flows.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    source_code: Mapped[str] = mapped_column(Text, nullable=False)
    input_spec: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_spec: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    test_messages: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # "human" or "transform_designer"

    # Relationships
    flow = relationship("Flow", back_populates="transforms")

    def __repr__(self) -> str:
        return f"Transform(id={self.id}, name={self.name}, v{self.version})"
