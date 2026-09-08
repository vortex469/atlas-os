"""Hostile P2 persistence checks using the complete P1 prerequisite chain."""

import ast
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.worker_activation_runtime_plan import contract as c
from app.worker_activation_runtime_plan import test_contract as p1
from app.worker_activation_runtime_plan.readers import (
    WorkerActivationRuntimePlanPrerequisiteStoreReader,
)
from app.worker_activation_runtime_plan.service import (
    WorkerActivationRuntimePlanService,
)
from app.worker_activation_runtime_plan.store import (
    WorkerActivationRuntimePlanStore,
    WorkerActivationRuntimePlanStoreError,
)
from app.worker_activation_runtime_plan.test_contract import (
    admission_facts,  # noqa: F401
    prior_facts,  # noqa: F401
)


@pytest.fixture(scope="module")
def facts(request):
    return p1.facts.__wrapped__(request)


class Reader:
    def __init__(self, facts):
        self.pair = (
            facts.worker_activation_runtime_admission,
            facts.worker_activation_runtime_admission_status,
        )
        self.calls = 0
        self.hook = None

    def read_owned(self, **kwargs):
        self.calls += 1
        if self.hook:
            return self.hook(self.calls)
        return self.pair


class Clock:
    def __init__(self, facts):
        self.now = datetime.fromisoformat(facts.authority.request_received_at)

    def __call__(self):
        return self.now


def setup(tmp_path, facts, *, enabled=True, **bounds):
    journal = WorkerActivationRuntimePlanStore(tmp_path / "v055.sqlite", **bounds)
    reader = Reader(facts)
    clock = Clock(facts)
    service = WorkerActivationRuntimePlanService(
        prerequisite_reader=reader, store=journal, clock=clock, enabled=enabled
    )
    return service, journal, reader, clock


def create(service, facts, **kwargs):
    arguments = {
        "authenticated_operator_id": facts.operator_id,
        "permission_verified": True,
        "candidate_record_id": facts.candidate_record_id,
        "idempotency_key": "v055-service-idempotency",
        "correlation_id": "private-correlation",
    }
    arguments.update(kwargs)
    return service.create(facts.create, **arguments)


def counts(journal):
    with sqlite3.connect(journal.database_path) as connection:
        return tuple(
            connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in ("reservations", "evidence", "failures")
        )


def error(result, code):
    assert isinstance(result, c.WorkerActivationRuntimePlanRedactedErrorV1)
    assert result.error_code == code
    assert result.retryable is False
    assert "private" not in result.model_dump_json()


def test_restart_duplicate_expiry_ownership_and_subject_replay(tmp_path, facts):
    service, journal, reader, clock = setup(tmp_path, facts)
    first = create(service, facts)
    assert isinstance(first, c.WorkerActivationRuntimePlanResultV1)
    assert reader.calls == 2
    assert not first.exact_duplicate
    assert first.record.blockers == c.SUCCESS_BLOCKERS
    assert (
        first.record.runtime_plan_record_fingerprint
        == c.runtime_plan_record_fingerprint(first.record)
    )
    assert counts(journal) == (1, 1, 0)
    clock.now = datetime.fromisoformat(first.record.valid_until) + timedelta(seconds=1)
    reader.hook = lambda _: pytest.fail("duplicate must not read prerequisites")
    restarted = WorkerActivationRuntimePlanStore(journal.database_path)
    service._store = restarted
    duplicate = create(service, facts)
    assert duplicate.exact_duplicate
    assert duplicate.record == first.record
    assert duplicate.status.lifecycle == "expired"
    assert counts(journal) == (1, 1, 0)
    error(
        create(service, facts, idempotency_key="a-different-v055-key"),
        "permanent_subject_reserved",
    )
    altered = facts.create.model_copy(update={"valid_until": "2099-01-01T00:00:00Z"})
    error(
        service.create(
            altered,
            authenticated_operator_id=facts.operator_id,
            permission_verified=True,
            candidate_record_id=facts.candidate_record_id,
            idempotency_key="v055-service-idempotency",
            correlation_id="private",
        ),
        "idempotency_conflict",
    )
    for owner, candidate in (
        ("foreign", facts.candidate_record_id),
        (facts.operator_id, "00000000-0000-4000-8000-000000000000"),
    ):
        error(
            service.get(
                authenticated_operator_id=owner,
                permission_verified=True,
                candidate_record_id=candidate,
                runtime_plan_id=first.record.runtime_plan_id,
                correlation_id="private",
            ),
            "evidence_not_found",
        )
    collection = service.list(
        authenticated_operator_id=facts.operator_id,
        permission_verified=True,
        candidate_record_id=facts.candidate_record_id,
        correlation_id="private",
    )
    assert collection.items == (first.record,)
    assert collection.collection_fingerprint == c.collection_fingerprint(collection)
    assert "v055-service-idempotency" not in journal.database_path.read_bytes().decode(
        errors="ignore"
    )


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"authenticated_operator_id": None}, "unauthenticated"),
        ({"permission_verified": False}, "forbidden"),
        ({"permission_verified": 1}, "forbidden"),
        ({"authenticated_operator_id": "foreign"}, "evidence_not_found"),
        (
            {"candidate_record_id": "00000000-0000-4000-8000-000000000000"},
            "evidence_not_found",
        ),
        ({"idempotency_key": "private"}, "invalid_request"),
    ],
)
def test_authorization_and_scope(tmp_path, facts, changes, code):
    service, journal, _, _ = setup(tmp_path, facts)
    error(create(service, facts, **changes), code)
    assert counts(journal) == (0, 0, 0)


def test_default_off(tmp_path, facts):
    _, journal, reader, clock = setup(tmp_path, facts)
    service = WorkerActivationRuntimePlanService(
        prerequisite_reader=reader, store=journal, clock=clock
    )
    error(create(service, facts), "installation_capability_unsupported")
    assert reader.calls == 0


@pytest.mark.parametrize(
    "bound", ["max_records_per_operator", "max_total_records", "max_model_bytes"]
)
def test_bounds_lower_only_and_no_eviction(tmp_path, facts, bound):
    service, journal, _, _ = setup(tmp_path, facts, **{bound: 0})
    error(
        create(service, facts),
        "record_too_large" if bound == "max_model_bytes" else "quota_exceeded",
    )
    assert counts(journal) == (0, 0, 0)
    for value in (True, -1, 999999999):
        with pytest.raises(WorkerActivationRuntimePlanStoreError):
            WorkerActivationRuntimePlanStore(
                tmp_path / "invalid.sqlite", **{bound: value}
            )


@pytest.mark.parametrize("boundary", [1, 2])
@pytest.mark.parametrize("damage", ["missing", "stale", "fingerprint", "exception"])
def test_revalidation_at_both_write_boundaries(tmp_path, facts, boundary, damage):
    service, journal, reader, clock = setup(tmp_path, facts)

    def hook(call):
        if call == boundary:
            if damage == "missing":
                return None
            if damage == "stale":
                clock.now += timedelta(seconds=31)
            if damage == "exception":
                raise RuntimeError("private endpoint token")
            if damage == "fingerprint":
                record, status = reader.pair
                record = record.model_copy(
                    update={
                        "runtime_admission_record_fingerprint": c.fingerprint(
                            "bad", "private"
                        )
                    }
                )
                return record, status
        return reader.pair

    reader.hook = hook
    result = create(service, facts)
    assert isinstance(result, c.WorkerActivationRuntimePlanRedactedErrorV1)
    assert "private" not in result.model_dump_json()
    if boundary == 1:
        assert counts(journal) == (0, 0, 0)
    else:
        error(result, "append_indeterminate")
        assert counts(journal) == (1, 0, 1)
        service._store = WorkerActivationRuntimePlanStore(journal.database_path)
        reader.hook = lambda _: pytest.fail("interrupted reservation cannot resume")
        error(create(service, facts), "append_indeterminate")
        error(
            create(service, facts, idempotency_key="different-v055-key"),
            "permanent_subject_reserved",
        )


@pytest.mark.parametrize("audit_fails", [False, True])
def test_disk_append_failure_is_permanent_even_if_audit_fails(
    tmp_path, facts, monkeypatch, audit_fails
):
    service, journal, reader, _ = setup(tmp_path, facts)

    def fail(*args):
        raise sqlite3.OperationalError("private disk path and token")

    monkeypatch.setattr(journal, "_append_record", fail)
    if audit_fails:
        monkeypatch.setattr(journal, "_append_failure", fail)
    error(create(service, facts), "append_indeterminate")
    assert counts(journal) == (1, 0, 0 if audit_fails else 1)
    service._store = WorkerActivationRuntimePlanStore(journal.database_path)
    reader.hook = lambda _: pytest.fail("must not retry")
    error(create(service, facts), "append_indeterminate")


def test_interrupted_reservation_counts_against_capacity(tmp_path, facts, monkeypatch):
    service, journal, _, _ = setup(tmp_path, facts, max_total_records=1)

    def crash(*args):
        raise KeyboardInterrupt()

    monkeypatch.setattr(journal, "_append_record", crash)
    with pytest.raises(KeyboardInterrupt):
        create(service, facts)
    assert counts(journal) == (1, 0, 0)
    service._store = WorkerActivationRuntimePlanStore(
        journal.database_path, max_total_records=1
    )
    error(create(service, facts), "append_indeterminate")
    error(
        create(service, facts, authenticated_operator_id="different-owner"),
        "quota_exceeded",
    )


def test_concurrent_independent_instances(tmp_path, facts):
    service, journal, _, _ = setup(tmp_path, facts)
    services = [service] + [
        WorkerActivationRuntimePlanService(
            store=WorkerActivationRuntimePlanStore(journal.database_path),
            prerequisite_reader=Reader(facts),
            clock=Clock(facts),
            enabled=True,
        )
        for _ in range(3)
    ]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda item: create(item, facts), services))
    successes = [
        item
        for item in results
        if isinstance(item, c.WorkerActivationRuntimePlanResultV1)
    ]
    assert successes
    assert sum(not item.exact_duplicate for item in successes) == 1
    assert all(item.record == successes[0].record for item in successes)
    assert counts(journal) == (1, 1, 0)
    for result in results:
        if result not in successes:
            assert result.error_code in {"append_indeterminate", "unavailable"}


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE failures",
        "CREATE INDEX unexpected_index ON reservations(operator_id)",
        "UPDATE reservations SET operator_id='foreign'",
        "UPDATE reservations SET request='sha256:private'",
        "UPDATE evidence SET record_json=substr(record_json, 1, length(record_json)-1)",
        "UPDATE evidence SET record_json=replace(record_json, '\"evidence_only\":true', '\"evidence_only\":1')",
        'UPDATE evidence SET record_json=replace(record_json, \'"schema":\', \'"schema":"duplicate","schema":\')',
        'UPDATE evidence SET audit_json=replace(audit_json, \'"outcome":"recorded"\', \'"outcome":"indeterminate"\')',
        "PRAGMA application_id=52",
    ],
)
def test_corruption_closes_all_connections_and_restart(tmp_path, facts, sql):
    service, journal, _, _ = setup(tmp_path, facts)
    first = create(service, facts)
    with sqlite3.connect(journal.database_path) as connection:
        connection.execute(sql)
    error(create(service, facts), "store_corrupt")
    error(
        service.get(
            authenticated_operator_id=facts.operator_id,
            permission_verified=True,
            candidate_record_id=facts.candidate_record_id,
            runtime_plan_id=first.record.runtime_plan_id,
            correlation_id="private",
        ),
        "store_corrupt",
    )
    error(
        service.list(
            authenticated_operator_id=facts.operator_id,
            permission_verified=True,
            candidate_record_id=facts.candidate_record_id,
            correlation_id="private",
        ),
        "store_corrupt",
    )
    with pytest.raises(WorkerActivationRuntimePlanStoreError, match="store_corrupt"):
        WorkerActivationRuntimePlanStore(journal.database_path)


def test_lock_contention_rejects_before_reservation(tmp_path, facts):
    service, journal, _, _ = setup(tmp_path, facts)
    with sqlite3.connect(journal.database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        error(create(service, facts), "unavailable")
    assert counts(journal) == (0, 0, 0)
    assert isinstance(create(service, facts), c.WorkerActivationRuntimePlanResultV1)


def test_durable_owner_scoped_reader(tmp_path, facts, request):
    from app.worker_activation_runtime_admission.test_service_store import (
        create as prior_create,
    )
    from app.worker_activation_runtime_admission.test_service_store import (
        setup as prior_setup,
    )

    prior, journal, _, clock = prior_setup(
        tmp_path, request.getfixturevalue("admission_facts")
    )
    result = prior_create(prior, request.getfixturevalue("admission_facts"))
    reader = WorkerActivationRuntimePlanPrerequisiteStoreReader(
        store=type(journal)(journal.database_path), clock=clock
    )
    arguments = {
        "operator_id": result.record.operator_id,
        "candidate_record_id": result.record.candidate_record_id,
        "runtime_admission_id": result.record.runtime_admission_id,
        "valid_until": result.record.valid_until,
    }
    before = journal.database_path.read_bytes()
    pair = reader.read_owned(**arguments)
    assert pair[0].model_dump_json() == result.record.model_dump_json()
    assert pair[1].evaluated_at == result.record.recorded_at
    service, successor, _, _ = setup(tmp_path, facts)
    service._prerequisite_reader = reader
    request = c.build_create(receipt=pair[0], receipt_status=pair[1])
    successor_facts = facts.model_copy(update={"create": request})
    admitted = create(service, successor_facts)
    assert isinstance(admitted, c.WorkerActivationRuntimePlanResultV1)
    assert admitted.record.worker_activation_runtime_admission == pair[0]
    assert counts(successor) == (1, 1, 0)
    assert (
        admitted.record.worker_activation_runtime_admission.model_dump_json()
        == pair[0].model_dump_json()
    )
    assert journal.database_path.read_bytes() == before
    assert reader.read_owned(**{**arguments, "operator_id": "foreign"}) is None
    assert (
        reader.read_owned(
            **{
                **arguments,
                "candidate_record_id": "00000000-0000-4000-8000-000000000000",
            }
        )
        is None
    )
    clock.now += timedelta(seconds=31)
    assert reader.read_owned(**arguments) is None


def test_no_production_or_effect_consumers():
    root = Path(__file__).resolve().parents[3]
    for area in ("atlas-agent", "atlas-execution-worker"):
        assert (root / area).is_dir()
        for path in (root / area).rglob("*.py"):
            assert "worker_activation_runtime_plan" not in path.read_text()
    package = Path(__file__).parent
    app = root / "atlas-core" / "app"
    consumers = {
        path.relative_to(app).as_posix()
        for path in app.rglob("*.py")
        if path.parent != package
        and not path.name.startswith("test_")
        and "worker_activation_runtime_plan" in path.read_text()
    }
    assert consumers == {
        "api/v1/router.py", "operator_auth/models.py",
        "routes/worker_activation_runtime_plan.py",
    }
    for name in ("service.py", "store.py", "readers.py"):
        tree = ast.parse((package / name).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(
                    item.name not in {"subprocess", "httpx", "requests", "socket"}
                    for item in node.names
                )


def test_database_page_bound_fails_closed(tmp_path, facts):
    service, journal, _, _ = setup(tmp_path, facts, max_database_bytes=64 * 1024)
    result = create(service, facts)
    error(result, "append_indeterminate")
    assert counts(journal)[0:2] == (1, 0)
    with sqlite3.connect(journal.database_path) as connection:
        assert (
            connection.execute("PRAGMA page_count").fetchone()[0]
            * connection.execute("PRAGMA page_size").fetchone()[0]
            <= 64 * 1024
        )
    service._store = WorkerActivationRuntimePlanStore(
        journal.database_path, max_database_bytes=64 * 1024
    )
    error(create(service, facts), "append_indeterminate")


def test_serialized_record_bound_precedes_reservation(tmp_path, facts):
    service, journal, _, _ = setup(tmp_path, facts, max_model_bytes=16 * 1024)
    error(create(service, facts), "record_too_large")
    assert counts(journal) == (0, 0, 0)


def test_damaged_index_root_closes_restart(tmp_path, facts):
    service, journal, _, _ = setup(tmp_path, facts)
    create(service, facts)
    with sqlite3.connect(journal.database_path) as connection:
        connection.execute("PRAGMA writable_schema=ON")
        connection.execute(
            "UPDATE sqlite_master SET rootpage=999999 WHERE name='sqlite_autoindex_reservations_2'"
        )
    error(create(service, facts), "store_corrupt")
    with pytest.raises(WorkerActivationRuntimePlanStoreError, match="store_corrupt"):
        WorkerActivationRuntimePlanStore(journal.database_path)


def test_uncertain_reservation_commit_is_indeterminate(tmp_path, facts, monkeypatch):
    from contextlib import contextmanager

    service, journal, reader, _ = setup(tmp_path, facts)
    original = journal._connect

    @contextmanager
    def uncertain():
        with original() as connection:
            before = connection.execute("SELECT count(*) FROM reservations").fetchone()[
                0
            ]
            yield connection
            after = connection.execute("SELECT count(*) FROM reservations").fetchone()[
                0
            ]
        if after > before:
            raise WorkerActivationRuntimePlanStoreError("unavailable")

    monkeypatch.setattr(journal, "_connect", uncertain)
    error(create(service, facts), "append_indeterminate")
    assert counts(journal) == (1, 0, 0)
    service._store = WorkerActivationRuntimePlanStore(journal.database_path)
    reader.hook = lambda _: pytest.fail("uncertain commit cannot retry")
    error(create(service, facts), "append_indeterminate")


def test_partial_evidence_write_rolls_back_and_remains_reserved(
    tmp_path, facts, monkeypatch
):
    from contextlib import contextmanager

    service, journal, _, _ = setup(tmp_path, facts)
    original = journal._connect

    @contextmanager
    def interrupted():
        with original() as connection:
            yield connection
            if connection.execute("SELECT count(*) FROM evidence").fetchone()[0]:
                raise sqlite3.OperationalError("private write failure")

    monkeypatch.setattr(journal, "_connect", interrupted)
    error(create(service, facts), "append_indeterminate")
    assert counts(journal) == (1, 0, 1)
    service._store = WorkerActivationRuntimePlanStore(journal.database_path)
    error(create(service, facts), "append_indeterminate")


def test_competing_keys_cannot_reserve_same_subject(tmp_path, facts):
    service, journal, _, _ = setup(tmp_path, facts)
    other = WorkerActivationRuntimePlanService(
        store=WorkerActivationRuntimePlanStore(journal.database_path),
        prerequisite_reader=Reader(facts),
        clock=Clock(facts),
        enabled=True,
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(create, service, facts)
        second = pool.submit(create, other, facts, idempotency_key="competing-v055-key")
        results = [first.result(), second.result()]
    assert (
        sum(isinstance(item, c.WorkerActivationRuntimePlanResultV1) for item in results)
        == 1
    )
    failure = next(
        item
        for item in results
        if isinstance(item, c.WorkerActivationRuntimePlanRedactedErrorV1)
    )
    error(failure, "permanent_subject_reserved")
    assert counts(journal) == (1, 1, 0)


def test_both_prerequisite_reads_hold_sqlite_write_lock(tmp_path, facts):
    service, journal, reader, _ = setup(tmp_path, facts)

    def inspect_lock(_call):
        with (
            sqlite3.connect(journal.database_path, timeout=0) as competitor,
            pytest.raises(sqlite3.OperationalError, match="locked"),
        ):
            competitor.execute("BEGIN IMMEDIATE")
        return reader.pair

    reader.hook = inspect_lock
    assert isinstance(create(service, facts), c.WorkerActivationRuntimePlanResultV1)
    assert reader.calls == 2
    with journal._connect() as connection:
        assert connection.execute("PRAGMA synchronous").fetchone()[0] == 2


def test_lowered_restart_bounds_close_existing_state(tmp_path, facts):
    service, journal, _, _ = setup(tmp_path, facts)
    create(service, facts)
    for bounds in (
        {"max_total_records": 0},
        {"max_records_per_operator": 0},
        {"max_model_bytes": 1},
    ):
        with pytest.raises(
            WorkerActivationRuntimePlanStoreError, match="store_corrupt"
        ):
            WorkerActivationRuntimePlanStore(journal.database_path, **bounds)


def test_clock_rollback_between_locked_reads_is_terminal(tmp_path, facts):
    service, journal, reader, clock = setup(tmp_path, facts)
    original = clock.now

    def hook(call):
        clock.now = original + timedelta(seconds=0 if call == 1 else -1)
        return reader.pair

    reader.hook = hook
    error(create(service, facts), "append_indeterminate")
    assert counts(journal) == (1, 0, 1)


@pytest.mark.parametrize(
    "correlation", ["e\u0301", "\ud800", "\x00", {"private": True}]
)
def test_hostile_correlation_is_redacted(tmp_path, facts, correlation):
    service, journal, _, _ = setup(tmp_path, facts)
    error(
        create(service, facts, permission_verified=False, correlation_id=correlation),
        "forbidden",
    )
    assert counts(journal) == (0, 0, 0)


def test_response_failure_does_not_renew_evidence(tmp_path, facts, monkeypatch):
    service, journal, reader, _ = setup(tmp_path, facts)
    original = service._result

    def fail(*args):
        raise RuntimeError("private response token")

    monkeypatch.setattr(service, "_result", fail)
    error(create(service, facts), "append_indeterminate")
    assert counts(journal) == (1, 1, 0)
    monkeypatch.setattr(service, "_result", original)
    reader.hook = lambda _: pytest.fail("response failure must not replay")
    assert create(service, facts).exact_duplicate


def _process_create(path, facts, barrier, output):
    """Independent process/SQLite connection; only the evidence service runs."""
    service = WorkerActivationRuntimePlanService(
        store=WorkerActivationRuntimePlanStore(path),
        prerequisite_reader=Reader(facts),
        clock=Clock(facts),
        enabled=True,
    )
    barrier.wait(timeout=30)
    result = create(service, facts)
    output.send(result.model_dump_json())
    output.close()


def test_independent_processes_share_permanent_reservation(tmp_path, facts):
    from multiprocessing import get_context

    _, journal, _, _ = setup(tmp_path, facts)
    context = get_context("fork")
    barrier = context.Barrier(2)
    pipes = [context.Pipe(duplex=False) for _ in range(2)]
    processes = [
        context.Process(
            target=_process_create,
            args=(journal.database_path, facts, barrier, sender),
        )
        for _, sender in pipes
    ]
    try:
        for process in processes:
            process.start()
        results = []
        for receiver, sender in pipes:
            sender.close()
            assert receiver.poll(60), "evidence process did not return"
            raw = receiver.recv()
            try:
                result = c.WorkerActivationRuntimePlanResultV1.model_validate_json(raw)
            except ValueError:
                result = (
                    c.WorkerActivationRuntimePlanRedactedErrorV1.model_validate_json(
                        raw
                    )
                )
                assert result.error_code in {"append_indeterminate", "unavailable"}
            results.append(result)
        for process in processes:
            process.join(timeout=10)
            assert process.exitcode == 0
        successes = [
            r for r in results if isinstance(r, c.WorkerActivationRuntimePlanResultV1)
        ]
        assert sum(not r.exact_duplicate for r in successes) == 1
        assert all(r.record == successes[0].record for r in successes)
        assert counts(journal) == (1, 1, 0)
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=10)
        for receiver, sender in pipes:
            receiver.close()
            sender.close()


@pytest.mark.parametrize("boundary", [1, 2])
@pytest.mark.parametrize(
    "field,value",
    [
        ("operator_id", "foreign"),
        ("runtime_admission_id", "00000000-0000-5000-8000-000000000000"),
        ("worker_start_allowed", True),
        ("payload_bytes", False),
    ],
)
def test_forged_lineage_at_each_write_lock(tmp_path, facts, boundary, field, value):
    service, journal, reader, _ = setup(tmp_path, facts)

    def hook(call):
        record, status = reader.pair
        if call == boundary:
            record = record.model_copy(update={field: value})
        return record, status

    reader.hook = hook
    result = create(service, facts)
    assert isinstance(result, c.WorkerActivationRuntimePlanRedactedErrorV1)
    assert counts(journal) == ((0, 0, 0) if boundary == 1 else (1, 0, 1))


def test_positive_owner_capacity_preserves_existing_duplicate(tmp_path, facts):
    service, journal, reader, _ = setup(tmp_path, facts, max_records_per_operator=1)
    first = create(service, facts)
    assert isinstance(first, c.WorkerActivationRuntimePlanResultV1)
    reader.hook = lambda _: pytest.fail("quota or duplicate must not read lineage")
    assert create(service, facts).record == first.record
    error(
        create(
            service,
            facts,
            candidate_record_id="00000000-0000-4000-8000-000000000000",
            idempotency_key="another-bounded-owner-key",
        ),
        "quota_exceeded",
    )
    assert counts(journal) == (1, 1, 0)


def test_reader_rejects_constructed_extra_and_redacts_store_errors(tmp_path, facts):
    record = facts.worker_activation_runtime_admission

    class BrokenStore:
        def get(self, **kwargs):
            return record.model_copy(update={"secret_endpoint": "private"})

    reader = WorkerActivationRuntimePlanPrerequisiteStoreReader(
        store=BrokenStore(), clock=Clock(facts)
    )
    with pytest.raises(WorkerActivationRuntimePlanStoreError, match="^store_corrupt$"):
        reader.read_owned(
            operator_id=record.operator_id,
            candidate_record_id=record.candidate_record_id,
            runtime_admission_id=record.runtime_admission_id,
            valid_until=record.valid_until,
        )
