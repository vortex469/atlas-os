from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from app.models.provider_management import (
    ManagedResourceIdentityAssurance,
    ManagedResourceProjectionV3,
    ProviderIntentMutationReadiness,
    ProviderIntentReadAuthority,
    ProviderIntentReadReason,
    ProviderIntentReadStatus,
    ProviderManagementDescriptorV3,
    ProviderManagementSection,
    ProviderManagementSectionAvailability,
    ProviderManagementSectionDescriptor,
    ProviderMonitoringExpectation,
    ProviderResourceManagementSupportV3,
)
from app.operator_auth.models import (
    OPERATIONAL_INTENT_CREATE,
    PROVIDER_INTENT_UPDATE,
    OperatorCredential,
)
from app.operator_auth.sessions import OperatorSessionStore
from app.routes.provider_management import router
from app.testing import ASGITestClient

FINGERPRINT = "provider-management-fingerprint-v1:" + "a" * 64


def _descriptor(permitted: bool) -> ProviderManagementDescriptorV3:
    return ProviderManagementDescriptorV3(
        provider_id="proxmox",
        provider_name="Proxmox",
        sections=tuple(
            ProviderManagementSectionDescriptor(
                section=section,
                availability=ProviderManagementSectionAvailability.AVAILABLE,
            )
            for section in ProviderManagementSection
        ),
        resource_types=(
            ProviderResourceManagementSupportV3(
                provider_id="proxmox",
                resource_type="qemu",
                resource_readable=True,
                authoritative_identity_supported=True,
                provider_intent_capability_supported=True,
                provider_intent_mutation_supported=True,
                supported_expectations=tuple(ProviderMonitoringExpectation),
            ),
        ),
        resources=(
            ManagedResourceProjectionV3(
                provider_id="proxmox",
                resource_id="110",
                resource_type="qemu",
                display_name="Frigate",
                current_state="running",
                missing=False,
                resource_live=True,
                identity_assurance=ManagedResourceIdentityAssurance.AUTHORITATIVE,
                management_fingerprint=FINGERPRINT,
                intent_authority=ProviderIntentReadAuthority.PROVIDER_INTENT,
                intent_status=ProviderIntentReadStatus.NEEDS_REVIEW,
                intent_reason=ProviderIntentReadReason.NO_ACTIVE_INTENT,
                legacy_review_available=False,
                replacement_detected=False,
                provider_intent_mutation_supported=True,
                mutation_readiness=ProviderIntentMutationReadiness.READY,
                editable_in_principle=True,
                caller_can_mutate=permitted,
            ),
        ),
        provider_intent_activation="activated",
        provider_intent_authority_status="available",
        caller_has_provider_intent_update=permitted,
    )


def _client(
    tmp_path: Path, permissions: tuple[str, ...]
) -> tuple[ASGITestClient, str]:
    app = FastAPI()
    app.include_router(router)
    app.state.operator_auth_enabled = True
    sessions = OperatorSessionStore(tmp_path / "sessions.db", 3600)
    app.state.operator_session_store = sessions
    created = sessions.create(
        OperatorCredential(
            operator_id="operator",
            password_hash="unused",
            permissions=permissions,
        )
    )
    return ASGITestClient(app), created.session_token


@pytest.fixture(autouse=True)
def descriptor_projection(monkeypatch: pytest.MonkeyPatch) -> list[bool]:
    from app.routes import provider_management as route

    captured: list[bool] = []

    async def project(
        provider_id: str, *, caller_has_provider_intent_update: bool
    ) -> ProviderManagementDescriptorV3:
        assert provider_id == "proxmox"
        captured.append(caller_has_provider_intent_update)
        return _descriptor(caller_has_provider_intent_update)

    monkeypatch.setattr(
        route, "get_authenticated_provider_management_descriptor", project
    )
    return captured


def test_authenticated_v3_derives_caller_capability_from_session(
    tmp_path: Path, descriptor_projection: list[bool]
) -> None:
    client, token = _client(tmp_path, (PROVIDER_INTENT_UPDATE,))
    response = client.get(
        "/providers/proxmox/management/operator",
        cookies={"atlas_operator_session": token},
    )
    assert response.status_code == 200
    assert descriptor_projection == [True]
    assert response.json()["schema_version"] == "provider-management-v3"
    assert response.json()["caller_has_provider_intent_update"] is True
    assert response.json()["resources"][0]["caller_can_mutate"] is True
    serialized = response.text.casefold()
    for forbidden in (
        "operator_id",
        "permissions",
        "vmgenid",
        "native_identity",
        "intent_id",
        "import_id",
        "request_digest",
        "old_fingerprint",
        "audit_id",
    ):
        assert forbidden not in serialized


def test_authenticated_v3_without_permission_is_read_only(
    tmp_path: Path, descriptor_projection: list[bool]
) -> None:
    client, token = _client(tmp_path, ())
    response = client.get(
        "/providers/proxmox/management/operator",
        cookies={"atlas_operator_session": token},
    )
    assert response.status_code == 200
    assert descriptor_projection == [False]
    assert response.json()["caller_has_provider_intent_update"] is False
    assert response.json()["resources"][0]["editable_in_principle"] is True


def test_operational_permission_does_not_grant_provider_intent_mutation(
    tmp_path: Path, descriptor_projection: list[bool]
) -> None:
    client, token = _client(tmp_path, (OPERATIONAL_INTENT_CREATE,))
    response = client.get(
        "/providers/proxmox/management/operator",
        cookies={"atlas_operator_session": token},
    )
    assert response.status_code == 200
    assert descriptor_projection == [False]
    assert response.json()["resources"][0]["caller_can_mutate"] is False


def test_authenticated_v3_rejects_anonymous_without_exposing_descriptor(
    tmp_path: Path, descriptor_projection: list[bool]
) -> None:
    client, _token = _client(tmp_path, ())
    response = client.get("/providers/proxmox/management/operator")
    assert response.status_code == 401
    assert descriptor_projection == []


def test_v2_and_authenticated_v3_are_distinct_get_routes() -> None:
    operations = {
        route.path: route.methods
        for route in router.routes
        if hasattr(route, "methods")
    }
    assert operations["/providers/{provider_id}/management"] == {"GET"}
    assert operations["/providers/{provider_id}/management/operator"] == {"GET"}


def test_v3_descriptor_rejects_permission_or_authority_contradictions() -> None:
    permitted = _descriptor(True).model_dump()
    with pytest.raises(ValidationError):
        ProviderManagementDescriptorV3.model_validate(
            {**permitted, "caller_has_provider_intent_update": False}
        )
    with pytest.raises(ValidationError):
        ProviderManagementDescriptorV3.model_validate(
            {**permitted, "provider_intent_activation": "not_activated"}
        )
