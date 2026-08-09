# S2 Execution Worker Skeleton

S2 adds a standalone `atlas-execution-worker` skeleton with HTTP over a private
Unix-domain socket only. The default socket is
`/run/atlas-execution-worker/worker.sock`; its parent is created with mode 0750
and the socket is mode 0660. A configured stale socket is removed only when it
is a socket, and shutdown removes the worker socket.

The service exposes `GET /health`, `POST /v1/executions`, and
`GET /v1/executions/{execution_request_id}`. It validates the canonical S1
request and digest, atomically claims request IDs in a non-durable in-memory
ledger, and returns a deterministic `blocked / worker_unavailable` result.
Execution is explicitly disabled: S2 never invokes Codex, subprocesses, or a
repository.

Identical requests reuse the existing claim/result. Reusing an ID with another
digest returns a deterministic conflict. The Unix socket's filesystem
possession is the S2 transport identity; the request digest provides integrity,
not caller authentication. Stronger authentication is a later threat-model
decision.

Atlas Agent remains the workflow, approval, persistence, verification, review,
and commit authority. The optional Agent `UnixSocketWorkerClient` is not wired
to `ExecutionEngine` or `WorkflowEngine`. S2 has no durable ledger and no
Compose or production topology changes.
