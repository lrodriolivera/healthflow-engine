"""
Pydantic v2 schemas para la API REST de HealthFlow Engine.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# --- Pagination ---

class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int = 1
    page_size: int = 20


# --- Flows ---

class FlowCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    tenant_id: uuid.UUID
    config: Optional[dict[str, Any]] = None


class FlowUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    config: Optional[dict[str, Any]] = None


class FlowResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: Optional[str] = None
    is_active: bool = True
    config: Optional[dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# --- Adapters ---

class AdapterCreate(BaseModel):
    name: str = Field(..., max_length=255)
    adapter_type: str  # mllp_in, mllp_out, soap_in, etc.
    config: Optional[dict[str, Any]] = None
    port: Optional[int] = None
    host: Optional[str] = None


class AdapterResponse(BaseModel):
    id: uuid.UUID
    flow_id: uuid.UUID
    name: str
    adapter_type: str
    is_active: bool = True
    config: Optional[dict[str, Any]] = None
    port: Optional[int] = None
    host: Optional[str] = None


# --- Routing Rules ---

class RoutingConditionSchema(BaseModel):
    field: str
    operator: str
    value: str
    case_sensitive: bool = True


class RoutingDestinationSchema(BaseModel):
    name: str
    adapter_name: str
    transform: Optional[str] = None


class RoutingRuleCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    priority: int = 100
    conditions: list[RoutingConditionSchema]
    destinations: list[RoutingDestinationSchema]
    stop_on_match: bool = False


class RoutingRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[int] = None
    conditions: Optional[list[RoutingConditionSchema]] = None
    destinations: Optional[list[RoutingDestinationSchema]] = None
    stop_on_match: Optional[bool] = None
    is_active: Optional[bool] = None


class RoutingRuleResponse(BaseModel):
    id: uuid.UUID
    flow_id: uuid.UUID
    name: str
    description: Optional[str] = None
    priority: int
    conditions: list[dict[str, Any]]
    destinations: list[dict[str, Any]]
    stop_on_match: bool
    is_active: bool
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None


class RoutingTestRequest(BaseModel):
    message: str  # Raw HL7 message


class RoutingTestResponse(BaseModel):
    message_type: str
    trigger_event: str
    matched_rules: list[str]
    destinations: list[str]


# --- Transforms ---

class TransformCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    source_code: str
    flow_id: uuid.UUID


class TransformDesignRequest(BaseModel):
    spec: str  # Natural language specification
    sample_messages: list[str]  # HL7 messages for validation
    flow_id: uuid.UUID


class TransformTestRequest(BaseModel):
    message: str  # Raw HL7 message


class TransformResponse(BaseModel):
    id: uuid.UUID
    flow_id: uuid.UUID
    name: str
    description: Optional[str] = None
    version: int
    source_code: str
    is_active: bool
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None


class TransformDesignResponse(BaseModel):
    source_code: str
    validated: bool
    test_results: list[dict[str, Any]]


# --- Messages ---

class MessageLogResponse(BaseModel):
    id: int
    timestamp: Optional[datetime] = None
    flow_id: Optional[uuid.UUID] = None
    message_type: Optional[str] = None
    trigger_event: Optional[str] = None
    message_control_id: Optional[str] = None
    sending_app: Optional[str] = None
    status: str
    processing_time_ms: Optional[float] = None
    trace_id: Optional[str] = None


class MessageParseRequest(BaseModel):
    message: str


class MessageParseResponse(BaseModel):
    message_type: str
    trigger_event: str
    message_id: str
    sending_app: str
    sending_facility: str
    version: str
    segment_count: int
    segments: list[dict[str, Any]]


# --- Agents ---

class ChatRequest(BaseModel):
    message: str
    context: Optional[dict[str, Any]] = None


class ChatResponse(BaseModel):
    response: str
    agent: str = "ops_agent"


class HealRequest(BaseModel):
    error_id: str


class HealResponse(BaseModel):
    diagnosis: str
    severity: str
    category: str
    fix: dict[str, Any]


class ErrorQueueResponse(BaseModel):
    id: uuid.UUID
    error_type: str
    error_detail: Optional[str] = None
    flow_id: Optional[uuid.UUID] = None
    retry_count: int
    timestamp: Optional[datetime] = None


# --- Lookups ---

class LookupTableCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    tenant_id: uuid.UUID


class LookupTableResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: Optional[str] = None
    is_active: bool


class LookupEntryCreate(BaseModel):
    key: str
    value: str


class LookupEntryResponse(BaseModel):
    id: uuid.UUID
    key: str
    value: str
    is_active: bool


# --- Health ---

class HealthResponse(BaseModel):
    status: str
    engine: str = "healthflow"
    version: str
    nats: bool = False
    redis: bool = False
    database: bool = False
    agents: list[str] = []
