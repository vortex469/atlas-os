# Controlled Dequeue Admission v1 planning contract

Status: **Atlas v0.44 P0 frozen planning contract**.

This document freezes the v0.44 Controlled Dequeue Admission boundary before
runtime work. It starts from the completed v0.43 Queue Observation and Enqueue
Receipt Evidence baseline as implemented in `queue_observation_receipt`, and
from the completed v0.42 One-Shot Live Enqueue Boundary as implemented in
`installation_one_shot_live_enqueue`.

V0.44 defines exactly one new evidence-only authority: Core may evaluate
whether one exact same-owner inert v0.42 queue item, backed by one active valid
v0.43 Queue Observation and Enqueue Receipt record, is eligible for later
dequeue consideration. This is an admission record for future consideration
only. It is not dequeue, polling, claim, lease, acknowledgement, consumption,
queue mutation, worker invocation, Agent invocation, execution authorization,
or execution start.

The authority invariant is:

`controlled_dequeue_admission_recorded == eligibility evidence for later dequeue consideration`

and:

`controlled_dequeue_admission_recorded != dequeue != queue polling != claim != lease != ack != worker start != Agent invocation != execution`

V0.44 must not dequeue, poll a queue for action, claim, lease, acknowledge,
consume, remove, mutate, or replace a queue item; start or invoke a worker;
invoke Agent; authorize or start execution; retry or resend; schedule workflow
work; run Docker, Podman, container, shell, or process execution; install;
mutate provider, repository, or in-guest state; deploy; roll back; or modify
`compose.execution-smoke.override.yaml`.

## 1. Authority boundary

V0.44 may authenticate an operator, require a dedicated controlled-dequeue
admission permission, re-read one owned active v0.43
`queue-observation-receipt-v1` record and status, re-read the exact owned
active v0.42 `one-shot-live-enqueue-v1` record and inert
`one-shot-live-enqueue-item-v1` embedded in that v0.43 record, recompute the
complete v0.20-v0.43 lineage and fingerprints, verify queue identity and
queue-item identity equality, verify ownership, lifecycle, freshness, and
earliest inherited expiry, verify byte-exact inherited sandbox, resource,
network, and filesystem ceilings, reserve one admission subject before append,
append one immutable Core-owned admission record, and return owned readback.

It may not contact a queue broker; poll a queue; list live queue messages;
peek into a live queue for action; claim, lease, acknowledge, dequeue, consume,
remove, mutate, replace, re-enqueue, retry, or resend the v0.42 item; contact,
authenticate, bind, start, or invoke a worker; invoke Agent; start a scheduler
or workflow; dispatch; bind a runner; authorize or start execution; execute a
process; start Docker, Podman, shell, container, or other process execution;
install; mutate a provider, repository, or guest; deploy; roll back; load
credentials; resolve endpoints; create a consumer group; or create Home
Assistant artifacts.

No v0.44 output is consumable by worker, dispatch, provider, repository,
guest, deployment, rollback, scheduler, workflow, Agent, execution-worker,
queue-client, or process-execution paths. A future milestone that wants to
dequeue must define a separate authority boundary and must treat v0.44 as
read-only prerequisite evidence only.

## 2. Frozen prerequisite lineage

V0.44 binds exactly one owned active v0.43
`queue-observation-receipt-v1` record whose successful state is
`queue_observation_recorded`. The prerequisite record must retain:

- schema `queue-observation-receipt-v1`;
- scope `installation_queue_observation_receipt_only`;
- v0.43 contract authority-context permission
  `installation.execution.queue_observation_receipt.record`;
- v0.43 public API record/read permissions
  `installation.execution.queue_observation.record` and
  `installation.execution.queue_observation.read`;
- successful blockers `dequeue_not_defined`, `queue_polling_not_defined`,
  `worker_start_not_defined`, and `execution_start_boundary_not_defined`;
- exact `queue-observation-v1`, `enqueue-receipt-evidence-v1`, and
  `queue-observation-receipt-status-v1` fields and fingerprints;
- exact embedded v0.42 enqueue record and status fingerprints;
- exact queue identity `abstract_installation_queue`;
- exact item identity `inert_reference_only_queue_item`;
- permanent idempotency and subject reservation fingerprints;
- fixed-false v0.43 authority fields.

The v0.43 record must bind exactly one owned v0.42
`one-shot-live-enqueue-v1` record whose successful state is
`one_shot_live_enqueue_recorded` and whose queue item is one inert
`one-shot-live-enqueue-item-v1`. The v0.42 item must retain:

- scope `installation_one_shot_live_enqueue_only`;
- `item_kind = inert_reference_only_queue_item`;
- `reference_only = true`;
- `item_state = recorded`;
- `payload_schema_defined = false`;
- `payload_constructed = false`;
- `payload_serialized = false`;
- `payload_bytes = 0`;
- `dequeue_defined = false`;
- `dequeued = false`;
- `queue_polled = false`;
- `queue_claimed = false`;
- `queue_leased = false`;
- `worker_contacted = false`;
- `worker_started = false`;
- `execution_allowed = false`.

The v0.20-v0.43 lineage must be reconstructed from owner-scoped readers and
embedded records. Summary fingerprints never replace validation of exact
nested fields. Missing, foreign, malformed, stale, expired, mismatched,
unsupported, corrupt, ambiguous, or non-inert prerequisite evidence fails
closed without partial admission output and without reservation release.

V0.44 does not modify, renew, replace, supersede, release, consume, or
reclassify v0.43 records, observations, receipts, statuses, audits, errors,
reservations, or embedded v0.42 records and queue items. Expired prerequisite
records remain readable evidence but cannot create new v0.44 admission
records. Boundary equality is expired.

## 3. Queue identity

The controlled-dequeue queue identity is not caller-supplied. It is derived
from the owned v0.43 record and its v0.39-v0.43 lineage:

- authenticated operator ID;
- candidate record ID;
- v0.39 worker queue reservation ID and fingerprint;
- v0.39 queue intake reference ID and fingerprint;
- v0.39 queue item reference ID and fingerprint;
- v0.40 worker intake admission ID and fingerprint;
- v0.41 live enqueue admission ID and fingerprint;
- v0.42 enqueue ID, record fingerprint, status fingerprint, queue item ID, and
  queue item fingerprint;
- v0.43 receipt ID, receipt record fingerprint, status fingerprint,
  queue observation fingerprint, queue identity, item identity, receipt
  fingerprint, lineage fingerprint, and subject fingerprint;
- inherited limits fingerprint.

The queue identity is abstract evidence identity only. It must not contain or
render a broker address, queue name, topic, stream, subscription, endpoint,
hostname, port, socket, credential, route key, consumer group, claim token,
lease name, visibility timeout, acknowledgement handle, callback, or queue
client configuration. Any supplied transport identity is rejected or redacted
and may contribute only to a bounded fingerprint if a later implementation
explicitly freezes that behavior.

## 4. Queue-item identity

The admitted item identity is exactly the v0.42 inert queue item:

- `v042.enqueue_id`;
- `v042.queue_item.queue_item_id`;
- `v043.receipt_evidence.inert_queue_item_id`;
- `v043.queue_observation.enqueue_id`.

All four values must be equal. The v0.42 item fingerprint must equal the
v0.42 `queue_item.item_fingerprint`, the v0.43
`receipt_evidence.inert_queue_item_fingerprint`, and the v0.43 item identity
fingerprint linkage.

V0.44 cannot construct a new payload, payload schema, envelope, serialized
message, worker request, command, environment, repository path, guest path,
image, mount, callback, lease, claim, acknowledgement, retry policy, resend
policy, consumer pointer, or queue position. It evaluates only the exact inert
reference-only queue item already recorded by v0.42 and observed by v0.43.

## 5. Observation and receipt linkage

The v0.43 prerequisite must be active and valid at admission creation time:

- `queue-observation-receipt-status-v1.lifecycle = active`;
- `queue-observation-receipt-status-v1.disposition = observation_recorded`;
- `queue-observation-receipt-result-v1` success, if supplied by an injected
  reader, contains the same record and status;
- `queue-observation-v1.observation_state =
  observed_recorded_not_consumable`;
- `enqueue-receipt-evidence-v1.receipt_state =
  receipt_recorded_for_contract_eligible_enqueue`;
- `enqueue-receipt-evidence-v1.receipt_disposition = contract_eligible`;
- `payload_present = false`;
- `executable = false`;
- `effect_attempted = false`;
- `queue_observation_recorded = true` only on successful v0.43 record/status/
  result fields where the v0.43 contract already permits it.

The receipt can prove only that the exact v0.42 item was recorded as
contract-eligible observation evidence. It cannot prove live availability for
dequeue, queue ordering, exclusive ownership in a broker, claimability,
leaseability, acknowledgement, no-redelivery, worker visibility, execution
eligibility, retry eligibility, resend eligibility, or installation success.

## 6. Closed vocabulary

Lifecycle is exactly `active | expired`. Admission state is exactly:

- `controlled_dequeue_admission_recorded`
- `readiness_gated`
- `blocked`
- `indeterminate`

Eligibility decision is exactly:

- `eligible_for_later_dequeue_consideration`
- `not_eligible_for_later_dequeue_consideration`

Every successful record carries these ordered blockers:

1. `dequeue_not_defined`
2. `queue_polling_not_defined`
3. `queue_claim_not_defined`
4. `queue_lease_not_defined`
5. `queue_ack_not_defined`
6. `worker_start_not_defined`
7. `execution_start_boundary_not_defined`

The closed ordered blocker vocabulary is:

- `installation_capability_unsupported`
- `evidence_not_found`
- `ownership_mismatch`
- `permission_scope_missing`
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
- `reservation_before_effect_failed`
- `permanent_subject_reserved`
- `idempotency_conflict`
- `append_indeterminate`
- `dequeue_not_defined`
- `queue_polling_not_defined`
- `queue_claim_not_defined`
- `queue_lease_not_defined`
- `queue_ack_not_defined`
- `worker_start_not_defined`
- `execution_start_boundary_not_defined`

Audit events are exactly `controlled_dequeue_admission_recorded`,
`controlled_dequeue_admission_read`, and
`controlled_dequeue_admission_indeterminate`. Unknown lifecycle values,
admission states, eligibility decisions, blockers, audit events, errors, or
authority labels fail closed.

Home Assistant remains the blocked golden state: it always returns `blocked`
with first blocker `installation_capability_unsupported`, records no
controlled dequeue admission, remains non-installable and non-executable, and
creates no deployment artifact or exception.

## 7. Canonical primitives and bounds

All models are immutable and closed. Unknown keys, duplicate JSON keys,
invalid UTF-8, non-NFC strings, non-finite numbers, unbounded nesting, and
contrary fixed booleans fail closed.

- UUIDs are canonical lowercase UUIDv4 unless explicitly derived as UUIDv5.
- Operator IDs are visible ASCII matching
  `[A-Za-z0-9][A-Za-z0-9._:-]{0,127}`.
- Timestamps are UTC RFC 3339 whole seconds ending in `Z`; clients supply none.
- Fingerprints use SHA-256 over `atlas-jcs-nfc-v1` canonical JSON after NFC
  normalization and are lowercase 64-character hexadecimal strings.
- POST bodies are at most 16 KiB with nesting depth 16.
- Records/results are at most 128 KiB.
- Collections contain at most 100 records.
- Store quota is at most 16 records per operator.
- Idempotency keys are 16-128 visible ASCII characters and are never stored,
  logged, returned, audited, or rendered raw.
- Identifiers other than UUIDs and operator IDs are visible ASCII, contain no
  whitespace-only value, and are at most 128 characters.

Fingerprint objects retain the released shape:

```yaml
algorithm: sha256
canonicalization: atlas-jcs-nfc-v1
value: <64 lowercase hexadecimal characters>
```

Domain separation is mandatory:

- `atlas:controlled-dequeue-admission-request:v1`
- `atlas:controlled-dequeue-admission-lineage:v1`
- `atlas:controlled-dequeue-admission-queue-identity:v1`
- `atlas:controlled-dequeue-admission-item-identity:v1`
- `atlas:controlled-dequeue-admission-observation-linkage:v1`
- `atlas:controlled-dequeue-admission-decision:v1`
- `atlas:controlled-dequeue-admission-subject:v1`
- `atlas:controlled-dequeue-admission-idempotency:v1`
- `atlas:controlled-dequeue-admission-reservation:v1`
- `atlas:controlled-dequeue-admission-record:v1`
- `atlas:controlled-dequeue-admission-status:v1`
- `atlas:controlled-dequeue-admission-audit:v1`
- `atlas:controlled-dequeue-admission-error:v1`
- `atlas:controlled-dequeue-admission-result:v1`
- `atlas:controlled-dequeue-admission-collection:v1`
- `atlas:controlled-dequeue-admission-correlation:v1`

Fingerprints from v0.43 and prior milestones remain in their original domains
and are not interchangeable with v0.44 fingerprints.

## 8. Exact create request

`controlled-dequeue-admission-create-v1` contains exactly:

- `schema = controlled-dequeue-admission-create-v1`
- `queue_observation_receipt_id`
- `queue_observation_receipt_fingerprint`
- `queue_observation_receipt_status_fingerprint`
- `queue_observation_receipt_valid_until`
- `queue_observation_id`
- `queue_observation_fingerprint`
- `enqueue_receipt_evidence_fingerprint`
- `one_shot_live_enqueue_id`
- `one_shot_live_enqueue_fingerprint`
- `one_shot_live_enqueue_status_fingerprint`
- `inert_queue_item_id`
- `inert_queue_item_fingerprint`
- `worker_queue_reservation_id`
- `worker_queue_reservation_fingerprint`
- `queue_intake_reference_id`
- `queue_intake_reference_fingerprint`
- `queue_item_reference_id`
- `queue_item_reference_fingerprint`
- `inherited_limits_fingerprint`
- `requested_scope = installation_controlled_dequeue_admission_only`
- `admission_intent = later_dequeue_consideration_only`
- `reference_only = true`
- `observation_required = true`
- `receipt_required = true`
- `payload_schema_defined = false`
- `payload_constructed = false`
- `payload_serialized = false`
- `dequeue_allowed = false`
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
complete v0.20-v0.43 evidence, queue identity, item identity, eligibility
decision, audit facts, and admission decision are server-owned dependencies.

The body cannot contain raw prior evidence, queue names, broker endpoints,
credentials, payloads, commands, images, paths, arbitrary metadata,
timestamps, permissions, authority overrides, worker execution requests,
dequeue instructions, polling instructions, consumer configuration, claim
instructions, lease instructions, acknowledgement instructions, retry
instructions, resend instructions, scheduler instructions, workflow
instructions, Agent requests, callback instructions, or queue mutation
instructions.

## 9. Exact lineage

`controlled-dequeue-admission-lineage-v1` contains exactly:

```yaml
schema: controlled-dequeue-admission-lineage-v1
operator_id: <operator id>
candidate_record_id: <uuid4>
v020_v042_chain_fingerprint: <fingerprint-v1>
v042_enqueue_id: <uuid5>
v042_enqueue_record_fingerprint: <fingerprint-v1>
v042_enqueue_status_fingerprint: <fingerprint-v1>
v042_queue_item_id: <uuid5>
v042_queue_item_fingerprint: <fingerprint-v1>
v043_receipt_id: <uuid5>
v043_receipt_record_fingerprint: <fingerprint-v1>
v043_receipt_status_fingerprint: <fingerprint-v1>
v043_queue_observation_fingerprint: <fingerprint-v1>
v043_enqueue_receipt_evidence_fingerprint: <fingerprint-v1>
queue_identity_fingerprint: <fingerprint-v1>
item_identity_fingerprint: <fingerprint-v1>
inherited_limits_fingerprint: <fingerprint-v1>
earliest_upstream_expiry: <timestamp>
lineage_fingerprint: <fingerprint-v1>
```

The lineage must be exact and same-owner from v0.20 through v0.43. No caller
may supply a summarized lineage in place of server-side reconstruction.

## 10. Exact admission decision

`controlled-dequeue-admission-decision-v1` contains exactly:

- `schema = controlled-dequeue-admission-decision-v1`
- `operator_id`
- `candidate_record_id`
- `receipt_id`
- `inert_queue_item_id`
- `evaluated_at`
- `valid_until`
- `eligibility_decision`
- `recognized_exact_v043_receipt_count`
- `recognized_exact_v042_inert_item_count`
- `recognized_same_owner_lineage`
- `recognized_contract_eligible_receipt`
- `recognized_inert_reference_only_item`
- `recognized_no_payload`
- `recognized_no_prior_dequeue`
- `later_dequeue_consideration_allowed = true` only for a successful
  admission record
- `dequeue_allowed = false`
- `queue_polling_allowed = false`
- `queue_claim_allowed = false`
- `queue_lease_allowed = false`
- `queue_ack_allowed = false`
- `worker_start_allowed = false`
- `execution_start_allowed = false`
- `decision_fingerprint`

The successful decision can say only that the exact item is eligible for a
future, separately authorized dequeue boundary to consider. It cannot say that
the item is live, available, ordered, exclusive, claimable, leasable,
acknowledgeable, executable, installable, retriable, resendable, or already
dequeued.

## 11. Record, status, result, audit, and error schemas

`controlled-dequeue-admission-v1` contains exactly its schema, admission UUIDv5,
owner and candidate IDs, trusted `recorded_at`, `valid_until`,
`record_state = recorded`, lifecycle, admission state
`controlled_dequeue_admission_recorded`, eligibility decision, ordered
blockers, exact v0.43 observation/receipt linkage, exact v0.42 queue item
identity, queue identity, item identity, lineage, inherited limits
fingerprint, idempotency fingerprint, request fingerprint, admission-subject
fingerprint, record fingerprint, audit evidence, and fixed authority from
section 17.

`controlled-dequeue-admission-status-v1` contains exactly admission/owner/
candidate IDs, lifecycle, admission state, eligibility decision, ordered
blockers, `evaluated_at`, `valid_until`, record fingerprint, status
fingerprint, and fixed authority.

`controlled-dequeue-admission-result-v1` contains exactly `schema`, `ok`,
`outcome = success | failure | indeterminate`, nullable closed record,
nullable closed status, nullable closed redacted error, correlation
fingerprint, and fixed authority. Success returns a record and status.
Failure returns only a redacted error. Indeterminate returns only a redacted
error with no retry authority and a permanent reservation.

`controlled-dequeue-admission-collection-v1` contains exactly `schema`, owner
and candidate IDs, ordered immutable `items`, `count`, collection fingerprint,
and fixed authority. Items are ordered by `(recorded_at, admission_id)`.

`controlled-dequeue-admission-error-v1` permits only closed safe codes derived
from the blocker vocabulary plus `unauthenticated`, `forbidden`, `not_found`,
`invalid_request`, `rate_limited`, `quota_exceeded`, `conflict`,
`record_too_large`, `store_corrupt`, and `internal_error`. It contains only
schema, code, fixed sanitized message, retryable (always false), correlation
fingerprint, redaction marker, and fixed authority. Foreign and missing
records both return `not_found`.

## 12. Ownership and permissions

Every operation requires an authenticated operator. Create requires exactly
`installation.execution.controlled_dequeue_admission.record`. List/get require
exactly `installation.execution.controlled_dequeue_admission.read`. The frozen
scope is `installation_controlled_dequeue_admission_only`.

Candidate, v0.43 observation receipt record, v0.43 status, v0.43 receipt
evidence, v0.43 queue observation, embedded v0.42 enqueue record, embedded
v0.42 queue item, v0.42 status, v0.41 admission, v0.40 worker intake
admission, v0.39 queue reservation, queue intake reference, queue item
reference, admission record, idempotency reservation, subject reservation,
status, and audit ownership must all equal the authenticated operator. No
caller-supplied identity, permission, receipt, queue identity, item identity,
or authority flag is trusted. Foreign and absent evidence are
indistinguishable.

Authentication and permission never imply dequeue, queue polling, claim,
lease, acknowledgement, queue mutation, worker start, Agent invocation,
execution, installation, dispatch, scheduler, workflow, deployment, rollback,
retry, resend, or mutation authority.

## 13. Freshness and lifecycle

The service uses a trusted server clock. At create time, the complete
v0.20-v0.43 chain, active v0.43 observation receipt record, active v0.43
status, active v0.42 enqueue record, active v0.42 queue item, active v0.41
live enqueue admission, active v0.40 worker intake admission, active v0.39
queue reservation, queue identity, item identity, and inherited limits must
be fresh and unexpired.

V0.44 cannot extend any predecessor: `valid_until` is the earliest upstream
expiry and is never more than 30 seconds after trusted `recorded_at`.
Prerequisite facts older than 30 seconds, facts from the future, or facts
whose source time is ambiguous fail closed. Boundary equality is expired.

Expired admission records remain readable as immutable evidence but cannot be
refreshed, renewed, replaced, superseded, consumed, retried, resent, released,
or used to create another record. Expiry causes no background work, callback,
cleanup, dequeue, polling, claim, lease, acknowledgement, queue mutation,
worker contact, Agent invocation, scheduler signal, workflow signal, runtime
signal, or execution signal.

## 14. Reservation before append and no replay

`controlled-dequeue-admission-idempotency-reservation-v1` and
`controlled-dequeue-admission-subject-reservation-v1` contain only schema,
owner/candidate IDs, hashed identifiers, request/admission-subject
fingerprints, admission/record IDs, `reserved_at`, `reservation_state`, and
`permanent = true`.

Reservation must complete durably before the admission record is appended. The
admission subject is the tuple `(owner, candidate, v0.43 receipt record
fingerprint, v0.43 receipt status fingerprint, v0.43 queue observation
fingerprint, v0.43 enqueue receipt evidence fingerprint, v0.42 enqueue record
fingerprint, v0.42 queue item fingerprint, v0.42 status fingerprint, v0.39
queue reservation fingerprint, queue intake reference fingerprint, queue item
reference fingerprint, queue identity fingerprint, item identity fingerprint,
inherited limits fingerprint)`.

One subject can produce at most one controlled dequeue admission record
forever. An exact retry returns the existing record without re-reading
evidence or contacting anything. Same key/different request or same
subject/different key is a permanent conflict.

Reservations cannot be consumed, released, refreshed, replaced, superseded,
retried, resent, repaired, garbage-collected, or bypassed, including after
expiry, restart, corruption, timeout, lost response, or indeterminate append.
Ambiguous append completion is recorded as indeterminate, keeps the permanent
reservation, returns a redacted error, and never permits reconstruction as new
work.

## 15. Ambiguity handling

Ambiguity is terminal and non-authorizing. If Core cannot prove whether the
exact same-owner inert v0.42 item is backed by one active valid v0.43
observation receipt record, it must classify the admission as `blocked` or
`indeterminate`, preserve only bounded redacted evidence, and keep any
completed subject reservation permanent.

Ambiguous, missing, stale, mismatched, foreign, malformed, corrupt, duplicate,
or oversized prerequisite evidence cannot be retried, resent, polled,
reconciled by worker contact, repaired by raw logs, or converted into success
by UI action. No ambiguity path releases a reservation, creates a partial
consumable item, constructs a payload, contacts a queue broker or worker,
starts dequeue or polling, claims or leases a queue item, acknowledges a queue
item, invokes Agent, invokes a workflow, starts execution, or starts an
effect.

## 16. Bounded evidence and redaction

Controlled dequeue admission evidence is bounded proof, not a queue transcript
or worker handoff. Records, errors, logs, metrics, audits, API responses, and
UI projections never disclose raw idempotency keys, credentials, endpoints,
addresses, queue names, broker details, payloads, commands, arguments,
environment, logs, paths, hostnames, ports, sockets, repository paths, guest
paths, mount sources, provider payloads, exception text, stack traces,
foreign-owner facts, raw receipt documents, claim handles, lease handles,
acknowledgement handles, consumer group names, or queue client configuration.

Redaction must preserve enough safe structure to audit owner, candidate,
schema, closed blocker, lifecycle, status, v0.42/v0.43 fingerprint linkage,
freshness, and fixed-false authority without revealing sensitive transport or
execution material.

## 17. Fixed non-authorizing posture

Every record, status, result, collection, audit, decision, and error fixes
these fields:

- `reference_only = true`
- `admission_only = true`
- `later_dequeue_consideration_only = true`
- `queue_observation_required = true`
- `enqueue_receipt_required = true`
- `payload_schema_defined = false`
- `payload_constructed = false`
- `payload_serialized = false`
- `payload_bytes = 0`
- `raw_receipt_persisted = false`
- `raw_queue_identity_persisted = false`
- `dequeue_defined = false`
- `dequeue_allowed = false`
- `dequeued = false`
- `queue_polling_allowed = false`
- `queue_consumer_defined = false`
- `queue_claim_allowed = false`
- `queue_claimed = false`
- `queue_lease_allowed = false`
- `queue_leased = false`
- `queue_ack_allowed = false`
- `queue_acknowledged = false`
- `queue_item_consumed = false`
- `queue_item_removed = false`
- `queue_item_mutated = false`
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

The only authority field allowed to be true in a successful record is
`controlled_dequeue_admission_recorded = true`. No field may be omitted,
renamed, defaulted to true, inferred from permission, inherited from v0.43 or
v0.42, or overridden by configuration.

## 18. API boundary

The only future Core surface is:

- `GET /api/v1/installation/candidate-records/{candidate_record_id}/controlled-dequeue-admissions`
- `POST /api/v1/installation/candidate-records/{candidate_record_id}/controlled-dequeue-admissions`
- `GET /api/v1/installation/candidate-records/{candidate_record_id}/controlled-dequeue-admissions/{admission_id}`

GET has no body or query parameters. POST requires authentication, the record
permission, trusted origin, CSRF, rate limiting, `Content-Type:
application/json`, the strict bounded body, and an `Idempotency-Key` of 16-128
visible ASCII characters. List/get require the read permission and owner scope.

No PUT, PATCH, DELETE, action subroute, or sibling dequeue/poll/claim/lease/
ack/consume/remove/mutate/replace/worker/start/run/execute/dispatch/retry/
resend/install/deploy/rollback/agent/workflow/scheduler route is permitted.
P0 registers no permission, dependency, store, route, setting, OpenAPI
operation, UI client, serializer, worker client, credential, endpoint,
migration, payload schema, queue library, broker integration, consumer,
scheduler, workflow, Agent, or execution-worker integration.

## 19. Default-off construction

No v0.44 runtime object may be ambiently available. Later phases must use
explicit construction with injected owner-scoped v0.43 and v0.42 readers,
injected store, injected trusted clock, explicit enabled flag, and explicit
permission checks. The default constructor state is disabled and cannot
admit, append, reserve, read, contact, poll, claim, lease, acknowledge,
consume, mutate, execute, or infer by side effect.

Configuration cannot enable dequeue, polling, queue claim, queue lease, queue
acknowledgement, queue item consumption, queue item removal, queue item
mutation, queue item replacement, worker contact, worker start, Agent
invocation, scheduler/workflow execution, Docker, Podman, container, shell,
process execution, installation, mutation, deployment, rollback, retry,
resend, credential loading, endpoint resolution, broker access, queue consumer
creation, or Home Assistant artifact creation. Production imports alone must
not construct the service.

## 20. Mission Control boundary

P4 may add strict typing for only the three P3 endpoints and an optional
nested evidence panel under the owned v0.43 queue observation receipt evidence
in the existing v0.41-v0.43 worker flow. It may present lifecycle,
eligibility decision, ordered blockers, exact v0.43 observation/receipt
binding, exact v0.42 enqueue and queue item binding, queue identity
fingerprint, item identity fingerprint, lineage, inherited ceilings,
freshness/expiry, Core-supplied owner context, audit evidence, permanent
no-replay, fixed-false authority, and redacted errors.

Creation may be shown only when Core supplies eligible server-owned v0.43
observation receipt context, and must use a two-step acknowledgement stating:
"Record controlled dequeue admission evidence only. This does not dequeue,
poll, claim, lease, acknowledge, consume, remove, mutate, or replace a queue
item; contact or start a worker; invoke Agent or a workflow; dispatch; retry;
resend; install; deploy; roll back; mutate; or execute anything."

Mission Control must not add polling, standalone navigation, live queue or
worker selectors, editable limits, raw/sensitive fields, arbitrary metadata,
or controls/labels for dequeue, poll, claim, lease, ack, consume, remove,
replace, worker start, run, execute, install, deploy, dispatch, retry/resend,
send-to-Agent, start-workflow, scheduler, rollback, Docker, Podman, container,
shell, process execution, or mutation.

## 21. Goldens

The canonical success golden is one authenticated same-owner request with the
dedicated record permission, one active valid v0.43 queue observation receipt
record, exact v0.20-v0.43 lineage, exact v0.42 inert queue item identity,
exact v0.43 observation and enqueue receipt linkage, exact intended queue
identity, exact inherited limits, and an unused idempotency key and admission
subject. It produces exactly one durable
`controlled_dequeue_admission_recorded` record, eligibility decision
`eligible_for_later_dequeue_consideration`, ordered blockers for undefined
dequeue, queue polling, queue claim, queue lease, queue acknowledgement,
worker start, and execution start, no sensitive output, and no downstream
consumer.

The exact duplicate golden returns the same record without re-reading evidence
or appending anything. Same key/different request and same subject/different
key are permanent conflicts. Foreign-owner and absent records are
indistinguishable. Home Assistant is blocked with no admission and no
artifact. Missing, stale, ambiguous, mismatched, expired, unsupported,
malformed, corrupt, executable-payload, reservation failure, and indeterminate
append cases fail closed and never create dequeue, polling, claim, lease,
acknowledgement, queue mutation, worker, Agent, scheduler, workflow,
retry/resend, or execution authority.

## 22. Threat model

Validation and tests in later phases must cover foreign-owner probing,
caller-forged identity, timestamps, permissions, references, scopes, queue
identity, item identity, observation receipt linkage, or authority; nested-link
substitution; stale or expired v0.43 evidence; stale or expired v0.42
evidence; v0.43 receipt mismatch; v0.43 queue observation mismatch; v0.42
enqueue mismatch; v0.42 inert item mismatch; v0.39 queue-reservation
mismatch; v0.39 queue intake reference substitution; v0.39 queue item
reference substitution; inherited-limit relaxation; duplicate-key/schema
smuggling; idempotency conflict; concurrent or post-restart subject replay;
reservation-before-effect failure; indeterminate append completion; store
corruption; raw receipt leakage; sensitive error/audit/UI rendering;
accidental payload schemas; accidental queue clients; accidental dequeue,
polling, claim, lease, acknowledgement, consume, remove, mutate, or replace
authority; live worker contact; and Agent, scheduler, workflow, or
execution-worker consumers.

Every condition fails closed. No failure releases a permanent reservation,
creates a partial consumable item, serializes a payload, contacts a queue
broker or worker, starts dequeue or polling, claims or leases a queue item,
acknowledges a queue item, invokes Agent, starts a scheduler or workflow, or
starts an effect.

## 23. Must-not-change authority boundaries

V0.44 must not change v0.43 schemas, v0.43 permissions, v0.43 scope, v0.43
fixed blockers, v0.43 fixed-false authority fields, v0.43 permanent
reservations, v0.42 schemas, v0.42 permissions, v0.42 scope, v0.42 inert item
semantics, v0.42 fixed blockers, v0.42 fixed-false authority fields, v0.42
permanent reservations, v0.41 admission semantics, v0.40 worker intake
semantics, v0.39 queue reservation semantics, Agent behavior,
execution-worker behavior, provider behavior, repository behavior, deployment
behavior, rollback behavior, or `compose.execution-smoke.override.yaml`.

Controlled dequeue admission evidence must remain downstream of v0.43
observation receipt evidence and upstream of no effect. It can be a
prerequisite for a later separately frozen dequeue boundary, but it cannot
itself define or start dequeue.

## 24. P0-P5 delivery plan

- **P0 - frozen planning contract (this change):** planning/roadmap documents
  only; no runtime model, service, store, migration, setting, permission,
  route, OpenAPI operation, UI code, queue library, payload schema,
  serializer, worker client, credential, endpoint, background task, Agent
  change, execution-worker change, dequeue, polling, claim, lease,
  acknowledgement, consume, remove, queue-item mutation, replacement, worker
  start/contact, Agent invocation, scheduler/workflow execution,
  installation, dispatch, execution authorization/start, retry/resend,
  deployment, rollback, mutation behavior, or change to
  `compose.execution-smoke.override.yaml`.
- **P1 - closed Core models:** immutable schemas, deterministic fingerprints,
  bounds, exact v0.20-v0.43 lineage validation, exact v0.43 observation/
  receipt linkage, exact v0.42 inert queue item and queue identity validation,
  eligibility decision validation, Home Assistant golden, fixed blockers,
  redaction, and fixed-false authority; no service or persistence.
- **P2 - explicit evidence service/store:** create/list/get only, injected
  owner-scoped v0.43 and prerequisite readers, append-only bounded store,
  atomic permanent idempotency-key and admission subject reservations,
  reservation-before-append, exact-duplicate zero-I/O readback, restart-safe
  ownership, indeterminate append handling, and corruption fail-closed; no
  production consumer.
- **P3 - guarded Core API:** only the frozen collection GET/POST and item GET,
  with exact authentication, record/read permissions, origin/CSRF/rate/parsing,
  ownership, error, OpenAPI, and isolation tests.
- **P4 - Mission Control evidence presentation:** strict create/list/get
  client and optional nested evidence presentation only, with redaction and
  structural absence of polling, queue selectors, sensitive rendering, extra
  mutations, and effect controls.
- **P5 - release closure:** exact v0.43 and v0.42 prerequisite linkage,
  eligibility goldens, concurrency, permanent single-use/no-replay, terminal
  ambiguous outcomes, bounded/redacted/secret-free persistence, API/UI limits,
  default-off construction, Agent/worker/execution-worker zero-consumer
  isolation, Home Assistant blocked behavior, and no dequeue, queue polling,
  claim, lease, acknowledgement, consume, remove, queue-item mutation,
  replacement, worker/Agent invocation, execution, retry/resend, scheduler/
  workflow, install, mutation, deployment, rollback, or Compose smoke override
  change.
