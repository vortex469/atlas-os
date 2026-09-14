"""Bound hostile journal metadata before Python readback, live and on restart."""

import sqlite3

import pytest

from .store import (
    WorkerActivationRuntimeInterfacePrerequisiteStore as Store,
)
from .store import (
    WorkerActivationRuntimeInterfacePrerequisiteStoreError as StoreError,
)


@pytest.mark.parametrize("damage", ["rows", "name", "sql", "utf8_sql"])
def test_schema_corruption_closes_before_metadata_materialization(
    tmp_path, monkeypatch, damage
):
    journal = Store(tmp_path / "journal.sqlite")
    with sqlite3.connect(journal.database_path) as connection:
        if damage == "rows":
            connection.execute("CREATE TABLE private_extra (secret TEXT)")
        elif damage == "name":
            connection.execute('ALTER TABLE failures RENAME TO "' + "x" * 1024 + '"')
        else:
            original = connection.execute(
                "SELECT sql FROM sqlite_master WHERE name='reservations'"
            ).fetchone()[0]
            maximum = max(len(sql.encode()) for _, sql in journal._schema if sql)
            if damage == "sql":
                suffix = "private" * 1024
            else:
                # Character length fits, but encoded byte length exceeds the
                # ceiling. Use the shortest DDL to leave room for the comment.
                original = connection.execute(
                    "SELECT sql FROM sqlite_master WHERE name='failures'"
                ).fetchone()[0]
                suffix = "界" * (maximum - len(original) - 4)
                assert len(original + "/*" + suffix + "*/") == maximum
            target = "failures" if damage == "utf8_sql" else "reservations"
            connection.execute("PRAGMA writable_schema=ON")
            connection.execute(
                "UPDATE sqlite_master SET sql=? WHERE name=?",
                (original + "/*" + suffix + "*/", target),
            )

    connect = sqlite3.connect

    class NoMetadataReadback(sqlite3.Connection):
        def execute(self, sql, *args, **kwargs):
            if sql == "SELECT name, sql FROM sqlite_master":
                pytest.fail("unbounded schema must never be materialized in Python")
            return super().execute(sql, *args, **kwargs)

    def guarded_connect(database, *args, **kwargs):
        # The reference schema is trusted, generated in memory by construction.
        if database != ":memory:":
            kwargs["factory"] = NoMetadataReadback
        return connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", guarded_connect)
    before = journal.database_path.read_bytes()
    for read in (
        lambda: journal.list_owned(operator_id="owner", candidate_record_id="missing"),
        lambda: journal.resolve_idempotency(
            operator_id="owner",
            idempotency_key_fingerprint="key",
            request_fingerprint="request",
        ),
        lambda: Store(journal.database_path),
    ):
        with pytest.raises(StoreError, match="^store_corrupt$") as caught:
            read()
        assert caught.value.__suppress_context__ or caught.value.__context__ is None
        assert journal.database_path.read_bytes() == before


def test_exact_schema_and_null_autoindex_sql_survive_restart(tmp_path):
    path = tmp_path / "journal.sqlite"
    journal = Store(path)
    assert any(sql is None for _, sql in journal._schema)
    before = path.read_bytes()
    restarted = Store(path)
    assert (
        restarted.list_owned(operator_id="owner", candidate_record_id="missing") == ()
    )
    assert path.read_bytes() == before
