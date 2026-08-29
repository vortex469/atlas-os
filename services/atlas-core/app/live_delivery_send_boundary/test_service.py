from __future__ import annotations

import ast
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.live_delivery_send_boundary.contract import (
    LiveDeliverySendAuditEvidenceV1,
    LiveDeliverySendEvidenceV1,
    LiveDeliverySendReceiptV1,
    LiveDeliverySendRedactedErrorV1,
    LiveDeliveryTransportEnvelopeV1,
    attempt_fingerprint,
    audit_evidence_fingerprint,
    receipt_fingerprint,
)
from app.live_delivery_send_boundary.service import LiveDeliverySendService
from app.live_delivery_send_boundary.store import (
    LiveDeliverySendStore,
    LiveDeliverySendStoredEvidence,
    LiveDeliverySendStoreError,
)
from app.live_delivery_send_boundary.test_contract import (
    ATTEMPT_ID,
    CREATED_AT,
    _configuration,
    _create,
    _evidence,
)
from app.operator_controlled_delivery_enablement.test_contract import OPERATOR


@dataclass
class Reader:
    value: LiveDeliverySendEvidenceV1
    calls: int = 0

    def resolve(self, *, operator_id: str, create):
        self.calls += 1
        return self.value


def _clock(value: str = CREATED_AT):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    return lambda: parsed


def _service(tmp_path: Path, *, enabled: bool = True, at: str = CREATED_AT,
             database: Path | None = None):
    evidence = _evidence(tmp_path, at=at)
    reader = Reader(evidence)
    service = LiveDeliverySendService(
        configuration=_configuration(enabled=enabled),
        evidence_reader=reader,
        store=LiveDeliverySendStore(database or tmp_path / "send.sqlite3"),
        clock=_clock(at),
        id_factory=lambda: ATTEMPT_ID,
    )
    return service, reader, evidence


def _reserve(service, evidence, *, key: str = "send-once", correlation: str = "send-1"):
    return service.create(
        _create(evidence),
        authenticated_operator_id=OPERATOR,
        idempotency_key=key,
        correlation_id=correlation,
    )


def test_create_exact_retry_and_public_surface_are_no_send(tmp_path: Path) -> None:
    service, reader, evidence = _service(tmp_path)
    created = _reserve(service, evidence)
    replay = _reserve(service, evidence)
    assert created.disposition == "reserved"
    assert replay.disposition == "exact_replay"
    assert created.attempt == replay.attempt
    assert reader.calls == 1
    assert not created.network_attempted and not created.replay_allowed
    assert {
        name for name in dir(LiveDeliverySendService) if not name.startswith("_")
    } == {"configuration", "create", "get", "list"}


def test_conflict_default_disabled_and_bad_key_are_redacted(tmp_path: Path) -> None:
    service, _, evidence = _service(tmp_path)
    assert _reserve(service, evidence).disposition == "reserved"
    conflict = _reserve(service, evidence, key="different")
    assert conflict.error and conflict.error.error_code == "already_reserved"
    disabled, disabled_reader, disabled_evidence = _service(
        tmp_path / "disabled", enabled=False
    )
    rejected = _reserve(disabled, disabled_evidence)
    assert rejected.error and rejected.error.error_code == "not_current"
    assert disabled_reader.calls == 0
    malformed = disabled.create(
        _create(disabled_evidence), authenticated_operator_id=OPERATOR,
        idempotency_key="bad key", correlation_id="secret\npath",
    )
    assert malformed.error and malformed.error.correlation_id == "live-send-redacted"
    assert set(malformed.error.model_dump()) == {
        "schema", "error_code", "safe_message", "correlation_id",
        "send_attempt_id", "attempt_fingerprint", "redacted", "retryable",
        "execution_authorized", "installation_allowed", "mutation_allowed",
        "replay_allowed",
    }


def test_stale_linkage_and_owner_mismatch_fail_closed(tmp_path: Path) -> None:
    stale, _, stale_evidence = _service(
        tmp_path / "stale", at="2026-08-27T12:00:42Z"
    )
    assert _reserve(stale, stale_evidence).error.error_code == "expired"  # type: ignore[union-attr]
    service, reader, evidence = _service(tmp_path / "linkage")
    raw = evidence.model_dump(mode="json")
    raw["linkage"]["enablement_id"] = "00000000-0000-4000-8000-000000000bee"
    reader.value = raw  # type: ignore[assignment]
    assert _reserve(service, evidence).error.error_code == "linkage_mismatch"  # type: ignore[union-attr]
    service, reader, evidence = _service(tmp_path / "owner")
    raw = evidence.model_dump(mode="json")
    raw["authenticated_operator_id"] = "operator-b"
    reader.value = raw  # type: ignore[assignment]
    assert _reserve(service, evidence).error.error_code == "linkage_mismatch"  # type: ignore[union-attr]


def test_restart_owned_readback_foreign_absence_and_corruption(tmp_path: Path) -> None:
    database = tmp_path / "restart.sqlite3"
    service, _, evidence = _service(tmp_path, database=database)
    created = _reserve(service, evidence)
    restarted, _, _ = _service(tmp_path, database=database)
    read = restarted.get(
        authenticated_operator_id=OPERATOR,
        send_attempt_id=created.attempt.send_attempt_id,  # type: ignore[union-attr]
        correlation_id="read-1",
    )
    assert read.attempt == created.attempt
    foreign = restarted.get(
        authenticated_operator_id="operator-b",
        send_attempt_id=created.attempt.send_attempt_id,  # type: ignore[union-attr]
        correlation_id="read-2",
    )
    assert foreign.error and foreign.error.error_code == "not_found"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE live_delivery_send_attempts SET attempt_json = ?",
            ("{\"secret\":\"do-not-leak\"}",),
        )
    corrupt = restarted.get(
        authenticated_operator_id=OPERATOR,
        send_attempt_id=created.attempt.send_attempt_id,  # type: ignore[union-attr]
        correlation_id="read-3",
    )
    assert corrupt.error and corrupt.error.error_code == "unavailable"
    assert "secret" not in corrupt.model_dump_json()


def test_store_appends_one_ambiguous_receipt_without_replay(tmp_path: Path) -> None:
    service, _, evidence = _service(tmp_path)
    created = _reserve(service, evidence)
    attempt = created.attempt
    assert attempt is not None
    error = LiveDeliverySendRedactedErrorV1(
        error_code="ambiguous", correlation_id="send-ambiguous"
    )
    raw = {
        "schema": "live-delivery-send-receipt-v1",
        "send_attempt_id": attempt.send_attempt_id,
        "attempt_fingerprint": attempt.attempt_fingerprint.model_dump(mode="json"),
        "completed_at": CREATED_AT, "lifecycle": "ambiguous",
        "http_status_class": "none", "response_fingerprint": None,
        "admission_fingerprint": None, "acknowledgement_fingerprint": None,
        "agent_audit_evidence_fingerprint": None,
        "redacted_error": error.model_dump(mode="json"), "agent_contacted": True,
        "evidence_admitted": False, "execution_admission_granted": False,
        "execution_authorized": False, "installation_allowed": False,
        "worker_allowed": False, "workflow_allowed": False,
        "deployment_allowed": False, "mutation_allowed": False,
        "replay_allowed": False,
    }
    raw["receipt_fingerprint"] = receipt_fingerprint(raw).model_dump(mode="json")
    receipt = LiveDeliverySendReceiptV1.model_validate(raw)
    store = service._store
    first = store.append_receipt(operator_id=OPERATOR, receipt=receipt)
    second = store.append_receipt(operator_id=OPERATOR, receipt=receipt)
    assert first.receipt == second.receipt == receipt
    assert not receipt.replay_allowed and receipt.lifecycle == "ambiguous"


def _distinct(stored: LiveDeliverySendStoredEvidence) -> LiveDeliverySendStoredEvidence:
    attempt_raw = stored.attempt.model_dump(mode="json")
    replacement = "00000000-0000-4000-8000-000000000b02"
    for key in ("enablement_id", "preflight_id", "delivery_preparation_id", "intake_request_id"):
        attempt_raw["linkage"][key] = replacement
    attempt_raw["linkage"]["enablement_fingerprint"]["value"] = "b" * 64
    attempt_raw["linkage"]["preparation_fingerprint"]["value"] = "c" * 64
    attempt_raw["send_attempt_id"] = replacement
    attempt_raw["attempt_fingerprint"] = attempt_fingerprint(
        attempt_raw, operator_id=OPERATOR
    ).model_dump(mode="json")
    attempt = type(stored.attempt).model_validate(attempt_raw)
    envelope_raw = stored.envelope.model_dump(mode="json")
    envelope_raw["send_attempt_id"] = replacement
    envelope = LiveDeliveryTransportEnvelopeV1.model_validate(envelope_raw)
    audit_raw = stored.audit_evidence.model_dump(mode="json")
    audit_raw["send_attempt_id"] = replacement
    audit_raw["attempt_fingerprint"] = attempt.attempt_fingerprint.model_dump(mode="json")
    audit_raw["evidence_fingerprint"] = audit_evidence_fingerprint(audit_raw).model_dump(mode="json")
    audit = LiveDeliverySendAuditEvidenceV1.model_validate(audit_raw)
    return LiveDeliverySendStoredEvidence(attempt, envelope, audit)


def test_quota_and_size_bounds_fail_closed(tmp_path: Path, monkeypatch) -> None:
    service, _, evidence = _service(tmp_path)
    created = _reserve(service, evidence)
    stored = service._store.get(
        operator_id=OPERATOR, send_attempt_id=created.attempt.send_attempt_id  # type: ignore[union-attr]
    )
    import app.live_delivery_send_boundary.store as store_module

    monkeypatch.setattr(store_module, "MAX_RECORDS_PER_OPERATOR", 1)
    with pytest.raises(LiveDeliverySendStoreError, match="quota_exceeded"):
        service._store.reserve(
            operator_id=OPERATOR, idempotency_key="second",
            create_fingerprint="f" * 64, evidence=_distinct(stored),
        )
    monkeypatch.setattr(store_module, "MAX_ATTEMPT_BYTES", 1)
    with pytest.raises(LiveDeliverySendStoreError, match="size_exceeded"):
        LiveDeliverySendStore(tmp_path / "size.sqlite3").reserve(
            operator_id=OPERATOR, idempotency_key="one",
            create_fingerprint="e" * 64, evidence=stored,
        )


def test_service_store_have_no_transport_runtime_or_mutation_calls() -> None:
    forbidden_imports = {
        "aiohttp", "docker", "httpx", "podman", "requests", "socket", "ssl",
        "subprocess", "urllib",
    }
    forbidden_calls = {
        "send", "post", "request", "connect", "run", "Popen", "system",
        "execute_container", "install", "deploy", "rollback", "dispatch",
        "start_workflow",
    }
    for path in (Path(__file__).with_name("service.py"), Path(__file__).with_name("store.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        calls = {
            getattr(node.func, "id", "")
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
        }
        assert imports.isdisjoint(forbidden_imports)
        assert calls.isdisjoint(forbidden_calls)


def test_service_has_no_production_consumer_or_registration() -> None:
    app_root = Path(__file__).parents[1]
    package = Path(__file__).parent
    repository_root = app_root.parents[2]
    roots = (app_root, repository_root / "services" / "atlas-agent" / "app")
    markers = {
        "LiveDeliverySendService",
        "create_live_delivery_send_service",
        "live_delivery_send_attempts",
    }
    violations = []
    for root in roots:
        for path in root.rglob("*.py"):
            if path.name.startswith("test_") or package in path.parents:
                continue
            source = path.read_text(encoding="utf-8")
            violations.extend(
                f"{path.relative_to(repository_root)} -> {marker}"
                for marker in markers
                if marker in source
            )
    assert violations == []
    main = (app_root / "main.py").read_text(encoding="utf-8")
    assert "live_delivery_send_boundary" not in main
