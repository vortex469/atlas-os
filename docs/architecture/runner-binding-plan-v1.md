# Runner Binding Plan v1 planning contract

Status: **Atlas v0.37 P0 selected; P1–P5 not implemented**.

Atlas v0.37 defines one closed, durable Core evidence record stating that an
authenticated operator planned the possible future binding of one exact,
eligible runner reference to one exact, active v0.36 installation-execution
admission under fixed sandbox, resource, network, and filesystem ceilings.
It does not register, contact, reserve, bind, or invoke a runner:

`binding plan != runner binding != execution authorization != execution`

The plan is evidence only. Its strongest state is `binding_planned`, with the
permanent blockers `runner_not_bound` and `execution_start_boundary_not_defined`.
No v0.37 output is an execution token, dispatch envelope, capability lease,
credential, endpoint, command, installation instruction, or mutation grant.

## Authority boundary

V0.37 may add only:

- closed Core contract models and pure validation;
- an explicitly constructed, owner-scoped, append-only evidence service/store
  over injected read-only v0.36 admission and runner-reference readers;
- one dedicated create permission and one owned-read permission;
- candidate-scoped collection `GET`/guarded `POST` and owned item `GET`;
- an optional Mission Control evidence panel using only those three methods.

The sole authority increase is permission to preserve a bounded runner-binding
**plan**. The record cannot be consumed in v0.37 by Agent, a runner, worker,
workflow, dispatch, provider action, repository execution, guest mutation,
deployment, rollback, scheduler, queue, transport, or process launcher.

## Normative constants and bounds

```text
CONTRACT_VERSION = 1
CREATE_PERMISSION = "installation.runner.binding.plan.record"
READ_PERMISSION = "installation.runner.binding.plan.read"
REQUEST_MAX_BYTES = 4096
RESPONSE_MAX_BYTES = 65536
MAX_JSON_DEPTH = 8
MAX_IDEMPOTENCY_KEY_BYTES = 128
MAX_CORRELATION_ID_BYTES = 128
MAX_RECORDS_PER_OPERATOR = 256
MAX_FRESHNESS_SECONDS = 30
MAX_PLAN_LIFETIME_SECONDS = 30
RUNNER_KIND = "isolated_installation_runner"
RUNNER_SCOPE = "installation_runner_binding_plan_only"
SANDBOX_PROFILE = "atlas-installation-confined-v1"
CPU_MILLIS_MAX = 1000
MEMORY_BYTES_MAX = 536870912
PIDS_MAX = 64
EPHEMERAL_BYTES_MAX = 268435456
WALL_TIME_SECONDS_MAX = 900
OUTPUT_BYTES_MAX = 1048576
```

IDs are lowercase canonical UUIDv4 strings. Times are UTC second-precision
`YYYY-MM-DDTHH:MM:SSZ`. Operator IDs, permission names, correlation IDs, and
opaque reference labels are normalized visible ASCII with no control
characters. Fingerprints are closed `{algorithm: "sha256", value: <64 lower
hex>}` objects. Unknown fields, duplicate JSON keys, non-canonical values,
unbounded strings, and non-finite or coercible numeric values are rejected.

Every fingerprint is SHA-256 over canonical UTF-8 JSON (sorted object keys,
compact separators, exact strings and integers) prefixed by the stated domain
and one NUL byte. The fingerprint field itself is omitted from its input.

## Exact create request

```yaml
RunnerBindingPlanCreateV1:
  schema: "runner-binding-plan-create-v1"
  admission_id: CanonicalUuid4
  admission_fingerprint: FingerprintV1
  admission_valid_until: UtcSecond
  runner_reference_id: CanonicalUuid4
  runner_reference_fingerprint: FingerprintV1
  limits_fingerprint: FingerprintV1
  requested_scope: "installation_runner_binding_plan_only"
  evidence_only: true
  runner_binding_allowed: false
  execution_authorized: false
  worker_start_allowed: false
  dispatch_allowed: false
  replay_allowed: false
```

The client supplies no operator ID, timestamp, evidence body, runner endpoint,
address, credential, command, image, mount path, environment value, or arbitrary
metadata. Core obtains the authenticated operator, permissions, trusted time,
v0.36 admission, runner reference, and exact limits from server-owned
dependencies. `limits_fingerprint` is an acknowledgement of the server-owned
profile returned in the surrounding read context; it cannot replace it.

The POST additionally requires a visible-ASCII `Idempotency-Key` header of
1–128 bytes. The raw key is never modeled, persisted, logged, or returned.

## Exact runner reference and limits

```yaml
RunnerReferenceV1:
  schema: "installation-runner-reference-v1"
  runner_reference_id: CanonicalUuid4
  owner_operator_id: OperatorId
  runner_kind: "isolated_installation_runner"
  trust_domain: "atlas-installation"
  scope: "installation_runner_binding_plan_only"
  eligibility: "eligible_for_binding_plan_only"
  identity_fingerprint: FingerprintV1
  capability_profile_fingerprint: FingerprintV1
  limits: RunnerBindingLimitsV1
  valid_from: UtcSecond
  valid_until: UtcSecond
  reference_fingerprint: FingerprintV1
  registered: false
  available: false
  contacted: false
  reserved: false
  invocation_allowed: false

RunnerBindingLimitsV1:
  schema: "runner-binding-limits-v1"
  sandbox: RunnerSandboxLimitsV1
  resources: RunnerResourceLimitsV1
  network: RunnerNetworkLimitsV1
  filesystem: RunnerFilesystemLimitsV1
  limits_fingerprint: FingerprintV1

RunnerSandboxLimitsV1:
  profile: "atlas-installation-confined-v1"
  privileged: false
  privilege_escalation: false
  host_pid_namespace: false
  host_ipc_namespace: false
  host_network_namespace: false
  host_devices: false
  capabilities_drop_all: true
  seccomp_required: true
  apparmor_required: true

RunnerResourceLimitsV1:
  cpu_millis_max: 1000
  memory_bytes_max: 536870912
  pids_max: 64
  wall_time_seconds_max: 900
  output_bytes_max: 1048576

RunnerNetworkLimitsV1:
  mode: "none"
  ingress_allowed: false
  egress_allowed: false
  dns_allowed: false
  image_pull_allowed: false
  allowed_endpoint_fingerprints: []

RunnerFilesystemLimitsV1:
  root_filesystem_read_only: true
  host_mounts_allowed: false
  repository_mount_allowed: false
  guest_mount_allowed: false
  internal_path_disclosure_allowed: false
  ephemeral_workspace_allowed: true
  ephemeral_workspace_bytes_max: 268435456
  writable_scope: "ephemeral_workspace_only"
```

The reference is a Core-readable eligibility artifact, not registration or
discovery. `identity_fingerprint` identifies an abstract runner principal;
`capability_profile_fingerprint` binds separately reviewed capability evidence.
Neither permits Core to infer an endpoint, credential, availability, or live
capability. The same authenticated operator must own the candidate, v0.36
admission, and runner reference.

The limits are immutable ceilings for a future boundary. V0.37 neither creates
a sandbox nor proves enforcement. A future binder must enforce equal-or-
stricter limits independently. Network `none` means no ingress, egress, DNS,
port exposure, endpoint exception, or image pull. Filesystem writes mean only
a future isolated ephemeral workspace: never a host, repository, provider, or
guest mount. Any less restrictive value is invalid in v0.37.

Fingerprint domains are:

```text
atlas:runner-sandbox-limits:v1
atlas:runner-resource-limits:v1
atlas:runner-network-limits:v1
atlas:runner-filesystem-limits:v1
atlas:runner-binding-limits:v1
atlas:installation-runner-reference:v1
```

## Exact linkage and plan

```yaml
RunnerBindingPlanLinkageV1:
  schema: "runner-binding-plan-linkage-v1"
  operator_id: OperatorId
  candidate_record_id: CanonicalUuid4
  execution_admission_linkage: InstallationExecutionAdmissionLinkageV1
  v020_v035_chain_fingerprint: FingerprintV1
  readiness_review_fingerprint: FingerprintV1
  permission_grant_fingerprint: FingerprintV1
  execution_admission_id: CanonicalUuid4
  execution_admission_fingerprint: FingerprintV1
  execution_admission_status_fingerprint: FingerprintV1
  runner_reference_id: CanonicalUuid4
  runner_reference_fingerprint: FingerprintV1
  runner_identity_fingerprint: FingerprintV1
  runner_capability_profile_fingerprint: FingerprintV1
  limits_fingerprint: FingerprintV1
  linkage_fingerprint: FingerprintV1

RunnerBindingPlanV1:
  schema: "runner-binding-plan-v1"
  plan_id: CanonicalUuid4
  operator_id: OperatorId
  candidate_record_id: CanonicalUuid4
  recorded_at: UtcSecond
  valid_until: UtcSecond
  record_state: "recorded"
  lifecycle: "active"
  eligibility: "binding_planned"
  blockers:
    - "runner_not_bound"
    - "execution_start_boundary_not_defined"
  linkage: RunnerBindingPlanLinkageV1
  runner_reference: RunnerReferenceV1
  limits: RunnerBindingLimitsV1
  idempotency_key_fingerprint: FingerprintV1
  request_fingerprint: FingerprintV1
  plan_fingerprint: FingerprintV1
  evidence_only: true
  runner_registered: false
  runner_contacted: false
  runner_reserved: false
  runner_bound: false
  execution_start_allowed: false
  execution_authorized: false
  installation_allowed: false
  dispatch_allowed: false
  retry_allowed: false
  resend_allowed: false
  agent_invocation_allowed: false
  worker_allowed: false
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

Core re-reads and validates the entire same-owner v0.20–v0.35 chain through the
v0.36 admission dependency, including the exact v0.34 readiness-review and
v0.35 permission-grant fingerprints. It then recomputes the v0.36 admission,
status, runner-reference, identity, capability-profile, limit, linkage,
request, and plan fingerprints. No client assertion can repair or replace a
missing or mismatched server-owned artifact.

Fingerprint domains are:

```text
atlas:runner-binding-plan-linkage:v1
atlas:runner-binding-plan-request:v1
atlas:runner-binding-plan:v1
```

`execution_admission_linkage` is the complete released v0.36 linkage object. It
transitively contains the released v0.35 permission-grant linkage and therefore
every required v0.20–v0.34 fingerprint; the adjacent v0.35 and v0.36 fields are
exact equality locks, not lossy summaries. V0.37 does not flatten, reinterpret,
or change any earlier fingerprint domain.

## Lifecycle, eligibility, and blockers

The only persisted lifecycle is `active`; readback derives `expired` once
`observed_at >= valid_until`. Expiry never deletes, refreshes, supersedes,
reopens, or permits another plan. The closed readback lifecycle vocabulary is:

```text
active
expired
```

The closed successful eligibility vocabulary is:

```text
binding_planned
```

The ordered blocker vocabulary is:

```text
authentication_required
permission_required
owner_mismatch
evidence_missing
evidence_linkage_mismatch
evidence_fingerprint_mismatch
evidence_stale
evidence_expired
execution_admission_not_active
execution_admission_not_admission_gated
runner_reference_missing
runner_reference_owner_mismatch
runner_reference_ineligible
runner_reference_expired
runner_identity_mismatch
runner_capability_mismatch
limits_mismatch
home_assistant_unsupported
runner_not_bound
execution_start_boundary_not_defined
```

Validation failures return `blocked` in a result and append nothing. Every
successful record has exactly the last two blockers, in that order. A plan can
never state `bound`, `ready`, `authorized`, `executable`, or `installed`.

Home Assistant is the golden blocked case. A Home Assistant candidate is
rejected with `home_assistant_unsupported`; no plan or reservation is appended,
and no deployment artifact, image, Compose file, command, or exception is
created.

## Ownership, authentication, and permissions

```yaml
RunnerBindingPlanAuthorityContextV1:
  schema: "runner-binding-plan-authority-context-v1"
  authenticated_operator_id: OperatorId
  permission: "installation.runner.binding.plan.record"
  permission_verified: true
  request_received_at: UtcSecond
  request_time_source: "core_trusted_whole_second_utc_clock"
```

- Core uses only the authenticated server principal; no body operator is
  accepted.
- Create requires `installation.runner.binding.plan.record`.
- List/get require `installation.runner.binding.plan.read`.
- Candidate, complete evidence chain, v0.36 admission, runner reference, plan,
  and reservations share the same operator owner.
- Foreign and absent item reads are indistinguishable `404 not_found`; lists
  contain owned records only.
- POST requires the existing session/authentication boundary, trusted origin,
  CSRF protection, and a dedicated rate-limit bucket.
- Authentication and permission never imply runner registration, binding,
  invocation, execution, or mutation authority.

## Freshness and expiry

Core owns `request_received_at` and `observed_at`. At create time:

```text
0 <= request_received_at - admission.recorded_at <= 30 seconds
0 <= request_received_at - runner_reference.valid_from <= 30 seconds
request_received_at < admission.valid_until
request_received_at < runner_reference.valid_until
valid_until = min(
  request_received_at + 30 seconds,
  admission.valid_until,
  runner_reference.valid_until,
)
```

The v0.34/v0.35/v0.36 inherited freshness and earliest-expiry rules remain
authoritative and are never extended. Clock skew, future timestamps, equality
at expiry, missing status, ambiguity, or stale evidence fail closed. Readback
may derive expiry only; it cannot refresh evidence or create a replacement.

## Permanent idempotency and no replay

```yaml
RunnerBindingPlanIdempotencyV1:
  schema: "runner-binding-plan-idempotency-v1"
  operator_id: OperatorId
  idempotency_key_fingerprint: FingerprintV1
  request_fingerprint: FingerprintV1
  retained_forever: true
  retry_allowed: false
  replay_allowed: false

RunnerBindingPlanReservationV1:
  schema: "runner-binding-plan-reservation-v1"
  operator_id: OperatorId
  candidate_record_id: CanonicalUuid4
  execution_admission_fingerprint: FingerprintV1
  runner_reference_fingerprint: FingerprintV1
  limits_fingerprint: FingerprintV1
  subject_fingerprint: FingerprintV1
  idempotency_key_fingerprint: FingerprintV1
  request_fingerprint: FingerprintV1
  plan_id: CanonicalUuid4
  reserved_at: UtcSecond
  reservation_state: "permanent"
  retained_forever: true
  releasable: false
  replay_allowed: false
  reservation_fingerprint: FingerprintV1
```

Before appending, one transaction reserves permanently:

1. `(operator_id, sha256(raw_idempotency_key))`; and
2. `(operator_id, candidate_record_id, execution_admission_fingerprint,
   runner_reference_fingerprint, limits_fingerprint)`.

The request fingerprint binds the authenticated operator, candidate ID, exact
create model, trusted request time, and idempotency-key fingerprint. The raw key
is excluded. An exact retry using the same key and request fingerprint returns
the original record without invoking evidence readers, clocks used for create,
or ID factories. Same key/different request or different key/same subject is
`conflict`. Reservations survive restart and expiry forever. There is no
consume, release, delete, retry, resend, replay, refresh, replace, revoke,
supersede, administrative bypass, or migration shortcut.

Fingerprint domains are `atlas:runner-binding-plan-idempotency:v1`,
`atlas:runner-binding-plan-subject:v1`, and
`atlas:runner-binding-plan-reservation:v1`.

## Result, audit, errors, and redaction

```yaml
RunnerBindingPlanStatusV1:
  schema: "runner-binding-plan-status-v1"
  plan_id: CanonicalUuid4
  observed_at: UtcSecond
  lifecycle: "active" | "expired"
  eligibility: "binding_planned"
  blockers: ["runner_not_bound", "execution_start_boundary_not_defined"]
  status_fingerprint: FingerprintV1
  evidence_only: true
  runner_bound: false
  execution_authorized: false
  replay_allowed: false

RunnerBindingPlanAuditEvidenceV1:
  schema: "runner-binding-plan-audit-evidence-v1"
  event: "runner_binding_plan_recorded" | "runner_binding_plan_read"
  outcome: "recorded" | "exact_duplicate" | "read" | "blocked"
  operator_fingerprint: FingerprintV1
  candidate_record_fingerprint: FingerprintV1
  plan_fingerprint: FingerprintV1 | null
  correlation_fingerprint: FingerprintV1
  occurred_at: UtcSecond
  audit_fingerprint: FingerprintV1
  evidence_only: true
  effect_attempted: false
  replay_attempted: false

RunnerBindingPlanRedactedErrorV1:
  schema: "runner-binding-plan-redacted-error-v1"
  error_code: "malformed" | "unauthenticated" | "unauthorized" | "not_found" | "not_eligible" | "expired" | "conflict" | "quota_exceeded" | "unavailable"
  message: "runner binding plan request could not be completed"
  correlation_fingerprint: FingerprintV1
  retryable: false
  evidence_only: true
  execution_authorized: false
  mutation_allowed: false
  replay_allowed: false

RunnerBindingPlanResultV1:
  schema: "runner-binding-plan-result-v1"
  disposition: "recorded" | "exact_duplicate" | "read" | "blocked"
  plan: RunnerBindingPlanV1 | null
  status: RunnerBindingPlanStatusV1 | null
  audit_evidence: RunnerBindingPlanAuditEvidenceV1 | null
  error: RunnerBindingPlanRedactedErrorV1 | null
  evidence_only: true
  runner_registration_allowed: false
  runner_contact_allowed: false
  runner_reservation_allowed: false
  runner_binding_allowed: false
  runner_bound: false
  execution_start_allowed: false
  execution_authorized: false
  installation_allowed: false
  dispatch_allowed: false
  agent_invocation_allowed: false
  worker_allowed: false
  workflow_allowed: false
  mutation_allowed: false
  deployment_allowed: false
  rollback_allowed: false
  retry_allowed: false
  replay_allowed: false

RunnerBindingPlanCollectionV1:
  schema: "runner-binding-plan-collection-v1"
  plans: tuple[RunnerBindingPlanResultV1, ...]
  evidence_only: true
  execution_authorized: false
  mutation_allowed: false
```

Audit domains are `atlas:runner-binding-plan-status:v1` and
`atlas:runner-binding-plan-audit:v1`. Audit/result/error bodies contain no raw
idempotency key, cookie, token, credential, provider payload, request/response
body, runner address/endpoint, command/argv, environment value, log/stdout/
stderr, image reference, internal path, mount source, host address, arbitrary
metadata, or exception text. Stores persist only closed models and hashed
identifiers. Corruption, unknown schema versions, invalid fingerprints, and
ambiguous writes fail closed as `unavailable`; they never suggest retry.

## API boundary

The only v0.37 Core paths are:

```text
GET  /api/v1/installation/candidate-records/{candidate_record_id}/runner-binding-plans
POST /api/v1/installation/candidate-records/{candidate_record_id}/runner-binding-plans
GET  /api/v1/installation/candidate-records/{candidate_record_id}/runner-binding-plans/{plan_id}
```

Collection GET and item GET have no request body or query parameters. POST has
the exact closed create body, `Idempotency-Key`, trusted origin, CSRF, auth,
permission, rate, size, depth, content-type, and duplicate-key gates. Other
methods return `405`. There is no `/bind`, `/run`, `/start`, `/execute`,
`/install`, `/dispatch`, `/retry`, `/resend`, `/agent`, `/worker`, `/workflow`,
`/deploy`, `/rollback`, `/replay`, or mutation sibling. OpenAPI exposes only
the closed models and these operations.

No production service construction is allowed until an explicitly injected,
owner-scoped v0.36 evidence reader and runner-reference reader exist. Neither
reader may contact Agent or a runner. Any durable database setting is isolated
from earlier evidence stores and creates no migration in v0.37.

## Mission Control boundary

P4 may add one panel within the v0.36 admission/readiness context. It may list,
read, and use a two-step confirmation to create a binding-plan evidence record.
It presents lifecycle, ordered blockers, complete linkage fingerprints, the
abstract runner reference, exact limit values, expiry, permanent no-replay,
audit, redacted failures, and every fixed-false authority flag.

Copy must say: **This records a runner binding plan only. It does not bind or
contact a runner and does not authorize or start installation or execution.**

There is no standalone navigation, polling, auto-refresh, runner discovery,
runner selector populated from a live endpoint, editable limit, free-form
metadata, raw sensitive field, or bind/run/start/execute/install/deploy/
dispatch/retry/resend/send-to-Agent/start-workflow/rollback control. The only
mutation call is the explicit guarded plan-evidence POST.

## Threats and fail-closed rules

- A forged or stale admission, runner reference, identity, capability, or
  limits fingerprint appends nothing.
- A reference never proves registration, availability, reachability, sandbox
  enforcement, or permission to invoke.
- Limits are ceilings, not commands or a runtime configuration delivery path.
- Admission and grant evidence remain immutable and unconsumed.
- Concurrent creates yield one append and permanent reservations.
- Expiry, restart, storage ambiguity, or corruption cannot enable another
  attempt or an effect.
- Operator enumeration is prevented by owner-scoped reads and indistinguishable
  foreign/not-found behavior.
- Redaction prevents credentials, endpoints, commands, paths, logs, and raw
  provider or runner data from entering persistence, API, UI, or audit output.
- Existing execution/dispatch/worker/workflow/provider/repository/guest systems
  have no v0.37 import, reader, callback, or consumer.

## P0–P5 plan

### P0 — Contract and threat model — complete

Freeze exact models, runner reference, fingerprints/linkage, lifecycle,
eligibility/blockers, ownership/permissions, freshness/expiry, bounded limit
semantics, permanent reservations, audit/redaction, API/UI, threats, later
enablement, and must-not-change contracts. Planning documents only.

### P1 — Closed models and pure validation

Add immutable request/reference/limit/linkage/plan/status/reservation/audit/
error/result models, domain-separated fingerprints, bounds, same-owner and
freshness validation, fixed blockers, Home Assistant golden, and fixed-false
authority. No service, store, reader, route, UI, Agent, runner, or effect.

### P2 — Append-only plan-evidence service and store

Add an explicitly constructed default-off Core service over injected
owner-scoped v0.36 and runner-reference readers plus a bounded append-only
store. Add atomic permanent key/subject reservations, exact-duplicate zero-I/O
readback, quotas, corruption closure, and derived expiry. No external I/O,
registration, runner contact, worker/workflow/process call, dispatch, or
mutation.

### P3 — Exact guarded Core API

Register only the two permissions and candidate-scoped collection GET/guarded
POST plus owned item GET. Lock authentication, origin, CSRF, rate, body/query/
idempotency parsing, ownership non-disclosure, redaction, OpenAPI, and fail-
closed construction. No action or effect sibling.

### P4 — Mission Control plan-evidence presentation

Add only the strict P3 client and evidence panel with two-step creation, exact
limits/linkage/lifecycle/audit readback, fixed-false authority, redaction, and
Home Assistant blocked state. No polling, live runner selection, editable
limits, sensitive rendering, effect label, or other mutation.

### P5 — Isolation, regression, and release closure

Prove permanent concurrent single plan, restart/expiry no-replay, secret-free
persistence, complete v0.20–v0.36 linkage, exact runner/limit fingerprints,
owner/permission isolation, exact API/UI surfaces, zero effect consumers,
Agent capability parity, prior-boundary regressions, and blocked/non-artifact
Home Assistant. Tests and release docs only; no runtime behavior, tag, push,
publication, or deployment.

## What v0.37 enables later

V0.37 enables a later release to require one active, exact, same-owner runner-
binding plan before separately defining an authenticated binding act. That
future contract must independently define live runner registration and trust,
endpoint/credential handling, capability attestation, availability, sandbox
enforcement, resource allocation, target locking, admission/plan consumption,
failure and ambiguity, revocation, and audit. A still-later execution-start
boundary must define dispatch and effect semantics. Neither is inferred or
authorized here.

## What remains blocked

Live runner discovery/registration/contact/reservation/binding/invocation,
execution authorization/start, executable intent, installation, worker or
workflow start, dispatch, retry/resend, Agent invocation, Docker/Podman/shell/
process execution, provider/repository/in-guest mutation, deployment,
rollback, credential or endpoint access, and Home Assistant artifacts remain
blocked. V0.37 records evidence only.

## Must-not-change contracts

1. V0.20–v0.33 retain their inert, admission-only, one-shot, append-only, and
   no-replay boundaries.
2. V0.34 remains GET-only readiness review; v0.35 remains append-only
   permission evidence; neither is refreshed, mutated, or consumed.
3. V0.36 remains `admission_gated` evidence; planning never mutates, consumes,
   refreshes, supersedes, or releases its reservations.
4. A runner reference remains an abstract server-owned eligibility artifact,
   not registration, discovery, availability, endpoint, credential, or live
   capability.
5. Agent gains no runner-binding schema, route, callback, credential,
   registration, invocation, executable capability, or behavior.
6. Existing workers, workflows, operational dispatch, provider actions,
   repository execution, guest mutation, deployment, and rollback do not
   consume v0.37 evidence.
7. Core adds no live runner registry, network client, queue, scheduler,
   transport, execution token, process launcher, or effect consumer.
8. Mission Control adds no polling, live runner selector, editable limits,
   sensitive view, standalone navigation, or effect control.
9. Home Assistant remains blocked, non-installable, non-executable, and has no
   deployment artifact.
10. P0 changes planning documents only. No phase may tag, push, publish,
    release, migrate, or deploy except through a separately requested action.
