"""Tests para los agentes AI de HealthFlow."""

import json
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.agents.bedrock import BedrockClient
from backend.app.agents.base import BaseAgent
from backend.app.agents.transform_designer import TransformDesignerAgent
from backend.app.agents.router import RouterAgent
from backend.app.agents.self_healer import SelfHealerAgent
from backend.app.agents.ops import OpsAgent
from backend.app.agents.anomaly_detector import AnomalyDetector, MetricWindow
from backend.app.agents.manager import AgentManager
from backend.app.config import Settings

ADT_A08 = (
    "MSH|^~\\&|SAP|UCCHRISTUS|IRIS|UCCHRISTUS|20260408120000||ADT^A08|MSG001|P|2.5\r"
    "EVN|A08|20260408120000\r"
    "PID|1||PAC123^^^MPI^MR||GONZALEZ^MARIA||19800115|F\r"
    "PV1|1|I|SALA301^CAMA1"
)


def _make_settings(**overrides):
    defaults = {
        "aws_access_key_id": "test_key",
        "aws_secret_access_key": "test_secret",
        "aws_region": "us-east-1",
    }
    defaults.update(overrides)
    with patch.dict(os.environ, {}, clear=True):
        return Settings(_env_file=None, **defaults)


class TestBedrockClient:
    """Tests para el Bedrock client wrapper."""

    def test_extract_text(self):
        response = {
            "output": {
                "message": {
                    "content": [
                        {"text": "Hello"},
                        {"text": " World"},
                    ]
                }
            }
        }
        assert BedrockClient.extract_text(response) == "Hello\n World"

    def test_extract_text_empty(self):
        response = {"output": {"message": {"content": []}}}
        assert BedrockClient.extract_text(response) == ""

    def test_extract_tool_uses(self):
        response = {
            "output": {
                "message": {
                    "content": [
                        {
                            "toolUse": {
                                "toolUseId": "tool-1",
                                "name": "validate",
                                "input": {"code": "test"},
                            }
                        }
                    ]
                }
            }
        }
        tools = BedrockClient.extract_tool_uses(response)
        assert len(tools) == 1
        assert tools[0]["name"] == "validate"
        assert tools[0]["input"]["code"] == "test"

    def test_format_user_message(self):
        msg = BedrockClient.format_user_message("hello")
        assert msg["role"] == "user"
        assert msg["content"][0]["text"] == "hello"

    def test_format_tool_result(self):
        msg = BedrockClient.format_tool_result("tool-1", "result text")
        assert msg["role"] == "user"
        assert msg["content"][0]["toolResult"]["toolUseId"] == "tool-1"


class TestTransformDesigner:
    """Tests para TransformDesigner con Bedrock mockeado."""

    def _make_bedrock_response(self, text: str, stop_reason: str = "end_turn"):
        return {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": text}],
                }
            },
            "stopReason": stop_reason,
            "usage": {"inputTokens": 100, "outputTokens": 50},
        }

    @pytest.mark.asyncio
    async def test_design_transform(self):
        settings = _make_settings()
        bedrock = MagicMock(spec=BedrockClient)
        bedrock.invoke_opus = AsyncMock(return_value=self._make_bedrock_response(
            "def transform(msg, lookup):\n    msg = msg.clone()\n    msg.set('MSH-5', 'TEST')\n    return msg"
        ))

        agent = TransformDesignerAgent(bedrock, settings)
        result = await agent.design_transform(
            spec="Change MSH-5 to TEST",
            sample_messages=[ADT_A08],
        )

        assert result["validated"] is True
        assert "def transform" in result["source_code"]
        assert len(result["test_results"]) == 1
        assert result["test_results"][0]["status"] == "success"

    @pytest.mark.asyncio
    async def test_design_transform_invalid_code(self):
        settings = _make_settings()
        bedrock = MagicMock(spec=BedrockClient)
        bedrock.invoke_opus = AsyncMock(return_value=self._make_bedrock_response(
            "def transform(msg, lookup):\n    return 'not_a_message'"
        ))

        agent = TransformDesignerAgent(bedrock, settings)
        result = await agent.design_transform(
            spec="Bad transform",
            sample_messages=[ADT_A08],
        )

        assert result["validated"] is False

    def test_extract_code_markdown(self):
        text = "Here's the code:\n```python\ndef transform(msg, lookup):\n    return msg\n```\nDone."
        code = TransformDesignerAgent._extract_code(text)
        assert code == "def transform(msg, lookup):\n    return msg"

    def test_extract_code_plain(self):
        text = "def transform(msg, lookup):\n    return msg"
        code = TransformDesignerAgent._extract_code(text)
        assert "def transform" in code


class TestRouterAgent:
    """Tests para AI Router con Bedrock mockeado."""

    @pytest.mark.asyncio
    async def test_route_message(self):
        settings = _make_settings()
        bedrock = MagicMock(spec=BedrockClient)

        routing_response = json.dumps({
            "destinations": [{"name": "LIS", "adapter_name": "MLLP_LIS", "transform": None}],
            "confidence": 0.9,
            "reasoning": "ADT messages should go to LIS",
            "suggested_rule": {
                "name": "Auto: ADT to LIS",
                "conditions": [{"field": "MSH-9.1", "operator": "equals", "value": "ADT"}],
                "destinations": [{"name": "LIS", "adapter_name": "MLLP_LIS"}],
                "priority": 50,
            },
        })
        bedrock.invoke_sonnet = AsyncMock(return_value={
            "output": {"message": {"role": "assistant", "content": [{"text": routing_response}]}},
            "stopReason": "end_turn",
            "usage": {"inputTokens": 200, "outputTokens": 100},
        })

        from backend.app.core.hl7.parser import HL7Message
        agent = RouterAgent(bedrock, settings)
        msg = HL7Message.parse(ADT_A08)
        result = await agent.route(msg, [{"name": "LIS", "adapter_name": "MLLP_LIS"}], [])

        assert len(result["destinations"]) == 1
        assert result["destinations"][0]["name"] == "LIS"
        assert result["confidence"] == 0.9
        assert result["suggested_rule"] is not None

    @pytest.mark.asyncio
    async def test_route_handles_bad_json(self):
        settings = _make_settings()
        bedrock = MagicMock(spec=BedrockClient)
        bedrock.invoke_sonnet = AsyncMock(return_value={
            "output": {"message": {"role": "assistant", "content": [{"text": "not json"}]}},
            "stopReason": "end_turn",
            "usage": {"inputTokens": 100, "outputTokens": 20},
        })

        from backend.app.core.hl7.parser import HL7Message
        agent = RouterAgent(bedrock, settings)
        msg = HL7Message.parse(ADT_A08)
        result = await agent.route(msg, [], [])

        assert result["destinations"] == []
        assert result["confidence"] == 0.0


class TestAnomalyDetector:
    """Tests para AnomalyDetector (ML local, sin mocks)."""

    def test_metric_window_stats(self):
        w = MetricWindow()
        for v in [10, 20, 30, 40, 50]:
            w.add(v)
        assert w.count == 5
        assert w.mean == 30.0
        assert w.min == 10.0
        assert w.max == 50.0

    def test_metric_window_sliding(self):
        w = MetricWindow(window_size=3)
        for v in [1, 2, 3, 4, 5]:
            w.add(v)
        assert w.count == 3
        assert w.values == [3, 4, 5]

    def test_no_anomaly_during_baseline(self):
        detector = AnomalyDetector()
        # During baseline (first 50 messages), no anomalies
        for _ in range(30):
            anomalies = detector.record_message("ADT", "flow-1", 5.0, 500)
            assert anomalies == []

    def test_detect_processing_time_anomaly(self):
        detector = AnomalyDetector(warning_threshold=2.0)
        # Build baseline
        for _ in range(100):
            detector.record_message("ADT", "flow-1", 5.0, 500)

        # Inject anomaly (very slow message)
        anomalies = detector.record_message("ADT", "flow-1", 500.0, 500)
        assert len(anomalies) > 0
        assert anomalies[0].severity in ("warning", "critical")

    def test_get_stats(self):
        detector = AnomalyDetector()
        for _ in range(10):
            detector.record_message("ADT", "flow-1", 5.0, 500)
        stats = detector.get_stats()
        assert "flow-1:ADT" in stats
        assert stats["flow-1:ADT"]["count"] == 10

    def test_error_rate_tracking(self):
        detector = AnomalyDetector()
        for _ in range(10):
            detector.record_message("ADT", "flow-1", 5.0, 500, is_error=False)
        detector.record_message("ADT", "flow-1", 5.0, 500, is_error=True)
        stats = detector.get_stats()
        assert stats["flow-1:ADT"]["error_rate"] > 0


class TestAgentManager:
    """Tests para AgentManager."""

    def test_init_without_credentials(self):
        settings = _make_settings(aws_access_key_id="", aws_secret_access_key="")
        manager = AgentManager(settings)
        manager.initialize()

        assert manager.has_bedrock is False
        assert manager.transform_designer is None
        assert manager.ai_router is None
        assert manager.anomaly_detector is not None
        assert "anomaly_detector" in manager.available_agents

    @patch("backend.app.agents.manager.BedrockClient")
    def test_init_with_credentials(self, mock_bedrock_cls):
        settings = _make_settings()
        manager = AgentManager(settings)
        manager.initialize()

        assert manager.has_bedrock is True
        assert manager.transform_designer is not None
        assert manager.ai_router is not None
        assert manager.self_healer is not None
        assert manager.ops_agent is not None
        assert len(manager.available_agents) == 5
