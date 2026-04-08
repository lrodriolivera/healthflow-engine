"""Tests para el sistema de configuración."""

import os
import pytest
from unittest.mock import patch

from backend.app.config import Settings


class TestSettings:

    def test_default_values(self):
        """Settings tiene defaults funcionales sin .env."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings(
                _env_file=None,
                aws_access_key_id="test",
                aws_secret_access_key="test",
            )
        assert settings.app_name == "HealthFlow Engine"
        assert settings.app_version == "0.1.0"
        assert settings.debug is False
        assert settings.mllp_default_port == 2575
        assert settings.mllp_ack_mode == "immediate"

    def test_env_prefix(self):
        """Variables con prefijo HF_ se cargan correctamente."""
        env = {
            "HF_DEBUG": "true",
            "HF_LOG_LEVEL": "DEBUG",
            "HF_MLLP_DEFAULT_PORT": "3000",
            "HF_AWS_ACCESS_KEY_ID": "AKIATEST",
            "HF_AWS_SECRET_ACCESS_KEY": "secret",
        }
        with patch.dict(os.environ, env, clear=True):
            settings = Settings(_env_file=None)
        assert settings.debug is True
        assert settings.log_level == "DEBUG"
        assert settings.mllp_default_port == 3000

    def test_database_url_default(self):
        settings = Settings(
            _env_file=None,
            aws_access_key_id="test",
            aws_secret_access_key="test",
        )
        assert "asyncpg" in settings.database_url
        assert "healthflow" in settings.database_url

    def test_bedrock_models(self):
        settings = Settings(
            _env_file=None,
            aws_access_key_id="test",
            aws_secret_access_key="test",
        )
        assert "claude-sonnet" in settings.bedrock_model_sonnet
        assert "claude-opus" in settings.bedrock_model_opus

    def test_nats_config(self):
        settings = Settings(
            _env_file=None,
            aws_access_key_id="test",
            aws_secret_access_key="test",
        )
        assert settings.nats_url == "nats://localhost:4222"
        assert settings.nats_stream_name == "HEALTHFLOW"

    def test_otel_config(self):
        settings = Settings(
            _env_file=None,
            aws_access_key_id="test",
            aws_secret_access_key="test",
        )
        assert settings.otel_enabled is True
        assert settings.otel_service_name == "healthflow-engine"
