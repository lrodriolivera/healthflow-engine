"""
Generador de ACK/NAK HL7 v2.x.

Patrones de ACK:
- AA (Application Accept): mensaje procesado OK
- AE (Application Error): error de negocio
- AR (Application Reject): error técnico / mensaje malformado
"""

from datetime import datetime

from .parser import HL7Message


def generate_ack(
    original: HL7Message,
    ack_code: str = "AA",
    error_message: str = "",
    application: str = "HEALTHFLOW",
    facility: str = "HF",
) -> str:
    """Generar ACK para un mensaje HL7.

    Args:
        original: Mensaje original al que se responde.
        ack_code: AA (accept), AE (error), AR (reject).
        error_message: Texto de error (para AE/AR).
        application: MSH.3 del ACK.
        facility: MSH.4 del ACK.

    Returns:
        ACK como string ER7.
    """
    now = datetime.now().strftime("%Y%m%d%H%M%S")
    original_msg_id = original.message_control_id
    original_msg_type = original.message_type
    version = original.version or "2.5"

    # MSH: swap sending/receiving
    msh = (
        f"MSH|^~\\&|{application}|{facility}"
        f"|{original.sending_application}|{original.sending_facility}"
        f"|{now}||ACK^{original.trigger_event}|ACK{now}|P|{version}"
    )

    # MSA: acknowledgment
    msa = f"MSA|{ack_code}|{original_msg_id}"
    if error_message:
        msa += f"|{error_message}"

    # ERR segment for errors
    segments = [msh, msa]
    if ack_code in ("AE", "AR") and error_message:
        err = f"ERR|||207^Application internal error^HL70357|E||||{error_message}"
        segments.append(err)

    return "\r".join(segments)


def generate_simple_ack(message_control_id: str, ack_code: str = "AA") -> str:
    """ACK mínimo cuando no se tiene el mensaje completo parseado."""
    now = datetime.now().strftime("%Y%m%d%H%M%S")
    return (
        f"MSH|^~\\&|HEALTHFLOW|HF|||{now}||ACK|ACK{now}|P|2.5\r"
        f"MSA|{ack_code}|{message_control_id}"
    )
