from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.installation_candidate_admission.contract import (
    InstallationCandidateAdmissionV1,
    fingerprint,
)
from app.installation_candidate_lifecycle.service import (
    InstallationCandidateLifecycleService,
)
from app.installation_candidate_lifecycle.store import (
    CandidateRecordIdempotencyConflictError,
    CandidateRecordNotFoundError,
    InstallationCandidateRecordStore,
)
from app.installation_candidate_lifecycle.test_lifecycle import NOW, admission


class Admissions:
    def __init__(self, result: InstallationCandidateAdmissionV1) -> None:
        self.result = result
        self.calls: list[tuple[str, str, str]] = []

    async def assemble(
        self, *, item_id: str, selection_id: str, principal_id: str
    ) -> InstallationCandidateAdmissionV1:
        self.calls.append((item_id, selection_id, principal_id))
        return self.result


def service(
    tmp_path: Path, admissions: Admissions, current: list[datetime]
) -> InstallationCandidateLifecycleService:
    records = InstallationCandidateRecordStore(
        tmp_path / "service.sqlite",
        clock=lambda: current[0],
        id_factory=lambda: uuid.UUID("00000000-0000-4000-8000-000000000001"),
    )
    return InstallationCandidateLifecycleService(
        store=records, admissions=admissions
    )


def test_service_recomputes_and_preserves_owned_positive_admission(
    tmp_path: Path,
) -> None:
    source = Admissions(admission())
    lifecycle = service(tmp_path, source, [NOW])

    record = asyncio.run(
        lifecycle.preserve(
            owner_id="operator-a",
            item_id="catalog-item",
            selection_id="00000000-0000-4000-8000-000000000099",
            idempotency_key="preserve-one",
        )
    )

    assert source.calls == [
        (
            "catalog-item",
            "00000000-0000-4000-8000-000000000099",
            "operator-a",
        )
    ]
    assert record.owner_id == "operator-a"
    assert record.admission_fingerprint == source.result.admission_fingerprint
    assert lifecycle.get(
        owner_id="operator-a", candidate_record_id=record.candidate_record_id
    ) == record
    with pytest.raises(CandidateRecordNotFoundError):
        lifecycle.get(
            owner_id="operator-b", candidate_record_id=record.candidate_record_id
        )


def test_service_replay_conflict_expiry_and_tombstone(tmp_path: Path) -> None:
    source = Admissions(admission())
    current = [NOW]
    lifecycle = service(tmp_path, source, current)
    arguments = {
        "owner_id": "operator",
        "item_id": "item",
        "selection_id": "00000000-0000-4000-8000-000000000099",
        "idempotency_key": "same-key",
    }
    first = asyncio.run(lifecycle.preserve(**arguments))
    assert asyncio.run(lifecycle.preserve(**arguments)) == first

    changed = source.result.model_dump()
    changed["evaluated_at"] = "2026-08-27T12:00:01Z"
    changed["candidate_record"]["evaluated_at"] = "2026-08-27T12:00:01Z"
    changed["candidate_record"]["record_fingerprint"] = fingerprint(
        "atlas:installation-candidate-record:v1",
        {
            key: value
            for key, value in changed["candidate_record"].items()
            if key != "record_fingerprint"
        },
    )
    changed["admission_fingerprint"] = fingerprint(
        "atlas:installation-candidate-admission:v1",
        {
            key: value
            for key, value in changed.items()
            if key != "admission_fingerprint"
        },
    )
    source.result = InstallationCandidateAdmissionV1.model_validate(changed)
    with pytest.raises(CandidateRecordIdempotencyConflictError):
        asyncio.run(lifecycle.preserve(**arguments))

    current[0] = datetime.strptime(
        first.candidate_record.valid_until, "%Y-%m-%dT%H:%M:%SZ"
    ).replace(tzinfo=UTC)
    assert lifecycle.state(
        owner_id="operator", candidate_record_id=first.candidate_record_id
    ) == "expired"
    lifecycle.delete(
        owner_id="operator", candidate_record_id=first.candidate_record_id
    )
    with pytest.raises(CandidateRecordNotFoundError):
        lifecycle.get(
            owner_id="operator", candidate_record_id=first.candidate_record_id
        )


def test_rejects_exactly_fingerprinted_but_mismatched_candidate(tmp_path: Path) -> None:
    value = admission().model_dump()
    value["plan_fingerprint"] = "1" * 64
    value["admission_fingerprint"] = fingerprint(
        "atlas:installation-candidate-admission:v1",
        {key: child for key, child in value.items() if key != "admission_fingerprint"},
    )
    crafted = InstallationCandidateAdmissionV1.model_validate(value)
    records = InstallationCandidateRecordStore(tmp_path / "mismatch.sqlite", clock=lambda: NOW)

    with pytest.raises(ValueError, match="identity disagree"):
        records.preserve(
            owner_id="operator", idempotency_key="mismatch", admission=crafted
        )
