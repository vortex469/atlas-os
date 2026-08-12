"""Run the execution-disabled worker on the private TCP network."""

from __future__ import annotations

import os
from pathlib import Path

import uvicorn

from .api import create_app
from .config import WorkerSettings
from .durable_ledger import DurableRequestLedger
from .runner import WorkspaceExecutionRunner
from .server import DEFAULT_HOST, DEFAULT_PORT, validate_port
from .workspace import WorkerWorkspaceManager


def main() -> None:
    state_dir = Path(
        os.environ.get(
            "ATLAS_EXECUTION_WORKER_STATE_DIR",
            "/opt/atlas/execution-worker-state",
        )
    )
    ledger = DurableRequestLedger(state_dir / "ledger.sqlite3")
    worker_settings = WorkerSettings.from_environment()
    runners = {
        token: WorkspaceExecutionRunner(
            WorkerWorkspaceManager(
                source_root=source,
                workspace_root=Path("/tmp/atlas-worker-workspaces") / token,
                repository_token=token,
                trusted_repository_paths=worker_settings.repository_mapping.values(),
            ),
            enabled=worker_settings.execution_enabled,
        )
        for token, source in worker_settings.repository_mapping.items()
    }
    reconciliation = ledger.reconcile_startup()
    print(
        "execution worker ledger reconciled "
        f"claimed={reconciliation['claimed']} "
        f"unknown_outcome={reconciliation['unknown_outcome']}"
    )
    app = create_app(
        durable_ledger=ledger,
        execution_enabled=worker_settings.execution_enabled,
        runners=runners,
    )
    host = os.environ.get("ATLAS_EXECUTION_WORKER_HOST", DEFAULT_HOST)
    port = validate_port(
        int(os.environ.get("ATLAS_EXECUTION_WORKER_PORT", str(DEFAULT_PORT)))
    )
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
