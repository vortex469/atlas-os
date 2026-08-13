# S2 Execution Worker Skeleton

> Historical design note: this document records the deliberately disabled S2
> skeleton milestone. The current production boundary is documented in
> `codex-execution-sandbox-hardening.md`; the limitations below describe S2
> history rather than current release status.

S2 adds a standalone `atlas-execution-worker` skeleton with HTTP over a private
TCP endpoint on the internal `atlas-execution-worker-net` Compose network.
The worker listens on port 8081 without publishing that port to the host.

The service exposes `GET /health`, `POST /v1/executions`, and
`GET /v1/executions/{execution_request_id}`. It validates the canonical S1
request and digest, atomically claims request IDs in a non-durable in-memory
ledger, and returns a deterministic `blocked / worker_unavailable` result.
Execution is explicitly disabled: S2 never invokes Codex, subprocesses, or a
repository.

Identical requests reuse the existing claim/result. Reusing an ID with another
digest returns a deterministic conflict. The internal network is the S2
transport boundary; the request digest provides integrity, not caller
authentication. Stronger authentication is a later threat-model decision.

Atlas Agent remains the workflow, approval, persistence, verification, review,
and commit authority. The optional Agent `TcpWorkerClient` is not wired
to `ExecutionEngine` or `WorkflowEngine`. S2 has no durable ledger and no
Compose or production topology changes.
