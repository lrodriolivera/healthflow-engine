"""
Configuración centralizada de HealthFlow Engine.

Usa pydantic-settings para cargar desde variables de entorno (prefijo HF_)
o desde archivo .env en la raíz del proyecto.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración de HealthFlow Engine."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="HF_",
        case_sensitive=False,
    )

    # App
    app_name: str = "HealthFlow Engine"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"

    # Database (PostgreSQL + TimescaleDB)
    database_url: str = "postgresql+asyncpg://healthflow:healthflow@localhost:5432/healthflow"
    database_pool_size: int = 20
    database_max_overflow: int = 10

    # NATS JetStream
    nats_url: str = "nats://localhost:4222"
    nats_stream_name: str = "HEALTHFLOW"
    nats_max_pending: int = 65536

    # Redis
    redis_url: str = "redis://localhost:6379"
    redis_lookup_db: int = 0
    redis_cache_db: int = 1

    # AWS Bedrock
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    bedrock_model_sonnet: str = "us.anthropic.claude-sonnet-4-6-20250514-v1:0"
    bedrock_model_opus: str = "us.anthropic.claude-opus-4-6-20250514-v1:0"

    # MLLP
    mllp_default_port: int = 2575
    mllp_read_timeout: int = 30
    mllp_ack_mode: str = "immediate"

    # OpenTelemetry
    otel_endpoint: str = "http://localhost:4317"
    otel_service_name: str = "healthflow-engine"
    otel_enabled: bool = True


@lru_cache
def get_settings() -> Settings:
    """Singleton de Settings para uso como dependency de FastAPI."""
    return Settings()
