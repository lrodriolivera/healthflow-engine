"""Modelos MessageLog y ErrorQueue.

MessageLog usa TimescaleDB hypertable para time-series.
ErrorQueue almacena mensajes fallidos para retry/self-healing.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class MessageStatus(str, enum.Enum):
    received = "received"
    routed = "routed"
    transformed = "transformed"
    sent = "sent"
    acked = "acked"
    error = "error"
    dlq = "dlq"


class MessageLog(Base):
    """Resumen de cada mensaje procesado. TimescaleDB hypertable."""

    __tablename__ = "message_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    flow_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    message_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    trigger_event: Mapped[str | None] = mapped_column(String(10), nullable=True)
    message_control_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    sending_app: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sending_facility: Mapped[str | None] = mapped_column(String(255), nullable=True)
    receiving_app: Mapped[str | None] = mapped_column(String(255), nullable=True)
    receiving_facility: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[MessageStatus] = mapped_column(
        Enum(MessageStatus, name="message_status_enum"), nullable=False, index=True
    )
    raw_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processing_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    destinations: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return f"MessageLog(id={self.id}, type={self.message_type}, status={self.status})"


class ErrorQueue(Base):
    """Cola de errores para retry y self-healing."""

    __tablename__ = "error_queue"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    flow_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    message_log_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    error_type: Mapped[str] = mapped_column(String(100), nullable=False)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    diagnosis: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return f"ErrorQueue(id={self.id}, type={self.error_type}, retries={self.retry_count})"
