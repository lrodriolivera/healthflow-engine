"""
FHIR R4 RESTful API endpoints.

Expone los endpoints FHIR estándar:
  GET /fhir/Patient, POST /fhir/Patient, GET /fhir/Patient/{id}
  POST /fhir/$convert — convierte HL7 v2 a FHIR Bundle
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..hl7.parser import HL7Message
from .mapper import hl7_to_fhir
from .resources import Bundle
from .subscriptions import (
    Subscription, SubscriptionFilter, SubscriptionChannel,
    SubscriptionChannelType, SubscriptionManager,
)

router = APIRouter(prefix="/fhir", tags=["fhir"])

# In-memory stores (for MVP, replace with DB later)
_resources: dict[str, dict[str, dict]] = {}  # resourceType -> {id -> resource}
_subscription_manager = SubscriptionManager()


class ConvertRequest(BaseModel):
    message: str  # Raw HL7 v2 message


@router.post("/$convert", response_model=dict)
async def convert_v2_to_fhir(body: ConvertRequest):
    """Convertir mensaje HL7 v2.x a FHIR R4 Bundle."""
    try:
        msg = HL7Message.parse(body.message)
    except Exception as e:
        raise HTTPException(400, f"Invalid HL7 message: {e}")

    bundle = hl7_to_fhir(msg)
    return bundle.model_dump(exclude_none=True)


@router.get("/{resource_type}")
async def search(resource_type: str):
    """FHIR Search — list resources of a type."""
    resources = _resources.get(resource_type, {})
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(resources),
        "entry": [
            {"resource": r} for r in resources.values()
        ],
    }


@router.get("/{resource_type}/{resource_id}")
async def read(resource_type: str, resource_id: str):
    """FHIR Read — get a specific resource."""
    resources = _resources.get(resource_type, {})
    resource = resources.get(resource_id)
    if not resource:
        raise HTTPException(404, f"{resource_type}/{resource_id} not found")
    return resource


@router.post("/{resource_type}")
async def create(resource_type: str, body: dict):
    """FHIR Create — store a resource."""
    import uuid
    resource_id = body.get("id", str(uuid.uuid4()))
    body["id"] = resource_id
    body["resourceType"] = resource_type

    if resource_type not in _resources:
        _resources[resource_type] = {}
    _resources[resource_type][resource_id] = body

    return body


@router.put("/{resource_type}/{resource_id}")
async def update(resource_type: str, resource_id: str, body: dict):
    """FHIR Update — replace a resource."""
    body["id"] = resource_id
    body["resourceType"] = resource_type

    if resource_type not in _resources:
        _resources[resource_type] = {}
    _resources[resource_type][resource_id] = body

    return body


@router.delete("/{resource_type}/{resource_id}", status_code=204)
async def delete(resource_type: str, resource_id: str):
    """FHIR Delete — remove a resource."""
    resources = _resources.get(resource_type, {})
    if resource_id not in resources:
        raise HTTPException(404, f"{resource_type}/{resource_id} not found")
    del resources[resource_id]


# --- Subscriptions ---

class SubscriptionCreateRequest(BaseModel):
    topic: str  # e.g., "create", "update", "*"
    resource_type: str  # e.g., "Patient"
    endpoint: str  # Webhook URL
    headers: dict = {}


@router.post("/Subscription", status_code=201)
async def create_subscription(body: SubscriptionCreateRequest):
    """Create a FHIR Subscription (R5-style topic-based)."""
    sub = Subscription(
        topic=body.topic,
        filter=SubscriptionFilter(resource_type=body.resource_type),
        channel=SubscriptionChannel(
            type=SubscriptionChannelType.rest_hook,
            endpoint=body.endpoint,
            headers=body.headers,
        ),
    )
    _subscription_manager.add(sub)
    return {"id": sub.id, "status": sub.status.value, "topic": sub.topic}


@router.get("/Subscription")
async def list_subscriptions():
    """List all active FHIR Subscriptions."""
    return [
        {
            "id": s.id,
            "status": s.status.value,
            "topic": s.topic,
            "resource_type": s.filter.resource_type if s.filter else "*",
            "endpoint": s.channel.endpoint if s.channel else "",
        }
        for s in _subscription_manager.list_all()
    ]


@router.delete("/Subscription/{sub_id}", status_code=204)
async def delete_subscription(sub_id: str):
    """Delete a FHIR Subscription."""
    if not _subscription_manager.remove(sub_id):
        raise HTTPException(404, "Subscription not found")
