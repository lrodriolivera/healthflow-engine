"""
FHIR R4 resource models — Pydantic models for core FHIR resources.

Subset focused on what's needed for v2→FHIR mapping:
Patient, Encounter, Observation, DiagnosticReport, ServiceRequest, Bundle.
"""

from __future__ import annotations

from datetime import datetime, date
from typing import Any, Optional
from enum import Enum

from pydantic import BaseModel, Field


class FHIRResourceType(str, Enum):
    Patient = "Patient"
    Encounter = "Encounter"
    Observation = "Observation"
    DiagnosticReport = "DiagnosticReport"
    ServiceRequest = "ServiceRequest"
    Condition = "Condition"
    Practitioner = "Practitioner"
    Organization = "Organization"
    Location = "Location"
    Bundle = "Bundle"


class Coding(BaseModel):
    system: Optional[str] = None
    code: Optional[str] = None
    display: Optional[str] = None


class CodeableConcept(BaseModel):
    coding: list[Coding] = []
    text: Optional[str] = None


class Identifier(BaseModel):
    system: Optional[str] = None
    value: Optional[str] = None
    type: Optional[CodeableConcept] = None


class Reference(BaseModel):
    reference: Optional[str] = None
    display: Optional[str] = None


class HumanName(BaseModel):
    family: Optional[str] = None
    given: list[str] = []
    prefix: list[str] = []
    suffix: list[str] = []
    text: Optional[str] = None


class Address(BaseModel):
    line: list[str] = []
    city: Optional[str] = None
    state: Optional[str] = None
    postalCode: Optional[str] = None
    country: Optional[str] = None


class ContactPoint(BaseModel):
    system: Optional[str] = None  # phone, email, fax
    value: Optional[str] = None
    use: Optional[str] = None  # home, work, mobile


class Period(BaseModel):
    start: Optional[str] = None
    end: Optional[str] = None


# --- Core Resources ---

class FHIRResource(BaseModel):
    """Base para todos los recursos FHIR."""
    resourceType: str
    id: Optional[str] = None
    meta: Optional[dict[str, Any]] = None
    identifier: list[Identifier] = []


class Patient(FHIRResource):
    resourceType: str = "Patient"
    name: list[HumanName] = []
    gender: Optional[str] = None  # male, female, other, unknown
    birthDate: Optional[str] = None
    address: list[Address] = []
    telecom: list[ContactPoint] = []
    active: bool = True
    deceasedBoolean: Optional[bool] = None


class Encounter(FHIRResource):
    resourceType: str = "Encounter"
    status: str = "in-progress"  # planned, arrived, triaged, in-progress, etc.
    class_: Optional[Coding] = Field(None, alias="class")
    type: list[CodeableConcept] = []
    subject: Optional[Reference] = None
    period: Optional[Period] = None
    location: list[dict[str, Any]] = []
    participant: list[dict[str, Any]] = []
    serviceProvider: Optional[Reference] = None

    model_config = {"populate_by_name": True}


class Observation(FHIRResource):
    resourceType: str = "Observation"
    status: str = "final"  # registered, preliminary, final, amended
    category: list[CodeableConcept] = []
    code: Optional[CodeableConcept] = None
    subject: Optional[Reference] = None
    encounter: Optional[Reference] = None
    effectiveDateTime: Optional[str] = None
    valueString: Optional[str] = None
    valueQuantity: Optional[dict[str, Any]] = None


class DiagnosticReport(FHIRResource):
    resourceType: str = "DiagnosticReport"
    status: str = "final"
    category: list[CodeableConcept] = []
    code: Optional[CodeableConcept] = None
    subject: Optional[Reference] = None
    encounter: Optional[Reference] = None
    effectiveDateTime: Optional[str] = None
    result: list[Reference] = []


class ServiceRequest(FHIRResource):
    resourceType: str = "ServiceRequest"
    status: str = "active"
    intent: str = "order"
    code: Optional[CodeableConcept] = None
    subject: Optional[Reference] = None
    encounter: Optional[Reference] = None
    requester: Optional[Reference] = None
    authoredOn: Optional[str] = None


class BundleEntry(BaseModel):
    fullUrl: Optional[str] = None
    resource: Optional[dict[str, Any]] = None


class Bundle(BaseModel):
    resourceType: str = "Bundle"
    type: str = "transaction"  # transaction, batch, collection, searchset
    entry: list[BundleEntry] = []
    total: Optional[int] = None
