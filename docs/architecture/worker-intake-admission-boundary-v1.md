# Worker Intake Admission Boundary v1 planning contract

Status: **Atlas v0.40 P0-P5 complete release contract**.

This document freezes the v0.40 Worker Intake Admission boundary. Worker intake
admission is one append-only Core evidence record that binds an exact, fresh
v0.20-v0.39 chain to one server-owned worker identity and one abstract intake
admission decision.

The authority invariant is:

`worker_intake_admission_recorded != live enqueue != dequeue != worker start != execution`

The strongest successful state is `worker_intake_admission_recorded`. The
record is not a queue message, worker execution request, dispatch envelope,
runner lease, capability token, install request, workflow step, or permission
to mutate.

## 1. Authority boundary

V0.40 may authenticate an operator, require a dedicated record permission,
re-read same-owner Core-local v0.39 queue-reservation evidence, resolve one
injected server-owned worker identity and one abstract intake reference,
recompute the exact v0.20-v0.39 linkage, verify byte-exact inherited ceilings,
evaluate freshness, permanently reserve one intake subject, append one bounded
evidence record, and return owned readback.

It may not enqueue, dequeue, poll a queue, start or contact a worker, bind a
runner, serialize or submit a worker request, invoke Agent or a workflow,
dispatch, retry, resend, execute a process, install, mutate a provider,
repository, or guest, deploy, roll back, load credentials, resolve endpoints,
or create Home Assistant artifacts. No output is consumable by execution,
worker, queue, dispatch, provider, repository, guest, deployment, or rollback
paths in v0.40.

## 2. Closed vocabulary

Lifecycle is exactly `active | expired`. Eligibility is exactly
`worker_intake_admission_recorded | readiness_gated | blocked`.

Every successful record carries these ordered blockers:

1. `live_enqueue_not_defined`
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
- `worker_identity_ineligible`
- `worker_intake_reference_ineligible`
- `queue_reservation_binding_mismatch`
- `inherited_limits_mismatch`
- `permanent_subject_reserved`
- `live_enqueue_not_defined`
- `dequeue_not_defined`
- `worker_start_not_defined`
- `execution_start_boundary_not_defined`

Unknown lifecycle values, eligibility states, blockers, or authority labels fail
closed. Home Assistant is the blocked golden state: it always returns `blocked`
with first blocker `installation_capability_unsupported`, produces no intake
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

Fingerprint objects retain the released shape:

```yaml
algorithm: sha256
canonicalization: atlas-jcs-nfc-v1
value: <64 lowercase hexadecimal characters>
```

Domain separation is mandatory:

- `atlas:worker-intake-admission-request:v1`
- `atlas:worker-intake-admission-worker-identity:v1`
- `atlas:worker-intake-admission-intake-reference:v1`
- `atlas:worker-intake-admission-decision:v1`
- `atlas:worker-intake-admission-linkage:v1`
- `atlas:worker-intake-admission-idempotency:v1`
- `atlas:worker-intake-admission-subject:v1`
- `atlas:worker-intake-admission-reservation:v1`
- `atlas:worker-intake-admission-record:v1`
- `atlas:worker-intake-admission-status:v1`
- `atlas:worker-intake-admission-audit:v1`
- `atlas:worker-intake-admission-collection:v1`
- `atlas:worker-intake-admission-correlation:v1`

Fingerprints from prior milestones remain in their original domains and are not
interchangeable with v0.40 fingerprints.

## 4. Exact create request

`worker-intake-admission-create-v1` contains exactly:

- `schema = worker-intake-admission-create-v1`
- `worker_queue_reservation_id`
- `worker_queue_reservation_fingerprint`
- `worker_queue_reservation_valid_until`
- `worker_identity_id`
- `worker_identity_fingerprint`
- `worker_intake_reference_id`
- `worker_intake_reference_fingerprint`
- `inherited_limits_fingerprint`
- `requested_scope = installation_worker_intake_admission_only`
- `evidence_only = true`
- `live_enqueue_allowed = false`
- `dequeue_allowed = false`
- `worker_start_allowed = false`
- `execution_authorized = false`
- `replay_allowed = false`

The body supplies references only. Operator identity, candidate identity,
permission result, trusted request time, idempotency key, correlation value,
complete v0.20-v0.39 evidence, queue-reservation contents, worker-identity
contents, intake-reference contents, and audit facts are server-owned
dependencies. The body cannot contain raw prior evidence, queue names,
endpoints, credentials, payloads, commands, images, paths, arbitrary metadata,
timestamps, permissions, authority overrides, or worker execution requests.

## 5. Exact worker identity

`worker-intake-worker-identity-v1` contains exactly:

- `schema = worker-intake-worker-identity-v1`
- `worker_identity_id`
- `owner_operator_id`
- `candidate_record_id`
- `worker_queue_reservation_id`
- `worker_queue_reservation_fingerprint`
- `worker_reference_id`
- `worker_reference_fingerprint`
- `queue_intake_reference_id`
- `queue_intake_reference_fingerprint`
- `queue_item_reference_id`
- `queue_item_reference_fingerprint`
- `worker_kind = isolated_installation_worker`
- `trust_domain = atlas-installation`
- `scope = installation_worker_intake_admission_only`
- `eligibility = eligible_for_intake_admission_evidence_only`
- `identity_fingerprint`
- `capability_profile_fingerprint`
- `inherited_limits`
- `inherited_limits_fingerprint`
- `valid_from`
- `valid_until`
- `registered = false`
- `available = false`
- `reachable = false`
- `authenticated = false`
- `contacted = false`
- `reserved = false`
- `started = false`
- `execution_allowed = false`
- `worker_identity_fingerprint`

The identity is an abstract server-owned eligibility artifact supplied only by
an injected owner-scoped reader. It is not the independently gated execution
worker's process identity, address, health, credential, ledger, workspace,
relay, request contract, or capability attestation. It must not encode or
reveal a hostname, port, socket, URL, token, container, internal path, queue,
repository, command, environment, mount, or provider payload.

## 6. Exact intake reference and admission decision

`worker-intake-reference-v1` contains exactly:

- `schema = worker-intake-reference-v1`
- `worker_intake_reference_id`
- `owner_operator_id`
- `candidate_record_id`
- `worker_queue_reservation_id`
- `worker_queue_reservation_fingerprint`
- `worker_identity_id`
- `worker_identity_fingerprint`
- `queue_intake_reference_id`
- `queue_intake_reference_fingerprint`
- `queue_item_reference_id`
- `queue_item_reference_fingerprint`
- `intake_kind = abstract_worker_intake`
- `trust_domain = atlas-installation`
- `scope = installation_worker_intake_admission_only`
- `eligibility = eligible_for_intake_admission_evidence_only`
- `valid_from`
- `valid_until`
- `intake_reference_fingerprint`
- `intake_protocol = none`
- `intake_exists = false`
- `intake_open = false`
- `endpoint_known = false`
- `credential_known = false`
- `payload_schema_defined = false`
- `serialization_allowed = false`
- `live_enqueue_allowed = false`
- `worker_start_allowed = false`

`worker-intake-admission-decision-v1` contains exactly:

- `schema = worker-intake-admission-decision-v1`
- `decision_id` (derived UUIDv5)
- `owner_operator_id`
- `candidate_record_id`
- `worker_queue_reservation_id`
- `worker_queue_reservation_fingerprint`
- `worker_identity_id`
- `worker_identity_fingerprint`
- `worker_intake_reference_id`
- `worker_intake_reference_fingerprint`
- `scope = installation_worker_intake_admission_only`
- `decision = preserve_non_executing_worker_intake_admission_evidence_only`
- `evaluated_at`
- `eligibility = worker_intake_admission_recorded`
- `blockers`
- `inherited_limits_fingerprint`
- `decision_fingerprint`
- `payload_constructed = false`
- `request_serialized = false`
- `request_sent = false`
- `queue_enqueued = false`
- `queue_dequeued = false`
- `worker_contacted = false`
- `worker_started = false`
- `execution_authorized = false`

Neither object may contain arbitrary operator text, payloads, queue protocol,
endpoint, credential, command, argument, environment, repository, image, path,
log, callback, lease, retry token, or provider data.

## 7. Exact linkage

`worker-intake-admission-linkage-v1` contains exactly:

```yaml
schema: worker-intake-admission-linkage-v1
operator_id: <operator id>
candidate_record_id: <uuid4>
worker_queue_reservation_linkage: <exact worker-queue-reservation-linkage-v1>
v020_v038_chain_fingerprint: <fingerprint-v1>
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
worker_identity_id: <uuid4>
worker_identity_fingerprint: <fingerprint-v1>
worker_intake_reference_id: <uuid4>
worker_intake_reference_fingerprint: <fingerprint-v1>
worker_intake_admission_decision_fingerprint: <fingerprint-v1>
inherited_limits_fingerprint: <fingerprint-v1>
linkage_fingerprint: <fingerprint-v1>
```

The nested v0.39 linkage is the byte-exact released linkage that transitively
contains the named v0.20 durable candidate record, v0.21 approval intent,
v0.22 Agent validation evidence, v0.23 execution request, v0.24 dispatch
handoff, v0.25 intake simulation, v0.26 simulated delivery, v0.27 real intake,
v0.28 dormant delivery wiring, v0.29 activation preflight, v0.30 enablement,
v0.31 send evidence, v0.32 live intake admission, v0.33 inert receipt, v0.34
readiness review, v0.35 permission grant, v0.36 execution admission, v0.37
runner binding plan, v0.38 worker admission stub, and v0.39 queue reservation
fingerprints. A summary fingerprint never replaces validation of exact nested
fields.

Core reconstructs the complete chain with injected owner-scoped readers. The
request cannot substitute raw evidence. Every ID, owner, subject, scope,
fingerprint, status, blocker, and expiry must match byte-for-byte. Missing,
foreign, malformed, stale, expired, mismatched, unsupported, corrupt, or
ambiguous elements fail closed without partial output or reservation release.

## 8. Queue reservation binding

V0.40 binds exactly one active v0.39 queue reservation. The v0.39 reservation,
its queue intake reference, queue item reference, worker reference, inherited
limits, status, subject, and blockers must all match the submitted references
and recomputed linkage. The v0.39 successful blockers remain live blockers in
v0.40 and cannot be removed, softened, reordered, or reinterpreted.

This binding does not create a queue, queue item, enqueue admission, dequeue
consumer, polling loop, claim, lease, payload, worker start, or execution
start. A later milestone must independently define authenticated live enqueue
admission and must require an active v0.40 record rather than treating v0.39
or v0.40 evidence as a queue operation.

## 9. Inherited ceilings

`inherited_limits` must equal the v0.37 runner-binding limits byte-for-byte as
inherited through v0.38 and v0.39. The v0.39 reservation, worker identity,
intake reference, decision, create request, linkage, record, and status
fingerprints must all agree on the same inherited limits fingerprint.

V0.40 cannot loosen, replace, negotiate, supplement, or claim enforcement of
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

`worker-intake-admission-v1` contains exactly its schema, admission UUIDv4,
owner and candidate IDs, trusted `recorded_at`, `valid_until`,
`record_state = recorded`, lifecycle, eligibility, ordered blockers, linkage,
worker identity, intake reference, admission decision, inherited limits,
idempotency fingerprint, request fingerprint, subject fingerprint, record
fingerprint, audit evidence, and fixed authority from section 14.

`worker-intake-admission-status-v1` contains exactly admission/owner/candidate
IDs, lifecycle, eligibility, ordered blockers, `evaluated_at`, `valid_until`,
record fingerprint, status fingerprint, and fixed authority.

`worker-intake-admission-result-v1` contains exactly `schema`, `ok`, nullable
closed record, nullable closed redacted error, correlation fingerprint, and
fixed authority. Exactly one of record or error is present.

`worker-intake-admission-collection-v1` contains exactly `schema`, owner and
candidate IDs, ordered immutable `items`, `count`, collection fingerprint, and
fixed authority. Items are ordered by `(recorded_at, admission_id)`.

## 11. Auth, ownership, and permissions

Every operation requires an authenticated operator. Create requires exactly
`installation.execution.worker_intake_admission.record`; list/get requires
exactly `installation.execution.worker_intake_admission.read`. The frozen
scope is `installation_worker_intake_admission_only`.

Candidate, v0.39 reservation, queue references, worker identity, intake
reference, decision, idempotency, subject, record, status, and audit ownership
must all equal the authenticated operator. No caller-supplied identity or
permission is trusted. Foreign and absent evidence are indistinguishable.
Authentication and permission never imply queue, enqueue, dequeue, worker
start, execution, installation, dispatch, Agent, workflow, deployment, rollback,
or mutation authority.

## 12. Freshness and expiry

The service uses a trusted server clock. At create time, the entire
v0.20-v0.39 chain, v0.39 active status, worker identity, and intake reference
must be fresh and unexpired. V0.40 cannot extend any predecessor:
`valid_until` is the earliest upstream expiry and is never more than 30 seconds
after trusted `recorded_at`. Boundary equality is expired.

Expired records remain readable as immutable evidence but cannot be refreshed,
renewed, replaced, superseded, consumed, retried, resent, released, or used to
create another record. Expiry causes no background work, callback, cleanup,
queue operation, or runtime signal.

## 13. Idempotency and no replay

`worker-intake-admission-idempotency-reservation-v1` and
`worker-intake-admission-subject-reservation-v1` contain only schema,
owner/candidate IDs, hashed identifiers, request/subject fingerprints,
admission/record IDs, `reserved_at`, and `permanent = true`.

The subject is the tuple `(owner, candidate, v0.39 reservation fingerprint,
worker identity fingerprint, intake reference fingerprint, admission decision
fingerprint, inherited limits fingerprint)`. One subject can produce at most
one record forever. An exact retry returns the existing record without
re-reading evidence or contacting anything. Same key/different request or same
subject/different key is a permanent conflict.

Reservations cannot be consumed, released, refreshed, replaced, superseded,
retried, resent, repaired, garbage-collected, or bypassed, including after
expiry, restart, corruption, timeout, or lost response. Ambiguous append
completion fails closed and never permits reconstruction as new work.

## 14. Fixed non-authorizing posture

Every record, status, result, collection, audit, and error fixes these fields:

- `evidence_only = true`
- `live_enqueue_allowed = false`
- `dequeue_allowed = false`
- `queue_polling_allowed = false`
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

`worker-intake-admission-audit-v1` permits only `intake_admission_recorded`
and `intake_admission_read`, with audit UUID, owner/candidate/admission IDs,
trusted time, outcome, correlation fingerprint, subject fingerprint, record
fingerprint, and audit fingerprint. There is no enqueue, dequeue, poll, claim,
lease, worker start, dispatch, execution, network, process, installation, or
mutation event.

`worker-intake-admission-error-v1` permits only closed safe codes derived from
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

The only Core surface is:

- `GET /api/v1/installation/candidate-records/{candidate_record_id}/worker-intake-admissions`
- `POST /api/v1/installation/candidate-records/{candidate_record_id}/worker-intake-admissions`
- `GET /api/v1/installation/candidate-records/{candidate_record_id}/worker-intake-admissions/{admission_id}`

GET has no body or query parameters. POST requires authentication, the record
permission, trusted origin, CSRF, rate limiting, `Content-Type:
application/json`, the strict bounded body, and an `Idempotency-Key` of 16-128
visible ASCII characters. List/get require the read permission and owner scope.

No PUT, PATCH, DELETE, action subroute, or sibling enqueue/dequeue/poll/claim/
lease/worker/start/run/execute/dispatch/retry/resend/install/deploy/rollback
route is permitted. P0 registers no permission, dependency, store, route,
setting, OpenAPI surface, UI client, or migration.

## 17. Mission Control boundary

P4 may add strict typing for only the three P3 endpoints and a nested evidence
panel under the owned v0.39 worker queue reservation. It may present lifecycle,
ordered blockers, abstract worker identity and intake reference, exact
fingerprints/linkage, inherited ceilings, freshness/expiry, Core-supplied owner
context, audit evidence, permanent no-replay, fixed-false authority, and
redacted errors.

Creation may be shown only when Core supplies eligible server-owned worker
identity and intake-reference context, and must use a two-step acknowledgement
stating: "Record worker intake admission evidence only. This does not enqueue,
dequeue, poll, start a worker, dispatch, install, or execute anything."

Mission Control must not add polling, standalone navigation, live queue or
worker selectors, editable limits, raw/sensitive fields, arbitrary metadata, or
controls/labels for enqueue, dequeue, poll, claim, lease, worker start, run,
execute, install, deploy, dispatch, retry/resend, send-to-Agent,
start-workflow, rollback, or mutation.

## 18. Threat model

Validation and tests in later phases must cover foreign-owner probing,
caller-forged identity, timestamps, permissions, references, or authority,
nested-link substitution, stale or expired evidence, v0.39 reservation mismatch,
worker identity substitution, intake reference substitution, inherited-limit
relaxation, duplicate-key/schema smuggling, idempotency conflict, concurrent or
post-restart subject replay, store corruption, sensitive error/audit/UI
rendering, accidental queue clients, live worker contact, and Agent or
execution-worker consumers.

Every condition fails closed. No failure releases a permanent reservation,
creates a partial record, contacts a worker, creates a queue item, or starts an
effect.

## 19. P0-P5 delivery plan

- **P0 - frozen planning contract (this change):** planning/roadmap documents
  only; no runtime model, service, store, route, permission, UI, migration,
  queue, worker, network, process, Agent, execution-worker, installation, or
  deployment behavior.
- **P1 - closed Core models:** immutable schemas, deterministic fingerprints,
  bounds, v0.20-v0.39 linkage validation, queue-reservation binding,
  worker-identity/intake-reference validation, inherited-limit validation,
  Home Assistant golden, fixed blockers, redaction, and fixed-false authority;
  no service or persistence.
- **P2 - explicit evidence service/store:** create/list/get only, injected
  owner-scoped v0.39, worker-identity, and intake-reference readers,
  append-only bounded store, atomic permanent reservations, exact-duplicate
  zero-I/O readback, restart-safe ownership, and corruption fail-closed; no
  production consumer.
- **P3 - guarded Core API:** only the frozen collection GET/POST and item GET,
  with exact authentication, permission, origin/CSRF/rate/parsing, ownership,
  error, OpenAPI, and isolation tests.
- **P4 - Mission Control evidence presentation:** strict create/list/get client
  and nested evidence presentation only, with redaction and structural absence
  of polling, sensitive rendering, extra mutations, and effect controls.
- **P5 - release isolation and closure:** regression, authority, no-replay,
  Agent/execution-worker zero-consumer, Home Assistant non-artifact, exact API/
  UI isolation, release documentation, and full gates only.

## 20. What v0.40 enables later

V0.40 lets a future milestone require one active, same-owner, permanently
reserved worker-intake-admission record before that milestone separately
defines live enqueue admission. It supplies inspectable linkage, worker
identity evidence, intake-reference evidence, and inherited ceilings only. It
does not pre-authorize live enqueue, define a queue protocol, create a payload,
or make any evidence consumable by a worker.

## 21. Must-not-change contracts

V0.20-v0.39 request/result schemas, linkage semantics, fingerprints,
ownership, freshness, permanent reservations, APIs, UI boundaries, authority
posture, and Home Assistant blocked golden behavior do not change. V0.40 may
read prior evidence only to validate this evidence record.

Live enqueue, dequeue, queue polling, queue claim/lease, worker
discovery/registration/contact/binding/start, runner binding, execution start,
dispatch, retry/resend, Agent or workflow invocation, Docker/Podman/shell/
process execution, installation, provider/repository/in-guest mutation,
deployment, rollback, credentials, endpoints, and Home Assistant deployment
artifacts remain blocked.

Atlas Agent and the independently gated execution-worker gain no schema,
client, callback, conversion, queue, address, credential, route, consumer,
relay, ledger, workspace, request/result binding, or behavior. P0 performs no
migration, tag, push, release publication, deployment, or runtime activation.
