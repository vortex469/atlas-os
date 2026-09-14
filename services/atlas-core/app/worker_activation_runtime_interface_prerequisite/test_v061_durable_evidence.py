"""v0.61 retains the bounded v0.57 journal, including terminal reservations."""

import sqlite3

import pytest

from . import contract as c
from . import test_contract as p1
from .store import WorkerActivationRuntimeInterfacePrerequisiteStore as Store
from .store import WorkerActivationRuntimeInterfacePrerequisiteStoreError as StoreError
from .test_service_store import (
    admission_facts,  # noqa: F401
    counts,
    create,
    error,
    plan_facts,  # noqa: F401
    prior_facts,  # noqa: F401
    review_facts,  # noqa: F401
    setup,
)


@pytest.fixture(scope="module")
def facts(request):
    return p1.facts.__wrapped__(request)


@pytest.mark.parametrize("outcome", ["recorded", "failed", "interrupted"])
@pytest.mark.parametrize("bound", ["max_records_per_operator", "max_total_records"])
def test_restart_preserves_terminal_state_and_capacity(
    tmp_path, facts, monkeypatch, outcome, bound
):
    service, journal, reader, _ = setup(tmp_path, facts, **{bound: 1})

    def stop_append(*args):
        if outcome == "interrupted":
            raise KeyboardInterrupt
        raise sqlite3.OperationalError("private disk failure")

    if outcome != "recorded":
        monkeypatch.setattr(journal, "_append_record", stop_append)
    if outcome == "interrupted":
        with pytest.raises(KeyboardInterrupt):
            create(service, facts)
    else:
        result = create(service, facts)
        if outcome == "recorded":
            assert isinstance(
                result, c.WorkerActivationRuntimeInterfacePrerequisiteResultV1
            )
            assert not result.exact_duplicate
        else:
            error(result, "append_indeterminate")

    expected = (1, int(outcome == "recorded"), int(outcome == "failed"))
    assert counts(journal) == expected
    before = journal.database_path.read_bytes()
    reader.hook = lambda _: pytest.fail("restart must not replay or read lineage")
    # Repeated restarts must retain both audited failures and bare reservations.
    for _ in range(2):
        service._store = Store(journal.database_path, **{bound: 1})
        duplicate = create(service, facts)
        if outcome == "recorded":
            assert duplicate.exact_duplicate
            assert duplicate.record == result.record
        else:
            error(duplicate, "append_indeterminate")
        error(
            create(service, facts, idempotency_key="different-retained-subject-key"),
            "permanent_subject_reserved",
        )
        error(
            create(
                service,
                facts,
                candidate_record_id="00000000-0000-4000-8000-000000000000",
                idempotency_key="different-retained-candidate-key",
                authenticated_operator_id=(
                    "different-owner"
                    if bound == "max_total_records"
                    else facts.operator_id
                ),
            ),
            "quota_exceeded",
        )
        assert counts(journal) == expected
        assert journal.database_path.read_bytes() == before


@pytest.mark.parametrize("populated", [False, True])
def test_version_label_cannot_reidentify_or_migrate_journal(tmp_path, facts, populated):
    service, journal, _, _ = setup(tmp_path, facts)
    if populated:
        assert isinstance(
            create(service, facts),
            c.WorkerActivationRuntimeInterfacePrerequisiteResultV1,
        )
    with sqlite3.connect(journal.database_path) as connection:
        assert connection.execute("PRAGMA application_id").fetchone() == (57,)
        connection.execute("PRAGMA application_id=61")
    before = journal.database_path.read_bytes()
    for operation in (
        lambda: journal.list_owned(
            operator_id=facts.operator_id, candidate_record_id=facts.candidate_record_id
        ),
        lambda: journal.resolve_idempotency(
            operator_id=facts.operator_id,
            idempotency_key_fingerprint="missing-key",
            request_fingerprint="missing-request",
        ),
        lambda: Store(journal.database_path),
    ):
        with pytest.raises(StoreError, match="^store_corrupt$"):
            operation()
        assert journal.database_path.read_bytes() == before
