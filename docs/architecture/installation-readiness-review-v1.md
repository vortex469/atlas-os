# Installation Readiness Review v1 planning contract

Status: **Atlas v0.34 P0–P5 implemented and release-validated**.

Atlas v0.34 defines a read-only, operator-owned review of the released
v0.20–v0.33 installation evidence chain. It answers only whether the exact
chain is blocked or has reached the evidence threshold for a later, separately
specified execution-admission review.

The authority equations for every v0.34 phase are:

`readiness_gated != execution_admitted != execution_authorized`

and:

`read-only review != install authority != execution authority`.

## Repository inspection baseline

Planning starts from `main` at
`343f683efb872b4b6322e27eaeffa64ccc4893ce`, after annotated tag
`atlas-v0.33.0` targeting
`4bc30527b1c5a99eb090a43619494bb557791a50`.

The repository contains the released owner-bound v0.20 candidate record,
v0.21 approval, v0.22 Agent validation evidence, v0.23 execution request,
v0.24 dispatch handoff, v0.25 intake simulation, v0.26 simulated delivery,
v0.27 real Agent intake evidence, v0.28 dormant preparation, v0.29 preflight,
v0.30 enablement, v0.31 one-shot live send, v0.32 admission, and v0.33 inert
receipt. No released record admits installation execution.

## Exact request and API

V0.34 adds exactly one authenticated, owner-scoped Core operation:

```text
GET /api/v1/installation/candidate-records/{candidate_record_id}/readiness-review
```

`candidate_record_id` is a canonical UUIDv4 path value. There is no request
body, query parameter, collection route, POST, PUT, PATCH, DELETE, action
suffix, refresh operation, retry, resend, admit, install, execute, dispatch,
deploy, rollback, or mutation sibling. Core may read only its existing local
owner-scoped stores. It must not contact Agent, load a credential, make a
network call, or infer missing Agent-local evidence.

The route uses the existing authenticated operator permission
`installation.destination.select`. An unauthenticated request is `401`; an
authenticated principal without that permission is `403`; a foreign or absent
candidate is indistinguishable as `404`; malformed input is `422`; corrupt or
unavailable local evidence is a redacted `503`. Authentication failures expose
no candidate, receipt, operator, or fingerprint value.

## Exact linkage schema

The review linkage is the complete frozen v0.33 linkage, unchanged, plus the
v0.33 Core receipt and verification identities:

```text
InstallationReadinessReviewLinkageV1 = {
  candidate_record_id: UUIDv4,
  candidate_envelope_fingerprint: FingerprintV1,
  candidate_record_fingerprint: FingerprintV1,
  approval_intent_id: UUIDv4,
  approval_intent_fingerprint: FingerprintV1,
  agent_request_id: UUIDv4,
  agent_request_fingerprint: FingerprintV1,
  agent_validation_fingerprint: FingerprintV1,
  agent_audit_evidence_fingerprint: FingerprintV1,
  destination_fingerprint: FingerprintV1,
  source_plan_fingerprint: FingerprintV1,
  artifact_policy_fingerprint: FingerprintV1,
  execution_request_id: UUIDv4,
  execution_request_fingerprint: FingerprintV1,
  dispatch_envelope_id: UUIDv4,
  dispatch_envelope_fingerprint: FingerprintV1,
  simulation_request_id: UUIDv4,
  intake_record_id: UUIDv4,
  intake_record_fingerprint: FingerprintV1,
  intake_simulation_evidence_fingerprint: FingerprintV1,
  simulated_delivery_id: UUIDv4,
  simulated_delivery_fingerprint: FingerprintV1,
  delivery_record_fingerprint: FingerprintV1,
  simulated_delivery_evidence_fingerprint: FingerprintV1,
  simulated_acknowledgement_id: UUIDv4,
  simulated_acknowledgement_fingerprint: FingerprintV1,
  simulated_acknowledgement_evidence_fingerprint: FingerprintV1,
  intake_request_id: UUIDv4,
  delivery_attempt_id: UUIDv4,
  dormant_preparation_fingerprint: FingerprintV1,
  delivery_preparation_id: UUIDv4,
  preparation_fingerprint: FingerprintV1,
  preflight_id: UUIDv4,
  preflight_fingerprint: FingerprintV1,
  enablement_id: UUIDv4,
  enablement_fingerprint: FingerprintV1,
  send_attempt_id: UUIDv4,
  attempt_fingerprint: FingerprintV1,
  v031_send_receipt_fingerprint: FingerprintV1,
  v032_envelope_fingerprint: FingerprintV1,
  v032_agent_result_fingerprint: FingerprintV1,
  v032_admission_id: UUIDv4,
  v032_admission_fingerprint: FingerprintV1,
  v032_acknowledgement_id: UUIDv4,
  v032_acknowledgement_fingerprint: FingerprintV1,
  v032_agent_receipt_exported: false,
  v032_agent_receipt_atomicity_relied_upon: true,
  v033_receipt_id: UUIDv4,
  v033_receipt_fingerprint: FingerprintV1,
  v033_verification_fingerprint: FingerprintV1,
  v033_linkage_fingerprint: FingerprintV1
}
```

Every field is required. Core recomputes every released fingerprint from the
complete authoritative record and requires exact same-owner, ID, fingerprint,
and transitive-link equality. The v0.19 admission remains transitively bound by
v0.20 and is recomputed but not duplicated. A partial, substituted, foreign,
cyclic, ambiguous, or unverifiable chain is blocked and never repaired by the
review.

## Exact evidence summary

The response contains exactly fourteen ordered summary items, one for each
release v0.20 through v0.33:

```text
InstallationReadinessEvidenceSummaryV1 = {
  release: "v0.20" | ... | "v0.33",
  evidence_kind:
    "candidate_record" |
    "approval_intent" |
    "agent_install_container_validation" |
    "execution_request" |
    "dispatch_handoff" |
    "agent_intake_simulation" |
    "simulated_handoff_delivery" |
    "real_agent_intake" |
    "dormant_delivery_wiring" |
    "delivery_activation_preflight" |
    "operator_delivery_enablement" |
    "live_delivery_send" |
    "agent_live_intake_admission" |
    "inert_delivery_receipt",
  evidence_id: UUIDv4 | null,
  evidence_fingerprint: FingerprintV1 | null,
  evidence_state: "current" | "missing" | "expired" | "terminal" | "unavailable",
  valid_until: UtcSecond | null,
  evidence_only: true,
  execution_authorized: false,
  installation_allowed: false
}
```

The array order is fixed by release number, has exactly fourteen unique items,
and cannot contain descriptions, raw records, arbitrary metadata, endpoints,
credentials, bodies, headers, commands, paths, or provider payloads. For a
release whose frozen primary record has no expiry, `valid_until` is null. The
summary does not replace or mutate source evidence.

## Exact readiness schema and blocker vocabulary

```text
InstallationReadinessReviewV1 = {
  schema: "installation-readiness-review-v1",
  review_id: UUIDv5,
  candidate_record_id: UUIDv4,
  operator_id: CanonicalOperatorId,
  observed_at: UtcSecond,
  readiness: "blocked" | "readiness_gated",
  blockers: [InstallationReadinessBlockerV1, ...],
  evidence: [exactly 14 InstallationReadinessEvidenceSummaryV1 items],
  linkage: InstallationReadinessReviewLinkageV1 | null,
  source: "core_local_owner_scoped_evidence_v1",
  evidence_only: true,
  read_only: true,
  execution_admission_granted: false,
  execution_authorized: false,
  installation_allowed: false,
  dispatch_allowed: false,
  worker_allowed: false,
  workflow_allowed: false,
  deployment_allowed: false,
  mutation_allowed: false,
  retry_allowed: false,
  replay_allowed: false,
  review_fingerprint: FingerprintV1
}
```

`InstallationReadinessBlockerV1` is the closed vocabulary:

```text
"missing_evidence"
"ownership_mismatch"
"linkage_mismatch"
"fingerprint_mismatch"
"invalid_evidence"
"stale_evidence"
"expired_evidence"
"terminal_ambiguity"
"agent_evidence_unavailable"
"source_unavailable"
"installation_capability_unsupported"
"execution_admission_not_defined"
```

Blockers are unique and sorted in the order above. `blocked` requires one or
more blockers. Null evidence identities are permitted only with `missing` or
`unavailable` and a corresponding blocker; null linkage is permitted only for
`blocked`. `readiness_gated` requires the exact current, valid, same-owner,
fully recomputed chain and exactly the sole blocker
`execution_admission_not_defined`. Thus v0.34 never returns an empty blocker
set, `ready`, `approved`, `admitted`, `authorized`, `executable`, or
`installable`. Home Assistant returns `blocked` with
`installation_capability_unsupported` and cannot be readiness-gated.

The review fingerprint is SHA-256 over UTF-8 domain
`atlas:installation-readiness-review:v1`, one NUL byte, and canonical NFC JSON
of the complete review excluding `review_fingerprint`. `review_id` is the
deterministic UUIDv5 of the authenticated operator ID, candidate record ID,
v0.33 receipt fingerprint, and `observed_at`; it is not persisted.

## Freshness and expiry interpretation

Review time is supplied by Core's trusted UTC whole-second clock. Core applies
each released contract's own creation, freshness, expiry, terminal ambiguity,
and no-replay rules without extending, refreshing, or restarting any window.
The v0.29–v0.33 inherited maximum 30-second chain window remains exact.

Expired evidence remains visible only as a redacted summary and produces
`expired_evidence`; evidence that violates a released point-in-time freshness
rule produces `stale_evidence`; a v0.31 or v0.33 ambiguous terminal outcome
produces `terminal_ambiguity`. A durable record's continued existence does not
make its time-bounded claim current. Review generation creates no reservation,
new evidence, cache, persistence, touch, refresh, retry, or replay opportunity.

## Redaction and audit evidence

The success response is bounded to 64 KiB and contains only the closed review
projection. It never includes raw evidence objects, credential material or
references, endpoint/host/address/URL, request/response bodies, headers,
idempotency keys, exceptions, commands, logs, repository/guest paths, provider
payloads, or Agent-local record contents not already exported by frozen
contracts.

```text
InstallationReadinessReviewAuditEvidenceV1 = {
  schema: "installation-readiness-review-audit-evidence-v1",
  review_id: UUIDv5,
  review_fingerprint: FingerprintV1,
  candidate_record_id: UUIDv4,
  v033_receipt_fingerprint: FingerprintV1 | null,
  linkage_fingerprint: FingerprintV1 | null,
  operator_fingerprint: FingerprintV1,
  correlation_id: CanonicalCorrelationId,
  observed_at: UtcSecond,
  outcome: "blocked" | "readiness_gated",
  blocker_codes: [InstallationReadinessBlockerV1, ...],
  source_was_owner_scoped_local_readers: true,
  evidence_only: true,
  read_only: true,
  mutation_attempted: false,
  execution_attempted: false,
  evidence_fingerprint: FingerprintV1
}
```

Audit evidence is deterministic response evidence, not a new durable record.
Its fingerprint domain is
`atlas:installation-readiness-review-audit-evidence:v1`. Existing bounded HTTP
access logging may record route template, status, correlation ID, and
operator fingerprint only; it must not log path IDs or response contents.

Errors use one safe message, **Installation readiness review is unavailable.**,
and codes `malformed`, `unauthenticated`, `unauthorized`, `not_found`, or
`unavailable`. They disclose no blocker, source record, fingerprint, or
existence detail beyond the authenticated owner-scoped success response.

The exact HTTP success and error bodies are:

```text
InstallationReadinessReviewResponseV1 = {
  review: InstallationReadinessReviewV1,
  audit_evidence: InstallationReadinessReviewAuditEvidenceV1
}

InstallationReadinessReviewRedactedErrorV1 = {
  schema: "installation-readiness-review-error-v1",
  error_code:
    "malformed" | "unauthenticated" | "unauthorized" | "not_found" | "unavailable",
  safe_message: "Installation readiness review is unavailable.",
  correlation_id: CanonicalCorrelationId,
  redacted: true,
  retryable: false,
  execution_authorized: false,
  installation_allowed: false,
  mutation_allowed: false
}
```

The success body is returned only after authentication, owner resolution, and
bounded evaluation. The error body has no optional identity or evidence field.

## Mission Control boundary

Mission Control may add one read-only client method, one closed response type,
one query hook, and one route:

```text
/installation/candidate-records/:candidateRecordId/readiness-review
```

The page title is **Installation readiness review**. It displays the top-level
state as **Blocked** or **Readiness gated — execution admission is not
defined**, the closed blocker labels, fourteen ordered evidence rows, review
time, expiry values, and shortened copyable IDs/fingerprints. It must explain
that readiness-gated is not approval, admission, authorization, or permission
to install.

There is no button, form, confirmation, mutation hook, polling, automatic
refresh, retry, resend, admit, send, install, execute, dispatch, worker,
workflow, deploy, rollback, credential, or raw-evidence control. Browser
refresh may repeat only the GET. The page cannot turn a transport/query retry
into an upstream Agent or delivery retry. Home Assistant may appear only as a
blocked golden with no exception or deployment artifact.

## P0–P5 plan

### P0 — Contract and threat model — selected

Freeze this exact schema, linkage, fingerprints, readiness/blocker vocabulary,
ownership/authentication, time interpretation, redaction/audit, one-GET API,
read-only UI, authority boundary, threats, goldens, and must-not-change rules.
Change planning documents only.

### P1 — Closed models and pure review evaluation — implemented

Add immutable Core review/linkage/summary/audit/error models, domain-separated
fingerprints, strict bounds, and pure evaluation over injected exact evidence.
Add no readers, stores, routes, registration, Agent access, UI, or runtime
composition.

P1 adds the strict immutable linkage, fourteen-item summary, review, audit,
redacted-error, response/result, and injected pure-evaluation models. It binds
the complete v0.20–v0.33 identities, enforces owner/authentication context,
closed readiness/blocker and freshness semantics, deterministic UUIDv5 and
domain-separated fingerprints, bounds, redaction, fixed-false authority, and
the blocked Home Assistant golden. It adds no service, reader, route, UI,
persistence, external I/O, or runtime behavior.

### P2 — Owner-scoped local read composition — implemented

Add an explicitly constructed read service that resolves the exact v0.20–v0.33
chain through existing Core-local owner-scoped readers and returns the pure
projection. Add no persistence, cache, mutation, network, credential read,
Agent invocation, retry, or background task.

P2 adds an explicitly injected Core-local evidence-reader protocol and trusted
whole-second UTC clock. The service enforces authentication, existing read
permission, owner/candidate/time binding, exact P1 validation and deterministic
projection, while collapsing absent/foreign evidence to the same redacted
`not_found` result and corrupt/unavailable sources to the single redacted
`unavailable` result. It has no store, identity factory, reservation, write,
cache, credential, Agent, transport, retry, replay, or effect dependency.

### P3 — Exact read-only Core API — implemented

Register only the authenticated GET frozen above, with exact OpenAPI,
permission, ownership non-disclosure, bounds, and redacted errors. Add no
collection or mutation/action route and no new permission.

P3 registers exactly the frozen candidate-record readiness-review GET. It uses
the existing `installation.destination.select` permission, calls only the P2
service, rejects query parameters and request bodies, requires no origin or
CSRF mutation proof, returns the closed success or redacted-error bodies, and
conceals foreign evidence as `not_found`. All non-GET methods are excluded from
OpenAPI and rejected with `Allow: GET`; there is no action or mutation sibling.

### P4 — Read-only Mission Control presentation — implemented

Add only the frozen client/type/query/page/route and navigation from an
operator-owned candidate detail context. Lock the exact state/blocker display,
sensitive-data absence, no polling, and absence of all effect controls.

P4 adds the exact strictly parsed GET client, closed response types, one-load
read-only page, frozen candidate-record route, and contextual link from an
operator-owned saved record. It renders the two states, ordered blockers,
fourteen evidence summaries, exact linkage/fingerprints, owner/source/time
context, audit evidence, redacted unavailable state, and fixed authority
fields. It adds no polling, form, action navigation, mutation client, raw
payload, credential, address, command, log, path, or effect control.

### P5 — Isolation, regression, and release closure — complete

Prove exact route/OpenAPI and UI surfaces, deterministic evaluation, complete
linkage recomputation, ownership isolation, freshness/expiry mapping,
redaction, no writes or external I/O, zero authority consumers, prior release
regressions, capability parity, and the blocked Home Assistant golden. Add
tests and release evidence only; do not tag, push, publish, deploy, or release
automatically.

P5 adds cross-layer release guards for the single Core GET, P2 no-effect
service, fixed-false authority, exclusive read-only v0.20–v0.33 consumption,
Mission Control GET-only client and control/data absence, Agent isolation, and
the blocked/non-artifact Home Assistant golden. Core, Agent, and Mission
Control lint, tests, build, and repository whitespace validation close P1–P5.
No tag, push, publication, release, or deployment is performed by P5.

## Exact authority boundary

V0.34 may authenticate an operator with the existing read permission, read
that operator's existing Core-local evidence, recompute and compare released
fingerprints, derive one ephemeral closed review and audit projection, and
render it through one GET and one read-only Mission Control page. That is the
entire authority increase.

It may not create, update, reserve, refresh, retry, replay, approve, admit,
send, dispatch, install, execute, enqueue, deploy, roll back, load credentials,
contact Agent, start a worker/workflow/process, or mutate any provider,
repository, guest, candidate, desired, or deployment state.

## What v0.34 enables later

A later separately frozen release may use a fresh owner-bound
`readiness_gated` review as one input to a new explicit execution-admission
decision. That release must independently define confirmation, authorization,
capability, cancellation, expiry, progress, failure, rollback, audit, and
effect boundaries. A v0.34 review is never itself an execution token.

## What remains blocked

Installation; execution; dispatch; retry/resend; Agent invocation; worker or
workflow start; Docker, Podman, Compose, containerd, shell, subprocess, or any
process execution; provider/repository/in-guest mutation; candidate or desired
state mutation; deployment; rollback; credential access; broad evidence
export; and Home Assistant installation/artifacts remain blocked.

## Threats and required goldens

- cross-owner and existence probing fail without disclosing evidence;
- missing, substituted, corrupt, stale, expired, cyclic, or partially linked
  evidence cannot produce `readiness_gated`;
- every v0.20–v0.33 fingerprint and transitive identity is recomputed;
- review GETs cause zero writes, reservations, credential reads, network calls,
  Agent calls, retries, dispatches, workflows, workers, or mutations;
- secret, endpoint, raw-body, command, path, exception, and Agent-local record
  data never enter response, audit evidence, logs, OpenAPI examples, or UI;
- `readiness_gated` always retains `execution_admission_not_defined` and every
  authority field fixed false;
- no review object is imported or consumed by execution or mutation code; and
- Home Assistant is blocked, non-installable, non-executable, and has no
  deployment artifact.

## Must-not-change contracts

- V0.20–v0.33 schemas, fingerprint domains, ownership, stores, routes,
  OpenAPI, freshness, expiry, idempotency/no-replay, redaction, and goldens are
  frozen; v0.34 only reads and projects them.
- V0.31 stays one-shot with permanent reservation, zero automatic retry, and
  terminal ambiguity. V0.32 stays admission-only on one guarded internal POST.
  V0.33 stays internal composition with no public receipt API.
- Existing installation, approval, execution-request, dispatch, worker,
  workflow, provider, repository, guest, deployment, rollback, and audit
  consumers must not import or react to a v0.34 review.
- Existing executable capability registries remain unchanged;
  `install-container` remains unsupported and Home Assistant remains blocked.
- Discovery remains GET-only, worker defaults remain off, and backup/restore
  remains explicit stopped-service operator maintenance.
- No v0.34 phase may add runtime effect authority, a mutation endpoint/control,
  background refresh, network/Agent access, deployment artifact, migration,
  tag, push, publication, release, or deployment.
