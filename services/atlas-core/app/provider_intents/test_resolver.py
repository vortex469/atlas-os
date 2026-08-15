from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.config.settings import ProviderIntentActivation, ProviderIntentSettings
from app.models.provider_intents import (
    ProviderIntentValue,
)
from app.models.provider_management import (
    ManagedResourceIdentityAssurance,
    ManagedResourceProjection,
)
from app.provider_intents.legacy_import import import_legacy_policy
from app.provider_intents.resolver import (
    ProviderIntentResolutionReason,
    ProviderIntentResolutionStatus,
    ProviderMonitoringIntentResolver,
)
from app.provider_intents.store import (
    ProviderIntentStore,
    ProviderIntentStoreCorruptionError,
)
from app.provider_intents.test_store import command

NOW = datetime(2026, 8, 15, tzinfo=UTC)
FINGERPRINT_A = "provider-management-fingerprint-v1:" + "a" * 64
FINGERPRINT_B = "provider-management-fingerprint-v1:" + "b" * 64
FINGERPRINT_C = "provider-management-fingerprint-v1:" + "c" * 64
IMPORT_ID = "provider-intent-legacy-policy-import-v1:" + "d" * 64


def activated(database: Path) -> ProviderIntentSettings:
    return ProviderIntentSettings(
        activation=ProviderIntentActivation.ACTIVATED,
        database=str(database),
        expected_legacy_import_id=IMPORT_ID,
    )


def snapshot(
    resource_id: str = "110",
    *,
    resource_type: str = "qemu",
    fingerprint: str | None = FINGERPRINT_A,
    missing: bool = False,
) -> ManagedResourceProjection:
    return ManagedResourceProjection(
        provider_id="proxmox",
        resource_id=resource_id,
        resource_type=resource_type,
        display_name=f"Resource {resource_id}",
        current_state="running",
        missing=missing,
        identity_assurance=(
            ManagedResourceIdentityAssurance.AUTHORITATIVE
            if fingerprint is not None
            else ManagedResourceIdentityAssurance.UNAVAILABLE
        ),
        management_fingerprint=fingerprint,
    )


def test_matching_and_ignored_active_qemu_are_configured(tmp_path: Path) -> None:
    store = ProviderIntentStore(tmp_path / "provider_intents.db")
    running = store.put(command("create-running", fingerprint=FINGERPRINT_A), now=NOW)
    ignored = store.put(
        command(
            "create-ignored",
            fingerprint=FINGERPRINT_B,
            value=ProviderIntentValue.IGNORED,
        ),
        now=NOW,
    )
    resolver = ProviderMonitoringIntentResolver(activated(Path(store.database_path)), store)

    first = resolver.resolve((snapshot(fingerprint=FINGERPRINT_A),)).resources[0]
    second = resolver.resolve((snapshot(fingerprint=FINGERPRINT_B),)).resources[0]
    assert first.status is ProviderIntentResolutionStatus.CONFIGURED
    assert first.reason is ProviderIntentResolutionReason.MATCHING_ACTIVE_INTENT
    assert first.expectation is ProviderIntentValue.RUNNING
    assert first.record_version == running.record.record_version
    assert second.expectation is ProviderIntentValue.IGNORED
    assert second.record_version == ignored.record.record_version


def test_no_active_legacy_only_and_identity_unavailable(tmp_path: Path) -> None:
    database = tmp_path / "provider_intents.db"
    policy = tmp_path / "policies.yaml"
    policy.write_text(
        'proxmox:\n  guests:\n    "109":\n      expected: stopped\n',
        encoding="utf-8",
    )
    import_legacy_policy(policy, database, now=NOW)
    store = ProviderIntentStore.open_existing(database)
    resolver = ProviderMonitoringIntentResolver(activated(database), store)
    results = resolver.resolve(
        (
            snapshot("108"),
            snapshot("109"),
            snapshot("109", fingerprint=None),
        )
    ).resources
    by_reason = {item.reason: item for item in results}
    assert by_reason[ProviderIntentResolutionReason.NO_ACTIVE_INTENT].expectation is None
    legacy = by_reason[ProviderIntentResolutionReason.LEGACY_UNBOUND_EVIDENCE]
    assert legacy.expectation is None
    assert legacy.legacy_expectation is ProviderIntentValue.STOPPED
    unavailable = by_reason[ProviderIntentResolutionReason.IDENTITY_UNAVAILABLE]
    assert unavailable.expectation is None


def test_replacement_multiple_incarnations_and_exact_match_wins(tmp_path: Path) -> None:
    store = ProviderIntentStore(tmp_path / "provider_intents.db")
    store.put(command("create-a", fingerprint=FINGERPRINT_A), now=NOW)
    store.put(
        command(
            "create-b",
            fingerprint=FINGERPRINT_B,
            value=ProviderIntentValue.STOPPED,
        ),
        now=NOW + timedelta(seconds=1),
    )
    resolver = ProviderMonitoringIntentResolver(activated(Path(store.database_path)), store)

    replacement = resolver.resolve((snapshot(fingerprint=FINGERPRINT_C),)).resources[0]
    assert replacement.status is ProviderIntentResolutionStatus.NEEDS_REVIEW
    assert replacement.reason is ProviderIntentResolutionReason.INCARNATION_MISMATCH
    assert replacement.replacement_detected is True
    assert replacement.expectation is None

    matching = resolver.resolve((snapshot(fingerprint=FINGERPRINT_B),)).resources[0]
    assert matching.status is ProviderIntentResolutionStatus.CONFIGURED
    assert matching.expectation is ProviderIntentValue.STOPPED


def test_lxc_is_unsupported_and_legacy_evidence_is_only_review_context(
    tmp_path: Path,
) -> None:
    database = tmp_path / "provider_intents.db"
    policy = tmp_path / "policies.yaml"
    policy.write_text(
        'proxmox:\n  guests:\n    "109":\n      expected: running\n',
        encoding="utf-8",
    )
    import_legacy_policy(policy, database, now=NOW)
    store = ProviderIntentStore.open_existing(database)
    result = ProviderMonitoringIntentResolver(activated(database), store).resolve(
        (snapshot("109", resource_type="lxc", fingerprint=None),)
    ).resources[0]
    assert result.status is ProviderIntentResolutionStatus.UNSUPPORTED
    assert result.reason is ProviderIntentResolutionReason.RESOURCE_TYPE_UNSUPPORTED
    assert result.expectation is None
    assert result.legacy_review_available is True


def test_active_record_without_live_coordinate_is_missing(tmp_path: Path) -> None:
    store = ProviderIntentStore(tmp_path / "provider_intents.db")
    created = store.put(command("create-a", fingerprint=FINGERPRINT_A), now=NOW)
    result = ProviderMonitoringIntentResolver(
        activated(Path(store.database_path)), store
    ).resolve(()).resources[0]
    assert result.status is ProviderIntentResolutionStatus.MISSING
    assert result.reason is ProviderIntentResolutionReason.RESOURCE_MISSING
    assert result.expectation is ProviderIntentValue.RUNNING
    assert result.record_version == created.record.record_version
    supplied_missing = snapshot(fingerprint=None, missing=True)
    assert ProviderMonitoringIntentResolver(
        activated(Path(store.database_path)), store
    ).resolve((supplied_missing,)).resources == (result,)


def test_inactive_and_failed_authority_never_fall_back_to_yaml(tmp_path: Path) -> None:
    inactive = ProviderMonitoringIntentResolver(
        ProviderIntentSettings(database=str(tmp_path / "absent.db")), None
    ).resolve((snapshot(),))
    assert inactive.authority_available is False
    assert inactive.resources[0].reason is (
        ProviderIntentResolutionReason.AUTHORITY_NOT_ACTIVATED
    )

    class FailedStore:
        def read_snapshot(self) -> tuple:
            raise ProviderIntentStoreCorruptionError("failed")

    failed = ProviderMonitoringIntentResolver(
        activated(tmp_path / "failed.db"), FailedStore()  # type: ignore[arg-type]
    ).resolve((snapshot(),))
    assert failed.authority_available is False
    assert failed.resources[0].status is ProviderIntentResolutionStatus.UNAVAILABLE
    assert failed.resources[0].reason is (
        ProviderIntentResolutionReason.AUTHORITY_STORE_UNAVAILABLE
    )


def test_reads_are_deterministic_and_do_not_write_store_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database = tmp_path / "provider_intents.db"
    store = ProviderIntentStore(database)
    store.put(command("create-a", fingerprint=FINGERPRINT_A), now=NOW)
    resolver = ProviderMonitoringIntentResolver(activated(database), store)
    original_read_snapshot = store.read_snapshot
    read_count = 0

    def counted_read_snapshot():
        nonlocal read_count
        read_count += 1
        return original_read_snapshot()

    monkeypatch.setattr(store, "read_snapshot", counted_read_snapshot)
    with sqlite3.connect(database) as connection:
        before = tuple(
            connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "provider_intent_records",
                "provider_intent_audit",
                "provider_intent_requests",
            )
        )
    database_bytes = database.read_bytes()
    database_mtime = database.stat().st_mtime_ns
    first = resolver.resolve((snapshot(),))
    second = resolver.resolve((snapshot(),))
    assert first == second
    assert read_count == 2
    with sqlite3.connect(database) as connection:
        after = tuple(
            connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "provider_intent_records",
                "provider_intent_audit",
                "provider_intent_requests",
            )
        )
    assert after == before
    assert database.read_bytes() == database_bytes
    assert database.stat().st_mtime_ns == database_mtime


def test_resolver_has_no_provider_network_or_execution_dependencies() -> None:
    source = Path(__file__).with_name("resolver.py").read_text(encoding="utf-8")
    for forbidden in (
        "providers.proxmox",
        "provider_actions",
        "operational_dispatch",
        "execution_candidates",
        "approval",
        "discovery",
        "selector",
        "handler",
        "execution_gate",
        "httpx",
        "requests",
        "policies.yaml",
    ):
        assert forbidden not in source.casefold()


def test_existing_production_authority_consumers_remain_unchanged() -> None:
    app_root = Path(__file__).parents[1]
    runtime = (app_root / "services" / "runtime_resolver.py").read_text(
        encoding="utf-8"
    )
    provider = (app_root / "providers" / "proxmox.py").read_text(encoding="utf-8")
    intelligence = (app_root / "intelligence" / "proxmox_rules.py").read_text(
        encoding="utf-8"
    )
    main = (app_root / "main.py").read_text(encoding="utf-8")
    assert "policy_config.load_policies" in runtime
    assert "reader.list_guest_expectations" in provider
    assert "get_expected_guest_state" in intelligence
    assert "ProviderMonitoringIntentResolver" not in main
    assert ProviderIntentSettings().activation is ProviderIntentActivation.NOT_ACTIVATED
