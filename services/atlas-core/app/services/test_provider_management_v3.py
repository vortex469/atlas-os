from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models.provider_management import (
    ManagedResourceIdentityAssurance,
    ManagedResourceProjection,
    ManagedResourceProjectionV3,
    ProviderIntentMutationReadiness,
    ProviderIntentReadAuthority,
    ProviderIntentReadReason,
    ProviderIntentReadStatus,
    ProviderManagementDescriptor,
    ProviderManagementSection,
    ProviderManagementSectionAvailability,
    ProviderManagementSectionDescriptor,
    ProviderMonitoringExpectation,
)
from app.provider_intents.store import ProviderIntentStore
from app.providers.management import provider_resource_management_registry
from app.services.provider_management import (
    get_authenticated_provider_management_descriptor,
)

FINGERPRINT = "provider-management-fingerprint-v1:" + "a" * 64


def _resource(**overrides: object) -> ManagedResourceProjection:
    values: dict[str, object] = {
        "provider_id": "proxmox",
        "resource_id": "110",
        "resource_type": "qemu",
        "display_name": "Frigate",
        "current_state": "running",
        "identity_assurance": ManagedResourceIdentityAssurance.AUTHORITATIVE,
        "management_fingerprint": FINGERPRINT,
        "intent_authority": ProviderIntentReadAuthority.PROVIDER_INTENT,
        "intent_status": ProviderIntentReadStatus.NEEDS_REVIEW,
        "intent_reason": ProviderIntentReadReason.NO_ACTIVE_INTENT,
    }
    values.update(overrides)
    return ManagedResourceProjection(**values)


def _descriptor(
    *resources: ManagedResourceProjection,
    activation: str = "activated",
    authority_status: str = "available",
) -> ProviderManagementDescriptor:
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
        resources=resources or (_resource(),),
        provider_intent_activation=activation,
        provider_intent_authority_status=authority_status,
    )


async def _project(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    descriptor: ProviderManagementDescriptor,
    *,
    permitted: bool,
    schema: int = 2,
    corrupt: bool = False,
):
    import app.services.provider_management as service

    async def get_v2(
        provider_id: str, *, registry: object
    ) -> ProviderManagementDescriptor:
        assert provider_id == "proxmox"
        return descriptor

    monkeypatch.setattr(service, "get_provider_management_descriptor", get_v2)
    database = tmp_path / "provider_intents.db"
    ProviderIntentStore(database)
    if schema == 1:
        with sqlite3.connect(database) as connection:
            connection.execute("DROP TABLE provider_intent_operation_audit")
            connection.execute("DROP TABLE provider_intent_operations")
            connection.execute("DROP TABLE provider_intent_active_coordinates")
            connection.execute(
                "UPDATE provider_intent_store_meta SET schema_version=1"
            )
    elif corrupt:
        with sqlite3.connect(database) as connection:
            connection.execute("DROP TABLE provider_intent_active_coordinates")
    return await get_authenticated_provider_management_descriptor(
        "proxmox",
        caller_has_provider_intent_update=permitted,
        provider_intent_database=database,
    )


def test_v3_separates_static_support_permission_and_readiness(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    permitted = asyncio.run(
        _project(monkeypatch, tmp_path, _descriptor(), permitted=True)
    )
    resource = permitted.resources[0]
    assert permitted.schema_version == "provider-management-v3"
    assert permitted.caller_has_provider_intent_update is True
    assert resource.provider_intent_mutation_supported is True
    assert resource.mutation_readiness is ProviderIntentMutationReadiness.READY
    assert resource.editable_in_principle is True
    assert resource.caller_can_mutate is True
    assert resource.operationally_requestable is False
    assert resource.grants_permission is resource.grants_execution is False

    unauthorized = asyncio.run(
        _project(
            monkeypatch,
            tmp_path / "unauthorized",
            _descriptor(),
            permitted=False,
        )
    )
    assert unauthorized.resources[0].mutation_readiness.value == "ready"
    assert unauthorized.resources[0].caller_can_mutate is False
    assert unauthorized.resources[0].editable_in_principle is True


def test_v3_schema_v1_is_read_only_and_migration_required(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    descriptor = asyncio.run(
        _project(
            monkeypatch, tmp_path, _descriptor(), permitted=True, schema=1
        )
    )
    assert descriptor.resources[0].mutation_readiness.value == (
        "store_migration_required"
    )
    assert descriptor.resources[0].caller_can_mutate is False
    with sqlite3.connect(tmp_path / "provider_intents.db") as connection:
        assert connection.execute(
            "SELECT schema_version FROM provider_intent_store_meta"
        ).fetchone()[0] == 1


def test_v3_corrupt_schema_v2_store_is_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    descriptor = asyncio.run(
        _project(
            monkeypatch,
            tmp_path,
            _descriptor(),
            permitted=True,
            corrupt=True,
        )
    )
    assert descriptor.resources[0].mutation_readiness.value == "store_unavailable"
    assert descriptor.resources[0].caller_can_mutate is False


@pytest.mark.parametrize(
    ("resource", "reason"),
    (
        (
            _resource(
                resource_type="lxc",
                identity_assurance=ManagedResourceIdentityAssurance.UNAVAILABLE,
                management_fingerprint=None,
                intent_status=ProviderIntentReadStatus.UNSUPPORTED,
                intent_reason=ProviderIntentReadReason.RESOURCE_TYPE_UNSUPPORTED,
            ),
            "resource_type_unsupported",
        ),
        (
            _resource(
                missing=True,
                identity_assurance=ManagedResourceIdentityAssurance.UNAVAILABLE,
                management_fingerprint=None,
                intent_status=ProviderIntentReadStatus.MISSING,
                intent_reason=ProviderIntentReadReason.RESOURCE_MISSING,
                expectation=ProviderMonitoringExpectation.RUNNING,
                record_version=1,
            ),
            "resource_missing",
        ),
        (
            _resource(
                identity_assurance=ManagedResourceIdentityAssurance.UNAVAILABLE,
                management_fingerprint=None,
                intent_reason=ProviderIntentReadReason.IDENTITY_UNAVAILABLE,
            ),
            "identity_unavailable",
        ),
        (
            _resource(
                intent_reason=ProviderIntentReadReason.INCARNATION_MISMATCH,
                replacement_detected=True,
            ),
            "ready",
        ),
    ),
)
def test_v3_resource_readiness_is_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    resource: ManagedResourceProjection,
    reason: str,
) -> None:
    descriptor = asyncio.run(
        _project(monkeypatch, tmp_path, _descriptor(resource), permitted=True)
    )
    projected = descriptor.resources[0]
    assert projected.mutation_readiness.value == reason
    assert projected.caller_can_mutate is (reason == "ready")


@pytest.mark.parametrize(
    ("activation", "authority_status", "reason"),
    (
        ("not_activated", "available", "not_activated"),
        ("activated", "unavailable", "authority_unavailable"),
    ),
)
def test_v3_authority_state_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    activation: str,
    authority_status: str,
    reason: str,
) -> None:
    descriptor = asyncio.run(
        _project(
            monkeypatch,
            tmp_path,
            _descriptor(
                activation=activation,
                authority_status=authority_status,
            ),
            permitted=True,
        )
    )
    assert descriptor.resources[0].mutation_readiness.value == reason
    assert descriptor.resources[0].editable_in_principle is False


def test_v3_contract_is_strict_and_leaks_no_internal_authority() -> None:
    fields = set(ManagedResourceProjectionV3.model_fields)
    assert fields.isdisjoint(
        {
            "operator_id",
            "permissions",
            "intent_id",
            "import_id",
            "request_digest",
            "native_identity",
            "vmgenid",
            "old_fingerprint",
            "audit_id",
        }
    )
    with pytest.raises(ValidationError):
        ManagedResourceProjectionV3.model_validate(
            {
                **_resource().model_dump(exclude={"mutation_available"}),
                "resource_live": True,
                "provider_intent_mutation_supported": True,
                "mutation_readiness": "ready",
                "editable_in_principle": True,
                "caller_can_mutate": False,
                "operator_id": "injected",
            }
        )


def _valid_v3_resource_values() -> dict[str, object]:
    return {
        **_resource().model_dump(exclude={"mutation_available"}),
        "resource_live": True,
        "provider_intent_mutation_supported": True,
        "mutation_readiness": ProviderIntentMutationReadiness.READY,
        "editable_in_principle": True,
        "caller_can_mutate": False,
    }


@pytest.mark.parametrize(
    "overrides",
    (
        {"provider_intent_mutation_supported": False},
        {"resource_type": "lxc"},
        {"missing": True, "resource_live": False},
        {
            "identity_assurance": ManagedResourceIdentityAssurance.UNAVAILABLE,
            "management_fingerprint": None,
        },
        {
            "mutation_readiness": (
                ProviderIntentMutationReadiness.STORE_MIGRATION_REQUIRED
            ),
            "editable_in_principle": True,
        },
        {
            "mutation_readiness": (
                ProviderIntentMutationReadiness.AUTHORITY_UNAVAILABLE
            ),
            "editable_in_principle": True,
        },
    ),
)
def test_v3_model_rejects_contradictory_editable_resources(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        ManagedResourceProjectionV3.model_validate(
            {**_valid_v3_resource_values(), **overrides}
        )


def test_v3_ready_resource_without_caller_permission_is_structurally_valid() -> None:
    resource = ManagedResourceProjectionV3.model_validate(
        _valid_v3_resource_values()
    )
    assert resource.editable_in_principle is True
    assert resource.caller_can_mutate is False
