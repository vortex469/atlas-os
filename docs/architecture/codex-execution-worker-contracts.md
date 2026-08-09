# Codex Execution Worker Contracts

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

`WorkerExecutionRequest` is schema version 1 and supports only
`update-compose-stack`. It contains workflow, candidate, plan, repository token
and expected HEAD, immutable `codex exec` argv, isolated relative working
directory, canonical affected files, timeout, and a digest. The digest uses
canonical sorted-key JSON and SHA-256 with the prefix
`execution-request-digest-v1:`. Argument order is significant. Affected files
are normalized, sorted, and duplicate-free. Absolute paths and traversal are
rejected.

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
