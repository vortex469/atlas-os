# Controlled Worker Queue Claim/Lease/Acknowledgement Prerequisite v1 planning contract

Status: **Atlas v0.50 P0-P5 closed controlled worker queue claim/lease/acknowledgement prerequisite contract**.

This document freezes the repository-supported v0.50 boundary after inspection
of the completed merged v0.49 baseline. The v0.49 baseline can record
controlled worker queue claim admission evidence over one exact active
same-owner v0.48 worker-binding activation evidence record. It still does not
define queue claim, queue lease, queue acknowledgement, worker activation
runtime, worker store contact, worker runtime contact, worker-start admission,
worker start, Agent invocation, execution authorization, or execution start.

Because those prerequisites are not present and proven, v0.50 cannot safely
select controlled worker invocation, worker start, worker-start admission, or
execution-start admission. The narrowest repository-supported next boundary is
therefore **Controlled Worker Queue Claim/Lease/Acknowledgement Prerequisite**:
a documentation-only freeze of the missing queue claim, lease, and
acknowledgement authority boundary that any later implementation must satisfy
before worker-start admission or execution-start admission can be considered.

This contract does not add a queue adapter, queue polling consumer, queue
claim, queue lease, queue acknowledgement, worker activation runtime, worker
store contact, worker runtime contact, worker-start admission, worker start,
Agent invocation, execution authorization, execution start, installation,
mutation, deployment, rollback, publication, or effect consumer.

## Repository Inspection Baseline

The completed v0.49 contract is
[Controlled Worker Queue Claim Admission v1](controlled-worker-queue-claim-admission-v1.md).
It records only `controlled_worker_queue_claim_admission_recorded` over one
exact active same-owner v0.48 activation-evidence record and keeps these
downstream blockers:

- `queue_claim_not_defined`
- `queue_lease_not_defined`
- `queue_ack_not_defined`
- `worker_activation_runtime_not_defined`
- `store_contact_not_defined`
- `runtime_contact_not_defined`
- `worker_start_admission_not_defined`
- `worker_start_not_defined`
- `agent_invocation_not_defined`
- `execution_start_boundary_not_defined`

The v0.49 implementation and release-closure tests prove that Core service,
store, route, and Mission Control surfaces remain default-off evidence
surfaces only. They also prove that Agent and the packaged execution worker
have no consumer for the v0.49 admission marker. No repository-supported
production queue polling consumer, claim primitive, lease primitive,
acknowledgement primitive, worker store client, worker runtime client,
worker-start admission path, worker-start path, Agent invocation path, or
execution-start boundary exists in this baseline.

## Frozen Boundary

V0.50 freezes only this prerequisite question:

```text
What must a later controlled queue claim/lease/acknowledgement authority
define and prove before any worker-start admission or execution-start
admission boundary may depend on it?
```

The strongest v0.50 state is documentation-only prerequisite closure. It does
not create a runtime record, route, schema, permission, queue operation, worker
operation, Agent operation, execution operation, deployment operation, or
release operation.

Any later controlled queue claim/lease/acknowledgement implementation must
separately define, implement, and prove all of the following before worker
start or execution-start admission can be selected:

- one exact active same-owner v0.49
  `controlled-worker-queue-claim-admission-v1` record as the only direct input;
- exact inherited v0.48-v0.20 lineage, ownership, lifecycle, freshness/expiry,
  fingerprints, and byte-exact inherited limits;
- a bounded queue identity and item identity derived only from the inherited
  admitted lineage, with no caller-supplied queue selector or payload;
- an explicitly constructed default-off queue adapter with no production
  construction unless a later release deliberately activates it;
- reservation-before-effect semantics for any future claim attempt;
- permanent idempotency and subject no-replay across claim, lease, and
  acknowledgement attempts;
- terminal ambiguity handling for indeterminate adapter outcomes;
- bounded, append-only, redacted, secret-free persistence and readback;
- lease token and acknowledgement handle treatment that prevents raw secret
  storage, raw secret rendering, replay bypass, or cross-owner reuse;
- operator-scoped API and UI isolation with no standalone action surface unless
  a later release explicitly defines it;
- no Home Assistant or other workload-specific authority exception;
- Agent and execution-worker zero-consumer behavior until a later release
  independently defines a worker-start or execution-start consumer.

## Authority Equations

V0.50 is governed by these fixed equations:

```text
v0.50_prerequisite_frozen != queue_claimed
v0.50_prerequisite_frozen != queue_leased
v0.50_prerequisite_frozen != queue_acknowledged
v0.50_prerequisite_frozen != worker_start_admitted
v0.50_prerequisite_frozen != worker_started
v0.50_prerequisite_frozen != agent_invoked
v0.50_prerequisite_frozen != execution_started
controlled_worker_queue_claim_admission_recorded != queue_claimed
queue_claimed != queue_leased != queue_acknowledged
queue_acknowledged != worker_start_admitted
worker_start_admitted != worker_started != execution_started
```

All downstream authority remains fixed false:

- caller-supplied credentials, endpoints, commands, queue selectors, claim
  tokens, lease tokens, acknowledgement handles, and payloads;
- queue polling, claim, lease, acknowledgement, consume/remove, requeue,
  retry/resend, and mutation;
- worker store contact, worker runtime contact, worker contact,
  worker-start admission, worker start, and worker invocation;
- Agent invocation;
- execution authorization, execution start, process execution, shell
  execution, scheduler/workflow start, and dispatch;
- provider, repository, or in-guest mutation;
- installation, deployment, rollback, replay bypass, artifact publication,
  tag, push, or release publication.

## Required Lineage

Any later implementation depending on this prerequisite must accept exactly
one active same-owner v0.49 `controlled-worker-queue-claim-admission-v1`
record and its status fingerprint. That v0.49 record remains the only accepted
source for the exact v0.48 activation evidence, v0.47 activation preflight,
v0.46 one-shot dequeue worker binding, v0.45 one-shot controlled dequeue
receipt, v0.40 worker intake subject, worker identity, abstract worker intake
reference, abstract queue intake reference, inert queue-item reference, and
byte-exact inherited limits.

Older evidence may be accepted only through the already-validated v0.49
controlled worker queue claim admission lineage unless a later phase
explicitly requires read-only recomputation for fingerprint verification. Any
owner, candidate, lifecycle, freshness, expiry, fingerprint, worker subject,
queue item, lineage, or inherited-limit mismatch must fail closed.

## Defaults and Operator Control

P0 freezes the planning boundary only. It requires no runtime model, service,
store, migration, setting, permission, route, OpenAPI operation, UI code,
queue library, broker integration, serializer, worker client, credential,
endpoint, background task, Agent change, execution-worker change, artifact,
tag, push, publication, deployment, rollback, or change to
`compose.execution-smoke.override.yaml`.

Any later phase must remain explicitly constructed and default-off in
production composition. It must preserve exact lineage and ownership,
permanent idempotency and subject no-replay, bounded append-only persistence,
redacted errors, secret-free storage and rendering, guarded candidate-scoped
API access, Mission Control read-only nesting until separately authorized, and
Agent/execution-worker zero-consumer behavior.

Mission Control may later display prerequisite evidence only as nested
read-only installation workflow evidence. It must not add a standalone route,
navigation entry, polling transport, queue selector, claim control, lease
control, acknowledgement control, worker selector, endpoint input, credential
input, payload editor, command editor, worker-start control, execute control,
deploy/rollback control, browser storage authority, or raw secret rendering
unless a later release explicitly freezes and implements that authority.

## Must Not Change

V0.50 does not modify any prior authority boundary. The completed v0.20-v0.49
lineage, ownership, limits, freshness, permanent no-replay, redaction,
ambiguity handling, default-off construction, API/UI isolation, Home Assistant
blocking, and Agent/execution-worker zero-consumer contracts remain
authoritative.

Controlled worker invocation, worker-start admission, worker start, and
execution-start admission may be selected only after separately released
boundaries define and prove queue claim, lease, acknowledgement, binding,
worker activation runtime, worker store/runtime contact, and worker-start
prerequisites, or deliberately prove why any omitted prerequisite is not
required for that specific authority. Until then, unsupported architectures
must fail closed with the explicit blockers listed in this document.

## P0-P5 Closure

P0 froze the narrow prerequisite boundary. P1 added closed immutable Core
models and pure validation. P2 added explicitly constructed default-off
service/store persistence with permanent idempotency, subject no-replay,
bounded/redacted persistence, restart-safe readback, and terminal
indeterminate reservations. P3 added only the guarded candidate-scoped Core
create/list/get API. P4 kept Mission Control nested and read-only under the
controlled worker queue claim admission evidence view. P5 locks release
isolation and adds focused tests plus release documentation only.

The closed v0.50 boundary advances only `v0.50_prerequisite_frozen`. It does
not create queue claim, queue lease, queue acknowledgement, worker activation
runtime, worker store contact, worker runtime contact, worker-start admission,
worker start, Agent invocation, execution authorization, execution start,
installation, mutation, deployment, rollback, publication, release, or effect
consumer authority.
