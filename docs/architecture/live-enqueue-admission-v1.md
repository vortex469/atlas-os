# Live Enqueue Admission v1 planning contract

Status: **Atlas v0.41 P0 frozen planning contract**.

This document freezes the v0.41 Live Enqueue Admission boundary before runtime
work. Live enqueue admission is one future append-only Core evidence record
that binds an exact, fresh v0.20-v0.40 chain to one active v0.40 worker intake
admission, one v0.39 queue reservation, one v0.40 worker identity, one v0.40
worker intake reference, and one derived non-enqueueing admission decision.

The authority invariant is:

`live_enqueue_admission_recorded != enqueue operation != dequeue != worker start != execution`

Admission evidence is not an enqueue operation. The strongest successful state
is `live_enqueue_admission_recorded`; it records that one exact subject passed
the live-enqueue-admission gate for future consideration only. The record is
not a queue message, payload, enqueue request, dequeue request, worker lease,
worker execution request, dispatch envelope, runner binding, capability token,
install request, workflow step, or permission to mutate.

## 1. Authority boundary

V0.41 may authenticate an operator, require a dedicated record permission,
re-read same-owner Core-local v0.40 worker intake admission evidence, re-read
the bound active v0.39 queue reservation and v0.40 worker identity/intake
reference by reference, recompute the exact v0.20-v0.40 linkage, verify
byte-exact inherited sandbox/resource/network/filesystem ceilings, evaluate
freshness and earliest inherited expiry, permanently reserve one
enqueue-admission subject, append one bounded evidence record, and return
owned readback.

It may not enqueue, serialize a payload, define a payload schema, submit a
queue message, poll, claim, lease, dequeue, contact or start a worker, bind a
runner, invoke Agent or a workflow, dispatch, retry, resend, execute a
process, install, mutate a provider, repository, or guest, deploy, roll back,
load credentials, resolve endpoints, or create Home Assistant artifacts. No
output is consumable by execution, worker, queue, dispatch, provider,
repository, guest, deployment, or rollback paths in v0.41.

## 2. Closed vocabulary

Lifecycle is exactly `active | expired`. Eligibility is exactly
`live_enqueue_admission_recorded | readiness_gated | blocked`.

Every successful record carries these ordered blockers:

1. `enqueue_operation_not_defined`
2. `dequeue_not_defined`
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
- `worker_queue_reservation_not_active`
- `worker_intake_admission_not_active`
- `worker_identity_ineligible`
- `worker_intake_reference_ineligible`
- `queue_reservation_binding_mismatch`
- `worker_intake_binding_mismatch`
- `inherited_limits_mismatch`
- `permanent_subject_reserved`
- `enqueue_operation_not_defined`
- `dequeue_not_defined`
- `worker_start_not_defined`
- `execution_start_boundary_not_defined`

Audit events are exactly `live_enqueue_admission_recorded` and
`live_enqueue_admission_read`. Authority labels are exactly the fixed fields in
section 14. Unknown lifecycle values, eligibility states, blockers, audit
events, errors, or authority labels fail closed.

Home Assistant is the blocked golden state: it always returns `blocked` with
first blocker `installation_capability_unsupported`, produces no live enqueue
admission record, remains non-installable and non-executable, and creates no
deployment artifact or exception.

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

- `atlas:live-enqueue-admission-request:v1`
- `atlas:live-enqueue-admission-enqueue-subject:v1`
- `atlas:live-enqueue-admission-decision:v1`
- `atlas:live-enqueue-admission-linkage:v1`
- `atlas:live-enqueue-admission-idempotency:v1`
- `atlas:live-enqueue-admission-subject:v1`
- `atlas:live-enqueue-admission-reservation:v1`
- `atlas:live-enqueue-admission-record:v1`
- `atlas:live-enqueue-admission-status:v1`
- `atlas:live-enqueue-admission-audit:v1`
- `atlas:live-enqueue-admission-error:v1`
- `atlas:live-enqueue-admission-result:v1`
- `atlas:live-enqueue-admission-collection:v1`
- `atlas:live-enqueue-admission-correlation:v1`

Fingerprints from prior milestones remain in their original domains and are not
interchangeable with v0.41 fingerprints.

## 4. Exact create request

`live-enqueue-admission-create-v1` contains exactly:

- `schema = live-enqueue-admission-create-v1`
- `worker_intake_admission_id`
- `worker_intake_admission_fingerprint`
- `worker_intake_admission_valid_until`
- `worker_queue_reservation_id`
- `worker_queue_reservation_fingerprint`
- `worker_identity_id`
- `worker_identity_fingerprint`
- `worker_intake_reference_id`
- `worker_intake_reference_fingerprint`
- `inherited_limits_fingerprint`
- `requested_scope = installation_live_enqueue_admission_only`
- `evidence_only = true`
- `payload_schema_defined = false`
- `payload_constructed = false`
- `enqueue_operation_allowed = false`
- `live_enqueue_allowed = false`
- `dequeue_allowed = false`
- `worker_start_allowed = false`
- `execution_authorized = false`
- `replay_allowed = false`

The body supplies references only. Operator identity, candidate identity,
permission result, trusted request time, idempotency key, correlation value,
complete v0.20-v0.40 evidence, queue-reservation contents, worker-intake
admission contents, worker identity, intake reference, admission decision, and
audit facts are server-owned dependencies. The body cannot contain raw prior
evidence, queue names, endpoints, credentials, payloads, commands, images,
paths, arbitrary metadata, timestamps, permissions, authority overrides,
worker execution requests, or enqueue operations.

## 5. Exact enqueue subject

`live-enqueue-admission-subject-v1` contains exactly:

- `schema = live-enqueue-admission-subject-v1`
- `enqueue_admission_subject_id` (derived UUIDv5)
- `owner_operator_id`
- `candidate_record_id`
- `worker_queue_reservation_id`
- `worker_queue_reservation_fingerprint`
- `worker_queue_reservation_status_fingerprint`
- `worker_intake_admission_id`
- `worker_intake_admission_fingerprint`
- `worker_intake_admission_status_fingerprint`
- `worker_identity_id`
- `worker_identity_fingerprint`
- `worker_intake_reference_id`
- `worker_intake_reference_fingerprint`
- `queue_intake_reference_id`
- `queue_intake_reference_fingerprint`
- `queue_item_reference_id`
- `queue_item_reference_fingerprint`
- `subject_kind = live_enqueue_admission_evidence_subject`
- `trust_domain = atlas-installation`
- `scope = installation_live_enqueue_admission_only`
- `eligibility = eligible_for_live_enqueue_admission_evidence_only`
- `inherited_limits`
- `inherited_limits_fingerprint`
- `valid_from`
- `valid_until`
- `enqueue_admission_subject_fingerprint`
- `payload_schema_defined = false`
- `payload_constructed = false`
- `payload_serialized = false`
- `enqueue_operation_defined = false`
- `queue_contacted = false`
- `enqueued = false`
- `dequeued = false`
- `worker_contacted = false`
- `worker_started = false`
- `execution_allowed = false`

The subject is a deterministic eligibility artifact supplied only by injected
owner-scoped readers and pure derivation. It is not a queue locator, queue item,
payload, worker endpoint, credential, lease, claim, callback, command,
environment, repository path, guest path, image, log, or provider payload.

## 6. Exact admission decision

`live-enqueue-admission-decision-v1` contains exactly:

- `schema = live-enqueue-admission-decision-v1`
- `decision_id` (derived UUIDv5)
- `owner_operator_id`
- `candidate_record_id`
- `worker_queue_reservation_id`
- `worker_queue_reservation_fingerprint`
- `worker_intake_admission_id`
- `worker_intake_admission_fingerprint`
- `worker_identity_id`
- `worker_identity_fingerprint`
- `worker_intake_reference_id`
- `worker_intake_reference_fingerprint`
- `enqueue_admission_subject_id`
- `enqueue_admission_subject_fingerprint`
- `scope = installation_live_enqueue_admission_only`
- `decision = preserve_non_enqueueing_live_enqueue_admission_evidence_only`
- `evaluated_at`
- `eligibility = live_enqueue_admission_recorded`
- `blockers`
- `inherited_limits_fingerprint`
- `decision_fingerprint`
- `payload_schema_defined = false`
- `payload_constructed = false`
- `request_serialized = false`
- `request_sent = false`
- `enqueue_operation_defined = false`
- `queue_enqueued = false`
- `queue_dequeued = false`
- `worker_contacted = false`
- `worker_started = false`
- `execution_authorized = false`

The decision is evidence only and never performs, schedules, implies, or
authorizes an enqueue operation.

## 7. Exact linkage

`live-enqueue-admission-linkage-v1` contains exactly:

```yaml
schema: live-enqueue-admission-linkage-v1
operator_id: <operator id>
candidate_record_id: <uuid4>
worker_intake_admission_linkage: <exact worker-intake-admission-linkage-v1>
worker_queue_reservation_linkage: <exact worker-queue-reservation-linkage-v1>
v020_v039_chain_fingerprint: <fingerprint-v1>
v020_v040_chain_fingerprint: <fingerprint-v1>
readiness_review_fingerprint: <v0.34 fingerprint-v1>
permission_grant_fingerprint: <v0.35 fingerprint-v1>
execution_admission_id: <v0.36 uuid4>
execution_admission_fingerprint: <fingerprint-v1>
runner_binding_plan_id: <v0.37 uuid4>
runner_binding_plan_fingerprint: <fingerprint-v1>
runner_binding_plan_status_fingerprint: <fingerprint-v1>
runner_reference_id: <v0.37 uuid4>
runner_reference_fingerprint: <fingerprint-v1>
worker_admission_stub_id: <v0.38 uuid4>
worker_admission_stub_fingerprint: <fingerprint-v1>
worker_admission_stub_status_fingerprint: <fingerprint-v1>
worker_reference_id: <v0.38 uuid4>
worker_reference_fingerprint: <fingerprint-v1>
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
worker_intake_admission_decision_fingerprint: <fingerprint-v1>
enqueue_admission_subject_id: <derived uuid5>
enqueue_admission_subject_fingerprint: <fingerprint-v1>
live_enqueue_admission_decision_fingerprint: <fingerprint-v1>
inherited_limits_fingerprint: <fingerprint-v1>
linkage_fingerprint: <fingerprint-v1>
```

The nested v0.40 linkage is the byte-exact released linkage that transitively
contains the named v0.20 durable candidate record, v0.21 approval intent,
v0.22 Agent validation evidence, v0.23 execution request, v0.24 dispatch
handoff, v0.25 intake simulation, v0.26 simulated delivery, v0.27 real intake,
v0.28 dormant delivery wiring, v0.29 activation preflight, v0.30 enablement,
v0.31 send evidence, v0.32 live intake admission, v0.33 inert receipt, v0.34
readiness review, v0.35 permission grant, v0.36 execution admission, v0.37
runner binding plan, v0.38 worker admission stub, v0.39 queue reservation, and
v0.40 worker intake admission fingerprints. A summary fingerprint never
replaces validation of exact nested fields.

Core reconstructs the complete chain with injected owner-scoped readers. The
request cannot substitute raw evidence. Every ID, owner, subject, scope,
fingerprint, status, blocker, and expiry must match byte-for-byte. Missing,
foreign, malformed, stale, expired, mismatched, unsupported, corrupt, or
ambiguous elements fail closed without partial output or reservation release.

## 8. v0.39 and v0.40 binding

V0.41 binds exactly one active v0.40 worker intake admission. That v0.40 record
must bind exactly one active v0.39 queue reservation, one server-owned worker
identity, and one abstract worker intake reference. The submitted references
must equal the IDs and fingerprints inside the v0.40 record and recomputed
linkage. The v0.39 and v0.40 successful blockers remain live blockers in
v0.41 and cannot be removed, softened, reordered, or reinterpreted.

This binding does not create a queue, queue item, payload, enqueue operation,
dequeue consumer, polling loop, claim, lease, worker start, or execution
start. A later milestone must independently define the actual enqueue
operation and must require an active v0.41 record rather than treating v0.39,
v0.40, or v0.41 evidence as an enqueue.

## 9. Inherited ceilings

`inherited_limits` must equal the v0.37 runner-binding limits byte-for-byte as
inherited through v0.38, v0.39, and v0.40. The v0.39 reservation, v0.40 worker
intake admission, enqueue subject, decision, create request, linkage, record,
and status fingerprints must all agree on the same inherited limits
fingerprint.

V0.41 cannot loosen, replace, negotiate, supplement, or claim enforcement of
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

These are evidence ceilings only. No sandbox, filesystem, network namespace,
workspace, container, queue, worker, or process is created, contacted, or
inspected.

## 10. Record, status, result, and collection

`live-enqueue-admission-v1` contains exactly its schema, admission UUIDv4,
owner and candidate IDs, trusted `recorded_at`, `valid_until`,
`record_state = recorded`, lifecycle, eligibility, ordered blockers, linkage,
enqueue admission subject, admission decision, inherited limits, idempotency
fingerprint, request fingerprint, subject fingerprint, record fingerprint,
audit evidence, and fixed authority from section 14.

`live-enqueue-admission-status-v1` contains exactly admission/owner/candidate
IDs, lifecycle, eligibility, ordered blockers, `evaluated_at`, `valid_until`,
record fingerprint, status fingerprint, and fixed authority.

`live-enqueue-admission-result-v1` contains exactly `schema`, `ok`, nullable
closed record, nullable closed redacted error, correlation fingerprint, and
fixed authority. Exactly one of record or error is present.

`live-enqueue-admission-collection-v1` contains exactly `schema`, owner and
candidate IDs, ordered immutable `items`, `count`, collection fingerprint, and
fixed authority. Items are ordered by `(recorded_at, admission_id)`.

## 11. Auth, ownership, and permissions

Every operation requires an authenticated operator. Create requires exactly
`installation.execution.live_enqueue_admission.record`; list/get requires
exactly `installation.execution.live_enqueue_admission.read`. The frozen scope
is `installation_live_enqueue_admission_only`.

Candidate, v0.39 reservation, v0.40 worker intake admission, worker identity,
intake reference, enqueue subject, decision, idempotency, subject reservation,
record, status, and audit ownership must all equal the authenticated operator.
No caller-supplied identity or permission is trusted. Foreign and absent
evidence are indistinguishable. Authentication and permission never imply
queue, enqueue operation, dequeue, worker start, execution, installation,
dispatch, Agent, workflow, deployment, rollback, or mutation authority.

## 12. Freshness and expiry

The service uses a trusted server clock. At create time, the entire
v0.20-v0.40 chain, active v0.39 queue reservation, active v0.40 worker intake
admission, worker identity, and intake reference must be fresh and unexpired.
V0.41 cannot extend any predecessor: `valid_until` is the earliest upstream
expiry and is never more than 30 seconds after trusted `recorded_at`. Boundary
equality is expired.

Expired records remain readable as immutable evidence but cannot be refreshed,
renewed, replaced, superseded, consumed, retried, resent, released, or used to
create another record. Expiry causes no background work, callback, cleanup,
queue operation, or runtime signal.

## 13. Permanent reservations and no replay

`live-enqueue-admission-idempotency-reservation-v1` and
`live-enqueue-admission-subject-reservation-v1` contain only schema,
owner/candidate IDs, hashed identifiers, request/subject fingerprints,
admission/record IDs, `reserved_at`, and `permanent = true`.

The subject is the tuple `(owner, candidate, v0.39 reservation fingerprint,
v0.40 worker intake admission fingerprint, worker identity fingerprint, intake
reference fingerprint, enqueue admission subject fingerprint, live enqueue
admission decision fingerprint, inherited limits fingerprint)`. One subject
can produce at most one record forever. An exact retry returns the existing
record without re-reading evidence or contacting anything. Same key/different
request or same subject/different key is a permanent conflict.

Reservations cannot be consumed, released, refreshed, replaced, superseded,
retried, resent, repaired, garbage-collected, or bypassed, including after
expiry, restart, corruption, timeout, or lost response. Ambiguous append
completion fails closed and never permits reconstruction as new work.

## 14. Fixed non-authorizing posture

Every record, status, result, collection, audit, and error fixes these fields:

- `evidence_only = true`
- `payload_schema_defined = false`
- `payload_constructed = false`
- `request_serialized = false`
- `request_sent = false`
- `enqueue_operation_defined = false`
- `enqueue_operation_allowed = false`
- `queue_enqueued = false`
- `live_enqueue_allowed = false`
- `dequeue_allowed = false`
- `queue_polling_allowed = false`
- `queue_claim_allowed = false`
- `queue_lease_allowed = false`
- `worker_contact_allowed = false`
- `worker_start_allowed = false`
- `execution_start_allowed = false`
- `runner_binding_allowed = false`
- `dispatch_allowed = false`
- `retry_allowed = false`
- `resend_allowed = false`
- `agent_invocation_allowed = false`
- `workflow_start_allowed = false`
- `docker_execution_allowed = false`
- `podman_execution_allowed = false`
- `shell_execution_allowed = false`
- `process_execution_allowed = false`
- `provider_mutation_allowed = false`
- `repository_mutation_allowed = false`
- `in_guest_mutation_allowed = false`
- `installation_allowed = false`
- `deployment_allowed = false`
- `rollback_allowed = false`
- `replay_bypass_allowed = false`

No field may be omitted, renamed, defaulted to true, inferred from permission,
or overridden by configuration.

## 15. Redaction and audit

`live-enqueue-admission-audit-v1` permits only
`live_enqueue_admission_recorded` and `live_enqueue_admission_read`, with audit
UUID, owner/candidate/admission IDs, trusted time, outcome, correlation
fingerprint, subject fingerprint, record fingerprint, and audit fingerprint.
There is no enqueue, dequeue, poll, claim, lease, worker start, dispatch,
execution, network, process, installation, or mutation event.

`live-enqueue-admission-error-v1` permits only closed safe codes derived from
the blocker vocabulary plus `unauthenticated`, `forbidden`, `not_found`,
`invalid_request`, `rate_limited`, `quota_exceeded`, `conflict`,
`record_too_large`, `store_corrupt`, and `internal_error`. It contains only
schema, code, fixed sanitized message, retryable (always false), correlation
fingerprint, and fixed authority. Foreign and missing records both return
`not_found`.

Errors, logs, metrics, audits, API responses, and UI projections never disclose
raw idempotency keys, credentials, endpoints, addresses, queue names, payloads,
commands, arguments, environment, logs, paths, hostnames, ports, sockets,
repository paths, guest paths, mount sources, provider payloads, exception
text, stack traces, or foreign-owner facts.

## 16. API boundary

The only future Core surface is:

- `GET /api/v1/installation/candidate-records/{candidate_record_id}/live-enqueue-admissions`
- `POST /api/v1/installation/candidate-records/{candidate_record_id}/live-enqueue-admissions`
- `GET /api/v1/installation/candidate-records/{candidate_record_id}/live-enqueue-admissions/{admission_id}`

GET has no body or query parameters. POST requires authentication, the record
permission, trusted origin, CSRF, rate limiting, `Content-Type:
application/json`, the strict bounded body, and an `Idempotency-Key` of 16-128
visible ASCII characters. List/get require the read permission and owner scope.

No PUT, PATCH, DELETE, action subroute, or sibling enqueue/dequeue/poll/claim/
lease/worker/start/run/execute/dispatch/retry/resend/install/deploy/rollback
route is permitted. P0 registers no permission, dependency, store, route,
setting, OpenAPI operation, UI client, serializer, worker client, credential,
endpoint, migration, payload schema, or queue library.

## 17. Mission Control boundary

P4 may add strict typing for only the three P3 endpoints and an optional nested
evidence panel under the owned v0.40 worker intake admission in the existing
worker flow. It may present lifecycle, ordered blockers, exact v0.39/v0.40
binding, enqueue admission subject, decision, fingerprints/linkage, inherited
ceilings, freshness/expiry, Core-supplied owner context, audit evidence,
permanent no-replay, fixed-false authority, and redacted errors.

Creation may be shown only when Core supplies eligible server-owned v0.40
worker intake admission context, and must use a two-step acknowledgement
stating: "Record live enqueue admission evidence only. This is not an enqueue
operation and does not submit, serialize, poll, claim, dequeue, start a worker,
dispatch, install, or execute anything."

Mission Control must not add polling, standalone navigation, live queue or
worker selectors, editable limits, raw/sensitive fields, arbitrary metadata, or
controls/labels for enqueue operation, enqueue-now, dequeue, poll, claim,
lease, worker start, run, execute, install, deploy, dispatch, retry/resend,
send-to-Agent, start-workflow, rollback, or mutation.

## 18. Threat model

Validation and tests in later phases must cover foreign-owner probing,
caller-forged identity, timestamps, permissions, references, scopes, or
authority, nested-link substitution, stale or expired evidence, v0.39
reservation mismatch, v0.40 worker-intake-admission mismatch, worker identity
substitution, intake reference substitution, enqueue-subject substitution,
inherited-limit relaxation, duplicate-key/schema smuggling, idempotency
conflict, concurrent or post-restart subject replay, store corruption,
sensitive error/audit/UI rendering, accidental payload schemas, accidental
queue clients, live worker contact, and Agent or execution-worker consumers.

Every condition fails closed. No failure releases a permanent reservation,
creates a partial record, serializes a request, creates a payload, contacts a
queue or worker, enqueues a queue item, or starts an effect.

## 19. P0-P5 delivery plan

- **P0 - frozen planning contract (this change):** planning/roadmap documents
  only; no runtime model, service, store, migration, setting, permission,
  route, OpenAPI operation, UI code, queue library, payload schema, serializer,
  worker client, credential, endpoint, background task, Agent change,
  execution-worker change, installation, dispatch, execution, or deployment
  behavior.
- **P1 - closed Core models:** immutable schemas, deterministic fingerprints,
  bounds, v0.20-v0.40 linkage validation, active v0.40 state/lifecycle/
  freshness/expiry validation, v0.39 reservation binding, v0.40 worker
  identity/intake-reference binding, inherited-limit validation, Home
  Assistant golden, fixed blockers, redaction, and fixed-false authority; no
  service or persistence.
- **P2 - explicit evidence service/store:** create/list/get only, injected
  owner-scoped v0.40, v0.39, worker-identity, and intake-reference readers,
  append-only bounded store, atomic permanent idempotency-key and
  enqueue-admission-subject reservations, exact-duplicate zero-I/O readback,
  restart-safe ownership, and corruption fail-closed; no production consumer.
- **P3 - guarded Core API:** only the frozen collection GET/POST and item GET,
  with exact authentication, record/read permissions, origin/CSRF/rate/parsing,
  ownership, error, OpenAPI, and isolation tests.
- **P4 - Mission Control evidence presentation:** strict create/list/get client
  and optional nested evidence presentation only, with redaction and structural
  absence of polling, sensitive rendering, extra mutations, and effect
  controls.
- **P5 - release isolation and closure:** regression, authority, no-replay,
  Agent/execution-worker zero-consumer, Home Assistant non-artifact, exact API/
  UI isolation, release documentation, and full gates only.

## 20. What v0.41 enables later

V0.41 lets a future milestone require one active, same-owner, permanently
reserved live-enqueue-admission record before that milestone separately
defines an actual enqueue operation. It supplies inspectable linkage, a
candidate-scoped subject, fixed-false authority, and inherited ceilings only.
It does not pre-authorize enqueue, define a queue protocol, define or serialize
a payload, create a live queue item, or make any evidence consumable by a
worker.

## 21. Must-not-change contracts

V0.20-v0.40 request/result schemas, linkage semantics, fingerprints,
ownership, freshness, permanent reservations, APIs, UI boundaries, authority
posture, and Home Assistant blocked golden behavior do not change. V0.41 may
read prior evidence only to validate this evidence record.

Live enqueue operation, payload construction/serialization, dequeue, queue
polling, queue claim/lease, worker discovery/registration/contact/binding/
start, runner binding, execution start, dispatch, retry/resend, Agent or
workflow invocation, Docker/Podman/shell/process execution, installation,
provider/repository/in-guest mutation, deployment, rollback, credentials,
endpoints, and Home Assistant deployment artifacts remain blocked.

Atlas Agent and the independently gated execution-worker gain no schema,
client, callback, conversion, queue, address, credential, route, consumer,
relay, ledger, workspace, request/result binding, or behavior. P0 performs no
migration, tag, push, release publication, deployment, or runtime activation.
