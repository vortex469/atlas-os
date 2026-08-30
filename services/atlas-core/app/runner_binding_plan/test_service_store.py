from __future__ import annotations

import ast
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.runner_binding_plan import service, store
from app.runner_binding_plan.contract import RunnerBindingPlanCreateV1
from app.runner_binding_plan.service import create_runner_binding_plan_service
from app.runner_binding_plan.store import RunnerBindingPlanStore
from app.runner_binding_plan.test_contract import PLAN_ID, _validation


class Reader:
    def __init__(self, value) -> None:
        self.value = value
        self.calls = 0

    def read_owned(self, **_kwargs):
        self.calls += 1
        return self.value


class Factory:
    def __init__(self, value: str = PLAN_ID) -> None:
        self.value = value
        self.calls = 0

    def __call__(self) -> str:
        self.calls += 1
        return self.value


def _clock(second: int = 32):
    instant = datetime(2026, 8, 27, 12, 0, tzinfo=UTC) + timedelta(seconds=second)
    return lambda: instant


def _fixtures(tmp_path: Path):
    validation = _validation(tmp_path / "evidence")
    return (
        validation.execution_admission,
        validation.execution_admission_status,
        validation.runner_reference,
    )


def _service(
    tmp_path: Path,
    *,
    evidence=None,
    runner=None,
    second: int = 32,
    quota: int = 16,
):
    admission, status, reference = _fixtures(tmp_path)
    evidence_reader = Reader(
        evidence if evidence is not None else (admission, status, False)
    )
    runner_reader = Reader(reference if runner is None else runner)
    factory = Factory()
    plan_store = RunnerBindingPlanStore(
        tmp_path / "runner-binding-plans.sqlite3",
        max_records_per_operator=quota,
    )
    plan_service = create_runner_binding_plan_service(
        evidence_reader=evidence_reader,
        runner_reader=runner_reader,
        store=plan_store,
        clock=_clock(second),
        id_factory=factory,
    )
    return (
        plan_service,
        plan_store,
        evidence_reader,
        runner_reader,
        factory,
        admission,
        status,
        reference,
    )


def _create(admission, runner) -> RunnerBindingPlanCreateV1:
    return RunnerBindingPlanCreateV1(
        admission_id=admission.admission_id,
        admission_fingerprint=admission.admission_fingerprint,
        admission_valid_until=admission.valid_until,
        runner_reference_id=runner.runner_reference_id,
        runner_reference_fingerprint=runner.reference_fingerprint,
        limits_fingerprint=runner.limits.limits_fingerprint,
    )


def _record(plan_service, admission, runner, **changes):
    values = {
        "authenticated_operator_id": admission.operator_id,
        "permission_verified": True,
        "candidate_record_id": admission.candidate_record_id,
        "idempotency_key": "runner-binding-plan-key-1",
        "correlation_id": "runner-binding-plan-correlation-1",
    }
    values.update(changes)
    return plan_service.create(_create(admission, runner), **values)


def test_create_get_list_and_restart_safe_readback(tmp_path: Path) -> None:
    plan_service, plan_store, evidence_reader, runner_reader, _, admission, _, runner = _service(tmp_path)
    created = _record(plan_service, admission, runner)
    assert created.disposition == "recorded"
    assert created.status.lifecycle == "active"
    assert created.status.eligibility == "binding_planned"
    assert created.plan.eligibility == "binding_planned"
    assert evidence_reader.calls == runner_reader.calls == 1
    assert not created.plan.runner_bound
    assert not created.plan.execution_authorized

    restarted = create_runner_binding_plan_service(
        evidence_reader=Reader(None),
        runner_reader=Reader(None),
        store=RunnerBindingPlanStore(plan_store.database_path),
        clock=_clock(50),
        id_factory=Factory("89924dd8-bfef-40b2-b729-18363a42904b"),
    )
    readback = restarted.get(
        authenticated_operator_id=admission.operator_id,
        permission_verified=True,
        plan_id=PLAN_ID,
        correlation_id="readback",
    )
    assert readback.plan == created.plan
    assert readback.status.lifecycle == "expired"
    listed = restarted.list(
        authenticated_operator_id=admission.operator_id,
        permission_verified=True,
        correlation_id="list",
    )
    assert tuple(item.plan.plan_id for item in listed) == (PLAN_ID,)
    assert restarted.get(
        authenticated_operator_id="operator-b",
        permission_verified=True,
        plan_id=PLAN_ID,
        correlation_id="foreign",
    ).error.error_code == "not_found"
    assert restarted.list(
        authenticated_operator_id="operator-b",
        permission_verified=True,
        correlation_id="foreign-list",
    ) == ()
    assert restarted.get(
        authenticated_operator_id=admission.operator_id,
        permission_verified=True,
        plan_id=PLAN_ID,
        correlation_id="deterministic-read",
    ) == restarted.get(
        authenticated_operator_id=admission.operator_id,
        permission_verified=True,
        plan_id=PLAN_ID,
        correlation_id="deterministic-read",
    )


def test_exact_duplicate_is_zero_reader_and_raw_key_is_never_persisted(tmp_path: Path) -> None:
    plan_service, plan_store, evidence_reader, runner_reader, factory, admission, _, runner = _service(tmp_path)
    created = _record(plan_service, admission, runner)
    duplicate = _record(plan_service, admission, runner)
    assert duplicate.disposition == "exact_duplicate"
    assert duplicate.plan == created.plan
    assert evidence_reader.calls == runner_reader.calls == factory.calls == 1
    with sqlite3.connect(plan_store.database_path) as connection:
        schema = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'runner_binding_plans'"
        ).fetchone()[0]
        row = connection.execute("SELECT * FROM runner_binding_plans").fetchone()
    assert "runner-binding-plan-key-1" not in schema
    assert all("runner-binding-plan-key-1" not in str(value) for value in row)


def test_idempotency_conflict_and_permanent_subject_reservation(tmp_path: Path) -> None:
    plan_service, _, _, _, _, admission, _, runner = _service(tmp_path)
    assert _record(plan_service, admission, runner).disposition == "recorded"
    subject_retry = _record(
        plan_service,
        admission,
        runner,
        idempotency_key="another-permanent-key",
    )
    assert subject_retry.error.error_code == "conflict"
    changed = _create(admission, runner).model_copy(
        update={"admission_valid_until": "2026-08-27T12:00:44Z"}
    )
    conflict = plan_service.create(
        changed,
        authenticated_operator_id=admission.operator_id,
        permission_verified=True,
        candidate_record_id=admission.candidate_record_id,
        idempotency_key="runner-binding-plan-key-1",
        correlation_id="conflict",
    )
    assert conflict.error.error_code == "conflict"


def test_auth_permission_owner_and_missing_evidence_fail_closed(tmp_path: Path) -> None:
    plan_service, _, evidence_reader, _, _, admission, _, runner = _service(tmp_path)
    assert _record(plan_service, admission, runner, permission_verified=False).error.error_code == "unauthorized"
    assert _record(plan_service, admission, runner, authenticated_operator_id=None).error.error_code == "unauthenticated"
    assert evidence_reader.calls == 0
    foreign = _record(plan_service, admission, runner, authenticated_operator_id="operator-b")
    assert foreign.error.error_code == "not_found"
    missing, _, _, _, _, admission2, _, runner2 = _service(
        tmp_path / "missing", evidence=Reader(None).value
    )
    missing._evidence_reader = Reader(None)  # explicitly injected test dependency
    assert _record(missing, admission2, runner2).error.error_code == "not_found"


def test_stale_expired_home_assistant_and_runner_mismatch_are_blocked(tmp_path: Path) -> None:
    stale, _, _, _, _, admission, _, runner = _service(tmp_path / "stale", second=50)
    assert _record(stale, admission, runner).error.error_code == "expired"

    admission2, status2, runner2 = _fixtures(tmp_path / "home-fixture")
    home, *_ = _service(
        tmp_path / "home", evidence=(admission2, status2, True), runner=runner2
    )
    assert _record(home, admission2, runner2).error.error_code == "not_eligible"

    mismatch, _, _, _, _, admission3, _, runner3 = _service(tmp_path / "mismatch")
    bad_create = _create(admission3, runner3).model_copy(
        update={
            "runner_reference_fingerprint": runner3.reference_fingerprint.model_copy(
                update={"value": "f" * 64}
            )
        }
    )
    result = mismatch.create(
        bad_create,
        authenticated_operator_id=admission3.operator_id,
        permission_verified=True,
        candidate_record_id=admission3.candidate_record_id,
        idempotency_key="mismatch",
        correlation_id="secret/internal/path",
    )
    assert result.error.error_code == "not_eligible"
    assert "secret/internal/path" not in result.model_dump_json()


def test_quota_record_bounds_and_corruption_fail_closed(tmp_path: Path, monkeypatch) -> None:
    quota_service, _, _, _, _, admission, _, runner = _service(tmp_path / "quota", quota=0)
    assert _record(quota_service, admission, runner).error.error_code == "quota_exceeded"

    bounded, _, _, _, _, admission2, _, runner2 = _service(tmp_path / "bounded")
    monkeypatch.setattr(store, "MAX_MODEL_BYTES", 1)
    assert _record(bounded, admission2, runner2).error.error_code == "unavailable"
    monkeypatch.undo()

    clean, plan_store, _, _, _, admission3, _, runner3 = _service(tmp_path / "corrupt")
    assert _record(clean, admission3, runner3).disposition == "recorded"
    with sqlite3.connect(plan_store.database_path) as connection:
        connection.execute(
            "UPDATE runner_binding_plans SET plan_json = ?", ("{}",)
        )
    assert clean.get(
        authenticated_operator_id=admission3.operator_id,
        permission_verified=True,
        plan_id=PLAN_ID,
        correlation_id="corrupt",
    ).error.error_code == "unavailable"


def test_service_store_have_no_effect_imports_and_no_production_consumers() -> None:
    root = Path(__file__).resolve().parents[1]
    forbidden_imports = {
        "subprocess", "docker", "podman", "requests", "httpx", "socket",
        "app.agent", "app.dispatch", "app.worker", "app.workflow",
    }
    for module in (service, store):
        tree = ast.parse(Path(module.__file__).read_text())
        imported = {
            name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for name in (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
            )
        }
        assert not (imported & forbidden_imports)
        assert not any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in {"bind", "execute", "dispatch", "retry", "resend", "start"}
            for node in ast.walk(tree)
        )
    consumers = []
    for path in root.rglob("*.py"):
        if path.parent.name == "runner_binding_plan" or path.name.startswith("test_"):
            continue
        if "runner_binding_plan.service" in path.read_text() or "RunnerBindingPlanService" in path.read_text():
            consumers.append(path)
    assert consumers == []


def test_store_has_no_update_delete_or_release_api() -> None:
    assert not any(
        hasattr(RunnerBindingPlanStore, name)
        for name in ("update", "delete", "release", "consume", "reserve_runner")
    )
    assert "UPDATE runner_binding_plans" not in Path(store.__file__).read_text()
    assert "DELETE FROM runner_binding_plans" not in Path(store.__file__).read_text()
