"""Data-backed v3 regression checks against the real Atlas store API."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.models.provider_intents import (
    ProviderIntentCoordinateMutationCommand,
    ProviderIntentKind,
    ProviderIntentValue,
)
from app.provider_intents.store import (
    ProviderIntentStore,
    ProviderIntentStoreConflictError,
)

NOW = datetime(2026, 8, 15, tzinfo=UTC)
FINGERPRINT_A = "provider-management-fingerprint-v1:" + "a" * 64
FINGERPRINT_B = "provider-management-fingerprint-v1:" + "b" * 64


def coordinate_command(
    request_id: str,
    *,
    fingerprint: str,
    value: ProviderIntentValue = ProviderIntentValue.RUNNING,
    expected_version: int = 0,
) -> ProviderIntentCoordinateMutationCommand:
    return ProviderIntentCoordinateMutationCommand(
        operator_id="operator@example.test",
        request_id=request_id,
        provider_id="proxmox",
        resource_type="qemu",
        resource_id="110",
        management_fingerprint=fingerprint,
        intent_kind=ProviderIntentKind.MONITORING_EXPECTATION,
        desired_value=value,
        expected_record_version=expected_version,
        acknowledge_monitoring_suppression=False,
    )


@pytest.fixture
def provider_intent_store(tmp_path: Path) -> ProviderIntentStore:
    return ProviderIntentStore(tmp_path / "provider_intents.db")


class TestV3Idempotency:
    def test_exact_mutation_replay_returns_original_result(
        self, provider_intent_store: ProviderIntentStore
    ) -> None:
        request_id = "provider-intent-mutation-" + "a" * 64
        command = coordinate_command(request_id, fingerprint=FINGERPRINT_A)

        first = provider_intent_store.mutate_coordinate(command, now=NOW)
        replay = provider_intent_store.mutate_coordinate(command, now=NOW + timedelta(seconds=1))

        assert first.outcome == "created"
        assert replay == first
        snapshot = provider_intent_store.read_snapshot()
        assert len(snapshot.active_identity_bound_records) == 1
        assert snapshot.active_identity_bound_records[0].incarnation_fingerprint == FINGERPRINT_A
        assert snapshot.active_identity_bound_records[0].record_version == 1

    def test_changed_request_with_reused_id_conflicts(
        self, provider_intent_store: ProviderIntentStore
    ) -> None:
        request_id = "provider-intent-mutation-" + "b" * 64
        original = coordinate_command(request_id, fingerprint=FINGERPRINT_A)
        provider_intent_store.mutate_coordinate(original, now=NOW)

        changed = coordinate_command(
            request_id,
            fingerprint=FINGERPRINT_B,
            value=ProviderIntentValue.STOPPED,
            expected_version=1,
        )
        with pytest.raises(ProviderIntentStoreConflictError, match="different input|stale"):
            provider_intent_store.mutate_coordinate(changed, now=NOW + timedelta(seconds=1))


class TestV3ReplacementIsolation:
    def test_rebinding_to_new_fingerprint_creates_new_incarnation(
        self, provider_intent_store: ProviderIntentStore
    ) -> None:
        first = provider_intent_store.mutate_coordinate(
            coordinate_command("provider-intent-mutation-" + "c" * 64, fingerprint=FINGERPRINT_A),
            now=NOW,
        )

        rebound = provider_intent_store.mutate_coordinate(
            coordinate_command("provider-intent-mutation-" + "d" * 64, fingerprint=FINGERPRINT_B),
            now=NOW + timedelta(seconds=1),
        )

        assert first.outcome == "created"
        assert rebound.outcome == "rebound"
        snapshot = provider_intent_store.read_snapshot()
        assert len(snapshot.active_identity_bound_records) == 1
        assert snapshot.active_identity_bound_records[0].incarnation_fingerprint == FINGERPRINT_B
        assert snapshot.active_identity_bound_records[0].record_version == 1

    def test_rebound_keeps_stale_incarnation_in_history(
        self, provider_intent_store: ProviderIntentStore
    ) -> None:
        first = provider_intent_store.mutate_coordinate(
            coordinate_command("provider-intent-mutation-" + "e" * 64, fingerprint=FINGERPRINT_A),
            now=NOW,
        )
        provider_intent_store.mutate_coordinate(
            coordinate_command("provider-intent-mutation-" + "f" * 64, fingerprint=FINGERPRINT_B),
            now=NOW + timedelta(seconds=1),
        )

        assert first.outcome == "created"
        snapshot = provider_intent_store.read_snapshot()
        assert len(snapshot.active_identity_bound_records) == 1
        assert snapshot.active_identity_bound_records[0].incarnation_fingerprint == FINGERPRINT_B
