"""Endpoints para routing rules + test de routing."""

from fastapi import APIRouter, HTTPException, Request

from ..schemas import (
    RoutingRuleCreate,
    RoutingRuleResponse,
    RoutingTestRequest,
    RoutingTestResponse,
)
from ...core.hl7.parser import HL7Message
from ...core.routing.engine import RoutingCondition, RoutingDestination, RoutingRule

router = APIRouter(prefix="/routing", tags=["routing"])


@router.post("/test", response_model=RoutingTestResponse)
async def test_routing(body: RoutingTestRequest, request: Request):
    """Evaluar reglas de routing contra un mensaje HL7."""
    try:
        msg = HL7Message.parse(body.message)
    except Exception as e:
        raise HTTPException(400, f"Invalid HL7 message: {e}")

    routing_engine = request.app.state.routing_engine
    destinations = routing_engine.evaluate(msg)

    # Find which rules matched
    matched_rules = []
    for rule in routing_engine.get_rules():
        if all(cond.evaluate(msg) for cond in rule.conditions):
            matched_rules.append(rule.name)

    return RoutingTestResponse(
        message_type=msg.message_type,
        trigger_event=msg.trigger_event,
        matched_rules=matched_rules,
        destinations=[d.name for d in destinations],
    )


@router.get("/rules", response_model=list[dict])
async def list_rules(request: Request):
    """Listar reglas del routing engine en memoria."""
    engine = request.app.state.routing_engine
    return [
        {
            "name": r.name,
            "priority": r.priority,
            "enabled": r.enabled,
            "stop_on_match": r.stop_on_match,
            "conditions": [
                {"field": c.field, "operator": c.operator, "value": c.value}
                for c in r.conditions
            ],
            "destinations": [
                {"name": d.name, "adapter_name": d.adapter_name, "transform": d.transform}
                for d in r.destinations
            ],
        }
        for r in engine.get_rules()
    ]


@router.post("/rules", status_code=201)
async def add_rule(body: RoutingRuleCreate, request: Request):
    """Agregar regla al routing engine en memoria."""
    engine = request.app.state.routing_engine
    rule = RoutingRule(
        name=body.name,
        priority=body.priority,
        stop_on_match=body.stop_on_match,
        conditions=[
            RoutingCondition(
                field=c.field,
                operator=c.operator,
                value=c.value,
                case_sensitive=c.case_sensitive,
            )
            for c in body.conditions
        ],
        destinations=[
            RoutingDestination(
                name=d.name,
                adapter_name=d.adapter_name,
                transform=d.transform,
            )
            for d in body.destinations
        ],
    )
    engine.add_rule(rule)
    return {"status": "created", "name": body.name, "rule_count": engine.rule_count}


@router.delete("/rules/{rule_name}")
async def remove_rule(rule_name: str, request: Request):
    """Eliminar regla por nombre."""
    engine = request.app.state.routing_engine
    if not engine.remove_rule(rule_name):
        raise HTTPException(404, f"Rule not found: {rule_name}")
    return {"status": "deleted", "name": rule_name}
