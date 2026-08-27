# Installation Candidate Record Lifecycle v1 planning contract

Status: **Atlas v0.20 P0–P5 implemented and release validation complete**.

This document freezes the selected planning boundary for Atlas v0.20,
**Installation Candidate Record Lifecycle**. V0.20 may preserve one exact,
still-valid v0.19 `admitted_but_non_executable` admission as a bounded durable
record. Persistence is the only new capability contemplated here. It grants no
approval, execution, dispatch, Agent, worker, provider, repository, in-guest,
deployment, rollback, remediation, or release authority.

## Repository inspection baseline

Planning started from `main` at `0344172`, after released tag
`atlas-v0.19.0` at `c23f4c4`; P5 validation started at `e198f48`. V0.19
already produces a closed immutable
`InstallationCandidateRecordV1` with exact upstream fingerprints,
`evaluated_at`, `valid_until`, five fixed-false authority fields, and a
domain-separated fingerprint. Its authenticated GET recomputes the admission;
the record is not persisted and no production subsystem consumes it.

The existing `ExecutionCandidate` subsystem predates v0.16–v0.19 and remains
out of scope. V0.20 must not reuse its model, intake, store, approval,
planning, workflow, audit, route, or execution consumers.

## Narrow lifecycle boundary

The sole creation input is a server-assembled v0.19
`InstallationCandidateAdmissionV1` whose status is exactly
`admitted_but_non_executable`, whose reason list is empty, whose candidate
record is present and fingerprint-valid, and whose `valid_until` is strictly
later than the server-owned creation time. The service must recompute this
admission during preservation. A caller supplies only the bounded v0.19 lookup
identifiers and an idempotency key, never an admission or candidate body.

The durable value is a closed `InstallationCandidateRecordEnvelopeV1`
containing only:

- `schema="installation-candidate-record-envelope-v1"`;
- an opaque canonical UUIDv4 `candidate_record_id`;
- authenticated `owner_id` in the store boundary, never exposed to another
  operator;
- `created_at`, a server-owned whole-second UTC timestamp;
- the exact v0.19 `admission_fingerprint`;
- the exact complete `InstallationCandidateRecordV1`, unchanged; and
- a domain-separated envelope fingerprint over every public envelope field
  except the fingerprint itself.

The envelope must not duplicate or enrich plan, selection, provider, artifact,
or destination data. It has no label, notes, extension map, mutable metadata,
approval state, desired state, intent, command, recipe, payload, credential,
address, provider payload, repository reference, workflow/action/dispatch ID,
worker job, retry token, or replay token. Unknown fields are rejected.

Preservation does not extend validity. The only projected lifecycle states are
derived, never stored:

- `active`: `created_at <= now < candidate_record.valid_until`; and
- `expired`: `now >= candidate_record.valid_until`.

The half-open boundary is exact. `expired` is terminal for that record: it
cannot be renewed, refreshed, reactivated, superseded, converted, or updated.
A changed or newly admitted source requires a new record and identity.
Expiration is evaluated during reads and triggers no write, callback, event,
queue, probe, or other work.

Deletion is the only post-create mutation. It removes only the saved advisory
envelope and is not cancellation of an admission, target, approval, intent,
workflow, or execution. There is no update operation and no tombstone visible
to runtime consumers because no such consumers may exist.

## Bounds, idempotency, and persistence

P0 selects conservative closed bounds to be validated before P2:

- at most 16 retained records per operator, counting active and expired;
- at most 64 KiB canonical serialized envelope size;
- visible-ASCII idempotency keys of 1–128 bytes, scoped to the authenticated
  operator and preserve operation;
- exact replay returns the original envelope; reuse with different resolved
  admission identity fails with conflict; and
- when the count limit is reached, creation fails closed until the operator
  explicitly deletes a record. No automatic eviction occurs.

The store is independent from existing ExecutionCandidate, destination
selection, workflow, approval, and audit stores. Create and delete are atomic;
reads validate the complete closed envelope and both fingerprints. Corruption
returns a sanitized unavailable result and is never repaired, partially
projected, or treated as authority.

The existing closed backup v3 inventory is not widened implicitly. P0–P5 must
document explicit operator maintenance, backup/restore compatibility, and
safe removal of this independent advisory store before release. Older code
must be unable to consume the store. No migration of v0.19 ephemeral results
occurs and no startup, scheduled, or background materialization is permitted.

## Proposed API and presentation boundary

P3 must freeze exact paths before implementation. The allowed shape is:

- one authenticated POST that resolves and preserves a current positive v0.19
  admission from bounded identifiers plus an idempotency header;
- one authenticated bounded list GET;
- one authenticated item GET; and
- one authenticated item DELETE.

POST accepts no record body, authority flag, plan, selection, capability fact,
provider payload, artifact, target selector, command, or arbitrary source
material. PUT and PATCH are absent. No route may approve, extend, refresh,
reactivate, convert, execute, dispatch, or attach the record. Cross-operator
item lookup and deletion are indistinguishable from absence under existing
conventions. Authentication, authorization, CSRF/trusted-origin protection,
rate and body bounds, duplicate-key rejection, redaction, and sanitized errors
must match the repository's hardened mutation conventions.

Mission Control may explicitly preserve a currently displayed positive v0.19
admission, list and review owned records, and delete a saved record. It must
state that preservation is not approval and that `active` means only
unexpired source facts. It has no Approve, Install, Prepare, Execute, Convert,
Dispatch, Deploy, Retry, Refresh, Extend, Reactivate, or authority-suggesting
control or navigation.

## Dependency, authority, and threat isolation

- V0.16–v0.19 packages must not import v0.20 code. V0.19 remains independently
  usable and ephemeral.
- V0.20 may depend on the v0.19 closed contract and reviewed read-side
  assembler only. It must not import execution-candidate, approval, workflow,
  dispatch, Agent, worker, provider-mutation, repository-execution,
  deployment, rollback, or release modules.
- No production subsystem may consume a v0.20 envelope. Agent, provider,
  worker, execution, workflow, and approval packages must not recognize its
  schema marker or record ID.
- Preservation performs no provider refresh, network access, guest-agent call,
  SSH, scan, credential lookup, artifact read, repository mutation, in-guest
  read/write, event emission, or clock-derived extension of source validity.
- Replays, restarts, concurrent requests, crafted fingerprints, expired input,
  ownership confusion, store corruption, and quota pressure must fail closed
  without creating duplicate authority or work.

## P0–P5 scope and acceptance

- **P0 — documentation only:** freeze this envelope, lifecycle, bounds,
  idempotency, deletion, store/API/UI isolation, threat model, backup posture,
  and goldens. Make no runtime, test, migration, store, route, or UI change.
- **P1 — contract and pure lifecycle:** implement closed models, exact snapshot
  validation, canonical fingerprints, and pure active/expired derivation with
  exhaustive boundary and hostile-input tests. No I/O or side effects.
- **P2 — bounded store:** implement operator-scoped atomic create/read/delete,
  idempotency, quotas, restart durability, corruption handling, and explicit
  maintenance behavior in a new isolated store. Add no consumer or background
  task.
- **P3 — lifecycle API:** implement the minimal authenticated preserve,
  list/get, and delete surface with server-owned re-admission, ownership,
  mutation defenses, bounds, redaction, OpenAPI, and method-isolation tests.
- **P4 — read-only review:** implement preservation and deletion UX plus
  accessible active/expired review. Prove the absence of authority controls,
  navigation, fields, and network calls.
- **P5 — isolation and closure:** validate exact v0.19 linkage, durability,
  expiry, deletion, concurrency, corruption, quotas, API/UI contracts,
  zero-consumer scans, v0.16–v0.19 goldens, capability parity, full regression,
  backup guidance, and release evidence. Do not automatically migrate, commit,
  tag, push, publish, deploy, or release.

## Must-not-change contracts

- V0.16 `InstallationPlan`, v0.17 destination selection/assessment, and v0.18
  provider facts/capability assessment retain their exact schemas,
  fingerprints, routes, ownership, freshness, lifecycle, storage, goldens, and
  non-authority semantics.
- V0.19 admission remains ephemeral and unchanged. Its schemas, exact record,
  reason precedence, fingerprints, GET route, evaluation rules,
  `valid_until`, fixed-false fields, and lack of consumers remain exact.
- A v0.20 ID or `active` state is not an existing `ExecutionCandidate`, target
  approval, installation intent, proposal, approval, workflow, action request,
  dispatch, deployment specification, executable plan, or permission.
- Existing ExecutionCandidate models, stores, routes, approvals, workflows,
  audit, and execution behavior do not change and never consume v0.20 data.
- Atlas Agent repository support remains exactly `update-compose-stack` and
  operational handling remains exactly `restart-service`;
  `install-container` remains unsupported. Production operational capability
  remains exactly `restart-service/proxmox/qemu`; Provider Intent remains
  identity-bound Proxmox QEMU `monitoring-policy`; Discovery remains GET-only
  and non-authoritative.
- No automatic preservation, approval, execution, dispatch, Agent
  install-container support, worker invocation, provider mutation, repository
  mutation, in-guest read or mutation, installation, deployment, rollback,
  remediation, replay, background refresh/probe, or authority-bearing event is
  introduced.
- Existing independent approval stages, interrupted-side-effect no-replay
  behavior, optional default-disabled execution worker, and
  operator-maintenance-only backup/restore remain unchanged.

## Golden and release-isolation cases

The Home Assistant golden remains `not_admitted` because
`compose/home-assistant.yaml` is absent. It therefore cannot be preserved and
no v0.20 record exists for it. A synthetic exact positive v0.19 fixture may be
preserved once, replayed idempotently, read across restart, observed as active
before its fixed deadline and expired at the deadline, then explicitly
deleted. At every point all authority flags remain false and no execution or
mutation subsystem is invoked.

P5 must scan Core and Agent production code for v0.20 consumers, lock OpenAPI
to the selected lifecycle surface, and verify Mission Control has only
preserve/review/delete behavior. The full Core, Agent, Mission Control,
baseline-aware lint/build, and `git diff --check` gates remain required.

## P5 closure evidence

P1 through P4 implemented the frozen contract without widening its authority.
P5 adds only regression, isolation, and release-validation tests plus this
documentation closure. Structural scans cover all Core and Agent production
Python files and reject recognition of the v0.20 module, envelope type, or
schema outside lifecycle storage/transport wiring. These locks include the
existing approval, execution, operational dispatch, Agent candidate/workflow,
worker, provider, repository, in-guest, deployment, rollback, and interrupted-
side-effect no-replay boundaries.

Integrated OpenAPI is frozen to `GET`/`POST
/api/v1/installation/candidate-records` and `GET`/`DELETE
/api/v1/installation/candidate-records/{candidate_record_id}`. Mission Control
may call only list, get, preserve, and delete and contains only Preserve,
Review, and Delete controls for this surface. The Home Assistant v0.19 golden
remains `not_admitted` with no candidate, and contract validation rejects it at
the v0.20 preservation boundary.

Backup v3 is deliberately not widened to include
`installation_candidate_records.db`. Operators must explicitly preserve or
remove that independent advisory store during maintenance; older releases do
not recognize or consume it. No automatic migration or restore behavior is
introduced. The exact validation commands and observed outcomes are recorded
in `docs/RELEASE_CHECKLIST.md`.
