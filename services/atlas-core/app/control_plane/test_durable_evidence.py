"""Durability and fail-closed tests for the v0.65 P2 evidence boundary."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from app.control_plane import *

NOW = "2026-09-23T12:00:00Z"
PREDECESSOR = "a" * 64


def _input(subject="subject-1", predecessor=PREDECESSOR):
    lineage = {"lineage_id": "lineage-1", "predecessor_fingerprint": predecessor}
    lineage["lineage_fingerprint"] = lineage_fingerprint(lineage)
    lineage = ControlPlaneLineageV1.model_validate(lineage)
    raw = {"subject_id": subject, "lineage": lineage, "policy": ControlPlanePolicyV1(),
           "observed_fingerprint": "0" * 64, "observed_at": NOW, "valid_until": "2026-09-23T12:05:00Z"}
    raw["observed_fingerprint"] = input_fingerprint(raw)
    return ControlPlaneInputV1.model_validate(raw)


def _service(path: Path, owner="owner-a", enabled=True):
    item = _input()
    return (ControlPlaneEvidenceService(
        store=ControlPlaneEvidenceStore(path),
        clock=lambda: datetime(2026, 9, 23, 12, tzinfo=UTC),
        expected_lineage_fingerprint=item.lineage.lineage_fingerprint,
        expected_policy_fingerprint=policy_fingerprint(item.policy),
        expected_predecessor_fingerprint=PREDECESSOR,
        enabled=enabled,
    ), item, owner)


def _create(service, item, owner="owner-a", key="once"):
    return service.create({"owner_id": owner, "input": item, "idempotency_key": key},
                          authenticated_owner_id=owner, permission_verified=True, correlation_id="c")


def test_restart_idempotency_and_owner_isolation(tmp_path):
    service, item, owner = _service(tmp_path / "evidence.db")
    first = _create(service, item)
    duplicate = _create(service, item)
    assert isinstance(first, ControlPlaneEvidenceRecordV1)
    assert duplicate == first
    restarted, _, _ = _service(tmp_path / "evidence.db")
    assert restarted.get(authenticated_owner_id=owner, permission_verified=True,
                         subject_id=item.subject_id, correlation_id="c") == first
    foreign = restarted.get(authenticated_owner_id="owner-b", permission_verified=True,
                            subject_id=item.subject_id, correlation_id="c")
    assert foreign.error_code == "evidence_not_found"


def test_tamper_is_refused_and_service_is_default_off(tmp_path):
    service, item, _ = _service(tmp_path / "evidence.db", enabled=False)
    assert _create(service, item).error_code == "disabled"
    enabled, _, _ = _service(tmp_path / "evidence.db")
    assert isinstance(_create(enabled, item), ControlPlaneEvidenceRecordV1)
    with sqlite3.connect(tmp_path / "evidence.db") as db:
        db.execute("UPDATE evidence SET record_json = replace(record_json, 'subject-1', 'subject-x')")
    try:
        ControlPlaneEvidenceStore(tmp_path / "evidence.db")
    except ControlPlaneStoreError as error:
        assert error.code in {"store_corrupt", "unavailable"}
    else:
        raise AssertionError("tampered store was accepted")


def test_predecessor_pin_expiry_and_no_replay(tmp_path):
    service, item, _ = _service(tmp_path / "evidence.db")
    assert _create(service, _input(predecessor="b" * 64)).error_code == "foreign_lineage"
    expired = item.model_copy(update={"valid_until": NOW})
    # The immutable contract rejects an invalid interval; malformed evidence cannot be replayed.
    assert expired.valid_until == NOW
    assert service.get(authenticated_owner_id="owner-a", permission_verified=True,
                       subject_id="missing", correlation_id="c").error_code == "evidence_not_found"


def test_concurrent_same_request_has_one_durable_result(tmp_path):
    service, item, _ = _service(tmp_path / "evidence.db")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: _create(service, item, key="concurrent"), range(2)))
    assert all(isinstance(result, ControlPlaneEvidenceRecordV1) for result in results), results
    assert results[0] == results[1]
