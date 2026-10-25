"""Real TCP response-loss rehearsal; executable with stdlib unittest in the worker image.

Only loopback listeners, temporary repositories and an inert patch fixture are
used. No model, production credentials, deployment command or live worker
configuration is involved. Fixture attestations are not runtime proofs.
"""

from __future__ import annotations

import hashlib
import http.client
import secrets
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from collections import Counter
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import uvicorn
from app.execution.backends import WorkerExecutionBackend, WorkerExecutionContext
from app.execution.models import ExecutionRequest, ExecutionStatus
from app.execution.patches import WorkerPatchApplier
from app.execution.worker_client import TcpWorkerClient, WorkerTransportError
from app.execution.worker_contracts import (
    CODEX_WORKSPACE_EXEC_ARGV_PREFIX,
    BoundedOutput,
    WorkerAttestation,
    WorkerExecutionResult,
    WorkerExecutionStatus,
)
from app.planning.models import ImplementationPlan
from atlas_execution_worker.api import create_app
from atlas_execution_worker.durable_ledger import DurableRequestLedger

PATCH = """diff --git a/compose.production.yaml b/compose.production.yaml
--- a/compose.production.yaml
+++ b/compose.production.yaml
@@ -1 +1 @@
-image: example/fixture:old
+image: example/fixture:new
"""


@contextmanager
def serve_app(app):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(16)
        server = uvicorn.Server(uvicorn.Config(
            app, log_level="critical", access_log=False, lifespan="off",
            loop="asyncio", ws="none", timeout_graceful_shutdown=2,
        ))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 5
            while not server.started and thread.is_alive() and time.monotonic() < deadline:
                time.sleep(0.01)
            if not server.started:
                raise RuntimeError("rehearsal worker did not start")
            yield listener.getsockname()[1]
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            if thread.is_alive():
                raise RuntimeError("rehearsal worker did not stop")


@contextmanager
def dropping_proxy():
    class Proxy(ThreadingHTTPServer):
        daemon_threads = True
        upstream_port = 0

        def __init__(self):
            super().__init__(("127.0.0.1", 0), Handler)
            self.methods = Counter()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def forward(self):
            self.server.methods[self.command] += 1
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            connection = http.client.HTTPConnection("127.0.0.1", self.server.upstream_port, timeout=5)
            try:
                connection.request(self.command, self.path, body=body, headers={
                    "Authorization": self.headers.get("Authorization", ""),
                    "Content-Type": "application/json", "Connection": "close",
                })
                response = connection.getresponse()
                data = response.read()
                if self.command == "POST":
                    # Consume the completed upstream response, then deliver EOF
                    # to Agent. The actual production TCP client sees the loss.
                    self.close_connection = True
                    self.connection.shutdown(socket.SHUT_RDWR)
                    return
                self.send_response(response.status)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(data)
            finally:
                connection.close()

        do_POST = forward
        do_GET = forward

    with Proxy() as proxy:
        thread = threading.Thread(target=proxy.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        thread.start()
        try:
            yield proxy
        finally:
            proxy.shutdown()
            thread.join(timeout=5)
            if thread.is_alive():
                raise RuntimeError("rehearsal proxy did not stop")


class InertPatchRunner:
    calls = 0

    def execute(self, request):
        self.calls += 1
        return WorkerExecutionResult(
            schema_version=1, execution_request_id=request.execution_request_id,
            status=WorkerExecutionStatus.SUCCEEDED, return_code=0,
            stdout=BoundedOutput(""), stderr=BoundedOutput(""),
            changed_files=("compose.production.yaml",),
            patch_digest="sha256:" + hashlib.sha256(PATCH.encode()).hexdigest(),
            patch_size_bytes=len(PATCH.encode()), patch_truncated=False,
            duration_seconds=0, failure_code=None,
            workspace_head=request.expected_repository_head,
            base_repository_head=request.expected_repository_head,
            patch=BoundedOutput(PATCH),
            worker_attestation=WorkerAttestation(10001, True, True, "0", "inert-fixture"),
        )


class TransportReconciliationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="atlas-response-loss-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repository = self.root / "repository"
        self.repository.mkdir()
        self.git("init", "--quiet", "--initial-branch=main")
        self.git("config", "user.name", "Inert Rehearsal")
        self.git("config", "user.email", "rehearsal@example.invalid")
        (self.repository / "compose.production.yaml").write_text("image: example/fixture:old\n")
        self.git("add", "compose.production.yaml")
        self.git("commit", "--quiet", "-m", "fixture")
        head = self.git("rev-parse", "HEAD")
        plan = ImplementationPlan(
            checkpoint_id="fixture", title="Inert TCP rehearsal", goal="Recover without replay",
            repository_root=self.repository, branch="main", head_commit=head,
            scope_items=("update-compose-stack",), affected_files=(Path("compose.production.yaml"),),
            required_tests=(), risks=(),
        )
        self.request = ExecutionRequest(
            "rehearsal-request", plan, (*CODEX_WORKSPACE_EXEC_ARGV_PREFIX, "inert fixture only"), self.repository,
        )
        self.context = WorkerExecutionContext(
            workflow_id="rehearsal-workflow", candidate_id="rehearsal-candidate",
            candidate_fingerprint="fixture-candidate", plan_id="fixture-plan",
            plan_fingerprint="fixture-plan-fingerprint", expected_repository_head=head,
            repository_token="fixture-repository", allowed_affected_files=("compose.production.yaml",),
            repository_branch="main",
        )
        self.database = self.root / "ledger.sqlite3"
        self.token = secrets.token_urlsafe(32)

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.repository), *args], check=True,
            capture_output=True, text=True,
        ).stdout.strip()

    def backend(self, port, *, authenticated=True):
        return WorkerExecutionBackend(
            TcpWorkerClient("127.0.0.1", port, timeout_seconds=5,
                            authentication_token=self.token if authenticated else None),
            repository_token=self.context.repository_token,
        )

    def app(self, ledger, runner=None):
        return create_app(
            durable_ledger=ledger, authentication_token=self.token,
            allowed_client_address="127.0.0.1", execution_enabled=runner is not None,
            runners={self.context.repository_token: runner} if runner else {},
        )

    def test_lost_tcp_response_and_worker_restart_recover_one_patch_without_resubmission(self):
        runner = InertPatchRunner()
        with dropping_proxy() as proxy:
            backend = self.backend(proxy.server_port)
            ledger = DurableRequestLedger(self.database)
            with serve_app(self.app(ledger, runner)) as port:
                proxy.upstream_port = port
                result = backend.execute(self.request, context=self.context)
                self.assertIs(result.status, ExecutionStatus.UNKNOWN)
                self.assertEqual(runner.calls, 1)
                self.assertEqual(ledger.get(self.request.identifier).state, "completed")
                self.assertEqual(self.git("diff", "--name-only"), "")

            # A new worker app, ledger reader and Agent adapter use the same
            # immutable request. The restarted worker has execution disabled.
            reopened = DurableRequestLedger(self.database)
            reopened.reconcile_startup()
            with serve_app(self.app(reopened)) as port:
                proxy.upstream_port = port
                with self.assertRaises(WorkerTransportError):
                    TcpWorkerClient("127.0.0.1", port).get_result(self.request.identifier)
                fresh_backend = self.backend(proxy.server_port)
                recovered = fresh_backend.reconcile(self.request, context=self.context)
                self.assertIs(recovered.status, ExecutionStatus.SUCCEEDED)
                WorkerPatchApplier().apply(
                    self.repository, fresh_backend.prepare(self.request, context=self.context),
                    recovered.worker_result,
                )
            self.assertEqual(proxy.methods, {"POST": 1, "GET": 1})
            self.assertEqual(runner.calls, 1)
            self.assertEqual(reopened.get(self.request.identifier).attempt, 1)
            self.assertEqual(self.git("diff", "--name-only"), "compose.production.yaml")

    def test_interrupted_start_stays_unknown_after_restart_without_execution(self):
        with dropping_proxy() as proxy:
            backend = self.backend(proxy.server_port)
            request = backend.prepare(self.request, context=self.context)
            ledger = DurableRequestLedger(self.database)
            ledger.claim(request)
            ledger.mark_executing(request)
            reopened = DurableRequestLedger(self.database)
            self.assertEqual(reopened.reconcile_startup()["unknown_outcome"], 1)
            with serve_app(self.app(reopened)) as port:
                proxy.upstream_port = port
                result = backend.reconcile(self.request, context=self.context)
            self.assertIs(result.status, ExecutionStatus.UNKNOWN)
            self.assertEqual(proxy.methods, {"GET": 1})
            self.assertEqual(reopened.get(self.request.identifier).attempt, 1)
            self.assertEqual(self.git("diff", "--name-only"), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
