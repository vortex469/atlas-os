"""Run the execution-disabled worker on a private Unix socket."""

from __future__ import annotations

import os
from pathlib import Path

import uvicorn

from .api import create_app
from .durable_ledger import DurableRequestLedger
from .server import DEFAULT_SOCKET_PATH, bind_socket, cleanup_socket


def main() -> None:
    state_dir = Path(
        os.environ.get(
            "ATLAS_EXECUTION_WORKER_STATE_DIR",
            "/opt/atlas/execution-worker-state",
        )
    )
    ledger = DurableRequestLedger(state_dir / "ledger.sqlite3")
    reconciliation = ledger.reconcile_startup()
    print(
        "execution worker ledger reconciled "
        f"claimed={reconciliation['claimed']} "
        f"unknown_outcome={reconciliation['unknown_outcome']}"
    )
    app = create_app(durable_ledger=ledger)
    socket_path = Path(os.environ.get("ATLAS_EXECUTION_WORKER_SOCKET", DEFAULT_SOCKET_PATH))
    server_socket = bind_socket(socket_path)
    try:
        uvicorn.run(app, fd=server_socket.fileno(), log_level="info")
    finally:
        server_socket.close()
        cleanup_socket(socket_path)


if __name__ == "__main__":
    main()
