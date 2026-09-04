# Queue Observation and Enqueue Receipt Evidence v1 planning contract

Status: **Atlas v0.43 P0 frozen planning contract**.

This document freezes the v0.43 Queue Observation and Enqueue Receipt
Evidence boundary before runtime work. It starts from the completed v0.42
One-Shot Live Enqueue Boundary as implemented in
`installation_one_shot_live_enqueue`: the exact inert
`one-shot-live-enqueue-v1` record, its exact
`one-shot-live-enqueue-item-v1` queue item, its exact
`one-shot-live-enqueue-lineage-v1` lineage, and its fixed-false authority
posture are prerequisites and may not be reinterpreted.

V0.43 defines one future evidence authority: Core may preserve bounded proof
that the exact inert v0.42 queue item was accepted by, or observed at, the
queue identity already intended by the v0.39-v0.42 lineage. Observation is
evidence only. It is not a consumer, claim, dequeue, worker signal, scheduler
signal, Agent signal, retry, resend, or execution trigger.

The authority invariant is:

`queue_observation_recorded == bounded evidence about one exact inert v0.42 queue item at its intended queue`

and:

`queue_observation_recorded != dequeue != queue polling consumer != worker start != Agent invocation != execution`

Observation evidence must not authorize or cause dequeue, queue-driven action,
worker start or invocation, Agent invocation, execution, retry/resend,
scheduler or workflow execution, Docker, Podman, container, shell, or process
execution, installation, provider mutation, repository mutation, in-guest
mutation, deployment, or rollback.

## 1. Authority boundary

V0.43 may authenticate an operator, require a dedicated observation-record
permission, re-read one owned active v0.42 one-shot live enqueue record,
recompute the v0.20-v0.42 lineage and fingerprints, verify the v0.42 inert
queue item identity, verify the v0.39 queue reservation and queue intake
reference that define the intended queue, verify byte-exact inherited
sandbox/resource/network/filesystem ceilings, accept or derive bounded
non-sensitive enqueue receipt facts, classify those facts as accepted,
observed, missing, stale, ambiguous, or mismatched, reserve the observation
subject before append, append one immutable Core-owned observation record, and
return owned readback.

It may not publish another item, retry or resend the v0.42 item, poll as a
consumer, claim, lease, acknowledge, dequeue, subscribe to a work stream,
contact or start a worker, bind a runner, invoke Agent, invoke a workflow,
start a scheduler, dispatch, execute a process, start Docker, Podman,
container, shell, or other process execution, install, mutate a provider,
repository, or guest, deploy, roll back, load credentials, resolve endpoints,
or create Home Assistant artifacts.

No v0.43 output is consumable by worker, dispatch, provider, repository,
guest, deployment, rollback, scheduler, workflow, Agent, execution-worker,
or process-execution paths. A future milestone that wants to consume queue
state must define a separate authority boundary and must treat v0.43 as
read-only prerequisite evidence only.

## 2. Frozen v0.42 prerequisite lineage

V0.43 binds exactly one owned v0.42 `one-shot-live-enqueue-v1` record whose
successful state is `one_shot_live_enqueue_recorded`. The prerequisite record
must retain:

- schema `one-shot-live-enqueue-v1`;
- scope `installation_one_shot_live_enqueue_only`;
- successful blockers `dequeue_not_defined`,
  `queue_polling_not_defined`, `worker_start_not_defined`, and
  `execution_start_boundary_not_defined`;
- exact `one-shot-live-enqueue-lineage-v1` fields and fingerprints;
- exact `one-shot-live-enqueue-item-v1` queue item fields and fingerprint;
- permanent idempotency and subject reservation fingerprints;
- byte-exact inherited limits fingerprint;
- fixed-false v0.42 authority fields.

V0.43 does not modify, renew, replace, supersede, release, consume, or
reclassify v0.42 records, items, reservations, status, audit, or errors.
Expired v0.42 records remain readable evidence but cannot create new v0.43
observation records. Boundary equality is expired.

The v0.20-v0.42 lineage must be reconstructed from owner-scoped readers. A
summary fingerprint never replaces validation of exact nested fields. Missing,
foreign, malformed, stale, expired, mismatched, unsupported, corrupt, or
ambiguous prerequisite evidence fails closed without partial observation
output and without reservation release.

## 3. Queue identity

The intended queue identity is not caller-supplied. It is derived from the
owned v0.42 record and its v0.39-v0.42 lineage:

- authenticated operator ID;
- candidate record ID;
- v0.39 worker queue reservation ID and fingerprint;
- v0.39 queue reservation status fingerprint;
- v0.39 queue intake reference ID and fingerprint;
- v0.39 queue item reference ID and fingerprint;
- v0.40 worker intake admission ID and fingerprint;
- v0.41 live enqueue admission ID and fingerprint;
- v0.42 enqueue ID and record fingerprint;
- v0.42 queue item ID and item fingerprint;
- inherited limits fingerprint.

The queue identity is abstract evidence identity only. It must not contain or
render a broker address, queue name, topic, stream, subscription, endpoint,
hostname, port, socket, credential, route key, consumer group, lease name,
visibility timeout, callback, or queue client configuration. Any supplied or
observed raw transport identity is redacted and may contribute only to a
bounded fingerprint if required by a later implementation.

## 4. Queue-item identity

The observed item identity is exactly the v0.42 `queue_item_id`, which equals
the v0.42 `enqueue_id` and the v0.42 lineage
`one_shot_queue_item_id`. The item fingerprint must equal the v0.42
`queue_item.item_fingerprint` and lineage `one_shot_queue_item_fingerprint`.

V0.43 cannot construct a new payload, payload schema, envelope, worker
request, serialized message, command, environment, repository path, guest
path, image, mount, callback, lease, claim, acknowledgement, retry policy, or
consumer pointer. It observes only the exact inert reference-only queue item
already recorded by v0.42.

## 5. Closed vocabulary

Lifecycle is exactly `active | expired`. Disposition is exactly:

- `accepted_by_intended_queue`
- `observed_at_intended_queue`
- `receipt_missing`
- `receipt_stale`
- `receipt_ambiguous`
- `receipt_mismatched`
- `blocked`
- `indeterminate`

The strongest successful outcome is `queue_observation_recorded`.

Every successful record carries these ordered blockers:

1. `dequeue_not_defined`
2. `queue_polling_consumer_not_defined`
3. `worker_start_not_defined`
4. `agent_invocation_not_defined`
5. `execution_start_boundary_not_defined`

The closed ordered blocker vocabulary is:

- `installation_capability_unsupported`
- `evidence_not_found`
- `ownership_mismatch`
- `permission_scope_missing`
- `v042_enqueue_not_found`
- `v042_enqueue_not_active`
- `v042_enqueue_not_recorded`
- `v042_lineage_mismatch`
- `queue_identity_mismatch`
- `queue_item_identity_mismatch`
- `enqueue_receipt_missing`
- `enqueue_receipt_stale`
- `enqueue_receipt_ambiguous`
- `enqueue_receipt_mismatched`
- `fingerprint_mismatch`
- `evidence_stale`
- `evidence_expired`
- `inherited_limits_mismatch`
- `reservation_before_effect_failed`
- `permanent_subject_reserved`
- `idempotency_conflict`
- `append_indeterminate`
- `dequeue_not_defined`
- `queue_polling_consumer_not_defined`
- `worker_start_not_defined`
- `agent_invocation_not_defined`
- `execution_start_boundary_not_defined`

Audit events are exactly `queue_observation_recorded`,
`queue_observation_read`, and `queue_observation_indeterminate`. Unknown
lifecycle values, dispositions, outcomes, blockers, audit events, errors, or
authority labels fail closed.

Home Assistant remains the blocked golden state: it always returns `blocked`
with first blocker `installation_capability_unsupported`, records no
observation, remains non-installable and non-executable, and creates no
deployment artifact or exception.

## 6. Canonical primitives and bounds

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
- Enqueue receipt evidence is at most 8 KiB before canonicalization and must
  be reduced to bounded schema fields and fingerprints before persistence.
- Identifiers other than UUIDs and operator IDs are visible ASCII, contain no
  whitespace-only value, and are at most 128 characters.

Fingerprint objects retain the released shape:

```yaml
algorithm: sha256
canonicalization: atlas-jcs-nfc-v1
value: <64 lowercase hexadecimal characters>
```

Domain separation is mandatory:

- `atlas:queue-observation-request:v1`
- `atlas:queue-observation-queue-identity:v1`
- `atlas:queue-observation-item-identity:v1`
- `atlas:queue-observation-enqueue-receipt:v1`
- `atlas:queue-observation-lineage:v1`
- `atlas:queue-observation-subject:v1`
- `atlas:queue-observation-idempotency:v1`
- `atlas:queue-observation-reservation:v1`
- `atlas:queue-observation-record:v1`
- `atlas:queue-observation-status:v1`
- `atlas:queue-observation-audit:v1`
- `atlas:queue-observation-error:v1`
- `atlas:queue-observation-result:v1`
- `atlas:queue-observation-collection:v1`
- `atlas:queue-observation-correlation:v1`

Fingerprints from v0.42 and prior milestones remain in their original domains
and are not interchangeable with v0.43 fingerprints.

## 7. Exact create request

`queue-observation-create-v1` contains exactly:

- `schema = queue-observation-create-v1`
- `one_shot_live_enqueue_id`
- `one_shot_live_enqueue_fingerprint`
- `one_shot_live_enqueue_status_fingerprint`
- `one_shot_queue_item_id`
- `one_shot_queue_item_fingerprint`
- `worker_queue_reservation_id`
- `worker_queue_reservation_fingerprint`
- `queue_intake_reference_id`
- `queue_intake_reference_fingerprint`
- `queue_item_reference_id`
- `queue_item_reference_fingerprint`
- `live_enqueue_admission_id`
- `live_enqueue_admission_fingerprint`
- `worker_intake_admission_id`
- `worker_intake_admission_fingerprint`
- `inherited_limits_fingerprint`
- `requested_scope = installation_queue_observation_only`
- `receipt_evidence_intent = enqueue_receipt_observation_only`
- `reference_only = true`
- `observation_only = true`
- `payload_schema_defined = false`
- `payload_constructed = false`
- `payload_serialized = false`
- `dequeue_allowed = false`
- `queue_polling_allowed = false`
- `worker_start_allowed = false`
- `agent_invocation_allowed = false`
- `execution_authorized = false`
- `retry_allowed = false`
- `resend_allowed = false`
- `replay_allowed = false`

The body supplies references only. Operator identity, candidate identity,
permission result, trusted request time, idempotency key, correlation value,
complete v0.20-v0.42 evidence, queue identity, enqueue receipt facts,
observation disposition, audit facts, and observation decision are server-owned
dependencies.

The body cannot contain raw prior evidence, queue names, broker endpoints,
credentials, payloads, commands, images, paths, arbitrary metadata,
timestamps, permissions, authority overrides, worker execution requests,
dequeue instructions, polling instructions, consumer configuration, retry
instructions, resend instructions, scheduler instructions, workflow
instructions, Agent requests, or callback instructions.

## 8. Enqueue receipt linkage

`queue-observation-enqueue-receipt-v1` contains exactly:

- `schema = queue-observation-enqueue-receipt-v1`
- `receipt_id` (derived UUIDv5)
- `owner_operator_id`
- `candidate_record_id`
- `one_shot_live_enqueue_id`
- `one_shot_live_enqueue_fingerprint`
- `one_shot_queue_item_id`
- `one_shot_queue_item_fingerprint`
- `queue_identity_fingerprint`
- `item_identity_fingerprint`
- `receipt_source = core_owned_bounded_observation`
- `receipt_kind = enqueue_acceptance_or_presence_evidence`
- `receipt_disposition`
- `receipt_observed_at`
- `valid_until`
- `receipt_fingerprint`
- `raw_receipt_persisted = false`
- `raw_queue_identity_persisted = false`
- `payload_bytes = 0`
- `dequeue_defined = false`
- `queue_consumer_defined = false`
- `worker_signal_defined = false`
- `execution_signal_defined = false`

The receipt can prove only that the exact v0.42 item was accepted by or
observed at the intended abstract queue identity. It cannot prove delivery to
a worker, worker visibility, queue ordering, availability for dequeue,
claimability, leaseability, acknowledgement, no-redelivery, execution
eligibility, retry eligibility, resend eligibility, or installation success.

Receipt facts must be bounded evidence, not raw transport transcripts. Allowed
facts are limited to receipt source classification, trusted observation time,
closed disposition, queue identity fingerprint, item identity fingerprint,
receipt fingerprint, and redacted diagnostic class. Raw broker responses,
transport headers, addresses, tokens, credentials, payload bytes, message
bodies, logs, exception text, and stack traces are forbidden.

## 9. Observation schema

`queue-observation-v1` contains exactly its schema, observation UUIDv5,
owner and candidate IDs, trusted `recorded_at`, `valid_until`,
`record_state = recorded`, lifecycle, outcome
`queue_observation_recorded`, disposition, ordered blockers, v0.42 lineage
linkage, queue identity, item identity, enqueue receipt, inherited limits
fingerprint, idempotency fingerprint, request fingerprint, observation-subject
fingerprint, record fingerprint, audit evidence, and fixed authority from
section 17.

`queue-observation-status-v1` contains exactly observation/owner/candidate
IDs, lifecycle, outcome, disposition, ordered blockers, `evaluated_at`,
`valid_until`, record fingerprint, status fingerprint, and fixed authority.

`queue-observation-result-v1` contains exactly `schema`, `ok`,
`outcome = success | failure | indeterminate`, nullable closed record,
nullable closed status, nullable closed redacted error, correlation
fingerprint, and fixed authority. Success returns a record and status.
Failure returns only a redacted error. Indeterminate returns only a redacted
error with no retry authority and a permanent reservation.

`queue-observation-collection-v1` contains exactly `schema`, owner and
candidate IDs, ordered immutable `items`, `count`, collection fingerprint,
and fixed authority. Items are ordered by `(recorded_at, observation_id)`.

## 10. Ownership and permissions

Every operation requires an authenticated operator. Create requires exactly
`installation.execution.queue_observation.record`; list/get requires exactly
`installation.execution.queue_observation.read`. The frozen scope is
`installation_queue_observation_only`.

Candidate, v0.42 enqueue record, v0.42 queue item, v0.41 admission, v0.40
worker intake admission, v0.39 queue reservation, queue intake reference,
queue item reference, enqueue receipt evidence, observation record,
idempotency reservation, subject reservation, status, and audit ownership must
all equal the authenticated operator. No caller-supplied identity, permission,
receipt, or queue identity is trusted. Foreign and absent evidence are
indistinguishable.

Authentication and permission never imply dequeue, queue polling consumer,
worker start, Agent invocation, execution, installation, dispatch, scheduler,
workflow, deployment, rollback, retry, resend, or mutation authority.

## 11. Freshness and lifecycle

The service uses a trusted server clock. At create time, the complete
v0.20-v0.42 chain, active v0.42 enqueue record, active v0.41 live enqueue
admission, active v0.40 worker intake admission, active v0.39 queue
reservation, queue identity, item identity, and enqueue receipt observation
must be fresh and unexpired.

V0.43 cannot extend any predecessor: `valid_until` is the earliest upstream
expiry and is never more than 30 seconds after trusted `recorded_at`.
Observation receipt facts older than 30 seconds, facts from the future, or
facts whose source time is ambiguous fail closed. Boundary equality is expired.

Expired observation records remain readable as immutable evidence but cannot
be refreshed, renewed, replaced, superseded, consumed, retried, resent,
released, or used to create another record. Expiry causes no background work,
callback, cleanup, dequeue, polling, worker contact, Agent invocation,
scheduler signal, workflow signal, or runtime signal.

## 12. Reservation before append and no replay

`queue-observation-idempotency-reservation-v1` and
`queue-observation-subject-reservation-v1` contain only schema,
owner/candidate IDs, hashed identifiers, request/observation-subject
fingerprints, observation/record IDs, `reserved_at`, `reservation_state`, and
`permanent = true`.

Reservation must complete durably before the observation record is appended.
The observation subject is the tuple `(owner, candidate, v0.42 enqueue
fingerprint, v0.42 queue item fingerprint, v0.42 status fingerprint, v0.39
queue reservation fingerprint, queue intake reference fingerprint, queue item
reference fingerprint, queue identity fingerprint, item identity fingerprint,
enqueue receipt fingerprint, inherited limits fingerprint)`.

One subject can produce at most one observation record forever. An exact retry
returns the existing record without re-reading evidence or contacting
anything. Same key/different request or same subject/different key is a
permanent conflict.

Reservations cannot be consumed, released, refreshed, replaced, superseded,
retried, resent, repaired, garbage-collected, or bypassed, including after
expiry, restart, corruption, timeout, lost response, or indeterminate append.
Ambiguous append completion is recorded as indeterminate, keeps the permanent
reservation, returns a redacted error, and never permits reconstruction as new
work.

## 13. Ambiguity handling

Ambiguity is terminal and non-authorizing. If Core cannot prove whether the
exact inert v0.42 item was accepted by or observed at the intended queue, it
must classify the disposition as `receipt_ambiguous` or the outcome as
`indeterminate`, preserve only bounded redacted evidence, and keep any
completed subject reservation permanent.

Ambiguous, missing, stale, mismatched, foreign, malformed, corrupt, duplicate,
or oversized receipt evidence cannot be retried, resent, polled, reconciled by
worker contact, repaired by raw logs, or converted into success by UI action.
No ambiguity path releases a reservation, creates a partial consumable item,
constructs a payload, contacts a queue broker or worker, starts dequeue or
polling, invokes Agent, invokes a workflow, starts execution, or starts an
effect.

## 14. Bounded evidence and redaction

Observation evidence is bounded proof, not a transcript. Records, errors,
logs, metrics, audits, API responses, and UI projections never disclose raw
idempotency keys, credentials, endpoints, addresses, queue names, broker
details, payloads, commands, arguments, environment, logs, paths, hostnames,
ports, sockets, repository paths, guest paths, mount sources, provider
payloads, exception text, stack traces, foreign-owner facts, or raw receipt
documents.

`queue-observation-error-v1` permits only closed safe codes derived from the
blocker vocabulary plus `unauthenticated`, `forbidden`, `not_found`,
`invalid_request`, `rate_limited`, `quota_exceeded`, `conflict`,
`record_too_large`, `store_corrupt`, and `internal_error`. It contains only
schema, code, fixed sanitized message, retryable (always false), correlation
fingerprint, redaction marker, and fixed authority. Foreign and missing
records both return `not_found`.

## 15. API boundary

The only future Core surface is:

- `GET /api/v1/installation/candidate-records/{candidate_record_id}/queue-observations`
- `POST /api/v1/installation/candidate-records/{candidate_record_id}/queue-observations`
- `GET /api/v1/installation/candidate-records/{candidate_record_id}/queue-observations/{observation_id}`

GET has no body or query parameters. POST requires authentication, the record
permission, trusted origin, CSRF, rate limiting, `Content-Type:
application/json`, the strict bounded body, and an `Idempotency-Key` of 16-128
visible ASCII characters. List/get require the read permission and owner scope.

No PUT, PATCH, DELETE, action subroute, or sibling dequeue/poll/claim/lease/
ack/worker/start/run/execute/dispatch/retry/resend/install/deploy/rollback/
agent/workflow/scheduler route is permitted. P0 registers no permission,
dependency, store, route, setting, OpenAPI operation, UI client, serializer,
worker client, credential, endpoint, migration, payload schema, queue library,
broker integration, consumer, scheduler, workflow, Agent, or execution-worker
integration.

## 16. Default-off construction

No v0.43 runtime object may be ambiently available. Later phases must use
explicit construction with injected owner-scoped readers, injected bounded
receipt source, injected store, injected trusted clock, explicit enabled flag,
and explicit permission checks. The default constructor state is disabled and
cannot observe, append, reserve, read, contact, poll, or infer by side effect.

Configuration cannot enable dequeue, polling, worker contact, worker start,
Agent invocation, scheduler/workflow execution, Docker, Podman, container,
shell, process execution, installation, mutation, deployment, rollback,
retry, resend, credential loading, endpoint resolution, broker access, queue
consumer creation, or Home Assistant artifact creation. Production imports
alone must not construct the service.

## 17. Fixed non-authorizing posture

Every record, status, result, collection, audit, receipt, and error fixes
these fields:

- `reference_only = true`
- `observation_only = true`
- `enqueue_receipt_evidence_only = true`
- `payload_schema_defined = false`
- `payload_constructed = false`
- `payload_serialized = false`
- `payload_bytes = 0`
- `raw_receipt_persisted = false`
- `raw_queue_identity_persisted = false`
- `dequeue_defined = false`
- `dequeue_allowed = false`
- `queue_polling_allowed = false`
- `queue_consumer_defined = false`
- `queue_claim_allowed = false`
- `queue_lease_allowed = false`
- `queue_ack_allowed = false`
- `worker_contact_allowed = false`
- `worker_authentication_allowed = false`
- `worker_binding_allowed = false`
- `worker_start_allowed = false`
- `agent_invocation_allowed = false`
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
`queue_observation_recorded = true`. No field may be omitted, renamed,
defaulted to true, inferred from permission, inherited from v0.42, or
overridden by configuration.

## 18. Mission Control boundary

P4 may add strict typing for only the three P3 endpoints and an optional
nested evidence panel under the owned v0.42 one-shot live enqueue evidence in
the existing v0.41 worker flow. It may present lifecycle, disposition, ordered
blockers, exact v0.42 enqueue and queue item binding, queue identity
fingerprint, item identity fingerprint, enqueue receipt fingerprint, lineage,
inherited ceilings, freshness/expiry, Core-supplied owner context, audit
evidence, permanent no-replay, fixed-false authority, and redacted errors.

Creation may be shown only when Core supplies eligible server-owned v0.42
one-shot live enqueue context, and must use a two-step acknowledgement
stating: "Record bounded queue observation evidence only. This does not
dequeue, poll as a consumer, claim, lease, acknowledge, contact or start a
worker, invoke Agent or a workflow, dispatch, retry, resend, install, deploy,
roll back, mutate, or execute anything."

Mission Control must not add polling, standalone navigation, live queue or
worker selectors, editable limits, raw/sensitive fields, arbitrary metadata,
or controls/labels for dequeue, poll, claim, lease, ack, worker start, run,
execute, install, deploy, dispatch, retry/resend, send-to-Agent,
start-workflow, scheduler, rollback, Docker, Podman, container, shell,
process execution, or mutation.

## 19. Goldens

The canonical success golden is one authenticated same-owner request with the
dedicated record permission, one active v0.42 one-shot live enqueue record,
exact v0.20-v0.42 lineage, exact intended queue identity, exact inert v0.42
queue item identity, exact inherited limits, one bounded receipt showing
acceptance by or observation at the intended queue, and an unused idempotency
key and observation subject. It produces exactly one durable
`queue_observation_recorded` record, an accepted or observed disposition,
ordered blockers for undefined dequeue, queue polling consumer, worker start,
Agent invocation, and execution start, no sensitive output, and no downstream
consumer.

The exact duplicate golden returns the same record without re-reading evidence
or appending anything. Same key/different request and same subject/different
key are permanent conflicts. Foreign-owner and absent records are
indistinguishable. Home Assistant is blocked with no observation and no
artifact. Missing, stale, ambiguous, mismatched, expired, unsupported,
malformed, corrupt, reservation failure, and indeterminate append cases fail
closed and never create dequeue, polling-consumer, worker, Agent, scheduler,
workflow, retry/resend, or execution authority.

## 20. Threat model

Validation and tests in later phases must cover foreign-owner probing,
caller-forged identity, timestamps, permissions, references, scopes, queue
identity, receipt evidence, or authority; nested-link substitution; stale or
expired v0.42 evidence; v0.42 enqueue mismatch; v0.42 queue item mismatch;
v0.39 queue-reservation mismatch; v0.39 queue intake reference substitution;
v0.39 queue item reference substitution; inherited-limit relaxation;
duplicate-key/schema smuggling; idempotency conflict; concurrent or
post-restart subject replay; reservation-before-effect failure;
indeterminate append completion; store corruption; raw receipt leakage;
sensitive error/audit/UI rendering; accidental payload schemas; accidental
queue clients; accidental dequeue/polling consumers; live worker contact; and
Agent, scheduler, workflow, or execution-worker consumers.

Every condition fails closed. No failure releases a permanent reservation,
creates a partial consumable item, serializes a payload, contacts a queue
broker or worker, starts dequeue/polling, invokes Agent, starts a scheduler or
workflow, or starts an effect.

## 21. Must-not-change authority boundaries

V0.43 must not change v0.42 schemas, v0.42 permissions, v0.42 scope, v0.42
fixed blockers, v0.42 fixed-false authority fields, v0.42 permanent
reservations, v0.41 admission semantics, v0.40 worker intake semantics, v0.39
queue reservation semantics, Agent behavior, execution-worker behavior,
provider behavior, repository behavior, deployment behavior, rollback
behavior, or `compose.execution-smoke.override.yaml`.

Observation evidence must remain downstream of v0.42 enqueue evidence and
upstream of no effect. It can be a prerequisite for a later separately frozen
consumer boundary, but it cannot itself define the consumer.

## 22. P0-P5 delivery plan

- **P0 - frozen planning contract (this change):** planning/roadmap documents
  only; no runtime model, service, store, migration, setting, permission,
  route, OpenAPI operation, UI code, queue library, payload schema, serializer,
  worker client, credential, endpoint, background task, Agent change,
  execution-worker change, dequeue, polling, claim, lease, acknowledgement,
  worker start/contact, Agent invocation, scheduler/workflow execution,
  installation, dispatch, execution, retry/resend, deployment, rollback,
  mutation behavior, or change to `compose.execution-smoke.override.yaml`.
- **P1 - closed Core models:** immutable schemas, deterministic fingerprints,
  bounds, exact v0.20-v0.42 lineage validation, exact v0.42 queue item and
  queue identity validation, closed receipt dispositions, Home Assistant
  golden, fixed blockers, redaction, and fixed-false authority; no service or
  persistence.
- **P2 - explicit evidence service/store:** create/list/get only, injected
  owner-scoped v0.42 and prerequisite readers, injected bounded receipt source,
  append-only bounded store, atomic permanent idempotency-key and observation
  subject reservations, reservation-before-append, exact-duplicate zero-I/O
  readback, restart-safe ownership, indeterminate append handling, and
  corruption fail-closed; no production consumer.
- **P3 - guarded Core API:** only the frozen collection GET/POST and item GET,
  with exact authentication, record/read permissions, origin/CSRF/rate/parsing,
  ownership, error, OpenAPI, and isolation tests.
- **P4 - Mission Control evidence presentation:** strict create/list/get client
  and optional nested evidence presentation only, with redaction and structural
  absence of polling, sensitive rendering, extra mutations, and effect
  controls.
- **P5 - release closure:** exact v0.42 prerequisite linkage, receipt
  disposition goldens, concurrency, permanent single-use/no-replay, terminal
  ambiguous outcomes, bounded/redacted/secret-free persistence, API/UI limits,
  default-off construction, Agent/worker/execution-worker zero-consumer
  isolation, Home Assistant blocked behavior, and no dequeue, queue polling
  consumer, worker/Agent invocation, execution, retry/resend, scheduler/
  workflow, install, mutation, deployment, rollback, or Compose smoke override
  change.
