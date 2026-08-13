# S3 Execution Backend Adapter

> Historical design note: this document records the S3 adapter milestone before
> production worker integration. The current production boundary is documented
> in `codex-execution-sandbox-hardening.md`; statements below about future or
> non-production worker mode describe S3 history rather than current release
> status.

S3 introduces a synchronous `ExecutionBackend` seam behind the existing
`ExecutionEngine` facade. `LocalExecutionBackend` retains the current
`SubprocessRunner`, `shell=False`, policy, timeout, output, and failure behavior.

`WorkerExecutionBackend` is an explicit adapter for the future isolated worker.
It requires a `WorkerExecutionContext` carrying workflow, candidate, plan,
repository HEAD/token, affected-file, intent, and branch evidence. It builds and
validates the immutable S1 request, preserves argv element-for-element, submits
through the private TCP client, validates the S1 result, and maps each worker
failure code deterministically to the local result model.

The backend setting is `ATLAS_EXECUTION_BACKEND`, defaulting to `local`.
`ATLAS_EXECUTION_WORKER_HOST` and `ATLAS_EXECUTION_WORKER_PORT` select the
private worker endpoint. Worker mode is
opt-in and not production-ready while S2 execution remains disabled. No
automatic worker-to-local fallback or automatic resubmission exists after a
worker submission attempt. Atlas Agent remains the approval, workflow,
persistence, verification, review, and commit authority.

S3 does not connect `WorkflowEngine` to the worker, add repository handling, or
change approval and candidate validation semantics.
