# Worker Queue Reservation Boundary v1 planning contract

Status: **Atlas v0.39 P0–P5 complete**

This document freezes the v0.39 boundary before runtime work. A worker queue
reservation is an append-only Core evidence record. It is not a reservation in
a live queue and grants no authority to enqueue, dequeue, start, dispatch, or
execute anything.

## 1. Authority boundary

The invariant is:

`worker_queue_reservation_recorded != live enqueue != dequeue != worker start != execution`

The strongest successful state is `worker_queue_reservation_recorded`. Every
successful record carries these ordered blockers:

1. `live_enqueue_not_defined`
2. `dequeue_not_defined`
3. `worker_start_not_defined`
4. `execution_start_boundary_not_defined`

The record is evidence that one exact, already admitted worker subject and one
abstract queue reference were reviewed together under inherited ceilings. It
does not prove that a queue, endpoint, worker, sandbox, filesystem, or network
exists, is reachable, is authenticated, has capacity, or has accepted work.

## 2. Closed vocabulary

Lifecycle is exactly `active | expired`. Eligibility is exactly
`worker_queue_reservation_recorded | readiness_gated | blocked`.

The closed ordered blocker vocabulary is:

- `installation_capability_unsupported`
- `evidence_not_found`
- `ownership_mismatch`
- `permission_scope_missing`
- `linkage_mismatch`
- `fingerprint_mismatch`
- `evidence_stale`
- `evidence_expired`
- `worker_admission_not_active`
- `worker_reference_ineligible`
- `queue_intake_reference_ineligible`
- `queue_item_reference_invalid`
- `inherited_limits_mismatch`
- `permanent_subject_reserved`
- `live_enqueue_not_defined`
- `dequeue_not_defined`
- `worker_start_not_defined`
- `execution_start_boundary_not_defined`

Unknown states or blockers fail closed. Home Assistant always returns
`blocked` with first blocker `installation_capability_unsupported`; it cannot
produce a reservation record or deployment artifact.

## 3. Exact closed schemas

All models are immutable, reject unknown fields, reject duplicate JSON keys,
and use UTC whole-second timestamps. UUIDs are canonical lowercase UUIDv4
unless explicitly described as derived UUIDv5. Fingerprints are lowercase
64-character SHA-256 hex strings.

### 3.1 Create request

`worker-queue-reservation-create-v1` contains exactly:

- `schema = worker-queue-reservation-create-v1`
- `worker_admission_stub_id`
- `worker_admission_stub_fingerprint`
- `worker_admission_stub_valid_until`
- `queue_intake_reference_id`
- `queue_intake_reference_fingerprint`
- `queue_item_reference_id`
- `queue_item_reference_fingerprint`
- `inherited_limits_fingerprint`
- `requested_scope = installation_worker_queue_reservation_only`
- `evidence_only = true`
- `live_enqueue_allowed = false`
- `dequeue_allowed = false`
- `worker_start_allowed = false`
- `execution_authorized = false`
- `replay_allowed = false`

The operator, candidate, clock, permission, complete linkage, references, and
limits are resolved server-side. The body cannot contain an operator ID,
permission claim, timestamp, queue address/name, endpoint, credential,
payload, command, image, path, arbitrary metadata, or authority override.

### 3.2 Queue intake reference

`worker-queue-intake-reference-v1` contains exactly:

- `schema = worker-queue-intake-reference-v1`
- `queue_intake_reference_id`
- `owner_operator_id`
- `candidate_record_id`
- `worker_admission_stub_id`
- `worker_admission_stub_fingerprint`
- `worker_reference_id`
- `worker_reference_fingerprint`
- `queue_kind = abstract_installation_queue`
- `trust_domain = atlas-installation`
- `scope = installation_worker_queue_reservation_only`
- `eligibility = eligible_for_reservation_evidence_only`
- `identity_fingerprint`
- `capability_fingerprint`
- `inherited_limits`
- `inherited_limits_fingerprint`
- `valid_from`
- `valid_until`
- `reference_fingerprint`
- `queue_exists = false`
- `queue_reachable = false`
- `queue_authenticated = false`
- `queue_contacted = false`
- `reservation_endpoint_known = false`
- `live_enqueue_allowed = false`
- `dequeue_allowed = false`

It is supplied only by an injected, owner-scoped read-only reference reader.
It is not a queue locator or live capability.

### 3.3 Queue item reference

`worker-queue-item-reference-v1` contains exactly:

- `schema = worker-queue-item-reference-v1`
- `queue_item_reference_id` (derived UUIDv5)
- `owner_operator_id`
- `candidate_record_id`
- `worker_admission_stub_id`
- `worker_admission_stub_fingerprint`
- `queue_intake_reference_id`
- `queue_intake_reference_fingerprint`
- `worker_reference_id`
- `worker_reference_fingerprint`
- `item_kind = installation_evidence_reference_only`
- `scope = installation_worker_queue_reservation_only`
- `inherited_limits_fingerprint`
- `created_at`
- `item_fingerprint`
- `payload_defined = false`
- `serialized = false`
- `enqueued = false`
- `dequeued = false`
- `claimed = false`
- `executable = false`

The item reference carries no payload, command, argument, environment,
credential, endpoint, address, image, repository path, guest path, log, or
provider data.

### 3.4 Linkage

`worker-queue-reservation-linkage-v1` contains exactly:

```yaml
schema: worker-queue-reservation-linkage-v1
operator_id: <operator id>
candidate_record_id: <uuid4>
worker_admission_stub_linkage: <exact worker-admission-stub-linkage-v1>
v020_v037_chain_fingerprint: <fingerprint-v1>
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
worker_admission_intent_fingerprint: <fingerprint-v1>
worker_intake_stub_fingerprint: <fingerprint-v1>
queue_intake_reference_id: <uuid4>
queue_intake_reference_fingerprint: <fingerprint-v1>
queue_item_reference_id: <derived uuid5>
queue_item_reference_fingerprint: <fingerprint-v1>
inherited_limits_fingerprint: <fingerprint-v1>
linkage_fingerprint: <fingerprint-v1>
```

The nested v0.38 linkage is the byte-exact released linkage that transitively
contains the named v0.20 durable candidate record, v0.21 approval intent,
v0.22 Agent validation evidence, v0.23 execution request, v0.24 dispatch
handoff, v0.25 intake simulation, v0.26 simulated delivery, v0.27 real intake,
v0.28 dormant delivery wiring, v0.29 activation preflight, v0.30 enablement,
v0.31 send evidence, v0.32 live intake admission, v0.33 inert receipt, v0.34
readiness review, v0.35 permission grant, v0.36 execution admission, and v0.37
runner binding plan fingerprints. No summary fingerprint replaces validation
of the exact nested fields.

Core reconstructs the complete chain with injected owner-scoped readers. The
request cannot substitute raw evidence. Every ID, owner, subject, scope,
fingerprint, and expiry must match byte-for-byte.

### 3.5 Record, status, result, and collection

`worker-queue-reservation-v1` contains exactly its schema, reservation UUIDv4,
owner and candidate IDs, trusted `recorded_at`, `valid_until`,
`record_state = recorded`, lifecycle, eligibility, ordered blockers, linkage,
queue intake reference, queue item reference, inherited limits, idempotency
fingerprint, request fingerprint, subject fingerprint, record fingerprint,
audit evidence, and the fixed authority object from section 8.

`worker-queue-reservation-status-v1` contains exactly reservation/owner/
candidate IDs, lifecycle, eligibility, ordered blockers, `evaluated_at`,
`valid_until`, record fingerprint, status fingerprint, and fixed authority.

`worker-queue-reservation-result-v1` contains exactly `schema`, `ok`, nullable
closed record, nullable closed redacted error, correlation fingerprint, and
fixed authority. Exactly one of record or error is present.

`worker-queue-reservation-collection-v1` contains exactly `schema`, owner and
candidate IDs, ordered immutable `items`, `count`, collection fingerprint, and
fixed authority. Items are ordered by `(recorded_at, reservation_id)`.

### 3.6 Permanent reservations and idempotency

`worker-queue-idempotency-reservation-v1` and
`worker-queue-subject-reservation-v1` contain only schema, owner/candidate IDs,
hashed identifiers, request/subject fingerprints, reservation/record IDs,
`reserved_at`, and `permanent = true`. Raw idempotency keys are never stored,
logged, audited, returned, or rendered.

The subject is the tuple `(owner, candidate, v0.38 stub fingerprint, worker
reference fingerprint, queue intake reference fingerprint, queue item
reference fingerprint, inherited limits fingerprint)`. One subject can
produce at most one record forever. An exact retry returns the existing record
without re-reading evidence or contacting anything. Same key/different request
or same subject/different key is a permanent conflict. Reservations cannot be
consumed, released, refreshed, replaced, superseded, retried, resent, or
bypassed, including after expiry, restart, or corruption.

### 3.7 Audit and redacted errors

`worker-queue-reservation-audit-v1` permits only `reservation_recorded` and
`reservation_read`, with audit UUID, owner/candidate/reservation IDs, trusted
time, outcome, correlation fingerprint, subject fingerprint, record
fingerprint, and audit fingerprint. There is no enqueue, dequeue, start,
dispatch, execution, network, process, or mutation event.

`worker-queue-reservation-error-v1` permits only closed safe codes derived from
the blocker vocabulary plus `unauthenticated`, `forbidden`, `not_found`,
`invalid_request`, `rate_limited`, `quota_exceeded`, `conflict`,
`record_too_large`, `store_corrupt`, and `internal_error`. It contains only
schema, code, fixed sanitized message, retryable (always false), correlation
fingerprint, and fixed authority. Foreign and missing records are the same
`not_found`. Errors never disclose evidence, keys, credentials, payloads,
commands, logs, paths, addresses, endpoints, or exception text.

## 4. Fingerprints and bounds

Canonicalization is `atlas-jcs-nfc-v1`: NFC strings, sorted JSON object keys,
no insignificant whitespace, integer-only numeric fields, and explicit nulls
only where the schema permits them. SHA-256 fingerprints use these domains:

- `atlas:worker-queue-intake-reference:v1`
- `atlas:worker-queue-item-reference:v1`
- `atlas:worker-queue-reservation-linkage:v1`
- `atlas:worker-queue-reservation-idempotency:v1`
- `atlas:worker-queue-reservation-request:v1`
- `atlas:worker-queue-reservation-subject:v1`
- `atlas:worker-queue-reservation-record:v1`
- `atlas:worker-queue-reservation-status:v1`
- `atlas:worker-queue-reservation-audit:v1`
- `atlas:worker-queue-reservation-collection:v1`
- `atlas:worker-queue-reservation-correlation:v1`

The POST body is at most 16 KiB and JSON nesting at most 16. A serialized
record/result is at most 128 KiB, a collection contains at most 100 records,
and the P2 store quota is at most 16 records per operator. Identifiers are at
most 128 visible ASCII characters where not fixed UUIDs; enum and error text
are fixed constants. Oversize values fail before persistence.

## 5. Ownership, authentication, and permissions

Every operation requires an authenticated operator. Create requires exactly
`installation.execution.worker_queue_reservation.record`; list/get requires
exactly `installation.execution.worker_queue_reservation.read`. The frozen
scope is `installation_worker_queue_reservation_only`.

Candidate, v0.38 stub, worker, queue intake, queue item, idempotency, subject,
record, and audit ownership must all equal the authenticated operator. No
caller-supplied identity or permission is trusted. Foreign and absent evidence
are indistinguishable. Authentication and permission never imply enqueue,
dequeue, worker, execution, installation, or mutation authority.

## 6. Freshness, expiry, and inherited limits

The service uses a trusted server clock. At create time the entire v0.20-v0.38
chain, v0.38 active status, worker reference, and queue intake reference must
be fresh and unexpired. V0.39 cannot extend any predecessor: `valid_until` is
the earliest upstream expiry and is never more than 30 seconds after trusted
`recorded_at`. Boundary equality is expired. Expired records remain readable
as immutable evidence but cannot be refreshed or used for another record.

The sandbox/resource/network/filesystem object and its fingerprint must be
byte-exact with v0.37 as inherited through v0.38. V0.39 cannot relax, edit,
reinterpret, or supplement a ceiling. Network remains `none`; filesystem
remains an abstract ephemeral-workspace-only constraint with no host path,
mount source, device, socket, credential, or address. These are evidence
ceilings, not proof of runtime enforcement or sandbox creation.

## 7. API boundary

The only planned Core surface is:

- `GET /api/v1/installation/candidate-records/{candidate_record_id}/worker-queue-reservations`
- `POST /api/v1/installation/candidate-records/{candidate_record_id}/worker-queue-reservations`
- `GET /api/v1/installation/candidate-records/{candidate_record_id}/worker-queue-reservations/{reservation_id}`

GET has no body or query parameters. POST requires authentication, the record
permission, trusted origin, CSRF, rate limiting, `Content-Type:
application/json`, the strict bounded body, and an `Idempotency-Key` of 16-128
visible ASCII characters. List/get require the read permission and owner scope.
No PUT, PATCH, DELETE, action subroute, or sibling enqueue/dequeue/worker/start/
run/execute/dispatch/retry/resend/install/deploy/rollback route is permitted.

P0 registers no permission, dependency, store, route, setting, or OpenAPI
surface. Later phases must keep construction explicit and use injected
owner-scoped read-only evidence/reference readers.

## 8. Fixed non-authorizing posture

Every record, status, result, collection, audit, and error fixes these fields:

- `evidence_only = true`
- `live_enqueue_allowed = false`
- `dequeue_allowed = false`
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

## 9. Mission Control boundary

P4 may add strict typing for only the three P3 endpoints and a nested evidence
panel under the owned v0.38 worker admission stub. It may present lifecycle,
ordered blockers, abstract references, exact fingerprints/linkage, inherited
ceilings, freshness/expiry, owner context supplied by Core, audit evidence,
permanent no-replay, fixed-false authority, and redacted errors.

Creation may be shown only when Core supplies the eligible server-owned queue
reference context and must use a two-step acknowledgement stating: “Record
queue reservation evidence only. This does not enqueue, dequeue, start a
worker, dispatch, install, or execute anything.” There is no polling,
standalone navigation, live queue/worker selector, editable limit, form field
for sensitive/raw data, or control/label for enqueue, dequeue, worker/start,
run, execute, install, deploy, dispatch, retry/resend, send-to-Agent,
start-workflow, rollback, or mutation.

## 10. P0-P5 delivery plan

- **P0 — frozen planning contract (this change):** planning/roadmap documents
  only; no runtime model, service, store, route, permission, UI, or migration.
- **P1 — closed Core models:** immutable schemas, canonical fingerprints,
  bounds, linkage/reference/limit validation, Home Assistant golden, fixed
  blockers, redaction, and fixed-false authority; no service or persistence.
- **P2 — explicit evidence service/store:** create/list/get only, injected
  owner-scoped v0.38 and queue-reference readers, append-only bounded store,
  atomic permanent reservations, exact-duplicate zero-I/O readback,
  restart-safe ownership, and corruption fail-closed; no production consumer.
- **P3 — guarded Core API:** only the frozen collection GET/POST and item GET,
  with exact authentication, permission, origin/CSRF/rate/parsing, ownership,
  error, OpenAPI, and isolation tests.
- **P4 — Mission Control evidence presentation:** strict create/list/get client
  and nested evidence presentation only, with redaction and structural absence
  of polling, sensitive rendering, extra mutations, and effect controls.
- **P5 — release isolation and closure:** regression, authority, no-replay,
  Agent/execution-worker zero-consumer, Home Assistant non-artifact, exact API/
  UI isolation, release documentation, and full gates only.

P1–P4 implemented only the frozen closed models, explicitly injected
append-only evidence service/store, exact guarded create/list/get API, and
nested Mission Control evidence presentation. P5 added isolation and authority
locks only. Closure validation passed both Ruff gates, 76 focused Core tests,
1049 Agent tests, 610 Mission Control tests, Mission Control lint/build, and
`git diff --check`.

The validation threat model explicitly covers foreign-owner probing, caller-
forged timestamps/permissions/references, nested-link substitution, stale or
expired evidence, limit relaxation, duplicate-key/schema smuggling,
idempotency conflict, concurrent or post-restart subject replay, store
corruption, sensitive error/audit rendering, accidental live queue clients,
and an Agent or execution-worker consumer. Each condition fails closed and no
failure releases a permanent reservation or creates an effect.

## 11. What v0.39 enables later

V0.39 lets a future milestone require one active, same-owner, permanently
reserved queue-evidence subject before that milestone separately defines a
live enqueue admission decision. It supplies inspectable linkage and ceilings
only. It does not pre-authorize that decision, define a queue protocol, create
a payload, or make any evidence consumable by a worker.

## 12. What remains blocked and must not change

Live enqueue, dequeue, queue polling, worker discovery/registration/contact/
binding/start, runner binding, execution start, dispatch, retry/resend, Agent
or workflow invocation, Docker/Podman/shell/process, installation,
provider/repository/in-guest mutation, deployment, rollback, credentials,
endpoints, and Home Assistant deployment artifacts remain blocked.

V0.20-v0.38 evidence semantics, ownership, fingerprints, freshness, permanent
reservations, APIs, and authority do not change. Core may read them only to
validate this evidence record. Atlas Agent and the independently gated
execution-worker gain no schema, client, callback, conversion, queue, address,
credential, route, consumer, or behavior. P0 performs no migration, tag, push,
release publication, or deployment.
