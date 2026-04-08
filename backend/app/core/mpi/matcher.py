"""
Patient matching engine — deterministic + probabilistic.

Deterministic matching:
  - Exact match on identifiers (MRN, RUN/SSN, passport)
  - Exact match on DOB + last name + first name

Probabilistic matching (Fellegi-Sunter simplified):
  - Weighted score across multiple fields
  - Configurable thresholds for auto-link vs. review
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import re
import unicodedata


class MatchScore(str, Enum):
    definite = "definite"    # Auto-link (score > high_threshold)
    probable = "probable"    # Review needed (score between thresholds)
    possible = "possible"    # Low probability
    no_match = "no_match"    # Below low threshold


@dataclass
class MatchResult:
    """Resultado de un match entre dos pacientes."""
    score: float  # 0.0 - 1.0
    level: MatchScore
    matched_fields: list[str]
    details: dict[str, float] = field(default_factory=dict)


@dataclass
class PatientRecord:
    """Datos de paciente para matching."""
    identifiers: dict[str, str] = field(default_factory=dict)  # type -> value
    family_name: str = ""
    given_name: str = ""
    birth_date: str = ""  # YYYYMMDD
    gender: str = ""  # M/F/O/U
    phone: str = ""
    address_line: str = ""
    city: str = ""


# Field weights for probabilistic matching
DEFAULT_WEIGHTS = {
    "identifier": 0.30,
    "family_name": 0.20,
    "given_name": 0.15,
    "birth_date": 0.20,
    "gender": 0.05,
    "phone": 0.05,
    "address": 0.05,
}


class PatientMatcher:
    """Motor de matching de pacientes."""

    def __init__(
        self,
        high_threshold: float = 0.85,
        low_threshold: float = 0.50,
        weights: Optional[dict[str, float]] = None,
    ):
        self.high_threshold = high_threshold
        self.low_threshold = low_threshold
        self.weights = weights or DEFAULT_WEIGHTS

    def match(self, patient_a: PatientRecord, patient_b: PatientRecord) -> MatchResult:
        """Comparar dos registros de paciente.

        Primero intenta matching determinístico. Si falla, usa probabilístico.
        """
        # Deterministic: exact identifier match
        deterministic = self._deterministic_match(patient_a, patient_b)
        if deterministic:
            return deterministic

        # Probabilistic: weighted field comparison
        return self._probabilistic_match(patient_a, patient_b)

    def _deterministic_match(
        self, a: PatientRecord, b: PatientRecord
    ) -> Optional[MatchResult]:
        """Match determinístico por identificadores exactos."""
        for id_type, id_value in a.identifiers.items():
            if id_type in b.identifiers and id_value and b.identifiers[id_type]:
                if _normalize(id_value) == _normalize(b.identifiers[id_type]):
                    return MatchResult(
                        score=1.0,
                        level=MatchScore.definite,
                        matched_fields=[f"identifier:{id_type}"],
                        details={f"identifier:{id_type}": 1.0},
                    )

        # DOB + Last Name + First Name exact match
        if (a.birth_date and b.birth_date and
            a.family_name and b.family_name and
            a.given_name and b.given_name):
            if (a.birth_date == b.birth_date and
                _normalize(a.family_name) == _normalize(b.family_name) and
                _normalize(a.given_name) == _normalize(b.given_name)):
                return MatchResult(
                    score=0.95,
                    level=MatchScore.definite,
                    matched_fields=["birth_date", "family_name", "given_name"],
                    details={"birth_date": 1.0, "family_name": 1.0, "given_name": 1.0},
                )

        return None

    def _probabilistic_match(self, a: PatientRecord, b: PatientRecord) -> MatchResult:
        """Match probabilístico con pesos por campo."""
        scores: dict[str, float] = {}
        matched_fields = []

        # Identifier partial (any type matches any type)
        id_score = self._compare_identifiers(a.identifiers, b.identifiers)
        scores["identifier"] = id_score
        if id_score > 0:
            matched_fields.append("identifier")

        # Name comparison
        scores["family_name"] = _string_similarity(a.family_name, b.family_name)
        if scores["family_name"] > 0.8:
            matched_fields.append("family_name")

        scores["given_name"] = _string_similarity(a.given_name, b.given_name)
        if scores["given_name"] > 0.8:
            matched_fields.append("given_name")

        # Birth date
        scores["birth_date"] = 1.0 if a.birth_date and a.birth_date == b.birth_date else 0.0
        if scores["birth_date"] > 0:
            matched_fields.append("birth_date")

        # Gender
        scores["gender"] = 1.0 if a.gender and a.gender == b.gender else 0.0
        if scores["gender"] > 0:
            matched_fields.append("gender")

        # Phone
        scores["phone"] = 1.0 if a.phone and _normalize_phone(a.phone) == _normalize_phone(b.phone) else 0.0
        if scores["phone"] > 0:
            matched_fields.append("phone")

        # Address
        scores["address"] = _string_similarity(a.address_line, b.address_line)
        if scores["address"] > 0.7:
            matched_fields.append("address")

        # Weighted total
        total = sum(scores.get(k, 0) * w for k, w in self.weights.items())

        if total >= self.high_threshold:
            level = MatchScore.definite
        elif total >= self.low_threshold:
            level = MatchScore.probable
        elif total >= 0.30:
            level = MatchScore.possible
        else:
            level = MatchScore.no_match

        return MatchResult(
            score=round(total, 4),
            level=level,
            matched_fields=matched_fields,
            details=scores,
        )

    def _compare_identifiers(
        self, ids_a: dict[str, str], ids_b: dict[str, str]
    ) -> float:
        """Comparar sets de identificadores."""
        if not ids_a or not ids_b:
            return 0.0
        for type_a, val_a in ids_a.items():
            for type_b, val_b in ids_b.items():
                if val_a and val_b and _normalize(val_a) == _normalize(val_b):
                    return 1.0
        return 0.0


# --- Utility functions ---

def _normalize(s: str) -> str:
    """Normalizar string para comparación."""
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", s).strip().upper()


def _normalize_phone(phone: str) -> str:
    """Normalizar teléfono: solo dígitos."""
    return re.sub(r"[^\d]", "", phone)


def _string_similarity(a: str, b: str) -> float:
    """Similitud entre strings (Jaro-Winkler simplificado).

    Returns 0.0-1.0.
    """
    if not a or not b:
        return 0.0

    a_norm = _normalize(a)
    b_norm = _normalize(b)

    if a_norm == b_norm:
        return 1.0
    if not a_norm or not b_norm:
        return 0.0

    # Simple character overlap ratio
    shorter = min(len(a_norm), len(b_norm))
    longer = max(len(a_norm), len(b_norm))

    # Count matching characters at same position
    matches = sum(1 for ca, cb in zip(a_norm, b_norm) if ca == cb)

    # Prefix bonus (Winkler)
    prefix = 0
    for ca, cb in zip(a_norm[:4], b_norm[:4]):
        if ca == cb:
            prefix += 1
        else:
            break

    base_score = matches / longer
    winkler_bonus = prefix * 0.1 * (1 - base_score)

    return min(1.0, base_score + winkler_bonus)
