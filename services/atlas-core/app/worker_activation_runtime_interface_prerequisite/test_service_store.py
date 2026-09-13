"""Hostile P2 persistence checks using the complete P1 prerequisite chain."""

import ast
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.worker_activation_runtime_interface_prerequisite import contract as c
from app.worker_activation_runtime_interface_prerequisite import test_contract as p1
from app.worker_activation_runtime_interface_prerequisite.readers import (
    WorkerActivationRuntimeInterfacePrerequisiteReviewStoreReader,
)
from app.worker_activation_runtime_interface_prerequisite.service import (
    WorkerActivationRuntimeInterfacePrerequisiteService,
)
from app.worker_activation_runtime_interface_prerequisite.store import (
    WorkerActivationRuntimeInterfacePrerequisiteStore,
    WorkerActivationRuntimeInterfacePrerequisiteStoreError,
)
from app.worker_activation_runtime_interface_prerequisite.test_contract import (
    admission_facts,  # noqa: F401
    plan_facts,  # noqa: F401
    prior_facts,  # noqa: F401
    review_facts,  # noqa: F401
)


@pytest.fixture(scope="module")
def facts(request):
    return p1.facts.__wrapped__(request)


class Reader:
    def __init__(self, facts):
        self.pair = (
            facts.worker_activation_runtime_plan_review,
            facts.worker_activation_runtime_plan_review_status,
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
    journal = WorkerActivationRuntimeInterfacePrerequisiteStore(
        tmp_path / "v057.sqlite", **bounds
    )
    reader = Reader(facts)
    clock = Clock(facts)
    service = WorkerActivationRuntimeInterfacePrerequisiteService(
        prerequisite_reader=reader, store=journal, clock=clock, enabled=enabled
    )
    return service, journal, reader, clock


def create(service, facts, **kwargs):
    arguments = {
        "authenticated_operator_id": facts.operator_id,
        "permission_verified": True,
        "candidate_record_id": facts.candidate_record_id,
        "idempotency_key": "v057-service-idempotency",
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
    assert isinstance(
        result, c.WorkerActivationRuntimeInterfacePrerequisiteRedactedErrorV1
    )
    assert result.error_code == code
    assert result.retryable is False
    assert "private" not in result.model_dump_json()


def test_restart_duplicate_expiry_ownership_and_subject_replay(tmp_path, facts):
    service, journal, reader, clock = setup(tmp_path, facts)
    first = create(service, facts)
    assert isinstance(first, c.WorkerActivationRuntimeInterfacePrerequisiteResultV1)
    assert reader.calls == 2
    assert not first.exact_duplicate
    assert first.record.blockers == c.SUCCESS_BLOCKERS
    assert (
        first.record.runtime_interface_prerequisite_record_fingerprint
        == c.runtime_interface_prerequisite_record_fingerprint(first.record)
    )
    assert counts(journal) == (1, 1, 0)
    clock.now = datetime.fromisoformat(first.record.valid_until) + timedelta(seconds=1)
    reader.hook = lambda _: pytest.fail("duplicate must not read prerequisites")
    restarted = WorkerActivationRuntimeInterfacePrerequisiteStore(journal.database_path)
    service._store = restarted
    duplicate = create(service, facts)
    assert duplicate.exact_duplicate
    assert duplicate.record == first.record
    assert duplicate.status.lifecycle == "expired"
    assert counts(journal) == (1, 1, 0)
    error(
        create(service, facts, idempotency_key="a-different-v057-key"),
        "permanent_subject_reserved",
    )
    altered = facts.create.model_copy(update={"valid_until": "2099-01-01T00:00:00Z"})
    error(
        service.create(
            altered,
            authenticated_operator_id=facts.operator_id,
            permission_verified=True,
            candidate_record_id=facts.candidate_record_id,
            idempotency_key="v057-service-idempotency",
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
                runtime_interface_prerequisite_id=first.record.runtime_interface_prerequisite_id,
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
    assert "v057-service-idempotency" not in journal.database_path.read_bytes().decode(
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
    service = WorkerActivationRuntimeInterfacePrerequisiteService(
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
        with pytest.raises(WorkerActivationRuntimeInterfacePrerequisiteStoreError):
            WorkerActivationRuntimeInterfacePrerequisiteStore(
                tmp_path / "invalid.sqlite", **{bound: value}
            )


@pytest.mark.parametrize("boundary", [1, 2])
@pytest.mark.parametrize(
    "damage", ["missing", "stale", "fingerprint", "exception", "status", "design"]
)
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
            if damage == "status":
                record, status = reader.pair
                clock.now += timedelta(seconds=1)
                return record, c.v056.derive_status(
                    record, evaluated_at=clock.now.strftime("%Y-%m-%dT%H:%M:%SZ")
                )
            if damage == "design":
                record, status = reader.pair
                return record.model_copy(update={"findings": ()}), status
            if damage == "fingerprint":
                record, status = reader.pair
                record = record.model_copy(
                    update={
                        "runtime_plan_review_record_fingerprint": c.fingerprint(
                            "bad", "private"
                        )
                    }
                )
                return record, status
        return reader.pair

    reader.hook = hook
    result = create(service, facts)
    assert isinstance(
        result, c.WorkerActivationRuntimeInterfacePrerequisiteRedactedErrorV1
    )
    assert "private" not in result.model_dump_json()
    if boundary == 1:
        assert counts(journal) == (0, 0, 0)
    else:
        error(result, "append_indeterminate")
        assert counts(journal) == (1, 0, 1)
        service._store = WorkerActivationRuntimeInterfacePrerequisiteStore(
            journal.database_path
        )
        reader.hook = lambda _: pytest.fail("interrupted reservation cannot resume")
        error(create(service, facts), "append_indeterminate")
        error(
            create(service, facts, idempotency_key="different-v057-key"),
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
    service._store = WorkerActivationRuntimeInterfacePrerequisiteStore(
        journal.database_path
    )
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
    service._store = WorkerActivationRuntimeInterfacePrerequisiteStore(
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
        WorkerActivationRuntimeInterfacePrerequisiteService(
            store=WorkerActivationRuntimeInterfacePrerequisiteStore(
                journal.database_path
            ),
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
        if isinstance(item, c.WorkerActivationRuntimeInterfacePrerequisiteResultV1)
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
            runtime_interface_prerequisite_id=first.record.runtime_interface_prerequisite_id,
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
    with pytest.raises(
        WorkerActivationRuntimeInterfacePrerequisiteStoreError, match="store_corrupt"
    ):
        WorkerActivationRuntimeInterfacePrerequisiteStore(journal.database_path)


def test_lock_contention_rejects_before_reservation(tmp_path, facts):
    service, journal, _, _ = setup(tmp_path, facts)
    with sqlite3.connect(journal.database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        error(create(service, facts), "unavailable")
    assert counts(journal) == (0, 0, 0)
    assert isinstance(
        create(service, facts), c.WorkerActivationRuntimeInterfacePrerequisiteResultV1
    )


def test_durable_owner_scoped_reader(tmp_path, facts, request):
    from app.worker_activation_runtime_plan_review.test_service_store import (
        create as prior_create,
    )
    from app.worker_activation_runtime_plan_review.test_service_store import (
        setup as prior_setup,
    )

    prior, journal, _, clock = prior_setup(
        tmp_path, request.getfixturevalue("review_facts")
    )
    result = prior_create(prior, request.getfixturevalue("review_facts"))
    reader = WorkerActivationRuntimeInterfacePrerequisiteReviewStoreReader(
        store=type(journal)(journal.database_path), clock=clock
    )
    arguments = {
        "operator_id": result.record.operator_id,
        "candidate_record_id": result.record.candidate_record_id,
        "runtime_plan_review_id": result.record.runtime_plan_review_id,
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
    assert isinstance(admitted, c.WorkerActivationRuntimeInterfacePrerequisiteResultV1)
    assert admitted.record.worker_activation_runtime_plan_review == pair[0]
    assert counts(successor) == (1, 1, 0)
    assert (
        admitted.record.worker_activation_runtime_plan_review.model_dump_json()
        == pair[0].model_dump_json()
    )
    restored = type(successor)(successor.database_path).get(
        operator_id=admitted.record.operator_id,
        candidate_record_id=admitted.record.candidate_record_id,
        runtime_interface_prerequisite_id=admitted.record.runtime_interface_prerequisite_id,
    )
    assert restored.model_dump_json() == admitted.record.model_dump_json()
    assert (
        restored.worker_activation_runtime_plan_review.model_dump_json()
        == pair[0].model_dump_json()
    )
    assert (
        restored.worker_activation_runtime_plan_review_status.model_dump_json()
        == pair[1].model_dump_json()
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
            assert (
                "worker_activation_runtime_interface_prerequisite"
                not in path.read_text()
            )
    package = Path(__file__).parent
    app = root / "atlas-core" / "app"
    consumers = {
        path.relative_to(app).as_posix()
        for path in app.rglob("*.py")
        if path.parent != package
        and not path.name.startswith("test_")
        and "worker_activation_runtime_interface_prerequisite" in path.read_text()
    }
    assert consumers == {
        "api/v1/router.py",
        "operator_auth/models.py",
        "routes/worker_activation_runtime_interface_prerequisite.py",
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
    service._store = WorkerActivationRuntimeInterfacePrerequisiteStore(
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
    with pytest.raises(
        WorkerActivationRuntimeInterfacePrerequisiteStoreError, match="store_corrupt"
    ):
        WorkerActivationRuntimeInterfacePrerequisiteStore(journal.database_path)


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
            raise WorkerActivationRuntimeInterfacePrerequisiteStoreError("unavailable")

    monkeypatch.setattr(journal, "_connect", uncertain)
    error(create(service, facts), "append_indeterminate")
    assert counts(journal) == (1, 0, 0)
    service._store = WorkerActivationRuntimeInterfacePrerequisiteStore(
        journal.database_path
    )
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
    service._store = WorkerActivationRuntimeInterfacePrerequisiteStore(
        journal.database_path
    )
    error(create(service, facts), "append_indeterminate")


def test_competing_keys_cannot_reserve_same_subject(tmp_path, facts):
    service, journal, _, _ = setup(tmp_path, facts)
    other = WorkerActivationRuntimeInterfacePrerequisiteService(
        store=WorkerActivationRuntimeInterfacePrerequisiteStore(journal.database_path),
        prerequisite_reader=Reader(facts),
        clock=Clock(facts),
        enabled=True,
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(create, service, facts)
        second = pool.submit(create, other, facts, idempotency_key="competing-v057-key")
        results = [first.result(), second.result()]
    assert (
        sum(
            isinstance(item, c.WorkerActivationRuntimeInterfacePrerequisiteResultV1)
            for item in results
        )
        == 1
    )
    failure = next(
        item
        for item in results
        if isinstance(
            item, c.WorkerActivationRuntimeInterfacePrerequisiteRedactedErrorV1
        )
    )
    # Full recursive validation may outlast the bounded SQLite busy timeout.
    # Either refusal is closed; once the winner commits, the losing key must
    # deterministically conflict without any new prerequisite read or append.
    assert failure.error_code in {"permanent_subject_reserved", "unavailable"}
    error(failure, failure.error_code)
    losing_key = ("v057-service-idempotency", "competing-v057-key")[
        results.index(failure)
    ]
    service._prerequisite_reader.hook = lambda _: pytest.fail("loser cannot replay")
    error(
        create(service, facts, idempotency_key=losing_key), "permanent_subject_reserved"
    )
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
    assert isinstance(
        create(service, facts), c.WorkerActivationRuntimeInterfacePrerequisiteResultV1
    )
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
            WorkerActivationRuntimeInterfacePrerequisiteStoreError,
            match="store_corrupt",
        ):
            WorkerActivationRuntimeInterfacePrerequisiteStore(
                journal.database_path, **bounds
            )


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
    service = WorkerActivationRuntimeInterfacePrerequisiteService(
        store=WorkerActivationRuntimeInterfacePrerequisiteStore(path),
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
                result = c.WorkerActivationRuntimeInterfacePrerequisiteResultV1.model_validate_json(
                    raw
                )
            except ValueError:
                result = c.WorkerActivationRuntimeInterfacePrerequisiteRedactedErrorV1.model_validate_json(
                    raw
                )
                assert result.error_code in {"append_indeterminate", "unavailable"}
            results.append(result)
        for process in processes:
            process.join(timeout=10)
            assert process.exitcode == 0
        successes = [
            r
            for r in results
            if isinstance(r, c.WorkerActivationRuntimeInterfacePrerequisiteResultV1)
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
        ("candidate_record_id", "00000000-0000-4000-8000-000000000000"),
        ("runtime_plan_review_id", "00000000-0000-5000-8000-000000000000"),
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
    assert isinstance(
        result, c.WorkerActivationRuntimeInterfacePrerequisiteRedactedErrorV1
    )
    assert counts(journal) == ((0, 0, 0) if boundary == 1 else (1, 0, 1))


def test_positive_owner_capacity_preserves_existing_duplicate(tmp_path, facts):
    service, journal, reader, _ = setup(tmp_path, facts, max_records_per_operator=1)
    first = create(service, facts)
    assert isinstance(first, c.WorkerActivationRuntimeInterfacePrerequisiteResultV1)
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
    record = facts.worker_activation_runtime_plan_review

    class BrokenStore:
        def get(self, **kwargs):
            return record.model_copy(update={"secret_endpoint": "private"})

    reader = WorkerActivationRuntimeInterfacePrerequisiteReviewStoreReader(
        store=BrokenStore(), clock=Clock(facts)
    )
    with pytest.raises(
        WorkerActivationRuntimeInterfacePrerequisiteStoreError, match="^store_corrupt$"
    ):
        reader.read_owned(
            operator_id=record.operator_id,
            candidate_record_id=record.candidate_record_id,
            runtime_plan_review_id=record.runtime_plan_review_id,
            valid_until=record.valid_until,
        )


@pytest.mark.parametrize(
    "code,expected",
    [
        ("evidence_not_found", None),
        ("store_corrupt", "store_corrupt"),
        ("unavailable", "unavailable"),
    ],
)
def test_reader_preserves_closed_predecessor_errors(facts, code, expected):
    from app.worker_activation_runtime_plan_review.store import (
        WorkerActivationRuntimePlanReviewStoreError,
    )

    class BrokenStore:
        def get(self, **kwargs):
            raise WorkerActivationRuntimePlanReviewStoreError(code)

    reader = WorkerActivationRuntimeInterfacePrerequisiteReviewStoreReader(
        store=BrokenStore(), clock=Clock(facts)
    )
    record = facts.worker_activation_runtime_plan_review
    arguments = {
        "operator_id": record.operator_id,
        "candidate_record_id": record.candidate_record_id,
        "runtime_plan_review_id": record.runtime_plan_review_id,
        "valid_until": record.valid_until,
    }
    if expected is None:
        assert reader.read_owned(**arguments) is None
    else:
        with pytest.raises(
            WorkerActivationRuntimeInterfacePrerequisiteStoreError,
            match=f"^{expected}$",
        ):
            reader.read_owned(**arguments)


def test_inflight_reservation_deterministically_refuses_all_competitors(
    tmp_path, facts, monkeypatch
):
    from threading import Event

    service, journal, reader, _ = setup(tmp_path, facts)
    other, _, other_reader, _ = setup(tmp_path, facts)
    reserved = Event()
    release = Event()
    original = journal._append_record

    def pause_after_commit(*args):
        reserved.set()
        assert release.wait(30), "reservation holder was not released"
        return original(*args)

    monkeypatch.setattr(journal, "_append_record", pause_after_commit)
    other_reader.hook = lambda _: pytest.fail("competitor must not read predecessor")
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(create, service, facts)
        try:
            assert reserved.wait(30), "reservation was not committed"
            assert counts(journal) == (1, 0, 0)
            error(create(other, facts), "append_indeterminate")
            error(
                create(other, facts, idempotency_key="another-inflight-key"),
                "permanent_subject_reserved",
            )
        finally:
            release.set()
        result = pending.result(timeout=30)
    assert isinstance(result, c.WorkerActivationRuntimeInterfacePrerequisiteResultV1)
    assert reader.calls == 2
    assert create(other, facts).exact_duplicate
    assert counts(journal) == (1, 1, 0)


def test_success_retains_all_blocked_authority_and_complete_envelope_bounds(
    tmp_path, facts
):
    service, journal, _, _ = setup(tmp_path, facts)
    result = create(service, facts)
    assert isinstance(result, c.WorkerActivationRuntimeInterfacePrerequisiteResultV1)
    collection = service.list(
        authenticated_operator_id=facts.operator_id,
        permission_verified=True,
        candidate_record_id=facts.candidate_record_id,
        correlation_id="private",
    )
    with sqlite3.connect(journal.database_path) as connection:
        audit = c.WorkerActivationRuntimeInterfacePrerequisiteAuditEvidenceV1.model_validate_json(
            connection.execute("SELECT audit_json FROM evidence").fetchone()[0]
        )
    for model in (result, result.record, result.status, collection, audit):
        assert len(model.model_dump_json().encode()) <= c.MAX_MODEL_BYTES
        for field, definition in c.ClosedAuthorityV1.model_fields.items():
            if definition.default is False:
                assert getattr(model, field) is False, field
    assert result.record.inventory == c.SUCCESS_INVENTORY
    assert result.status.blockers == c.SUCCESS_BLOCKERS
    assert audit.worker_activation_runtime_plan_recorded is True
    assert audit.worker_activation_runtime_plan_review_recorded is True
    assert audit.worker_activation_runtime_interface_prerequisite_recorded is True


def test_lost_terminal_commit_acknowledgement_keeps_single_recorded_audit(
    tmp_path, facts, monkeypatch
):
    service, journal, reader, _ = setup(tmp_path, facts)
    original = journal._append_record

    def committed_but_unacknowledged(*args):
        original(*args)
        raise sqlite3.OperationalError("private terminal commit acknowledgement")

    monkeypatch.setattr(journal, "_append_record", committed_but_unacknowledged)
    error(create(service, facts), "append_indeterminate")
    assert counts(journal) == (1, 1, 0)
    service._store = WorkerActivationRuntimeInterfacePrerequisiteStore(
        journal.database_path
    )
    reader.hook = lambda _: pytest.fail("committed evidence must not replay")
    duplicate = create(service, facts)
    assert duplicate.exact_duplicate
    assert counts(journal) == (1, 1, 0)


def test_missing_live_journal_never_creates_replayable_empty_replacement(
    tmp_path, facts
):
    service, journal, reader, _ = setup(tmp_path, facts)
    first = create(service, facts)
    assert isinstance(first, c.WorkerActivationRuntimeInterfacePrerequisiteResultV1)
    retained = tmp_path / "retained.sqlite"
    journal.database_path.rename(retained)
    before = retained.read_bytes()
    reader.hook = lambda _: pytest.fail("missing journal cannot read predecessor")

    error(create(service, facts), "unavailable")
    error(
        service.get(
            authenticated_operator_id=facts.operator_id,
            permission_verified=True,
            candidate_record_id=facts.candidate_record_id,
            runtime_interface_prerequisite_id=first.record.runtime_interface_prerequisite_id,
            correlation_id="private",
        ),
        "unavailable",
    )
    error(
        service.list(
            authenticated_operator_id=facts.operator_id,
            permission_verified=True,
            candidate_record_id=facts.candidate_record_id,
            correlation_id="private",
        ),
        "unavailable",
    )
    assert not journal.database_path.exists()
    assert retained.read_bytes() == before

    # Restore the exact retained journal to simulate storage becoming available;
    # the service itself performs no recovery or initialization.
    retained.rename(journal.database_path)
    service._store = type(journal)(journal.database_path)
    duplicate = create(service, facts)
    assert duplicate.exact_duplicate
    assert duplicate.record == first.record
    error(
        create(service, facts, idempotency_key="different-v058-retained-key"),
        "permanent_subject_reserved",
    )
    assert counts(journal) == (1, 1, 0)


@pytest.mark.parametrize("redirect", ["cwd", "symlink"])
def test_journal_path_binding_survives_redirection(tmp_path, monkeypatch, redirect):
    original = tmp_path / "original"
    other = tmp_path / "other"
    original.mkdir()
    other.mkdir()
    monkeypatch.chdir(original)
    if redirect == "symlink":
        path = tmp_path / "journal-link"
        path.symlink_to(original / "journal.sqlite")
    else:
        path = Path("journal.sqlite")
    journal = WorkerActivationRuntimeInterfacePrerequisiteStore(path)
    assert journal.database_path == original / "journal.sqlite"
    before = journal.database_path.read_bytes()
    if redirect == "symlink":
        path.unlink()
        path.symlink_to(other / "journal.sqlite")
    else:
        monkeypatch.chdir(other)
    assert journal.list_owned(operator_id="owner", candidate_record_id="missing") == ()
    assert journal.database_path.read_bytes() == before
    assert not (other / "journal.sqlite").exists()


@pytest.mark.parametrize("name", ["journal ?mode=memory#é.sqlite", ":memory:"])
def test_sqlite_uri_metacharacters_remain_durable_literal_paths(tmp_path, name):
    path = tmp_path / name
    journal = WorkerActivationRuntimeInterfacePrerequisiteStore(path)
    assert path.is_file()
    assert counts(journal) == (0, 0, 0)
    before = path.read_bytes()
    restarted = type(journal)(path)
    assert (
        restarted.list_owned(operator_id="owner", candidate_record_id="missing") == ()
    )
    assert path.read_bytes() == before


def test_path_resolution_failure_is_redacted(tmp_path):
    path = tmp_path / "private-journal-loop"
    path.symlink_to(path)
    with pytest.raises(
        WorkerActivationRuntimeInterfacePrerequisiteStoreError, match="^unavailable$"
    ) as caught:
        WorkerActivationRuntimeInterfacePrerequisiteStore(path)
    assert caught.value.__suppress_context__
    assert "private" not in str(caught.value)
    assert path.is_symlink()


@pytest.mark.parametrize(
    "table,column",
    [
        ("reservations", "subject"),
        ("reservations", "operator_id"),
        ("reservations", "candidate_record_id"),
        ("reservations", "runtime_plan_review_id"),
        ("reservations", "idem"),
        ("reservations", "request"),
        ("evidence", "subject"),
        ("failures", "subject"),
    ],
)
@pytest.mark.parametrize("payload", ["oversized", "blob"])
def test_v059_index_corruption_is_bounded_before_python_decode(
    tmp_path, monkeypatch, table, column, payload
):
    journal = WorkerActivationRuntimeInterfacePrerequisiteStore(
        tmp_path / "index.sqlite"
    )
    # Deliberately malformed rows isolate the SQL preflight: no recursive model
    # decoding or Python materialization of an oversized index is permitted.
    with sqlite3.connect(journal.database_path) as connection:
        connection.execute(
            "INSERT INTO reservations VALUES ('s','o','c','r','i','q','{}')"
        )
        if table == "evidence":
            connection.execute("INSERT INTO evidence VALUES ('s','{}','{}')")
        if table == "failures":
            connection.execute("INSERT INTO failures VALUES ('s','{}')")
        value = "x" * (c.MAX_MODEL_BYTES + 1) if payload == "oversized" else b"s"
        connection.execute(f"UPDATE {table} SET {column}=?", (value,))

    def no_decode(*args):
        pytest.fail("corrupt indexes must be rejected before decoding any row")

    monkeypatch.setattr(type(journal), "_decode", no_decode)
    before = journal.database_path.read_bytes()
    with pytest.raises(
        WorkerActivationRuntimeInterfacePrerequisiteStoreError, match="^store_corrupt$"
    ):
        journal.list_owned(operator_id="o", candidate_record_id="c")
    with pytest.raises(
        WorkerActivationRuntimeInterfacePrerequisiteStoreError, match="^store_corrupt$"
    ):
        type(journal)(journal.database_path)
    assert journal.database_path.read_bytes() == before


@pytest.mark.parametrize("field", ["operator", "candidate", "id"])
def test_v059_service_get_rechecks_exact_owned_store_result(tmp_path, facts, field):
    service, journal, _, _ = setup(tmp_path, facts)
    record = c.build_runtime_interface_prerequisite(
        facts, idempotency_key="v059-owned-reader-key"
    )

    class WrongScopeStore:
        def get(self, **kwargs):
            return record

    service._store = WrongScopeStore()
    arguments = {
        "authenticated_operator_id": facts.operator_id,
        "permission_verified": True,
        "candidate_record_id": facts.candidate_record_id,
        "runtime_interface_prerequisite_id": record.runtime_interface_prerequisite_id,
        "correlation_id": "private",
    }
    # Positive control: the injected read result must itself be fully valid.
    assert service.get(**arguments).record == record
    key, value = {
        "operator": ("authenticated_operator_id", "foreign"),
        "candidate": ("candidate_record_id", "00000000-0000-4000-8000-000000000000"),
        "id": (
            "runtime_interface_prerequisite_id",
            "00000000-0000-5000-8000-000000000000",
        ),
    }[field]
    error(service.get(**{**arguments, key: value}), "evidence_not_found")
    assert counts(journal) == (0, 0, 0)


@pytest.mark.parametrize(
    "field", ["candidate_record_id", "runtime_interface_prerequisite_id"]
)
@pytest.mark.parametrize("value", [None, 1, "private-invalid-id"])
def test_v059_service_get_rejects_invalid_scope_before_store(
    tmp_path, facts, field, value
):
    service, journal, _, _ = setup(tmp_path, facts)

    class NoReadStore:
        def get(self, **kwargs):
            pytest.fail("invalid scope must not access the journal")

    service._store = NoReadStore()
    arguments = {
        "authenticated_operator_id": facts.operator_id,
        "permission_verified": True,
        "candidate_record_id": facts.candidate_record_id,
        "runtime_interface_prerequisite_id": "00000000-0000-5000-8000-000000000000",
        "correlation_id": "private",
    }
    error(service.get(**{**arguments, field: value}), "invalid_request")
    assert counts(journal) == (0, 0, 0)


@pytest.mark.parametrize("path", ["lookup", "append_duplicate", "append_created"])
@pytest.mark.parametrize(
    "damage",
    [
        "none",
        "owner",
        "candidate",
        "key",
        "review",
        "record_pin",
        "status_pin",
        "expiry",
        "authority",
    ],
)
def test_v059_create_independently_binds_store_readback(facts, path, damage):
    record = c.build_runtime_interface_prerequisite(
        facts, idempotency_key="v057-service-idempotency"
    )
    if damage == "authority":
        record = record.model_copy(update={"evidence_only": False})

    class ReadbackStore:
        def resolve_idempotency(self, **kwargs):
            return record if path == "lookup" else None

        def append(self, **kwargs):
            assert path != "lookup"
            return record, path == "append_created"

    reader = Reader(facts)
    reader.hook = lambda _: pytest.fail("readback must not read predecessor")
    service = WorkerActivationRuntimeInterfacePrerequisiteService(
        prerequisite_reader=reader,
        store=ReadbackStore(),
        clock=Clock(facts),
        enabled=True,
    )
    arguments = {
        "authenticated_operator_id": facts.operator_id,
        "permission_verified": True,
        "candidate_record_id": facts.candidate_record_id,
        "idempotency_key": "v057-service-idempotency",
        "correlation_id": "private-readback",
    }
    changes = {}
    if damage == "owner":
        arguments["authenticated_operator_id"] = "foreign"
    elif damage == "candidate":
        arguments["candidate_record_id"] = "00000000-0000-4000-8000-000000000000"
    elif damage == "key":
        arguments["idempotency_key"] = "different-private-key"
    elif damage == "review":
        changes["runtime_plan_review_id"] = "00000000-0000-5000-8000-000000000000"
    elif damage == "record_pin":
        changes["runtime_plan_review_record_fingerprint"] = c.fingerprint(
            "record", "foreign"
        )
    elif damage == "status_pin":
        changes["status_fingerprint"] = c.fingerprint("status", "foreign")
    elif damage == "expiry":
        changes["valid_until"] = "2099-01-01T00:00:00Z"
    request = c.WorkerActivationRuntimeInterfacePrerequisiteCreateV1.model_validate(
        facts.create.model_copy(update=changes)
    )
    result = service.create(request, **arguments)
    if damage == "none":
        assert result.record == record
        assert result.exact_duplicate is (path != "append_created")
    elif damage == "authority":
        error(
            result,
            "append_indeterminate" if path == "append_created" else "invalid_request",
        )
    else:
        error(result, "fingerprint_mismatch")
    assert reader.calls == 0
