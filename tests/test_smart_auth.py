"""Tests para SMART on FHIR auth y Bulk Data."""

import pytest

from backend.app.core.fhir.smart_auth import (
    SMARTAuthProvider, SMARTConfig, SMARTToken, ScopeAccess,
)


class TestSMARTAuth:

    def test_disabled_returns_anonymous(self):
        provider = SMARTAuthProvider(SMARTConfig(enabled=False))
        import asyncio
        token = asyncio.get_event_loop().run_until_complete(provider.validate_token("anything"))
        assert token is not None
        assert token.sub == "anonymous"

    def test_dev_token_valid(self):
        provider = SMARTAuthProvider(SMARTConfig(enabled=True))
        provider.add_dev_token("test-token-123", sub="user1", scopes=["patient/Patient.read"])
        import asyncio
        token = asyncio.get_event_loop().run_until_complete(provider.validate_token("test-token-123"))
        assert token is not None
        assert token.sub == "user1"

    def test_invalid_token_returns_none(self):
        provider = SMARTAuthProvider(SMARTConfig(enabled=True))
        import asyncio
        token = asyncio.get_event_loop().run_until_complete(provider.validate_token("bad-token"))
        assert token is None

    def test_scope_check_exact(self):
        provider = SMARTAuthProvider()
        token = SMARTToken(sub="user1", scopes=["patient/Patient.read"])
        assert provider.check_scope(token, "Patient", ScopeAccess.read) is True
        assert provider.check_scope(token, "Patient", ScopeAccess.write) is False
        assert provider.check_scope(token, "Encounter", ScopeAccess.read) is False

    def test_scope_check_wildcard_resource(self):
        provider = SMARTAuthProvider()
        token = SMARTToken(sub="user1", scopes=["user/*.read"])
        assert provider.check_scope(token, "Patient", ScopeAccess.read) is True
        assert provider.check_scope(token, "Encounter", ScopeAccess.read) is True
        assert provider.check_scope(token, "Patient", ScopeAccess.write) is False

    def test_scope_check_wildcard_access(self):
        provider = SMARTAuthProvider()
        token = SMARTToken(sub="system", scopes=["system/Patient.*"])
        assert provider.check_scope(token, "Patient", ScopeAccess.read) is True
        assert provider.check_scope(token, "Patient", ScopeAccess.write) is True
        assert provider.check_scope(token, "Encounter", ScopeAccess.read) is False

    def test_scope_check_full_wildcard(self):
        provider = SMARTAuthProvider()
        token = SMARTToken(sub="admin", scopes=["system/*.*"])
        assert provider.check_scope(token, "Patient", ScopeAccess.read) is True
        assert provider.check_scope(token, "Encounter", ScopeAccess.write) is True
        assert provider.check_scope(token, "DiagnosticReport", ScopeAccess.all) is True

    def test_well_known_config(self):
        provider = SMARTAuthProvider(SMARTConfig(
            issuer="https://auth.hospital.com",
            jwks_uri="https://auth.hospital.com/.well-known/jwks.json",
        ))
        config = provider.get_well_known_config()
        assert config["issuer"] == "https://auth.hospital.com"
        assert "authorization_endpoint" in config
        assert "patient/*.read" in config["scopes_supported"]
        assert "launch-ehr" in config["capabilities"]


class TestBulkExportJob:

    def test_export_job_creation(self):
        from backend.app.core.fhir.bulk_export import ExportJob, ExportStatus
        job = ExportJob(resource_types=["Patient", "Encounter"])
        assert job.status == ExportStatus.accepted
        assert "Patient" in job.resource_types

    def test_execute_export_empty_store(self):
        from backend.app.core.fhir.bulk_export import ExportJob, ExportStatus, _execute_export, set_resource_store
        set_resource_store({})
        job = ExportJob()
        _execute_export(job)
        assert job.status == ExportStatus.complete
        assert len(job.output_files) == 0

    def test_execute_export_with_data(self):
        from backend.app.core.fhir.bulk_export import ExportJob, ExportStatus, _execute_export, set_resource_store
        store = {
            "Patient": {
                "p1": {"resourceType": "Patient", "id": "p1", "name": [{"family": "Test"}]},
                "p2": {"resourceType": "Patient", "id": "p2", "name": [{"family": "Other"}]},
            },
            "Encounter": {
                "e1": {"resourceType": "Encounter", "id": "e1", "status": "in-progress"},
            },
        }
        set_resource_store(store)
        job = ExportJob()
        _execute_export(job)
        assert job.status == ExportStatus.complete
        assert "Patient" in job.output_files
        assert len(job.output_files["Patient"]) == 2
        assert "Encounter" in job.output_files

    def test_execute_export_type_filter(self):
        from backend.app.core.fhir.bulk_export import ExportJob, ExportStatus, _execute_export, set_resource_store
        store = {
            "Patient": {"p1": {"resourceType": "Patient", "id": "p1"}},
            "Encounter": {"e1": {"resourceType": "Encounter", "id": "e1"}},
        }
        set_resource_store(store)
        job = ExportJob(resource_types=["Patient"])
        _execute_export(job)
        assert "Patient" in job.output_files
        assert "Encounter" not in job.output_files
