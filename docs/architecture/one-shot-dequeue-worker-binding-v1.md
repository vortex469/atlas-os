# One-Shot Dequeue Worker Binding v1 planning contract

Status: **Atlas v0.46 P0-P5 closed one-shot dequeue worker binding contract**.

This document freezes the repository-supported v0.46 boundary. V0.46 records
evidence that one successful same-owner v0.45 one-shot controlled dequeue
receipt is bound to one exact same-owner v0.40 worker intake subject. It does not
contact a worker store, contact a worker runtime, start a worker, invoke Agent,
authorize execution, or start execution.

## Authority

V0.46 has exactly one strongest successful state:
`one_shot_dequeue_worker_binding_recorded`. Even in that state it remains
`readiness_gated` and carries the fixed blockers:

- `store_contact_not_defined`
- `runtime_contact_not_defined`
- `worker_start_not_defined`
- `execution_start_boundary_not_defined`

All downstream authority fields are fixed false: caller-supplied credentials,
caller-supplied endpoints, caller-supplied commands, payload construction,
queue polling, claim, lease, acknowledgement, queue mutation, worker contact,
worker start, Agent invocation, execution start, process execution, dispatch,
retry, scheduler/workflow start, shell execution, provider mutation,
repository mutation, in-guest mutation, installation, deployment, rollback, and
replay bypass.

## Exact Lineage

The v0.46 record is valid only when it binds:

- one active same-owner successful v0.45
  `one-shot-controlled-dequeue-v1` record;
- the v0.45 status fingerprint and dequeue record fingerprint;
- the exact v0.45 inherited limits from its v0.42 inert queue item lineage;
- one active same-owner v0.40 `worker-intake-admission-v1` subject;
- the v0.40 worker intake status fingerprint and record fingerprint;
- the v0.40 worker subject fingerprint, worker identity fingerprint, worker
  intake reference fingerprint, queue intake reference fingerprint, and queue
  item reference fingerprint.

The v0.45 record remains the only dequeue evidence accepted by this boundary.
Older v0.44/v0.43/v0.42 data is accepted only through the already-validated
v0.45 receipt lineage. Any owner, candidate, lifecycle, freshness, fingerprint,
worker-subject, queue-item-reference, or inherited-limit mismatch fails closed.

## Persistence and Replay

The v0.46 store is append-only evidence. It records permanent reservations for
the idempotency key fingerprint and binding subject before appending the
evidence record. Exact duplicate requests return the original record. Conflicts
with a different idempotency request or already-reserved subject fail closed.
An indeterminate reservation remains terminal across restart and is never
replayed as a worker, Agent, queue, runtime, or execution action.

Persisted data is bounded and redacted. Raw idempotency keys, credentials,
tokens, endpoints, commands, worker runtime addresses, and shell material are
not valid request fields and must not be persisted or rendered.

## API and Mission Control

The Core API surface is limited to:

- `GET /api/v1/installation/candidate-records/{candidate_record_id}/one-shot-dequeue-worker-bindings`
- `POST /api/v1/installation/candidate-records/{candidate_record_id}/one-shot-dequeue-worker-bindings`
- `GET /api/v1/installation/candidate-records/{candidate_record_id}/one-shot-dequeue-worker-bindings/{binding_id}`

The POST requires the dedicated record permission, CSRF/origin checks,
`application/json`, a 16-128 byte visible-ASCII `Idempotency-Key`, strict body
size limits, and exact v0.46 create schema validation. Reads require the
dedicated read permission and disclose only owned records.

Mission Control may parse and display v0.46 evidence only as a nested,
read-only panel under the existing installation workflow. It has no standalone
route, navigation item, polling transport, worker selector, endpoint input,
payload editor, limit editor, start/contact/execute/deploy controls, raw secret
rendering, or browser storage authority.

## Release Isolation

V0.46 adds no production composition that constructs the service by default.
It adds no worker client, Agent client, queue consumer, scheduler, workflow
runner, Docker/Podman/container/shell/process execution path, provider
mutation, repository mutation, in-guest mutation, installation, deployment,
rollback, background task, endpoint credential, artifact, tag, push, or release
publication. Future worker start or execution milestones must define a new
authority boundary and treat v0.46 as read-only prerequisite evidence only.
