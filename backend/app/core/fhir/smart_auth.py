"""
SMART on FHIR Auth — OAuth 2.0 para endpoints FHIR.

Implementa:
  - Token validation (Bearer tokens)
  - SMART scopes (patient/*.read, user/*.write, etc.)
  - Well-known configuration endpoint
  - Token introspection

Para producción, conectar a un Authorization Server externo (Keycloak, Auth0, etc.).
Para desarrollo, soporta tokens estáticos configurables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from enum import Enum

from fastapi import HTTPException, Request, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import structlog

logger = structlog.get_logger()

security_scheme = HTTPBearer(auto_error=False)


class ScopeAccess(str, Enum):
    read = "read"
    write = "write"
    all = "*"


@dataclass
class SMARTToken:
    """Token SMART on FHIR validado."""
    sub: str  # Subject (user or client ID)
    scopes: list[str]  # e.g., ["patient/Patient.read", "user/*.write"]
    exp: Optional[datetime] = None
    client_id: Optional[str] = None
    patient_id: Optional[str] = None  # For patient-level access


@dataclass
class SMARTConfig:
    """Configuración SMART on FHIR."""
    enabled: bool = False
    issuer: str = "https://healthflow.local/auth"
    jwks_uri: str = ""
    # Dev mode: static tokens for testing
    dev_tokens: dict[str, SMARTToken] = field(default_factory=dict)


class SMARTAuthProvider:
    """Provider de autenticación SMART on FHIR."""

    def __init__(self, config: Optional[SMARTConfig] = None):
        self.config = config or SMARTConfig()

    def add_dev_token(self, token: str, sub: str, scopes: list[str], patient_id: str = None) -> None:
        """Agregar token de desarrollo para testing."""
        self.config.dev_tokens[token] = SMARTToken(
            sub=sub,
            scopes=scopes,
            patient_id=patient_id,
        )

    async def validate_token(self, token: str) -> Optional[SMARTToken]:
        """Validar un Bearer token.

        En producción: introspección contra Authorization Server o JWT validation.
        En dev: lookup en tabla de tokens estáticos.
        """
        if not self.config.enabled:
            # Auth disabled — return permissive token
            return SMARTToken(sub="anonymous", scopes=["*/*.*"])

        # Dev mode: static tokens
        if token in self.config.dev_tokens:
            smart_token = self.config.dev_tokens[token]
            if smart_token.exp and smart_token.exp < datetime.now(timezone.utc):
                return None
            return smart_token

        # TODO: JWT validation with JWKS
        # TODO: Token introspection endpoint
        logger.warning("smart_token_invalid", token_prefix=token[:8])
        return None

    def check_scope(self, token: SMARTToken, resource_type: str, access: ScopeAccess) -> bool:
        """Verificar si el token tiene scope para el recurso y acceso requerido.

        SMART scopes format: context/ResourceType.access
        Examples:
          patient/Patient.read — read Patient in patient context
          user/*.write — write any resource in user context
          system/*.* — system-level full access
        """
        required_patterns = [
            f"*/*.*",                          # Wildcard all
            f"*/**.{access.value}",             # Any context, any resource, specific access
            f"*/{resource_type}.*",             # Any context, specific resource, any access
            f"*/{resource_type}.{access.value}",# Any context, specific resource, specific access
        ]

        for scope in token.scopes:
            parts = scope.split("/")
            if len(parts) != 2:
                continue
            context, resource_access = parts[0], parts[1]
            res_parts = resource_access.split(".")
            if len(res_parts) != 2:
                continue
            scope_resource, scope_access = res_parts

            # Check match
            resource_match = scope_resource in ("*", resource_type)
            access_match = scope_access in ("*", access.value)

            if resource_match and access_match:
                return True

        return False

    def get_well_known_config(self) -> dict:
        """SMART Well-Known Configuration (.well-known/smart-configuration)."""
        return {
            "issuer": self.config.issuer,
            "jwks_uri": self.config.jwks_uri,
            "authorization_endpoint": f"{self.config.issuer}/authorize",
            "token_endpoint": f"{self.config.issuer}/token",
            "introspection_endpoint": f"{self.config.issuer}/introspect",
            "scopes_supported": [
                "openid", "fhirUser", "launch", "launch/patient",
                "patient/*.read", "patient/*.write", "patient/*.*",
                "user/*.read", "user/*.write", "user/*.*",
                "system/*.read", "system/*.write", "system/*.*",
            ],
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "client_credentials"],
            "code_challenge_methods_supported": ["S256"],
            "capabilities": [
                "launch-ehr", "launch-standalone",
                "client-public", "client-confidential-symmetric",
                "sso-openid-connect", "context-ehr-patient",
                "permission-patient", "permission-user",
            ],
        }


# Module-level singleton
_auth_provider: Optional[SMARTAuthProvider] = None


def get_auth_provider() -> SMARTAuthProvider:
    global _auth_provider
    if _auth_provider is None:
        _auth_provider = SMARTAuthProvider()
    return _auth_provider


def set_auth_provider(provider: SMARTAuthProvider) -> None:
    global _auth_provider
    _auth_provider = provider


async def require_smart_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme),
) -> SMARTToken:
    """FastAPI dependency — require valid SMART token."""
    provider = get_auth_provider()

    if not provider.config.enabled:
        return SMARTToken(sub="anonymous", scopes=["*/*.*"])

    if not credentials:
        raise HTTPException(401, "Missing Authorization header", headers={"WWW-Authenticate": "Bearer"})

    token = await provider.validate_token(credentials.credentials)
    if not token:
        raise HTTPException(401, "Invalid or expired token", headers={"WWW-Authenticate": "Bearer"})

    return token
