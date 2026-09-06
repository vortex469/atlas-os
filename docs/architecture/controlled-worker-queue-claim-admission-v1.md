# Controlled Worker Queue Claim Admission v1 planning contract

Status: **Atlas v0.49 P0-P5 closed controlled worker queue claim admission contract**.

This document freezes the repository-supported v0.49 boundary after inspection
of the completed merged v0.48 baseline. The v0.48 baseline can record
worker-binding activation evidence over one exact active same-owner v0.47
worker-binding activation preflight record. It still does not define runtime
activation, worker store contact, worker runtime contact, queue claim, queue
lease, queue acknowledgement, worker-start admission, worker start, Agent
invocation, or execution start.

Because queue claim, lease, and acknowledgement prerequisites remain
unsupported, v0.49 cannot safely select worker-start admission evidence,
worker start, Agent invocation, or execution start. The narrowest
repository-supported next boundary toward controlled worker start is
**Controlled Worker Queue Claim Admission Evidence**: a Core-local,
evidence-only admission record that one exact active v0.48 activation-evidence
record may be considered by a later, separately released controlled queue
claim/lease/acknowledgement contract. It is not a queue claim, lease,
acknowledgement, runtime activation, worker-start admission, worker start,
Agent invocation, execution authorization, or execution start.

## Repository Inspection Baseline

The completed v0.48 contract is
[Worker Binding Activation Evidence v1](worker-binding-activation-evidence-v1.md).
It records only `worker_binding_activation_evidence_recorded` over one active
same-owner v0.47 preflight record and carries these required blockers:

- `worker_activation_runtime_not_defined`
- `store_contact_not_defined`
- `runtime_contact_not_defined`
- `queue_claim_not_defined`
- `queue_lease_not_defined`
- `queue_ack_not_defined`
- `worker_start_admission_not_defined`
- `worker_start_not_defined`
- `agent_invocation_not_defined`
- `execution_start_boundary_not_defined`

The v0.48 implementation and release-closure tests prove that its Core
service, store, route, and Mission Control parser are default-off evidence
surfaces only. They also prove that Agent and the packaged execution worker
have no consumer for the activation evidence. No repository-supported
production queue polling consumer, claim primitive, lease primitive,
acknowledgement primitive, worker store client, worker runtime client,
worker-start admission path, worker-start path, Agent invocation path, or
execution-start boundary exists in this baseline.

## Selected Boundary

V0.49 selects only this future evidence question:

```text
Given one active same-owner v0.48 worker-binding activation evidence record,
may Core record that the exact activation evidence has been admitted for later
controlled queue claim/lease/acknowledgement consideration?
```

The strongest future state allowed by this planning contract is:

```text
controlled_worker_queue_claim_admission_recorded
```

That state remains evidence only and must carry all downstream blockers:

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

The successful state must fail closed if any caller attempts to treat it as a
queue claim, queue lease, acknowledgement, runtime activation, worker contact,
worker-start admission, worker start, Agent invocation, execution
authorization, execution start, or effect consumer.

## Authority Equations

V0.49 is governed by these fixed equations:

```text
controlled_worker_queue_claim_admission_recorded != queue_claimed
controlled_worker_queue_claim_admission_recorded != queue_leased
controlled_worker_queue_claim_admission_recorded != queue_acknowledged
controlled_worker_queue_claim_admission_recorded != worker_start_admitted
controlled_worker_queue_claim_admission_recorded != worker_started
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

Any later implementation of this boundary must accept exactly one active
same-owner v0.48 `worker-binding-activation-evidence-v1` record and its status
fingerprint. The v0.48 record remains the only accepted source for the exact
v0.47 activation preflight, v0.46 one-shot dequeue worker binding, v0.45
one-shot controlled dequeue receipt, v0.40 worker intake subject, worker
identity, abstract worker intake reference, abstract queue intake reference,
inert queue-item reference, and byte-exact inherited limits.

Older v0.47, v0.46, v0.45, v0.44, v0.43, v0.42, and v0.40 evidence may be
accepted only through the already-validated v0.48 activation-evidence lineage
unless a later phase explicitly requires a read-only recomputation for
fingerprint verification. Any owner, candidate, lifecycle, freshness, expiry,
fingerprint, worker subject, queue item, lineage, or inherited-limit mismatch
must fail closed.

## Persistence and Defaults

P0 freezes the planning boundary only. Any later implementation must use
explicit construction and remain default-off in production composition. It must
preserve bounded append-only persistence, permanent idempotency and subject
no-replay, redacted errors, secret-free storage, guarded candidate-scoped API
access, Mission Control read-only nesting, Home Assistant blocking, and
Agent/execution-worker zero-consumer behavior.

Mission Control may display the resulting evidence only as nested read-only
installation workflow evidence. It must not add a standalone route, navigation
entry, polling transport, queue selector, claim control, lease control,
acknowledgement control, worker selector, endpoint input, credential input,
payload editor, command editor, worker-start control, execute control,
deploy/rollback control, browser storage authority, or raw secret rendering.

## P5 Release Closure

P0 through P5 are complete. The repository-supported v0.49 boundary advanced
only to `controlled_worker_queue_claim_admission_recorded` over one exact
active same-owner v0.48 worker-binding activation evidence record. Queue
claim, queue lease, queue acknowledgement, worker activation runtime, worker
store/runtime contact, worker-start admission, worker start, Agent invocation,
execution authorization/start, publication, deployment, rollback, and effect
consumers remain fixed false and blocked by the downstream blockers listed in
this contract.

P5 preserves exact v0.48 lineage and ownership, freshness/expiry,
fingerprints, inherited limits, permanent idempotency and subject no-replay,
bounded append-only secret-free persistence, redacted errors, default-off
production construction, guarded API isolation, nested read-only Mission
Control presentation, Home Assistant blocking, Agent/execution-worker
zero-consumer checks, and the absence of
`compose.execution-smoke.override.yaml`. P5 adds focused tests and release
evidence only.

## Must Not Change

V0.49 does not modify any prior authority boundary. The completed v0.20-v0.48
lineage, ownership, limits, freshness, no-replay, redaction, default-off
construction, API/UI isolation, Home Assistant blocking, and Agent/
execution-worker zero-consumer contracts remain authoritative.

Future worker-start admission may be selected only after separately released
boundaries define the queue claim, lease, and acknowledgement prerequisites it
depends on, or deliberately prove why any omitted prerequisite is not required
for that specific authority. Until then, unsupported architectures must fail
closed with the explicit blockers listed in this document.

V0.49 P0 added documentation only. Later phases added the closed model,
explicitly constructed service/store, guarded Core API, nested read-only
Mission Control evidence, and P5 release locks. They introduced no production
construction, queue adapter, queue polling consumer, claim, lease,
acknowledgement, worker store contact, worker runtime contact,
worker-start admission, worker start, Agent invocation, execution start,
publication, deployment, rollback, effect consumer, or change to
`compose.execution-smoke.override.yaml`.
