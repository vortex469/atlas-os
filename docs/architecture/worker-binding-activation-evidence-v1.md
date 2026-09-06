# Worker Binding Activation Evidence v1 planning contract

Status: **Atlas v0.48 P0-P5 closed worker binding activation evidence contract**.

This document freezes the repository-supported v0.48 boundary after inspection
of the completed merged v0.47 baseline and records its P5 closure. The v0.47
baseline can record worker-binding activation preflight evidence over one
active same-owner v0.46 one-shot dequeue worker binding record. It still does
not define binding activation, worker store contact, worker runtime contact,
queue claim, queue lease, queue acknowledgement, worker start, Agent
invocation, or execution start.

Because queue claim, lease, and acknowledgement prerequisites remain
unsupported, v0.48 cannot safely select worker-start admission, worker store
contact, worker runtime contact, Agent invocation, or execution start. The
narrowest repository-supported next boundary is **Worker Binding Activation
Evidence**: a Core-local, evidence-only record that one exact active v0.47
preflight was accepted as activation evidence for a later boundary. It is not
runtime activation and grants no authority to contact, claim, lease,
acknowledge, start, invoke, execute, mutate, publish, deploy, or roll back.

## Repository Inspection Baseline

The completed v0.47 contract is
[Worker Binding Activation Preflight v1](worker-binding-activation-preflight-v1.md).
It records only `worker_binding_activation_preflight_recorded` over one active
same-owner v0.46 binding record and carries these required blockers:

- `worker_binding_activation_not_defined`
- `store_contact_not_defined`
- `runtime_contact_not_defined`
- `queue_claim_not_defined`
- `queue_lease_not_defined`
- `queue_ack_not_defined`
- `worker_start_not_defined`
- `agent_invocation_not_defined`
- `execution_start_boundary_not_defined`

The v0.47 implementation and release-closure tests prove that its Core service,
store, route, and Mission Control parser are default-off evidence surfaces only.
They also prove that Agent and the packaged execution worker have no consumer
for the preflight evidence. No repository-supported production queue polling
consumer, claim primitive, lease primitive, acknowledgement primitive, worker
store client, worker runtime client, worker-start path, Agent invocation path,
or execution-start boundary exists in this baseline.

## Selected Boundary

V0.48 selects only this future evidence question:

```text
Given one active same-owner v0.47 worker-binding activation preflight record,
may Core record that the exact preflight evidence has been accepted as
activation evidence for a later, separately released runtime activation
boundary?
```

The strongest future state allowed by this planning contract is:

```text
worker_binding_activation_evidence_recorded
```

That state remains evidence only and must carry all downstream blockers:

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

The successful state must fail closed if any caller attempts to treat it as a
worker-start admission, runtime activation, claim, lease, acknowledgement,
worker contact, Agent invocation, execution authorization, or effect consumer.

## Authority Equations

V0.48 is governed by these fixed equations:

```text
worker_binding_activation_evidence_recorded != worker_binding_activated
worker_binding_activation_evidence_recorded != worker_start_admitted
worker_binding_activation_evidence_recorded != queue_claim
worker_binding_activation_evidence_recorded != queue_lease
worker_binding_activation_evidence_recorded != queue_ack
worker_start_admitted != worker_started != execution_started
```

All downstream authority remains fixed false:

- caller-supplied credentials, endpoints, commands, and payloads;
- queue polling, claim, lease, acknowledgement, consume/remove, and mutation;
- worker store contact, worker runtime contact, worker contact, worker-start
  admission, worker start, and worker invocation;
- Agent invocation;
- execution authorization, execution start, process execution, shell
  execution, scheduler/workflow start, dispatch, retry, and resend;
- provider, repository, or in-guest mutation;
- installation, deployment, rollback, replay bypass, artifact publication,
  tag, push, or release publication.

## Required Lineage

Any later implementation of this boundary must accept exactly one active
same-owner v0.47 `worker-binding-activation-preflight-v1` record and its status
fingerprint. The v0.47 record remains the only accepted source for the exact
v0.46 one-shot dequeue worker binding, v0.45 one-shot controlled dequeue
receipt, v0.40 worker intake subject, worker identity, abstract worker intake
reference, abstract queue intake reference, inert queue-item reference, and
byte-exact inherited limits.

Older v0.46, v0.45, v0.44, v0.43, v0.42, and v0.40 evidence may be accepted
only through the already-validated v0.47 preflight lineage unless a later phase
explicitly requires a read-only recomputation for fingerprint verification. Any
owner, candidate, lifecycle, freshness, expiry, fingerprint, worker subject,
queue item, lineage, or inherited-limit mismatch must fail closed.

## Persistence and Defaults

The v0.48 boundary uses explicit construction and remains default-off in
production composition. Its service/store use bounded append-only persistence,
permanent idempotency and subject no-replay, redacted errors, secret-free
storage, and guarded candidate-scoped API access.

Mission Control may display the resulting evidence only as nested read-only
installation workflow evidence. It must not add a standalone route, navigation
entry, polling transport, worker selector, endpoint input, credential input,
payload editor, command editor, worker-start control, execute control,
deploy/rollback control, browser storage authority, or raw secret rendering.

## Must Not Change

V0.48 does not modify any prior authority boundary. The completed v0.20-v0.47
lineage, ownership, limits, freshness, no-replay, redaction, and default-off
contracts remain authoritative.

Future worker-start admission may be selected only after a separately released
boundary defines the queue claim, lease, and acknowledgement prerequisites it
depends on, or deliberately proves why they are not prerequisites for that
specific authority. Until then, unsupported architectures must fail closed with
the explicit blockers listed in this document.

P5 release closure adds focused regression checks and documentation only. It
proves the only advanced authority is
`worker_binding_activation_evidence_recorded`, while runtime activation,
worker store/runtime contact, queue claim/lease/acknowledgement, worker-start
admission, worker start, Agent invocation, execution start, publication,
deployment, rollback, effect consumers, and `compose.execution-smoke.override.yaml`
remain blocked or absent.
