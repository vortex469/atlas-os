# Installation Execution Admission v1 planning contract

Status: **Atlas v0.36 P0 selected; P1–P5 not implemented**.

Atlas v0.36 defines one closed, durable Core evidence record stating that an
authenticated operator's exact, fresh v0.20–v0.35 installation chain satisfies
the evidence prerequisites for later runner consideration. It does not select,
register, invoke, or authorize a runner and it cannot start an effect:

`admission evidence != runner binding != execution authorization`

and:

`record admission != install != execute != dispatch`.

## Repository inspection baseline

Planning starts from `main` at
`adb74c2a49fee28483ebe48c703b6887bcee7ee9`, after annotated tag
`atlas-v0.35.0` targeting
`5c56940e21db9e80a9470d2db434415d02dff9ac` and the v0.35 checklist
reconciliation merged to `main`.

The released chain contains the exact v0.20–v0.33 installation evidence,
v0.34 read-only readiness review, and v0.35 durable operator permission grant.
No released Agent capability, worker, workflow, operational dispatch,
repository executor, provider action, or deployment surface consumes that
chain for installation execution. Home Assistant remains the blocked golden.

## Exact authority boundary

V0.36 may authenticate an operator, require a dedicated permission, re-read
same-owner Core-local v0.34 and v0.35 evidence, recompute the complete linkage,
evaluate freshness and a closed blocker vocabulary, permanently reserve one
grant subject, append one bounded admission-evidence record, and return owned
list/readback with derived active/expired status.

That is the entire authority increase. The new permissions are exactly:

```text
installation.execution.admission.record
installation.execution.admission.read
```

They authorize only admission-evidence creation and owned observation. They do
not imply any existing read, grant, operational, workflow, provider,
repository, Agent, deployment, or execution permission, and no existing
permission implies them. The v0.35 grant is validated but never mutated,
consumed, refreshed, released, or converted into executable authority.

V0.36 must not start a worker or workflow, dispatch, retry/resend, invoke
Agent, load a credential, run Docker/Podman/shell/process commands, mutate a
provider/repository/guest, install, deploy, roll back, or create an executable
intent. No runner identity, endpoint, command, payload, or credential enters
the contract.

## Canonical primitives and bounds

- Released `UUIDv4`, `UUIDv5`, `UtcSecond`, `FingerprintV1`, canonical NFC JSON,
  and lower-case SHA-256 rules are unchanged.
- Every model is immutable, strict, closed, duplicate-key rejecting, NFC
  validating, and rejects unknown fields.
- The create body is at most 8 KiB with JSON nesting at most four.
- An admission, status, eligibility, audit, reservation, or error is at most
  64 KiB; one result or collection item is at most 128 KiB.
- No free-form metadata, note, reason, description, URL, address, endpoint,
  header, body, command, log, path, provider payload, credential reference, or
  credential value is accepted or returned.

`FingerprintV1` remains exactly:

```text
{ algorithm: "sha256", canonicalization: "atlas-jcs-nfc-v1", value: LowerHex64 }
```

## Exact admission request

The path supplies `candidate_record_id`; authenticated identity and trusted
request time are server-owned:

```text
InstallationExecutionAdmissionCreateV1 = {
  schema: "installation-execution-admission-create-v1",
  permission_grant_id: UUIDv4,
  permission_grant_fingerprint: FingerprintV1,
  grant_valid_until: UtcSecond,
  requested_scope: "future_installation_runner_consideration_only",
  runner_eligibility_claim: "evidence_chain_only_no_runner_selected",
  execution_authorized: false,
  installation_allowed: false,
  dispatch_allowed: false,
  worker_allowed: false,
  mutation_allowed: false,
  replay_allowed: false
}
```

The body cannot choose operator, admission ID, timestamps, linkage, blockers,
status, runner identity, reservation, audit, or any true authority field. Core
accepts no client-supplied v0.20–v0.34 evidence. Request fingerprint domain is
`atlas:installation-execution-admission-request:v1` over authenticated operator
ID, path candidate ID, exact create body, and idempotency-key fingerprint.

## Exact required linkage and fingerprints

```text
InstallationExecutionAdmissionLinkageV1 = {
  permission_grant_linkage: ExecutionPermissionGrantLinkageV1,
  v035_grant_id: UUIDv4,
  v035_grant_fingerprint: FingerprintV1,
  v035_status_fingerprint: FingerprintV1,
  v035_request_fingerprint: FingerprintV1,
  v035_confirmation_fingerprint: FingerprintV1,
  v035_operator_fingerprint: FingerprintV1,
  v034_review_fingerprint: FingerprintV1,
  v034_audit_evidence_fingerprint: FingerprintV1,
  chain_fingerprint: FingerprintV1,
  linkage_fingerprint: FingerprintV1
}
```

`permission_grant_linkage` is exactly the released v0.35 linkage and thereby
embeds the complete v0.20–v0.34 IDs, fingerprints, transitive links, fixed
receipt facts, v0.34 review/audit/operator fingerprints, and v0.35 grant
subject. Core recomputes every fingerprint from authoritative same-owner
records. Grant ID/fingerprint, candidate, operator, request, confirmation,
scope, record, status, validity, and all transitive links must match exactly.

`chain_fingerprint` uses domain
`atlas:installation-execution-admission-chain:v1` over the canonical complete
v0.20–v0.35 chain. `linkage_fingerprint` uses domain
`atlas:installation-execution-admission-linkage:v1` over this model excluding
itself. Fingerprints from other domains are never interchangeable.

## Closed readiness and blocker vocabulary

Readiness is exactly `blocked | admission_gated`. Blockers are unique and in
this fixed order:

```text
missing_evidence
ownership_mismatch
linkage_mismatch
fingerprint_mismatch
invalid_evidence
stale_evidence
expired_evidence
grant_not_active
grant_scope_mismatch
grant_unavailable
permission_denied
subject_reserved
installation_capability_unsupported
runner_binding_not_defined
execution_start_boundary_not_defined
```

Validation failures are `blocked` and append no admission. A successful record
is always `admission_gated` with exactly the final two blockers, in order:
`runner_binding_not_defined`, `execution_start_boundary_not_defined`. No
released runner is selected or eligible for invocation. No state named
`ready`, `executable`, `authorized`, `installable`, `dispatchable`, `running`,
or `completed` exists.

## Runner eligibility evidence

```text
InstallationRunnerEligibilityV1 = {
  schema: "installation-runner-eligibility-v1",
  evaluation: "evidence_chain_eligible",
  scope: "future_installation_runner_consideration_only",
  evaluated_at: UtcSecond,
  admission_gated: true,
  runner_selected: false,
  runner_registered: false,
  runner_available: false,
  runner_invocation_allowed: false,
  worker_start_allowed: false,
  workflow_start_allowed: false,
  execution_start_boundary_defined: false,
  evidence_only: true,
  eligibility_fingerprint: FingerprintV1
}
```

This model means only that the evidence chain passed v0.36 validation. It does
not claim any actual runner exists or can execute. Its fingerprint domain is
`atlas:installation-runner-eligibility:v1`.

## Exact durable admission record

```text
InstallationExecutionAdmissionV1 = {
  schema: "installation-execution-admission-v1",
  admission_id: UUIDv4,
  operator_id: CanonicalOperatorId,
  candidate_record_id: UUIDv4,
  recorded_at: UtcSecond,
  valid_until: UtcSecond,
  record_state: "recorded",
  readiness: "admission_gated",
  blockers: ["runner_binding_not_defined", "execution_start_boundary_not_defined"],
  scope: "future_installation_runner_consideration_only",
  linkage: InstallationExecutionAdmissionLinkageV1,
  runner_eligibility: InstallationRunnerEligibilityV1,
  idempotency_key_fingerprint: FingerprintV1,
  request_fingerprint: FingerprintV1,
  admission_evidence_recorded: true,
  evidence_only: true,
  execution_authorized: false,
  installation_allowed: false,
  dispatch_allowed: false,
  retry_allowed: false,
  resend_allowed: false,
  agent_invocation_allowed: false,
  worker_allowed: false,
  workflow_allowed: false,
  docker_allowed: false,
  podman_allowed: false,
  shell_allowed: false,
  process_allowed: false,
  provider_mutation_allowed: false,
  repository_mutation_allowed: false,
  in_guest_mutation_allowed: false,
  deployment_allowed: false,
  rollback_allowed: false,
  replay_allowed: false,
  admission_fingerprint: FingerprintV1
}
```

Admission fingerprint domain is
`atlas:installation-execution-admission:v1`. The record is append-only: no
update, consume, revoke, release, refresh, extend, delete, execute, dispatch,
retry, replay, or effect transition exists.

## Lifecycle and freshness

```text
InstallationExecutionAdmissionStatusV1 = {
  schema: "installation-execution-admission-status-v1",
  admission_id: UUIDv4,
  admission_fingerprint: FingerprintV1,
  observed_at: UtcSecond,
  lifecycle: "active" | "expired",
  readiness: "admission_gated",
  evidence_only: true,
  execution_authorized: false,
  installation_allowed: false,
  worker_allowed: false,
  replay_allowed: false,
  status_fingerprint: FingerprintV1
}
```

`active` means only `observed_at < valid_until` and all inherited prerequisites
remain current. `expired` preserves immutable evidence but cannot satisfy later
freshness. Status is derived and never mutates the row. Status fingerprint
domain is `atlas:installation-execution-admission-status:v1`.

At trusted `recorded_at`, the v0.35 grant must be `active`, no more than 30
seconds old, its v0.34 review and all inherited evidence must still be current,
and Home Assistant must remain blocked. `valid_until` is the earliest of the
v0.35 grant expiry, every inherited non-null expiry, and
`recorded_at + 30 seconds`. Core requires `recorded_at < valid_until` and never
rounds forward, refreshes, extends, or restarts a window.

## Ownership, authentication, and permissions

Authenticated principal, path candidate, complete v0.20–v0.35 chain,
reservation, admission, and readback must share one exact operator owner.
Foreign and absent objects are indistinguishable. Operator identity is never
accepted from a body or header.

POST requires an authenticated Core session,
`installation.execution.admission.record`, allowed HTTPS origin, valid CSRF,
bounded mutation rate, exact closed JSON, and visible-ASCII `Idempotency-Key`.
Owned list/get require `installation.execution.admission.read` without mutation
CSRF semantics. The grant's permission scope must be exactly
`future_execution_admission_consideration_only`; the new record narrows that to
future runner consideration and never expands it.

## Permanent idempotency and no replay

Only the fingerprint of a 1–128 byte printable-ASCII idempotency key is stored,
using domain `atlas:installation-execution-admission-idempotency:v1` over
operator ID and raw key. Core atomically reserves forever:

```text
(operator_id, idempotency_key_fingerprint)
(operator_id, candidate_record_id, v035_grant_fingerprint)
```

An exact duplicate returns the original record and performs zero evidence
reads, ID allocations, appends, touches, refreshes, retries, replays, or
effects. Any changed key/request/subject conflicts. Expiry, restart,
corruption, ambiguous response, or deletion attempts cannot release either
reservation. Concurrent exact requests yield one record. There is no retry
daemon, scheduler, polling, resend, replay, reconciliation mutation, or bypass.

## Audit and redaction

```text
InstallationExecutionAdmissionAuditEvidenceV1 = {
  schema: "installation-execution-admission-audit-evidence-v1",
  admission_id: UUIDv4 | null,
  candidate_record_id: UUIDv4 | null,
  operator_fingerprint: FingerprintV1,
  request_fingerprint: FingerprintV1 | null,
  idempotency_key_fingerprint: FingerprintV1 | null,
  v035_grant_fingerprint: FingerprintV1 | null,
  linkage_fingerprint: FingerprintV1 | null,
  eligibility_fingerprint: FingerprintV1 | null,
  admission_fingerprint: FingerprintV1 | null,
  blocker_codes: BlockerV1[],
  correlation_id: CanonicalCorrelationId,
  occurred_at: UtcSecond,
  outcome: "recorded" | "exact_duplicate" | "rejected" | "unavailable",
  evidence_only: true,
  execution_attempted: false,
  dispatch_attempted: false,
  agent_invoked: false,
  worker_started: false,
  workflow_started: false,
  process_started: false,
  mutation_attempted: false,
  retry_attempted: false,
  replay_attempted: false,
  evidence_fingerprint: FingerprintV1
}
```

Audit fingerprint domain is
`atlas:installation-execution-admission-audit-evidence:v1`. Audit and storage
contain no raw idempotency key, cookie, CSRF token, credential, provider
payload, request/response body, endpoint, address, command, log, exception, or
internal path.

```text
InstallationExecutionAdmissionRedactedErrorV1 = {
  schema: "installation-execution-admission-error-v1",
  error_code:
    "malformed" | "unauthenticated" | "unauthorized" | "not_found" |
    "not_eligible" | "expired" | "conflict" | "quota_exceeded" | "unavailable",
  safe_message: "Installation execution admission evidence could not be recorded.",
  blocker_codes: BlockerV1[],
  correlation_id: CanonicalCorrelationId,
  redacted: true,
  retryable: false,
  evidence_only: true,
  execution_authorized: false,
  installation_allowed: false,
  mutation_allowed: false,
  replay_allowed: false
}
```

Foreign and absent use `not_found`; detailed ownership/linkage/fingerprint
facts are never disclosed. Blockers reveal only closed codes safe for the
authenticated owner.

## Exact result union

```text
InstallationExecutionAdmissionResultV1 = {
  disposition: "recorded" | "exact_duplicate" | "rejected" | "unavailable",
  admission: InstallationExecutionAdmissionV1 | null,
  status: InstallationExecutionAdmissionStatusV1 | null,
  audit_evidence: InstallationExecutionAdmissionAuditEvidenceV1 | null,
  error: InstallationExecutionAdmissionRedactedErrorV1 | null,
  evidence_only: true,
  execution_authorized: false,
  installation_allowed: false,
  dispatch_allowed: false,
  agent_invocation_allowed: false,
  worker_allowed: false,
  workflow_allowed: false,
  mutation_allowed: false,
  deployment_allowed: false,
  rollback_allowed: false,
  retry_allowed: false,
  replay_allowed: false
}
```

Success requires admission/status/audit and no error. Failure returns a closed
redacted error and no admission/status. An ambiguous write never authorizes a
retry or implies success.

## Exact Core API boundary

V0.36 may add only:

```text
POST /api/v1/installation/candidate-records/{candidate_record_id}/execution-admissions
GET  /api/v1/installation/candidate-records/{candidate_record_id}/execution-admissions
GET  /api/v1/installation/candidate-records/{candidate_record_id}/execution-admissions/{admission_id}
```

POST accepts only the exact body and `Idempotency-Key`, without query. GET has
no body or query and returns only same-owner candidate records. There is no
PUT, PATCH, DELETE, install, execute, start, dispatch, retry/resend, Agent,
worker, workflow, Docker/Podman/shell/process, provider/repository/guest
mutation, deploy, rollback, consume, refresh, release, or action sibling.

HTTP outcomes are `200` exact duplicate/read, `201` new evidence, `401`, `403`,
indistinguishable `404`, `409` blocked/expired/conflict, `413`, `415`, `422`,
`429`, and redacted `503`. OpenAPI contains only these operations and closed
models. Production service construction remains fail-closed unless its exact
server-owned evidence readers and independent store are configured.

## Exact Mission Control boundary

Mission Control may add one strict create/list/get client and one evidence
panel inside the existing authenticated installation review context. It shows
the v0.35 grant binding, ordered blockers, `admission_gated` lifecycle,
eligibility evidence, expiry, permanent reservation/no-replay posture, audit,
redacted errors, and all fixed-false authority fields.

Creation, if surfaced, is a two-step explicit flow whose final control is
**Record admission evidence** and whose adjacent copy says: **This records
admission evidence only. It does not select or invoke a runner and does not
install or execute anything.** It invokes only the exact POST. It is never
labeled install, execute, run, dispatch, retry, resend, send to Agent, start
worker/workflow, deploy, or roll back.

There is no polling, automatic refresh, retry/repeat control, free text, raw
payload, credential, endpoint, address, header, command, log, internal path,
provider data, runner selector, Agent control, worker/workflow control, effect
navigation, or mutation outside the explicit admission-evidence POST. Home
Assistant renders blocked and exposes no creation control.

## Threats and fail-closed rules

- A stale or substituted browser grant cannot create evidence; Core rereads and
  recomputes the entire same-owner chain at trusted time.
- A grant is never considered consumed, executable, or refreshed by admission.
- A second key cannot bypass the permanent grant-subject reservation.
- Missing runner binding is a permanent blocker in every successful v0.36
  record, not a UI hint or optional warning.
- Storage/network ambiguity cannot authorize retry, replay, execution, or an
  inferred success.
- No field or label may be treated as a worker job, dispatch request, install
  request, execution token, runner capability, or mutation permission.
- Home Assistant has no exception and no deployment artifact.

## P0–P5 plan

### P0 — Contract and threat model — complete

Freeze exact schemas, fingerprints/linkage, readiness/blockers, lifecycle,
ownership/permissions, freshness, permanent reservations, audit/redaction,
API/UI, threats, later enablement, and must-not-change contracts. Planning docs
only.

### P1 — Closed models and pure validation

Add strict immutable create/linkage/eligibility/admission/status/reservation/
audit/error/result models, domain-separated fingerprints, bounds, ordered
blockers, and pure same-owner/freshness/fixed-authority validation. No service,
store, route, UI, reader, Agent, runner, or effect behavior.

### P2 — Append-only admission-evidence service and store

Add an explicitly constructed default-off Core service over injected
owner-scoped v0.34/v0.35 readers and a bounded append-only local store. Add
atomic permanent key/grant-subject reservations, exact-duplicate zero-I/O
readback, quotas, corruption closure, and derived status. No external I/O,
Agent/runner/worker/workflow/process call, dispatch, or mutation.

### P3 — Exact guarded Core API

Register only the dedicated permissions and exact candidate-scoped collection
GET/guarded POST plus item GET. Lock authentication, origin, CSRF, rate,
body/query/idempotency parsing, ownership non-disclosure, redaction, OpenAPI,
and fail-closed construction. No effect or action sibling.

### P4 — Mission Control admission-evidence presentation

Add only the strict P3 client and evidence panel with two-step creation,
ordered blockers, lifecycle/linkage/eligibility/audit readback, fixed-false
authority, redaction, and Home Assistant blocked state. No polling, sensitive
rendering, runner selector, effect label, or other mutation.

### P5 — Isolation, regression, and release closure

Prove concurrent permanent single admission, restart/expiry no-replay,
secret-free persistence, complete v0.20–v0.35 linkage, owner/permission
isolation, exact API/UI surfaces, zero effect consumers, prior regressions,
Agent capability parity, and blocked/non-artifact Home Assistant. Tests and
release docs only; no runtime behavior, tag, push, publication, or deployment.

## What v0.36 enables later

V0.36 enables a future release to require one active, exact, same-owner
admission-evidence record before separately defining a runner-binding or
execution-start decision. That later release must define runner identity and
authentication, capability negotiation, target locking, grant/admission
consumption, dispatch, execution, failure/ambiguity, recovery, audit, and
rollback contracts. None are inferred or authorized by v0.36.

## What remains blocked

Runner selection/registration/invocation, executable intent, installation,
execution authorization/start, dispatch, retry/resend, Agent invocation,
worker/workflow/process start, Docker/Podman/shell, provider/repository/in-guest
mutation, deployment, rollback, credential access, and Home Assistant
artifacts remain blocked. V0.36 records evidence only.

## Must-not-change contracts

1. V0.20–v0.33 remain evidence artifacts with their released one-shot,
   admission-only, inert, and no-replay boundaries.
2. V0.34 remains GET-only readiness review; its released models and
   fingerprints do not change.
3. V0.35 remains append-only operator permission evidence; admission never
   mutates, consumes, refreshes, revokes, or releases its reservations.
4. Agent gains no installation-execution schema, route, capability, callback,
   credential, registration, or behavior.
5. Existing workers, workflows, operational dispatch, provider actions,
   repository execution, guest mutation, deployment, and rollback do not
   consume v0.36 evidence.
6. Core adds no runner registry, queue, scheduler, transport, execution token,
   process launcher, or effect consumer.
7. Mission Control adds no runner selector, polling, retry, sensitive view, or
   effect control.
8. Home Assistant remains blocked, non-installable, non-executable, and has no
   deployment artifact.
9. P0 changes planning documents only. No phase may tag, push, publish,
   release, migrate, or deploy except through a separately requested action.
