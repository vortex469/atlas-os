# Execution Permission Grant v1 planning contract

Status: **Atlas v0.35 P0 selected; P1–P5 not implemented**.

Atlas v0.35 defines one closed, durable Core evidence artifact recording that
an authenticated operator explicitly permits one exact, currently fresh
v0.20–v0.34 evidence chain to be considered by a future, separately released
execution-admission boundary.

The grant is not execution admission and is never an effect command:

`permission evidence != execution admission != execution authorization`

and:

`record grant != install != execute != dispatch`.

## Repository inspection baseline

Planning starts from `main` at
`5965e3c016a4ee1e6d871d675964cbe40b04e353`, after annotated tag
`atlas-v0.34.0` targeting
`fb3d9014574b5aa85a1024d77fe7b29bf35e1b88`.

The released chain contains v0.20–v0.33 durable and exported evidence plus the
v0.34 owner-scoped read-only review. A v0.34 `readiness_gated` result still has
the sole blocker `execution_admission_not_defined`; no released record admits
or authorizes installation execution. Existing executable intent registries,
Agent capabilities, worker/workflow paths, provider actions, repository
execution, and deployment surfaces do not consume installation evidence.

## Exact authority increase

V0.35 may authenticate an operator, require dedicated create and owned-read
permissions,
re-read the operator's existing Core-local evidence, recompute the exact
v0.20–v0.34 fingerprints, validate exact confirmation text, reserve one
subject permanently, and append one bounded permission-evidence record. It may
return that record and its derived current/expired status to the same owner.

That is the entire authority increase. The permissions are:

```text
installation.execution.permission.grant
installation.execution.permission.grant.read
```

They authorize only creation and owned list/readback of this evidence
artifact. They do not imply `installation.destination.select`, execution admission,
execution authorization, an executable intent, dispatch, or any target effect.
Conversely, existing read, approval, installation, operational, Provider
Intent, repository, or workflow permissions do not imply this permission.

V0.35 must not contact Agent, load a credential, send or resend an envelope,
start a worker/workflow/process, invoke Docker/Podman/shell, mutate a provider,
repository, or guest, install anything, deploy, or roll back.

## Canonical primitives and bounds

- `UUIDv4`, `UUIDv5`, `UtcSecond`, and `FingerprintV1` retain their released
  closed meanings.
- All models are immutable, reject unknown and duplicate fields, reject
  non-NFC text, and use strict types.
- The create body is at most 8 KiB and JSON nesting is at most four.
- A grant, status, audit item, or redacted error is at most 64 KiB; a result is
  at most 128 KiB.
- No model accepts arbitrary metadata, description, reason, comment, URL,
  address, endpoint, header, body, command, log, path, provider payload,
  credential reference, or credential value.

`FingerprintV1` remains exactly:

```text
{
  algorithm: "sha256",
  canonicalization: "atlas-jcs-nfc-v1",
  value: LowerHex64
}
```

## Exact confirmation text

The operator must see and explicitly confirm this exact NFC UTF-8 text,
including capitalization and punctuation:

```text
I confirm that Atlas may record my permission for this exact evidence chain to be considered by a future execution-admission boundary. This does not install or execute anything.
```

No abbreviation, localization, hidden suffix, free-form replacement, boolean
without the displayed text, or server-side substitution is accepted. The
stored confirmation fingerprint is SHA-256 over domain
`atlas:execution-permission-confirmation:v1`, one NUL byte, and the exact UTF-8
text. The raw text is safe and fixed, contains no operator-entered note, and is
stored in the grant for human auditability.

## Exact create request

The path owns `candidate_record_id`; it is not duplicated in the body:

```text
ExecutionPermissionGrantCreateV1 = {
  schema: "execution-permission-grant-create-v1",
  readiness_review_id: UUIDv5,
  readiness_review_fingerprint: FingerprintV1,
  review_observed_at: UtcSecond,
  confirmation_text: ExactConfirmationText,
  permission_scope: "future_execution_admission_consideration_only",
  execution_admission_granted: false,
  execution_authorized: false,
  installation_allowed: false,
  dispatch_allowed: false,
  mutation_allowed: false,
  replay_allowed: false
}
```

The body cannot choose the operator, grant ID, grant time, expiry, linkage,
idempotency fingerprint, or any authority flag. Core obtains operator identity
only from the authenticated session, time only from its trusted whole-second
UTC clock, and linkage only from owner-scoped local readers.

The request fingerprint is SHA-256 over domain
`atlas:execution-permission-grant-request:v1`, one NUL byte, and canonical NFC
JSON of authenticated operator ID, path candidate ID, exact create body, and
the idempotency-key fingerprint. Raw idempotency keys are never persisted.

## Exact required linkage and fingerprints

The grant embeds the complete frozen v0.34 linkage without omission or
reinterpretation:

```text
ExecutionPermissionGrantLinkageV1 = {
  readiness_linkage: InstallationReadinessReviewLinkageV1,
  v034_review_id: UUIDv5,
  v034_review_fingerprint: FingerprintV1,
  v034_audit_evidence_fingerprint: FingerprintV1,
  v034_operator_fingerprint: FingerprintV1,
  linkage_fingerprint: FingerprintV1
}
```

`readiness_linkage` is exactly the released v0.34 object and therefore binds
all v0.20–v0.33 IDs and fingerprints: candidate envelope/record, approval,
Agent validation/audit, destination/plan/artifact policy, execution request,
dispatch handoff, simulation, simulated delivery/acknowledgement, real intake,
dormant preparation, preflight, enablement, one-shot send, Agent live
admission/acknowledgement, inert receipt, receipt verification, and v0.33
linkage fingerprint. It also retains the fixed false exported-receipt claim
and fixed true atomicity-reliance claim from v0.32.

Core must recompute every released fingerprint from the authoritative
same-owner record and require exact ID, fingerprint, transitive-link, operator,
candidate, and time equality. It must recompute the v0.34 review and audit
fingerprints for `review_observed_at`; the review must be
`readiness_gated`, have exactly `execution_admission_not_defined`, and contain
the exact fourteen current evidence summaries. Client-supplied linkage or raw
evidence is forbidden.

The linkage fingerprint is SHA-256 over domain
`atlas:execution-permission-grant-linkage:v1`, one NUL byte, and canonical NFC
JSON of the complete linkage excluding `linkage_fingerprint`.

## Exact durable grant

```text
ExecutionPermissionGrantV1 = {
  schema: "execution-permission-grant-v1",
  grant_id: UUIDv4,
  operator_id: CanonicalOperatorId,
  candidate_record_id: UUIDv4,
  recorded_at: UtcSecond,
  valid_until: UtcSecond,
  record_state: "recorded",
  permission_scope: "future_execution_admission_consideration_only",
  confirmation_text: ExactConfirmationText,
  confirmation_fingerprint: FingerprintV1,
  linkage: ExecutionPermissionGrantLinkageV1,
  idempotency_key_fingerprint: FingerprintV1,
  request_fingerprint: FingerprintV1,
  statement: "operator_recorded_exact_non_executing_permission_evidence",
  permission_evidence_recorded: true,
  evidence_only: true,
  execution_admission_granted: false,
  execution_authorized: false,
  installation_allowed: false,
  dispatch_allowed: false,
  agent_invocation_allowed: false,
  worker_allowed: false,
  workflow_allowed: false,
  provider_mutation_allowed: false,
  repository_mutation_allowed: false,
  in_guest_mutation_allowed: false,
  deployment_allowed: false,
  rollback_allowed: false,
  retry_allowed: false,
  replay_allowed: false,
  grant_fingerprint: FingerprintV1
}
```

The grant fingerprint is SHA-256 over domain
`atlas:execution-permission-grant:v1`, one NUL byte, and canonical NFC JSON of
the complete grant excluding `grant_fingerprint`. Audit/operator,
confirmation, linkage, request, idempotency, and grant fingerprints use
different domains and cannot be substituted for one another.

The grant is append-only. There is no update, revoke, delete, refresh, extend,
consume, approve, admit, execute, or dispatch transition in v0.35. Later
expiry changes only a derived status and never edits the record.

## Lifecycle and status

```text
ExecutionPermissionGrantStatusV1 = {
  schema: "execution-permission-grant-status-v1",
  grant_id: UUIDv4,
  grant_fingerprint: FingerprintV1,
  observed_at: UtcSecond,
  lifecycle: "active" | "expired",
  permission_evidence_recorded: true,
  evidence_only: true,
  execution_admission_granted: false,
  execution_authorized: false,
  installation_allowed: false,
  mutation_allowed: false,
  replay_allowed: false,
  status_fingerprint: FingerprintV1
}
```

`active` means only that trusted `observed_at < valid_until` and every
time-bounded prerequisite remains current. `expired` means the immutable
evidence remains readable but cannot satisfy any later freshness prerequisite.
There is no `ready`, `approved`, `admitted`, `authorized`, `executable`,
`installable`, `consumed`, `revoked`, or `replayable` state.

Status fingerprint domain is
`atlas:execution-permission-grant-status:v1`. Status is derived, not stored as
a mutable lifecycle row.

## Freshness and expiry

The POST uses Core's trusted whole-second UTC time as `recorded_at`. It accepts
only a v0.34 review observed no later than `recorded_at`, no more than 30
seconds earlier, and still exactly current at `recorded_at`. Core applies every
released creation, expiry, freshness, terminal-ambiguity, and no-replay rule;
continued record existence never restores freshness.

`valid_until` is the earliest of:

1. `review_observed_at + 30 seconds`;
2. `recorded_at + 30 seconds`; and
3. every non-null released `valid_until` in the exact v0.34 evidence summary.

Core requires `recorded_at < valid_until`. It cannot round forward, extend,
refresh, restart, or replace a window. Missing, stale, expired, terminal,
ambiguous, blocked, foreign, mismatched, or unavailable evidence cannot create
a grant. Home Assistant is always rejected because its v0.34 review is
`blocked` with `installation_capability_unsupported`.

## Ownership, authentication, and confirmation

All v0.20–v0.34 records, the authenticated principal, the dedicated permission
subject, the path candidate, the reservation, grant, status, and readback must
have one exact operator owner. A foreign and absent candidate or grant are
indistinguishable. Operator IDs are never accepted from a body or header.

POST requires an authenticated session, the dedicated
`installation.execution.permission.grant` permission, an allowed HTTPS origin,
valid CSRF token, bounded mutation rate limit, exact confirmation text, and a
valid `Idempotency-Key`. GET list/readback requires the same authenticated
operator and the independent `installation.execution.permission.grant.read`
permission but no mutation origin/CSRF proof.

## Permanent idempotency and no replay

The raw `Idempotency-Key` is printable ASCII, 1–128 bytes, supplied only on
POST. Its fingerprint domain is
`atlas:execution-permission-grant-idempotency:v1` over authenticated operator
ID, one NUL byte, and the raw key. Only the fingerprint is persisted or
returned.

Before append, Core permanently reserves both:

```text
(operator_id, idempotency_key_fingerprint)
(operator_id, candidate_record_id, v034_review_fingerprint)
```

Reservation and append occur in one local transaction. An exact duplicate
with the same request and key returns the original immutable record with
`exact_duplicate`; it performs no new read composition, ID allocation, append,
touch, refresh, retry, replay, or effect. Reuse with a different request or
key is a conflict. Expiry, restart, error, deletion attempts, or later release
cannot free either reservation. Concurrent exact requests yield one record.

V0.35 has no automatic retry, resend, scheduler, polling, daemon, replay, or
reconciliation action. A transport interruption does not authorize the UI to
submit again; owned GET readback is the only safe observation when the grant
ID is known. Unknown outcomes fail closed and require later separately planned
operator reconciliation rather than another grant.

## Redaction and audit evidence

```text
ExecutionPermissionGrantAuditEvidenceV1 = {
  schema: "execution-permission-grant-audit-evidence-v1",
  grant_id: UUIDv4 | null,
  candidate_record_id: UUIDv4 | null,
  operator_fingerprint: FingerprintV1,
  request_fingerprint: FingerprintV1 | null,
  idempotency_key_fingerprint: FingerprintV1 | null,
  confirmation_fingerprint: FingerprintV1 | null,
  v034_review_fingerprint: FingerprintV1 | null,
  linkage_fingerprint: FingerprintV1 | null,
  grant_fingerprint: FingerprintV1 | null,
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
`atlas:execution-permission-grant-audit-evidence:v1`. Durable audit evidence
contains only closed identities, fingerprints, codes, and fixed authority
facts. It contains no raw key, cookie, CSRF value, credential, endpoint,
request/response body, exception, command, log, path, address, provider data,
or Agent-local record.

```text
ExecutionPermissionGrantRedactedErrorV1 = {
  schema: "execution-permission-grant-error-v1",
  error_code:
    "malformed" | "unauthenticated" | "unauthorized" | "not_found" |
    "confirmation_mismatch" | "not_readiness_gated" | "expired" |
    "conflict" | "quota_exceeded" | "unavailable",
  safe_message: "Execution permission evidence could not be recorded.",
  correlation_id: CanonicalCorrelationId,
  redacted: true,
  retryable: false,
  execution_admission_granted: false,
  execution_authorized: false,
  installation_allowed: false,
  mutation_allowed: false,
  replay_allowed: false
}
```

Foreign and absent objects use `not_found`. Fingerprint/linkage/ownership
details are never returned. Authentication errors contain no candidate,
operator, review, receipt, grant, or fingerprint value.

## Exact result union

```text
ExecutionPermissionGrantResultV1 = {
  disposition: "recorded" | "exact_duplicate" | "rejected" | "unavailable",
  grant: ExecutionPermissionGrantV1 | null,
  status: ExecutionPermissionGrantStatusV1 | null,
  audit_evidence: ExecutionPermissionGrantAuditEvidenceV1 | null,
  error: ExecutionPermissionGrantRedactedErrorV1 | null,
  evidence_only: true,
  execution_admission_granted: false,
  execution_authorized: false,
  installation_allowed: false,
  dispatch_allowed: false,
  agent_invocation_allowed: false,
  worker_allowed: false,
  workflow_allowed: false,
  provider_mutation_allowed: false,
  repository_mutation_allowed: false,
  in_guest_mutation_allowed: false,
  deployment_allowed: false,
  rollback_allowed: false,
  retry_allowed: false,
  replay_allowed: false
}
```

Success requires grant, status, and audit with no error. Failure requires one
redacted error and no grant/status. An unavailable write outcome must not claim
whether a grant exists and cannot be retried automatically.

## Exact Core API boundary

V0.35 may add only:

```text
POST /api/v1/installation/candidate-records/{candidate_record_id}/execution-permission-grants
GET  /api/v1/installation/candidate-records/{candidate_record_id}/execution-permission-grants
GET  /api/v1/installation/candidate-records/{candidate_record_id}/execution-permission-grants/{grant_id}
```

POST has exactly the closed JSON body above plus `Idempotency-Key`; no query
parameters. GET has no body or query. Collection GET returns only owned grants
for the path candidate. There is no PUT, PATCH, DELETE, approve, admit,
execute, install, dispatch, retry, resend, refresh,
consume, revoke, deploy, rollback, or action sibling.

HTTP outcomes are `200` for exact duplicate/readback, `201` for one new grant,
`401` unauthenticated, `403` permission/origin/CSRF rejection, `404` absent or
foreign, `409` conflict/not-readiness-gated/expired, `413` oversized, `415`
wrong media type, `422` malformed/confirmation mismatch, `429` rate limited,
and redacted `503` unavailable. OpenAPI exposes only these three operations and
closed bodies. Existing API discovery gains no implied effect authority.

## Exact Mission Control boundary

Mission Control may add one strict create/readback client and one confirmation
panel inside the existing authenticated v0.34 readiness-review page. The panel
appears only for a `readiness_gated` same-owner response and displays the exact
confirmation text, expiry warning, candidate/review fingerprints, dedicated
permission requirement, and fixed no-effect authority copy.

The operator must explicitly check **I have read and explicitly confirm the
statement above** before the single button **Record permission evidence** is
enabled. The button invokes only the POST above. Success renders the immutable
grant and status. It is never labeled approve, admit, authorize execution,
install, run, execute, dispatch, send, deploy, or start. A blocked or Home
Assistant review shows why permission evidence cannot be recorded and exposes
no mutation control.

There is no polling, automatic refresh, retry/resend, repeat button, form for
free text, raw evidence view, credential, endpoint, address, header, body,
command, log, internal path, provider payload, Agent control, worker/workflow
control, install/execute/dispatch/deploy/rollback control, or global
navigation. Browser refresh may perform only owned GET readback when a known
grant ID is present; it never repeats POST.

## Threats and fail-closed rules

- A stale browser review cannot mint a grant: Core recomputes the exact chain
  and evaluates freshness at trusted current time.
- A foreign candidate, substituted review, reordered evidence summary,
  mismatched fingerprint, or partial linkage fails closed without disclosure.
- A second key cannot create another grant for the same review subject.
- An expired grant remains reserved and cannot be refreshed or replaced.
- A network or storage ambiguity cannot become authorization to retry, replay,
  execute, or infer success.
- Confirmation cannot carry script, markup, notes, credentials, or commands
  because it is one exact literal.
- No grant field, UI label, audit item, or lifecycle state may be interpreted
  as execution admission or executable capability.
- Home Assistant remains the blocked golden and has no exception or artifact.

## P0–P5 plan

### P0 — Contract and threat model — complete

Freeze these exact schemas, linkage/fingerprints, confirmation, ownership,
freshness, permanent reservations, lifecycle, redaction/audit, API/UI,
authority, threats, goldens, and must-not-change contracts. Change planning
documents only.

### P1 — Closed models and pure validation — complete

Add strict immutable create/linkage/grant/status/audit/error/result models,
domain-separated fingerprints, bounds, exact confirmation validation, and pure
same-owner/freshness/authority validation. Add no service, store, route, UI,
Agent access, or runtime composition.

P1 implements those closed models plus explicit idempotency and permanent
reservation shapes. Its pure validation binds the authenticated operator,
dedicated permission expectation, trusted server-owned request time, exact
v0.20–v0.34 fingerprints, maximum inherited 30-second window, fixed-false
authority, redaction, and blocked Home Assistant golden. P1 adds no service,
store, route, UI, persistence, migration, reader, Agent access, or runtime
composition.

### P2 — Append-only reservation service and store — complete

Add an explicitly constructed, default-off Core service over injected
owner-scoped v0.34 evidence readers and one bounded append-only local store.
Implement atomic permanent subject/idempotency reservations, exact-duplicate
readback, quotas, corruption checks, and derived status. Add no external I/O,
credential access, Agent call, dispatch, worker/workflow/process start, or
effect consumer.

P2 implements that boundary as an explicitly constructed Core-local service
over one injected owner-scoped v0.34 evidence reader, trusted whole-second UTC
clock, ID factory, and bounded SQLite store. Grant, sanitized `recorded` audit,
and both permanent reservation subjects append atomically; raw idempotency keys
are never stored. Owned create/get/list are restart-safe, exact duplicates do
not reread evidence or allocate identity, lifecycle is derived without row
updates, and corruption fails closed. No route, permission registration, UI,
external I/O, Agent/worker/workflow call, or effect consumer is added.

### P3 — Exact guarded Core API — complete

Add only the dedicated permission, exact POST, and owned GET. Lock
authentication, origin, CSRF, idempotency, rate limit, body/query bounds,
non-disclosure, redacted errors, OpenAPI, and default-off construction. Add no
effect or action sibling.

P3 applies the explicit implementation-scope amendment to add owner-scoped
collection GET alongside the guarded POST and item GET, with an independent
owned-read permission. It registers only those three operations, validates the
independent durable database path, and locks authentication, trusted origin,
CSRF, mutation rate, strict body/query/idempotency parsing, owner
non-disclosure, redaction, and fixed-false authority. Production service
construction remains unavailable until a server-owned v0.34 evidence reader is
explicitly supplied; no route reaches an Agent, worker, workflow, provider,
repository, guest, process, or effect consumer.

### P4 — Exact Mission Control confirmation surface — complete

Add only the strict client and confirmation/readback panel in the v0.34 review
context. Lock exact text, explicit confirmation, short expiry, ambiguous-write
guidance, Home Assistant absence, no polling/retry, and absence of every effect
control or sensitive field.

Implemented in the existing v0.34 readiness-review context with strict closed
parsing of only the P3 collection `GET`/guarded `POST` and item `GET`. The
two-step flow repeats the exact frozen confirmation and labels the sole write
as durable permission evidence only. Owned readback exposes lifecycle,
inherited 30-second validity/expiry interpretation, exact v0.20–v0.34 linkage
and fingerprints, operator context, permanent reservation/no-replay posture,
sanitized audit evidence, redacted failures, and fixed-false authority. It adds
no polling, effect control, sensitive raw field, Home Assistant artifact, or
mutation outside the explicit grant-evidence create operation.

### P5 — Isolation, regression, and release closure — complete

Prove permanent single grant, concurrency, restart readback, expiry without
refresh, exact duplicate zero-I/O, secret-free persistence, complete linkage
recomputation, permission/owner isolation, exact API/UI surfaces, zero effect
consumers, prior v0.20–v0.34 regressions, Agent capability parity, and blocked
Home Assistant with no artifact. Add release tests/docs only; do not tag, push,
publish, release, or deploy automatically.

P5 adds release-only tests proving the exact collection `GET`/guarded `POST`
and item `GET`, fixed-false authority, concurrent single-record creation,
permanent idempotency and review-subject reservations across restart and
expiry, exact-duplicate zero-reader/zero-ID behavior, corruption closure, and
absence of effect or replay-bypass dependencies. Persistence and Mission
Control rendering are checked for raw idempotency keys, credentials, provider
payloads, commands, logs, internal paths, and addresses. A closed consumer
allowlist keeps v0.34 evidence confined to readiness review and permission
evidence, while Mission Control, Agent regression, and Home Assistant
non-artifact goldens lock the remaining release boundary. No production
behavior or authority changes in P5.

## What v0.35 enables later

V0.35 enables a later release to treat one active, exact, same-owner permission
grant as an additional prerequisite for a separately specified execution-
admission decision. That later release must define its own authority,
authentication, freshness, consumption/no-replay, Agent/runtime capability,
target locking, execution intent, dispatch, failure, audit, and rollback
contracts. It cannot infer those from this grant.

## What remains blocked

Actual installation, execution admission, execution authorization, dispatch,
retry/resend, Agent invocation, worker/workflow/process start,
Docker/Podman/shell execution, provider/repository/in-guest mutation,
deployment, rollback, credential access, new executable intent, and Home
Assistant deployment artifacts remain blocked. V0.35 records evidence only.

## Must-not-change contracts

1. V0.20 remains a non-executable candidate record.
2. V0.21 approval remains intent evidence, not execution permission.
3. V0.22 validation remains unsupported/validate-only and Agent gains no new
   executable `install-container` capability.
4. V0.23–v0.30 remain record, simulation, preparation, preflight, and
   enablement evidence without effect consumers.
5. V0.31 remains independently default-off, one-shot, permanently no-replay,
   with terminal ambiguity and no resend.
6. V0.32 remains admission-only on its exact guarded Agent POST.
7. V0.33 receipt remains inert evidence and authorizes no effect.
8. V0.34 remains a GET-only read review; `readiness_gated` still means
   execution admission is undefined.
9. Existing Agent, worker, workflow, operational dispatch, provider,
   repository, guest, deployment, and rollback authorities do not consume the
   v0.35 grant.
10. Home Assistant remains blocked, non-installable, non-executable, and has
    no deployment artifact.
11. No phase may add a migration, tag, push, publication, release, or
    deployment except through a separately requested release action.
