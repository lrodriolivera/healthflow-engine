"""
HL7 v2 → FHIR R4 mapper.

Mapea mensajes HL7 v2.x a recursos FHIR R4 siguiendo el
HL7 v2-to-FHIR Implementation Guide.

Soporta:
  - ADT → Patient + Encounter
  - ORM/OML → ServiceRequest
  - ORU → DiagnosticReport + Observation
"""

from __future__ import annotations

from typing import Optional
import uuid

from ..hl7.parser import HL7Message
from .resources import (
    Patient, Encounter, Observation, DiagnosticReport, ServiceRequest,
    Bundle, BundleEntry,
    HumanName, Identifier, Address, ContactPoint, Coding, CodeableConcept,
    Reference, Period,
)


def hl7_to_fhir(message: HL7Message) -> Bundle:
    """Convertir mensaje HL7 v2.x a FHIR Bundle.

    Dispatch por tipo de mensaje (MSH-9.1).
    """
    msg_type = message.message_type_code

    if msg_type == "ADT":
        return _map_adt(message)
    elif msg_type in ("ORM", "OML"):
        return _map_order(message)
    elif msg_type in ("ORU", "OUL"):
        return _map_result(message)
    else:
        # Generic: extract Patient only
        return _map_generic(message)


def _map_adt(msg: HL7Message) -> Bundle:
    """ADT → Patient + Encounter."""
    patient = _extract_patient(msg)
    encounter = _extract_encounter(msg, patient)

    entries = [
        BundleEntry(
            fullUrl=f"urn:uuid:{patient.id}",
            resource=patient.model_dump(by_alias=True, exclude_none=True),
        ),
        BundleEntry(
            fullUrl=f"urn:uuid:{encounter.id}",
            resource=encounter.model_dump(by_alias=True, exclude_none=True),
        ),
    ]
    return Bundle(type="transaction", entry=entries)


def _map_order(msg: HL7Message) -> Bundle:
    """ORM/OML → Patient + ServiceRequest(s)."""
    patient = _extract_patient(msg)
    entries = [
        BundleEntry(
            fullUrl=f"urn:uuid:{patient.id}",
            resource=patient.model_dump(by_alias=True, exclude_none=True),
        ),
    ]

    # One ServiceRequest per OBR
    obr_count = msg.count_segments("OBR")
    for i in range(obr_count):
        sr = _extract_service_request(msg, patient, i)
        entries.append(BundleEntry(
            fullUrl=f"urn:uuid:{sr.id}",
            resource=sr.model_dump(by_alias=True, exclude_none=True),
        ))

    return Bundle(type="transaction", entry=entries)


def _map_result(msg: HL7Message) -> Bundle:
    """ORU → Patient + DiagnosticReport + Observation(s)."""
    patient = _extract_patient(msg)
    entries = [
        BundleEntry(
            fullUrl=f"urn:uuid:{patient.id}",
            resource=patient.model_dump(by_alias=True, exclude_none=True),
        ),
    ]

    # One DiagnosticReport per OBR, Observations per OBX
    obr_count = msg.count_segments("OBR")
    for i in range(obr_count):
        obr = msg.get_segment("OBR", i)
        if not obr:
            continue

        report_id = str(uuid.uuid4())
        obs_refs = []

        # Find OBX segments belonging to this OBR
        obx_segments = msg.get_all_segments("OBX")
        for obx in obx_segments:
            obs = _extract_observation(obx, patient)
            obs_refs.append(Reference(reference=f"urn:uuid:{obs.id}"))
            entries.append(BundleEntry(
                fullUrl=f"urn:uuid:{obs.id}",
                resource=obs.model_dump(by_alias=True, exclude_none=True),
            ))

        report = DiagnosticReport(
            id=report_id,
            status="final",
            code=CodeableConcept(
                coding=[Coding(code=obr.get_component(4, 1), display=obr.get_component(4, 2))],
            ),
            subject=Reference(reference=f"urn:uuid:{patient.id}"),
            result=obs_refs,
        )
        entries.append(BundleEntry(
            fullUrl=f"urn:uuid:{report_id}",
            resource=report.model_dump(by_alias=True, exclude_none=True),
        ))

    return Bundle(type="transaction", entry=entries)


def _map_generic(msg: HL7Message) -> Bundle:
    """Generic mapping — Patient only."""
    patient = _extract_patient(msg)
    return Bundle(type="collection", entry=[
        BundleEntry(
            fullUrl=f"urn:uuid:{patient.id}",
            resource=patient.model_dump(by_alias=True, exclude_none=True),
        ),
    ])


# --- Extraction helpers ---

def _extract_patient(msg: HL7Message) -> Patient:
    """PID → Patient resource."""
    patient_id = str(uuid.uuid4())

    # Identifiers from PID-3 (repeating)
    identifiers = []
    pid = msg.get_segment("PID")
    if pid:
        pid3 = pid.get_field(3)
        for rep in pid3.split("~"):
            parts = rep.split("^")
            if parts:
                id_value = parts[0]
                id_type = parts[4] if len(parts) > 4 else ""
                identifiers.append(Identifier(
                    value=id_value,
                    type=CodeableConcept(coding=[Coding(code=id_type)]) if id_type else None,
                ))

    # Name from PID-5
    names = []
    pid5 = msg.get("PID-5")
    if pid5:
        parts = pid5.split("^")
        names.append(HumanName(
            family=parts[0] if parts else None,
            given=[parts[1]] if len(parts) > 1 and parts[1] else [],
        ))

    # Gender from PID-8
    gender_map = {"F": "female", "M": "male", "O": "other", "U": "unknown"}
    gender = gender_map.get(msg.get("PID-8"), None)

    # Birth date from PID-7
    birth_date = msg.get("PID-7")
    if birth_date and len(birth_date) >= 8:
        birth_date = f"{birth_date[:4]}-{birth_date[4:6]}-{birth_date[6:8]}"

    # Address from PID-11
    addresses = []
    pid11 = msg.get("PID-11")
    if pid11:
        parts = pid11.split("^")
        addresses.append(Address(
            line=[parts[0]] if parts[0] else [],
            city=parts[2] if len(parts) > 2 else None,
            state=parts[3] if len(parts) > 3 else None,
            postalCode=parts[4] if len(parts) > 4 else None,
            country=parts[5] if len(parts) > 5 else None,
        ))

    # Telecom from PID-13
    telecom = []
    pid13 = msg.get("PID-13")
    if pid13:
        telecom.append(ContactPoint(system="phone", value=pid13, use="home"))

    return Patient(
        id=patient_id,
        identifier=identifiers,
        name=names,
        gender=gender,
        birthDate=birth_date or None,
        address=addresses,
        telecom=telecom,
    )


def _extract_encounter(msg: HL7Message, patient: Patient) -> Encounter:
    """PV1 → Encounter resource."""
    encounter_id = str(uuid.uuid4())

    # Patient class from PV1-2
    class_map = {
        "I": Coding(system="http://terminology.hl7.org/CodeSystem/v3-ActCode", code="IMP", display="inpatient"),
        "O": Coding(system="http://terminology.hl7.org/CodeSystem/v3-ActCode", code="AMB", display="ambulatory"),
        "E": Coding(system="http://terminology.hl7.org/CodeSystem/v3-ActCode", code="EMER", display="emergency"),
    }
    pv1_class = msg.get("PV1-2")
    encounter_class = class_map.get(pv1_class)

    # Location from PV1-3
    location = []
    pv1_3 = msg.get("PV1-3")
    if pv1_3:
        location.append({
            "location": {"display": pv1_3.split("^")[0] if "^" in pv1_3 else pv1_3},
        })

    return Encounter(
        id=encounter_id,
        status="in-progress",
        **{"class": encounter_class} if encounter_class else {},
        subject=Reference(reference=f"urn:uuid:{patient.id}"),
        location=location,
    )


def _extract_service_request(msg: HL7Message, patient: Patient, obr_index: int) -> ServiceRequest:
    """OBR → ServiceRequest."""
    sr_id = str(uuid.uuid4())
    obr = msg.get_segment("OBR", obr_index)

    code = None
    if obr:
        obr4_code = obr.get_component(4, 1)
        obr4_display = obr.get_component(4, 2)
        if obr4_code:
            code = CodeableConcept(
                coding=[Coding(code=obr4_code, display=obr4_display)],
            )

    return ServiceRequest(
        id=sr_id,
        status="active",
        intent="order",
        code=code,
        subject=Reference(reference=f"urn:uuid:{patient.id}"),
    )


def _extract_observation(obx_segment, patient: Patient) -> Observation:
    """OBX → Observation."""
    obs_id = str(uuid.uuid4())

    code = None
    obx3_code = obx_segment.get_component(3, 1)
    obx3_display = obx_segment.get_component(3, 2)
    if obx3_code:
        code = CodeableConcept(
            coding=[Coding(code=obx3_code, display=obx3_display)],
        )

    # Value from OBX-5
    value = obx_segment.get_field(5)

    return Observation(
        id=obs_id,
        status="final",
        code=code,
        subject=Reference(reference=f"urn:uuid:{patient.id}"),
        valueString=value or None,
    )
