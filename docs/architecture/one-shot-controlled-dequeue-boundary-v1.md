# One-Shot Controlled Dequeue Boundary v1 planning contract

Status: **Atlas v0.45 P0 frozen planning contract**.

This document freezes the repository-supported v0.45 One-Shot Controlled
Dequeue Boundary before runtime work. It starts from the completed v0.44
Controlled Dequeue Admission baseline as implemented in
`controlled_dequeue_admission`, from the completed v0.43 Queue Observation and
Enqueue Receipt Evidence baseline as implemented in `queue_observation_receipt`,
and from the completed v0.42 One-Shot Live Enqueue Boundary as implemented in
`installation_one_shot_live_enqueue`.

V0.45 defines exactly one future authority: after one active valid same-owner
v0.44 `controlled-dequeue-admission-v1` record, Core may perform at most one
explicitly authorized, single-use controlled dequeue of the exact admitted
inert v0.42 queue item. The dequeue is bounded receipt evidence only. It is not
queue polling, autonomous work discovery, claim, lease, acknowledgement,
worker invocation, Agent invocation, execution authorization, execution start,
retry/resend, scheduler/workflow execution, installation, mutation,
deployment, or rollback.

The authority invariant is:

`one_shot_controlled_dequeue_recorded == bounded receipt evidence for one explicit dequeue attempt of the exact admitted inert v0.42 item`

and:

`one_shot_controlled_dequeue_recorded != autonomous queue polling != worker start != Agent invocation != execution`

V0.45 must not add autonomous queue polling, worker start or invocation, Agent
invocation, execution start, retry or resend, scheduler/workflow execution,
installation, provider/repository/in-guest mutation, deployment, rollback, or
any change to `compose.execution-smoke.override.yaml`.

## 1. Authority boundary

V0.45 may authenticate an operator, require a dedicated one-shot controlled
dequeue permission, re-read one owned active v0.44
`controlled-dequeue-admission-v1` record and status, re-read the embedded
owned active v0.43 observation/receipt record and exact embedded owned active
v0.42 inert queue item, recompute the complete v0.20-v0.44 lineage and
fingerprints, verify queue identity and queue-item identity equality, verify
ownership, lifecycle, freshness, earliest inherited expiry, and byte-exact
inherited sandbox/resource/network/filesystem ceilings, reserve one dequeue
subject before any dequeue effect, call one injected explicitly constructed
single-use dequeue adapter for only that exact admitted item, append one
immutable Core-owned dequeue receipt record, and return owned readback.

The only permitted effect is that one explicitly authorized dequeue attempt for
the exact v0.42 inert queue item already admitted by v0.44. The adapter input
must be server-owned, derived from v0.44/v0.43/v0.42 evidence, and bounded to
the item identity; it cannot discover work, poll for the next item, subscribe
to a stream, claim, lease, acknowledge, mutate, replace, re-enqueue, retry, or
resend anything.

It may not contact or start a worker; invoke Agent; start a scheduler or
workflow; dispatch; bind a runner; authorize or start execution; execute a
process; start Docker, Podman, shell, container, or other process execution;
install; mutate a provider, repository, or guest; deploy; roll back; load
credentials outside the injected dequeue adapter; resolve arbitrary endpoints;
create a consumer group; or create Home Assistant artifacts.

No v0.45 output is consumable by worker, dispatch, provider, repository, guest,
deployment, rollback, scheduler, workflow, Agent, execution-worker,
queue-polling, or process-execution paths. A future milestone that wants to
start work from a dequeued item must define a separate authority boundary and
must treat v0.45 as read-only prerequisite receipt evidence only.

## 2. Frozen prerequisite lineage

V0.45 binds exactly one owned active v0.44
`controlled-dequeue-admission-v1` record whose successful state is
`controlled_dequeue_admission_recorded`. The prerequisite record must retain:

- schema `controlled-dequeue-admission-v1`;
- scope `installation_controlled_dequeue_admission_only`;
- v0.44 record permission
  `installation.execution.controlled_dequeue_admission.record`;
- v0.44 read permission
  `installation.execution.controlled_dequeue_admission.read`;
- eligibility `eligible_for_later_dequeue_consideration`;
- successful blockers `dequeue_not_defined`, `queue_polling_not_defined`,
  `queue_claim_not_defined`, `queue_lease_not_defined`,
  `queue_ack_not_defined`, `worker_start_not_defined`, and
  `execution_start_boundary_not_defined`;
- exact v0.44 admission decision, queue identity, item identity, lineage,
  inherited limits, subject, record, and status fingerprints;
- exact embedded v0.43 `queue-observation-receipt-v1` record and status;
- exact embedded v0.42 `one-shot-live-enqueue-v1` record and
  `one-shot-live-enqueue-item-v1` queue item;
- permanent v0.44 idempotency and subject reservation fingerprints;
- fixed-false v0.44 authority fields.

The embedded v0.43 record must retain `queue_observation_recorded` evidence
over the same exact v0.42 item. The embedded v0.42 item must retain
`item_kind = inert_reference_only_queue_item`, `reference_only = true`,
`payload_schema_defined = false`, `payload_constructed = false`,
`payload_serialized = false`, `payload_bytes = 0`, `dequeue_defined = false`,
`dequeued = false`, `queue_polled = false`, `queue_claimed = false`,
`queue_leased = false`, `worker_contacted = false`, `worker_started = false`,
and `execution_allowed = false`.

The v0.20-v0.44 lineage must be reconstructed from owner-scoped readers and
embedded records. Summary fingerprints never replace validation of exact
nested fields. Missing, foreign, malformed, stale, expired, mismatched,
unsupported, corrupt, ambiguous, non-inert, previously dequeued, or
non-admitted prerequisite evidence fails closed without partial dequeue output
and without reservation release.

V0.45 does not modify, renew, replace, supersede, release, or reclassify v0.44,
v0.43, or v0.42 records, statuses, audits, errors, reservations, observations,
receipts, or queue items. Expired prerequisite records remain readable
evidence but cannot create new v0.45 dequeue records. Boundary equality is
expired.

## 3. Queue and item identity

The dequeue queue identity is not caller-supplied. It is derived from the owned
v0.44 record and its v0.20-v0.44 lineage:

- authenticated operator ID;
- candidate record ID;
- v0.39 worker queue reservation ID and fingerprint;
- v0.39 queue intake reference ID and fingerprint;
- v0.39 queue item reference ID and fingerprint;
- v0.40 worker intake admission ID and fingerprint;
- v0.41 live enqueue admission ID and fingerprint;
- v0.42 enqueue ID, record fingerprint, status fingerprint, queue item ID, and
  queue item fingerprint;
- v0.43 receipt ID, receipt record fingerprint, status fingerprint, queue
  observation fingerprint, receipt fingerprint, queue identity fingerprint,
  item identity fingerprint, lineage fingerprint, and subject fingerprint;
- v0.44 admission ID, admission record fingerprint, status fingerprint,
  decision fingerprint, queue identity fingerprint, item identity fingerprint,
  lineage fingerprint, and subject fingerprint;
- inherited limits fingerprint.

The item identity is exactly the v0.42 inert queue item admitted by v0.44:

- `v042.enqueue_id`;
- `v042.queue_item.queue_item_id`;
- `v043.receipt_evidence.inert_queue_item_id`;
- `v043.queue_observation.enqueue_id`;
- `v044.controlled_dequeue_admission.inert_queue_item_id`, if represented by
  a future read model.

All represented values must be equal. The v0.42 item fingerprint must equal
the v0.42 `queue_item.item_fingerprint`, the v0.43
`receipt_evidence.inert_queue_item_fingerprint`, and the v0.44 item identity
fingerprint linkage.

The queue identity is abstract evidence identity only. It must not contain or
render a broker address, queue name, topic, stream, subscription, endpoint,
hostname, port, socket, credential, route key, consumer group, claim token,
lease name, visibility timeout, acknowledgement handle, callback, or queue
client configuration. The injected adapter may receive only the bounded
server-owned fields needed to attempt the exact authorized dequeue; raw
transport details are never persisted or rendered.

## 4. Dequeue receipt evidence

The receipt can prove only one of these facts about the exact admitted inert
item:

- one authorized dequeue attempt returned a bounded success receipt for the
  exact item;
- one authorized dequeue attempt returned a bounded failure receipt;
- Core could not determine whether the append or dequeue attempt completed.

It cannot prove worker visibility, queue ordering, payload execution,
installation success, provider mutation, repository mutation, in-guest
mutation, deployment, rollback, retry eligibility, resend eligibility,
acknowledgement, or no-redelivery unless a later milestone freezes a separate
authority for those facts.

Receipt evidence must carry the exact v0.44 admission linkage, exact v0.43
observation/receipt linkage, exact v0.42 item identity, trusted attempt time,
valid-until, closed outcome, ordered blockers, bounded adapter receipt
fingerprint, redaction marker, subject fingerprint, idempotency fingerprint,
record fingerprint, status fingerprint, and fixed authority posture.

## 5. Closed vocabulary

Lifecycle is exactly `active | expired`. Dequeue state is exactly:

- `one_shot_controlled_dequeue_recorded`
- `readiness_gated`
- `blocked`
- `indeterminate`

Outcome is exactly:

- `success`
- `failure`
- `indeterminate`

Disposition is exactly:

- `exact_inert_item_dequeued`
- `exact_inert_item_not_dequeued`
- `dequeue_completion_indeterminate`

Every successful dequeue receipt carries these ordered blockers:

1. `queue_polling_not_defined`
2. `queue_claim_not_defined`
3. `queue_lease_not_defined`
4. `queue_ack_not_defined`
5. `worker_start_not_defined`
6. `execution_start_boundary_not_defined`

The closed ordered blocker vocabulary is:

- `installation_capability_unsupported`
- `evidence_not_found`
- `ownership_mismatch`
- `permission_scope_missing`
- `v044_admission_not_active`
- `v044_admission_not_recorded`
- `v044_admission_not_eligible`
- `v043_observation_not_active`
- `v043_observation_not_recorded`
- `v043_receipt_not_contract_eligible`
- `v042_enqueue_not_active`
- `v042_enqueue_not_recorded`
- `linkage_mismatch`
- `queue_identity_mismatch`
- `item_identity_mismatch`
- `observation_receipt_mismatch`
- `fingerprint_mismatch`
- `inherited_limits_mismatch`
- `evidence_stale`
- `evidence_expired`
- `ambiguous_state`
- `executable_payload`
- `unsupported_authority`
- `dequeue_adapter_unavailable`
- `dequeue_receipt_mismatch`
- `reservation_before_effect_failed`
- `permanent_subject_reserved`
- `idempotency_conflict`
- `append_indeterminate`
- `dequeue_indeterminate`
- `queue_polling_not_defined`
- `queue_claim_not_defined`
- `queue_lease_not_defined`
- `queue_ack_not_defined`
- `worker_start_not_defined`
- `execution_start_boundary_not_defined`

Audit events are exactly `one_shot_controlled_dequeue_recorded`,
`one_shot_controlled_dequeue_read`, and
`one_shot_controlled_dequeue_indeterminate`. Unknown lifecycle values, dequeue
states, outcomes, dispositions, blockers, audit events, errors, or authority
labels fail closed.

Home Assistant remains the blocked golden state: it always returns `blocked`
with first blocker `installation_capability_unsupported`, records no one-shot
controlled dequeue, remains non-installable and non-executable, and creates no
deployment artifact or exception.

## 6. Canonical primitives and bounds

All models are immutable and closed. Unknown keys, duplicate JSON keys,
invalid UTF-8, non-NFC strings, non-finite numbers, unbounded nesting, and
contrary fixed booleans fail closed.

- UUIDs are canonical lowercase UUIDv4 unless explicitly derived as UUIDv5.
- Operator IDs are visible ASCII matching
  `[A-Za-z0-9][A-Za-z0-9._:-]{0,127}`.
- Timestamps are UTC RFC 3339 whole seconds ending in `Z`; clients supply
  none.
- Fingerprints use SHA-256 over `atlas-jcs-nfc-v1` canonical JSON after NFC
  normalization and are lowercase 64-character hexadecimal strings.
- POST bodies are at most 16 KiB with nesting depth 16.
- Records/results are at most 192 KiB.
- Collections contain at most 16 records per operator.
- Idempotency keys are 16-128 visible ASCII characters and are never stored,
  logged, returned, audited, or rendered raw.
- Bounded adapter receipt evidence is at most 8 KiB before canonicalization and
  must be reduced to closed fields and fingerprints before persistence.
- Identifiers other than UUIDs and operator IDs are visible ASCII, contain no
  whitespace-only value, and are at most 128 characters.

Fingerprint objects retain the released shape:

```yaml
algorithm: sha256
canonicalization: atlas-jcs-nfc-v1
value: <64 lowercase hexadecimal characters>
```

Domain separation is mandatory:

- `atlas:one-shot-controlled-dequeue-request:v1`
- `atlas:one-shot-controlled-dequeue-lineage:v1`
- `atlas:one-shot-controlled-dequeue-queue-identity:v1`
- `atlas:one-shot-controlled-dequeue-item-identity:v1`
- `atlas:one-shot-controlled-dequeue-admission-linkage:v1`
- `atlas:one-shot-controlled-dequeue-receipt:v1`
- `atlas:one-shot-controlled-dequeue-subject:v1`
- `atlas:one-shot-controlled-dequeue-idempotency:v1`
- `atlas:one-shot-controlled-dequeue-reservation:v1`
- `atlas:one-shot-controlled-dequeue-record:v1`
- `atlas:one-shot-controlled-dequeue-status:v1`
- `atlas:one-shot-controlled-dequeue-audit:v1`
- `atlas:one-shot-controlled-dequeue-error:v1`
- `atlas:one-shot-controlled-dequeue-result:v1`
- `atlas:one-shot-controlled-dequeue-collection:v1`
- `atlas:one-shot-controlled-dequeue-correlation:v1`

Fingerprints from v0.44 and prior milestones remain in their original domains
and are not interchangeable with v0.45 fingerprints.

## 7. Exact create request

`one-shot-controlled-dequeue-create-v1` contains exactly:

- `schema = one-shot-controlled-dequeue-create-v1`
- `controlled_dequeue_admission_id`
- `controlled_dequeue_admission_fingerprint`
- `controlled_dequeue_admission_status_fingerprint`
- `controlled_dequeue_admission_valid_until`
- `queue_observation_receipt_id`
- `queue_observation_receipt_fingerprint`
- `queue_observation_receipt_status_fingerprint`
- `one_shot_live_enqueue_id`
- `one_shot_live_enqueue_fingerprint`
- `one_shot_live_enqueue_status_fingerprint`
- `inert_queue_item_id`
- `inert_queue_item_fingerprint`
- `queue_identity_fingerprint`
- `item_identity_fingerprint`
- `inherited_limits_fingerprint`
- `requested_scope = installation_one_shot_controlled_dequeue_only`
- `dequeue_intent = exact_inert_item_single_use_dequeue_only`
- `reference_only = true`
- `payload_schema_defined = false`
- `payload_constructed = false`
- `payload_serialized = false`
- `queue_polling_allowed = false`
- `queue_claim_allowed = false`
- `queue_lease_allowed = false`
- `queue_ack_allowed = false`
- `worker_start_allowed = false`
- `agent_invocation_allowed = false`
- `execution_authorized = false`
- `retry_allowed = false`
- `resend_allowed = false`
- `replay_allowed = false`

The body supplies references only. Operator identity, candidate identity,
permission result, trusted request time, idempotency key, correlation value,
complete v0.20-v0.44 evidence, queue identity, item identity, dequeue adapter
selection, audit facts, dequeue attempt, and receipt classification are
server-owned dependencies.

The body cannot contain raw prior evidence, queue names, broker endpoints,
credentials, payloads, commands, images, paths, arbitrary metadata,
timestamps, permissions, authority overrides, worker execution requests,
polling instructions, consumer configuration, claim instructions, lease
instructions, acknowledgement instructions, retry instructions, resend
instructions, scheduler instructions, workflow instructions, Agent requests,
callback instructions, or queue mutation instructions.

## 8. Reservation before effect and no replay

`one-shot-controlled-dequeue-idempotency-reservation-v1` and
`one-shot-controlled-dequeue-subject-reservation-v1` contain only schema,
owner/candidate IDs, hashed identifiers, request/dequeue-subject fingerprints,
record IDs, `reserved_at`, `reservation_state`, and `permanent = true`.

Reservation must complete durably before the injected dequeue adapter is
called. The dequeue subject is the tuple `(owner, candidate, v0.44 admission
record fingerprint, v0.44 admission status fingerprint, v0.44 subject
fingerprint, v0.43 receipt record fingerprint, v0.43 receipt status
fingerprint, v0.43 queue observation fingerprint, v0.43 enqueue receipt
evidence fingerprint, v0.42 enqueue record fingerprint, v0.42 queue item
fingerprint, v0.42 status fingerprint, queue identity fingerprint, item
identity fingerprint, inherited limits fingerprint)`.

One subject can produce at most one one-shot controlled dequeue record forever.
An exact retry returns the existing record without re-reading evidence,
contacting the adapter, or attempting another dequeue. Same key/different
request or same subject/different key is a permanent conflict.

Reservations cannot be consumed, released, refreshed, replaced, superseded,
retried, resent, repaired, garbage-collected, or bypassed, including after
expiry, restart, corruption, timeout, lost response, dequeue uncertainty, or
indeterminate append. Ambiguous completion is recorded as indeterminate, keeps
the permanent reservation, returns a redacted error, and never permits
reconstruction as new work.

## 9. Record, status, result, audit, and error schemas

`one-shot-controlled-dequeue-v1` contains exactly its schema, dequeue UUIDv5,
owner and candidate IDs, trusted `attempted_at`, `valid_until`,
`record_state = recorded`, lifecycle, dequeue state, outcome, disposition,
ordered blockers, exact v0.44 admission linkage, exact v0.43
observation/receipt linkage, exact v0.42 queue item identity, queue identity,
item identity, lineage, inherited limits fingerprint, idempotency fingerprint,
request fingerprint, dequeue-subject fingerprint, bounded dequeue receipt
evidence, record fingerprint, audit evidence, and fixed authority from
section 14.

`one-shot-controlled-dequeue-status-v1` contains exactly dequeue/owner/
candidate IDs, lifecycle, dequeue state, outcome, disposition, ordered
blockers, `evaluated_at`, `valid_until`, record fingerprint, status
fingerprint, and fixed authority.

`one-shot-controlled-dequeue-result-v1` contains exactly `schema`, `ok`,
`outcome = success | failure | indeterminate`, nullable closed record,
nullable closed status, nullable closed redacted error, correlation
fingerprint, and fixed authority. Success returns a record and status. Failure
returns only a redacted error unless the dequeue attempt completed with a
closed non-dequeued receipt record. Indeterminate returns only a redacted error
with no retry authority and a permanent reservation.

`one-shot-controlled-dequeue-collection-v1` contains exactly `schema`, owner
and candidate IDs, ordered immutable `items`, `count`, collection fingerprint,
and fixed authority. Items are ordered by `(attempted_at, dequeue_id)`.

`one-shot-controlled-dequeue-error-v1` permits only closed safe codes derived
from the blocker vocabulary plus `unauthenticated`, `forbidden`, `not_found`,
`invalid_request`, `rate_limited`, `quota_exceeded`, `conflict`,
`record_too_large`, `store_corrupt`, and `internal_error`. It contains only
schema, code, fixed sanitized message, retryable (always false), correlation
fingerprint, redaction marker, and fixed authority. Foreign and missing
records both return `not_found`.

## 10. Ownership, permissions, and freshness

Every operation requires an authenticated operator. Create requires exactly
`installation.execution.one_shot_controlled_dequeue.record`. List/get require
exactly `installation.execution.one_shot_controlled_dequeue.read`. The frozen
scope is `installation_one_shot_controlled_dequeue_only`.

Candidate, v0.44 admission record, v0.44 status, v0.44 decision, v0.43
observation receipt record, v0.43 status, v0.43 receipt evidence, v0.43 queue
observation, embedded v0.42 enqueue record, embedded v0.42 queue item, v0.42
status, v0.41 admission, v0.40 worker intake admission, v0.39 queue
reservation, queue intake reference, queue item reference, dequeue record,
idempotency reservation, subject reservation, status, and audit ownership must
all equal the authenticated operator. No caller-supplied identity, permission,
receipt, queue identity, item identity, dequeue result, or authority flag is
trusted. Foreign and absent evidence are indistinguishable.

The service uses a trusted server clock. At create time, the complete
v0.20-v0.44 chain and all active prerequisite records must be fresh and
unexpired. V0.45 cannot extend any predecessor: `valid_until` is the earliest
upstream expiry and is never more than 30 seconds after trusted `attempted_at`.
Prerequisite facts older than 30 seconds, facts from the future, or facts whose
source time is ambiguous fail closed. Boundary equality is expired.

Expired dequeue records remain readable as immutable evidence but cannot be
refreshed, renewed, replaced, superseded, acknowledged, retried, resent,
released, or used to create another record. Expiry causes no background work,
callback, cleanup, polling, claim, lease, acknowledgement, queue mutation,
worker contact, Agent invocation, scheduler signal, workflow signal, runtime
signal, or execution signal.

## 11. Bounded evidence and redaction

One-shot controlled dequeue evidence is bounded proof, not a queue transcript
or worker handoff. Records, errors, logs, metrics, audits, API responses, and
UI projections never disclose raw idempotency keys, credentials, endpoints,
addresses, queue names, broker details, payloads, commands, arguments,
environment, logs, paths, hostnames, ports, sockets, repository paths, guest
paths, mount sources, provider payloads, exception text, stack traces,
foreign-owner facts, raw receipt documents, claim handles, lease handles,
acknowledgement handles, consumer group names, or queue client configuration.

Redaction must preserve enough safe structure to audit owner, candidate,
schema, closed blocker, lifecycle, outcome, v0.42/v0.43/v0.44 fingerprint
linkage, freshness, single-use subject identity, and fixed authority without
revealing sensitive transport or execution material.

## 12. API boundary

The only future Core surface is:

- `GET /api/v1/installation/candidate-records/{candidate_record_id}/one-shot-controlled-dequeues`
- `POST /api/v1/installation/candidate-records/{candidate_record_id}/one-shot-controlled-dequeues`
- `GET /api/v1/installation/candidate-records/{candidate_record_id}/one-shot-controlled-dequeues/{dequeue_id}`

GET has no body or query parameters. POST requires authentication, the record
permission, trusted origin, CSRF, rate limiting, `Content-Type:
application/json`, the strict bounded body, and an `Idempotency-Key` of 16-128
visible ASCII characters. List/get require the read permission and owner scope.

No PUT, PATCH, DELETE, action subroute, or sibling poll/claim/lease/ack/
consume/remove/mutate/replace/worker/start/run/execute/dispatch/retry/resend/
install/deploy/rollback/agent/workflow/scheduler route is permitted. P0
registers no permission, dependency, store, route, setting, OpenAPI operation,
UI client, serializer, worker client, credential, endpoint, migration, payload
schema, queue library, broker integration, consumer, scheduler, workflow,
Agent, or execution-worker integration.

## 13. Default-off construction and Mission Control boundary

No v0.45 runtime object may be ambiently available. Later phases must use
explicit construction with injected owner-scoped v0.44, v0.43, and v0.42
readers, injected store, injected trusted clock, explicit enabled flag,
explicit permission checks, and one injected single-use dequeue adapter. The
default constructor state is disabled and cannot dequeue, append, reserve,
read, contact, poll, claim, lease, acknowledge, consume, mutate, execute, or
infer by side effect.

Configuration cannot enable autonomous queue polling, queue claim, queue
lease, queue acknowledgement, queue item mutation, queue item replacement,
worker contact, worker start, Agent invocation, scheduler/workflow execution,
Docker, Podman, container, shell, process execution, installation, mutation,
deployment, rollback, retry, resend, arbitrary credential loading, arbitrary
endpoint resolution, broker browsing, queue consumer creation, or Home
Assistant artifact creation. Production imports alone must not construct the
service.

Mission Control may add strict typing for only the three future endpoints and
an optional nested evidence panel under the owned v0.44 controlled dequeue
admission evidence. It may present lifecycle, outcome, disposition, ordered
blockers, exact v0.44/v0.43/v0.42 linkage, queue identity fingerprint, item
identity fingerprint, inherited ceilings, freshness/expiry, Core-supplied
owner context, audit evidence, permanent no-replay, fixed authority, and
redacted errors.

Creation may be shown only when Core supplies eligible server-owned v0.44
admission context, and must use a two-step acknowledgement stating: "Attempt
one controlled dequeue of the exact admitted inert queue item only. This does
not poll for work, claim, lease, acknowledge, mutate, or replace a queue item;
contact or start a worker; invoke Agent or a workflow; dispatch; retry;
resend; install; deploy; roll back; mutate; or execute anything."

Mission Control must not add polling, standalone navigation, live queue or
worker selectors, editable limits, raw/sensitive fields, arbitrary metadata,
or controls/labels for poll, claim, lease, ack, consume, remove, replace,
worker start, run, execute, install, deploy, dispatch, retry/resend,
send-to-Agent, start-workflow, scheduler, rollback, Docker, Podman, container,
shell, process execution, or mutation.

## 14. Fixed authority posture

Every record, status, result, collection, audit, receipt, and error fixes these
fields:

- `reference_only = true`
- `one_shot_dequeue_only = true`
- `exact_admitted_item_only = true`
- `payload_schema_defined = false`
- `payload_constructed = false`
- `payload_serialized = false`
- `payload_bytes = 0`
- `raw_receipt_persisted = false`
- `raw_queue_identity_persisted = false`
- `autonomous_queue_polling_allowed = false`
- `queue_polling_allowed = false`
- `queue_consumer_defined = false`
- `queue_claim_allowed = false`
- `queue_claimed = false`
- `queue_lease_allowed = false`
- `queue_leased = false`
- `queue_ack_allowed = false`
- `queue_acknowledged = false`
- `queue_item_mutation_allowed = false`
- `queue_item_mutated = false`
- `queue_item_replacement_allowed = false`
- `queue_item_replaced = false`
- `worker_contact_allowed = false`
- `worker_authentication_allowed = false`
- `worker_binding_allowed = false`
- `worker_start_allowed = false`
- `worker_invocation_allowed = false`
- `agent_invocation_allowed = false`
- `execution_authorized = false`
- `execution_start_allowed = false`
- `runner_binding_allowed = false`
- `dispatch_allowed = false`
- `retry_allowed = false`
- `resend_allowed = false`
- `workflow_start_allowed = false`
- `scheduler_allowed = false`
- `docker_execution_allowed = false`
- `podman_execution_allowed = false`
- `container_execution_allowed = false`
- `shell_execution_allowed = false`
- `process_execution_allowed = false`
- `provider_mutation_allowed = false`
- `repository_mutation_allowed = false`
- `in_guest_mutation_allowed = false`
- `installation_allowed = false`
- `deployment_allowed = false`
- `rollback_allowed = false`
- `replay_bypass_allowed = false`

The only effect-state fields allowed to be true in a successful record are
`one_shot_controlled_dequeue_recorded = true` and
`dequeue_attempted = true`. `dequeued = true` may appear only in a successful
bounded receipt for the exact admitted inert item. No authority field may be
omitted, renamed, defaulted to true, inferred from permission, inherited from
v0.44, v0.43, or v0.42, or overridden by configuration.

## 15. Goldens and threats

The canonical success golden is one authenticated same-owner request with the
dedicated record permission, one active valid v0.44 controlled dequeue
admission record, exact v0.20-v0.44 lineage, exact v0.43 observation and
enqueue receipt linkage, exact v0.42 inert queue item identity, exact intended
queue identity, exact inherited limits, an unused idempotency key and dequeue
subject, and one injected bounded adapter success receipt for that exact item.
It produces exactly one durable `one_shot_controlled_dequeue_recorded` record,
outcome `success`, disposition `exact_inert_item_dequeued`, ordered blockers
for undefined queue polling, queue claim, queue lease, queue acknowledgement,
worker start, and execution start, no sensitive output, and no downstream
consumer.

The exact duplicate golden returns the same record without re-reading evidence
or attempting another dequeue. Same key/different request and same subject/
different key are permanent conflicts. Foreign-owner and absent records are
indistinguishable. Home Assistant is blocked with no dequeue and no artifact.
Missing, stale, ambiguous, mismatched, expired, unsupported, malformed,
corrupt, executable-payload, already-dequeued, adapter-failure, reservation
failure, and indeterminate cases fail closed and never create polling, claim,
lease, acknowledgement, queue mutation, worker, Agent, scheduler, workflow,
retry/resend, or execution authority.

Validation and tests in later phases must cover foreign-owner probing,
caller-forged identity, timestamps, permissions, references, scopes, queue
identity, item identity, observation receipt linkage, admission linkage, or
authority; nested-link substitution; stale or expired v0.44 evidence; stale or
expired v0.43 evidence; stale or expired v0.42 evidence; v0.44 admission
mismatch; v0.43 receipt mismatch; v0.43 queue observation mismatch; v0.42
enqueue mismatch; v0.42 inert item mismatch; inherited-limit relaxation;
duplicate-key/schema smuggling; idempotency conflict; concurrent or
post-restart subject replay; reservation-before-effect failure; dequeue
completion uncertainty; indeterminate append completion; store corruption; raw
receipt leakage; sensitive error/audit/UI rendering; accidental payload
schemas; accidental autonomous queue clients; accidental polling, claim, lease,
acknowledgement, consume, remove, mutate, or replace authority; live worker
contact; and Agent, scheduler, workflow, or execution-worker consumers.

Every condition fails closed. No failure releases a permanent reservation,
creates a partial worker-consumable item, serializes a payload, starts polling,
claims or leases a queue item, acknowledges a queue item, invokes Agent, starts
a scheduler or workflow, or starts an effect beyond the one explicitly
authorized bounded dequeue attempt.

## 16. Must-not-change authority boundaries

V0.45 must not change v0.44 schemas, v0.44 permissions, v0.44 scope, v0.44
fixed blockers, v0.44 fixed-false authority fields, v0.44 permanent
reservations, v0.43 schemas, v0.43 permissions, v0.43 scope, v0.43
observation/receipt semantics, v0.42 schemas, v0.42 permissions, v0.42 scope,
v0.42 inert item semantics, v0.42 permanent reservations, v0.41 admission
semantics, v0.40 worker intake semantics, v0.39 queue reservation semantics,
Agent behavior, execution-worker behavior, provider behavior, repository
behavior, deployment behavior, rollback behavior, or
`compose.execution-smoke.override.yaml`.

V0.45 P0 changes planning documentation only. It adds no runtime model,
service, store, route, permission, setting, migration, OpenAPI operation, UI
code, queue library, broker integration, worker client, credential, endpoint,
consumer, scheduler, workflow, Agent change, execution-worker change,
artifact, tag, push, release publication, deployment, rollback, or runtime
authority.
