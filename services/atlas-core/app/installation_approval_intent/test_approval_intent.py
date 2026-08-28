from __future__ import annotations

import ast
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.installation_approval_intent.contract import (
    APPROVAL_STATEMENT,
    InstallationApprovalIntentV1,
    validate_approval_subject,
)
from app.installation_approval_intent.store import (
    ApprovalIntentCandidateUnavailableError,
    ApprovalIntentIdempotencyConflictError,
    ApprovalIntentLimitError,
    ApprovalIntentNotFoundError,
    ApprovalIntentRecordLimitError,
    ApprovalIntentStoreError,
    InstallationApprovalIntentStore,
)
from app.installation_candidate_lifecycle.store import (
    InstallationCandidateRecordStore,
)
from app.installation_candidate_lifecycle.test_lifecycle import NOW, admission


def stores(tmp_path: Path, current: list[datetime]):
    candidate_ids = iter(range(1, 100))
    intent_ids = iter(range(101, 200))
    candidates = InstallationCandidateRecordStore(
        tmp_path / "candidates.sqlite",
        clock=lambda: current[0],
        id_factory=lambda: uuid.UUID(
            f"00000000-0000-4000-8000-{next(candidate_ids):012d}"
        ),
    )
    intents = InstallationApprovalIntentStore(
        tmp_path / "intents.sqlite",
        candidates=candidates,
        clock=lambda: current[0],
        id_factory=lambda: uuid.UUID(
            f"00000000-0000-4000-8000-{next(intent_ids):012d}"
        ),
    )
    return candidates, intents


def candidate(candidates: InstallationCandidateRecordStore, index: int = 1):
    return candidates.preserve(
        owner_id="operator-a",
        idempotency_key=f"candidate-{index}",
        admission=admission(),
    )[0]


def test_closed_schema_fingerprint_fixed_statement_and_exact_binding(
    tmp_path: Path,
) -> None:
    candidates, intents = stores(tmp_path, [NOW])
    envelope = candidate(candidates)
    intent, created = intents.create(
        operator_id="operator-a",
        candidate_record_id=envelope.candidate_record_id,
        idempotency_key="approval-1",
    )
    assert created
    assert intent.statement == APPROVAL_STATEMENT
    assert intent.approved_subject.model_dump() == {
        "candidate_record_id": envelope.candidate_record_id,
        "candidate_envelope_fingerprint": envelope.envelope_fingerprint,
        "admission_fingerprint": envelope.admission_fingerprint,
        "candidate_record_fingerprint": envelope.candidate_record.record_fingerprint,
    }
    with pytest.raises(ValidationError):
        InstallationApprovalIntentV1.model_validate(
            {**intent.model_dump(), "command": "install"}
        )
    for field, value in (
        ("statement", "approved"),
        ("operator_id", "operator-b"),
        ("recorded_at", "2026-08-27T12:00:01Z"),
        ("intent_fingerprint", "0" * 64),
    ):
        changed = intent.model_dump()
        changed[field] = value
        with pytest.raises(ValidationError):
            InstallationApprovalIntentV1.model_validate(changed)


def test_append_only_replay_conflict_restart_and_operator_isolation(
    tmp_path: Path,
) -> None:
    current = [NOW]
    candidates, intents = stores(tmp_path, current)
    first_candidate = candidate(candidates)
    first, _ = intents.create(
        operator_id="operator-a",
        candidate_record_id=first_candidate.candidate_record_id,
        idempotency_key="approval",
    )
    replay, created = intents.create(
        operator_id="operator-a",
        candidate_record_id=first_candidate.candidate_record_id,
        idempotency_key="approval",
    )
    assert (replay, created) == (first, False)
    same_subject, created = intents.create(
        operator_id="operator-a",
        candidate_record_id=first_candidate.candidate_record_id,
        idempotency_key="another-key",
    )
    assert (same_subject, created) == (first, False)
    second_candidate = candidate(candidates, 2)
    with pytest.raises(ApprovalIntentIdempotencyConflictError):
        intents.create(
            operator_id="operator-a",
            candidate_record_id=second_candidate.candidate_record_id,
            idempotency_key="approval",
        )
    assert intents.list_for_operator("operator-b") == ()
    with pytest.raises(ApprovalIntentNotFoundError):
        intents.get(
            operator_id="operator-b", approval_intent_id=first.approval_intent_id
        )
    reopened = InstallationApprovalIntentStore(
        tmp_path / "intents.sqlite", candidates=candidates, clock=lambda: current[0]
    )
    assert reopened.get(
        operator_id="operator-a", approval_intent_id=first.approval_intent_id
    ) == first
    assert not hasattr(intents, "delete")
    assert not hasattr(intents, "update")


def test_rejects_expired_deleted_foreign_and_authority_bearing_candidates(
    tmp_path: Path,
) -> None:
    current = [NOW]
    candidates, intents = stores(tmp_path, current)
    envelope = candidate(candidates)
    with pytest.raises(ApprovalIntentCandidateUnavailableError):
        intents.create(
            operator_id="operator-b",
            candidate_record_id=envelope.candidate_record_id,
            idempotency_key="foreign",
        )
    current[0] = datetime.strptime(
        envelope.candidate_record.valid_until, "%Y-%m-%dT%H:%M:%SZ"
    ).replace(tzinfo=UTC)
    with pytest.raises(ValueError, match="not active"):
        intents.create(
            operator_id="operator-a",
            candidate_record_id=envelope.candidate_record_id,
            idempotency_key="expired",
        )
    current[0] = NOW
    candidates.delete(
        owner_id="operator-a", candidate_record_id=envelope.candidate_record_id
    )
    with pytest.raises(ApprovalIntentCandidateUnavailableError):
        intents.create(
            operator_id="operator-a",
            candidate_record_id=envelope.candidate_record_id,
            idempotency_key="deleted",
        )

    hostile_record = envelope.candidate_record.model_copy(
        update={"executable": True}
    )
    hostile = envelope.model_copy(update={"candidate_record": hostile_record})
    with pytest.raises(ValidationError):
        validate_approval_subject(
            hostile, operator_id="operator-a", recorded_at=envelope.created_at
        )


def test_home_assistant_and_unpreservable_input_cannot_create_intent(
    tmp_path: Path,
) -> None:
    candidates, intents = stores(tmp_path, [NOW])
    with pytest.raises(ValueError, match="not currently preservable"):
        candidates.preserve(
            owner_id="operator-a",
            idempotency_key="home-assistant",
            admission=admission(ready=False),
        )
    with pytest.raises(ApprovalIntentCandidateUnavailableError):
        intents.create(
            operator_id="operator-a",
            candidate_record_id="00000000-0000-4000-8000-000000000099",
            idempotency_key="approval",
        )


def test_count_size_corruption_and_no_replay(tmp_path: Path, monkeypatch) -> None:
    current = [NOW]
    candidates, intents = stores(tmp_path, current)
    first = None
    for index in range(16):
        envelope = candidate(candidates, index)
        value, _ = intents.create(
            operator_id="operator-a",
            candidate_record_id=envelope.candidate_record_id,
            idempotency_key=f"approval-{index}",
        )
        first = first or value
        candidates.delete(
            owner_id="operator-a", candidate_record_id=envelope.candidate_record_id
        )
    with pytest.raises(ApprovalIntentLimitError):
        envelope = candidate(candidates, 17)
        intents.create(
            operator_id="operator-a",
            candidate_record_id=envelope.candidate_record_id,
            idempotency_key="overflow",
        )

    monkeypatch.setattr(
        "app.installation_approval_intent.store.MAX_INTENT_BYTES", 1
    )
    with pytest.raises(ApprovalIntentStoreError, match="unavailable"):
        intents.get(
            operator_id="operator-a", approval_intent_id=first.approval_intent_id
        )
    monkeypatch.undo()
    with sqlite3.connect(intents.database_path) as connection:
        connection.execute(
            "UPDATE installation_approval_intents SET intent_json='{}' "
            "WHERE approval_intent_id=?",
            (first.approval_intent_id,),
        )
    with pytest.raises(ApprovalIntentStoreError, match="unavailable"):
        intents.get(
            operator_id="operator-a", approval_intent_id=first.approval_intent_id
        )
    # Neither corruption nor disappearance of the source causes recreation.
    with sqlite3.connect(intents.database_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM installation_approval_intents"
        ).fetchone()[0] == 16

    monkeypatch.setattr(
        "app.installation_approval_intent.store.MAX_INTENT_BYTES", 1
    )
    other_candidates, other_intents = stores(tmp_path / "size", [NOW])
    with pytest.raises(ApprovalIntentRecordLimitError):
        envelope = candidate(other_candidates)
        other_intents.create(
            operator_id="operator-a",
            candidate_record_id=envelope.candidate_record_id,
            idempotency_key="size",
        )


def test_visible_ascii_keys_and_no_forbidden_authority_imports_or_calls(
    tmp_path: Path,
) -> None:
    candidates, intents = stores(tmp_path, [NOW])
    envelope = candidate(candidates)
    for key in ("", "x" * 129, "has space", "nonascii-\u2603"):
        with pytest.raises(ValueError):
            intents.create(
                operator_id="operator-a",
                candidate_record_id=envelope.candidate_record_id,
                idempotency_key=key,
            )

    package = Path(__file__).parent
    trees = [
        ast.parse(path.read_text())
        for path in (package / "contract.py", package / "store.py")
    ]
    names = {
        alias.name
        for tree in trees
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    calls = {
        node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
        for tree in trees
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
    assert not names & forbidden
    assert not calls & forbidden
