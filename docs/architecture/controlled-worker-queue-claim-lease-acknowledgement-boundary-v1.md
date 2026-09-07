# Controlled Worker Queue Claim/Lease/Acknowledgement Boundary v1 contract

Status: **Atlas v0.52 P0-P5 closed controlled worker queue claim/lease/acknowledgement receipt evidence contract**.

This document specifies the completed v0.52 evidence boundary after
inspection of the released v0.51.0 baseline at
`8d1ece090b14e6fc2d06332b14b03559b252555d` (`atlas-v0.51.0`). The v0.51
baseline can record bounded admission evidence over one exact active
same-owner v0.50 controlled worker queue claim/lease/acknowledgement
prerequisite record. It still does not define a queue adapter, queue claim,
queue lease, queue acknowledgement, worker activation runtime, worker store
contact, worker runtime contact, worker-start admission, worker start, Agent
invocation, execution authorization, or execution start.

The completed boundary is Core-owned, explicitly constructed, default-off,
single-subject queue receipt evidence over one exact active same-owner v0.51
admission record and its inherited inert queue-item lineage.
Core reads injected, already-observed redacted adapter receipt
facts. It has no queue adapter client and performs no claim, lease, or
acknowledgement effect. The reader's reservation-before-effect assertion is
validated evidence, not an effect performed or authorized by this service.

P0 is documentation-only and adds no runtime architecture. P1-P5 are complete
in the repository; this is not a tag, publication, deployment, or production
enablement claim. The original P0 selection considered an injected queue adapter;
the final implementation is narrower: an injected owner-scoped receipt reader.
No worker activation runtime, worker store/runtime contact, worker-start
admission, worker start, Agent invocation, execution start, artifact publication,
tag push, release publication, deployment, rollback, or effect consumer is added.
`compose.execution-smoke.override.yaml` remains absent and unchanged.

## Repository Inspection Baseline

The completed v0.51 contract is [Controlled Worker Queue
Claim/Lease/Acknowledgement Admission v1](controlled-worker-queue-claim-lease-acknowledgement-admission-v1.md).
It records only
`controlled_worker_queue_claim_lease_acknowledgement_admission_recorded` over
one exact active same-owner v0.50 prerequisite record and carries these
required downstream blockers:

- `queue_adapter_not_defined`
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

The v0.51 implementation and release-closure tests prove that Core service,
store, route, and Mission Control surfaces remain default-off evidence
surfaces only. They also prove that Agent and the packaged execution worker
have no consumer for the v0.51 admission marker. No repository-supported
production queue adapter, queue polling consumer, claim primitive, lease
primitive, acknowledgement primitive, worker store client, worker runtime
client, worker-start admission path, worker-start path, Agent invocation
path, or execution-start boundary exists in this baseline.

## Frozen Boundary

V0.52 answers only this evidence question:

```text
Given one exact active same-owner v0.51 controlled worker queue
claim/lease/acknowledgement admission record and its inherited inert queue
item lineage, may Core record one bounded, already-observed controlled queue
claim, lease, and acknowledgement receipt supplied by an owner-scoped reader
for that exact subject?
```

The strongest recorded state allowed by this contract is:

```text
controlled_worker_queue_claim_lease_acknowledgement_recorded
```

That state is queue receipt evidence only. It records validated reader assertions
that the exact admitted queue subject was claimed, leased, and acknowledged. Core does not independently contact the
queue to verify or repeat those effects. Its own reservation precedes receipt
append and permanently prevents another append attempt for that subject. It does
not make the queue subject executable and must carry these remaining blockers:

- `worker_activation_runtime_not_defined`
- `store_contact_not_defined`
- `runtime_contact_not_defined`
- `worker_start_admission_not_defined`
- `worker_start_not_defined`
- `agent_invocation_not_defined`
- `execution_start_boundary_not_defined`

## Authority Equations

V0.52 is governed by these fixed equations:

```text
controlled_worker_queue_claim_lease_acknowledgement_recorded != worker_activation_runtime_defined
controlled_worker_queue_claim_lease_acknowledgement_recorded != store_contact_defined
controlled_worker_queue_claim_lease_acknowledgement_recorded != runtime_contact_defined
controlled_worker_queue_claim_lease_acknowledgement_recorded != worker_start_admitted
controlled_worker_queue_claim_lease_acknowledgement_recorded != worker_started
controlled_worker_queue_claim_lease_acknowledgement_recorded != agent_invoked
controlled_worker_queue_claim_lease_acknowledgement_recorded != execution_started
controlled_worker_queue_claim_lease_acknowledgement_admission_recorded != queue_claimed
queue_claimed != worker_start_admitted
queue_leased != worker_started
queue_acknowledged != execution_started
worker_start_admitted != worker_started != execution_started
```

All downstream authority remains fixed false/default off:

- caller-supplied credentials, endpoints, commands, queue selectors, payloads,
  payload schemas, claim tokens, lease tokens, and acknowledgement handles;
- autonomous queue polling, work discovery, consume/remove of non-subject
  items, requeue, retry/resend, replacement, mutation, or replay bypass;
- worker activation runtime, worker store contact, worker runtime contact,
  worker contact, worker-start admission, worker start, and worker invocation;
- Agent invocation;
- execution authorization, execution start, process execution, shell
  execution, scheduler/workflow execution, scheduler/workflow start, and
  dispatch;
- provider, repository, or in-guest mutation;
- installation, deployment, rollback, artifact publication, tag push, or
  release publication.

## Required Lineage

The v0.52 implementation accepts exactly one active same-owner v0.51
`controlled-worker-queue-claim-lease-acknowledgement-admission-v1` record and
its status fingerprint as the only direct prerequisite input. The v0.51 record
remains the only accepted source for the exact v0.50 prerequisite, v0.49
controlled worker queue claim admission, v0.48 worker-binding activation
evidence, v0.47 activation preflight, v0.46 one-shot dequeue worker binding,
v0.45 one-shot controlled dequeue receipt, v0.40 worker intake subject, worker
identity, abstract worker intake reference, abstract queue intake reference,
inert queue-item reference, and byte-exact inherited limits.

The injected adapter receipt reader receives only owner, candidate, admission
ID, adapter identity, queue subject, and expected claim/lease/acknowledgement
fingerprints. It returns bounded, redacted, secret-free receipt facts. Any
owner, candidate, lifecycle, freshness, expiry, fingerprint, worker subject,
queue item, lineage, inherited-limit, adapter identity, reservation, claim,
lease, acknowledgement, or ambiguity mismatch fails closed.

## Durable and API semantics

The service revalidates the exact prerequisite under the SQLite write lock
before reservation and immediately before receipt append. Failure after
reservation is terminal and indeterminate. Exact duplicates return historical
evidence, including expired evidence, without reader calls or another append.
Reservations survive restart and expiry; there is no retry, eviction, repair,
release, replacement, or replay bypass API.

Limits may only be lowered: 16 reservations per owner, 256 globally, 192 KiB per
serialized model, one terminal audit per reservation, and a 256 MiB main database
page limit. FULL synchronous transactions validate schema and bounded state on
every connection. Corruption closes reads and writes, including damaged lookup
indexes. Capacity exhaustion rejects new subjects without evicting reservations.
The database page limit is not a total filesystem or temporary journal quota.

The candidate-record API suffix is
`/{candidate_record_id}/controlled-worker-queue-claim-lease-acknowledgements`.
POST records evidence; GET lists owned receipts; GET `/{admission_id}` reads
one receipt under its exact candidate. Dedicated `.evaluate`/`.read` permissions
under `installation.execution.controlled_worker_queue_claim_lease_acknowledgement`
apply. POST also requires trusted origin, CSRF, strict bounded JSON, and a bounded
Idempotency-Key. Caller body fields cannot select the authenticated owner.
An absent app-state service returns redacted 503; disabled creation returns 409.
Production startup never constructs the service or readers.

Mission Control uses guarded GET only, nested under the exact v0.51 admission.
It has no create control, independent route, navigation, polling, browser storage,
raw selector/token/handle rendering, or later authority controls.

## P1-P5 Progression

- P1 - closed immutable Core contract models and pure fail-closed validation
  only, including deterministic fingerprints, exact v0.51-v0.20 lineage,
  fixed remaining blockers, redaction, fixed-false downstream authority, and
  rejection of caller-supplied queue selectors, credentials, endpoints,
  payloads, claim tokens, lease tokens, acknowledgement handles, commands,
  worker contact, Agent invocation, and execution authority.
  Implemented in Core as validation-only models and a deterministic evaluator
  over exactly one injected active same-owner v0.51 admission record/status
  pair plus injected bounded redacted adapter receipt facts for the exact
  inherited queue subject. P1 fails closed on malformed lineage, wrong
  ownership, stale or expired evidence, wrong fingerprints, inherited-limit
  drift, replay, corruption, ambiguity, malformed authority state, and unknown
  fields, while adding no persistence, route, Mission Control UI, worker
  runtime effect, Agent invocation, execution start, deployment, rollback, or
  publication authority.
- P2 - explicitly constructed append-only Core receipt service/store with an
  injected owner-scoped v0.51 admission reader and one adapter receipt reader,
  reservation-before-effect, permanent idempotency and subject no-replay,
  bounded/redacted secret-free persistence, restart-safe readback, quotas,
  corruption closure, and terminal indeterminate post-reservation outcomes.
- P3 - guarded default-off owner-scoped Core list/create/get API under
  candidate records with dedicated operator permissions, CSRF/origin checks,
  strict JSON and idempotency bounds, redacted errors, OpenAPI registration,
  and no production construction unless an explicit app-state service is
  supplied.
- P4 - nested Mission Control read-only presentation only under the existing
  v0.51 admission evidence chain, using guarded read APIs only and adding no
  standalone route, navigation entry, polling transport, browser storage
  authority, selector, token or handle rendering, worker-start control, Agent
  action, execution control, deployment control, rollback control, or publish
  control.
- P5 - release isolation and regression closure proving exact lineage,
  ownership, freshness/expiry, fingerprints, inherited limits,
  reservation-before-effect, permanent no-replay, bounded/redacted
  persistence, fixed-false downstream authority, default-off production
  construction, API/UI isolation, Home Assistant blocking,
  Agent/execution-worker zero-consumer behavior, absence of
  `compose.execution-smoke.override.yaml`, and release evidence.

## Must Not Change

V0.52 does not modify any prior authority boundary. The completed
v0.20-v0.51 lineage, ownership, limits, freshness, permanent no-replay,
redaction, ambiguity handling, default-off construction, API/UI isolation,
Home Assistant blocking, and Agent/execution-worker zero-consumer contracts
remain authoritative.

V0.52 does not authorize worker activation runtime, worker store contact,
worker runtime contact, worker-start admission, worker start, Agent
invocation, execution authorization, execution start, scheduler/workflow
execution, process execution, installation, mutation, deployment, rollback,
artifact publication, tag push, release publication, or any effect consumer.
Those boundaries may be selected only by later releases that independently
define and prove their own prerequisites and fail-closed constraints.
