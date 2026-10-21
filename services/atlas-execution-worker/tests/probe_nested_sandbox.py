"""Credential-free nested Codex sandbox rehearsal for a disposable runsc container.

Run with the worker image's entrypoint replaced by Python and stdin attached.
The worker fixture listens only on loopback and never enables execution.
"""

from __future__ import annotations

import json
import secrets
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import uvicorn
from atlas_execution_worker.api import create_app


def main() -> None:
    # :workspace permits temporary scratch writes. Match the production probe:
    # its protected target is persistent worker state, not a sibling in /tmp.
    state_directory = "/opt/atlas/execution-worker-state"
    with tempfile.TemporaryDirectory(prefix="atlas-nested-sandbox-") as temporary, tempfile.TemporaryDirectory(
        prefix="nested-sandbox-proof-", dir=state_directory,
    ) as protected:
        root = Path(temporary)
        state = Path(protected)
        workspace = root / "workspace"
        workspace.mkdir()
        outside = state / "outside-proof"
        outside.write_text("unchanged\n")
        token = secrets.token_urlsafe(32)
        authentication = state / "fixture-token"
        authentication.write_text(token)
        authentication.chmod(0o400)

        # Model commands share the worker network namespace. A valid token
        # must not bypass the worker's separately enforced peer identity.
        app = create_app(authentication_token=token, allowed_client_address="127.0.0.2")
        server = uvicorn.Server(uvicorn.Config(
            app, host="127.0.0.1", port=8081, log_level="critical",
            access_log=False, lifespan="off", loop="asyncio", ws="none",
        ))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 5
            while not server.started and thread.is_alive() and time.monotonic() < deadline:
                time.sleep(0.01)
            if not server.started:
                raise RuntimeError("isolated worker fixture did not start")
            subprocess.run([
                "codex", "sandbox", "-P", "atlas-workspace",
                "-c", 'permissions.atlas-workspace.extends=":workspace"',
                "-c", "permissions.atlas-workspace.network.enabled=true",
                "-C", str(workspace), "python",
                "/opt/atlas/services/atlas-execution-worker/sandbox_probe.py",
                str(outside), str(authentication),
            ], check=True, timeout=30)
            if (workspace / "workspace-proof").read_text() != "workspace-write-ok\n":
                raise RuntimeError("workspace write proof is missing")
            if outside.read_text() != "unchanged\n":
                raise RuntimeError("outside-workspace data was changed")
            version = subprocess.run(
                ["codex", "--version"], check=True, capture_output=True, text=True,
            ).stdout.strip()
            print(json.dumps({
                "status": "passed", "codex_cli": version,
                "workspace_write": "passed", "protected_worker_state_write_denial": "passed",
                "authenticated_untrusted_peer_denial": "passed",
                "model_invocations": 0, "account_credentials_used": False,
            }, sort_keys=True))
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            if thread.is_alive():
                raise RuntimeError("isolated worker fixture did not stop")


if __name__ == "__main__":
    main()
