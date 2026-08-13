# Codex Execution Worker Contracts

> Historical design note: this document records the S1 contract milestone as
> designed at that stage. The current production boundary is documented in
> `codex-execution-sandbox-hardening.md`; statements below about future or
> disabled integration describe S1 history rather than current release status.

S1 defines the versioned data boundary for a future `atlas-execution-worker`.
It does not create the worker, transport, sandbox, or execution path.

## Authority and trust

Atlas Agent remains the sole authority for planning, approvals, workflow state,
persistence, verification, review, and commit decisions. A worker receives only
an already-approved immutable `WorkerExecutionRequest`; it cannot approve,
change the command, expand affected-file scope, access Agent state databases,
commit, or push. `WorkerAttestation` is bounded runtime evidence, not a
cryptographic trust claim.

The existing local `ExecutionRequest` and `ExecutionResult` remain unchanged.
The worker contracts are separate because they carry candidate, plan,
repository-freshness, affected-file, and digest evidence that has different
semantics from local subprocess execution.

## S1 request

`WorkerExecutionRequest` is schema version 1 and supports `update-compose-stack`
plus the validation-only `rc1-validation-smoke` operation. It contains workflow,
candidate, plan, repository token and expected HEAD, immutable operation argv,
isolated relative working directory, canonical affected files, timeout, and a
digest. The digest uses
canonical sorted-key JSON and SHA-256 with the prefix
`execution-request-digest-v1:`. Argument order is significant. Affected files
are normalized, sorted, and duplicate-free. Absolute paths and traversal are
rejected.

The `rc1-validation-smoke` operation is fixed to one argv token, repository
root working directory, one target file
`services/atlas-agent/tests/test_execution_engine.py`, and one marker string.
The worker performs that append directly in the disposable workspace. It does
not invoke a shell or interpreter and accepts no arbitrary command, path,
content, or additional affected file. Existing `codex exec` validation remains
unchanged.

## S1 result

`WorkerExecutionResult` separates outcome status from a deterministic failure
code. It bounds stdout, stderr, changed-file count, and patch metadata. Output
truncation is explicit. Results bind to the request ID, validate changed files
against the approved scope, and carry structured evidence for uid 10001,
read-only rootfs, no-new-privileges, capabilities, and the named sandbox
profile.

## Compatibility and rollout

Unknown fields and unsupported schema versions are rejected. No old local
execution snapshot is reinterpreted as a worker request. S1 does not enable
execution; transport, isolated workspace/patch handling, sandbox runtime, and
Agent integration are later milestones.
