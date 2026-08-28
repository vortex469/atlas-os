# Installation Execution Request v1 planning contract

Status: **Atlas v0.23 P0–P5 complete; record-only boundary validated**.

This document freezes the narrowest Core-side **Installation Execution Request
Boundary** that can bind one v0.20 durable candidate record, one v0.21 approval
intent, and one v0.22 Agent install-container validation evidence chain. The
request is an immutable, operator-owned record of a request that may be
considered by a separately designed future release. It is not an execution
authorization, dispatch, job, workflow, Agent instruction, or replay token.

The binding equation for every v0.23 phase is:

`recorded request != execution approval != dispatch != execution`.

## Repository inspection baseline

Planning starts from current `main` at
`22bff36`, after the v0.22 implementation merge. V0.20 provides an owned,
durable, immutable, non-executable candidate envelope with passive
`active`/`expired` derivation. V0.21 provides an owned, immutable approval
statement for one exact active v0.20 identity. V0.22 provides a closed
validation-only Agent request/result/evidence contract whose successful status
is only `valid_but_unsupported`, whose four authority fields are false, and
whose implementation has no production intake or consumer.

Existing `ExecutionCandidate`, approval, audit, workflow, action-request,
dispatch, execution, worker, provider, repository, and Agent intent surfaces
remain separate. V0.23 must not reuse or modify them.

## Exact creation and durable schemas

The authenticated caller supplies only this closed body plus the existing
hardened idempotency header:

```text
InstallationExecutionRequestCreateV1 = {
  schema: "installation-execution-request-create-v1",
  candidate_record_id: canonical UUIDv4,
  approval_intent_id: canonical UUIDv4,
  agent_request: AgentInstallContainerRequestV1,
  agent_validation: AgentInstallContainerValidationV1
}
```

The two embedded v0.22 values retain their exact released schemas and bounds.
The Core request body is at most 96 KiB in canonical form. Every JSON object is
closed and rejects duplicate and unknown keys; strings are NFC; timestamps are
UTC whole seconds; JSON numbers remain prohibited where the embedded contract
prohibits them. The caller cannot supply operator identity, Core request ID,
recording time, validity, lifecycle state, statement, authority field, linkage
fingerprint, or Core record fingerprint.

After resolving and validating every dependency, Core may atomically append
only this durable public value:

```text
InstallationExecutionRequestV1 = {
  schema: "installation-execution-request-v1",
  execution_request_id: canonical UUIDv4,
  recorded_at: UtcSecond,
  valid_until: UtcSecond,
  operation: "install-container",
  mode: "record-only",
  linkage: InstallationExecutionRequestLinkageV1,
  statement: "operator_requested_future_execution_of_exact_validated_candidate",
  execution_authorized: false,
  dispatch_allowed: false,
  agent_invocation_allowed: false,
  mutation_allowed: false,
  replay_allowed: false,
  execution_request_fingerprint: FingerprintV1
}

InstallationExecutionRequestLinkageV1 = {
  candidate_record_id: canonical UUIDv4,
  candidate_envelope_fingerprint: FingerprintV1,
  admission_fingerprint: FingerprintV1,
  candidate_record_fingerprint: FingerprintV1,
  approval_intent_id: canonical UUIDv4,
  approval_intent_fingerprint: FingerprintV1,
  agent_request_id: canonical UUIDv4,
  agent_request_fingerprint: FingerprintV1,
  agent_validation_fingerprint: FingerprintV1,
  agent_evidence_fingerprint: FingerprintV1,
  destination_fingerprint: lowerhex[64],
  source_plan_fingerprint: FingerprintV1,
  artifact_policy_fingerprint: FingerprintV1
}
```

`owner_id` is a mandatory store partition and authorization attribute but is
not part of the public value. It is included in the fingerprint input so an
identical public record cannot be transplanted between operators. The request
fingerprint is SHA-256 over UTF-8
`"atlas:installation-execution-request:v1"`, one NUL byte, and canonical JSON
of `{owner_id, record}` excluding `execution_request_fingerprint`.

`artifact_policy_fingerprint` is copied from the v0.22 audit evidence's exact
runtime/limit-policy fingerprint. No raw candidate, approval, provider payload,
deployment document, Compose/YAML, command, environment, secret, credential,
address, hostname, arbitrary metadata, notes, labels, URL, extension map,
desired state, workflow/action/dispatch ID, worker job, lease, retry token, or
replay token is stored.

## Exact fingerprints, ownership, and linkage

Creation is one deliberate action by the authenticated operator. Core must:

1. load the v0.20 envelope through its existing ownership boundary, validate
   the complete envelope and embedded candidate fingerprints, and derive it as
   `active` at server-owned `recorded_at`;
2. load the v0.21 intent through its existing ownership boundary, validate its
   complete fingerprint, require its `operator_id` to equal the authenticated
   operator, and require its approved-subject tuple to equal the loaded v0.20
   ID plus envelope, admission, and candidate-record fingerprints;
3. validate the complete submitted v0.22 Agent request, request fingerprint,
   validation, validation fingerprint, and audit-evidence fingerprint without
   calling Atlas Agent;
4. require the Agent request's six candidate/approval proof values to equal
   the resolved v0.20/v0.21 chain and require its subject, destination, source
   plan, artifact source, immutable image, and policy values to satisfy the
   frozen v0.22 linkage and boundary rules;
5. require the validation and evidence to identify that exact Agent request,
   have `status=valid_but_unsupported`, have no reason codes, and retain every
   execution/dispatch/mutation/replay field as false; and
6. copy only the closed linkage above and calculate a new Core fingerprint.

The submitted v0.22 evidence is structurally and fingerprint validated, not
promoted into an Agent attestation or execution authority. V0.22 evidence has
no signature or trusted delivery channel; v0.23 must label its provenance as
`operator_submitted_agent_validation_evidence` in API/UI projections and must
not claim Agent liveness, destination liveness, image presence, or runtime
readiness. Any missing, foreign-owner, expired, deleted, corrupt, mismatched,
reconstructed, refreshed, partially supplied, or legacy proof fails closed.

## Lifecycle, freshness, expiry, and no replay

Lifecycle is derived during reads and never stored:

- `recorded`: `recorded_at <= now < valid_until`; and
- `expired`: `now >= valid_until`.

Both states are non-executing and non-authorizing. `recorded` means only that
the complete evidence chain was fresh when Core accepted it. `expired` is
terminal: no renew, refresh, reactivate, supersede, convert, attach, dispatch,
execute, retry, resume, or status update exists. Expiry performs no write,
event, callback, queueing, cleanup, probe, or other work.

At creation, server-owned whole-second `recorded_at` must satisfy all of:

- the v0.20 envelope is active;
- `agent_request.issued_at <= agent_validation.validated_at <
  agent_request.expires_at`;
- `agent_validation.validated_at <= recorded_at` and
  `recorded_at - agent_validation.validated_at <= 60 seconds`; and
- `recorded_at < agent_request.expires_at`.

`valid_until` is exactly
`min(candidate_record.valid_until, agent_request.expires_at,
recorded_at + 300 seconds)`. The approval intent is historical and has no
expiry; its source identity must nevertheless still resolve to the same active
v0.20 record at creation. Clock rollback, future validation time, unavailable
trusted clock, zero-width validity, or any boundary ambiguity fails closed.

Idempotency and no replay are stricter than ordinary request retry:

- visible-ASCII idempotency keys are 1–128 bytes and scoped to authenticated
  operator plus create operation;
- exact replay returns the original record without re-resolution,
  revalidation, time extension, or work; reuse for different content fails;
- the store atomically reserves the operator-scoped idempotency key, v0.21
  `approval_intent_id`, v0.22 `agent_request_id`, Agent request fingerprint,
  validation fingerprint, and Core execution-request fingerprint;
- concurrent duplicates create one logical record; reuse of any reserved
  identity with different content fails closed;
- one approval intent can produce at most one v0.23 request, including after
  expiry, deletion of a source, restart, timeout, or lost response; and
- missing durable reservation evidence or ambiguous append completion returns
  an unavailable result and never permits reconstruction or retry as new work.

There is no runtime delete or cancellation API. The record performs no work,
so deleting it would not cancel anything. A later release must define a new,
independent, fresh execution approval and atomic consume/dispatch/no-replay
contract; it may reference a still-resolvable v0.23 record but may not treat
the record, its `recorded` state, or exact replay response as permission.

## Store, redaction, and audit evidence

P2 may add one independent append-only operator-scoped store with atomic
creation, restart durability, complete-record validation, and these bounds:

- at most 16 retained requests per operator;
- at most 64 KiB canonical serialized record size; and
- no eviction, compaction, automatic expiry deletion, migration, repair, or
  background task.

Quota exhaustion and corruption fail closed. Backup v3 remains closed and is
not widened. File-level retention, copy, restore, or removal is explicit
operator maintenance while Core is stopped; older versions must ignore and be
unable to consume the store.

The durable record itself is the complete v0.23 audit evidence. API/UI/log
projections may expose only owned IDs, bounded timestamps, derived lifecycle,
fixed statement and authority fields, exact fingerprints, sanitized subject
class (`proxmox/qemu/existing-guest` plus resource ID), immutable image digest,
artifact kind, and evidence provenance class. They must not expose owner IDs to
other operators, provider payloads, destination raw identity, credentials,
tokens, environment, commands, arbitrary source text, raw deployment content,
registry authentication, exception serialization, or unbounded paths.

Errors use only a closed bounded vocabulary: `malformed`, `not_found`,
`not_current`, `ownership_mismatch`, `proof_mismatch`, `evidence_rejected`,
`replay_conflict`, `quota_exceeded`, and `unavailable`. Cross-operator lookup is
indistinguishable from absence. Logs contain only correlation ID, owned request
ID when available, fingerprints, lifecycle, and one error code. The v0.23
record is not appended to the existing execution audit store and emits no
event; log or record presence is never evidence that work occurred.

## Default-disabled API and Mission Control boundary

P3 may add exactly these authenticated Core routes:

- `POST /api/v1/installation/execution-requests` with the closed create body
  and hardened idempotency header;
- `GET /api/v1/installation/execution-requests`; and
- `GET /api/v1/installation/execution-requests/{execution_request_id}`.

There is no PUT, PATCH, DELETE, execute, dispatch, send-to-Agent, validate via
Agent, convert, attach, workflow, retry, resume, deploy, rollback, or enable
route. POST performs only local ownership reads, pure validation, and one
append. It must not import an Agent client, execution/dispatch/worker/provider/
repository/runtime module, run a process, read a repository or guest, or make
network calls. No configuration or environment switch can activate execution.

Mission Control may provide one deliberate **Record execution request** action
only from an owned active candidate and exact approval-intent review, require
explicit confirmation of the exact identities and submitted validation
evidence, and list/read immutable records. It must display **Non-executing;
Agent evidence is operator-submitted; no work has started** and distinguish
`recorded` from `expired` without terms such as queued, ready, authorized, or
approved for execution. It has no install, execute, dispatch, deploy, send,
start-workflow, retry, cancel, rollback, or authority navigation/control.

The entire v0.23 feature remains default-disabled until P5 release closure.
Before then, no production router or Mission Control navigation may expose it.
Even when the record-only API is explicitly released, execution remains
unconditionally disabled because no execution route, consumer, adapter, or
feature flag exists.

## P0–P5 scope and acceptance

### P0 — Core request contract and threat model — complete

Freeze this exact schema, full three-release linkage, ownership, freshness,
lifecycle, idempotency/no-replay, append-only evidence, redaction, API/UI
boundary, default-disabled posture, threats, goldens, and must-not-change
contracts. P0 changes planning documentation only.

### P1 — Closed Core models and pure validation — complete

Implement isolated immutable models, duplicate/unknown-field rejection,
canonical fingerprints, exact v0.20/v0.21/v0.22 linkage validation, freshness,
derived lifecycle, redacted failures, and complete hostile-input tests. Use
injected closed values only; perform no I/O or registration.

### P2 — Bounded append-only request store — complete

Implement the independent operator-scoped store, atomic multi-identity
reservation, idempotency, uniqueness, quotas, restart durability, reads, and
fail-closed corruption/ambiguity behavior. Add no delete/update, event, queue,
audit bridge, expiration task, consumer, worker job, or migration.

### P3 — Authenticated record-only Core API — complete

Implement only create/list/item-read. Re-resolve v0.20/v0.21 ownership and
current state locally, accept only the complete submitted v0.22 pair, enforce
freshness and bounds, and lock OpenAPI/method/redaction/dependency isolation.
Do not call Agent or any authority/mutation subsystem.

### P4 — Mission Control request evidence review — complete

Implement explicit confirmation, submission, and immutable review with
conspicuous non-execution and untrusted-delivery provenance language. Prove
accessibility, lifecycle/error rendering, ownership isolation, exact identity
display, and absence of prohibited controls, navigation, and network calls.

### P5 — Isolation, no-replay, and release closure — complete

Prove exact linkage, same-owner resolution, freshness boundaries, all atomic
reservations, concurrency/restart/timeout ambiguity, quotas, corruption,
redaction, API/UI contracts, and zero consumers. Reconfirm all v0.16–v0.22
goldens, capability parity, existing approval/no-replay/worker/backup
boundaries, full Core/Agent/Mission Control gates, and default-disabled release
posture. P5 does not automatically migrate, tag, push, publish, deploy, or
release.

P5 validation began from
`b6148294039c295b9e781ac13079403c4deee69b`. Structural tests lock the
default-disabled service, fixed-false authority schema, exact guarded
create/list/get Core surface, repository-wide absence of Core and Agent
consumers, and Mission Control's dedicated adapter and prohibited-control
boundary. The focused Core suite passed 233 tests, the full Agent suite passed
948 tests, and Mission Control passed 499 tests plus lint and production build.
Home Assistant remains unable to reach this boundary and no deployment
artifact exists. P5 changed tests and release evidence only.

## Must-not-change contracts for P0–P5

- V0.16–v0.22 schemas, fingerprints, routes, ownership, stores, lifecycle,
  freshness, goldens, and non-authority meanings remain exact. Upstream
  packages do not import v0.23 and gain no consumer or field.
- V0.20 remains an immutable non-executable snapshot with passive
  active/expired derivation and unchanged deletion. V0.23 neither extends its
  validity nor blocks deletion.
- V0.21 remains immutable historical statement evidence with no mutable state,
  deletion, expiry, revocation, execution consumer, or authority. One-time
  v0.23 reservation does not mutate it.
- V0.22 remains validation-only, unsupported, default-disabled, and without a
  runtime/Core intake. Its request, validation, and evidence schemas and
  five-minute freshness remain exact; Core performs no Agent call.
- Existing ExecutionCandidate, approvals, audit, workflow, action, dispatch,
  execution, repository candidate, operational handling, independent approval,
  and interrupted-side-effect no-replay contracts remain unchanged and never
  consume v0.23 records.
- Agent support remains exactly `update-compose-stack` for repository work and
  `restart-service` for operational handling. `install-container` remains
  unsupported and absent from planning, conversion, action, dispatch, worker,
  and execution sets.
- Operational capability remains `restart-service/proxmox/qemu`; Provider
  Intent remains identity-bound Proxmox QEMU `monitoring-policy`; Discovery
  remains GET-only and non-authoritative.
- No Agent/worker invocation, Core-to-Agent dispatch, process/shell/Docker/
  Podman execution, provider or repository read/mutation, guest read/mutation,
  image acquisition, container creation, workflow start, install, deployment,
  rollback, remediation, replay, background work, or authority-bearing event
  is introduced.
- The execution worker remains optional and default-disabled. Backup/restore
  remains explicit operator maintenance and backup v3 is not widened.

## Golden cases, later enablement, and blocked work

The positive golden is synthetic only: one same-owner active v0.20 envelope,
its exact v0.21 intent, and a complete fresh v0.22 request/validation/evidence
pair with `valid_but_unsupported`, empty reasons, and all false authority fields
produce one immutable `recorded` Core record. Exact replay returns it. Any
changed owner, proof, destination, plan, artifact, image, policy, timestamp,
status, reason, authority field, request identity, or fingerprint fails closed
and creates no record or work.

Home Assistant remains the blocked golden. Its required deployment artifact is
absent, so no positive v0.19 candidate, v0.20 record, or v0.21 intent exists;
its realistic persistent/networked artifact is also outside v0.22 policy. It
cannot reach the v0.23 creation boundary, and no deployment artifact is added.

V0.23 enables later design to reference one durable, same-owner, freshness-
bounded, no-replay Core record that cryptographically binds the exact v0.20,
v0.21, and v0.22 values. It does not enable consumption of that record. Still
blocked are execution authorization, fresh execution-time destination/image
proof, trusted Agent evidence transport or signing, Core-to-Agent dispatch,
worker/runtime design, atomic consume semantics, interruption recovery,
side-effect audit, cancellation, image acquisition, persistent/networked
workloads, deployment, rollback, and Home Assistant installation.
