"""Initial schema — all tables + TimescaleDB hypertables.

Revision ID: 001
Revises: None
Create Date: 2026-04-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Tenants ---
    op.create_table(
        "tenants",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), unique=True, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("settings", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"])

    # --- Flows ---
    op.create_table(
        "flows",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("config", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_flows_tenant_id", "flows", ["tenant_id"])

    # --- Adapters ---
    adapter_type_enum = sa.Enum(
        "mllp_in", "mllp_out", "soap_in", "soap_out", "rest_in", "rest_out",
        "fhir_in", "fhir_out", "file_in", "file_out",
        name="adapter_type_enum",
    )
    op.create_table(
        "adapters",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("flow_id", UUID(as_uuid=True), sa.ForeignKey("flows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("adapter_type", adapter_type_enum, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("config", JSONB, nullable=True),
        sa.Column("port", sa.Integer, nullable=True),
        sa.Column("host", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- Routing Rules ---
    op.create_table(
        "routing_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("flow_id", UUID(as_uuid=True), sa.ForeignKey("flows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("priority", sa.Integer, nullable=False, server_default="100"),
        sa.Column("conditions", JSONB, nullable=False),
        sa.Column("destinations", JSONB, nullable=False),
        sa.Column("stop_on_match", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- Transforms ---
    op.create_table(
        "transforms",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("flow_id", UUID(as_uuid=True), sa.ForeignKey("flows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("source_code", sa.Text, nullable=False),
        sa.Column("input_spec", JSONB, nullable=True),
        sa.Column("output_spec", JSONB, nullable=True),
        sa.Column("test_messages", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- Lookup Tables ---
    op.create_table(
        "lookup_tables",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_lookup_tables_tenant_id", "lookup_tables", ["tenant_id"])
    op.create_index("ix_lookup_tables_name", "lookup_tables", ["name"])

    # --- Lookup Entries ---
    op.create_table(
        "lookup_entries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("table_id", UUID(as_uuid=True), sa.ForeignKey("lookup_tables.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(500), nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_lookup_entries_key", "lookup_entries", ["key"])

    # --- Credentials ---
    credential_type_enum = sa.Enum(
        "basic", "token", "certificate", "aws", "api_key",
        name="credential_type_enum",
    )
    op.create_table(
        "credentials",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("credential_type", credential_type_enum, nullable=False),
        sa.Column("encrypted_value", sa.LargeBinary, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_credentials_tenant_id", "credentials", ["tenant_id"])

    # --- Audit Log (TimescaleDB hypertable) ---
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("actor", sa.String(255), nullable=True),
        sa.Column("resource_type", sa.String(100), nullable=True),
        sa.Column("resource_id", sa.String(255), nullable=True),
        sa.Column("details", JSONB, nullable=True),
        sa.Column("trace_id", sa.String(64), nullable=True),
    )
    op.create_index("ix_audit_log_tenant_id", "audit_log", ["tenant_id"])
    op.create_index("ix_audit_log_timestamp", "audit_log", ["timestamp"])
    op.create_index("ix_audit_log_event_type", "audit_log", ["event_type"])

    # --- Message Log (TimescaleDB hypertable) ---
    message_status_enum = sa.Enum(
        "received", "routed", "transformed", "sent", "acked", "error", "dlq",
        name="message_status_enum",
    )
    op.create_table(
        "message_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("flow_id", UUID(as_uuid=True), nullable=True),
        sa.Column("message_type", sa.String(50), nullable=True),
        sa.Column("trigger_event", sa.String(10), nullable=True),
        sa.Column("message_control_id", sa.String(255), nullable=True),
        sa.Column("sending_app", sa.String(255), nullable=True),
        sa.Column("sending_facility", sa.String(255), nullable=True),
        sa.Column("receiving_app", sa.String(255), nullable=True),
        sa.Column("receiving_facility", sa.String(255), nullable=True),
        sa.Column("status", message_status_enum, nullable=False),
        sa.Column("raw_size", sa.Integer, nullable=True),
        sa.Column("processing_time_ms", sa.Float, nullable=True),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.Column("destinations", JSONB, nullable=True),
    )
    op.create_index("ix_message_log_tenant_id", "message_log", ["tenant_id"])
    op.create_index("ix_message_log_timestamp", "message_log", ["timestamp"])
    op.create_index("ix_message_log_flow_id", "message_log", ["flow_id"])
    op.create_index("ix_message_log_message_type", "message_log", ["message_type"])
    op.create_index("ix_message_log_message_control_id", "message_log", ["message_control_id"])
    op.create_index("ix_message_log_status", "message_log", ["status"])

    # --- Error Queue ---
    op.create_table(
        "error_queue",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=True),
        sa.Column("flow_id", UUID(as_uuid=True), nullable=True),
        sa.Column("message_log_id", sa.BigInteger, nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("error_type", sa.String(100), nullable=False),
        sa.Column("error_detail", sa.Text, nullable=True),
        sa.Column("raw_message", sa.Text, nullable=True),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer, nullable=False, server_default="3"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(100), nullable=True),
        sa.Column("diagnosis", JSONB, nullable=True),
    )

    # --- TimescaleDB hypertables ---
    # These will only work if TimescaleDB extension is installed
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")
    op.execute("SELECT create_hypertable('audit_log', 'timestamp', migrate_data => true)")
    op.execute("SELECT create_hypertable('message_log', 'timestamp', migrate_data => true)")


def downgrade() -> None:
    op.drop_table("error_queue")
    op.drop_table("message_log")
    op.drop_table("audit_log")
    op.drop_table("credentials")
    op.drop_table("lookup_entries")
    op.drop_table("lookup_tables")
    op.drop_table("transforms")
    op.drop_table("routing_rules")
    op.drop_table("adapters")
    op.drop_table("flows")
    op.drop_table("tenants")
    op.execute("DROP TYPE IF EXISTS adapter_type_enum")
    op.execute("DROP TYPE IF EXISTS credential_type_enum")
    op.execute("DROP TYPE IF EXISTS message_status_enum")
