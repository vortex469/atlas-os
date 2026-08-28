# Installation Dispatch Handoff v1 planning contract

Status: **Atlas v0.24 P0 selected; documentation-only contract freeze**.

This document freezes the narrowest non-executing **Installation Dispatch
Handoff** boundary. Core may prepare one immutable, operator-owned dispatch
envelope that binds the exact released v0.20 candidate, v0.21 approval intent,
v0.22 Agent validation evidence, and v0.23 execution-request record. It does
not deliver the envelope, invoke Agent, admit work, create a job, or authorize
execution.

The authority equation for every v0.24 phase is:

`prepared handoff != delivered request != Agent admission != execution`.

## Repository inspection baseline

Planning starts from current `main` at `d51d91e`, after the v0.23.0 release
and merge. V0.20 supplies an owned durable non-executable candidate; v0.21 an
immutable approval statement; v0.22 a validation-only Agent contract and
operator-submitted evidence; and v0.23 an owned, freshness-bounded,
non-executing execution-request record. V0.23 explicitly leaves consumption,
trusted transport, dispatch, and execution approval blocked.

Existing repository execution, operational dispatch, Provider Intent,
workflow, approval, worker, Agent client, and execution surfaces remain
separate and must not consume v0.24 data.

## Exact Core create and dispatch-envelope schemas

The authenticated caller supplies only the closed body below and the existing
hardened idempotency header:

```text
InstallationDispatchHandoffCreateV1 = {
  schema: "installation-dispatch-handoff-create-v1",
  execution_request_id: canonical UUIDv4
}
```

Core resolves every upstream value from its authoritative owned stores. The
caller cannot submit an upstream fingerprint, owner, Agent identity, endpoint,
transport instruction, delivery attempt, credential, command, or authority
field. After complete validation, Core may atomically append only:

```text
InstallationDispatchEnvelopeV1 = {
  schema: "installation-dispatch-envelope-v1",
  dispatch_envelope_id: canonical UUIDv4,
  prepared_at: UtcSecond,
  valid_until: UtcSecond,
  operation: "install-container",
  mode: "handoff-only",
  recipient: {
    service: "atlas-agent",
    intake_contract: "agent-installation-dispatch-intake-v1"
  },
  linkage: InstallationDispatchLinkageV1,
  statement: "core_prepared_non_executing_agent_handoff",
  delivery_authorized: false,
  agent_admission_authorized: false,
  execution_authorized: false,
  mutation_authorized: false,
  replay_allowed: false,
  dispatch_envelope_fingerprint: FingerprintV1
}

InstallationDispatchLinkageV1 = {
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
  artifact_policy_fingerprint: FingerprintV1,
  execution_request_id: canonical UUIDv4,
  execution_request_fingerprint: FingerprintV1
}
```

All objects are closed and reject duplicate or unknown keys. Strings are NFC,
timestamps are UTC whole seconds, UUIDs are canonical lowercase UUIDv4, and
fingerprints retain the released `FingerprintV1` shape. The create body is at
most 1 KiB and the canonical durable envelope at most 32 KiB.

`owner_id` is a mandatory store partition and authorization attribute. It is
not public, but is included in the fingerprint input. The envelope fingerprint
is SHA-256 over UTF-8 `"atlas:installation-dispatch-envelope:v1"`, one NUL
byte, and canonical JSON of `{owner_id, envelope}` excluding
`dispatch_envelope_fingerprint`.

The envelope contains no raw v0.22 request/validation, deployment artifact,
provider payload, address, hostname, endpoint, route, command, environment,
secret, credential, token, arbitrary metadata, desired state, workflow/job
identifier, queue name, lease, retry token, delivery nonce, or replay token.

## Exact linkage and operator ownership

At server-owned `prepared_at`, Core must:

1. load the v0.23 record through its existing owner boundary and validate its
   complete fingerprint and `recorded` lifecycle;
2. load the linked v0.20 record and v0.21 intent through their existing owner
   boundaries, validate every released fingerprint, require the v0.20 record
   to be active, and require exact same-owner subject linkage;
3. require the v0.23 record's complete copied v0.22 request, validation,
   evidence, destination, plan, and artifact-policy fingerprints and preserve
   their transitive binding under the validated v0.23 record fingerprint,
   without reconstructing raw v0.22 values or calling Agent;
4. require v0.22 status `valid_but_unsupported`, empty reason codes, and all
   v0.22 and v0.23 authority fields false; and
5. copy only the closed linkage and calculate the owner-bound envelope
   fingerprint.

P0 does not authorize copying new raw evidence into v0.23 or reconstructing it
from fingerprints. The v0.24 binding to v0.22 is deliberately transitive
through the complete, owner-bound v0.23 fingerprint and its closed linkage.

Foreign-owner access is indistinguishable from absence. Ownership cannot be
delegated, transferred, shared, inferred from a client field, or replaced by
administrator/global enumeration. The same authenticated operator must own
the complete v0.20/v0.21/v0.23 chain and the v0.24 envelope.

## Contract-only Agent intake/admission shape

V0.24 freezes an Agent parser/admission shape only. It has no HTTP route,
listener, Core client, transport registration, application wiring, or runtime
consumer:

```text
AgentInstallationDispatchIntakeV1 = {
  schema: "agent-installation-dispatch-intake-v1",
  envelope: InstallationDispatchEnvelopeV1
}

AgentInstallationDispatchAdmissionV1 = {
  schema: "agent-installation-dispatch-admission-v1",
  dispatch_envelope_id: canonical UUIDv4,
  dispatch_envelope_fingerprint: FingerprintV1,
  evaluated_at: UtcSecond,
  status: "valid_but_not_admitted",
  reason_codes: [],
  delivery_accepted: false,
  execution_admitted: false,
  worker_allowed: false,
  mutation_allowed: false,
  replay_allowed: false,
  dispatch_admission_fingerprint: FingerprintV1
}
```

The sole v0.24 success-like status is `valid_but_not_admitted`. It proves only
that an injected value satisfied the frozen parser and linkage rules. It is
never returned by a live Agent endpoint and is not Core audit evidence of
delivery. The admission fingerprint uses SHA-256 over UTF-8
`"atlas:agent-installation-dispatch-admission:v1"`, one NUL byte, and
canonical JSON excluding `dispatch_admission_fingerprint`.

Unknown status/reason/authority fields fail closed. Rejections are represented
only by the redacted error vocabulary below; no negative durable Agent result
is required. A future live intake release must define authenticated transport,
recipient identity, freshness at receipt, atomic acceptance/consume semantics,
and durable delivery evidence independently; it may not silently activate
this contract-only parser.

## Lifecycle, expiry, idempotency, and no replay

Core derives lifecycle during reads and never stores it:

- `prepared`: `prepared_at <= now < valid_until`; and
- `expired`: `now >= valid_until`.

Both states are non-delivered, non-admitted, and non-authorizing. `expired` is
terminal. There is no renew, refresh, reprepare, supersede, attach, consume,
send, retry, cancel, revoke, dispatch, execute, or state-transition API.
Expiry causes no write, event, callback, probe, cleanup, or background work.

Creation requires `prepared_at` to be no earlier than the v0.23 `recorded_at`,
the v0.20 and v0.23 records to be current, and the complete chain to validate
at that instant. `valid_until` is exactly
`min(candidate_record.valid_until, execution_request.valid_until,
prepared_at + 60 seconds)`. Zero-width validity, unavailable trusted time,
clock rollback, future source timestamps, or ambiguity fails closed.

Idempotency/no-replay rules are exact:

- visible-ASCII idempotency keys are 1–128 bytes and scoped to operator plus
  the create operation;
- exact retry returns the original envelope without re-resolution, time
  extension, parser evaluation, delivery, or other work;
- the store atomically reserves the operator-scoped idempotency key, v0.23
  `execution_request_id`, and envelope fingerprint;
- one v0.23 request can produce at most one v0.24 envelope forever, including
  after expiry, source deletion, restart, timeout, or lost response;
- any reservation reuse with different content fails closed; and
- ambiguous append completion or missing durable reservation evidence returns
  unavailable and never permits reconstruction or creation as new work.

The envelope has no delivery-attempt identity. A later delivery release must
add a separate, single-use, atomically consumed attempt/receipt contract. It
must not treat an exact create retry, `prepared` state, envelope fingerprint,
or contract-only admission result as permission to deliver or execute.

## Store, redaction, and audit evidence

P2 may add one independent, append-only, operator-scoped envelope store with
atomic creation and complete-record validation. Bounds are 16 retained
envelopes per operator and 32 KiB canonical bytes per envelope. There is no
eviction, update, delete, compaction, migration, repair, expiry task, event,
queue, or audit-store bridge. Backup v3 remains closed and is not widened.

The Core envelope is evidence only that Core prepared a non-executing handoff;
it is not evidence of delivery, Agent receipt, admission, or work. API/UI/log
projections may expose only owned IDs, timestamps, derived lifecycle, fixed
statement/authority fields, exact fingerprints, sanitized subject class and
resource ID, immutable image digest, artifact kind, and evidence provenance
`core_prepared_not_delivered`. They must redact owner IDs from other operators,
raw destination identity, provider payload, addresses, paths, credentials,
tokens, commands, environment, deployment content, raw v0.22 content, and
exception serialization.

Errors use only `malformed`, `not_found`, `not_current`,
`ownership_mismatch`, `proof_mismatch`, `evidence_unavailable`,
`replay_conflict`, `quota_exceeded`, and `unavailable`. Logs contain only a
correlation ID, owned envelope ID when available, fingerprints, lifecycle,
and one closed error code. No v0.24 record or log may claim delivery or work.

## Default-disabled API and UI boundaries

P3 may add exactly these authenticated Core routes:

- `POST /api/v1/installation/dispatch-handoffs`;
- `GET /api/v1/installation/dispatch-handoffs`; and
- `GET /api/v1/installation/dispatch-handoffs/{dispatch_envelope_id}`.

POST performs only local owned reads, pure validation, and one append. There
is no PUT, PATCH, DELETE, send, dispatch, admit, execute, retry, consume,
workflow, deploy, rollback, Agent callback, or receipt route. Core must not
import an Agent client, worker, transport, runtime, process, provider,
repository, workflow, or execution adapter, and it makes no network call.

Mission Control may offer one deliberate **Prepare Agent handoff** action from
an owned current v0.23 record, with exact-identity confirmation, plus owned
list/item review. It must display **Prepared only; not sent to Agent; no work
has started**. It must not use queued, dispatched, admitted, ready, executing,
or installed language and has no send, install, execute, retry, cancel,
workflow, deploy, or rollback control/navigation.

The feature remains default-disabled through P5. Before release closure no
production router, application container, Agent route, or Mission Control
navigation exposes it. No environment/configuration switch can enable live
delivery or execution because no such adapter or consumer may exist.

## P0–P5 scope and acceptance

### P0 — Dispatch-handoff contract and threat model — selected

Freeze this exact schema, four-release linkage, ownership, freshness,
lifecycle, idempotency/no-replay, contract-only Agent shape, redaction/audit,
default-disabled API/UI, goldens, threats, and must-not-change contracts. P0
changes planning documentation only.

### P1 — Closed models and pure assembly/admission validation — planned

Implement isolated immutable Core envelope and Agent intake/admission models,
canonical fingerprints, exact linkage, freshness, derived lifecycle, pure
assembly over injected authoritative values, redacted failures, and hostile
input tests. Perform no I/O, persistence, registration, or invocation.

### P2 — Bounded append-only handoff store — planned

Implement only the independent Core store, atomic reservations, idempotency,
quotas, restart durability, reads, and fail-closed corruption/ambiguity. Add no
Agent store, delivery attempt, receipt, event, queue, worker, or consumer.

### P3 — Authenticated preparation-only Core API — planned

Implement create/list/item-read only, resolve the complete owned chain locally,
and lock methods, OpenAPI, redaction, freshness, and dependency isolation. Do
not expose or call the contract-only Agent intake.

### P4 — Mission Control handoff-evidence review — planned

Implement explicit preparation confirmation and immutable review with clear
not-delivered language, ownership isolation, accessibility, and no prohibited
controls, navigation, or requests.

### P5 — Isolation, no-replay, and release closure — planned

Prove exact linkage, lifecycle boundaries, one-envelope-per-request,
concurrency/restart/timeout ambiguity, quotas, corruption, redaction, API/UI
contracts, zero Core/Agent consumers, default-disabled posture, all prior
goldens, capability parity, and full regression gates. P5 does not migrate,
tag, push, publish, deploy, or release automatically.

## Must-not-change contracts for P0–P5

- V0.16–v0.23 schemas, fingerprints, routes, ownership, stores, lifecycle,
  freshness, idempotency, goldens, and meanings remain exact. Upstream packages
  do not import v0.24 or gain fields or consumers.
- V0.20 remains an immutable non-executable snapshot; v0.21 remains an
  immutable historical statement; v0.22 remains validation-only, unsupported,
  and without production intake; v0.23 remains record-only with all authority
  fields false. V0.24 mutates none of them.
- Existing ExecutionCandidate, approvals, execution audit, workflow, action,
  operational dispatch, repository execution, worker, Provider Intent, and
  interrupted-side-effect no-replay contracts remain unchanged and do not
  consume v0.24 data.
- Agent support remains exactly `update-compose-stack` and
  `restart-service`; `install-container` remains unsupported and absent from
  planning, conversion, action, dispatch, worker, and execution sets.
- Operational capability remains `restart-service/proxmox/qemu`; Provider
  Intent remains Proxmox QEMU `monitoring-policy`; Discovery remains GET-only.
- No live Core-to-Agent invocation, worker dispatch, Docker/Podman/shell/
  process execution, provider mutation, repository read/mutation, guest
  read/mutation, workflow start, installation, deployment, rollback, image
  acquisition, network delivery, background work, or authority event exists.
- The optional execution worker stays default-disabled. Backup/restore remains
  explicit operator maintenance and backup v3 is not widened.

## Threats, golden cases, later enablement, and blocked work

The closed threat model covers cross-operator substitution, stale or corrupt
upstream proof, v0.22 evidence being promoted to attestation, confused-deputy
recipient changes, endpoint/credential injection, envelope tampering,
preparation being mistaken for delivery, parser validation being mistaken for
admission, replay after expiry or ambiguous persistence, duplicate delivery
identity smuggling, secret/error leakage, and accidental feature activation.

The positive golden is synthetic only: one same-owner current v0.20/v0.21/
v0.22/v0.23 chain produces one `prepared` envelope with five false authority
fields. Exact retry returns it without work. Any changed owner, ID,
fingerprint, proof, timestamp, state, status, reason, authority field, or
recipient contract fails closed and creates no envelope or side effect.

Home Assistant remains the blocked golden. It still cannot reach the v0.20
boundary and its realistic artifact remains outside v0.22 policy. No Home
Assistant deployment artifact or exception is added.

V0.24 enables later design to use one compact, owner-bound, freshness-bounded,
single-preparation envelope and one frozen Agent parser/admission vocabulary as
inputs to a separately authorized transport and consumption release. Still
blocked are independent execution approval, trusted mutual Core/Agent
authentication, live intake, delivery attempts and receipts, atomic consume
and no-redelivery barriers, execution-time destination/image proof, worker and
runtime behavior, interruption recovery, side-effect audit, cancellation,
image acquisition, persistent/networked workloads, installation, deployment,
rollback, and Home Assistant installation.
