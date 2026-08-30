# Worker Admission Stub v1 planning contract

Status: **Atlas v0.38 P0–P5 complete; release preparation remains separate**.

Atlas v0.38 defines one closed, durable Core evidence record stating that an
authenticated operator's exact, fresh v0.20–v0.37 installation chain has been
checked against one abstract worker-admission intent and worker reference. The
strongest successful state is `worker_admission_stubbed`:

`worker admission stub != queue admission != worker start != execution`

The record is not a job, queue message, dispatch envelope, capability token,
worker request, execution lease, install request, or permission to mutate.

## Repository inspection baseline

Planning starts from `main` at
`83d08274a805ca3c972e9827c6a2ce9253982758`, after annotated tag
`atlas-v0.37.0` targeting
`eee726fe68da80ca2e4ecab9478494881836e648` and the v0.37 checklist
reconciliation merged to `main`.

The repository already contains an independently gated execution-worker
backend, relay, request contracts, ledger, workspace manager, and process
runner. Those are pre-existing operational surfaces and are explicitly out of
scope. V0.38 adds no import, adapter, client, socket, address, credential,
queue, callback, request conversion, or consumer connecting installation
evidence to that subsystem. Its optional/default-disabled posture and existing
authentication and execution gates do not change.

## Exact authority boundary

V0.38 may authenticate an operator, require a dedicated permission, re-read
same-owner Core-local v0.36 admission and v0.37 runner-binding-plan evidence,
read one injected server-owned abstract worker reference, recompute the exact
v0.20–v0.37 linkage, verify inherited limits and freshness, permanently
reserve one admission subject, append one bounded evidence record, and return
owned readback.

It may not register, discover, contact, reserve, bind, authenticate to, or
start a worker; create or submit a worker execution request; enqueue, publish,
schedule, dispatch, retry, resend, invoke Agent, start a workflow, execute a
process, install, mutate, deploy, or roll back. No output is consumable by an
execution, worker, queue, dispatch, provider, repository, guest, deployment,
or rollback path in v0.38.

## Canonical primitives and bounds

- IDs are canonical lowercase UUIDv4, except a server-derived intent ID may be
  UUIDv5.
- `operator_id` is visible ASCII matching `[A-Za-z0-9][A-Za-z0-9._:-]{0,127}`.
- Timestamps are UTC RFC 3339 seconds ending in `Z`; clients supply none.
- Fingerprints use SHA-256 over RFC 8785 JCS after NFC normalization:

```yaml
algorithm: sha256
canonicalization: atlas-jcs-nfc-v1
value: <64 lowercase hexadecimal characters>
```

- Domain separation is mandatory. Domains are
  `atlas:worker-admission-stub-{intent,intake,reference,linkage,idempotency,request,subject,reservation,record,status,audit,operator,candidate,correlation}:v1`.
- Unknown or duplicate JSON keys, non-finite numbers, non-canonical strings,
  invalid UTF-8, and unbounded nesting fail closed.
- POST body maximum is 16 KiB, response maximum 128 KiB, nesting depth 16,
  blockers maximum 16, and collection maximum 100 records.
- An idempotency key is 16–128 visible ASCII characters and is never stored or
  returned raw; only its domain-separated fingerprint is durable.

Every model is immutable and closed (`extra=forbid`). Defaults do not relax
validation; fixed booleans reject any contrary value.

## Exact request schema

```yaml
schema: worker-admission-stub-create-v1
runner_binding_plan_id: <uuid4>
runner_binding_plan_fingerprint: <fingerprint-v1>
runner_binding_plan_valid_until: <UTC instant copied from owned plan>
worker_reference_id: <uuid4>
worker_reference_fingerprint: <fingerprint-v1>
inherited_limits_fingerprint: <fingerprint-v1>
requested_scope: installation_worker_admission_stub_only
evidence_only: true
worker_start_allowed: false
queue_allowed: false
dispatch_allowed: false
execution_authorized: false
replay_allowed: false
```

The body supplies references only. Operator identity, permission result,
candidate identity, trusted request time, idempotency key, correlation value,
v0.20–v0.37 evidence, worker-reference contents, and all audit facts are
server-owned dependencies. No client may submit raw prior evidence, runner or
worker payloads, limits, credentials, endpoints, commands, or metadata.

## Exact worker admission intent schema

Core derives this immutable intent; it is not an operational request.

```yaml
schema: worker-admission-intent-v1
intent_id: <server UUIDv5>
operator_id: <operator id>
candidate_record_id: <uuid4>
runner_binding_plan_id: <uuid4>
runner_binding_plan_fingerprint: <fingerprint-v1>
worker_reference_id: <uuid4>
worker_reference_fingerprint: <fingerprint-v1>
inherited_limits_fingerprint: <fingerprint-v1>
scope: installation_worker_admission_stub_only
intent: preserve_non_executing_worker_admission_evidence_only
requested_at: <trusted server instant>
intent_fingerprint: <fingerprint-v1>
queue_requested: false
dispatch_requested: false
worker_start_requested: false
execution_requested: false
agent_invocation_requested: false
mutation_requested: false
```

Intent text is fixed. It cannot contain commands, arguments, repositories,
targets, images, environment variables, secrets, endpoints, queue names,
worker addresses, or arbitrary operator text.

## Exact worker intake stub schema

Core derives this closed descriptor from the intent and reference. It describes
only that no intake exists; it is never serialized into an execution-worker
request or sent anywhere.

```yaml
schema: worker-admission-intake-stub-v1
intent_id: <server UUIDv5>
intent_fingerprint: <fingerprint-v1>
worker_reference_id: <uuid4>
worker_reference_fingerprint: <fingerprint-v1>
scope: installation_worker_admission_stub_only
intake_state: undefined
intake_protocol: none
intake_fingerprint: <fingerprint-v1>
queue_selected: false
queue_created: false
intake_open: false
payload_constructed: false
request_serialized: false
request_sent: false
worker_contacted: false
worker_started: false
execution_authorized: false
```

No address, protocol value other than `none`, queue identifier, credential,
payload, command, argument, environment, repository, target, or arbitrary data
is permitted.

## Exact worker reference schema

The injected reader returns one same-owner abstract eligibility artifact:

```yaml
schema: installation-worker-reference-v1
worker_reference_id: <uuid4>
owner_operator_id: <operator id>
worker_kind: isolated_installation_worker
trust_domain: atlas-installation
scope: installation_worker_admission_stub_only
eligibility: eligible_for_admission_stub_only
runner_reference_id: <uuid4 from v0.37>
runner_reference_fingerprint: <fingerprint-v1>
identity_fingerprint: <fingerprint-v1>
capability_profile_fingerprint: <fingerprint-v1>
inherited_limits: <runner-binding-limits-v1, exact v0.37 value>
inherited_limits_fingerprint: <fingerprint-v1>
valid_from: <UTC instant>
valid_until: <UTC instant>
reference_fingerprint: <fingerprint-v1>
registered: false
available: false
reachable: false
authenticated: false
contacted: false
reserved: false
bound: false
queue_known: false
intake_open: false
invocation_allowed: false
```

This is not the pre-existing execution worker's identity, address, health,
credential, ledger, request contract, or capability attestation. The reader is
injected explicitly and has no production construction until a later contract
authorizes a source. The reference must not encode or reveal an endpoint,
socket, token, container, internal path, hostname, port, queue, repository, or
command.

## Inherited sandbox/resource/network/filesystem bounds

`inherited_limits` must equal the v0.37 runner binding plan limits byte-for-byte
after canonicalization, and all three fingerprints (plan linkage, worker
reference, create request) must equal the recomputed limits fingerprint.
V0.38 cannot loosen, replace, negotiate, or claim enforcement of them:

- sandbox profile `atlas-installation-confined-v1`; non-privileged; no
  escalation, host namespaces, host devices, or capabilities; seccomp and
  AppArmor required;
- CPU ≤ 1000 millis, memory ≤ 536870912 bytes, PIDs ≤ 64, wall time ≤ 900
  seconds, output ≤ 1048576 bytes;
- network mode `none`; ingress, egress, DNS, image pull, and allowed endpoints
  are all absent/false;
- read-only root; no host, repository, or guest mount; only an ephemeral
  workspace up to 268435456 bytes may be described.

These are evidence ceilings only. No sandbox, filesystem, network namespace,
workspace, container, or process is created or inspected.

## Exact linkage schema

```yaml
schema: worker-admission-stub-linkage-v1
operator_id: <operator id>
candidate_record_id: <uuid4>
runner_binding_plan_linkage: <exact runner-binding-plan-linkage-v1>
v020_v036_chain_fingerprint: <fingerprint-v1>
readiness_review_fingerprint: <v0.34 fingerprint-v1>
permission_grant_fingerprint: <v0.35 fingerprint-v1>
execution_admission_id: <v0.36 uuid4>
execution_admission_fingerprint: <fingerprint-v1>
runner_binding_plan_id: <v0.37 uuid4>
runner_binding_plan_fingerprint: <fingerprint-v1>
runner_binding_plan_status_fingerprint: <fingerprint-v1>
runner_reference_id: <v0.37 uuid4>
runner_reference_fingerprint: <fingerprint-v1>
worker_reference_id: <uuid4>
worker_reference_fingerprint: <fingerprint-v1>
worker_identity_fingerprint: <fingerprint-v1>
worker_capability_profile_fingerprint: <fingerprint-v1>
worker_admission_intent_fingerprint: <fingerprint-v1>
worker_admission_intake_fingerprint: <fingerprint-v1>
inherited_limits_fingerprint: <fingerprint-v1>
linkage_fingerprint: <fingerprint-v1>
```

All nested and summarized values must recompute exactly. Operator, candidate,
admission, plan, runner, worker reference, intent, and limits must agree. A
missing, foreign, malformed, stale, expired, mismatched, unsupported, or
corrupt element fails closed without partial output or reservation release.

## Exact authority context

```yaml
schema: worker-admission-stub-authority-context-v1
authenticated_operator_id: <operator id>
required_permission: installation.execution.worker_admission_stub.record
permission_verified: true
requested_scope: installation_worker_admission_stub_only
request_received_at: <trusted server instant>
evidence_only: true
worker_registration_allowed: false
worker_contact_allowed: false
worker_reservation_allowed: false
worker_binding_allowed: false
worker_start_allowed: false
queue_allowed: false
enqueue_allowed: false
dispatch_allowed: false
execution_start_allowed: false
execution_authorized: false
installation_allowed: false
retry_allowed: false
resend_allowed: false
agent_invocation_allowed: false
workflow_allowed: false
docker_allowed: false
podman_allowed: false
shell_allowed: false
process_allowed: false
provider_mutation_allowed: false
repository_mutation_allowed: false
in_guest_mutation_allowed: false
deployment_allowed: false
rollback_allowed: false
replay_allowed: false
```

Read operations require `installation.execution.worker_admission_stub.read`.
Permissions are dedicated and cannot be inferred from v0.35–v0.37 permissions,
administrator labels, worker credentials, Agent permissions, or UI visibility.

## Exact record and status schemas

```yaml
schema: worker-admission-stub-v1
stub_id: <server uuid4>
operator_id: <operator id>
candidate_record_id: <uuid4>
recorded_at: <trusted server instant>
valid_until: <earliest admissible expiry>
record_state: recorded
lifecycle: active
eligibility: worker_admission_stubbed
blockers:
  - worker_not_started
  - queue_boundary_not_defined
  - execution_start_boundary_not_defined
linkage: <worker-admission-stub-linkage-v1>
worker_admission_intent: <worker-admission-intent-v1>
worker_admission_intake: <worker-admission-intake-stub-v1>
worker_reference: <installation-worker-reference-v1>
inherited_limits: <runner-binding-limits-v1>
idempotency_key_fingerprint: <fingerprint-v1>
request_fingerprint: <fingerprint-v1>
stub_fingerprint: <fingerprint-v1>
evidence_only: true
worker_registered: false
worker_contacted: false
worker_reserved: false
worker_bound: false
worker_started: false
queue_created: false
work_enqueued: false
dispatch_allowed: false
execution_start_allowed: false
execution_authorized: false
installation_allowed: false
retry_allowed: false
resend_allowed: false
agent_invocation_allowed: false
workflow_allowed: false
docker_allowed: false
podman_allowed: false
shell_allowed: false
process_allowed: false
provider_mutation_allowed: false
repository_mutation_allowed: false
in_guest_mutation_allowed: false
deployment_allowed: false
rollback_allowed: false
replay_allowed: false
```

```yaml
schema: worker-admission-stub-status-v1
stub_id: <uuid4>
observed_at: <trusted server instant>
lifecycle: active | expired
eligibility: worker_admission_stubbed
blockers: [worker_not_started, queue_boundary_not_defined,
           execution_start_boundary_not_defined]
status_fingerprint: <fingerprint-v1>
evidence_only: true
worker_started: false
work_enqueued: false
execution_authorized: false
replay_allowed: false
```

Stored records are never updated. Status is a derived read projection; expiry
does not delete, refresh, consume, release, supersede, or authorize anything.

## Eligibility and blocker vocabulary

Successful records have exactly one eligibility:

- `worker_admission_stubbed`

and exactly the three ordered permanent blockers shown above. Validation
failures use only this ordered vocabulary:

1. `missing_evidence`
2. `ownership_mismatch`
3. `linkage_mismatch`
4. `fingerprint_mismatch`
5. `invalid_evidence`
6. `stale_evidence`
7. `expired_evidence`
8. `runner_binding_plan_not_active`
9. `runner_binding_scope_mismatch`
10. `worker_reference_unavailable`
11. `worker_reference_ineligible`
12. `worker_scope_mismatch`
13. `inherited_limits_mismatch`
14. `permission_denied`
15. `subject_reserved`
16. `installation_capability_unsupported`

Unknown blockers and arbitrary text are rejected. Home Assistant always
returns `blocked` with `installation_capability_unsupported`; it cannot produce
a stub record.

## Freshness and expiry

- Trusted request time must fall within the active v0.36 admission, active
  v0.37 plan, v0.37 runner reference, and worker reference intervals.
- Maximum inherited age is 30 seconds from the oldest required trusted
  evidence timestamp. No read or record operation refreshes evidence.
- `valid_until` is the earliest upstream expiry and never more than 30 seconds
  after `recorded_at`.
- Clock ambiguity, future timestamps, non-overlapping intervals, equality at
  expiry, stale status, or missing clock evidence fail closed.
- An expired record remains durable evidence and cannot be replaced or replayed.

## Permanent idempotency and no-replay

The subject fingerprint binds operator, candidate, v0.37 plan fingerprint,
worker reference fingerprint, intent fingerprint, and limits fingerprint.

- One transaction permanently reserves both `(operator, idempotency hash)` and
  `(operator, subject hash)` and appends at most one record/audit pair.
- An exact duplicate key/request returns the original record with zero evidence
  reads, worker-reference reads, identity allocation, append, or external I/O.
- Same key/different request and different key/same subject return conflict.
- Reservations survive restart, expiry, corruption recovery, quota errors, and
  ambiguous commit outcomes. There is no delete, release, retry, replay,
  replace, supersede, repair, migration, cleanup, or bypass method.
- Per-operator quota is 16 records; exhaustion fails closed before append.

The closed durable reservation projections are:

```yaml
schema: worker-admission-stub-idempotency-v1
operator_id: <operator id>
idempotency_key_fingerprint: <fingerprint-v1>
request_fingerprint: <fingerprint-v1>
subject_fingerprint: <fingerprint-v1>
stub_id: <uuid4>
stub_fingerprint: <fingerprint-v1>
reservation_state: permanently_reserved
exact_duplicate: true | false
raw_key_persisted: false
retry_allowed: false
replay_allowed: false
```

```yaml
schema: worker-admission-stub-reservation-v1
operator_id: <operator id>
subject_fingerprint: <fingerprint-v1>
idempotency_key_fingerprint: <fingerprint-v1>
stub_id: <uuid4>
reserved_at: <trusted server instant>
reservation_state: permanent
reservation_fingerprint: <fingerprint-v1>
consumed: false
released: false
replaceable: false
supersedable: false
retry_allowed: false
replay_allowed: false
```

## Audit and redaction

```yaml
schema: worker-admission-stub-audit-evidence-v1
event: worker_admission_stub_recorded | worker_admission_stub_read
outcome: recorded | exact_duplicate | read | blocked
operator_fingerprint: <fingerprint-v1>
candidate_record_fingerprint: <fingerprint-v1>
stub_fingerprint: <fingerprint-v1 or null>
correlation_fingerprint: <fingerprint-v1>
occurred_at: <trusted server instant>
audit_fingerprint: <fingerprint-v1>
evidence_only: true
worker_contact_attempted: false
worker_start_attempted: false
enqueue_attempted: false
dispatch_attempted: false
execution_start_attempted: false
agent_invocation_attempted: false
workflow_start_attempted: false
process_execution_attempted: false
mutation_attempted: false
replay_attempted: false
effect_attempted: false
```

```yaml
schema: worker-admission-stub-redacted-error-v1
error_code: malformed | unauthenticated | unauthorized | not_found |
  not_eligible | expired | conflict | quota_exceeded | unavailable
message: worker admission stub request could not be completed
correlation_fingerprint: <fingerprint-v1>
retryable: false
redacted: true
evidence_only: true
worker_start_allowed: false
enqueue_allowed: false
dispatch_allowed: false
execution_authorized: false
mutation_allowed: false
replay_allowed: false
```

Raw idempotency/correlation values, credentials, authorization headers,
provider/runner/worker payloads, endpoints, addresses, ports, queue names,
commands, arguments, environment, images, repository data, logs, stdout,
stderr, internal paths, mount sources, stack traces, and exception text are
forbidden in persistence, responses, audit, and Mission Control.

## Exact result and collection schemas

```yaml
schema: worker-admission-stub-result-v1
disposition: recorded | exact_duplicate | read | blocked
stub: <worker-admission-stub-v1 or null>
status: <worker-admission-stub-status-v1 or null>
audit_evidence: <worker-admission-stub-audit-evidence-v1 or null>
error: <worker-admission-stub-redacted-error-v1 or null>
evidence_only: true
worker_registration_allowed: false
worker_contact_allowed: false
worker_reservation_allowed: false
worker_binding_allowed: false
worker_start_allowed: false
queue_allowed: false
enqueue_allowed: false
dispatch_allowed: false
execution_start_allowed: false
execution_authorized: false
installation_allowed: false
agent_invocation_allowed: false
workflow_allowed: false
mutation_allowed: false
deployment_allowed: false
rollback_allowed: false
retry_allowed: false
replay_allowed: false
```

```yaml
schema: worker-admission-stub-collection-v1
stubs: [<worker-admission-stub-result-v1>, ...]
evidence_only: true
worker_start_allowed: false
enqueue_allowed: false
execution_authorized: false
mutation_allowed: false
```

Success requires record/status/audit agreement. Blocked results contain only a
redacted error. Mixed or partial envelopes are invalid.

## Store and service boundary

P2 may add one independent append-only SQLite evidence store. It contains no
queue/outbox, worker job, executable payload, credential, endpoint, retry
schedule, status mutation, or migration of earlier stores. The service must be
constructed explicitly with injected owner-scoped v0.37 and worker-reference
readers, clock, ID factory, and store. Production construction remains absent
until all readers are authorized by a later phase or release.

The service may only create, get, and list owned evidence. It cannot import or
call execution-worker packages, Core execution/dispatch/provider/repository
systems, Agent clients, network libraries, subprocess/process/container APIs,
workflow engines, schedulers, queues, or deployment code.

## Exact Core API boundary

The only v0.38 paths are:

- `GET /api/v1/installation/candidate-records/{candidate_record_id}/worker-admission-stubs`
- `POST /api/v1/installation/candidate-records/{candidate_record_id}/worker-admission-stubs`
- `GET /api/v1/installation/candidate-records/{candidate_record_id}/worker-admission-stubs/{stub_id}`

No query parameters are accepted. GET has no body. POST requires authenticated
operator identity, record permission, trusted origin, CSRF, visible-ASCII
idempotency key, rate limit, and strict bounded JSON. GET requires read
permission. Foreign and absent records are indistinguishable 404s.

PUT/PATCH/DELETE and sibling `start`, `enqueue`, `queue`, `dispatch`, `run`,
`execute`, `retry`, `resend`, `agent`, `worker`, `install`, `deploy`, `rollback`,
`replay`, or `mutate` routes do not exist. OpenAPI exposes only the methods
above and fixed closed response schemas.

## Mission Control boundary

P4 may add a strict nested evidence panel using list/get only. Creation is not
surfaced because Core exposes no eligible worker-reference context to the
browser. There is no standalone route or navigation item, polling, background
refresh, form, worker selector, queue selector, editable intent or limits,
sensitive rendering, or mutation client beyond the typed but unused P3 create
function.

Copy must say: **This records a worker admission stub only. It does not start
or contact a worker, enqueue work, dispatch, install, or execute anything.** It
must show lifecycle, ordered blockers, worker reference fingerprints, exact
inherited limits, v0.20–v0.37 linkage, ownership context exposed by Core,
freshness/expiry, permanent no-replay, audit, fixed-false authority, redacted
errors, and the blocked Home Assistant golden.

No label/control may imply start, run, execute, install, enqueue, dispatch,
retry/resend, send to Agent, workflow, deploy, rollback, or mutation authority.

## Threat model and goldens

- Forged/foreign linkage, runner plan, worker reference, identity, capability,
  limits, intent, operator, permission, or timestamp fails closed.
- Browser-supplied raw evidence or worker/queue/runtime data is rejected.
- Concurrent requests append once; restart and expiry cannot bypass permanent
  reservations.
- Corruption or ambiguous storage completion cannot enable another attempt.
- Redaction prevents secrets and operational topology entering evidence/UI.
- The pre-existing execution worker, relay, ledger, runner, Agent, workers,
  workflows, dispatch, providers, repositories, and guests have no v0.38
  import, reader, callback, conversion, or consumer.
- Home Assistant is `installation_capability_unsupported`, produces no record,
  remains non-installable/non-executable, and gains no deployment artifact.

## P0–P5 plan

### P0 — Contract and threat model — complete

Freeze exact models, reference/intent, linkage, lifecycle, blockers,
ownership/permissions, freshness, inherited limits, permanent reservations,
audit/redaction, API/UI, threats, later enablement, and must-not-change rules.
Planning documents only.

### P1 — Closed models and pure validation — complete

Added immutable request/intent/reference/linkage/stub/status/reservation/audit/
error/result/collection models, domain-separated fingerprints, bounds,
same-owner/freshness/limit validation, fixed blockers, Home Assistant golden,
and fixed-false authority. No service, store, reader, route, UI, worker, queue,
Agent, or effect.

### P2 — Append-only stub-evidence service and store — complete

Added an explicitly constructed Core service over injected owner-scoped v0.37
and abstract worker-reference readers plus a bounded append-only store. Add
atomic permanent key/subject reservations, exact-duplicate zero-I/O readback,
quotas, corruption closure, and derived expiry. No worker/queue/network/
process/Agent/workflow/dispatch/mutation integration.

### P3 — Exact guarded Core API — complete

Registered only the two permissions and exact candidate-scoped collection GET/
guarded POST plus owned item GET. Lock authentication, origin, CSRF, rate,
body/query/idempotency parsing, ownership non-disclosure, redaction, OpenAPI,
and fail-closed construction. No action or effect sibling.

### P4 — Mission Control evidence presentation — complete

Added only strict create/list/get typing and a nested list/get evidence panel.
Show exact inherited limits/linkage/lifecycle/audit/fixed-false authority,
redaction, and Home Assistant blocking. No surfaced creation without a
server-owned worker context; no polling, selection, form, navigation,
sensitive view, effect label, or other mutation.

### P5 — Isolation, regression, and release closure — complete

Proved concurrent/restart permanent no-replay, secret-free persistence, exact
v0.20–v0.37 linkage and inherited limits, owner/permission isolation, exact
API/UI surfaces, zero execution-worker/Agent/effect consumers, prior-boundary
regressions, and blocked/non-artifact Home Assistant. Tests and release docs
only; no runtime behavior, tag, push, publication, or deployment. Validation
passed both Ruff gates, 98 focused Core tests, 1049 Agent tests, 605 Mission
Control tests, Mission Control lint/build, and `git diff --check`.

## What v0.38 enables later

V0.38 enables a later milestone to require one active exact same-owner worker
admission stub before separately defining a queue-admission or worker-start
boundary. That future contract must independently define real worker identity,
authentication, reachability, intake protocol, queue ownership and durability,
payload construction, capacity, sandbox enforcement, target locking,
consumption, cancellation, ambiguity, recovery, and audit. None is inferred or
authorized here.

## What remains blocked

Worker discovery/registration/contact/reservation/binding/start, queue creation
or enqueue, worker request construction, dispatch, execution authorization or
start, installation, retry/resend, Agent invocation, workflow start,
Docker/Podman/shell/process execution, provider/repository/in-guest mutation,
deployment, rollback, endpoint/credential access, and Home Assistant artifacts
remain blocked. V0.38 records evidence only.

## Must-not-change contracts

1. V0.20–v0.33 retain inert/admission-only/one-shot/append-only/no-replay
   boundaries; v0.34 stays GET-only; v0.35–v0.37 remain unconsumed evidence.
2. V0.37 remains `binding_planned`; a stub never binds, contacts, refreshes,
   consumes, supersedes, or releases its plan or reservations.
3. The abstract worker reference is not the execution worker's identity,
   endpoint, credential, health, queue, ledger, request, or capability lease.
4. The existing execution-worker backend and relay remain independently gated
   and gain no installation-evidence client, route, callback, job, or behavior.
5. Agent gains no stub schema, reader, route, callback, credential, worker
   integration, invocation, executable capability, or behavior.
6. Existing workers, workflows, queues, operational dispatch, provider actions,
   repository execution, guest mutation, deployment, and rollback do not
   consume v0.38 evidence.
7. Core adds no worker/queue client, network transport, scheduler, execution
   token, process launcher, or effect consumer.
8. Mission Control adds no polling, standalone navigation, form, live worker/
   queue selector, editable intent/limits, sensitive view, or effect control.
9. Home Assistant remains blocked, non-installable, non-executable, and has no
   deployment artifact.
10. P0 changes planning documents only. No phase may tag, push, publish,
    release, deploy, or expand authority as an incidental step.
