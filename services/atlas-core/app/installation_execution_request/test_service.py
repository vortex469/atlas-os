from __future__ import annotations

import ast
import sqlite3
import uuid
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.installation_execution_request.contract import (
    InstallationExecutionRequestCreateV1,
)
from app.installation_execution_request.service import (
    InstallationExecutionRequestService,
)
from app.installation_execution_request.store import (
    ExecutionRequestNotCurrentError,
    ExecutionRequestNotFoundError,
    ExecutionRequestQuotaError,
    ExecutionRequestRecordLimitError,
    ExecutionRequestReplayConflictError,
    ExecutionRequestUnavailableError,
    InstallationExecutionRequestStore,
)
from app.installation_execution_request.test_contract import chain

NOW = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)


class Candidates:
    def __init__(self, values):
        self.values = {value.candidate_record_id: value for value in values}

    def get(self, *, owner_id: str, candidate_record_id: str):
        value = self.values[candidate_record_id]
        if value.owner_id != owner_id:
            raise KeyError
        return value


class Approvals:
    def __init__(self, values):
        self.values = {value.approval_intent_id: value for value in values}

    def get(self, *, operator_id: str, approval_intent_id: str):
        value = self.values[approval_intent_id]
        if value.operator_id != operator_id:
            raise KeyError
        return value


def setup(tmp_path: Path, *, enabled: bool = True, current=None):
    envelope, intent, create = chain(tmp_path / "chain")
    current = current or [NOW]
    store = InstallationExecutionRequestStore(
        tmp_path / "requests.sqlite",
        candidates=Candidates([envelope]),
        approvals=Approvals([intent]),
        clock=lambda: current[0],
        id_factory=lambda: uuid.UUID("00000000-0000-4000-8000-000000000301"),
    )
    return (
        InstallationExecutionRequestService(store=store, enabled=enabled),
        store,
        envelope,
        intent,
        create,
        current,
    )


def test_create_replay_passive_expiry_and_restart_durability(tmp_path: Path) -> None:
    service, store, envelope, intent, create, current = setup(tmp_path)
    request = service.record(
        operator_id="operator-a", idempotency_key="request", create=create
    )
    assert request.mode == "record-only"
    assert not any(
        (
            request.execution_authorized,
            request.dispatch_allowed,
            request.agent_invocation_allowed,
            request.mutation_allowed,
            request.replay_allowed,
        )
    )
    current[0] = NOW + timedelta(days=1)
    # Exact replay neither consults the stale chain nor extends the record.
    assert service.record(
        operator_id="operator-a", idempotency_key="request", create=create
    ) == request
    assert service.state(
        operator_id="operator-a", execution_request_id=request.execution_request_id
    ) == "expired"
    reopened = InstallationExecutionRequestStore(
        store.database_path,
        candidates=Candidates([envelope]),
        approvals=Approvals([intent]),
    )
    assert reopened.get(
        owner_id="operator-a", execution_request_id=request.execution_request_id
    ) == request


def test_default_disabled_linkage_staleness_and_idempotency_conflict(
    tmp_path: Path,
) -> None:
    disabled, _store, _envelope, _intent, create, _current = setup(
        tmp_path / "disabled", enabled=False
    )
    with pytest.raises(ExecutionRequestUnavailableError, match="^unavailable$"):
        disabled.record(
            operator_id="operator-a", idempotency_key="request", create=create
        )

    service, _store, _envelope, _intent, create, _current = setup(tmp_path / "live")
    service.record(operator_id="operator-a", idempotency_key="same", create=create)
    changed = deepcopy(create.model_dump(mode="json"))
    changed["candidate_record_id"] = "00000000-0000-4000-8000-000000000999"
    changed_create = InstallationExecutionRequestCreateV1.model_validate(changed)
    with pytest.raises(ExecutionRequestReplayConflictError, match="^replay_conflict$"):
        service.record(
            operator_id="operator-a", idempotency_key="same", create=changed_create
        )

    stale, *_ = setup(tmp_path / "stale", current=[NOW + timedelta(seconds=31)])
    with pytest.raises(ExecutionRequestNotCurrentError, match="^not_current$"):
        stale.record(
            operator_id="operator-a", idempotency_key="stale", create=create
        )


def test_no_replay_across_keys_and_ownership_isolation(tmp_path: Path) -> None:
    service, _store, _envelope, _intent, create, _current = setup(tmp_path)
    request = service.record(
        operator_id="operator-a", idempotency_key="first", create=create
    )
    with pytest.raises(ExecutionRequestReplayConflictError):
        service.record(
            operator_id="operator-a", idempotency_key="second", create=create
        )
    with pytest.raises(ExecutionRequestNotFoundError):
        service.get(
            operator_id="operator-b", execution_request_id=request.execution_request_id
        )
    assert service.list_for_operator(operator_id="operator-b") == ()
    for forbidden in ("delete", "cancel", "tombstone", "update", "refresh", "replay"):
        assert not hasattr(service, forbidden)


def test_quota_record_bound_and_corruption_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, store, _envelope, _intent, create, _current = setup(tmp_path)
    request = service.record(
        operator_id="operator-a", idempotency_key="first", create=create
    )
    with sqlite3.connect(store.database_path) as connection:
        connection.execute(
            "UPDATE installation_execution_requests SET request_json='{}' "
            "WHERE execution_request_id=?",
            (request.execution_request_id,),
        )
    with pytest.raises(ExecutionRequestUnavailableError, match="^unavailable$"):
        service.get(
            operator_id="operator-a", execution_request_id=request.execution_request_id
        )

    bounded, bounded_store, *_rest = setup(tmp_path / "bounded")
    monkeypatch.setattr(
        "app.installation_execution_request.store.MAX_RETAINED_REQUESTS_PER_OPERATOR",
        0,
    )
    with pytest.raises(ExecutionRequestQuotaError, match="^quota_exceeded$"):
        bounded.record(
            operator_id="operator-a", idempotency_key="quota", create=_rest[2]
        )
    monkeypatch.setattr(
        "app.installation_execution_request.store.MAX_RETAINED_REQUESTS_PER_OPERATOR",
        16,
    )
    monkeypatch.setattr("app.installation_execution_request.store.MAX_RECORD_BYTES", 1)
    with pytest.raises(ExecutionRequestRecordLimitError, match="^quota_exceeded$"):
        bounded_store.create(
            owner_id="operator-a", idempotency_key="size", create=_rest[2]
        )


def test_mismatch_is_redacted_and_modules_have_no_forbidden_consumers(
    tmp_path: Path,
) -> None:
    service, _store, envelope, _intent, create, _current = setup(tmp_path)
    hostile = envelope.model_copy(update={"owner_id": "operator-b"})
    service._store._candidates = Candidates([hostile])
    with pytest.raises(ExecutionRequestNotFoundError) as caught:
        service.record(
            operator_id="operator-a", idempotency_key="foreign", create=create
        )
    assert str(caught.value) == "not_found"

    forbidden = {
        "subprocess",
        "requests",
        "httpx",
        "socket",
        "dispatch",
        "worker",
        "provider",
        "repository",
        "execution_candidates",
    }
    for filename in ("store.py", "service.py"):
        tree = ast.parse((Path(__file__).parent / filename).read_text())
        imports = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        assert not imports & forbidden
    assert not hasattr(service, "dispatch")
    assert not hasattr(service, "execute")
