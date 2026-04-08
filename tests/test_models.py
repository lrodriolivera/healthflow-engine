"""Tests para los modelos SQLAlchemy."""

import uuid
import pytest

from backend.app.models import (
    Base,
    Tenant,
    Flow,
    Adapter,
    AdapterType,
    RoutingRuleModel,
    Transform,
    LookupTable,
    LookupEntry,
    AuditLog,
    MessageLog,
    MessageStatus,
    ErrorQueue,
    Credential,
    CredentialType,
)


class TestModelInstantiation:
    """Verificar que los modelos se instancian correctamente."""

    def test_tenant(self):
        t = Tenant(
            id=uuid.uuid4(),
            name="UC CHRISTUS",
            slug="ucchristus",
            is_active=True,
            settings={"region": "CL"},
        )
        assert t.name == "UC CHRISTUS"
        assert t.slug == "ucchristus"
        assert t.settings["region"] == "CL"

    def test_flow(self):
        f = Flow(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            name="ADT Flow",
            is_active=True,
            config={"description": "ADT messages from SAP"},
        )
        assert f.name == "ADT Flow"
        assert f.config["description"] == "ADT messages from SAP"

    def test_adapter_types(self):
        assert AdapterType.mllp_in == "mllp_in"
        assert AdapterType.mllp_out == "mllp_out"
        assert AdapterType.soap_in == "soap_in"
        assert AdapterType.rest_out == "rest_out"

    def test_adapter(self):
        a = Adapter(
            id=uuid.uuid4(),
            flow_id=uuid.uuid4(),
            name="MLLP_IN_2575",
            adapter_type=AdapterType.mllp_in,
            port=2575,
            config={"ack_mode": "immediate"},
        )
        assert a.adapter_type == AdapterType.mllp_in
        assert a.port == 2575

    def test_routing_rule_model(self):
        r = RoutingRuleModel(
            id=uuid.uuid4(),
            flow_id=uuid.uuid4(),
            name="ADT to LIS",
            priority=10,
            conditions=[{"field": "MSH-9.1", "operator": "equals", "value": "ADT"}],
            destinations=[{"name": "LIS", "adapter_name": "MLLP_LIS"}],
            created_by="human",
        )
        assert r.priority == 10
        assert r.conditions[0]["field"] == "MSH-9.1"

    def test_transform(self):
        t = Transform(
            id=uuid.uuid4(),
            flow_id=uuid.uuid4(),
            name="ADT remap",
            version=1,
            source_code="def transform(msg, lookup): return msg",
            created_by="transform_designer",
        )
        assert "def transform" in t.source_code

    def test_lookup_table_and_entry(self):
        table = LookupTable(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            name="procedure_codes",
        )
        entry = LookupEntry(
            id=uuid.uuid4(),
            table_id=table.id,
            key="PREST001",
            value="Radiografía Tórax",
        )
        assert table.name == "procedure_codes"
        assert entry.key == "PREST001"

    def test_message_status_enum(self):
        assert MessageStatus.received == "received"
        assert MessageStatus.routed == "routed"
        assert MessageStatus.error == "error"
        assert MessageStatus.dlq == "dlq"

    def test_message_log(self):
        m = MessageLog(
            id=1,
            message_type="ADT",
            trigger_event="A08",
            message_control_id="MSG001",
            sending_app="SAP",
            status=MessageStatus.received,
            raw_size=512,
        )
        assert m.message_type == "ADT"
        assert m.status == MessageStatus.received

    def test_error_queue(self):
        e = ErrorQueue(
            id=uuid.uuid4(),
            error_type="parse_error",
            error_detail="Invalid MSH segment",
            retry_count=0,
            max_retries=3,
        )
        assert e.error_type == "parse_error"
        assert e.retry_count == 0

    def test_credential_types(self):
        assert CredentialType.basic == "basic"
        assert CredentialType.aws == "aws"
        assert CredentialType.api_key == "api_key"

    def test_credential(self):
        c = Credential(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            name="SAP Auth",
            credential_type=CredentialType.basic,
            encrypted_value=b"encrypted_data",
        )
        assert c.name == "SAP Auth"
        assert c.credential_type == CredentialType.basic


class TestBaseMetadata:
    """Verificar que todos los modelos están registrados en Base.metadata."""

    def test_all_tables_registered(self):
        table_names = set(Base.metadata.tables.keys())
        expected = {
            "tenants", "flows", "adapters", "routing_rules", "transforms",
            "lookup_tables", "lookup_entries", "audit_log", "message_log",
            "error_queue", "credentials",
        }
        assert expected.issubset(table_names), f"Missing tables: {expected - table_names}"

    def test_table_count(self):
        assert len(Base.metadata.tables) >= 11
