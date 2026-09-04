# One-Shot Live Enqueue Boundary v1 planning contract

Status: **Atlas v0.42 P0 frozen planning contract**.

This document freezes the v0.42 One-Shot Live Enqueue Boundary before runtime
work. It defines exactly one new future authority: after a valid same-owner
v0.41 Live Enqueue Admission, Core may perform one explicitly authorized,
single-use enqueue of one inert reference-only queue item. The item is an
immutable reference artifact only; it contains no executable payload and has no
consumer in v0.42.

The authority invariant is:

`one_shot_live_enqueue_recorded == one inert reference-only queue item`

and:

`one_shot_live_enqueue_recorded != dequeue != queue polling != worker start != execution`

The v0.42 item is not a worker request, payload envelope, lease, claim,
dispatch handoff, runner binding, Agent request, workflow step, installation
request, provider mutation, repository mutation, in-guest mutation,
deployment, rollback, credential, endpoint, shell command, process request, or
container request.

## 1. Authority boundary

V0.42 may authenticate an operator, require a dedicated one-shot enqueue
permission, re-read one active same-owner v0.41 live enqueue admission record,
recompute the complete v0.20-v0.41 lineage and fingerprints, verify the active
v0.39 queue reservation, v0.40 worker intake admission, v0.40 worker identity,
v0.40 worker intake reference, v0.39 queue intake reference, v0.39 queue item
reference, and v0.41 admission subject, verify byte-exact inherited sandbox,
resource, network, and filesystem ceilings, evaluate freshness and earliest
inherited expiry, reserve one enqueue item subject before any enqueue effect,
append one inert reference-only queue item record, and return owned readback.

It may not define or serialize an executable payload, poll, claim, lease,
acknowledge, dequeue, contact or start a worker, bind a runner, invoke Agent or
a workflow, dispatch, retry, resend, execute a process, start Docker, Podman,
shell, container, or other process execution, install, mutate a provider,
repository, or guest, deploy, roll back, load credentials, resolve endpoints,
or create Home Assistant artifacts. No v0.42 output is consumable by worker,
dispatch, provider, repository, guest, deployment, rollback, scheduler,
workflow, Agent, execution-worker, or process-execution paths.

## 2. Closed vocabulary

Lifecycle is exactly `active | expired`. Outcome is exactly
`one_shot_live_enqueue_recorded | readiness_gated | blocked |
indeterminate`.

Every successful record carries these ordered blockers:

1. `dequeue_not_defined`
2. `queue_polling_not_defined`
3. `worker_start_not_defined`
4. `execution_start_boundary_not_defined`

The closed ordered blocker vocabulary is:

- `installation_capability_unsupported`
- `evidence_not_found`
- `ownership_mismatch`
- `permission_scope_missing`
- `linkage_mismatch`
- `fingerprint_mismatch`
- `evidence_stale`
- `evidence_expired`
- `live_enqueue_admission_not_active`
- `live_enqueue_admission_not_recorded`
- `queue_reservation_not_active`
- `worker_intake_admission_not_active`
- `worker_identity_ineligible`
- `worker_intake_reference_ineligible`
- `queue_intake_reference_ineligible`
- `queue_item_reference_ineligible`
- `inherited_limits_mismatch`
- `reservation_before_effect_failed`
- `permanent_subject_reserved`
- `idempotency_conflict`
- `append_indeterminate`
- `dequeue_not_defined`
- `queue_polling_not_defined`
- `worker_start_not_defined`
- `execution_start_boundary_not_defined`

Audit events are exactly `one_shot_live_enqueue_recorded`,
`one_shot_live_enqueue_read`, and `one_shot_live_enqueue_indeterminate`.
Unknown lifecycle values, outcomes, blockers, audit events, errors, or
authority labels fail closed.

Home Assistant remains the blocked golden state: it always returns `blocked`
with first blocker `installation_capability_unsupported`, produces no queue
item, remains non-installable and non-executable, and creates no deployment
artifact or exception.

## 3. Canonical primitives and bounds

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
- The P2 store quota is at most 16 records per operator.
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

- `atlas:one-shot-live-enqueue-request:v1`
- `atlas:one-shot-live-enqueue-item-subject:v1`
- `atlas:one-shot-live-enqueue-item:v1`
- `atlas:one-shot-live-enqueue-lineage:v1`
- `atlas:one-shot-live-enqueue-idempotency:v1`
- `atlas:one-shot-live-enqueue-reservation:v1`
- `atlas:one-shot-live-enqueue-record:v1`
- `atlas:one-shot-live-enqueue-status:v1`
- `atlas:one-shot-live-enqueue-audit:v1`
- `atlas:one-shot-live-enqueue-error:v1`
- `atlas:one-shot-live-enqueue-result:v1`
- `atlas:one-shot-live-enqueue-collection:v1`
- `atlas:one-shot-live-enqueue-correlation:v1`

Fingerprints from prior milestones remain in their original domains and are
not interchangeable with v0.42 fingerprints.

## 4. Exact create request

`one-shot-live-enqueue-create-v1` contains exactly:

- `schema = one-shot-live-enqueue-create-v1`
- `live_enqueue_admission_id`
- `live_enqueue_admission_fingerprint`
- `live_enqueue_admission_status_fingerprint`
- `live_enqueue_admission_valid_until`
- `worker_intake_admission_id`
- `worker_intake_admission_fingerprint`
- `worker_queue_reservation_id`
- `worker_queue_reservation_fingerprint`
- `worker_identity_id`
- `worker_identity_fingerprint`
- `worker_intake_reference_id`
- `worker_intake_reference_fingerprint`
- `queue_intake_reference_id`
- `queue_intake_reference_fingerprint`
- `queue_item_reference_id`
- `queue_item_reference_fingerprint`
- `inherited_limits_fingerprint`
- `requested_scope = installation_one_shot_live_enqueue_only`
- `reference_only = true`
- `payload_schema_defined = false`
- `payload_constructed = false`
- `payload_serialized = false`
- `dequeue_allowed = false`
- `queue_polling_allowed = false`
- `worker_start_allowed = false`
- `execution_authorized = false`
- `retry_allowed = false`
- `resend_allowed = false`
- `replay_allowed = false`

The body supplies references only. Operator identity, candidate identity,
permission result, trusted request time, idempotency key, correlation value,
complete v0.20-v0.41 evidence, queue item contents, audit facts, and enqueue
decision are server-owned dependencies. The body cannot contain raw prior
evidence, queue names, broker endpoints, credentials, payloads, commands,
images, paths, arbitrary metadata, timestamps, permissions, authority
overrides, worker execution requests, or dequeue instructions.

## 5. Exact queue item

`one-shot-live-enqueue-item-v1` contains exactly:

- `schema = one-shot-live-enqueue-item-v1`
- `queue_item_id` (derived UUIDv5)
- `owner_operator_id`
- `candidate_record_id`
- `live_enqueue_admission_id`
- `live_enqueue_admission_fingerprint`
- `live_enqueue_admission_status_fingerprint`
- `worker_queue_reservation_id`
- `worker_queue_reservation_fingerprint`
- `worker_intake_admission_id`
- `worker_intake_admission_fingerprint`
- `worker_identity_id`
- `worker_identity_fingerprint`
- `worker_intake_reference_id`
- `worker_intake_reference_fingerprint`
- `queue_intake_reference_id`
- `queue_intake_reference_fingerprint`
- `queue_item_reference_id`
- `queue_item_reference_fingerprint`
- `item_kind = inert_reference_only_queue_item`
- `trust_domain = atlas-installation`
- `scope = installation_one_shot_live_enqueue_only`
- `reference_only = true`
- `item_state = recorded`
- `recorded_at`
- `valid_until`
- `lineage_fingerprint`
- `inherited_limits_fingerprint`
- `item_fingerprint`
- `payload_schema_defined = false`
- `payload_constructed = false`
- `payload_serialized = false`
- `payload_bytes = 0`
- `dequeue_defined = false`
- `dequeued = false`
- `queue_polled = false`
- `queue_claimed = false`
- `queue_leased = false`
- `worker_contacted = false`
- `worker_started = false`
- `execution_allowed = false`

The queue item is a durable Core-owned reference artifact. It has no queue
broker address, queue name, worker endpoint, credential, payload, command,
environment, repository path, guest path, image, log, callback, lease, claim,
acknowledgement, visibility timeout, retry policy, or consumer pointer.

## 6. Exact lineage

`one-shot-live-enqueue-lineage-v1` contains exactly:

```yaml
schema: one-shot-live-enqueue-lineage-v1
operator_id: <operator id>
candidate_record_id: <uuid4>
live_enqueue_admission_linkage: <exact live-enqueue-admission-linkage-v1>
v020_v040_chain_fingerprint: <fingerprint-v1>
v020_v041_chain_fingerprint: <fingerprint-v1>
readiness_review_fingerprint: <v0.34 fingerprint-v1>
permission_grant_fingerprint: <v0.35 fingerprint-v1>
execution_admission_id: <v0.36 uuid4>
execution_admission_fingerprint: <fingerprint-v1>
runner_binding_plan_id: <v0.37 uuid4>
runner_binding_plan_fingerprint: <fingerprint-v1>
worker_admission_stub_id: <v0.38 uuid4>
worker_admission_stub_fingerprint: <fingerprint-v1>
queue_reservation_id: <v0.39 uuid4>
queue_reservation_fingerprint: <fingerprint-v1>
queue_reservation_status_fingerprint: <fingerprint-v1>
queue_intake_reference_id: <v0.39 uuid4>
queue_intake_reference_fingerprint: <fingerprint-v1>
queue_item_reference_id: <v0.39 derived uuid5>
queue_item_reference_fingerprint: <fingerprint-v1>
worker_intake_admission_id: <v0.40 uuid4>
worker_intake_admission_fingerprint: <fingerprint-v1>
worker_intake_admission_status_fingerprint: <fingerprint-v1>
worker_identity_id: <v0.40 uuid4>
worker_identity_fingerprint: <fingerprint-v1>
worker_intake_reference_id: <v0.40 uuid4>
worker_intake_reference_fingerprint: <fingerprint-v1>
live_enqueue_admission_id: <v0.41 derived uuid5>
live_enqueue_admission_fingerprint: <fingerprint-v1>
live_enqueue_admission_status_fingerprint: <fingerprint-v1>
live_enqueue_admission_subject_fingerprint: <fingerprint-v1>
live_enqueue_admission_decision_fingerprint: <fingerprint-v1>
one_shot_queue_item_id: <derived uuid5>
one_shot_queue_item_fingerprint: <fingerprint-v1>
inherited_limits_fingerprint: <fingerprint-v1>
lineage_fingerprint: <fingerprint-v1>
```

The nested v0.41 linkage is the byte-exact released linkage that transitively
contains the named v0.20 durable candidate record, v0.21 approval intent,
v0.22 Agent validation evidence, v0.23 execution request, v0.24 dispatch
handoff, v0.25 intake simulation, v0.26 simulated delivery, v0.27 real intake,
v0.28 dormant delivery wiring, v0.29 activation preflight, v0.30 enablement,
v0.31 send evidence, v0.32 live intake admission, v0.33 inert receipt, v0.34
readiness review, v0.35 permission grant, v0.36 execution admission, v0.37
runner binding plan, v0.38 worker admission stub, v0.39 queue reservation,
v0.40 worker intake admission, and v0.41 live enqueue admission fingerprints.
A summary fingerprint never replaces validation of exact nested fields.

Core reconstructs the complete chain with injected owner-scoped readers. The
request cannot substitute raw evidence. Every ID, owner, subject, scope,
fingerprint, status, blocker, and expiry must match byte-for-byte. Missing,
foreign, malformed, stale, expired, mismatched, unsupported, corrupt, or
ambiguous elements fail closed without partial output or reservation release.

## 7. Prerequisite v0.41 binding

V0.42 binds exactly one active v0.41 live enqueue admission record. That record
must bind exactly one active v0.40 worker intake admission, one active v0.39
queue reservation, one server-owned worker identity, one abstract worker
intake reference, one abstract queue intake reference, and one inert queue item
reference. The submitted references must equal the IDs and fingerprints inside
the v0.41 record and recomputed lineage.

The v0.41 successful blockers remain live blockers in v0.42 and cannot be
removed, softened, reordered, or reinterpreted. V0.42 changes only the one
previously undefined enqueue step by defining a single inert reference-only
item. Dequeue, queue polling, claim, lease, worker start, and execution start
remain undefined.

## 8. Inherited ceilings

`inherited_limits` must equal the v0.37 runner-binding limits byte-for-byte as
inherited through v0.38, v0.39, v0.40, and v0.41. The v0.42 request, lineage,
queue item, record, and status fingerprints must all agree on the same
inherited limits fingerprint.

V0.42 cannot loosen, replace, negotiate, supplement, or claim enforcement of
the ceilings:

- sandbox profile `atlas-installation-confined-v1`; non-privileged; no
  escalation, host namespaces, host devices, or capabilities; seccomp and
  AppArmor required;
- CPU <= 1000 millis, memory <= 536870912 bytes, PIDs <= 64, wall time <= 900
  seconds, output <= 1048576 bytes;
- network mode `none`; ingress, egress, DNS, image pull, and allowed endpoints
  are all absent/false;
- read-only root; no host, repository, or guest mount; only an abstract
  ephemeral workspace up to 268435456 bytes may be described.

These are inherited evidence ceilings only. No sandbox, filesystem, network
namespace, workspace, container, worker, or process is created, contacted, or
inspected.

## 9. Record, status, result, and collection

`one-shot-live-enqueue-v1` contains exactly its schema, enqueue UUIDv5, owner
and candidate IDs, trusted `recorded_at`, `valid_until`,
`record_state = recorded`, lifecycle, outcome, ordered blockers, lineage,
queue item, inherited limits, idempotency fingerprint, request fingerprint,
item-subject fingerprint, record fingerprint, audit evidence, and fixed
authority from section 14.

`one-shot-live-enqueue-status-v1` contains exactly enqueue/owner/candidate
IDs, lifecycle, outcome, ordered blockers, `evaluated_at`, `valid_until`,
record fingerprint, status fingerprint, and fixed authority.

`one-shot-live-enqueue-result-v1` contains exactly `schema`, `ok`,
`outcome = success | failure | indeterminate`, nullable closed record,
nullable closed status, nullable closed redacted error, correlation
fingerprint, and fixed authority. Success returns a record and status.
Failure returns only a redacted error. Indeterminate returns only a redacted
error with no retry authority and a permanent reservation.

`one-shot-live-enqueue-collection-v1` contains exactly `schema`, owner and
candidate IDs, ordered immutable `items`, `count`, collection fingerprint, and
fixed authority. Items are ordered by `(recorded_at, enqueue_id)`.

## 10. Auth, ownership, and permissions

Every operation requires an authenticated operator. Create requires exactly
`installation.execution.one_shot_live_enqueue.record`; list/get requires
exactly `installation.execution.one_shot_live_enqueue.read`. The frozen scope
is `installation_one_shot_live_enqueue_only`.

Candidate, v0.41 admission, v0.39 reservation, v0.40 worker intake admission,
worker identity, worker intake reference, queue intake reference, queue item
reference, v0.42 item, idempotency reservation, subject reservation, record,
status, and audit ownership must all equal the authenticated operator. No
caller-supplied identity or permission is trusted. Foreign and absent evidence
are indistinguishable. Authentication and permission never imply dequeue,
queue polling, worker start, execution, installation, dispatch, Agent,
workflow, deployment, rollback, or mutation authority.

## 11. Freshness and expiry

The service uses a trusted server clock. At create time, the entire
v0.20-v0.41 chain, active v0.41 live enqueue admission, active v0.40 worker
intake admission, active v0.39 queue reservation, worker identity, worker
intake reference, queue intake reference, and queue item reference must be
fresh and unexpired. V0.42 cannot extend any predecessor: `valid_until` is the
earliest upstream expiry and is never more than 30 seconds after trusted
`recorded_at`. Boundary equality is expired.

Expired records remain readable as immutable evidence but cannot be refreshed,
renewed, replaced, superseded, consumed, retried, resent, released, or used to
create another record. Expiry causes no background work, callback, cleanup,
dequeue, polling, worker contact, or runtime signal.

## 12. Reservation before effect and no replay

`one-shot-live-enqueue-idempotency-reservation-v1` and
`one-shot-live-enqueue-subject-reservation-v1` contain only schema,
owner/candidate IDs, hashed identifiers, request/item-subject fingerprints,
enqueue/record IDs, `reserved_at`, `reservation_state`, and
`permanent = true`.

Reservation must complete durably before the inert queue item record is
appended. The item subject is the tuple `(owner, candidate, v0.41 admission
fingerprint, v0.41 admission status fingerprint, v0.39 reservation
fingerprint, v0.40 worker intake admission fingerprint, worker identity
fingerprint, worker intake reference fingerprint, queue intake reference
fingerprint, queue item reference fingerprint, inherited limits fingerprint)`.
One subject can produce at most one queue item forever. An exact retry returns
the existing record without re-reading evidence or contacting anything. Same
key/different request or same subject/different key is a permanent conflict.

Reservations cannot be consumed, released, refreshed, replaced, superseded,
retried, resent, repaired, garbage-collected, or bypassed, including after
expiry, restart, corruption, timeout, lost response, or indeterminate append.
Ambiguous append completion is recorded as indeterminate, keeps the permanent
reservation, returns a redacted error, and never permits reconstruction as new
work.

## 13. Success, failure, and indeterminate outcomes

Success means exactly one inert reference-only queue item record is durable and
readable by its owner. Failure means no item was appended and no future retry
is authorized unless it is an exact duplicate returning an already durable
success. Indeterminate means reservation-before-effect completed but append
completion cannot be proven; the subject remains permanently reserved and
cannot be retried, resent, released, reconstructed, or consumed.

No outcome starts a worker, exposes a dequeue path, creates a queue consumer,
schedules polling, starts execution, or emits a signal to Agent, workflow,
execution-worker, provider, repository, guest, deployment, rollback, shell,
container, Docker, or Podman paths.

## 14. Fixed non-authorizing posture

Every record, status, result, collection, audit, and error fixes these fields:

- `reference_only = true`
- `payload_schema_defined = false`
- `payload_constructed = false`
- `payload_serialized = false`
- `payload_bytes = 0`
- `dequeue_defined = false`
- `dequeue_allowed = false`
- `queue_polling_allowed = false`
- `queue_claim_allowed = false`
- `queue_lease_allowed = false`
- `queue_ack_allowed = false`
- `worker_contact_allowed = false`
- `worker_authentication_allowed = false`
- `worker_binding_allowed = false`
- `worker_start_allowed = false`
- `execution_start_allowed = false`
- `runner_binding_allowed = false`
- `dispatch_allowed = false`
- `retry_allowed = false`
- `resend_allowed = false`
- `agent_invocation_allowed = false`
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
`one_shot_live_enqueue_recorded = true`. No field may be omitted, renamed,
defaulted to true, inferred from permission, or overridden by configuration.

## 15. Redaction and audit

`one-shot-live-enqueue-audit-v1` permits only
`one_shot_live_enqueue_recorded`, `one_shot_live_enqueue_read`, and
`one_shot_live_enqueue_indeterminate`, with audit UUID,
owner/candidate/enqueue IDs, trusted time, outcome, correlation fingerprint,
item-subject fingerprint, record fingerprint, and audit fingerprint. There is
no dequeue, poll, claim, lease, worker start, dispatch, execution, network,
process, installation, or mutation event.

`one-shot-live-enqueue-error-v1` permits only closed safe codes derived from
the blocker vocabulary plus `unauthenticated`, `forbidden`, `not_found`,
`invalid_request`, `rate_limited`, `quota_exceeded`, `conflict`,
`record_too_large`, `store_corrupt`, and `internal_error`. It contains only
schema, code, fixed sanitized message, retryable (always false), correlation
fingerprint, and fixed authority. Foreign and missing records both return
`not_found`.

Errors, logs, metrics, audits, API responses, and UI projections never disclose
raw idempotency keys, credentials, endpoints, addresses, queue names, broker
details, payloads, commands, arguments, environment, logs, paths, hostnames,
ports, sockets, repository paths, guest paths, mount sources, provider
payloads, exception text, stack traces, or foreign-owner facts.

## 16. API boundary

The only future Core surface is:

- `GET /api/v1/installation/candidate-records/{candidate_record_id}/one-shot-live-enqueues`
- `POST /api/v1/installation/candidate-records/{candidate_record_id}/one-shot-live-enqueues`
- `GET /api/v1/installation/candidate-records/{candidate_record_id}/one-shot-live-enqueues/{enqueue_id}`

GET has no body or query parameters. POST requires authentication, the record
permission, trusted origin, CSRF, rate limiting, `Content-Type:
application/json`, the strict bounded body, and an `Idempotency-Key` of 16-128
visible ASCII characters. List/get require the read permission and owner scope.

No PUT, PATCH, DELETE, action subroute, or sibling dequeue/poll/claim/lease/
worker/start/run/execute/dispatch/retry/resend/install/deploy/rollback route
is permitted. P0 registers no permission, dependency, store, route, setting,
OpenAPI operation, UI client, serializer, worker client, credential, endpoint,
migration, payload schema, queue library, or broker integration.

## 17. Default-off construction

No v0.42 runtime object may be ambiently available. Later phases must use
explicit construction with injected owner-scoped readers, injected store,
injected trusted clock, explicit enabled flag, and explicit permission checks.
The default constructor state is disabled and cannot append, reserve, or read
by side effect.

Configuration cannot enable dequeue, polling, worker contact, worker start,
Agent invocation, scheduler/workflow execution, Docker, Podman, container,
shell, process execution, installation, mutation, deployment, rollback,
retry, resend, credential loading, endpoint resolution, or Home Assistant
artifact creation. Production imports alone must not construct the service.

## 18. Mission Control boundary

P4 may add strict typing for only the three P3 endpoints and an optional nested
evidence panel under the owned v0.41 live enqueue admission in the existing
worker flow. It may present lifecycle, ordered blockers, exact v0.39-v0.41
binding, queue item reference, item fingerprint, lineage, inherited ceilings,
freshness/expiry, Core-supplied owner context, audit evidence, permanent
no-replay, fixed-false authority, and redacted errors.

Creation may be shown only when Core supplies eligible server-owned v0.41 live
enqueue admission context, and must use a two-step acknowledgement stating:
"Record one inert reference-only queue item. This does not dequeue, poll,
claim, lease, contact or start a worker, dispatch, retry, resend, install,
invoke Agent or a workflow, or execute anything."

Mission Control must not add polling, standalone navigation, live queue or
worker selectors, editable limits, raw/sensitive fields, arbitrary metadata,
or controls/labels for dequeue, poll, claim, lease, worker start, run,
execute, install, deploy, dispatch, retry/resend, send-to-Agent,
start-workflow, rollback, scheduler/workflow execution, Docker, Podman,
container, shell, process execution, or mutation.

## 19. Goldens

The canonical success golden is one authenticated same-owner request with the
dedicated record permission, one active v0.41 live enqueue admission, exact
v0.20-v0.41 lineage, exact inherited limits, and an unused idempotency key and
item subject. It produces exactly one durable
`one_shot_live_enqueue_recorded` item, ordered blockers for undefined dequeue,
queue polling, worker start, and execution start, no sensitive output, and no
downstream consumer.

The exact duplicate golden returns the same record without re-reading evidence
or appending anything. Same key/different request and same subject/different
key are permanent conflicts. Foreign-owner and absent records are
indistinguishable. Home Assistant is blocked with no item and no artifact.
Stale, expired, mismatched, unsupported, malformed, corrupt, reservation
failure, and indeterminate append cases fail closed and never create
dequeue/polling/worker/execution authority.

## 20. Threat model

Validation and tests in later phases must cover foreign-owner probing,
caller-forged identity, timestamps, permissions, references, scopes, or
authority, nested-link substitution, stale or expired evidence, v0.41
admission mismatch, v0.39 queue-reservation mismatch, v0.40
worker-intake-admission mismatch, worker identity substitution, worker intake
reference substitution, queue intake reference substitution, queue item
reference substitution, inherited-limit relaxation, duplicate-key/schema
smuggling, idempotency conflict, concurrent or post-restart subject replay,
reservation-before-effect failure, indeterminate append completion, store
corruption, sensitive error/audit/UI rendering, accidental payload schemas,
accidental queue clients, accidental dequeue/polling consumers, live worker
contact, and Agent, scheduler, workflow, or execution-worker consumers.

Every condition fails closed. No failure releases a permanent reservation,
creates a partial consumable item, serializes a payload, contacts a queue
broker or worker, starts dequeue/polling, or starts an effect.

## 21. P0-P5 delivery plan

- **P0 - frozen planning contract (this change):** planning/roadmap documents
  only; no runtime model, service, store, migration, setting, permission,
  route, OpenAPI operation, UI code, queue library, payload schema, serializer,
  worker client, credential, endpoint, background task, Agent change,
  execution-worker change, dequeue, polling, worker start/contact,
  installation, dispatch, execution, retry/resend, deployment, rollback, or
  mutation behavior.
- **P1 - closed Core models:** immutable schemas, deterministic fingerprints,
  bounds, v0.20-v0.41 lineage validation, active v0.41 state/lifecycle/
  freshness/expiry validation, v0.39-v0.41 binding, inherited-limit
  validation, Home Assistant golden, fixed blockers, redaction, and
  fixed-false authority; no service or persistence.
- **P2 - explicit evidence service/store:** create/list/get only, injected
  owner-scoped v0.41, v0.40, and v0.39 readers, append-only bounded store,
  atomic permanent idempotency-key and item-subject reservations,
  reservation-before-effect, exact-duplicate zero-I/O readback, restart-safe
  ownership, indeterminate append handling, and corruption fail-closed; no
  production consumer.
- **P3 - guarded Core API:** only the frozen collection GET/POST and item GET,
  with exact authentication, record/read permissions, origin/CSRF/rate/parsing,
  ownership, error, OpenAPI, and isolation tests.
- **P4 - Mission Control evidence presentation:** strict create/list/get client
  and optional nested evidence presentation only, with redaction and structural
  absence of polling, sensitive rendering, extra mutations, and effect
  controls.
- **P5 - release isolation and closure:** regression, authority, no-replay,
  reservation-before-effect, indeterminate outcome, Agent/execution-worker
  zero-consumer, Home Assistant non-artifact, exact API/UI isolation, release
  documentation, and full gates only.

## 22. What v0.42 enables later

V0.42 lets a future milestone require one active, same-owner, permanently
reserved inert reference-only queue item before that milestone separately
defines dequeue, polling, worker claim/lease, worker start, or execution
start. It supplies inspectable lineage, a candidate-scoped item identity,
fixed-false downstream authority, and inherited ceilings only.

It does not define dequeue, queue polling, claim, lease, worker discovery,
registration, contact, binding, or start, runner binding, execution start,
installation, dispatch, retry/resend, Agent or workflow invocation,
Docker/Podman/container/shell/process execution, provider/repository/in-guest
mutation, deployment, rollback, credentials, endpoints, or Home Assistant
deployment artifacts.

## 23. Must-not-change contracts

V0.20-v0.41 request/result schemas, linkage semantics, fingerprints,
ownership, freshness, permanent reservations, APIs, UI boundaries, authority
posture, and Home Assistant blocked golden behavior do not change. V0.42 may
read prior evidence only to validate this one inert queue item.

Dequeue, queue polling, queue claim/lease/ack, worker discovery/registration/
contact/binding/start, runner binding, execution start, dispatch, retry/resend,
Agent or workflow invocation, scheduler/workflow execution,
Docker/Podman/container/shell/process execution, installation,
provider/repository/in-guest mutation, deployment, rollback, credentials,
endpoints, and Home Assistant deployment artifacts remain blocked.

Atlas Agent and the independently gated execution-worker gain no schema,
client, callback, conversion, queue, address, credential, route, consumer,
relay, ledger, workspace, request/result binding, or behavior. P0 performs no
migration, tag, push, release publication, deployment, runtime activation, or
change to `compose.execution-smoke.override.yaml`.
