import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

from app.operational_dispatch.ledger import (
    OperationalDispatchLedger,
    OperationalLedgerState,
)
from app.operational_dispatch.models import (
    OperationalDispatchResult,
    OperationalDispatchStatus,
    OperationalVerificationStatus,
)
from app.operational_dispatch.test_support import make_request, make_target
from app.operational_dispatch.verification import OperationalVerificationService


def test_verification_is_read_only_and_reports_unknown_without_policy(
    tmp_path,
) -> None:
    request = make_request()
    resolver = AsyncMock(return_value=make_target())
    started = datetime.now(UTC)
    result = asyncio.run(OperationalVerificationService(resolver=resolver).verify(
        request,
        started_at=started,
        deadline=started + timedelta(seconds=5),
    ))
    assert result.status is OperationalVerificationStatus.OUTCOME_UNKNOWN
    assert result.observed_target_fingerprint == request.target_fingerprint
    resolver.assert_awaited_once_with("proxmox", "qemu/101", "qemu")


def test_verification_can_resume_from_durable_unknown_without_mutation(
    tmp_path,
) -> None:
    path = tmp_path / "operational.db"
    request = make_request()
    ledger = OperationalDispatchLedger(path)
    ledger.claim(request)
    now = datetime.now(UTC)
    ledger.persist_dispatch_result(
        request,
        OperationalDispatchResult(
            status=OperationalDispatchStatus.OUTCOME_UNKNOWN,
            request_id=request.request_id,
            request_digest=request.request_digest,
            target_fingerprint=request.target_fingerprint,
            started_at=now,
            completed_at=now,
        ),
        state=OperationalLedgerState.OUTCOME_UNKNOWN,
    )
    restarted = OperationalDispatchLedger(path)
    entry, owner = restarted.begin_verification(request)
    assert owner is True
    assert entry.state is OperationalLedgerState.VERIFYING
    resumed = OperationalDispatchLedger(path)
    assert resumed.reconcile_startup()["verification_resumable"] == 1
    result = asyncio.run(OperationalVerificationService(
        resolver=AsyncMock(return_value=make_target())
    ).verify(
        request,
        started_at=now,
        deadline=now + timedelta(seconds=5),
    ))
    completed = resumed.persist_verification_result(request, result)
    assert completed.state is OperationalLedgerState.VERIFICATION_FAILED
