"""
AgentManager — crea y gestiona todos los agentes AI.

Punto central para inicializar todos los agentes con sus dependencias.
"""

from __future__ import annotations

from typing import Optional

import structlog

from .bedrock import BedrockClient
from .transform_designer import TransformDesignerAgent
from .router import RouterAgent
from .self_healer import SelfHealerAgent
from .ops import OpsAgent
from .anomaly_detector import AnomalyDetector
from ..config import Settings

logger = structlog.get_logger()


class AgentManager:
    """Gestor central de todos los agentes."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._bedrock: Optional[BedrockClient] = None

        # Agents
        self.transform_designer: Optional[TransformDesignerAgent] = None
        self.ai_router: Optional[RouterAgent] = None
        self.self_healer: Optional[SelfHealerAgent] = None
        self.ops_agent: Optional[OpsAgent] = None
        self.anomaly_detector: AnomalyDetector = AnomalyDetector()

    def initialize(self) -> None:
        """Inicializar todos los agentes.

        Requiere credenciales AWS configuradas para los agentes que usan Bedrock.
        El AnomalyDetector funciona sin credenciales (ML local).
        """
        if self._settings.aws_access_key_id and self._settings.aws_secret_access_key:
            try:
                self._bedrock = BedrockClient(self._settings)
                self.transform_designer = TransformDesignerAgent(self._bedrock, self._settings)
                self.ai_router = RouterAgent(self._bedrock, self._settings)
                self.self_healer = SelfHealerAgent(self._bedrock, self._settings)
                self.ops_agent = OpsAgent(self._bedrock, self._settings)
                logger.info(
                    "agents_initialized",
                    agents=["transform_designer", "ai_router", "self_healer", "ops_agent", "anomaly_detector"],
                    bedrock_region=self._settings.aws_region,
                    model_sonnet=self._settings.bedrock_model_sonnet,
                    model_opus=self._settings.bedrock_model_opus,
                )
            except Exception as e:
                logger.error("agents_init_failed", error=str(e))
                logger.info("agents_degraded_mode", agents=["anomaly_detector"])
        else:
            logger.warning(
                "agents_no_credentials",
                message="AWS credentials not configured — running without AI agents",
                agents=["anomaly_detector"],
            )

    @property
    def has_bedrock(self) -> bool:
        return self._bedrock is not None

    @property
    def available_agents(self) -> list[str]:
        agents = ["anomaly_detector"]
        if self.transform_designer:
            agents.append("transform_designer")
        if self.ai_router:
            agents.append("ai_router")
        if self.self_healer:
            agents.append("self_healer")
        if self.ops_agent:
            agents.append("ops_agent")
        return agents
