# Controlled Worker Queue Claim/Lease/Acknowledgement Boundary v1 planning contract

Status: **Atlas v0.52 P0 selected controlled worker queue claim/lease/acknowledgement boundary**.

This document freezes the repository-supported v0.52 P0 boundary after
inspection of the released v0.51.0 baseline at
`8d1ece090b14e6fc2d06332b14b03559b252555d` (`atlas-v0.51.0`). The v0.51
baseline can record bounded admission evidence over one exact active
same-owner v0.50 controlled worker queue claim/lease/acknowledgement
prerequisite record. It still does not define a queue adapter, queue claim,
queue lease, queue acknowledgement, worker activation runtime, worker store
contact, worker runtime contact, worker-start admission, worker start, Agent
invocation, execution authorization, or execution start.

The narrowest repository-supported next boundary is therefore **Controlled
Worker Queue Claim/Lease/Acknowledgement Boundary**: a Core-owned,
explicitly constructed, default-off, single-subject queue receipt boundary
over one exact active same-owner v0.51 admission record. Its purpose is to
define and prove the minimum controlled queue adapter, claim, lease, and
acknowledgement semantics needed before any later worker-start admission may
be considered. It is not worker activation runtime, worker store contact,
worker runtime contact, worker-start admission, worker start, Agent
invocation, execution authorization, execution start, publication, deployment,
rollback, or an effect consumer.

P0 is documentation-only and adds no runtime architecture. P1-P5 may add only
the closed Core contract, explicitly constructed default-off receipt
service/store with an injected queue adapter, guarded owner-scoped Core API,
nested read-only Mission Control presentation, and release-closure
regressions required by this contract. V0.52 must not add production service
construction, queue polling, autonomous work discovery, worker activation
runtime, worker store/runtime contact, worker-start admission, worker start,
Agent change, execution-worker change, execution start, artifact publication,
tag push, release publication, deployment, rollback, or a change to
`compose.execution-smoke.override.yaml`.

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

V0.52 P0 freezes only this authority question:

```text
Given one exact active same-owner v0.51 controlled worker queue
claim/lease/acknowledgement admission record and its inherited inert queue
item lineage, may Core perform at most one explicitly authorized controlled
queue claim, bounded lease observation, and terminal acknowledgement receipt
against an injected queue adapter for that exact subject?
```

The strongest future state allowed by this planning contract is:

```text
controlled_worker_queue_claim_lease_acknowledgement_recorded
```

That state is queue receipt evidence only. It may prove that the exact
admitted queue subject was claimed, leased, and acknowledged through the
injected adapter under reservation-before-effect and permanent no-replay
rules. It does not make the queue subject executable and must carry these
remaining blockers:

- `worker_activation_runtime_not_defined`
- `store_contact_not_defined`
- `runtime_contact_not_defined`
- `worker_start_admission_not_defined`
- `worker_start_not_defined`
- `agent_invocation_not_defined`
- `execution_start_boundary_not_defined`

## Authority Equations

V0.52 P0 is governed by these fixed equations:

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

Any v0.52 implementation must accept exactly one active same-owner v0.51
`controlled-worker-queue-claim-lease-acknowledgement-admission-v1` record and
its status fingerprint as the only direct prerequisite input. The v0.51 record
remains the only accepted source for the exact v0.50 prerequisite, v0.49
controlled worker queue claim admission, v0.48 worker-binding activation
evidence, v0.47 activation preflight, v0.46 one-shot dequeue worker binding,
v0.45 one-shot controlled dequeue receipt, v0.40 worker intake subject, worker
identity, abstract worker intake reference, abstract queue intake reference,
inert queue-item reference, and byte-exact inherited limits.

The injected queue adapter may receive only a bounded subject derived from the
validated inherited queue-item lineage and may return only bounded,
redacted, secret-free claim, lease, acknowledgement, and ambiguity evidence.
Any owner, candidate, lifecycle, freshness, expiry, fingerprint, worker
subject, queue item, lineage, inherited-limit, adapter identity, reservation,
claim, lease, acknowledgement, or ambiguity mismatch fails closed.

## P1-P5 Progression

- P1 - closed immutable Core contract models and pure fail-closed validation
  only, including deterministic fingerprints, exact v0.51-v0.20 lineage,
  fixed remaining blockers, redaction, fixed-false downstream authority, and
  rejection of caller-supplied queue selectors, credentials, endpoints,
  payloads, claim tokens, lease tokens, acknowledgement handles, commands,
  worker contact, Agent invocation, and execution authority.
- P2 - explicitly constructed append-only Core receipt service/store with an
  injected owner-scoped v0.51 admission reader and one injected queue adapter,
  reservation-before-effect, permanent idempotency and subject no-replay,
  bounded/redacted secret-free persistence, restart-safe readback, quotas,
  corruption closure, and terminal indeterminate adapter or append outcomes.
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
