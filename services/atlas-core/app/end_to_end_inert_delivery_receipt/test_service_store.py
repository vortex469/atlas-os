from __future__ import annotations

import ast
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.end_to_end_inert_delivery_receipt import store as store_module
from app.end_to_end_inert_delivery_receipt.contract import (
    AgentAdmissionReceiptCopyV1,
    agent_receipt_copy_fingerprint,
    idempotency_key_fingerprint,
    request_fingerprint,
)
from app.end_to_end_inert_delivery_receipt.service import (
    InertDeliveryReceiptEvidence,
    InertDeliveryReceiptService,
)
from app.end_to_end_inert_delivery_receipt.store import (
    InertDeliveryReceiptConflictError,
    InertDeliveryReceiptStore,
)
from app.end_to_end_inert_delivery_receipt.test_contract import (
    RECEIPT_ID,
    _evidence,
    _fp,
)
from app.live_delivery_send_boundary.contract import (
    LiveDeliverySendReceiptV1,
    receipt_fingerprint,
)
from app.operator_controlled_delivery_enablement.test_contract import OPERATOR

CORRELATION_ID = "inert-receipt-correlation"
IDEMPOTENCY_KEY = "verify-receipt-once"


def _prior_receipt(request, agent_copy) -> LiveDeliverySendReceiptV1:
    admission = agent_copy.result.admission
    acknowledgement = agent_copy.result.acknowledgement
    assert admission is not None and acknowledgement is not None
    raw = {
        "send_attempt_id": request.send_attempt_id,
        "attempt_fingerprint": request.attempt_fingerprint.model_dump(mode="json"),
        "completed_at": agent_copy.copied_at,
        "lifecycle": "admitted_evidence_only",
        "http_status_class": "2xx",
        "response_fingerprint": _fp("1").model_dump(mode="json"),
        "admission_fingerprint": admission.admission_fingerprint.model_dump(mode="json"),
        "acknowledgement_fingerprint": acknowledgement.acknowledgement_fingerprint.model_dump(mode="json"),
        "agent_audit_evidence_fingerprint": _fp("2").model_dump(mode="json"),
        "redacted_error": None,
        "evidence_admitted": True,
        "receipt_fingerprint": _fp("3").model_dump(mode="json"),
    }
    seed = LiveDeliverySendReceiptV1.model_construct(**raw)
    return LiveDeliverySendReceiptV1.model_validate(
        seed.model_copy(update={"receipt_fingerprint": receipt_fingerprint(seed)})
    )


@dataclass
class Reader:
    evidence: InertDeliveryReceiptEvidence
    calls: int = 0
    error: Exception | None = None

    def resolve(self, *, operator_id, request):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.evidence


def _setup(tmp_path: Path, *, quota: int = 1000):
    request, agent_copy, *_ = _evidence(tmp_path)
    request_seed = request.model_copy(
        update={
            "idempotency_key_fingerprint": idempotency_key_fingerprint(
                OPERATOR, IDEMPOTENCY_KEY
            ),
            "request_fingerprint": _fp("0"),
        }
    )
    request = type(request).model_validate(
        request_seed.model_copy(
            update={"request_fingerprint": request_fingerprint(request_seed)}
        )
    )
    evidence = InertDeliveryReceiptEvidence(
        prior_send_receipt=_prior_receipt(request, agent_copy),
        agent_receipt_copy=agent_copy,
    )
    reader = Reader(evidence)
    store = InertDeliveryReceiptStore(tmp_path / "receipt.sqlite3", quota=quota)
    service = InertDeliveryReceiptService(
        evidence_reader=reader,
        store=store,
        clock=lambda: datetime(2026, 8, 27, 12, 0, 16, tzinfo=UTC),
        receipt_id_factory=lambda: RECEIPT_ID,
    )
    return request, agent_copy, reader, store, service


def _verify(service, request, *, key=IDEMPOTENCY_KEY, operator=OPERATOR):
    return service.verify(
        request,
        authenticated_operator_id=operator,
        idempotency_key=key,
        correlation_id=CORRELATION_ID,
    )


def test_valid_verification_list_get_and_authority_flags(tmp_path: Path):
    request, _, reader, _, service = _setup(tmp_path)

    result = _verify(service, request)

    assert result.disposition == "verified_inert_receipt"
    assert result.receipt is not None
    assert result.receipt.prior_send_receipt_fingerprint == (
        reader.evidence.prior_send_receipt.receipt_fingerprint
    )
    assert result.audit_evidence is not None
    assert not result.execution_authorized
    assert not result.installation_allowed
    assert not result.worker_allowed
    assert not result.workflow_allowed
    assert not result.deployment_allowed
    assert not result.mutation_allowed
    listed = service.list(
        authenticated_operator_id=OPERATOR, correlation_id=CORRELATION_ID
    )
    assert isinstance(listed, tuple) and len(listed) == 1
    fetched = service.get(
        authenticated_operator_id=OPERATOR,
        receipt_id=RECEIPT_ID,
        correlation_id=CORRELATION_ID,
    )
    assert fetched.receipt == result.receipt


def test_exact_retry_is_read_only_and_conflicting_key_is_no_replay(tmp_path: Path):
    request, _, reader, store, service = _setup(tmp_path)
    first = _verify(service, request)
    duplicate = _verify(service, request)

    assert first.receipt == duplicate.receipt
    assert duplicate.disposition == "exact_duplicate"
    assert reader.calls == 1
    with pytest.raises(InertDeliveryReceiptConflictError):
        store.reserve(
            operator_id=OPERATOR,
            send_attempt_id=request.send_attempt_id,
            request_fingerprint=_fp("f").value,
            idempotency_key_fingerprint=request.idempotency_key_fingerprint.value,
            receipt_id=RECEIPT_ID,
        )


def test_ownership_staleness_and_send_mismatch_fail_closed(tmp_path: Path):
    request, _, _, _, service = _setup(tmp_path / "owner")
    ownership = _verify(service, request, operator="operator-b")
    assert ownership.error is not None
    assert ownership.error.error_code == "ownership_mismatch"

    request, _, _, store, _ = _setup(tmp_path / "stale")
    stale = InertDeliveryReceiptService(
        evidence_reader=_setup(tmp_path / "stale-reader")[2],
        store=store,
        clock=lambda: datetime(2026, 8, 27, 12, 0, 42, tzinfo=UTC),
        receipt_id_factory=lambda: RECEIPT_ID,
    )
    expired = _verify(stale, request)
    assert expired.error is not None and expired.error.error_code == "expired"

    request, _, reader, _, service = _setup(tmp_path / "mismatch")
    bad_raw = reader.evidence.prior_send_receipt.model_dump(mode="python")
    bad_raw["send_attempt_id"] = "00000000-0000-4000-8000-00000000dead"
    bad_raw["receipt_fingerprint"] = receipt_fingerprint(bad_raw)
    reader.evidence = InertDeliveryReceiptEvidence(
        LiveDeliverySendReceiptV1.model_validate(bad_raw),
        reader.evidence.agent_receipt_copy,
    )
    mismatch = _verify(service, request)
    assert mismatch.error is not None
    assert mismatch.error.error_code == "linkage_mismatch"


def test_agent_authenticity_and_admission_mismatch_fail_closed(tmp_path: Path):
    request, copy, reader, _, service = _setup(tmp_path / "auth")
    authenticity = copy.authenticity.model_copy(
        update={"endpoint_fingerprint": _fp("f")}
    )
    seed = copy.model_copy(
        update={"authenticity": authenticity, "copy_fingerprint": _fp("0")}
    )
    bad_copy = AgentAdmissionReceiptCopyV1.model_validate(
        seed.model_copy(
            update={"copy_fingerprint": agent_receipt_copy_fingerprint(seed)}
        )
    )
    reader.evidence = InertDeliveryReceiptEvidence(
        reader.evidence.prior_send_receipt, bad_copy
    )
    result = _verify(service, request)
    assert result.error is not None
    assert result.error.error_code == "linkage_mismatch"

    request, copy, reader, _, service = _setup(tmp_path / "admission")
    malformed = copy.model_construct(
        **{
            **copy.model_dump(mode="python"),
            "result": copy.result.model_copy(update={"send_attempt_id": None}),
        }
    )
    reader.evidence = InertDeliveryReceiptEvidence(
        reader.evidence.prior_send_receipt, malformed
    )
    rejected = _verify(service, request)
    assert rejected.error is not None
    assert rejected.error.error_code == "fingerprint_mismatch"


def test_restart_readback_foreign_isolation_and_corruption(tmp_path: Path):
    request, _, reader, _, service = _setup(tmp_path)
    created = _verify(service, request)
    assert created.receipt is not None
    restarted = InertDeliveryReceiptService(
        evidence_reader=reader,
        store=InertDeliveryReceiptStore(tmp_path / "receipt.sqlite3"),
        clock=lambda: datetime(2026, 8, 27, 12, 0, 17, tzinfo=UTC),
        receipt_id_factory=lambda: "00000000-0000-4000-8000-000000000c04",
    )
    assert restarted.get(
        authenticated_operator_id=OPERATOR,
        receipt_id=RECEIPT_ID,
        correlation_id=CORRELATION_ID,
    ).receipt == created.receipt
    foreign = restarted.get(
        authenticated_operator_id="operator-b",
        receipt_id=RECEIPT_ID,
        correlation_id=CORRELATION_ID,
    )
    assert foreign.error is not None and foreign.error.error_code == "not_found"

    with sqlite3.connect(tmp_path / "receipt.sqlite3") as connection:
        connection.execute(
            "UPDATE inert_delivery_receipts SET receipt_json = ?",
            ('{"schema":"secret://must-not-escape"}',),
        )
    corrupt = restarted.get(
        authenticated_operator_id=OPERATOR,
        receipt_id=RECEIPT_ID,
        correlation_id=CORRELATION_ID,
    )
    assert corrupt.error is not None and corrupt.error.error_code == "unavailable"
    assert "secret" not in corrupt.model_dump_json()


def test_quota_size_and_dependency_errors_are_redacted(tmp_path: Path, monkeypatch):
    request, _, _, _, service = _setup(tmp_path / "quota", quota=0)
    quota = _verify(service, request)
    assert quota.error is not None and quota.error.error_code == "quota_exceeded"

    request, _, _, _, service = _setup(tmp_path / "size")
    monkeypatch.setattr(store_module, "MAX_RECEIPT_BYTES", 1)
    oversized = _verify(service, request)
    assert oversized.error is not None
    assert oversized.error.error_code == "unavailable"

    request, _, reader, _, service = _setup(tmp_path / "redacted")
    reader.error = RuntimeError(
        "Bearer live-secret credential://production internal/path 10.0.0.8"
    )
    failed = _verify(service, request)
    rendered = failed.model_dump_json()
    assert failed.error is not None and failed.error.redacted
    for secret in ("live-secret", "credential://", "internal/path", "10.0.0.8"):
        assert secret not in rendered


def test_service_store_have_no_transport_or_mutation_capabilities():
    package = Path(__file__).parent
    forbidden_imports = {
        "docker",
        "httpx",
        "requests",
        "socket",
        "subprocess",
        "urllib",
    }
    forbidden_calls = {"exec", "eval", "open", "system", "popen", "run"}
    for path in (package / "service.py", package / "store.py"):
        tree = ast.parse(path.read_text())
        imports = {
            node.names[0].name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
        } | {
            (node.module or "").split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        calls = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert not imports.intersection(forbidden_imports)
        assert not calls.intersection(forbidden_calls)


def test_failed_reservation_is_permanent_no_replay(tmp_path: Path):
    request, _, reader, _, service = _setup(tmp_path)
    reader.error = RuntimeError("uncertain evidence reader")
    first = _verify(service, request)
    reader.error = None
    second = _verify(service, request)
    assert first.error is not None and first.error.error_code == "unavailable"
    assert second.error is not None and second.error.error_code == "unavailable"
    assert reader.calls == 1


@pytest.mark.parametrize("key", ["", "contains space", "bad\nkey", "x" * 129])
def test_idempotency_key_shape_rejected(tmp_path: Path, key: str):
    request, _, reader, _, service = _setup(tmp_path)
    result = _verify(service, request, key=key)
    assert result.error is not None
    assert result.error.error_code == "response_invalid"
    assert reader.calls == 0
