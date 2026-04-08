"""Tests para el parser HL7 v2.x."""

import pytest
from backend.app.core.hl7.parser import HL7Message, HL7Segment
from backend.app.core.hl7.ack import generate_ack


# Mensaje ADT^A08 real (basado en UC CHRISTUS)
ADT_A08 = (
    "MSH|^~\\&|SAP|UCCHRISTUS|IRIS|UCCHRISTUS|20260408120000||ADT^A08^ADT_A01|MSG001|P|2.5|||AL|NE\r"
    "EVN|A08|20260408120000\r"
    "PID|1||PAC123^^^MPI^MR~12345678-9^^^RUN^RUN||GONZALEZ^MARIA^TERESA||19800115|F|||AV LIBERTADOR 1234^^SANTIAGO^^8320000^CL||+56912345678\r"
    "PV1|1|I|SALA301^CAMA1^1^^^HOSP_CENTRAL||||MED001^DR.LOPEZ^JUAN^CARLOS^^^^MD\r"
    "PV2|||RAD^Radiología"
)

# Mensaje OML^O21 con múltiples OBR (multi-exam order)
OML_O21_MULTI = (
    "MSH|^~\\&|MODULAB|LAB|IRIS|UCCHRISTUS|20260408130000||OML^O21|MSG002|P|2.5\r"
    "PID|1||PAC456^^^MPI^MR||PEREZ^CARLOS||19750320|M\r"
    "PV1|1|O|CONSULTA1\r"
    "ORC|NW|ORD001|SOL001||CM\r"
    "OBR|1|ORD001|SOL001|HEMO^Hemograma completo\r"
    "ORC|NW|ORD002|SOL002||CM\r"
    "OBR|2|ORD002|SOL002|GLUC^Glicemia\r"
    "ORC|NW|ORD003|SOL003||CM\r"
    "OBR|3|ORD003|SOL003|CREA^Creatinina"
)

# DFT^P03 con FT1 y PR1 (cargo financiero, patrón UC CHRISTUS)
DFT_P03 = (
    "MSH|^~\\&|SAP|UCCHRISTUS|IRIS|UCCHRISTUS|20260408140000||DFT^P03|MSG003|P|2.5\r"
    "EVN|P03|20260408140000\r"
    "PID|1||PAC789^^^MPI^MR~98765432-1^^^RUN^RUN||SILVA^PEDRO||19901225|M\r"
    "PV1|1|O|CONSULTA2\r"
    "FT1|1|E12345|E12345.PREST001|20260408|20260408|CG||100.00|||1\r"
    "PR1|1||PREST001^Radiografía Tórax\r"
    "PR1|2||PREST002^Ecografía Abdominal"
)


class TestHL7Parser:
    """Tests del parser HL7."""

    def test_parse_adt_a08(self):
        msg = HL7Message.parse(ADT_A08)
        assert msg.message_type == "ADT^A08^ADT_A01"
        assert msg.message_type_code == "ADT"
        assert msg.trigger_event == "A08"
        assert msg.message_control_id == "MSG001"
        assert msg.version == "2.5"

    def test_parse_msh_fields(self):
        msg = HL7Message.parse(ADT_A08)
        assert msg.sending_application == "SAP"
        assert msg.sending_facility == "UCCHRISTUS"
        assert msg.receiving_application == "IRIS"

    def test_get_pid_fields(self):
        msg = HL7Message.parse(ADT_A08)
        # PID.3 full (first repetition)
        pid3 = msg.get("PID-3")
        assert "PAC123" in pid3
        # PID.3.1 (first component)
        assert msg.get("PID-3.1") == "PAC123"
        # PID.5.1 (family name)
        assert msg.get("PID-5.1") == "GONZALEZ"
        # PID.5.2 (given name)
        assert msg.get("PID-5.2") == "MARIA"
        # PID.7 (DOB)
        assert msg.get("PID-7") == "19800115"
        # PID.8 (sex)
        assert msg.get("PID-8") == "F"

    def test_get_pv1_fields(self):
        msg = HL7Message.parse(ADT_A08)
        # PV1.2 (patient class)
        assert msg.get("PV1-2") == "I"
        # PV1.3.1 (point of care)
        assert msg.get("PV1-3.1") == "SALA301"

    def test_get_pv2_fields(self):
        msg = HL7Message.parse(ADT_A08)
        assert msg.get("PV2-3.1") == "RAD"
        assert msg.get("PV2-3.2") == "Radiología"

    def test_missing_segment(self):
        msg = HL7Message.parse(ADT_A08)
        assert msg.get("ZPD-1") == ""  # Z-segment doesn't exist

    def test_missing_field(self):
        msg = HL7Message.parse(ADT_A08)
        assert msg.get("PID-99") == ""

    def test_multi_obr(self):
        msg = HL7Message.parse(OML_O21_MULTI)
        assert msg.count_segments("OBR") == 3
        assert msg.count_segments("ORC") == 3

        # First OBR
        assert msg.get("OBR-4.1", segment_index=0) == "HEMO"
        # Second OBR
        assert msg.get("OBR-4.1", segment_index=1) == "GLUC"
        # Third OBR
        assert msg.get("OBR-4.1", segment_index=2) == "CREA"

    def test_get_all_segments(self):
        msg = HL7Message.parse(OML_O21_MULTI)
        obrs = msg.get_all_segments("OBR")
        assert len(obrs) == 3
        assert obrs[0].get_component(4, 1) == "HEMO"
        assert obrs[1].get_component(4, 1) == "GLUC"
        assert obrs[2].get_component(4, 1) == "CREA"

    def test_dft_ft1_pr1(self):
        msg = HL7Message.parse(DFT_P03)
        assert msg.message_type_code == "DFT"
        # FT1.2 (transaction ID)
        assert msg.get("FT1-2") == "E12345"
        # FT1.6 (transaction type) - CG = Charge
        assert msg.get("FT1-6") == "CG"
        # PR1 count
        assert msg.count_segments("PR1") == 2
        assert msg.get("PR1-3.1", segment_index=0) == "PREST001"
        assert msg.get("PR1-3.1", segment_index=1) == "PREST002"

    def test_repetition(self):
        msg = HL7Message.parse(ADT_A08)
        pid = msg.get_segment("PID")
        # PID.3 has two repetitions: PAC123 ~ 12345678-9
        rep0 = pid.get_repetition(3, 0)
        assert "PAC123" in rep0
        rep1 = pid.get_repetition(3, 1)
        assert "12345678-9" in rep1

    def test_to_er7_roundtrip(self):
        msg = HL7Message.parse(ADT_A08)
        er7 = msg.to_er7()
        msg2 = HL7Message.parse(er7)
        assert msg2.message_type == msg.message_type
        assert msg2.message_control_id == msg.message_control_id
        assert msg2.get("PID-5.1") == "GONZALEZ"

    def test_clone_and_modify(self):
        msg = HL7Message.parse(ADT_A08)
        clone = msg.clone()
        clone.set("PID-8", "M")
        assert clone.get("PID-8") == "M"
        assert msg.get("PID-8") == "F"  # Original unchanged

    def test_normalize_line_endings(self):
        # LF instead of CR
        lf_msg = ADT_A08.replace("\r", "\n")
        msg = HL7Message.parse(lf_msg)
        assert msg.message_type == "ADT^A08^ADT_A01"

        # CRLF
        crlf_msg = ADT_A08.replace("\r", "\r\n")
        msg2 = HL7Message.parse(crlf_msg)
        assert msg2.message_type == "ADT^A08^ADT_A01"

    def test_iris_style_path(self):
        """Soportar formato IRIS: PID:3.1 además de PID-3.1."""
        msg = HL7Message.parse(ADT_A08)
        assert msg.get("PID:3.1") == msg.get("PID-3.1")
        assert msg.get("MSH:9.1") == "ADT"

    def test_empty_message_raises(self):
        with pytest.raises(ValueError, match="Empty"):
            HL7Message.parse("")

    def test_non_msh_start_raises(self):
        with pytest.raises(ValueError, match="must start with MSH"):
            HL7Message.parse("PID|1||PAC123")


class TestACKGenerator:
    """Tests del generador de ACK."""

    def test_generate_aa_ack(self):
        msg = HL7Message.parse(ADT_A08)
        ack = generate_ack(msg, "AA")
        ack_msg = HL7Message.parse(ack)
        assert ack_msg.get("MSA-1") == "AA"
        assert ack_msg.get("MSA-2") == "MSG001"

    def test_generate_ae_ack(self):
        msg = HL7Message.parse(ADT_A08)
        ack = generate_ack(msg, "AE", "Patient not found")
        ack_msg = HL7Message.parse(ack)
        assert ack_msg.get("MSA-1") == "AE"
        assert ack_msg.get("MSA-2") == "MSG001"
        assert "Patient not found" in ack_msg.get("MSA-3")
        # Should have ERR segment
        assert ack_msg.get_segment("ERR") is not None

    def test_ack_swaps_sending_receiving(self):
        msg = HL7Message.parse(ADT_A08)
        ack = generate_ack(msg, "AA", application="HEALTHFLOW", facility="HF")
        ack_msg = HL7Message.parse(ack)
        assert ack_msg.sending_application == "HEALTHFLOW"
        assert ack_msg.receiving_application == "SAP"
