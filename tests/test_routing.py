"""Tests para el motor de routing determinista."""

import pytest
from backend.app.core.hl7.parser import HL7Message
from backend.app.core.routing.engine import (
    RoutingEngine,
    RoutingRule,
    RoutingCondition,
    RoutingDestination,
)

ADT_A08 = (
    "MSH|^~\\&|SAP|UCCHRISTUS|IRIS|UCCHRISTUS|20260408120000||ADT^A08|MSG001|P|2.5\r"
    "PID|1||PAC123^^^MPI||GONZALEZ^MARIA||19800115|F\r"
    "PV1|1|I|SALA301^CAMA1\r"
    "PV2|||RAD^Radiología"
)

ORM_O01 = (
    "MSH|^~\\&|AGFA|RIS|IRIS|UCCHRISTUS|20260408120000||ORM^O01|MSG002|P|2.5\r"
    "PID|1||PAC456||PEREZ^CARLOS||19750320|M\r"
    "ORC|NW|ORD001\r"
    "OBR|1|ORD001||RXTOR^Rx Torax"
)

DFT_P03 = (
    "MSH|^~\\&|SAP|UCCHRISTUS|IRIS|UCCHRISTUS|20260408120000||DFT^P03|MSG003|P|2.5\r"
    "PID|1||PAC789||SILVA^PEDRO||19901225|M\r"
    "FT1|1|E12345||20260408|20260408|CG"
)


class TestRoutingEngine:

    def setup_method(self):
        self.engine = RoutingEngine()

    def test_basic_routing_by_message_type(self):
        """ADT → LIS, RIS, Farmacia (fan-out)."""
        rule = RoutingRule(
            name="ADT to all",
            conditions=[
                RoutingCondition(field="MSH-9.1", operator="equals", value="ADT"),
            ],
            destinations=[
                RoutingDestination(name="LIS", adapter_name="MLLP_LIS"),
                RoutingDestination(name="RIS", adapter_name="MLLP_RIS"),
                RoutingDestination(name="Farmacia", adapter_name="SOAP_FARMACIA"),
            ],
        )
        self.engine.add_rule(rule)

        msg = HL7Message.parse(ADT_A08)
        destinations = self.engine.evaluate(msg)
        assert len(destinations) == 3
        assert {d.name for d in destinations} == {"LIS", "RIS", "Farmacia"}

    def test_routing_by_sending_app(self):
        """ORM from AGFA → TrackCare only."""
        rule = RoutingRule(
            name="ORM from AGFA",
            conditions=[
                RoutingCondition(field="MSH-9.1", operator="equals", value="ORM"),
                RoutingCondition(field="MSH-3", operator="equals", value="AGFA"),
            ],
            destinations=[
                RoutingDestination(name="TrackCare", adapter_name="MLLP_TC"),
            ],
        )
        self.engine.add_rule(rule)

        msg = HL7Message.parse(ORM_O01)
        destinations = self.engine.evaluate(msg)
        assert len(destinations) == 1
        assert destinations[0].name == "TrackCare"

    def test_no_match_returns_empty(self):
        """No rules match → empty list (candidate for AI Router)."""
        rule = RoutingRule(
            name="SIU only",
            conditions=[
                RoutingCondition(field="MSH-9.1", operator="equals", value="SIU"),
            ],
            destinations=[
                RoutingDestination(name="Agenda", adapter_name="REST_AGENDA"),
            ],
        )
        self.engine.add_rule(rule)

        msg = HL7Message.parse(ADT_A08)
        destinations = self.engine.evaluate(msg)
        assert len(destinations) == 0

    def test_priority_ordering(self):
        """Higher priority (lower number) rules evaluated first."""
        rule_generic = RoutingRule(
            name="All DFT",
            priority=100,
            conditions=[
                RoutingCondition(field="MSH-9.1", operator="equals", value="DFT"),
            ],
            destinations=[
                RoutingDestination(name="SAP_Generic", adapter_name="SOAP_SAP"),
            ],
        )
        rule_specific = RoutingRule(
            name="DFT CG only",
            priority=10,
            conditions=[
                RoutingCondition(field="MSH-9.1", operator="equals", value="DFT"),
                RoutingCondition(field="FT1-6", operator="equals", value="CG"),
            ],
            destinations=[
                RoutingDestination(name="SAP_Cargo", adapter_name="SOAP_SAP_CARGO"),
            ],
            stop_on_match=True,
        )

        self.engine.add_rule(rule_generic)
        self.engine.add_rule(rule_specific)

        msg = HL7Message.parse(DFT_P03)
        destinations = self.engine.evaluate(msg)
        # Specific rule matches first (priority 10 < 100) and stops
        assert len(destinations) == 1
        assert destinations[0].name == "SAP_Cargo"

    def test_disabled_rule_skipped(self):
        rule = RoutingRule(
            name="Disabled",
            enabled=False,
            conditions=[
                RoutingCondition(field="MSH-9.1", operator="equals", value="ADT"),
            ],
            destinations=[
                RoutingDestination(name="Nowhere", adapter_name="NULL"),
            ],
        )
        self.engine.add_rule(rule)
        msg = HL7Message.parse(ADT_A08)
        assert len(self.engine.evaluate(msg)) == 0

    def test_disabled_destination_filtered(self):
        rule = RoutingRule(
            name="ADT mixed",
            conditions=[
                RoutingCondition(field="MSH-9.1", operator="equals", value="ADT"),
            ],
            destinations=[
                RoutingDestination(name="Active", adapter_name="A", enabled=True),
                RoutingDestination(name="Disabled", adapter_name="B", enabled=False),
            ],
        )
        self.engine.add_rule(rule)
        msg = HL7Message.parse(ADT_A08)
        destinations = self.engine.evaluate(msg)
        assert len(destinations) == 1
        assert destinations[0].name == "Active"

    def test_contains_operator(self):
        rule = RoutingRule(
            name="RAD service",
            conditions=[
                RoutingCondition(field="PV2-3.1", operator="equals", value="RAD"),
            ],
            destinations=[
                RoutingDestination(name="RIS", adapter_name="MLLP_RIS"),
            ],
        )
        self.engine.add_rule(rule)
        msg = HL7Message.parse(ADT_A08)
        assert len(self.engine.evaluate(msg)) == 1

    def test_in_operator(self):
        rule = RoutingRule(
            name="ADT or ORM",
            conditions=[
                RoutingCondition(field="MSH-9.1", operator="in", value="ADT,ORM,SIU"),
            ],
            destinations=[
                RoutingDestination(name="TrackCare", adapter_name="MLLP_TC"),
            ],
        )
        self.engine.add_rule(rule)
        msg_adt = HL7Message.parse(ADT_A08)
        msg_orm = HL7Message.parse(ORM_O01)
        msg_dft = HL7Message.parse(DFT_P03)
        assert len(self.engine.evaluate(msg_adt)) == 1
        assert len(self.engine.evaluate(msg_orm)) == 1
        assert len(self.engine.evaluate(msg_dft)) == 0

    def test_case_insensitive(self):
        rule = RoutingRule(
            name="case insensitive",
            conditions=[
                RoutingCondition(
                    field="MSH-3", operator="equals", value="sap", case_sensitive=False
                ),
            ],
            destinations=[
                RoutingDestination(name="SAP", adapter_name="SOAP_SAP"),
            ],
        )
        self.engine.add_rule(rule)
        msg = HL7Message.parse(ADT_A08)
        assert len(self.engine.evaluate(msg)) == 1
