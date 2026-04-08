"""Endpoints para mensajes — parse, búsqueda, trace."""

from fastapi import APIRouter, HTTPException

from ..schemas import MessageParseRequest, MessageParseResponse
from ...core.hl7.parser import HL7Message

router = APIRouter(prefix="/messages", tags=["messages"])


@router.post("/parse", response_model=MessageParseResponse)
async def parse_message(body: MessageParseRequest):
    """Parsear un mensaje HL7 para inspección."""
    try:
        msg = HL7Message.parse(body.message)
    except Exception as e:
        raise HTTPException(400, f"Invalid HL7 message: {e}")

    return MessageParseResponse(
        message_type=msg.message_type,
        trigger_event=msg.trigger_event,
        message_id=msg.message_control_id,
        sending_app=msg.sending_application,
        sending_facility=msg.sending_facility,
        version=msg.version,
        segment_count=len(msg.segments),
        segments=[
            {"name": seg.name, "fields": seg.field_count}
            for seg in msg.segments
        ],
    )
