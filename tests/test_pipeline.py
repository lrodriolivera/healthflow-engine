"""Tests para el pipeline orchestrator y componentes del bus."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.bus.nats_client import NATSMessage
from backend.app.core.pipeline import MessagePipeline, _extract_ack_code
from backend.app.core.routing.engine import (
    RoutingEngine,
    RoutingRule,
    RoutingCondition,
    RoutingDestination,
)
from backend.app.adapters.registry import AdapterRegistry
from backend.app.adapters.handler import create_nats_handler
from backend.app.core.hl7.parser import HL7Message

# Sample HL7 messages
ADT_A08_SAMPLE = (
    "MSH|^~\\&|SAP|UCCHRISTUS|IRIS|UCCHRISTUS|20260408120000||ADT^A08|MSG001|P|2.5\r"
    "EVN|A08|20260408120000\r"
    "PID|1||PAC123^^^MPI^MR||GONZALEZ^MARIA||19800115|F\r"
    "PV1|1|I|SALA301^CAMA1"
)


class TestNATSMessage:
    """Tests para serialización de NATSMessage."""

    def test_to_bytes_and_back(self):
        msg = NATSMessage(
            subject="flow.abc.inbound",
            raw=ADT_A08_SAMPLE,
            flow_id="abc-123",
            trace_id="trace-456",
            metadata={"message_type": "ADT^A08", "source_adapter": "MLLP_2575"},
        )
        data = msg.to_bytes()
        restored = NATSMessage.from_bytes("flow.abc.inbound", data)

        assert restored.raw == ADT_A08_SAMPLE
        assert restored.flow_id == "abc-123"
        assert restored.trace_id == "trace-456"
        assert restored.metadata["message_type"] == "ADT^A08"

    def test_to_bytes_is_json(self):
        msg = NATSMessage(subject="test", raw="MSH|...", flow_id="f1")
        data = msg.to_bytes()
        parsed = json.loads(data)
        assert parsed["flow_id"] == "f1"
        assert parsed["raw"] == "MSH|..."

    def test_empty_metadata(self):
        msg = NATSMessage(subject="test", raw="raw")
        data = msg.to_bytes()
        restored = NATSMessage.from_bytes("test", data)
        assert restored.metadata == {}


class TestAdapterRegistry:
    """Tests para el registry de adapters outbound."""

    def test_register_and_get(self):
        registry = AdapterRegistry()
        mock_adapter = MagicMock()
        registry.register("MLLP_LIS", mock_adapter)
        assert registry.get("MLLP_LIS") is mock_adapter
        assert registry.count == 1

    def test_get_missing_returns_none(self):
        registry = AdapterRegistry()
        assert registry.get("nonexistent") is None

    def test_unregister(self):
        registry = AdapterRegistry()
        mock_adapter = MagicMock()
        registry.register("MLLP_LIS", mock_adapter)
        assert registry.unregister("MLLP_LIS") is True
        assert registry.get("MLLP_LIS") is None
        assert registry.count == 0

    def test_list_names(self):
        registry = AdapterRegistry()
        registry.register("A", MagicMock())
        registry.register("B", MagicMock())
        assert set(registry.list_names()) == {"A", "B"}

    def test_list_destinations(self):
        registry = AdapterRegistry()
        registry.register("MLLP_LIS", MagicMock())
        dests = registry.list_destinations()
        assert len(dests) == 1
        assert dests[0]["name"] == "MLLP_LIS"


class TestCreateNatsHandler:
    """Tests para el handler factory MLLP→NATS."""

    @pytest.mark.asyncio
    async def test_handler_publishes_to_nats(self):
        mock_nats = AsyncMock()
        handler = create_nats_handler(mock_nats, "flow-123")

        msg = HL7Message.parse(ADT_A08_SAMPLE)
        await handler(msg, "MLLP_2575")

        mock_nats.publish.assert_called_once()
        call_args = mock_nats.publish.call_args
        subject = call_args[0][0]
        nats_msg = call_args[0][1]

        assert subject == "flow.flow-123.inbound"
        assert nats_msg.flow_id == "flow-123"
        assert nats_msg.metadata["message_type"] == "ADT^A08"
        assert nats_msg.metadata["sending_app"] == "SAP"

    @pytest.mark.asyncio
    async def test_handler_returns_none(self):
        """Handler retorna None — ACK handled by MLLP listener."""
        mock_nats = AsyncMock()
        handler = create_nats_handler(mock_nats, "flow-123")
        msg = HL7Message.parse(ADT_A08_SAMPLE)
        result = await handler(msg, "MLLP_2575")
        assert result is None


class TestPipelineInbound:
    """Tests para pipeline._on_inbound."""

    def _make_pipeline(self, routing_engine=None, adapter_registry=None):
        nats = AsyncMock()
        routing = routing_engine or RoutingEngine()
        registry = adapter_registry or AdapterRegistry()
        return MessagePipeline(
            nats_client=nats,
            routing_engine=routing,
            adapter_registry=registry,
        ), nats

    @pytest.mark.asyncio
    async def test_inbound_routes_to_destinations(self):
        """Mensaje ADT ruteado a LIS y RIS."""
        engine = RoutingEngine()
        engine.add_rule(RoutingRule(
            name="ADT to all",
            conditions=[RoutingCondition(field="MSH-9.1", operator="equals", value="ADT")],
            destinations=[
                RoutingDestination(name="LIS", adapter_name="MLLP_LIS"),
                RoutingDestination(name="RIS", adapter_name="MLLP_RIS"),
            ],
        ))

        pipeline, mock_nats = self._make_pipeline(routing_engine=engine)

        msg = NATSMessage(
            subject="flow.f1.inbound",
            raw=ADT_A08_SAMPLE,
            flow_id="f1",
            trace_id="t1",
        )
        await pipeline._on_inbound(msg)

        # Debe publicar 2 mensajes routed (LIS y RIS)
        assert mock_nats.publish.call_count == 2
        subjects = [call[0][0] for call in mock_nats.publish.call_args_list]
        assert "flow.f1.routed.LIS" in subjects
        assert "flow.f1.routed.RIS" in subjects

    @pytest.mark.asyncio
    async def test_inbound_no_match_publishes_error(self):
        """Sin match y sin AI router → publica error."""
        pipeline, mock_nats = self._make_pipeline()

        msg = NATSMessage(
            subject="flow.f1.inbound",
            raw=ADT_A08_SAMPLE,
            flow_id="f1",
            trace_id="t1",
        )
        await pipeline._on_inbound(msg)

        # Debe publicar 1 error
        assert mock_nats.publish.call_count == 1
        subject = mock_nats.publish.call_args[0][0]
        assert subject == "flow.f1.error"

    @pytest.mark.asyncio
    async def test_inbound_bad_message_publishes_error(self):
        """Mensaje malformado → publica error."""
        pipeline, mock_nats = self._make_pipeline()

        msg = NATSMessage(
            subject="flow.f1.inbound",
            raw="NOT_HL7_DATA",
            flow_id="f1",
            trace_id="t1",
        )
        await pipeline._on_inbound(msg)

        assert mock_nats.publish.call_count == 1
        nats_msg = mock_nats.publish.call_args[0][1]
        assert nats_msg.metadata["error_type"] == "parse_or_route_error"


class TestPipelineRouted:
    """Tests para pipeline._on_routed."""

    @pytest.mark.asyncio
    async def test_routed_passthrough(self):
        """Sin transform → passthrough."""
        nats = AsyncMock()
        pipeline = MessagePipeline(
            nats_client=nats,
            routing_engine=RoutingEngine(),
            adapter_registry=AdapterRegistry(),
        )

        msg = NATSMessage(
            subject="flow.f1.routed.LIS",
            raw=ADT_A08_SAMPLE,
            flow_id="f1",
            trace_id="t1",
            metadata={"destination": "LIS", "adapter_name": "MLLP_LIS", "transform": ""},
        )
        await pipeline._on_routed(msg)

        assert nats.publish.call_count == 1
        subject = nats.publish.call_args[0][0]
        assert subject == "flow.f1.transformed.LIS"
        # Raw should be unchanged (passthrough)
        published_msg = nats.publish.call_args[0][1]
        assert published_msg.raw == ADT_A08_SAMPLE


class TestPipelineTransformed:
    """Tests para pipeline._on_transformed."""

    @pytest.mark.asyncio
    async def test_transformed_sends_via_adapter(self):
        """Mensaje transformado se envía por adapter outbound."""
        nats = AsyncMock()
        registry = AdapterRegistry()

        mock_sender = AsyncMock()
        mock_sender.send.return_value = (
            "MSH|^~\\&|LIS|LAB|SAP|UCCHRISTUS|20260408||ACK|ACK001|P|2.5\r"
            "MSA|AA|MSG001"
        )
        registry.register("MLLP_LIS", mock_sender)

        pipeline = MessagePipeline(
            nats_client=nats,
            routing_engine=RoutingEngine(),
            adapter_registry=registry,
        )

        msg = NATSMessage(
            subject="flow.f1.transformed.LIS",
            raw=ADT_A08_SAMPLE,
            flow_id="f1",
            trace_id="t1",
            metadata={"destination": "LIS", "adapter_name": "MLLP_LIS"},
        )
        await pipeline._on_transformed(msg)

        mock_sender.send.assert_called_once_with(ADT_A08_SAMPLE)
        assert nats.publish.call_count == 1
        subject = nats.publish.call_args[0][0]
        assert subject == "flow.f1.ack.LIS"

    @pytest.mark.asyncio
    async def test_transformed_missing_adapter_publishes_error(self):
        """Adapter no encontrado → error."""
        nats = AsyncMock()
        pipeline = MessagePipeline(
            nats_client=nats,
            routing_engine=RoutingEngine(),
            adapter_registry=AdapterRegistry(),
        )

        msg = NATSMessage(
            subject="flow.f1.transformed.LIS",
            raw=ADT_A08_SAMPLE,
            flow_id="f1",
            trace_id="t1",
            metadata={"destination": "LIS", "adapter_name": "NONEXISTENT"},
        )
        await pipeline._on_transformed(msg)

        assert nats.publish.call_count == 1
        error_msg = nats.publish.call_args[0][1]
        assert error_msg.metadata["error_type"] == "outbound_error"


class TestExtractAckCode:

    def test_extract_aa(self):
        ack = "MSH|^~\\&|LIS||SAP||20260408||ACK|ACK1|P|2.5\rMSA|AA|MSG001"
        assert _extract_ack_code(ack) == "AA"

    def test_extract_ae(self):
        ack = "MSH|^~\\&|LIS||SAP||20260408||ACK|ACK1|P|2.5\rMSA|AE|MSG001|Error"
        assert _extract_ack_code(ack) == "AE"

    def test_invalid_returns_unknown(self):
        assert _extract_ack_code("not hl7") == "unknown"
