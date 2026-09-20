"""v0.63 retains the bounded v0.57 journal without a new evidence stage."""

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
def test_restart_keeps_terminal_or_reserved_subject_permanent(
    tmp_path, facts, monkeypatch, outcome
):
    service, journal, reader, _ = setup(tmp_path, facts, max_total_records=1)

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
    reader.hook = lambda _: pytest.fail("restart must not replay prerequisites")

    service._store = Store(journal.database_path, max_total_records=1)
    duplicate = create(service, facts)
    if outcome == "recorded":
        assert duplicate.exact_duplicate
    else:
        error(duplicate, "append_indeterminate")
    error(
        create(service, facts, idempotency_key="different-retained-v063-key"),
        "permanent_subject_reserved",
    )
    assert counts(journal) == expected
    assert journal.database_path.read_bytes() == before


@pytest.mark.parametrize("populated", [False, True])
def test_v063_cannot_relabel_retained_journal(tmp_path, facts, populated):
    service, journal, _, _ = setup(tmp_path, facts)
    if populated:
        assert isinstance(
            create(service, facts), c.WorkerActivationRuntimeInterfacePrerequisiteResultV1
        )
    with sqlite3.connect(journal.database_path) as connection:
        assert connection.execute("PRAGMA application_id").fetchone() == (57,)
        connection.execute("PRAGMA application_id=63")
    before = journal.database_path.read_bytes()

    with pytest.raises(StoreError, match="^store_corrupt$"):
        Store(journal.database_path)
    assert journal.database_path.read_bytes() == before
