# Worker Binding Activation Preflight v1 planning contract

Status: **Atlas v0.47 P0 documentation-only selected boundary**.

This document records the repository-supported v0.47 P0 decision after
inspection of the completed merged v0.46 baseline. The narrowest next boundary
is a Core-local **Worker Binding Activation Preflight** over one exact v0.46
one-shot dequeue worker binding record. It may only answer whether that binding
evidence is eligible to be considered by a later, separately released
activation contract. It does not activate a binding, contact a worker store,
contact a worker runtime, claim work, lease work, acknowledge work, start a
worker, invoke Agent, authorize execution, or start execution.

The authority equations for v0.47 P0 are:

```text
activation_preflight_eligible != binding_activated
binding_activated != worker_contact_authorized
worker_contact_authorized != worker_start_authorized
worker_start_authorized != execution_start_authorized
```

and:

```text
worker_binding_preflight_evidence != queue_claim != queue_lease != queue_ack
```

## Repository Inspection Baseline

Planning starts from the completed repository-supported v0.46 baseline. The
current v0.46 contract records one successful same-owner v0.45 one-shot
controlled dequeue receipt bound to one exact same-owner v0.40 worker intake
subject. Its strongest state is
`one_shot_dequeue_worker_binding_recorded`, but it remains
`readiness_gated` behind `store_contact_not_defined`,
`runtime_contact_not_defined`, `worker_start_not_defined`, and
`execution_start_boundary_not_defined`.

The v0.46 implementation is append-only, explicitly constructed, default-off,
and absent from production startup composition. It reads only owner-scoped v0.45
dequeue evidence and v0.40 worker intake evidence through injected readers,
then records bounded binding evidence with permanent idempotency and subject
no-replay. The route and Mission Control surfaces are read/record evidence
surfaces only.

The repository does not provide a supported production queue polling consumer,
claim operation, lease operation, acknowledgement operation, worker store
client, worker runtime client, worker start path, Agent invocation path, or
execution-start boundary for this installation chain. Therefore v0.47 P0 does
not select claim, lease, acknowledgement, worker store contact, worker runtime
contact, worker start, Agent invocation, or execution start as the next
authority boundary.

## Selected Boundary

V0.47 selects only a future preflight/admission question:

```text
Given one active same-owner v0.46 one-shot dequeue worker binding record,
is the exact binding evidence eligible to be considered by a later,
separately released worker-binding activation contract?
```

The strongest future state allowed by this planning contract is:

```text
worker_binding_activation_preflight_recorded
```

That state is evidence only and must remain blocked by:

- `worker_binding_activation_not_defined`
- `store_contact_not_defined`
- `runtime_contact_not_defined`
- `queue_claim_not_defined`
- `queue_lease_not_defined`
- `queue_ack_not_defined`
- `worker_start_not_defined`
- `agent_invocation_not_defined`
- `execution_start_boundary_not_defined`

The preflight may not consume a queue item. It may not mutate or replace the
v0.42 inert queue item, alter the v0.45 dequeue receipt, alter the v0.46 worker
binding, contact a worker, create payload bytes, select a command, load
credentials, or grant new downstream authority.

## Required Lineage

Any later implementation of this boundary must require exactly one active
same-owner v0.46 `one-shot-dequeue-worker-binding-v1` record and its status
fingerprint. The v0.46 record remains the only accepted source for the exact
v0.45 dequeue receipt, v0.40 worker intake subject, worker identity, abstract
worker intake reference, abstract queue intake reference, inert queue-item
reference, and byte-exact inherited limits.

Older v0.45/v0.44/v0.43/v0.42 and v0.40 values may be accepted only through the
already-validated v0.46 binding lineage unless a later phase explicitly
requires a read-only recomputation for fingerprint verification. Any owner,
candidate, lifecycle, freshness, fingerprint, worker-subject, queue-item,
lineage, or inherited-limit mismatch must fail closed.

## Authority Limits

All downstream authority remains fixed false in v0.47 P0:

- caller-supplied credentials, endpoints, commands, and payloads;
- queue polling, claim, lease, acknowledgement, consume/remove, and mutation;
- worker store contact, worker runtime contact, worker start, and worker
  invocation;
- Agent invocation;
- execution authorization, execution start, process execution, shell
  execution, scheduler/workflow start, dispatch, retry, and resend;
- provider, repository, or in-guest mutation;
- installation, deployment, rollback, replay bypass, artifact publication,
  tag, push, or release publication.

Worker start, Agent invocation, and execution remain undefined. Claim, lease,
and acknowledgement remain undefined because the repository does not yet expose
the queue-consumption primitives needed to support them safely.

## Persistence, Redaction, and Defaults

P0 changes planning documents only. It adds no runtime model, service, store,
migration, setting, permission, route, OpenAPI operation, UI code, queue
library, worker client, runtime client, credential, endpoint, payload schema,
background task, Agent change, execution-worker change, artifact, tag, push,
publication, deployment, rollback, or change to
`compose.execution-smoke.override.yaml`.

Any later phase must preserve v0.46 permanent idempotency and subject
no-replay, bounded append-only persistence, redacted failure behavior,
secret-free storage and rendering, explicit construction, default-off
activation, API/UI isolation, Home Assistant blocking, and Agent/
execution-worker zero-consumer contracts.

## Must Not Change

V0.47 P0 does not modify any prior authority boundary. The completed v0.20-v0.46
lineage, ownership, limits, freshness, no-replay, redaction, and default-off
contracts remain authoritative. Future worker-binding activation, worker store
contact, runtime contact, worker start, Agent invocation, queue claim/lease/
acknowledgement, or execution-start work must be separately planned,
implemented, and validated as its own authority boundary.
