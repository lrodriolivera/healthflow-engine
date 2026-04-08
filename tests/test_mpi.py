"""Tests para Master Patient Index."""

import pytest

from backend.app.core.mpi.matcher import (
    PatientMatcher, PatientRecord, MatchResult, MatchScore,
    _normalize, _string_similarity,
)
from backend.app.core.mpi.index import MasterPatientIndex


class TestPatientMatcher:

    def setup_method(self):
        self.matcher = PatientMatcher()

    def test_exact_identifier_match(self):
        a = PatientRecord(identifiers={"MR": "PAC123"}, family_name="GONZALEZ")
        b = PatientRecord(identifiers={"MR": "PAC123"}, family_name="GONZALEZ")
        result = self.matcher.match(a, b)
        assert result.level == MatchScore.definite
        assert result.score == 1.0

    def test_exact_dob_name_match(self):
        a = PatientRecord(family_name="GONZALEZ", given_name="MARIA", birth_date="19800115")
        b = PatientRecord(family_name="GONZALEZ", given_name="MARIA", birth_date="19800115")
        result = self.matcher.match(a, b)
        assert result.level == MatchScore.definite

    def test_no_match_different_patients(self):
        a = PatientRecord(family_name="GONZALEZ", given_name="MARIA", birth_date="19800115")
        b = PatientRecord(family_name="PEREZ", given_name="CARLOS", birth_date="19750320")
        result = self.matcher.match(a, b)
        assert result.level == MatchScore.no_match
        assert result.score < 0.3

    def test_probable_match_similar(self):
        a = PatientRecord(
            family_name="GONZALEZ", given_name="MARIA",
            birth_date="19800115", gender="F", phone="+56912345678",
        )
        b = PatientRecord(
            family_name="GONZALEZ", given_name="MARIA TERESA",
            birth_date="19800115", gender="F", phone="+56912345678",
        )
        result = self.matcher.match(a, b)
        assert result.level in (MatchScore.definite, MatchScore.probable)
        assert result.score > 0.5

    def test_identifier_different_type_match(self):
        a = PatientRecord(identifiers={"RUN": "12345678-9"})
        b = PatientRecord(identifiers={"SSN": "12345678-9"})
        result = self.matcher.match(a, b)
        # Cross-type identifier match via probabilistic
        assert result.score > 0

    def test_normalize(self):
        assert _normalize("González") == "GONZALEZ"
        assert _normalize("  María  Teresa  ") == "MARIA TERESA"

    def test_string_similarity_exact(self):
        assert _string_similarity("GONZALEZ", "GONZALEZ") == 1.0

    def test_string_similarity_empty(self):
        assert _string_similarity("", "GONZALEZ") == 0.0

    def test_string_similarity_partial(self):
        score = _string_similarity("GONZALEZ", "GONZALES")
        assert 0.5 < score < 1.0


class TestMasterPatientIndex:

    def test_add_new_patient(self):
        mpi = MasterPatientIndex()
        record = PatientRecord(
            identifiers={"MR": "PAC001"},
            family_name="GONZALEZ",
            given_name="MARIA",
            birth_date="19800115",
        )
        mpi_id, matches = mpi.add_patient(record, "SAP")
        assert mpi_id is not None
        assert mpi.count == 1

    def test_auto_link_same_identifier(self):
        mpi = MasterPatientIndex()
        r1 = PatientRecord(identifiers={"MR": "PAC001"}, family_name="GONZALEZ")
        r2 = PatientRecord(identifiers={"MR": "PAC001"}, family_name="GONZALEZ MARIA")

        mpi_id1, _ = mpi.add_patient(r1, "SAP")
        mpi_id2, matches = mpi.add_patient(r2, "LIS")

        assert mpi_id1 == mpi_id2  # Same MPI ID
        assert mpi.count == 1  # Only one entry

    def test_separate_entries_different_patients(self):
        mpi = MasterPatientIndex()
        r1 = PatientRecord(identifiers={"MR": "PAC001"}, family_name="GONZALEZ", birth_date="19800115")
        r2 = PatientRecord(identifiers={"MR": "PAC002"}, family_name="PEREZ", birth_date="19750320")

        mpi_id1, _ = mpi.add_patient(r1, "SAP")
        mpi_id2, _ = mpi.add_patient(r2, "SAP")

        assert mpi_id1 != mpi_id2
        assert mpi.count == 2

    def test_lookup_by_identifier(self):
        mpi = MasterPatientIndex()
        r = PatientRecord(identifiers={"RUN": "12345678-9"}, family_name="SILVA")
        mpi_id, _ = mpi.add_patient(r, "SAP")

        entry = mpi.lookup_by_identifier("RUN", "12345678-9")
        assert entry is not None
        assert entry.mpi_id == mpi_id

    def test_lookup_missing(self):
        mpi = MasterPatientIndex()
        assert mpi.lookup_by_identifier("MR", "NONEXISTENT") is None

    def test_merge(self):
        mpi = MasterPatientIndex()
        r1 = PatientRecord(identifiers={"MR": "PAC001"}, family_name="GONZALEZ")
        r2 = PatientRecord(identifiers={"MR": "PAC999"}, family_name="GONZALES")

        id1, _ = mpi.add_patient(r1, "SAP")
        id2, _ = mpi.add_patient(r2, "LIS")
        assert mpi.count == 2

        result = mpi.merge(id1, id2)
        assert result is True

        # Surviving entry has both records
        entry = mpi.get(id1)
        assert len(entry.records) == 2

        # Retired entry is inactive
        retired = mpi.get(id2)
        assert retired.is_active is False

    def test_get_stats(self):
        mpi = MasterPatientIndex()
        mpi.add_patient(PatientRecord(identifiers={"MR": "P1"}), "S1")
        mpi.add_patient(PatientRecord(identifiers={"MR": "P2"}), "S1")
        stats = mpi.get_stats()
        assert stats["active_entries"] == 2
        assert stats["indexed_ids"] >= 2

    def test_search_returns_sorted(self):
        mpi = MasterPatientIndex()
        mpi.add_patient(PatientRecord(
            identifiers={"MR": "P1"}, family_name="GONZALEZ",
            given_name="MARIA", birth_date="19800115",
        ), "SAP")
        mpi.add_patient(PatientRecord(
            identifiers={"MR": "P2"}, family_name="PEREZ",
            given_name="CARLOS", birth_date="19750320",
        ), "SAP")

        query = PatientRecord(family_name="GONZALEZ", given_name="MARIA", birth_date="19800115")
        results = mpi.search(query)

        # Best match should be first
        if results:
            assert results[0][0].score >= results[-1][0].score
