from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier

import pytest
from pydantic import ValidationError

from app.models.provider_intents import (
    ProviderIntentAuditEventKind,
    ProviderIntentCoordinateMutationCommand,
    ProviderIntentDomainAuditEvent,
    ProviderIntentLifecycle,
    ProviderIntentValue,
)
from app.provider_intents.store import (
    ProviderIntentStore,
    ProviderIntentStoreConflictError,
    ProviderIntentStoreCorruptionError,
    ProviderIntentStoreError,
)

NOW = datetime(2026, 8, 15, tzinfo=UTC)
FINGERPRINT_A = "provider-management-fingerprint-v1:" + "a" * 64
FINGERPRINT_B = "provider-management-fingerprint-v1:" + "b" * 64
FINGERPRINT_C = "provider-management-fingerprint-v1:" + "c" * 64


def command(
    suffix: str,
    *,
    fingerprint: str = FINGERPRINT_A,
    value: ProviderIntentValue = ProviderIntentValue.RUNNING,
    version: int = 0,
    operator: str = "operator@example.test",
) -> ProviderIntentCoordinateMutationCommand:
    return ProviderIntentCoordinateMutationCommand(
        operator_id=operator,
        request_id="provider-intent-mutation-" + suffix * 32,
        provider_id="proxmox",
        resource_type="qemu",
        resource_id="110",
        management_fingerprint=fingerprint,
        intent_kind="monitoring_expectation",
        desired_value=value,
        expected_record_version=version,
        acknowledge_monitoring_suppression=value is ProviderIntentValue.IGNORED,
    )


def test_command_is_strict_bounded_and_acknowledgement_is_exact() -> None:
    with pytest.raises(ValidationError):
        command("a").model_copy(update={"extra": "x"}).model_validate(
            {**command("a").model_dump(), "extra": "x"}
        )
    for override in (
        {"provider_id": "other"},
        {"resource_type": "lxc"},
        {"resource_id": "qemu/110"},
        {"management_fingerprint": "provider-management-fingerprint-v1:" + "A" * 64},
        {"operator_id": "operator secret"},
        {"request_id": "request-1"},
    ):
        with pytest.raises(ValidationError):
            ProviderIntentCoordinateMutationCommand.model_validate(
                {**command("a").model_dump(), **override}
            )
    with pytest.raises(ValidationError, match="acknowledgement"):
        ProviderIntentCoordinateMutationCommand.model_validate(
            {
                **command("a").model_dump(),
                "desired_value": ProviderIntentValue.IGNORED,
            }
        )


def test_domain_audit_rejects_contradictory_event_lifecycle() -> None:
    values = {
        "sequence": 1,
        "event_id": "provider-intent-audit-v1:" + "a" * 64,
        "occurred_at": NOW,
        "operation_id": "provider-intent-mutation-" + "a" * 32,
        "request_id": "provider-intent-mutation-" + "a" * 32,
        "operator_id": "operator@example.test",
        "intent_id": command("a").intent_id,
        "record_version": 1,
        "event": ProviderIntentAuditEventKind.UPDATED,
        "lifecycle": ProviderIntentLifecycle.SUPERSEDED,
        "resulting_value": ProviderIntentValue.RUNNING,
    }
    with pytest.raises(ValidationError, match="event and lifecycle contradict"):
        ProviderIntentDomainAuditEvent.model_validate(values)


def test_create_update_rebind_audit_and_replay_after_reopen(tmp_path: Path) -> None:
    path = tmp_path / "provider_intents.db"
    store = ProviderIntentStore(path)
    created = store.mutate_coordinate(command("a"), now=NOW)
    updated = store.mutate_coordinate(
        command("b", value=ProviderIntentValue.STOPPED, version=1),
        now=NOW + timedelta(seconds=1),
    )
    rebound_command = command(
        "c", fingerprint=FINGERPRINT_B, value=ProviderIntentValue.STOPPED
    )
    rebound = store.mutate_coordinate(
        rebound_command, now=NOW + timedelta(seconds=2)
    )

    assert (created.outcome, updated.outcome, rebound.outcome) == (
        "created", "updated", "rebound"
    )
    assert rebound.superseded_previous_incarnation is True
    assert [event.event.value for event in store.operation_audit()] == [
        "created", "updated", "superseded", "rebound"
    ]
    assert {event.operator_id for event in store.operation_audit()} == {
        "operator@example.test"
    }
    snapshot = store.read_snapshot()
    assert len(snapshot.active_identity_bound_records) == 1
    assert snapshot.active_identity_bound_records[0].incarnation_fingerprint == FINGERPRINT_B
    assert len(store.history(command("a").intent_id)) == 3
    assert ProviderIntentStore.open_existing(path).mutate_coordinate(
        rebound_command, now=NOW + timedelta(seconds=3)
    ) == rebound
    assert len(store.operation_audit()) == 4


def test_same_value_update_and_rebind_append_explicit_authorization(tmp_path: Path) -> None:
    store = ProviderIntentStore(tmp_path / "provider_intents.db")
    store.mutate_coordinate(command("a"), now=NOW)
    updated = store.mutate_coordinate(command("b", version=1), now=NOW)
    rebound = store.mutate_coordinate(
        command("c", fingerprint=FINGERPRINT_B), now=NOW
    )
    assert updated.record_version == 2
    assert rebound.outcome == "rebound"
    assert store.read_snapshot().active_identity_bound_records[0].intent_value is ProviderIntentValue.RUNNING


def test_stale_and_request_reuse_conflicts_leave_no_success_evidence(tmp_path: Path) -> None:
    path = tmp_path / "provider_intents.db"
    store = ProviderIntentStore(path)
    first = command("a")
    store.mutate_coordinate(first, now=NOW)
    with pytest.raises(ProviderIntentStoreConflictError, match="stale"):
        store.mutate_coordinate(command("b", version=0), now=NOW)
    with pytest.raises(ProviderIntentStoreConflictError, match="different input"):
        store.mutate_coordinate(
            command("a", value=ProviderIntentValue.STOPPED, version=1), now=NOW
        )
    with pytest.raises(ProviderIntentStoreConflictError, match="different input"):
        store.mutate_coordinate(command("a", operator="other"), now=NOW)
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM provider_intent_operations").fetchone()[0] == 1


@pytest.mark.parametrize(
    "stage",
    (
        "after_active_state_validation",
        "after_old_superseded_record_append",
        "after_new_record_append",
        "after_audit_event_1",
        "after_audit_event_2",
        "before_idempotency_result",
        "after_idempotency_result_before_commit",
    ),
)
def test_rebind_failure_injection_rolls_back_every_stage(
    tmp_path: Path, stage: str
) -> None:
    store = ProviderIntentStore(tmp_path / f"{stage}.db")
    store.mutate_coordinate(command("a"), now=NOW)
    initial = store.read_snapshot().active_identity_bound_records

    def fail(current: str) -> None:
        if current == stage:
            raise RuntimeError(stage)

    with pytest.raises(RuntimeError, match=stage):
        store.mutate_coordinate(
            command("b", fingerprint=FINGERPRINT_B),
            now=NOW + timedelta(seconds=1),
            failure_injector=fail,
        )
    reopened = ProviderIntentStore.open_existing(store.database_path)
    assert reopened.read_snapshot().active_identity_bound_records == initial
    assert reopened.operation_audit() == store.operation_audit()


def _race(path: Path, commands: tuple[ProviderIntentCoordinateMutationCommand, ...]):
    barrier = Barrier(len(commands))

    def invoke(item: ProviderIntentCoordinateMutationCommand):
        try:
            return ProviderIntentStore(path).mutate_coordinate(
                item,
                now=NOW,
                failure_injector=lambda stage: (
                    barrier.wait(timeout=5)
                    if stage == "after_active_state_observation"
                    else None
                ),
            )
        except ProviderIntentStoreConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=len(commands)) as executor:
        return tuple(executor.map(invoke, commands))


def test_concurrent_create_update_and_rebind_preserve_single_active(tmp_path: Path) -> None:
    create_path = tmp_path / "create.db"
    ProviderIntentStore(create_path)
    create_results = _race(create_path, (command("a"), command("b", fingerprint=FINGERPRINT_B)))
    assert sum(result == "conflict" for result in create_results) == 1

    update_path = tmp_path / "update.db"
    ProviderIntentStore(update_path).mutate_coordinate(command("c"), now=NOW)
    update_results = _race(
        update_path,
        (
            command("d", value=ProviderIntentValue.STOPPED, version=1),
            command("e", value=ProviderIntentValue.IGNORED, version=1),
        ),
    )
    assert sum(result == "conflict" for result in update_results) == 1

    rebind_path = tmp_path / "rebind.db"
    ProviderIntentStore(rebind_path).mutate_coordinate(command("f"), now=NOW)
    rebind_results = _race(
        rebind_path,
        (command("1", fingerprint=FINGERPRINT_B), command("2", fingerprint=FINGERPRINT_C)),
    )
    assert sum(result == "conflict" for result in rebind_results) == 1
    assert len(ProviderIntentStore.open_existing(rebind_path).read_snapshot().active_identity_bound_records) == 1


def test_concurrent_update_and_rebind_recheck_the_observed_generation(
    tmp_path: Path,
) -> None:
    path = tmp_path / "update-rebind.db"
    ProviderIntentStore(path).mutate_coordinate(command("a"), now=NOW)
    barrier = Barrier(2)

    def invoke(item: ProviderIntentCoordinateMutationCommand):
        try:
            return ProviderIntentStore(path).mutate_coordinate(
                item,
                now=NOW + timedelta(seconds=1),
                failure_injector=lambda stage: (
                    barrier.wait(timeout=5)
                    if stage == "after_active_state_observation"
                    else None
                ),
            )
        except ProviderIntentStoreConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(
            executor.map(
                invoke,
                (
                    command("b", value=ProviderIntentValue.STOPPED, version=1),
                    command("c", fingerprint=FINGERPRINT_B),
                ),
            )
        )
    assert sum(result == "conflict" for result in results) == 1
    assert len(
        ProviderIntentStore.open_existing(path).read_snapshot().active_identity_bound_records
    ) == 1


def test_corrupt_multiple_active_state_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "provider_intents.db"
    store = ProviderIntentStore(path)
    store.mutate_coordinate(command("a"), now=NOW)
    with sqlite3.connect(path) as connection:
        connection.execute("DROP TABLE provider_intent_active_coordinates")
    with pytest.raises((ProviderIntentStoreCorruptionError, ProviderIntentStoreError)):
        store.mutate_coordinate(command("b"), now=NOW)
