from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI

from app.models.provider_management import (
    ManagedResourceIdentityAssurance,
    ManagedResourceProjection,
    ProviderIntentReadAuthority,
    ProviderIntentReadReason,
    ProviderIntentReadStatus,
    ProviderManagementDescriptor,
    ProviderManagementSection,
    ProviderManagementSectionAvailability,
    ProviderManagementSectionDescriptor,
)
from app.operator_auth.models import OPERATIONAL_INTENT_CREATE, OperatorCredential
from app.operator_auth.sessions import OperatorSessionStore
from app.providers import ProviderNotFoundError
from app.providers.management import provider_resource_management_registry
from app.routes.provider_intent_suggestions import router
from app.testing import ASGITestClient

FINGERPRINT_A = "provider-management-fingerprint-v1:" + "a" * 64
FINGERPRINT_B = "provider-management-fingerprint-v1:" + "b" * 64
URL = "/providers/proxmox/management/operator/monitoring-suggestions"


def _descriptor() -> ProviderManagementDescriptor:
    return ProviderManagementDescriptor(
        provider_id="proxmox",
        provider_name="Proxmox",
        sections=tuple(
            ProviderManagementSectionDescriptor(
                section=section,
                availability=ProviderManagementSectionAvailability.AVAILABLE,
            )
            for section in ProviderManagementSection
        ),
        resource_types=provider_resource_management_registry.for_provider(
            "proxmox"
        ),
        resources=tuple(
            ManagedResourceProjection(
                provider_id="proxmox",
                resource_id=resource_id,
                resource_type="qemu",
                display_name=f"QEMU {resource_id}",
                current_state="running",
                identity_assurance=(
                    ManagedResourceIdentityAssurance.AUTHORITATIVE
                ),
                management_fingerprint=fingerprint,
                intent_authority=ProviderIntentReadAuthority.PROVIDER_INTENT,
                intent_status=ProviderIntentReadStatus.NEEDS_REVIEW,
                intent_reason=ProviderIntentReadReason.NO_ACTIVE_INTENT,
            )
            for resource_id, fingerprint in (
                ("200", FINGERPRINT_B),
                ("110", FINGERPRINT_A),
            )
        ),
        provider_intent_activation="activated",
        provider_intent_authority_status="available",
    )


def _client(
    tmp_path: Path,
    *,
    permissions: tuple[str, ...] = (),
    enabled: bool = True,
) -> tuple[ASGITestClient, str]:
    app = FastAPI()
    app.include_router(router)
    app.state.operator_auth_enabled = enabled
    sessions = OperatorSessionStore(tmp_path / "sessions.db", 3600)
    app.state.operator_session_store = sessions
    created = sessions.create(
        OperatorCredential(
            operator_id="reader",
            password_hash="unused",
            permissions=permissions,
        )
    )
    return ASGITestClient(app), created.session_token


@pytest.fixture(autouse=True)
def descriptor_reader(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    from app.routes import provider_intent_suggestions as route

    calls: list[str] = []

    async def read(provider_id: str) -> ProviderManagementDescriptor:
        calls.append(provider_id)
        if provider_id == "missing":
            raise ProviderNotFoundError(provider_id)
        return _descriptor()

    monkeypatch.setattr(route, "get_provider_management_descriptor", read)
    return calls


def test_authenticated_read_without_update_permission_is_bounded_and_sorted(
    tmp_path: Path, descriptor_reader: list[str]
) -> None:
    client, token = _client(tmp_path)
    response = client.get(
        URL, cookies={"atlas_operator_session": token}
    )
    assert response.status_code == 200
    assert descriptor_reader == ["proxmox"]
    body = response.json()
    assert [item["resource_id"] for item in body] == ["110", "200"]
    assert all(
        set(item)
        == {
            "schema_version",
            "suggestion_id",
            "provider_id",
            "resource_type",
            "resource_id",
            "management_fingerprint",
            "suggested_expectation",
            "base_record_version",
            "source",
            "source_rule",
            "reason",
            "advisory_only",
            "grants_permission",
            "grants_execution",
        }
        for item in body
    )
    serialized = response.text.casefold()
    for forbidden in (
        "operator_id",
        "permissions",
        "vmgenid",
        "native_identity",
        "provider_payload",
        "audit",
        "import_id",
        "database",
        "request_id",
        "cookie",
        "csrf",
        "command",
        "environment",
        '"url"',
        '"metadata"',
    ):
        assert forbidden not in serialized


def test_operational_permission_neither_required_nor_exposed(
    tmp_path: Path,
) -> None:
    client, token = _client(
        tmp_path, permissions=(OPERATIONAL_INTENT_CREATE,)
    )
    response = client.get(
        URL, cookies={"atlas_operator_session": token}
    )
    assert response.status_code == 200
    assert response.json()[0]["grants_permission"] is False


def test_anonymous_invalid_and_disabled_sessions_fail_closed(
    tmp_path: Path, descriptor_reader: list[str]
) -> None:
    client, _token = _client(tmp_path / "anonymous")
    assert client.get(URL).status_code == 401
    assert client.get(
        URL, cookies={"atlas_operator_session": "invalid"}
    ).status_code == 401
    disabled, token = _client(tmp_path / "disabled", enabled=False)
    assert disabled.get(
        URL, cookies={"atlas_operator_session": token}
    ).status_code == 503
    assert descriptor_reader == []


def test_repeated_gets_are_fresh_and_deterministic(
    tmp_path: Path, descriptor_reader: list[str]
) -> None:
    client, token = _client(tmp_path)
    cookies = {"atlas_operator_session": token}
    first = client.get(URL, cookies=cookies)
    second = client.get(URL, cookies=cookies)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert descriptor_reader == ["proxmox", "proxmox"]


def test_unknown_provider_uses_management_not_found_semantics(
    tmp_path: Path,
) -> None:
    client, token = _client(tmp_path)
    response = client.get(
        "/providers/missing/management/operator/monitoring-suggestions",
        cookies={"atlas_operator_session": token},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown provider 'missing'."


def test_provider_path_cannot_return_another_provider_descriptor(
    tmp_path: Path, descriptor_reader: list[str]
) -> None:
    client, token = _client(tmp_path)
    response = client.get(
        "/providers/docker/management/operator/monitoring-suggestions",
        cookies={"atlas_operator_session": token},
    )
    assert response.status_code == 200
    assert response.json() == []
    assert descriptor_reader == ["docker"]


def test_route_is_get_only_and_does_not_require_csrf(tmp_path: Path) -> None:
    client, token = _client(tmp_path)
    cookies = {"atlas_operator_session": token}
    assert client.get(URL, cookies=cookies).status_code == 200
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        assert client.request(method, URL, cookies=cookies).status_code == 405
