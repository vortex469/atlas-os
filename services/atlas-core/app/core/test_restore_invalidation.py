from __future__ import annotations

import asyncio
import os
import runpy
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

from app.operational_dispatch.ledger import (
    OperationalDispatchLedger,
    OperationalLedgerState,
)
from app.operational_dispatch.registry import (
    OperationalHandlerRegistration,
    OperationalHandlerRegistry,
)
from app.operational_dispatch.service import OperationalDispatchService
from app.operational_dispatch.test_support import make_request
from app.operator_auth.models import OperatorCredential
from app.operator_auth.sessions import OperatorSessionStore
from scripts.test_atlas_data_tool import _close, _source

TOOL = runpy.run_path(
    str(Path(__file__).parents[4] / "scripts" / "atlas-data-tool.py")
)


def test_v3_restore_invalidates_sessions_and_leaves_provider_intents_inactive(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    connections = _source(source)
    backup = tmp_path / "backup"
    TOOL["create_backup"](source, backup, operator_auth_initialized=False)
    _close(connections)

    target = tmp_path / "target"
    target.mkdir()
    old_store = OperatorSessionStore(target / "operator_sessions.db", 3600)
    created = old_store.create(
        OperatorCredential(
            operator_id="operator",
            password_hash="unused",
            permissions=(),
        ),
        now=datetime(2026, 1, 1, tzinfo=UTC),
    )
    (target / "provider_intents.db").write_bytes(b"stale provider intent")

    TOOL["restore_backup"](backup, target)

    assert not (target / "operator_sessions.db").exists()
    assert not (target / "provider_intents.db").exists()
    new_store = OperatorSessionStore(target / "operator_sessions.db", 3600)
    assert new_store.resolve(created.session_token, now=datetime(2026, 1, 1, tzinfo=UTC)) is None
    with sqlite3.connect(target / "operator_sessions.db") as connection:
        assert connection.execute("SELECT count(*) FROM operator_sessions").fetchone()[0] == 0
    assert not (target / "provider_intents.db").exists()
    assert (target / "operator_sessions.db").stat().st_mode & 0o777 == 0o600
    assert (target / "operator_sessions.db").stat().st_uid == os.getuid()


def test_restored_dispatching_ledger_reconciles_without_handler_replay(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    connections = _source(source)
    _close(connections)
    (source / "operational_dispatch.db").unlink()
    request = make_request()
    source_ledger = OperationalDispatchLedger(source / "operational_dispatch.db")
    source_ledger.claim(request)
    source_ledger.mark_revalidated(request)
    source_ledger.mark_dispatching(request)
    backup = tmp_path / "backup"
    TOOL["create_backup"](source, backup, operator_auth_initialized=False)

    target = tmp_path / "target"
    target.mkdir()
    TOOL["restore_backup"](backup, target)

    restored = OperationalDispatchLedger(target / "operational_dispatch.db")
    assert restored.get(request.request_id).state is OperationalLedgerState.DISPATCHING  # type: ignore[union-attr]
    assert restored.reconcile_startup()["outcome_unknown"] == 1
    assert restored.get(request.request_id).state is OperationalLedgerState.OUTCOME_UNKNOWN  # type: ignore[union-attr]

    handler = AsyncMock()
    result = asyncio.run(
        OperationalDispatchService(
            ledger=restored,
            registry=OperationalHandlerRegistry(
                (
                    OperationalHandlerRegistration(
                        "restart-service", "proxmox", "qemu", handler
                    ),
                )
            ),
            execution_intents=frozenset({"restart-service"}),
            resolver=AsyncMock(),
        ).dispatch(request)
    )
    assert result.status == "outcome_unknown"
    handler.assert_not_awaited()
