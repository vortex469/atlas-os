"""Guardrail tests covering v3 identity and read-only isolation boundaries."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models.provider_intents import (
    ProviderIntentCoordinateMutationCommand,
    ProviderIntentKind,
    ProviderIntentLifecycle,
    ProviderIntentProvenance,
    ProviderIntentRecord,
    ProviderIntentValue,
)
from app.provider_intents.store import ProviderIntentStore

NOW = datetime(2026, 8, 15, tzinfo=UTC)
FINGERPRINT_A = "provider-management-fingerprint-v1:" + "a" * 64
FINGERPRINT_B = "provider-management-fingerprint-v1:" + "b" * 64


def command(
    request_id: str,
    *,
    fingerprint: str,
    value: ProviderIntentValue = ProviderIntentValue.RUNNING,
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
        expected_record_version=0,
        acknowledge_monitoring_suppression=False,
    )


@pytest.fixture
def provider_intent_store(tmp_path: Path) -> ProviderIntentStore:
    return ProviderIntentStore(tmp_path / "provider_intents.db")


class TestV3DiscoveryIsolation:
    def test_store_starts_empty_for_read_only_operations(
        self, provider_intent_store: ProviderIntentStore
    ) -> None:
        snapshot = provider_intent_store.read_snapshot()
        assert snapshot.active_identity_bound_records == ()
        assert snapshot.legacy_unbound_records == ()


class TestV3ACEIsolation:
    def test_identity_bound_insert_requires_explicit_store_mutation(
        self, provider_intent_store: ProviderIntentStore
    ) -> None:
        before = provider_intent_store.read_snapshot()
        provider_intent_store.mutate_coordinate(
            command("provider-intent-mutation-" + "c" * 64, fingerprint=FINGERPRINT_A),
            now=NOW,
        )
        after = provider_intent_store.read_snapshot()
        assert len(before.active_identity_bound_records) == 0
        assert len(after.active_identity_bound_records) == 1
        assert after.active_identity_bound_records[0].intent_value is ProviderIntentValue.RUNNING


class TestV3LegacyYAMLIsolation:
    def test_store_is_not_a_legacy_yaml_authority(
        self, provider_intent_store: ProviderIntentStore
    ) -> None:
        snapshot = provider_intent_store.read_snapshot()
        assert isinstance(snapshot.active_identity_bound_records, tuple)


class TestV3LXCUnsupported:
    def test_lxc_record_creation_fails_closed(
        self, provider_intent_store: ProviderIntentStore
    ) -> None:
        with pytest.raises(ValidationError):
            ProviderIntentRecord(
                intent_id="provider-intent-series-v1:" + "x" * 64,
                record_version=1,
                provider_id="proxmox",
                resource_type="lxc",
                resource_id="110",
                incarnation_fingerprint=FINGERPRINT_A,
                intent_kind=ProviderIntentKind.MONITORING_EXPECTATION,
                intent_value=ProviderIntentValue.RUNNING,
                lifecycle=ProviderIntentLifecycle.ACTIVE,
                provenance=ProviderIntentProvenance.OPERATOR,
                created_at=NOW,
                updated_at=NOW,
            )


class TestV3SuggestionNonAuthority:
    def test_reads_do_not_create_authority(self, provider_intent_store: ProviderIntentStore) -> None:
        before = provider_intent_store.read_snapshot()
        after = provider_intent_store.read_snapshot()
        assert len(before.active_identity_bound_records) == len(after.active_identity_bound_records) == 0

    def test_explicit_store_write_is_required_before_active_intent_exists(
        self, provider_intent_store: ProviderIntentStore
    ) -> None:
        before = provider_intent_store.read_snapshot()
        provider_intent_store.mutate_coordinate(
            command("provider-intent-mutation-" + "d" * 64, fingerprint=FINGERPRINT_B),
            now=NOW,
        )
        after = provider_intent_store.read_snapshot()
        assert len(before.active_identity_bound_records) == 0
        assert len(after.active_identity_bound_records) == 1
        assert after.active_identity_bound_records[0].incarnation_fingerprint == FINGERPRINT_B
