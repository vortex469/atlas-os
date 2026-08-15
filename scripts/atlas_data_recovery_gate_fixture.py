"""Disposable v3 recovery-gate fixture creation and verification."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path

UID = 10001
GID = 10001


def _digest(prefix: str, payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"{prefix}:{hashlib.sha256(encoded.encode()).hexdigest()}"


def dispatching_request() -> dict[str, object]:
    generated_at = "2026-01-01T00:00:00+00:00"
    expires_at = "2026-01-02T00:00:00+00:00"
    verification = {
        "pre_state": "running",
        "expected_post_state": "running-and-healthy",
        "identity_fingerprint": "target-fingerprint-v1:bounded",
        "health_requirement": "healthy",
        "unknown_outcome_policy": "stop-and-reconcile",
    }
    verification_digest = _digest(
        "operational-verification-digest-v1",
        {
            **verification,
            "version": "operational-verification-digest-v1",
        },
    )
    values: dict[str, object] = {
        "schema_version": 1,
        "request_id": "dispatching-request",
        "request_digest": "pending",
        "idempotency_key": "pending",
        "workflow_session_id": "workflow",
        "candidate_planning_session_id": "planning",
        "candidate_id": "candidate",
        "candidate_fingerprint": "candidate-fingerprint-v1:bounded",
        "candidate_plan_id": "plan",
        "candidate_plan_fingerprint": "plan-fingerprint-v1:bounded",
        "effect_kind": "operational_action",
        "execution_intent": "restart-service",
        "provider_id": "proxmox",
        "resource_id": "qemu/101",
        "resource_type": "qemu",
        "provider_action_id": "proxmox-qemu-graceful-restart-v1",
        "target_fingerprint": "target-fingerprint-v1:bounded",
        "target_version": "uid-v1",
        "expected_pre_state": "running",
        "disruption_scope": "one service interruption",
        "evidence_ids": ["evidence"],
        "verification": verification,
        "generated_at": generated_at,
        "expires_at": expires_at,
        "translator_version": "operational-action-translator-v1",
    }
    request_payload = {
        "candidate_fingerprint": values["candidate_fingerprint"],
        "candidate_id": values["candidate_id"],
        "candidate_plan_fingerprint": values["candidate_plan_fingerprint"],
        "candidate_plan_id": values["candidate_plan_id"],
        "candidate_planning_session_id": values["candidate_planning_session_id"],
        "disruption_scope": values["disruption_scope"],
        "effect_kind": values["effect_kind"],
        "evidence_ids": sorted(values["evidence_ids"]),
        "execution_intent": values["execution_intent"],
        "expected_pre_state": values["expected_pre_state"],
        "expires_at": expires_at,
        "generated_at": generated_at,
        "provider_action_id": values["provider_action_id"],
        "provider_id": values["provider_id"],
        "request_id": values["request_id"],
        "resource_id": values["resource_id"],
        "resource_type": values["resource_type"],
        "target_fingerprint": values["target_fingerprint"],
        "target_version": values["target_version"],
        "translator_version": values["translator_version"],
        "verification_digest": verification_digest,
        "version": "operational-action-request-digest-v1",
        "workflow_session_id": values["workflow_session_id"],
    }
    request_digest = _digest("operational-action-request-digest-v1", request_payload)
    values["request_digest"] = request_digest
    values["idempotency_key"] = _digest(
        "operational-action-execution-key-v1",
        {
            "request_digest": request_digest,
            "request_id": values["request_id"],
            "version": "operational-action-execution-key-v1",
        },
    )
    values["approval"] = {
        "approval_request_id": "approval",
        "action_request_id": values["request_id"],
        "action_request_digest": request_digest,
        "candidate_id": values["candidate_id"],
        "candidate_fingerprint": values["candidate_fingerprint"],
        "operational_plan_fingerprint": values["candidate_plan_fingerprint"],
        "provider_id": values["provider_id"],
        "resource_id": values["resource_id"],
        "resource_type": values["resource_type"],
        "target_fingerprint": values["target_fingerprint"],
        "target_version": values["target_version"],
        "operation_intent": values["execution_intent"],
        "disruption_scope": values["disruption_scope"],
        "verification_digest": verification_digest,
        "generated_at": generated_at,
        "expires_at": expires_at,
    }
    return values

SCHEMAS = {
    "action_history.db": """
        CREATE TABLE provider_action_history (
            id TEXT PRIMARY KEY, provider_id TEXT NOT NULL, provider_name TEXT NOT NULL,
            action_id TEXT NOT NULL, action_label TEXT NOT NULL, status TEXT NOT NULL,
            success INTEGER NOT NULL, message TEXT NOT NULL, confirmed INTEGER NOT NULL,
            destructive INTEGER NOT NULL, parameter_names TEXT NOT NULL, request_id TEXT,
            started_at TEXT NOT NULL, completed_at TEXT NOT NULL, duration_ms REAL NOT NULL);
        CREATE INDEX idx_provider_action_history_completed_at
            ON provider_action_history (completed_at DESC);
        CREATE INDEX idx_provider_action_history_provider_status
            ON provider_action_history (provider_id, status, completed_at DESC);
    """,
    "provider_intelligence.db": """
        CREATE TABLE intelligence_telemetry
            (id TEXT PRIMARY KEY, collected_at TEXT NOT NULL, telemetry TEXT NOT NULL);
        CREATE INDEX idx_intelligence_telemetry_collected_at
            ON intelligence_telemetry (collected_at DESC);
    """,
    "operational_dispatch.db": """
        CREATE TABLE operational_dispatch (
            request_id TEXT PRIMARY KEY, request_digest TEXT NOT NULL, state TEXT NOT NULL,
            request_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            dispatch_started_at TEXT, dispatch_result_json TEXT,
            verification_result_json TEXT);
        CREATE TABLE operational_dispatch_events (
            event_id TEXT PRIMARY KEY, status TEXT NOT NULL, occurred_at TEXT NOT NULL,
            event_json TEXT NOT NULL);
        CREATE INDEX idx_operational_dispatch_events_time
            ON operational_dispatch_events (occurred_at DESC);
        CREATE TABLE operational_dispatch_transitions (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT, request_id TEXT NOT NULL,
            request_digest TEXT NOT NULL, previous_state TEXT, state TEXT NOT NULL,
            occurred_at TEXT NOT NULL);
        CREATE INDEX idx_operational_dispatch_transitions_request
            ON operational_dispatch_transitions (request_id, sequence);
    """,
    "operator_intents.db": """
        CREATE TABLE operator_intents (
            record_id TEXT PRIMARY KEY, request_digest TEXT NOT NULL, record_json TEXT NOT NULL,
            created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
            schema_version INTEGER NOT NULL);
        CREATE TABLE operator_intent_audit (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT, occurred_at TEXT NOT NULL,
            record_id TEXT, candidate_id TEXT, operator_id TEXT, event TEXT NOT NULL,
            reason TEXT NOT NULL);
    """,
    "operator_security_audit.db": """
        CREATE TABLE operator_security_audit (
            event_id TEXT PRIMARY KEY, occurred_at TEXT NOT NULL, request_id TEXT NOT NULL,
            operator_id TEXT, auth_method TEXT, action TEXT NOT NULL, outcome TEXT NOT NULL,
            reason TEXT NOT NULL);
    """,
}


def seed(root: Path, audit: bool) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for name, schema in SCHEMAS.items():
        if name == "operator_security_audit.db" and not audit:
            continue
        with sqlite3.connect(root / name) as connection:
            connection.executescript(schema)
            if name == "action_history.db":
                connection.execute(
                    "INSERT INTO provider_action_history VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    ("history", "p", "Provider", "inspect", "Inspect", "succeeded", 1,
                     "ok", 1, 0, "[]", "request", "2026-01-01", "2026-01-01", 1.0),
                )
            elif name == "provider_intelligence.db":
                connection.execute(
                    "INSERT INTO intelligence_telemetry VALUES (?,?,?)",
                    ("telemetry", "2026-01-01", '{"status":"ok"}'),
                )
            elif name == "operational_dispatch.db":
                request = {
                    "schema_version": 1, "request_id": "dispatch-request",
                    "request_digest": "dispatch-digest", "idempotency_key": "key",
                    "effect_kind": "operational_action", "execution_intent": "restart-service",
                    "provider_id": "proxmox", "resource_id": "qemu/101",
                    "resource_type": "qemu",
                    "provider_action_id": "proxmox-qemu-graceful-restart-v1",
                    "target_fingerprint": "fingerprint", "verification": {}, "approval": {},
                }
                result = {
                    "request_id": "dispatch-request", "request_digest": "dispatch-digest",
                    "status": "succeeded", "target_fingerprint": "fingerprint",
                    "provider_operation_id": "UPID:disposable:restart",
                    "started_at": "2026-01-01", "completed_at": "2026-01-01",
                }
                verification = {
                    "request_id": "dispatch-request", "status": "succeeded",
                    "started_at": "2026-01-01", "completed_at": "2026-01-01",
                    "deadline": "2026-01-01", "observed_state": "running",
                }
                connection.execute(
                    "INSERT INTO operational_dispatch VALUES (?,?,?,?,?,?,?,?,?)",
                    ("dispatch-request", "dispatch-digest", "verified", json.dumps(request),
                     "2026-01-01", "2026-01-01", "2026-01-01", json.dumps(result),
                     json.dumps(verification)),
                )
                for previous, state in (
                    (None, "claimed"), ("claimed", "revalidated"),
                    ("revalidated", "dispatching"),
                    ("dispatching", "succeeded"),
                    ("succeeded", "verifying"),
                    ("verifying", "verified"),
                ):
                    connection.execute(
                        "INSERT INTO operational_dispatch_transitions "
                        "(request_id, request_digest, previous_state, state, occurred_at) "
                        "VALUES (?,?,?,?,?)",
                        ("dispatch-request", "dispatch-digest", previous, state, "2026-01-01"),
                    )
                connection.execute(
                    "INSERT INTO operational_dispatch_events VALUES (?,?,?,?)",
                    (
                        "event",
                        "dispatching",
                        "2026-01-01T00:00:00+00:00",
                        json.dumps(
                            {
                                "event_id": "event",
                                "status": "dispatching",
                                "occurred_at": "2026-01-01T00:00:00Z",
                            }
                        ),
                    ),
                )
                dispatching = dispatching_request()
                connection.execute(
                    "INSERT INTO operational_dispatch VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        "dispatching-request",
                        dispatching["request_digest"],
                        "dispatching",
                        json.dumps(dispatching),
                        "2026-01-01",
                        "2026-01-01",
                        "2026-01-01",
                        None,
                        None,
                    ),
                )
                for previous, state in (
                    (None, "claimed"),
                    ("claimed", "revalidated"),
                    ("revalidated", "dispatching"),
                ):
                    connection.execute(
                        "INSERT INTO operational_dispatch_transitions "
                        "(request_id, request_digest, previous_state, state, occurred_at) "
                        "VALUES (?,?,?,?,?)",
                        (
                            "dispatching-request",
                            dispatching["request_digest"],
                            previous,
                            state,
                            "2026-01-01",
                        ),
                    )
            elif name == "operator_intents.db":
                record = {
                    "record_id": "intent", "request_digest": "intent-digest",
                    "candidate_id": "candidate", "operator_id": "operator",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "expires_at": "2026-01-02T00:00:00+00:00", "schema_version": 1,
                }
                connection.execute(
                    "INSERT INTO operator_intents VALUES (?,?,?,?,?,?)",
                    ("intent", "intent-digest", json.dumps(record),
                     record["created_at"], record["expires_at"], 1),
                )
                connection.execute(
                    "INSERT INTO operator_intent_audit "
                    "(occurred_at,record_id,candidate_id,operator_id,event,reason) "
                    "VALUES (?,?,?,?,?,?)",
                    (record["created_at"], "intent", "candidate", "operator", "created", "gate"),
                )
            elif name == "operator_security_audit.db":
                connection.execute(
                    "INSERT INTO operator_security_audit VALUES (?,?,?,?,?,?,?,?)",
                    ("audit", "2026-01-01", "request", "operator", "token",
                     "read", "allowed", "gate"),
                )
        os.chmod(root / name, 0o600)
        os.chown(root / name, UID, GID)
    config = root / "config"
    secrets = root / "secrets"
    config.mkdir(mode=0o700)
    secrets.mkdir(mode=0o700)
    values = {
        config / "policies.yaml": 'proxmox:\n  guests:\n    "109":\n      expected: stopped\n',
        config / "provider-connections.yaml": (
            "version: 1\nproviders:\n  proxmox:\n    connection:\n"
            "      host: restored.example\n      port: 8006\n      node: restored-node\n"
            "      verify_tls: false\n"
        ),
        secrets / "provider-connections.yaml": (
            "version: 1\nproviders:\n  proxmox:\n    secrets:\n"
            "      token_value: restored-secret\n"
        ),
    }
    for path, value in values.items():
        path.write_text(value, encoding="utf-8")
        os.chmod(path, 0o600)
        os.chown(path, UID, GID)
    for directory in (config, secrets):
        os.chown(directory, UID, GID)
    os.chown(root, UID, GID)


def stale(root: Path, audit: bool) -> None:
    for relative in (
        "operator_sessions.db", "operator_sessions.db-wal", "operator_sessions.db-shm",
        "provider_intents.db", "provider_intents.db-wal", "provider_intents.db-shm",
        "operational_dispatch.db-wal", "operator_intents.db-shm",
    ):
        path = root / relative
        path.write_bytes(b"stale")
    if not audit:
        for relative in (
            "operator_security_audit.db",
            "operator_security_audit.db-wal",
            "operator_security_audit.db-shm",
        ):
            (root / relative).write_bytes(b"stale audit")
    for relative in (
        "cache/sentinel", "history/sentinel", "knowledge/sentinel",
        "providers/sentinel", "unrelated-root",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("preserve", encoding="utf-8")


def verify(root: Path, audit: bool) -> None:
    for relative in (
        "operator_sessions.db", "operator_sessions.db-wal", "operator_sessions.db-shm",
        "provider_intents.db", "provider_intents.db-wal", "provider_intents.db-shm",
        "operational_dispatch.db-wal", "operator_intents.db-shm",
    ):
        assert not (root / relative).exists(), relative
    for relative in (
        "operator_security_audit.db-wal",
        "operator_security_audit.db-shm",
    ):
        assert not (root / relative).exists(), relative
    for relative in (
        "cache/sentinel", "history/sentinel", "knowledge/sentinel",
        "providers/sentinel", "unrelated-root",
    ):
        assert (root / relative).read_text(encoding="utf-8") == "preserve"
    assert not (root / ".atlas-restore").exists()
    assert (root / "operator_security_audit.db").exists() is audit
    if audit:
        with sqlite3.connect(root / "operator_security_audit.db") as connection:
            assert connection.execute(
                "SELECT event_id,operator_id,reason FROM operator_security_audit"
            ).fetchone() == ("audit", "operator", "gate")
    with sqlite3.connect(root / "operational_dispatch.db") as connection:
        assert connection.execute(
            "SELECT request_id,request_digest,state,dispatch_result_json "
            "FROM operational_dispatch"
        ).fetchone()[:3] == ("dispatch-request", "dispatch-digest", "verified")
        assert connection.execute(
            "SELECT count(*) FROM operational_dispatch_transitions"
        ).fetchone()[0] == 9
        assert connection.execute(
            "SELECT count(*) FROM operational_dispatch_events"
        ).fetchone()[0] == 1
    with sqlite3.connect(root / "operator_intents.db") as connection:
        assert connection.execute(
            "SELECT record_id,request_digest,created_at,expires_at FROM operator_intents"
        ).fetchone() == (
            "intent", "intent-digest", "2026-01-01T00:00:00+00:00",
            "2026-01-02T00:00:00+00:00",
        )
        assert connection.execute(
            "SELECT record_id,candidate_id,operator_id,event,reason "
            "FROM operator_intent_audit"
        ).fetchone() == ("intent", "candidate", "operator", "created", "gate")
    expected = {
        "config/policies.yaml": "expected: stopped",
        "config/provider-connections.yaml": "host: restored.example",
        "secrets/provider-connections.yaml": "restored-secret",
    }
    for relative, marker in expected.items():
        path = root / relative
        assert marker in path.read_text(encoding="utf-8")
        metadata = path.stat()
        assert (metadata.st_uid, metadata.st_gid) == (UID, GID)
        assert metadata.st_mode & 0o777 == 0o600


if __name__ == "__main__":
    command, root_value, audit_value = sys.argv[1:]
    root = Path(root_value)
    audit = audit_value == "true"
    {"seed": seed, "verify": verify, "stale": stale}[command](root, audit)
