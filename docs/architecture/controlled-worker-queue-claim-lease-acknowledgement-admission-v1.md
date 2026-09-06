# Controlled Worker Queue Claim/Lease/Acknowledgement Admission v1 planning contract

Status: **Atlas v0.51 P0-P5 closed controlled worker queue claim/lease/acknowledgement admission contract**.

This document freezes the repository-supported v0.51 P0 boundary after
inspection of the completed merged v0.50 baseline. The v0.50 baseline can
record bounded controlled worker queue claim/lease/acknowledgement
prerequisite evidence over one active same-owner v0.49 controlled worker queue
claim admission record. It still does not define a queue adapter, queue claim,
queue lease, queue acknowledgement, worker activation runtime, worker store
contact, worker runtime contact, worker-start admission, worker start, Agent
invocation, execution authorization, or execution start.

Because queue claim, lease, acknowledgement, worker contact, worker-start, and
execution-start effects remain unsupported, v0.51 cannot safely select
controlled worker invocation, worker-start admission, worker start,
execution-start admission, or execution. The narrowest repository-supported
next authority boundary is therefore **Controlled Worker Queue
Claim/Lease/Acknowledgement Admission Evidence**: a documentation-only P0
freeze stating that one exact active same-owner v0.50 prerequisite record may
be admitted for later, separately released queue claim/lease/acknowledgement
implementation consideration. It is not a queue claim, lease,
acknowledgement, worker-start admission, worker start, Agent invocation,
execution authorization, execution start, publication, deployment, rollback,
or effect consumer.

P0 does not implement runtime authority. P1-P5 add only the closed Core
contract, explicitly constructed default-off evidence service/store, guarded
owner-scoped evidence API, nested read-only Mission Control presentation, and
release-closure regressions required by this contract. V0.51 still adds no
production service construction, queue adapter, broker integration,
serializer, worker client, credential, endpoint, background task, Agent
change, execution-worker change, artifact, tag, push, publication, deployment,
rollback, or change to `compose.execution-smoke.override.yaml`.

## Completed Implementation

V0.51 P0-P5 are complete. The implementation records only bounded admission
evidence that one exact active same-owner v0.50 prerequisite record is admitted
for separately released controlled queue claim/lease/acknowledgement
implementation consideration. The only successful eligibility state is:

```text
controlled_worker_queue_claim_lease_acknowledgement_admission_recorded
```

The Core contract accepts only injected v0.50 prerequisite record/status
facts, recomputes and verifies the v0.50 prerequisite record fingerprint,
v0.50 prerequisite status fingerprint, v0.49 admission record/status
fingerprints, binding subject fingerprint, worker subject fingerprint, queue
item reference fingerprint, and inherited limits fingerprint, and fails closed
on ownership, linkage, lifecycle, freshness, expiry, ambiguity, Home
Assistant, caller-supplied material, or unsupported authority drift.

The evidence service and store are not constructed by production startup. When
explicitly constructed for the guarded API, the service is default-off and
uses only an injected owner-scoped v0.50 prerequisite reader. The SQLite store
is append-only for successful records, reserves idempotency and subject
identity before append, preserves permanent no-replay across restart, bounds
record size and per-operator count, stores only redacted/fingerprinted
evidence, and treats ambiguous append outcomes as terminal indeterminate
reservations.

Mission Control displays v0.51 admission evidence only as nested read-only
installation workflow evidence below v0.49 claim admission and v0.50
prerequisite evidence. It uses guarded Core read APIs only and provides no
standalone route, navigation entry, polling transport, browser storage
authority, form, selector, claim/lease/acknowledgement control, worker-start
control, Agent/workflow action, execution control, deployment control, or raw
secret rendering.

## Repository Inspection Baseline

The completed v0.50 contract is [Controlled Worker Queue
Claim/Lease/Acknowledgement Prerequisite v1](controlled-worker-queue-claim-lease-acknowledgement-prerequisite-v1.md).
It records only `v0.50_prerequisite_frozen` over one active same-owner v0.49
controlled worker queue claim admission record and carries these required
downstream blockers:

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

The v0.50 implementation and release-closure tests prove that Core service,
store, route, and Mission Control surfaces remain default-off evidence
surfaces only. They also prove that Agent and the packaged execution worker
have no consumer for the v0.50 prerequisite marker. No repository-supported
production queue adapter, queue polling consumer, claim primitive, lease
primitive, acknowledgement primitive, worker store client, worker runtime
client, worker-start admission path, worker-start path, Agent invocation path,
or execution-start boundary exists in this baseline.

## Frozen Boundary

V0.51 P0 freezes only this admission question:

```text
Given one exact active same-owner v0.50 controlled worker queue
claim/lease/acknowledgement prerequisite record, may Core later record that
the prerequisite evidence is admitted for a separately released controlled
queue claim/lease/acknowledgement implementation?
```

The strongest future state allowed by this planning contract is:

```text
controlled_worker_queue_claim_lease_acknowledgement_admission_recorded
```

That state remains evidence only and must carry all downstream blockers from
the v0.50 prerequisite record. The successful state must fail closed if any
caller attempts to treat it as a queue adapter, queue claim, queue lease,
acknowledgement, queue polling consumer, runtime activation, worker contact,
worker-start admission, worker start, Agent invocation, execution
authorization, execution start, installation, mutation, deployment, rollback,
publication, release, or effect consumer.

## Authority Equations

V0.51 P0 is governed by these fixed equations:

```text
controlled_worker_queue_claim_lease_acknowledgement_admission_recorded != queue_adapter_defined
controlled_worker_queue_claim_lease_acknowledgement_admission_recorded != queue_claimed
controlled_worker_queue_claim_lease_acknowledgement_admission_recorded != queue_leased
controlled_worker_queue_claim_lease_acknowledgement_admission_recorded != queue_acknowledged
controlled_worker_queue_claim_lease_acknowledgement_admission_recorded != worker_start_admitted
controlled_worker_queue_claim_lease_acknowledgement_admission_recorded != worker_started
controlled_worker_queue_claim_lease_acknowledgement_admission_recorded != agent_invoked
controlled_worker_queue_claim_lease_acknowledgement_admission_recorded != execution_started
v0.50_prerequisite_frozen != queue_claimed
v0.50_prerequisite_frozen != queue_leased
v0.50_prerequisite_frozen != queue_acknowledged
queue_claimed != queue_leased != queue_acknowledged
queue_acknowledged != worker_start_admitted
worker_start_admitted != worker_started != execution_started
```

All downstream authority remains fixed false/default off:

- caller-supplied credentials, endpoints, commands, queue selectors, claim
  tokens, lease tokens, acknowledgement handles, payloads, and payload
  schemas;
- queue adapter construction, queue polling, claim, lease, acknowledgement,
  consume/remove, requeue, retry/resend, and mutation;
- worker activation runtime, worker store contact, worker runtime contact,
  worker contact, worker-start admission, worker start, and worker invocation;
- Agent invocation;
- execution authorization, execution start, process execution, shell
  execution, scheduler/workflow start, and dispatch;
- provider, repository, or in-guest mutation;
- installation, deployment, rollback, replay bypass, artifact publication,
  tag push, or release publication.

## Required Lineage

The v0.51 implementation accepts exactly one active same-owner v0.50
`controlled-worker-queue-claim-lease-acknowledgement-prerequisite-v1` record
and its status fingerprint as the only direct input. The v0.50 record remains
the only accepted source for the exact v0.49 controlled worker queue claim
admission, v0.48 worker-binding activation evidence, v0.47 activation
preflight, v0.46 one-shot dequeue worker binding, v0.45 one-shot controlled
dequeue receipt, v0.40 worker intake subject, worker identity, abstract worker
intake reference, abstract queue intake reference, inert queue-item reference,
and byte-exact inherited limits.

Older evidence is accepted only through the already-validated v0.50
prerequisite lineage plus read-only fingerprint recomputation of that v0.50
record and status. Any owner, candidate, lifecycle, freshness, expiry,
fingerprint, worker subject, queue item, lineage, or inherited-limit mismatch
fails closed.

## Persistence and Replay Rules

P0 is documentation-only and creates no durable v0.51 record. P2 implements
explicitly constructed bounded append-only persistence with redacted,
secret-free storage and readback. It reserves idempotency and subject identity
before recording admission evidence, preserves permanent no-replay across
admission attempts, fails closed on changed content under a reserved identity,
and treats ambiguous commit or storage outcomes as terminal indeterminate
reservations.

No v0.51 admission record stores raw credentials, raw endpoints, raw claim
tokens, raw lease tokens, raw acknowledgement handles, raw payloads, raw
idempotency keys, or unredacted adapter errors. Expired, failed, ambiguous, or
foreign prerequisite evidence remains durable evidence only and cannot be
renewed, retried, replayed, resent, rekeyed, or promoted to authority by v0.51.

## API and UI Exposure

V0.51 P3 exposes only owner-scoped, candidate-scoped Core evidence APIs:
guarded `POST` to record admission evidence, guarded collection `GET`, and
guarded owned item `GET`. They use dedicated operator permissions,
CSRF/origin checks, strict JSON and idempotency bounds, redacted errors, and
default-off service construction.

V0.51 creates no Mission Control route, navigation entry, standalone action,
browser storage authority, polling transport, queue selector, claim/lease/
acknowledgement control, worker selector, endpoint input, credential input,
payload editor, command editor, worker-start control, execute control,
deploy/rollback control, publication control, or raw secret rendering. Mission
Control presents admission evidence only as nested read-only installation
workflow evidence under the v0.50 prerequisite evidence chain until a later
release explicitly freezes and implements a separate action authority.

## Agent and Execution-Worker Isolation

V0.51 P0-P5 make no Agent or execution-worker change. Agent and the packaged
execution worker must have zero consumers for
`controlled_worker_queue_claim_lease_acknowledgement_admission_recorded`,
`v0.50_prerequisite_frozen`, or any v0.51 admission marker. They must not poll,
claim, lease, acknowledge, contact a worker store, contact a worker runtime,
start a worker, invoke Agent, start execution, run a process, mutate provider
state, mutate repository state, mutate in-guest state, deploy, roll back,
publish artifacts, push tags, publish releases, retry, resend, or replay based
on v0.51 evidence.

## Release-Isolation Requirements

V0.51 P5 proves exact v0.50-v0.20 lineage and ownership, freshness/expiry,
fingerprints, inherited limits, permanent idempotency and subject no-replay,
bounded/redacted/secret-free persistence, default-off production construction,
API/UI isolation, Home Assistant blocking, Agent/execution-worker
zero-consumer behavior, and the absence of `compose.execution-smoke.override.yaml`.

Release closure for v0.51 adds tests and documentation only. Runtime queue
adapters, queue claim, queue lease, acknowledgement, worker activation
runtime, worker store/runtime contact, worker-start admission, worker start,
Agent invocation, execution authorization/start, publication, deployment,
rollback, and effect consumers remain out of scope.

## Must Not Change

V0.51 P0-P5 do not modify any prior authority boundary. The completed
v0.20-v0.50 lineage, ownership, limits, freshness, permanent no-replay,
redaction, ambiguity handling, default-off construction, API/UI isolation,
Home Assistant blocking, and Agent/execution-worker zero-consumer contracts
remain authoritative.

Controlled worker invocation, worker-start admission, worker start, and
execution-start admission may be selected only after separately released
boundaries define and prove controlled queue claim, lease, acknowledgement,
binding, worker activation runtime, worker store/runtime contact, and
worker-start prerequisites, or deliberately prove why any omitted prerequisite
is not required for that specific authority. Until then, unsupported
architectures must fail closed with the explicit blockers listed in this
document.
