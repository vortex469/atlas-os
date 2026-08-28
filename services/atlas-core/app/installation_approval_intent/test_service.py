from __future__ import annotations

import ast
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.installation_approval_intent.contract import APPROVAL_STATEMENT
from app.installation_approval_intent.service import InstallationApprovalIntentService
from app.installation_approval_intent.store import (
    ApprovalIntentCandidateUnavailableError,
    ApprovalIntentIdempotencyConflictError,
    ApprovalIntentLimitError,
    ApprovalIntentNotFoundError,
    ApprovalIntentRecordLimitError,
    InstallationApprovalIntentStore,
)
from app.installation_candidate_lifecycle.contract import (
    InstallationCandidateRecordEnvelopeV1,
)
from app.installation_candidate_lifecycle.store import InstallationCandidateRecordStore
from app.installation_candidate_lifecycle.test_lifecycle import NOW, admission


def services(
    tmp_path: Path, current: list[datetime]
) -> tuple[
    InstallationCandidateRecordStore,
    InstallationApprovalIntentService,
]:
    candidate_ids = iter(range(1, 100))
    intent_ids = iter(range(101, 200))
    candidates = InstallationCandidateRecordStore(
        tmp_path / "candidates.sqlite",
        clock=lambda: current[0],
        id_factory=lambda: uuid.UUID(
            f"00000000-0000-4000-8000-{next(candidate_ids):012d}"
        ),
    )
    store = InstallationApprovalIntentStore(
        tmp_path / "intents.sqlite",
        candidates=candidates,
        clock=lambda: current[0],
        id_factory=lambda: uuid.UUID(
            f"00000000-0000-4000-8000-{next(intent_ids):012d}"
        ),
    )
    return candidates, InstallationApprovalIntentService(store=store)


def preserve(
    candidates: InstallationCandidateRecordStore,
    *,
    owner_id: str = "operator-a",
    index: int = 1,
) -> InstallationCandidateRecordEnvelopeV1:
    return candidates.preserve(
        owner_id=owner_id,
        idempotency_key=f"candidate-{index}",
        admission=admission(),
    )[0]


def test_records_fixed_evidence_for_current_owned_non_executable_candidate(
    tmp_path: Path,
) -> None:
    candidates, service = services(tmp_path, [NOW])
    envelope = preserve(candidates)

    intent = service.record(
        operator_id="operator-a",
        candidate_record_id=envelope.candidate_record_id,
        idempotency_key="approval-1",
    )

    assert intent.operator_id == "operator-a"
    assert intent.recorded_at == NOW.strftime("%Y-%m-%dT%H:%M:%SZ")
    assert intent.statement == APPROVAL_STATEMENT
    assert intent.approved_subject.model_dump() == {
        "candidate_record_id": envelope.candidate_record_id,
        "candidate_envelope_fingerprint": envelope.envelope_fingerprint,
        "admission_fingerprint": envelope.admission_fingerprint,
        "candidate_record_fingerprint": envelope.candidate_record.record_fingerprint,
    }
    assert service.get(
        operator_id="operator-a", approval_intent_id=intent.approval_intent_id
    ) == intent
    assert service.list_for_operator(operator_id="operator-a") == (intent,)
    assert set(intent.model_dump()) == {
        "schema",
        "approval_intent_id",
        "operator_id",
        "recorded_at",
        "approved_subject",
        "statement",
        "intent_fingerprint",
    }


def test_rejects_expired_deleted_foreign_and_non_owned_candidates(
    tmp_path: Path,
) -> None:
    current = [NOW]
    candidates, service = services(tmp_path, current)
    envelope = preserve(candidates)

    with pytest.raises(ApprovalIntentCandidateUnavailableError):
        service.record(
            operator_id="operator-b",
            candidate_record_id=envelope.candidate_record_id,
            idempotency_key="foreign",
        )

    current[0] = datetime.strptime(
        envelope.candidate_record.valid_until, "%Y-%m-%dT%H:%M:%SZ"
    ).replace(tzinfo=UTC)
    with pytest.raises(ValueError, match="not active"):
        service.record(
            operator_id="operator-a",
            candidate_record_id=envelope.candidate_record_id,
            idempotency_key="expired",
        )

    current[0] = NOW
    candidates.delete(
        owner_id="operator-a", candidate_record_id=envelope.candidate_record_id
    )
    with pytest.raises(ApprovalIntentCandidateUnavailableError):
        service.record(
            operator_id="operator-a",
            candidate_record_id=envelope.candidate_record_id,
            idempotency_key="deleted",
        )

    with pytest.raises(ValidationError):
        service.record(
            operator_id="has space",
            candidate_record_id=envelope.candidate_record_id,
            idempotency_key="invalid-owner",
        )


class HostileCandidates:
    def __init__(self, envelope: InstallationCandidateRecordEnvelopeV1) -> None:
        self.envelope = envelope

    def get(
        self, *, owner_id: str, candidate_record_id: str
    ) -> InstallationCandidateRecordEnvelopeV1:
        del owner_id, candidate_record_id
        record = self.envelope.candidate_record.model_copy(
            update={"approved": True, "executable": True}
        )
        return self.envelope.model_copy(update={"candidate_record": record})


def test_rejects_exactly_fingerprinted_authority_bearing_candidate(
    tmp_path: Path,
) -> None:
    candidates, _service = services(tmp_path, [NOW])
    envelope = preserve(candidates)
    store = InstallationApprovalIntentStore(
        tmp_path / "hostile.sqlite",
        candidates=HostileCandidates(envelope),
        clock=lambda: NOW,
    )

    with pytest.raises(ValidationError, match="Input should be False"):
        InstallationApprovalIntentService(store=store).record(
            operator_id="operator-a",
            candidate_record_id=envelope.candidate_record_id,
            idempotency_key="hostile",
        )


def test_fixed_statement_replay_conflict_duplicate_and_reopened_persistence(
    tmp_path: Path,
) -> None:
    current = [NOW]
    candidates, service = services(tmp_path, current)
    first_candidate = preserve(candidates)
    first = service.record(
        operator_id="operator-a",
        candidate_record_id=first_candidate.candidate_record_id,
        idempotency_key="approval",
    )
    assert service.record(
        operator_id="operator-a",
        candidate_record_id=first_candidate.candidate_record_id,
        idempotency_key="approval",
    ) == first
    assert service.record(
        operator_id="operator-a",
        candidate_record_id=first_candidate.candidate_record_id,
        idempotency_key="duplicate-subject",
    ) == first

    second_candidate = preserve(candidates, index=2)
    with pytest.raises(ApprovalIntentIdempotencyConflictError):
        service.record(
            operator_id="operator-a",
            candidate_record_id=second_candidate.candidate_record_id,
            idempotency_key="approval",
        )

    reopened = InstallationApprovalIntentService(
        store=InstallationApprovalIntentStore(
            tmp_path / "intents.sqlite", candidates=candidates, clock=lambda: current[0]
        )
    )
    assert reopened.get(
        operator_id="operator-a", approval_intent_id=first.approval_intent_id
    ) == first
    with pytest.raises(ApprovalIntentNotFoundError):
        reopened.get(
            operator_id="operator-b", approval_intent_id=first.approval_intent_id
        )
    assert not hasattr(service, "update")
    assert not hasattr(service, "delete")
    assert not hasattr(service, "refresh")
    assert not hasattr(service, "replay")


def test_service_enforces_count_and_size_bounds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidates, service = services(tmp_path, [NOW])
    for index in range(16):
        envelope = preserve(candidates, index=index)
        service.record(
            operator_id="operator-a",
            candidate_record_id=envelope.candidate_record_id,
            idempotency_key=f"approval-{index}",
        )
        candidates.delete(
            owner_id="operator-a", candidate_record_id=envelope.candidate_record_id
        )
    overflow = preserve(candidates, index=17)
    with pytest.raises(ApprovalIntentLimitError):
        service.record(
            operator_id="operator-a",
            candidate_record_id=overflow.candidate_record_id,
            idempotency_key="overflow",
        )

    monkeypatch.setattr("app.installation_approval_intent.store.MAX_INTENT_BYTES", 1)
    other_candidates, other_service = services(tmp_path / "size", [NOW])
    envelope = preserve(other_candidates)
    with pytest.raises(ApprovalIntentRecordLimitError):
        other_service.record(
            operator_id="operator-a",
            candidate_record_id=envelope.candidate_record_id,
            idempotency_key="oversize",
        )


def test_home_assistant_cannot_be_approved_and_service_has_no_forbidden_calls(
    tmp_path: Path,
) -> None:
    candidates, service = services(tmp_path, [NOW])
    with pytest.raises(ValueError, match="not currently preservable"):
        candidates.preserve(
            owner_id="operator-a",
            idempotency_key="home-assistant",
            admission=admission(ready=False),
        )
    with pytest.raises(ApprovalIntentCandidateUnavailableError):
        service.record(
            operator_id="operator-a",
            candidate_record_id="00000000-0000-4000-8000-000000000099",
            idempotency_key="approval",
        )

    tree = ast.parse((Path(__file__).parent / "service.py").read_text())
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    calls = {
        node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, (ast.Attribute, ast.Name))
    }
    forbidden = {
        "execution_candidates",
        "approval",
        "workflow",
        "dispatch",
        "agent",
        "worker",
        "provider_intents",
        "repository",
        "requests",
        "httpx",
        "socket",
        "subprocess",
        "execute_candidate",
        "approve",
    }
    assert not imports & forbidden
    assert not calls & forbidden
