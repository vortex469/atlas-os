from __future__ import annotations

import pytest

from app.actions.history import ProviderActionHistory
from app.main import app
from app.models.provider_management import (
    ManagedResourceIdentityAssurance,
    ManagedResourceProjection,
    ProviderManagementDescriptor,
    ProviderManagementSection,
    ProviderManagementSectionAvailability,
    ProviderManagementSectionDescriptor,
)
from app.testing import ASGITestClient

client = ASGITestClient(app)


@pytest.fixture
def management_descriptor() -> ProviderManagementDescriptor:
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
        resources=(
            ManagedResourceProjection(
                provider_id="proxmox",
                resource_id="110",
                resource_type="qemu",
                display_name="Frigate",
                current_state="running",
                identity_assurance=ManagedResourceIdentityAssurance.AUTHORITATIVE,
                management_fingerprint=(
                    "provider-management-fingerprint-v1:" + "a" * 64
                ),
            ),
            ManagedResourceProjection(
                provider_id="proxmox",
                resource_id="109",
                resource_type="lxc",
                display_name="Kenny",
                current_state="stopped",
                identity_assurance=ManagedResourceIdentityAssurance.UNAVAILABLE,
            ),
        ),
    )


def test_management_route_is_read_only_sanitized_and_has_no_action_side_effect(
    monkeypatch: pytest.MonkeyPatch,
    isolated_action_history: ProviderActionHistory,
    management_descriptor: ProviderManagementDescriptor,
) -> None:
    import app.routes.provider_management as route

    called = 0

    async def collect(provider_id: str) -> ProviderManagementDescriptor:
        nonlocal called
        called += 1
        assert provider_id == "proxmox"
        return management_descriptor

    monkeypatch.setattr(route, "get_provider_management_descriptor", collect)
    before = isolated_action_history.list(limit=100)
    response = client.get("/api/v1/providers/proxmox/management")
    after = isolated_action_history.list(limit=100)

    assert response.status_code == 200
    assert called == 1
    assert before == after == []
    body = response.json()
    assert body["grants_permission"] is False
    assert body["grants_execution"] is False
    assert body["resources"][0]["operationally_requestable"] is False
    assert body["resources"][1]["identity_assurance"] == "unavailable"
    serialized = response.text.casefold()
    for forbidden in (
        "vmgenid",
        "provider_action_id",
        "credentials",
        "cookie",
        "csrf",
        "command",
        "environment",
        '"parameters"',
        '"url"',
    ):
        assert forbidden not in serialized


def test_management_route_is_get_only_and_in_openapi() -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    operations = response.json()["paths"][
        "/api/v1/providers/{provider_id}/management"
    ]
    assert set(operations) == {"get"}


def test_contract_contains_no_timestamp_or_write_authority(
    management_descriptor: ProviderManagementDescriptor,
) -> None:
    assert set(ProviderManagementDescriptor.model_fields).isdisjoint(
        {
            "permission",
            "requestable",
            "action_id",
            "mutation",
            "generated_at",
            "updated_at",
        }
    )
    assert management_descriptor.schema_version == "provider-management-v1"
