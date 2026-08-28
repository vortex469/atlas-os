# Installation Approval Intent v1 planning contract

Status: **Atlas v0.21 P0–P5 complete; release validation closed**.

This document freezes the narrowest explicit operator approval-intent boundary
for Atlas v0.21, **Installation Approval Intent**. An authenticated operator may
record the statement that they explicitly approved one exact, owned, active
v0.20 durable non-executable installation candidate identity. The record is
evidence of that statement only. It is not permission and no production
subsystem may consume it to perform work.

P1–P4 implement only the closed evidence contract, isolated append-only store,
authenticated append/list/get routes, and explicit Mission Control evidence
review. P5 adds structural release locks and documentation only. The milestone
adds no migration, execution consumer, worker or Agent capability, provider or
repository mutation, guest access, workflow, deployment, or rollback behavior.

## Repository inspection baseline

Planning starts from current `main` at `2e48731`, after the v0.20 implementation
and validation merge and released tag `atlas-v0.20.0` at `929ebc0`. V0.20
provides an authenticated, operator-scoped, immutable
`InstallationCandidateRecordEnvelopeV1`; its only derived states are `active`
and `expired`, all five embedded authority fields are false, and no production
authority or mutation subsystem consumes it.

The existing `ExecutionCandidate`, approval, audit, workflow, action-request,
dispatch, and execution subsystems predate this milestone and remain separate.
V0.21 must not reuse or modify their models, stores, routes, approvals, workers,
or consumers.

## Narrow approval-intent boundary

Creation is one authenticated operator action over one exact v0.20 record. The
server must load the record through the v0.20 ownership boundary, validate the
complete closed envelope and fingerprints, and require its derived state to be
`active` at a server-owned whole-second UTC time. A caller supplies only the
bounded `candidate_record_id` and an idempotency key. A caller never supplies a
candidate, fingerprint, operator identity, approval time, authority field,
intent statement, target, payload, command, or desired state.

The approved subject identity is exactly this closed tuple:

- the v0.20 `candidate_record_id`;
- the v0.20 envelope fingerprint;
- the exact v0.19 admission fingerprint carried by that envelope; and
- the exact embedded v0.19 candidate-record fingerprint.

No component may omit or substitute a member of this tuple, follow a mutable
alias, or interpret the identity as approval of a catalog item, application,
destination class, future admission, refreshed candidate, replacement guest,
or later record. Any changed source fact or new candidate has a different
identity and requires a distinct future operator action.

The durable value is a closed `InstallationApprovalIntentV1` containing only:

- `schema="installation-approval-intent-v1"`;
- an opaque canonical UUIDv4 `approval_intent_id`;
- the authenticated canonical `operator_id` that made the statement;
- `recorded_at`, a server-owned whole-second UTC timestamp;
- the exact closed approved-subject tuple above;
- `statement="operator_approved_exact_non_executable_candidate"`; and
- a domain-separated fingerprint over every preceding public field.

`operator_id` is also the ownership key and is disclosed only through that
operator's authenticated boundary. The fixed statement has no caller-authored
text, reason, scope, conditions, notes, labels, or extension map. Unknown
fields are rejected. The record contains no candidate snapshot, plan,
selection, provider fact or payload, artifact, credential, address, repository
reference, command, recipe, executable payload, desired state, capability,
workflow/action/dispatch identifier, worker job, retry token, or replay token.

The record is immutable and append-only. It has no mutable `approved` status,
activation, expiry, renewal, refresh, supersession, revocation, cancellation,
conversion, attachment, or delete API. Exactly one intent may exist for an
operator and exact approved-subject tuple; an exact retry returns the original
record. A different candidate identity always requires a new explicit action.

The source candidate may later expire or be deleted under its unchanged v0.20
lifecycle. Neither event changes, revokes, executes, or deletes the historical
statement. After source deletion, the tuple still identifies what was approved
but Atlas may no longer resolve the candidate contents; the intent must expose
that distinction and must not reconstruct, refresh, or treat the subject as
current. Candidate deletion must not be blocked by an intent.

## Bounds, persistence, and failure behavior

P0 selects these conservative closed bounds for validation before P2:

- at most 16 retained approval intents per operator;
- at most 32 KiB canonical serialized size per intent;
- visible-ASCII idempotency keys of 1–128 bytes, scoped to operator and create
  operation;
- exact replay returns the original intent, while reuse for another resolved
  subject fails with conflict; and
- reaching the count limit fails closed, with no eviction, overwrite, expiry,
  compaction, or deletion through the runtime API.

The store is independent from candidate, ExecutionCandidate, approval,
workflow, audit, action, dispatch, and worker stores. Creation is atomic; reads
validate the complete closed record and fingerprint. Corruption returns a
sanitized unavailable result and is never repaired, partially projected, or
treated as authority. Concurrent creation for the same exact subject produces
one record and no duplicate statement.

Backup v3 remains closed and is not widened implicitly. Explicit operator
maintenance, backup/restore compatibility, retention, export if any, and safe
store removal are documented below. Older releases must be unable to consume
the store. There is no migration or approval inference from v0.20 records and
no startup, scheduled, background, or bulk creation.

P5 retains that exclusion. `installation_approval_intents.db` is independent
operator-maintained state and is not part of backup v3. Any file-level copy,
restore, retention, or removal requires Atlas Core to be stopped and remains an
explicit operator procedure; no runtime export, restore, deletion, downgrade
conversion, or automatic migration is introduced. Older releases ignore the
database and cannot consume it as authority.

## API and presentation boundary

P3 may add exactly these authenticated routes under a new namespace:

- `POST /api/v1/installation/candidate-approval-intents` with only
  `candidate_record_id` in its closed body and the hardened idempotency header;
- `GET /api/v1/installation/candidate-approval-intents`; and
- `GET /api/v1/installation/candidate-approval-intents/{approval_intent_id}`.

There is no PUT, PATCH, DELETE, approve-again, revoke, convert, attach, execute,
dispatch, workflow, deployment, or rollback route. Cross-operator lookup is
indistinguishable from absence. Authentication, authorization, CSRF and
trusted-origin protection, rate/body/nesting bounds, duplicate-key rejection,
redaction, and sanitized errors must follow the repository's hardened mutation
conventions.

Mission Control may present one deliberate **Record approval intent** control
for an owned active v0.20 record, require explicit confirmation that names the
exact record identity, and list/review the resulting immutable evidence. It
must say that recording approval neither starts nor permits installation and
that source expiry/deletion does not make the intent executable. There is no
Install, Execute, Dispatch, Deploy, Start workflow, Convert, Attach, Retry,
Revoke, Reactivate, Rollback, or equivalent control, navigation, or request.

## Dependency, authority, and threat isolation

- V0.16–v0.20 packages must not import v0.21 code. V0.20 stays independently
  usable and its preservation, read, expiry, and deletion behavior is exact.
- V0.21 may depend only on the v0.20 closed contract and ownership/read
  boundary. It must not import ExecutionCandidate, legacy approval, audit,
  workflow, action-request, dispatch, Agent, worker, provider-mutation,
  repository-execution, deployment, rollback, or release modules.
- No production subsystem may consume a v0.21 intent. Existing approval and
  execution packages, Atlas Agent, workers, providers, and repositories must
  not recognize its schema, ID, statement, or fingerprint.
- Creation performs no re-admission, candidate refresh, provider read, network
  access, Agent or guest-agent call, SSH, scan, credential lookup, artifact
  read, repository access, mutation, event emission, queueing, or workflow
  creation.
- Forged IDs, cross-operator references, expired/deleted/corrupt candidates,
  crafted fingerprints, replays, concurrency, restart, corruption, and quota
  pressure fail closed without creating authority or work.

The equation is binding for every phase:

`approval intent != execution authorization != dispatch != installation`.

## P0–P5 scope and acceptance

### P0 — Approval-intent contract and threat model — complete

Freeze this exact subject identity, fixed statement, authenticated actor,
immutability, idempotency, bounds, persistence isolation, routes,
presentation, failures, threats, backup posture, and goldens. Acceptance is a
decision-complete documentation diff only. No runtime or test implementation
is included.

### P1 — Closed intent contract and pure validation — complete

Implement the closed model, canonical domain-separated fingerprint, approved-
subject tuple, exact actor binding, and pure validation of a complete active
v0.20 envelope at server-owned time. Tests exhaust unknown fields, bounds,
fingerprint sensitivity, identity substitution, expiry boundary, hostile
input, and determinism. P1 performs no I/O and derives no authority.

### P2 — Bounded append-only store — complete

Implement the independent operator-scoped store, atomic unique creation,
conflict-safe idempotency, quotas, restart durability, reads, and fail-closed
corruption handling. Add no runtime delete, update, expiry task, event, queue,
audit bridge, worker job, or consumer. Document explicit maintenance.

### P3 — Authenticated intent API — complete

Implement only the create/list/item routes frozen above. Creation re-resolves
the owned v0.20 record and accepts it only while active; clients cannot submit
identity proofs or authority fields. Lock ownership, mutation defenses,
bounds, redaction, OpenAPI, unsupported methods, and dependency isolation.

### P4 — Mission Control explicit statement and review — complete

Implement deliberate exact-record confirmation and immutable evidence review
with conspicuous non-execution language and source-availability distinctions.
Prove accessibility, fail-closed/error rendering, exact identity presentation,
and absence of every prohibited control, navigation, field, and network call.

### P5 — Isolation, regression, and release closure — complete

Validate exact v0.20 linkage, actor proof, uniqueness, concurrency, restart,
quota and corruption behavior, API/UI contracts, and zero-consumer structural
scans. Reconfirm v0.16–v0.20 goldens, capability parity, existing approval
separation, no-replay, worker default, backup isolation, and full regression
gates. P5 does not automatically migrate, commit, tag, push, publish, deploy,
or release.

Observed closure: Core/Agent Ruff passed; the focused approval-intent/API/
release-isolation suite passed 38 tests; the full Agent suite passed 912 tests;
Mission Control passed 485 tests plus lint and production build. Structural
tests lock zero Core/Agent consumers, the exact three intended OpenAPI routes,
append/list/get-only Mission Control calls, and the Home Assistant negative
golden. `git diff --check` is clean.

## Must-not-change contracts for P0–P5

- V0.16–v0.19 schemas, fingerprints, routes, ownership, freshness, lifecycle,
  storage, goldens, and non-authority semantics remain exact.
- V0.20 remains an immutable, operator-scoped, durable non-executable snapshot
  with only passive `active`/`expired` derivation and deletion of that advisory
  record. Its envelope, fingerprints, routes, quotas, backup exclusion, five
  false authority fields, lack of consumers, and Home Assistant golden do not
  change. V0.21 neither adds approval fields to it nor blocks its deletion.
- An approval intent is not an existing `ExecutionCandidate`, approved target,
  installation intent, execution approval, permission, proposal, workflow,
  action request, dispatch, deployment specification, executable plan, audit
  approval, replay token, or Agent instruction.
- Existing ExecutionCandidate, approval, audit, workflow, action, dispatch,
  execution, and no-replay contracts remain unchanged and never consume v0.21
  data.
- Atlas Agent repository support remains exactly `update-compose-stack` and
  operational handling remains exactly `restart-service`;
  `install-container` remains unsupported. Production operational capability
  remains exactly `restart-service/proxmox/qemu`; Provider Intent remains
  identity-bound Proxmox QEMU `monitoring-policy`; Discovery remains GET-only
  and non-authoritative.
- No execution, dispatch, Agent invocation, worker invocation, provider
  mutation, repository mutation, guest read or mutation, install, deployment,
  rollback, remediation, replay, workflow start, background work, or
  authority-bearing event is introduced.
- Existing independent approval stages, interrupted-side-effect no-replay
  behavior, optional default-disabled execution worker, and operator-
  maintenance-only backup/restore remain unchanged.

## Golden and release-isolation cases

Home Assistant remains v0.19 `not_admitted`, so no v0.20 record exists and no
v0.21 approval intent can be created for it. A synthetic exact positive v0.19
fixture may produce one owned active v0.20 record. Its owner may explicitly
record exactly one approval intent; replay returns that record, a second
operator cannot observe or approve it, and expired, deleted, altered, or
corrupt candidates fail closed. Later source expiry or deletion creates no
work and does not rewrite the historical intent. At every point all embedded
candidate authority fields remain false and no authority or mutation subsystem
is invoked.

P5 must scan all Core and Agent production code for v0.21 consumers, lock
OpenAPI to the three intent routes, and verify Mission Control has only exact-
record confirmation and evidence review. Full Core, Agent, Mission Control,
baseline-aware lint/build, and `git diff --check` gates remain required.
