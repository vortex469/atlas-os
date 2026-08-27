from __future__ import annotations

import ast
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.installation_candidate_admission.contract import (
    InstallationCandidateAdmissionV1,
    fingerprint,
)
from app.installation_candidate_admission.evaluation import (
    evaluate_installation_candidate_admission,
)
from app.installation_candidate_lifecycle.contract import (
    InstallationCandidateRecordEnvelopeV1,
    candidate_record_state,
)
from app.installation_candidate_lifecycle.store import (
    CandidateRecordEnvelopeLimitError,
    CandidateRecordIdempotencyConflictError,
    CandidateRecordIdempotencyDeletedError,
    CandidateRecordLimitError,
    CandidateRecordNotFoundError,
    CandidateRecordStoreError,
    InstallationCandidateRecordStore,
)
from app.installation_capability.test_assessment import (
    NOW,
    assess,
    destination,
    plan,
    selection,
)


def admission(*, ready: bool = True) -> InstallationCandidateAdmissionV1:
    value = plan(ready=ready)
    result = evaluate_installation_candidate_admission(
        plan=value,
        selection=selection(),
        current_destination=destination(),
        capability_assessment=assess(value),
        evaluated_at=NOW,
    )
    assert result is not None
    return result


def clock(at: datetime = NOW) -> list[datetime]:
    return [at]


def store(tmp_path: Path, current: list[datetime], *, database: str = "records.sqlite"):
    counter = iter(range(1, 100))
    return InstallationCandidateRecordStore(
        tmp_path / database,
        clock=lambda: current[0],
        id_factory=lambda: uuid.UUID(f"00000000-0000-4000-8000-{next(counter):012d}"),
    )


def test_closed_schema_exact_fingerprints_and_fixed_false_authority(tmp_path: Path) -> None:
    current = clock()
    envelope, created = store(tmp_path, current).preserve(
        owner_id="operator-a", idempotency_key="one", admission=admission()
    )
    assert created
    assert envelope.candidate_record.record_fingerprint
    assert not any((
        envelope.candidate_record.approved,
        envelope.candidate_record.executable,
        envelope.candidate_record.deployable,
        envelope.candidate_record.dispatchable,
        envelope.candidate_record.agent_execution_supported,
    ))
    with pytest.raises(ValidationError):
        InstallationCandidateRecordEnvelopeV1.model_validate(
            {**envelope.model_dump(), "command": "install"}
        )
    with pytest.raises(ValidationError):
        InstallationCandidateRecordEnvelopeV1.model_validate(
            {**envelope.model_dump(), "envelope_fingerprint": "0" * 64}
        )
    changed = envelope.model_dump(mode="json")
    changed["candidate_record"]["record_fingerprint"] = "0" * 64
    with pytest.raises(ValidationError):
        InstallationCandidateRecordEnvelopeV1.model_validate(changed)


def test_active_expired_delete_and_no_replay(tmp_path: Path) -> None:
    current = clock()
    records = store(tmp_path, current)
    envelope, _ = records.preserve(
        owner_id="operator-a", idempotency_key="one", admission=admission()
    )
    assert records.state(owner_id="operator-a", candidate_record_id=envelope.candidate_record_id) == "active"
    current[0] = datetime.strptime(
        envelope.candidate_record.valid_until, "%Y-%m-%dT%H:%M:%SZ"
    ).replace(tzinfo=UTC)
    assert records.state(owner_id="operator-a", candidate_record_id=envelope.candidate_record_id) == "expired"
    records.delete(owner_id="operator-a", candidate_record_id=envelope.candidate_record_id)
    with pytest.raises(CandidateRecordNotFoundError):
        records.get(owner_id="operator-a", candidate_record_id=envelope.candidate_record_id)
    current[0] = NOW
    with pytest.raises(CandidateRecordIdempotencyDeletedError):
        records.preserve(owner_id="operator-a", idempotency_key="one", admission=admission())


def test_half_open_boundary_and_invalid_precreation_observation(tmp_path: Path) -> None:
    current = clock()
    envelope, _ = store(tmp_path, current).preserve(
        owner_id="operator", idempotency_key="one", admission=admission()
    )
    assert candidate_record_state(envelope, now=envelope.created_at) == "active"
    assert candidate_record_state(envelope, now=envelope.candidate_record.valid_until) == "expired"
    with pytest.raises(ValueError):
        candidate_record_state(envelope, now="2026-08-27T11:59:59Z")


def test_idempotency_replay_conflict_and_restart_durability(tmp_path: Path) -> None:
    current = clock()
    records = store(tmp_path, current)
    first, _ = records.preserve(
        owner_id="operator", idempotency_key="one", admission=admission()
    )
    replay, replay_created = records.preserve(
        owner_id="operator", idempotency_key="one", admission=admission()
    )
    assert (replay, replay_created) == (first, False)
    other = admission()
    changed = other.model_dump(mode="json")
    changed["reason_codes"] = ()
    changed["evaluated_at"] = "2026-08-27T12:00:01Z"
    changed["candidate_record"]["evaluated_at"] = "2026-08-27T12:00:01Z"
    changed["candidate_record"]["record_fingerprint"] = fingerprint(
        "atlas:installation-candidate-record:v1",
        {k: v for k, v in changed["candidate_record"].items() if k != "record_fingerprint"},
    )
    changed["admission_fingerprint"] = fingerprint(
        "atlas:installation-candidate-admission:v1",
        {k: v for k, v in changed.items() if k != "admission_fingerprint"},
    )
    with pytest.raises(CandidateRecordIdempotencyConflictError):
        records.preserve(
            owner_id="operator",
            idempotency_key="one",
            admission=InstallationCandidateAdmissionV1.model_validate(changed),
        )
    reopened = InstallationCandidateRecordStore(tmp_path / "records.sqlite", clock=lambda: current[0])
    assert reopened.get(owner_id="operator", candidate_record_id=first.candidate_record_id) == first


def test_operator_isolation_and_sixteen_retained_records(tmp_path: Path) -> None:
    current = clock()
    records = store(tmp_path, current)
    first = None
    for index in range(16):
        value, _ = records.preserve(
            owner_id="operator-a", idempotency_key=f"key-{index}", admission=admission()
        )
        first = first or value
    with pytest.raises(CandidateRecordLimitError):
        records.preserve(owner_id="operator-a", idempotency_key="overflow", admission=admission())
    assert len(records.list_for_operator("operator-a")) == 16
    assert records.list_for_operator("operator-b") == ()
    with pytest.raises(CandidateRecordNotFoundError):
        records.get(owner_id="operator-b", candidate_record_id=first.candidate_record_id)
    records.preserve(owner_id="operator-b", idempotency_key="key-0", admission=admission())
    records.delete(owner_id="operator-a", candidate_record_id=first.candidate_record_id)
    records.preserve(owner_id="operator-a", idempotency_key="replacement", admission=admission())


def test_envelope_size_bound_and_corruption_is_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    current = clock()
    records = store(tmp_path, current)
    monkeypatch.setattr("app.installation_candidate_lifecycle.store.MAX_ENVELOPE_BYTES", 1)
    with pytest.raises(CandidateRecordEnvelopeLimitError):
        records.preserve(owner_id="operator", idempotency_key="one", admission=admission())
    monkeypatch.undo()
    envelope, _ = records.preserve(owner_id="operator", idempotency_key="two", admission=admission())
    with sqlite3.connect(records.database_path) as connection:
        connection.execute(
            "UPDATE installation_candidate_records SET envelope_json='{}' WHERE candidate_record_id=?",
            (envelope.candidate_record_id,),
        )
    with pytest.raises(CandidateRecordStoreError, match="unavailable"):
        records.get(owner_id="operator", candidate_record_id=envelope.candidate_record_id)


def test_rejects_stale_not_admitted_and_home_assistant(tmp_path: Path) -> None:
    current = clock()
    records = store(tmp_path, current)
    with pytest.raises(ValueError, match="not currently preservable"):
        records.preserve(owner_id="operator", idempotency_key="home", admission=admission(ready=False))
    positive = admission()
    current[0] = datetime.strptime(
        positive.candidate_record.valid_until, "%Y-%m-%dT%H:%M:%SZ"
    ).replace(tzinfo=UTC)
    with pytest.raises(ValueError, match="not currently preservable"):
        records.preserve(owner_id="operator", idempotency_key="stale", admission=positive)
    assert records.list_for_operator("operator") == ()


def test_visible_ascii_idempotency_bounds(tmp_path: Path) -> None:
    records = store(tmp_path, clock())
    for key in ("", "x" * 129, "has space", "nonascii-\N{SNOWMAN}"):
        with pytest.raises(ValueError):
            records.preserve(owner_id="operator", idempotency_key=key, admission=admission())


def test_no_authority_or_side_effect_imports_and_calls() -> None:
    package = Path(__file__).parent
    trees = [ast.parse(path.read_text()) for path in (package / "contract.py", package / "store.py")]
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
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Attribute, ast.Name))
    }
    forbidden = {
        "execution_candidates", "approval", "workflow", "dispatch", "agent",
        "worker", "provider_intents", "repository", "requests", "httpx",
        "socket", "subprocess", "execute_candidate", "approve",
    }
    assert not names & forbidden
    assert not calls & forbidden
