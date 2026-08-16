from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import pytest

from app.config.settings import ProviderIntentActivation, ProviderIntentSettings
from app.models.provider_intents import (
    ProviderIntentMutationRequest,
    ProviderIntentValue,
    VerifiedProviderIntentMutationTarget,
)
from app.models.provider_management import (
    ManagedResourceIdentityAssurance,
    ManagedResourceProjection,
)
from app.provider_intents.mutation import (
    ProviderIntentMutationFailureReason,
    ProviderIntentMutationServiceError,
    mutate_provider_monitoring_intent,
)
from app.provider_intents.resolver import (
    ProviderIntentResolutionReason,
    ProviderMonitoringIntentResolver,
)
from app.provider_intents.store import ProviderIntentStore

FINGERPRINT_A = "provider-management-fingerprint-v1:" + "a" * 64
FINGERPRINT_B = "provider-management-fingerprint-v1:" + "b" * 64


def request(
    suffix: str,
    *,
    fingerprint: str = FINGERPRINT_A,
    value: ProviderIntentValue = ProviderIntentValue.RUNNING,
    version: int = 0,
) -> ProviderIntentMutationRequest:
    return ProviderIntentMutationRequest(
        request_id="provider-intent-mutation-" + suffix * 32,
        expected_management_fingerprint=fingerprint,
        expectation=value,
        expected_record_version=version,
        acknowledge_monitoring_suppression=value is ProviderIntentValue.IGNORED,
    )


def invoke(path: Path, item: ProviderIntentMutationRequest, **updates):
    values = {
        "operator_id": "session-operator",
        "provider_id": "proxmox",
        "resource_type": "qemu",
        "resource_id": "110",
        "request": item,
        "activation": ProviderIntentActivation.ACTIVATED,
        "store_path": path,
    }
    values.update(updates)
    return asyncio.run(mutate_provider_monitoring_intent(**values))


@pytest.fixture(autouse=True)
def verified_target(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.provider_intents import mutation

    async def verify(**values):
        return VerifiedProviderIntentMutationTarget(
            provider_id="proxmox",
            resource_type="qemu",
            resource_id=values["resource_id"],
            management_fingerprint=values["expected_management_fingerprint"],
        )

    monkeypatch.setattr(mutation, "resolve_provider_intent_mutation_target", verify)


def test_service_create_update_rebind_and_session_actor(tmp_path: Path) -> None:
    path = tmp_path / "provider_intents.db"
    store = ProviderIntentStore(path)
    created = invoke(path, request("a"))
    updated = invoke(
        path,
        request("b", value=ProviderIntentValue.STOPPED, version=1),
    )
    rebound = invoke(
        path,
        request(
            "c",
            fingerprint=FINGERPRINT_B,
            value=ProviderIntentValue.IGNORED,
        ),
    )
    assert (created.outcome, updated.outcome, rebound.outcome) == (
        "created", "updated", "rebound"
    )
    assert rebound.superseded_previous_incarnation is True
    assert {event.operator_id for event in store.operation_audit()} == {
        "session-operator"
    }
    assert store.read_snapshot().active_identity_bound_records[
        0
    ].incarnation_fingerprint == FINGERPRINT_B


def test_service_stale_cas_idempotency_and_request_conflict(tmp_path: Path) -> None:
    path = tmp_path / "provider_intents.db"
    ProviderIntentStore(path)
    original = request("a")
    first = invoke(path, original)
    assert invoke(path, original) == first
    with pytest.raises(ProviderIntentMutationServiceError) as captured:
        invoke(path, request("b", version=0))
    assert captured.value.reason is ProviderIntentMutationFailureReason.CAS_CONFLICT
    with pytest.raises(ProviderIntentMutationServiceError) as captured:
        invoke(
            path,
            request("a", value=ProviderIntentValue.STOPPED, version=1),
        )
    assert captured.value.reason is ProviderIntentMutationFailureReason.REQUEST_CONFLICT
    assert len(ProviderIntentStore.open_existing(path).operation_audit()) == 1


def test_service_requires_activated_exact_p3_store(tmp_path: Path) -> None:
    missing = tmp_path / "missing.db"
    with pytest.raises(ProviderIntentMutationServiceError) as captured:
        invoke(missing, request("a"))
    assert captured.value.reason is ProviderIntentMutationFailureReason.STORE_UNAVAILABLE
    assert not missing.exists()

    p2c = tmp_path / "p2c.db"
    ProviderIntentStore(p2c)
    with sqlite3.connect(p2c) as connection:
        connection.execute("DROP TABLE provider_intent_operation_audit")
        connection.execute("DROP TABLE provider_intent_operations")
        connection.execute("DROP TABLE provider_intent_active_coordinates")
        connection.execute("UPDATE provider_intent_store_meta SET schema_version=1")
    with pytest.raises(ProviderIntentMutationServiceError) as captured:
        invoke(p2c, request("b"))
    assert (
        captured.value.reason
        is ProviderIntentMutationFailureReason.STORE_MIGRATION_REQUIRED
    )
    with sqlite3.connect(p2c) as connection:
        assert connection.execute(
            "SELECT schema_version FROM provider_intent_store_meta"
        ).fetchone()[0] == 1

    corrupt = tmp_path / "corrupt.db"
    corrupt.write_bytes(b"not sqlite")
    with pytest.raises(ProviderIntentMutationServiceError) as captured:
        invoke(corrupt, request("c"))
    assert captured.value.reason is ProviderIntentMutationFailureReason.STORE_UNAVAILABLE

    p3 = tmp_path / "inactive.db"
    ProviderIntentStore(p3)
    with pytest.raises(ProviderIntentMutationServiceError) as captured:
        invoke(
            p3,
            request("d"),
            activation=ProviderIntentActivation.NOT_ACTIVATED,
        )
    assert (
        captured.value.reason
        is ProviderIntentMutationFailureReason.MUTATION_NOT_ACTIVATED
    )


def test_mutation_dependencies_exclude_execution_and_policy_domains() -> None:
    package = Path(__file__).parent
    source = "\n".join(
        (package / name).read_text(encoding="utf-8").casefold()
        for name in ("mutation.py", "target_resolver.py")
    )
    for forbidden in (
        "operational_dispatch",
        "execution_candidates",
        "operator_intents",
        "provider_actions",
        "planning",
        "approval",
        "discovery",
        "execution_gate",
        "handler_registry",
        "update_proxmox_guest_expectation",
        "policies.yaml",
    ):
        assert forbidden not in source


def test_identity_change_after_verification_cannot_transfer_intent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.provider_intents import mutation

    path = tmp_path / "provider_intents.db"
    store = ProviderIntentStore(path)

    async def verify(**values):
        return VerifiedProviderIntentMutationTarget(
            provider_id="proxmox",
            resource_type="qemu",
            resource_id="110",
            management_fingerprint=FINGERPRINT_A,
        )

    monkeypatch.setattr(mutation, "resolve_provider_intent_mutation_target", verify)
    invoke(path, request("a", fingerprint=FINGERPRINT_A))
    record = store.read_snapshot().active_identity_bound_records[0]
    assert record.incarnation_fingerprint == FINGERPRINT_A

    resolver = ProviderMonitoringIntentResolver(
        ProviderIntentSettings(
            activation=ProviderIntentActivation.ACTIVATED,
            database=str(path),
            expected_legacy_import_id=(
                "provider-intent-legacy-policy-import-v1:" + "f" * 64
            ),
        ),
        store,
    )
    resolution = resolver.resolve(
        (
            ManagedResourceProjection(
                provider_id="proxmox",
                resource_type="qemu",
                resource_id="110",
                display_name="Replacement",
                current_state="running",
                identity_assurance=(
                    ManagedResourceIdentityAssurance.AUTHORITATIVE
                ),
                management_fingerprint=FINGERPRINT_B,
            ),
        )
    ).resources[0]
    assert resolution.reason is ProviderIntentResolutionReason.INCARNATION_MISMATCH
    assert resolution.expectation is None
