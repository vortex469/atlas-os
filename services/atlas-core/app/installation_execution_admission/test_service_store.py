from __future__ import annotations

import ast
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.installation_execution_admission import service, store
from app.installation_execution_admission.contract import (
    InstallationExecutionAdmissionCreateV1,
)
from app.installation_execution_admission.service import (
    create_installation_execution_admission_service,
)
from app.installation_execution_admission.store import (
    InstallationExecutionAdmissionStore,
)
from app.installation_execution_admission.test_contract import (
    ADMISSION_ID,
    _grant,
)


class Reader:
    def __init__(self, evidence) -> None:
        self.evidence = evidence
        self.calls = 0

    def read_owned(self, **_kwargs):
        self.calls += 1
        return self.evidence


class Factory:
    def __init__(self, value: str = ADMISSION_ID) -> None:
        self.value = value
        self.calls = 0

    def __call__(self) -> str:
        self.calls += 1
        return self.value


def _clock(second: int = 30):
    instant = datetime(2026, 8, 27, 12, 0, tzinfo=UTC) + timedelta(seconds=second)
    return lambda: instant


def _service(tmp_path: Path, *, evidence=None, second: int = 30):
    grant, status = _grant(tmp_path / "evidence")
    evidence = evidence if evidence is not None else (grant, status, False)
    reader = Reader(evidence)
    factory = Factory()
    admission_store = InstallationExecutionAdmissionStore(
        tmp_path / "admissions.sqlite3"
    )
    admission_service = create_installation_execution_admission_service(
        evidence_reader=reader,
        store=admission_store,
        clock=_clock(second),
        id_factory=factory,
    )
    return admission_service, admission_store, reader, factory, grant, status


def _create(grant) -> InstallationExecutionAdmissionCreateV1:
    return InstallationExecutionAdmissionCreateV1(
        permission_grant_id=grant.grant_id,
        permission_grant_fingerprint=grant.grant_fingerprint,
        grant_valid_until=grant.valid_until,
    )


def _record(admission_service, grant, **changes):
    values = {
        "authenticated_operator_id": grant.operator_id,
        "permission_verified": True,
        "candidate_record_id": grant.candidate_record_id,
        "idempotency_key": "admission-key-1",
        "correlation_id": "admission-correlation-1",
    }
    values.update(changes)
    return admission_service.create(_create(grant), **values)


def test_create_get_list_and_restart_safe_readback(tmp_path: Path) -> None:
    admission_service, admission_store, reader, _, grant, _ = _service(tmp_path)
    created = _record(admission_service, grant)
    assert created.disposition == "recorded"
    assert created.status.lifecycle == "active"
    assert created.status.readiness == "admission_gated"
    assert created.admission.readiness == "admission_gated"
    assert reader.calls == 1
    assert not created.admission.execution_start_allowed
    assert not created.admission.runner_binding_allowed

    restarted = create_installation_execution_admission_service(
        evidence_reader=Reader(None),
        store=InstallationExecutionAdmissionStore(admission_store.database_path),
        clock=_clock(50),
        id_factory=Factory("89924dd8-bfef-40b2-b729-18363a42904b"),
    )
    readback = restarted.get(
        authenticated_operator_id=grant.operator_id,
        permission_verified=True,
        admission_id=ADMISSION_ID,
        correlation_id="admission-readback-1",
    )
    assert readback.admission == created.admission
    assert readback.status.lifecycle == "expired"
    listed = restarted.list(
        authenticated_operator_id=grant.operator_id,
        permission_verified=True,
        correlation_id="admission-list-1",
    )
    assert tuple(item.admission.admission_id for item in listed) == (ADMISSION_ID,)


def test_exact_duplicate_is_zero_reader_and_zero_id_allocation(tmp_path: Path) -> None:
    admission_service, admission_store, reader, factory, grant, _ = _service(tmp_path)
    created = _record(admission_service, grant)
    duplicate = _record(admission_service, grant)
    assert duplicate.disposition == "exact_duplicate"
    assert duplicate.admission == created.admission
    assert reader.calls == 1
    assert factory.calls == 1
    with sqlite3.connect(admission_store.database_path) as connection:
        schema = connection.execute(
            """SELECT sql FROM sqlite_master
            WHERE name = 'installation_execution_admissions'"""
        ).fetchone()[0]
        row = connection.execute(
            "SELECT * FROM installation_execution_admissions"
        ).fetchone()
    assert "admission-key-1" not in schema
    assert all("admission-key-1" not in str(value) for value in row)


def test_key_and_grant_subject_reservations_are_permanent(tmp_path: Path) -> None:
    admission_service, _, _, _, grant, _ = _service(tmp_path)
    assert _record(admission_service, grant).disposition == "recorded"
    changed_key = _record(
        admission_service, grant, idempotency_key="different-permanent-key"
    )
    assert changed_key.error.error_code == "conflict"
    assert changed_key.error.blocker_codes == ("subject_reserved",)

    changed = _create(grant).model_copy(
        update={"grant_valid_until": "2026-08-27T12:00:45Z"}
    )
    conflict = admission_service.create(
        changed,
        authenticated_operator_id=grant.operator_id,
        permission_verified=True,
        candidate_record_id=grant.candidate_record_id,
        idempotency_key="admission-key-1",
        correlation_id="admission-conflict-1",
    )
    assert conflict.error.error_code == "conflict"


def test_auth_owner_linkage_and_permission_fail_closed(tmp_path: Path) -> None:
    admission_service, _, reader, _, grant, status = _service(tmp_path)
    denied = _record(admission_service, grant, permission_verified=False)
    assert denied.error.error_code == "unauthorized"
    assert reader.calls == 0
    missing_auth = _record(
        admission_service, grant, authenticated_operator_id=None
    )
    assert missing_auth.error.error_code == "unauthenticated"

    foreign = _record(
        admission_service, grant, authenticated_operator_id="operator-b"
    )
    assert foreign.error.error_code == "not_found"
    assert reader.calls == 1

    mismatch_service, _, _, _, _, _ = _service(
        tmp_path / "mismatch", evidence=(grant, status, False)
    )
    mismatched = mismatch_service.create(
        _create(grant).model_copy(
            update={
                "permission_grant_fingerprint": grant.grant_fingerprint.model_copy(
                    update={"value": "f" * 64}
                )
            }
        ),
        authenticated_operator_id=grant.operator_id,
        permission_verified=True,
        candidate_record_id=grant.candidate_record_id,
        idempotency_key="mismatch-key",
        correlation_id="mismatch-correlation",
    )
    assert mismatched.error.error_code in {"not_found", "not_eligible"}
    assert "fingerprint" not in mismatched.error.model_dump_json()


def test_stale_expired_and_home_assistant_are_blocked(tmp_path: Path) -> None:
    stale_service, _, _, _, grant, _ = _service(tmp_path / "stale", second=61)
    stale = _record(stale_service, grant)
    assert stale.error.error_code == "expired"
    assert stale.error.blocker_codes in {
        ("stale_evidence",),
        ("expired_evidence",),
    }

    home_grant, home_status = _grant(tmp_path / "home-evidence")
    home_service, _, _, _, _, _ = _service(
        tmp_path / "home", evidence=(home_grant, home_status, True)
    )
    blocked = _record(home_service, home_grant)
    assert blocked.error.error_code == "not_eligible"
    assert blocked.error.blocker_codes == (
        "installation_capability_unsupported",
    )


def test_quota_size_corruption_and_foreign_readback_fail_closed(
    tmp_path: Path,
) -> None:
    admission_service, admission_store, _, _, grant, _ = _service(tmp_path)
    with sqlite3.connect(admission_store.database_path) as connection:
        for index in range(store.MAX_RECORDS_PER_OPERATOR):
            token = f"{index:064x}"
            connection.execute(
                """INSERT INTO installation_execution_admissions VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    grant.operator_id,
                    f"dummy-{index}",
                    f"candidate-{index}",
                    f"idem-{index}",
                    token,
                    f"request-{index}",
                    f"admission-{index}",
                    "2026-08-27T11:00:00Z",
                    "{}",
                    "{}",
                    "{}",
                ),
            )
    quota = _record(admission_service, grant)
    assert quota.error.error_code == "quota_exceeded"

    with sqlite3.connect(admission_store.database_path) as connection:
        connection.execute(
            """UPDATE installation_execution_admissions SET admission_json = ?
            WHERE admission_id = ?""",
            ("x" * (store.MAX_MODEL_BYTES + 1), "dummy-0"),
        )
    listed = admission_service.list(
        authenticated_operator_id=grant.operator_id,
        permission_verified=True,
        correlation_id="bounded-list-1",
    )
    assert len(listed) == 1 and listed[0].error.error_code == "unavailable"

    foreign = admission_service.get(
        authenticated_operator_id="operator-b",
        permission_verified=True,
        admission_id="dummy-1",
        correlation_id="foreign-read-1",
    )
    assert foreign.error.error_code == "not_found"


def test_persisted_corruption_is_redacted_and_audit_is_deterministic(
    tmp_path: Path,
) -> None:
    first_service, first_store, _, _, first_grant, _ = _service(tmp_path / "first")
    first = _record(first_service, first_grant)
    second_service, _, _, _, second_grant, _ = _service(tmp_path / "second")
    second = _record(second_service, second_grant)
    assert first.audit_evidence == second.audit_evidence

    with sqlite3.connect(first_store.database_path) as connection:
        connection.execute(
            "UPDATE installation_execution_admissions SET admission_fingerprint = ?",
            ("f" * 64,),
        )
    corrupt = first_service.get(
        authenticated_operator_id=first_grant.operator_id,
        permission_verified=True,
        admission_id=ADMISSION_ID,
        correlation_id="corrupt-read-1",
    )
    assert corrupt.error.error_code == "unavailable"
    assert "fingerprint" not in corrupt.error.model_dump_json()


def test_service_store_have_no_effect_dependencies_or_production_consumers() -> None:
    forbidden_imports = {
        "docker", "httpx", "requests", "socket", "subprocess", "urllib"
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

    app_root = Path(service.__file__).parents[1]
    allowed = {service.__file__, store.__file__}
    boundary_only = {
        "api/v1/router.py",
        "config/settings.py",
        "routes/installation_execution_admission.py",
        "runner_binding_plan/contract.py",
        "runner_binding_plan/service.py",
        "worker_admission_stub/contract.py",
        "worker_queue_reservation/contract.py",
        "worker_intake_admission/contract.py",
        "installation_live_enqueue_admission/contract.py",
        "installation_one_shot_live_enqueue/contract.py",
        "queue_observation_receipt/contract.py",
        "controlled_dequeue_admission/contract.py",
        "one_shot_controlled_dequeue/contract.py",
        "one_shot_dequeue_worker_binding/contract.py",
        "worker_binding_activation_preflight/contract.py",
    }
    consumers = _execution_admission_consumers(app_root, allowed, boundary_only)
    assert consumers == []


def test_service_store_consumer_scanner_rejects_unapproved_effect_consumer(
    tmp_path: Path,
) -> None:
    app_root = tmp_path / "app"
    effect_consumer = app_root / "unauthorized_worker" / "service.py"
    effect_consumer.parent.mkdir(parents=True)
    effect_consumer.write_text(
        "from app.installation_execution_admission.contract import FingerprintV1\n"
        "def activate_worker() -> None:\n"
        "    raise RuntimeError(FingerprintV1)\n"
    )
    boundary_contract = app_root / "worker_binding_activation_preflight" / "contract.py"
    boundary_contract.parent.mkdir(parents=True)
    boundary_contract.write_text(
        "from app.installation_execution_admission.contract import FingerprintV1\n"
    )

    consumers = _execution_admission_consumers(
        app_root,
        allowed=set(),
        boundary_only={"worker_binding_activation_preflight/contract.py"},
    )
    assert consumers == ["unauthorized_worker/service.py"]


def _execution_admission_consumers(
    app_root: Path, allowed: set[str], boundary_only: set[str]
) -> list[str]:
    consumers = []
    for path in app_root.rglob("*.py"):
        if str(path) in allowed or path.name.startswith("test_"):
            continue
        if "installation_execution_admission" in path.read_text():
            relative = str(path.relative_to(app_root))
            if relative not in boundary_only:
                consumers.append(relative)
    return consumers
