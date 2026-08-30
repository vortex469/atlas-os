from __future__ import annotations

import ast
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.execution_permission_grant import service, store
from app.execution_permission_grant.contract import (
    CONFIRMATION_TEXT,
    ExecutionPermissionGrantCreateV1,
)
from app.execution_permission_grant.service import (
    create_execution_permission_grant_service,
)
from app.execution_permission_grant.store import ExecutionPermissionGrantStore
from app.installation_readiness_review.contract import (
    create_installation_readiness_review,
)
from app.installation_readiness_review.test_contract import (
    CORRELATION_ID,
)
from app.installation_readiness_review.test_contract import (
    _input as readiness_input,
)

GRANT_ID = "319e9180-02fe-442e-88fc-4adf6709546a"
CANDIDATE = "2f4bb970-799c-47ac-8b53-c416ffe29f3d"


class Reader:
    def __init__(self, response) -> None:
        self.response = response
        self.calls = 0

    def read_owned(self, **_kwargs):
        self.calls += 1
        return self.response


class Factory:
    def __init__(self, value: str = GRANT_ID) -> None:
        self.value = value
        self.calls = 0

    def __call__(self) -> str:
        self.calls += 1
        return self.value


def _response(tmp_path: Path, **changes):
    tmp_path.mkdir(parents=True, exist_ok=True)
    return create_installation_readiness_review(
        readiness_input(tmp_path, **changes), correlation_id=CORRELATION_ID
    )


def _create(response) -> ExecutionPermissionGrantCreateV1:
    return ExecutionPermissionGrantCreateV1(
        readiness_review_id=response.review.review_id,
        readiness_review_fingerprint=response.review.review_fingerprint,
        review_observed_at=response.review.observed_at,
        confirmation_text=CONFIRMATION_TEXT,
    )


def _clock(second: int = 20):
    return lambda: datetime(2026, 8, 27, 12, 0, second, tzinfo=UTC)


def _service(tmp_path: Path, *, response=None, second: int = 20):
    response = response or _response(tmp_path)
    reader = Reader(response)
    factory = Factory()
    grant_store = ExecutionPermissionGrantStore(tmp_path / "grants.sqlite3")
    grant_service = create_execution_permission_grant_service(
        evidence_reader=reader,
        store=grant_store,
        clock=_clock(second),
        id_factory=factory,
    )
    return grant_service, grant_store, reader, factory, response


def _record(grant_service, response, **changes):
    values = {
        "authenticated_operator_id": "operator-a",
        "permission_verified": True,
        "candidate_record_id": response.review.candidate_record_id,
        "idempotency_key": "permission-key-1",
        "correlation_id": "permission-correlation-1",
    }
    values.update(changes)
    return grant_service.create(_create(response), **values)


def test_valid_create_get_list_and_restart_safe_readback(tmp_path: Path) -> None:
    grant_service, grant_store, reader, _, response = _service(tmp_path)
    created = _record(grant_service, response)
    assert created.disposition == "recorded"
    assert created.status.lifecycle == "active"
    assert reader.calls == 1
    assert not created.grant.execution_authorized

    restarted = create_execution_permission_grant_service(
        evidence_reader=Reader(None),
        store=ExecutionPermissionGrantStore(grant_store.database_path),
        clock=_clock(50),
        id_factory=Factory("89924dd8-bfef-40b2-b729-18363a42904b"),
    )
    readback = restarted.get(
        authenticated_operator_id="operator-a",
        permission_verified=True,
        grant_id=GRANT_ID,
        correlation_id="permission-readback-1",
    )
    assert readback.grant == created.grant
    assert readback.status.lifecycle == "expired"
    listed = restarted.list(
        authenticated_operator_id="operator-a",
        permission_verified=True,
        correlation_id="permission-list-1",
    )
    assert tuple(item.grant.grant_id for item in listed) == (GRANT_ID,)


def test_exact_duplicate_is_zero_reader_and_zero_id_allocation(tmp_path: Path) -> None:
    grant_service, _, reader, factory, response = _service(tmp_path)
    created = _record(grant_service, response)
    duplicate = _record(grant_service, response)
    assert duplicate.disposition == "exact_duplicate"
    assert duplicate.grant == created.grant
    assert reader.calls == 1
    assert factory.calls == 1
    with sqlite3.connect(tmp_path / "grants.sqlite3") as connection:
        schema = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'execution_permission_grants'"
        ).fetchone()[0]
        row = connection.execute(
            "SELECT * FROM execution_permission_grants"
        ).fetchone()
    assert "permission-key-1" not in schema
    assert all("permission-key-1" not in str(value) for value in row)


def test_key_and_review_subject_reservations_are_permanent(tmp_path: Path) -> None:
    grant_service, _, _, _, response = _service(tmp_path)
    assert _record(grant_service, response).disposition == "recorded"
    changed_key = _record(
        grant_service, response, idempotency_key="different-permanent-key"
    )
    assert changed_key.error.error_code == "conflict"

    changed_create = _create(response).model_copy(
        update={"review_observed_at": "2026-08-27T12:00:15Z"}
    )
    changed_request = grant_service.create(
        changed_create,
        authenticated_operator_id="operator-a",
        permission_verified=True,
        candidate_record_id=response.review.candidate_record_id,
        idempotency_key="permission-key-1",
        correlation_id="permission-conflict-1",
    )
    assert changed_request.error.error_code == "conflict"


def test_stale_blocked_owner_and_permission_fail_closed(tmp_path: Path) -> None:
    stale_service, _, stale_reader, _, response = _service(tmp_path, second=47)
    stale = _record(stale_service, response)
    assert stale.error.error_code == "expired"
    assert stale_reader.calls == 1

    blocked = _response(
        tmp_path, home_assistant=True, installation_capability_supported=False
    )
    blocked_service, _, _, _, _ = _service(tmp_path / "blocked", response=blocked)
    rejected = _record(blocked_service, blocked)
    assert rejected.error.error_code == "not_readiness_gated"

    foreign = _response(
        tmp_path / "foreign",
        operator_id="operator-b",
        authenticated_operator_id="operator-b",
    )
    foreign_service, _, _, _, _ = _service(tmp_path / "owned", response=foreign)
    isolated = _record(foreign_service, foreign)
    assert isolated.error.error_code == "not_found"

    denied_service, _, denied_reader, _, denied_response = _service(tmp_path / "denied")
    denied = _record(denied_service, denied_response, permission_verified=False)
    assert denied.error.error_code == "unauthorized"
    assert denied_reader.calls == 0
    unauthenticated = _record(
        denied_service, denied_response, authenticated_operator_id=None
    )
    assert unauthenticated.error.error_code == "unauthenticated"


def test_invalid_confirmation_and_errors_are_redacted(tmp_path: Path) -> None:
    grant_service, _, reader, _, response = _service(tmp_path)
    invalid_raw = _create(response).model_dump(mode="python")
    invalid_raw["confirmation_text"] = "secret operator note"
    invalid = ExecutionPermissionGrantCreateV1.model_construct(
        **invalid_raw,
    )
    result = grant_service.create(
        invalid,
        authenticated_operator_id="operator-a",
        permission_verified=True,
        candidate_record_id=response.review.candidate_record_id,
        idempotency_key="permission-key-1",
        correlation_id="bad correlation value",
    )
    assert result.error.error_code == "confirmation_mismatch"
    assert result.error.correlation_id == "execution-permission-redacted"
    assert reader.calls == 0
    rendered = result.model_dump_json()
    assert "secret operator note" not in rendered
    assert "permission-key-1" not in rendered


def test_quota_and_record_bounds_fail_closed(tmp_path: Path) -> None:
    grant_service, grant_store, _, _, response = _service(tmp_path)
    with sqlite3.connect(grant_store.database_path) as connection:
        for index in range(store.MAX_RECORDS_PER_OPERATOR):
            token = f"{index:064x}"
            connection.execute(
                """INSERT INTO execution_permission_grants VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    "operator-a",
                    f"dummy-{index}",
                    f"candidate-{index}",
                    f"idem-{index}",
                    token,
                    f"request-{index}",
                    f"grant-{index}",
                    "2026-08-27T11:00:00Z",
                    "{}",
                    "{}",
                    "{}",
                ),
            )
    quota = _record(grant_service, response)
    assert quota.error.error_code == "quota_exceeded"

    with sqlite3.connect(grant_store.database_path) as connection:
        connection.execute(
            "UPDATE execution_permission_grants SET grant_json = ? WHERE grant_id = ?",
            ("x" * (store.MAX_MODEL_BYTES + 1), "dummy-0"),
        )
    listed = grant_service.list(
        authenticated_operator_id="operator-a",
        permission_verified=True,
        correlation_id="bounded-list-1",
    )
    assert len(listed) == 1 and listed[0].error.error_code == "unavailable"


def test_corruption_foreign_readback_and_audit_determinism(tmp_path: Path) -> None:
    first_service, first_store, _, _, first_response = _service(tmp_path / "first")
    first = _record(first_service, first_response)
    second_service, _, _, _, second_response = _service(tmp_path / "second")
    second = _record(second_service, second_response)
    assert first.audit_evidence == second.audit_evidence

    foreign = first_service.get(
        authenticated_operator_id="operator-b",
        permission_verified=True,
        grant_id=GRANT_ID,
        correlation_id="foreign-read-1",
    )
    assert foreign.error.error_code == "not_found"

    with sqlite3.connect(first_store.database_path) as connection:
        connection.execute(
            "UPDATE execution_permission_grants SET grant_fingerprint = ?",
            ("f" * 64,),
        )
    corrupt = first_service.get(
        authenticated_operator_id="operator-a",
        permission_verified=True,
        grant_id=GRANT_ID,
        correlation_id="corrupt-read-1",
    )
    assert corrupt.error.error_code == "unavailable"
    assert "fingerprint" not in corrupt.error.model_dump_json()


def test_service_and_store_have_no_forbidden_imports_or_calls() -> None:
    forbidden_imports = {
        "docker",
        "httpx",
        "requests",
        "socket",
        "subprocess",
        "urllib",
    }
    forbidden_calls = {"exec", "eval", "open", "Popen", "run", "system"}
    for module in (service, store):
        tree = ast.parse(Path(module.__file__).read_text())
        imports = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imports.update(
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        calls = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert imports.isdisjoint(forbidden_imports)
        assert calls.isdisjoint(forbidden_calls)
