"""Tests para la API REST de HealthFlow Engine."""

import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from backend.app.core.routing.engine import RoutingEngine
from backend.app.core.transform import TransformRegistry
from backend.app.adapters.registry import AdapterRegistry
from backend.app.agents.anomaly_detector import AnomalyDetector


ADT_A08 = (
    "MSH|^~\\&|SAP|UCCHRISTUS|IRIS|UCCHRISTUS|20260408120000||ADT^A08|MSG001|P|2.5\r"
    "EVN|A08|20260408120000\r"
    "PID|1||PAC123^^^MPI^MR||GONZALEZ^MARIA||19800115|F\r"
    "PV1|1|I|SALA301^CAMA1"
)


@pytest.fixture
def client():
    """TestClient con dependencias mockeadas (sin NATS/Redis/DB reales)."""
    with patch("backend.app.main.NATSClient") as mock_nats_cls, \
         patch("backend.app.main.RedisClient") as mock_redis_cls, \
         patch("backend.app.main.create_engine") as mock_engine, \
         patch("backend.app.main.create_session_factory") as mock_session_factory, \
         patch("backend.app.main.load_all", new_callable=AsyncMock) as mock_load, \
         patch("backend.app.main.AgentManager") as mock_agent_cls:

        mock_nats = MagicMock()
        mock_nats.is_connected = False
        mock_nats.connect = AsyncMock()
        mock_nats.close = AsyncMock()
        mock_nats_cls.return_value = mock_nats

        mock_redis = MagicMock()
        mock_redis.is_connected = False
        mock_redis.connect = AsyncMock()
        mock_redis.close = AsyncMock()
        mock_redis_cls.return_value = mock_redis

        mock_eng = MagicMock()
        mock_eng.dispose = AsyncMock()
        mock_engine.return_value = mock_eng

        # Session factory mock
        mock_sf = MagicMock()
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_sf.return_value = mock_session
        mock_session_factory.return_value = mock_sf

        mock_agent = MagicMock()
        mock_agent.available_agents = ["anomaly_detector"]
        mock_agent.has_bedrock = False
        mock_agent.ai_router = None
        mock_agent.ops_agent = None
        mock_agent.self_healer = None
        mock_agent.transform_designer = None
        mock_agent.anomaly_detector = AnomalyDetector()
        mock_agent_cls.return_value = mock_agent

        mock_load.return_value = {}

        from backend.app.main import app
        with TestClient(app) as c:
            yield c


class TestHealthEndpoint:

    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["engine"] == "healthflow"


class TestMessagesEndpoint:

    def test_parse_valid_hl7(self, client):
        r = client.post("/api/v1/messages/parse", json={"message": ADT_A08})
        assert r.status_code == 200
        data = r.json()
        assert data["message_type"] == "ADT^A08"
        assert data["trigger_event"] == "A08"
        assert data["message_id"] == "MSG001"
        assert data["sending_app"] == "SAP"
        assert data["segment_count"] == 4

    def test_parse_invalid_hl7(self, client):
        r = client.post("/api/v1/messages/parse", json={"message": "NOT_HL7"})
        assert r.status_code == 400


class TestRoutingEndpoints:

    def test_list_rules_empty(self, client):
        r = client.get("/api/v1/routing/rules")
        assert r.status_code == 200
        assert r.json() == []

    def test_add_rule(self, client):
        r = client.post("/api/v1/routing/rules", json={
            "name": "ADT to LIS",
            "conditions": [{"field": "MSH-9.1", "operator": "equals", "value": "ADT"}],
            "destinations": [{"name": "LIS", "adapter_name": "MLLP_LIS"}],
            "priority": 10,
        })
        assert r.status_code == 201
        assert r.json()["rule_count"] == 1

    def test_routing_test(self, client):
        client.post("/api/v1/routing/rules", json={
            "name": "ADT test",
            "conditions": [{"field": "MSH-9.1", "operator": "equals", "value": "ADT"}],
            "destinations": [{"name": "LIS", "adapter_name": "MLLP_LIS"}],
        })
        r = client.post("/api/v1/routing/test", json={"message": ADT_A08})
        assert r.status_code == 200
        data = r.json()
        assert data["message_type"] == "ADT^A08"
        assert "LIS" in data["destinations"]

    def test_routing_test_invalid_message(self, client):
        r = client.post("/api/v1/routing/test", json={"message": "BAD"})
        assert r.status_code == 400

    def test_delete_rule(self, client):
        client.post("/api/v1/routing/rules", json={
            "name": "to_delete",
            "conditions": [{"field": "MSH-9.1", "operator": "equals", "value": "SIU"}],
            "destinations": [{"name": "X", "adapter_name": "Y"}],
        })
        r = client.delete("/api/v1/routing/rules/to_delete")
        assert r.status_code == 200


class TestTransformEndpoints:

    def test_list_empty(self, client):
        r = client.get("/api/v1/transforms")
        assert r.status_code == 200

    def test_create_transform(self, client):
        r = client.post("/api/v1/transforms", json={
            "name": "passthrough",
            "source_code": "def transform(msg, lookup):\n    return msg.clone()",
            "flow_id": str(uuid.uuid4()),
        })
        assert r.status_code == 201
        assert r.json()["name"] == "passthrough"

    def test_create_invalid_transform(self, client):
        r = client.post("/api/v1/transforms", json={
            "name": "bad",
            "source_code": "import os\ndef transform(msg, lookup): return msg",
            "flow_id": str(uuid.uuid4()),
        })
        assert r.status_code == 400

    def test_test_transform(self, client):
        client.post("/api/v1/transforms", json={
            "name": "test_xform",
            "source_code": "def transform(msg, lookup):\n    msg = msg.clone()\n    msg.set('MSH-5', 'TESTED')\n    return msg",
            "flow_id": str(uuid.uuid4()),
        })
        r = client.post("/api/v1/transforms/test_xform/test", json={"message": ADT_A08})
        assert r.status_code == 200
        assert r.json()["status"] == "success"
        assert "TESTED" in r.json()["output_er7"]


class TestAgentEndpoints:

    def test_agent_status(self, client):
        r = client.get("/api/v1/agents/status")
        assert r.status_code == 200
        assert "agents" in r.json()

    def test_anomalies_empty(self, client):
        r = client.get("/api/v1/agents/anomalies")
        assert r.status_code == 200
        assert r.json()["anomalies"] == []

    def test_chat_no_agent(self, client):
        r = client.post("/api/v1/agents/chat", json={"message": "hello"})
        assert r.status_code == 503
