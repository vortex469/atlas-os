from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models.provider_management import (
    ManagedResourceIdentityAssurance,
    ManagedResourceProjection,
    ProviderManagementDescriptor,
    ProviderManagementSection,
    ProviderManagementSectionAvailability,
    ProviderManagementSectionDescriptor,
)
from app.models.resources import (
    ProviderResource,
    ProviderResourceExpectation,
    ProviderResourceIdentity,
)
from app.providers.proxmox_identity import build_proxmox_qemu_identity
from app.services.provider_management import project_managed_resource


def _resource(
    *,
    resource_type: str = "qemu",
    vmgenid: str = "11111111-1111-1111-1111-111111111111",
    display_name: str = "Frigate",
    current_state: str = "running",
    metadata: dict | None = None,
) -> ProviderResource:
    identity = (
        build_proxmox_qemu_identity(
            node="vorex469",
            vmid="110",
            vmgenid=vmgenid,
        )
        if resource_type == "qemu"
        else None
    )
    return ProviderResource(
        provider_id="proxmox",
        resource_id="110",
        resource_type=resource_type,
        display_name=display_name,
        current_state=current_state,
        identity=identity,
        expectation=ProviderResourceExpectation(),
        configured=False,
        metadata=metadata or {},
    )


def test_management_models_are_strict_frozen_and_closed() -> None:
    section = ProviderManagementSectionDescriptor(
        section=ProviderManagementSection.RESOURCES,
        availability=ProviderManagementSectionAvailability.AVAILABLE,
    )
    with pytest.raises(ValidationError, match="frozen"):
        section.availability = ProviderManagementSectionAvailability.UNAVAILABLE  # type: ignore[misc]
    with pytest.raises(ValidationError, match="Extra inputs"):
        ProviderManagementSectionDescriptor.model_validate(
            {
                **section.model_dump(),
                "permission": "operational_intent:create",
            }
        )
    with pytest.raises(ValidationError):
        ProviderManagementSectionDescriptor.model_validate(
            {"section": "shell", "availability": "available"}
        )
    with pytest.raises(ValidationError):
        ManagedResourceProjection.model_validate(
            {
                "provider_id": "proxmox",
                "resource_id": "110",
                "resource_type": "qemu",
                "display_name": "Frigate",
                "current_state": "running",
                "identity_assurance": "guessed",
            }
        )
    with pytest.raises(ValidationError, match="only authoritative"):
        ManagedResourceProjection(
            provider_id="proxmox",
            resource_id="110",
            resource_type="qemu",
            display_name="Frigate",
            current_state="running",
            identity_assurance=ManagedResourceIdentityAssurance.AUTHORITATIVE,
        )
    with pytest.raises(ValidationError, match="only authoritative"):
        ManagedResourceProjection(
            provider_id="proxmox",
            resource_id="109",
            resource_type="lxc",
            display_name="Kenny",
            current_state="stopped",
            identity_assurance=ManagedResourceIdentityAssurance.UNAVAILABLE,
            management_fingerprint=(
                "provider-management-fingerprint-v1:" + "a" * 64
            ),
        )


def test_qemu_management_identity_is_authoritative_deterministic_and_opaque() -> None:
    first = project_managed_resource(_resource())
    second = project_managed_resource(_resource())

    assert first.identity_assurance is ManagedResourceIdentityAssurance.AUTHORITATIVE
    assert first.management_fingerprint == second.management_fingerprint
    assert first.management_fingerprint is not None
    assert "11111111-1111-1111-1111-111111111111" not in first.model_dump_json()
    assert set(ManagedResourceProjection.model_fields).isdisjoint(
        {
            "identity",
            "vmgenid",
            "credentials",
            "token",
            "cookies",
            "csrf",
            "command",
            "environment",
            "url",
            "provider_action_id",
            "parameters",
            "metadata",
        }
    )


def test_changed_qemu_incarnation_changes_management_fingerprint() -> None:
    before = project_managed_resource(_resource())
    replacement = project_managed_resource(
        _resource(vmgenid="22222222-2222-2222-2222-222222222222")
    )

    assert before.resource_id == replacement.resource_id == "110"
    assert before.management_fingerprint != replacement.management_fingerprint


def test_untrusted_qemu_identity_fails_closed() -> None:
    qemu = _resource()
    qemu.identity = ProviderResourceIdentity(
        token="other-identity-v1:" + "a" * 64,
        token_version="other-identity-v1",
    )

    projected = project_managed_resource(qemu)

    assert projected.identity_assurance is ManagedResourceIdentityAssurance.UNAVAILABLE
    assert projected.management_fingerprint is None


def test_mutable_qemu_fields_do_not_define_management_identity() -> None:
    before = project_managed_resource(
        _resource(
            metadata={
                "cpu_percent": 2.0,
                "memory_used_gib": 1.0,
                "uptime_seconds": 10,
            }
        )
    )
    changed = project_managed_resource(
        _resource(
            display_name="Renamed",
            current_state="stopped",
            metadata={
                "cpu_percent": 99.0,
                "memory_used_gib": 7.5,
                "uptime_seconds": 999,
            },
        )
    )

    assert before.management_fingerprint == changed.management_fingerprint


def test_lxc_identity_is_unavailable_even_if_an_identity_is_injected() -> None:
    lxc = _resource(resource_type="lxc")
    lxc.identity = ProviderResourceIdentity(
        token="synthetic-lxc-identity",
        token_version="synthetic-v1",
    )

    projected = project_managed_resource(lxc)

    assert projected.identity_assurance is ManagedResourceIdentityAssurance.UNAVAILABLE
    assert projected.management_fingerprint is None
    assert projected.operationally_requestable is False
    assert projected.grants_execution is False


def test_descriptor_presence_grants_no_permission_or_execution() -> None:
    descriptor = ProviderManagementDescriptor(
        provider_id="proxmox",
        provider_name="Proxmox",
        sections=tuple(
            ProviderManagementSectionDescriptor(
                section=section,
                availability=ProviderManagementSectionAvailability.AVAILABLE,
            )
            for section in ProviderManagementSection
        ),
        resources=(project_managed_resource(_resource()),),
    )

    assert descriptor.grants_permission is False
    assert descriptor.grants_execution is False
    assert all(section.grants_permission is False for section in descriptor.sections)
    assert all(section.grants_execution is False for section in descriptor.sections)
    assert all(resource.operationally_requestable is False for resource in descriptor.resources)


def test_management_projection_has_no_mutation_or_execution_dependencies() -> None:
    source = Path(__file__).with_name("provider_management.py").read_text(
        encoding="utf-8"
    )
    for forbidden in (
        "execution_candidates",
        "operational_dispatch",
        "candidate_planning",
        "app.actions",
        "update_provider_resource_expectation",
        "refresh_provider_resources",
        "Provider Intent Store",
    ):
        assert forbidden not in source
