import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest

from app.operational_dispatch.ledger import (
    OperationalDispatchLedger,
    OperationalLedgerConflictError,
    OperationalLedgerCorruptionError,
    OperationalLedgerError,
    OperationalLedgerState,
)
from app.operational_dispatch.models import (
    OperationalDispatchResult,
    OperationalDispatchStatus,
)
from app.operational_dispatch.test_support import make_request


def test_claim_is_idempotent_and_digest_conflict_is_rejected(tmp_path) -> None:
    ledger = OperationalDispatchLedger(tmp_path / "operational.db")
    request = make_request()
    assert ledger.claim(request) == ledger.claim(request)
    conflicting = make_request(candidate_id="candidate-2")
    with pytest.raises(OperationalLedgerConflictError):
        ledger.claim(conflicting)


def test_concurrent_dispatch_barrier_has_one_owner(tmp_path) -> None:
    ledger = OperationalDispatchLedger(tmp_path / "operational.db")
    request = make_request()
    ledger.claim(request)
    ledger.mark_revalidated(request)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: ledger.mark_dispatching(request), range(8)))
    assert sum(owner for _, owner in results) == 1
    assert ledger.get(request.request_id).state is OperationalLedgerState.DISPATCHING  # type: ignore[union-attr]
    assert [transition.state for transition in ledger.list_transitions(request.request_id)] == [
        OperationalLedgerState.CLAIMED,
        OperationalLedgerState.REVALIDATED,
        OperationalLedgerState.DISPATCHING,
    ]


def test_startup_recovery_marks_dispatching_unknown_without_replay(tmp_path) -> None:
    path = tmp_path / "operational.db"
    request = make_request()
    ledger = OperationalDispatchLedger(path)
    ledger.claim(request)
    ledger.mark_revalidated(request)
    ledger.mark_dispatching(request)

    recovered = OperationalDispatchLedger(path)
    summary = recovered.reconcile_startup()
    entry = recovered.get(request.request_id)
    assert summary["outcome_unknown"] == 1
    assert entry is not None
    assert entry.state is OperationalLedgerState.OUTCOME_UNKNOWN
    assert entry.dispatch_result.status is OperationalDispatchStatus.OUTCOME_UNKNOWN  # type: ignore[union-attr]


def test_terminal_dispatch_result_is_immutable(tmp_path) -> None:
    ledger = OperationalDispatchLedger(tmp_path / "operational.db")
    request = make_request()
    ledger.claim(request)
    now = datetime.now(UTC)
    result = OperationalDispatchResult(
        status=OperationalDispatchStatus.FAILED,
        request_id=request.request_id,
        request_digest=request.request_digest,
        target_fingerprint=request.target_fingerprint,
        started_at=now,
        completed_at=now,
        sanitized_message="disabled",
    )
    ledger.persist_dispatch_result(request, result, state=OperationalLedgerState.FAILED)
    with pytest.raises(OperationalLedgerError, match="immutable"):
        ledger.persist_dispatch_result(
            request,
            result.model_copy(update={"sanitized_message": "changed"}),
            state=OperationalLedgerState.FAILED,
        )


def test_corrupt_terminal_record_fails_closed(tmp_path) -> None:
    path = tmp_path / "operational.db"
    ledger = OperationalDispatchLedger(path)
    request = make_request()
    ledger.claim(request)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE operational_dispatch SET state='failed' WHERE request_id=?",
            (request.request_id,),
        )
    with pytest.raises(OperationalLedgerCorruptionError):
        ledger.get(request.request_id)
