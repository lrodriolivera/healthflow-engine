"""Modelo Credential — credenciales encriptadas."""

import enum
import uuid

from sqlalchemy import Enum, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantMixin, TimestampMixin


class CredentialType(str, enum.Enum):
    basic = "basic"
    token = "token"
    certificate = "certificate"
    aws = "aws"
    api_key = "api_key"


class Credential(TenantMixin, TimestampMixin, Base):
    """Credencial encriptada para conexiones externas."""

    __tablename__ = "credentials"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    credential_type: Mapped[CredentialType] = mapped_column(
        Enum(CredentialType, name="credential_type_enum"), nullable=False
    )
    encrypted_value: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    def __repr__(self) -> str:
        return f"Credential(id={self.id}, name={self.name}, type={self.credential_type})"
