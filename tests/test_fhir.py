"""Tests para FHIR R4 — mapper v2→FHIR y resources."""

import pytest

from backend.app.core.hl7.parser import HL7Message
from backend.app.core.fhir.mapper import hl7_to_fhir, _extract_patient
from backend.app.core.fhir.resources import Patient, Encounter, Bundle


ADT_A08 = (
    "MSH|^~\\&|SAP|UCCHRISTUS|IRIS|UCCHRISTUS|20260408120000||ADT^A08|MSG001|P|2.5\r"
    "EVN|A08|20260408120000\r"
    "PID|1||PAC123^^^MPI^MR~12345678-9^^^RUN^RUN||GONZALEZ^MARIA||19800115|F|||AV LIBERTADOR^^SANTIAGO^^8320000^CL||+56912345678\r"
    "PV1|1|I|SALA301^CAMA1"
)

OML_O21 = (
    "MSH|^~\\&|MODULAB|LAB|IRIS|UCCHRISTUS|20260408130000||OML^O21|MSG002|P|2.5\r"
    "PID|1||PAC456^^^MPI^MR||PEREZ^CARLOS||19750320|M\r"
    "ORC|NW|ORD001|SOL001||CM\r"
    "OBR|1|ORD001|SOL001|HEMO^Hemograma completo\r"
    "ORC|NW|ORD002|SOL002||CM\r"
    "OBR|2|ORD002|SOL002|GLUC^Glicemia"
)

ORU_R01 = (
    "MSH|^~\\&|MODULAB|LAB|IRIS|UCCHRISTUS|20260408140000||ORU^R01|MSG003|P|2.5\r"
    "PID|1||PAC456^^^MPI^MR||PEREZ^CARLOS||19750320|M\r"
    "OBR|1|ORD001|SOL001|HEMO^Hemograma\r"
    "OBX|1|NM|WBC^White Blood Cells||7500|/uL\r"
    "OBX|2|NM|RBC^Red Blood Cells||4800000|/uL"
)


class TestPatientMapping:

    def test_adt_to_patient(self):
        msg = HL7Message.parse(ADT_A08)
        patient = _extract_patient(msg)
        assert patient.resourceType == "Patient"
        assert patient.name[0].family == "GONZALEZ"
        assert patient.name[0].given == ["MARIA"]
        assert patient.gender == "female"
        assert patient.birthDate == "1980-01-15"

    def test_patient_identifiers(self):
        msg = HL7Message.parse(ADT_A08)
        patient = _extract_patient(msg)
        assert len(patient.identifier) == 2
        assert patient.identifier[0].value == "PAC123"
        assert patient.identifier[1].value == "12345678-9"

    def test_patient_address(self):
        msg = HL7Message.parse(ADT_A08)
        patient = _extract_patient(msg)
        assert len(patient.address) == 1
        assert patient.address[0].city == "SANTIAGO"
        assert patient.address[0].country == "CL"

    def test_patient_telecom(self):
        msg = HL7Message.parse(ADT_A08)
        patient = _extract_patient(msg)
        assert len(patient.telecom) == 1
        assert "+56912345678" in patient.telecom[0].value


class TestADTMapping:

    def test_adt_produces_bundle(self):
        msg = HL7Message.parse(ADT_A08)
        bundle = hl7_to_fhir(msg)
        assert isinstance(bundle, Bundle)
        assert bundle.type == "transaction"
        assert len(bundle.entry) == 2  # Patient + Encounter

    def test_adt_encounter(self):
        msg = HL7Message.parse(ADT_A08)
        bundle = hl7_to_fhir(msg)
        encounter_entry = bundle.entry[1].resource
        assert encounter_entry["resourceType"] == "Encounter"
        assert encounter_entry["status"] == "in-progress"


class TestOrderMapping:

    def test_oml_produces_bundle(self):
        msg = HL7Message.parse(OML_O21)
        bundle = hl7_to_fhir(msg)
        assert bundle.type == "transaction"
        # Patient + 2 ServiceRequests
        assert len(bundle.entry) == 3

    def test_oml_service_requests(self):
        msg = HL7Message.parse(OML_O21)
        bundle = hl7_to_fhir(msg)
        sr1 = bundle.entry[1].resource
        sr2 = bundle.entry[2].resource
        assert sr1["resourceType"] == "ServiceRequest"
        assert sr1["code"]["coding"][0]["code"] == "HEMO"
        assert sr2["code"]["coding"][0]["code"] == "GLUC"


class TestResultMapping:

    def test_oru_produces_bundle(self):
        msg = HL7Message.parse(ORU_R01)
        bundle = hl7_to_fhir(msg)
        assert bundle.type == "transaction"
        # Patient + 2 Observations + 1 DiagnosticReport
        assert len(bundle.entry) == 4

    def test_oru_observations(self):
        msg = HL7Message.parse(ORU_R01)
        bundle = hl7_to_fhir(msg)
        obs_entries = [
            e for e in bundle.entry
            if e.resource and e.resource.get("resourceType") == "Observation"
        ]
        assert len(obs_entries) == 2
        codes = {e.resource["code"]["coding"][0]["code"] for e in obs_entries}
        assert "WBC" in codes
        assert "RBC" in codes

    def test_oru_diagnostic_report(self):
        msg = HL7Message.parse(ORU_R01)
        bundle = hl7_to_fhir(msg)
        report_entries = [
            e for e in bundle.entry
            if e.resource and e.resource.get("resourceType") == "DiagnosticReport"
        ]
        assert len(report_entries) == 1
        report = report_entries[0].resource
        assert report["code"]["coding"][0]["code"] == "HEMO"
        assert len(report["result"]) == 2


class TestFHIRResources:

    def test_patient_model(self):
        p = Patient(
            id="test-1",
            name=[{"family": "Smith", "given": ["John"]}],
            gender="male",
            birthDate="1990-01-01",
        )
        data = p.model_dump(exclude_none=True)
        assert data["resourceType"] == "Patient"
        assert data["gender"] == "male"

    def test_bundle_model(self):
        b = Bundle(type="searchset", total=0, entry=[])
        data = b.model_dump(exclude_none=True)
        assert data["resourceType"] == "Bundle"
        assert data["type"] == "searchset"
