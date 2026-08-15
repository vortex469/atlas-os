"""Production-Core runtime proof used by the disposable recovery gate."""

from __future__ import annotations

import sys
from pathlib import Path

from app.core.restore_interlock import assert_restore_state_clean
from app.operational_dispatch.ledger import (
    OperationalDispatchLedger,
    OperationalLedgerState,
)


def prove(root: Path) -> None:
    for name in (
        "provider_intents.db",
        "provider_intents.db-wal",
        "provider_intents.db-shm",
    ):
        if (root / name).exists():
            raise RuntimeError("Provider Intent pre-activation cleanup failed")
    assert_restore_state_clean(root)
    namespace = root / ".atlas-restore"
    namespace.mkdir()
    (namespace / "evidence").write_text("bounded", encoding="utf-8")
    try:
        assert_restore_state_clean(root)
    except RuntimeError:
        pass
    else:
        raise RuntimeError("Core startup interlock accepted restore evidence")
    (namespace / "evidence").unlink()
    namespace.rmdir()

    fake_provider_invocations = 0
    ledger = OperationalDispatchLedger(root / "operational_dispatch.db")
    before = ledger.get("dispatching-request")
    if before is None or before.state is not OperationalLedgerState.DISPATCHING:
        raise RuntimeError("restored dispatch barrier evidence is missing")
    summary = ledger.reconcile_startup()
    after = ledger.get("dispatching-request")
    if summary["outcome_unknown"] != 1:
        raise RuntimeError("startup reconciliation did not classify ambiguity")
    if after is None or after.state is not OperationalLedgerState.OUTCOME_UNKNOWN:
        raise RuntimeError("ambiguous dispatch did not become outcome_unknown")
    if fake_provider_invocations != 0:
        raise RuntimeError("startup reconciliation invoked a provider handler")
    for name in (
        "provider_intents.db",
        "provider_intents.db-wal",
        "provider_intents.db-shm",
    ):
        if (root / name).exists():
            raise RuntimeError("Core runtime created inactive Provider Intent state")


if __name__ == "__main__":
    prove(Path(sys.argv[1]))
    print("Core recovery runtime evidence passed")
