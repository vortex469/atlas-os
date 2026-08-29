# Operator-Controlled Delivery Enablement v1 planning contract

Status: **Atlas v0.30 P0–P5 complete; frozen**.

This document freezes the narrowest Core-local boundary by which one
authenticated operator may explicitly enable one exact, currently eligible
v0.29 delivery activation preflight for later consideration by a separately
released activation contract. V0.30 records bounded operator intent. It does
not activate delivery, contact Agent, send, install, or execute anything.

The authority equations for every v0.30 phase are:

`operator_enabled != delivery_activated != delivery_authorized`

and:

`durable enablement evidence != transport authority != execution authority`.

## Repository inspection baseline

Planning starts from `main` at
`95c3828bca9e75ddd405074640552598e06e1770`, after released annotated tag
`atlas-v0.29.0` targeting
`8eae3f4238da0eba2322b2297a97ec6aa77715bf`.

The repository provides the released owner-bound v0.20 candidate, v0.21
approval intent, v0.22 Agent validation evidence, v0.23 execution request,
v0.24 dispatch handoff, v0.25 intake simulation, v0.26 simulated delivery and
acknowledgement, v0.27 real-intake evidence boundary, v0.28 dormant delivery
preparation, and v0.29 short-lived delivery activation preflight. Production
Core and Agent remain disconnected. V0.30 preserves that state.

## Exact create request

The authenticated operator may submit only this closed request:

```text
OperatorControlledDeliveryEnablementCreateV1 = {
  schema: "operator-controlled-delivery-enablement-create-v1",
  preflight_id: canonical UUIDv4,
  preflight_fingerprint: FingerprintV1,
  confirmation: "I enable this exact delivery for later consideration only. This does not send, install, or execute anything."
}
```

The confirmation is case-sensitive UTF-8 text and must match byte-for-byte.
It is the only accepted affirmative wording. The UI action label is exactly
**Enable exact delivery for later consideration only** and must open a
confirmation step displaying the exact preflight ID, preflight fingerprint,
delivery-preparation ID, preparation fingerprint, expiry, and the fixed
confirmation sentence before POST. There is no one-click action.

The caller cannot supply operator identity, linkage, upstream records,
timestamps, lifecycle, status, expiry, authority flags, endpoint/auth details,
credentials, an Agent response, transport state, or execution state. Core
resolves all such evidence through server-owned, owner-scoped local readers.

## Exact linkage schema

The enablement record copies the complete v0.29 linkage projection and adds
the exact v0.29 preflight identity:

```text
OperatorControlledDeliveryEnablementLinkageV1 = {
  candidate_record_id: canonical UUIDv4,
  candidate_envelope_fingerprint: FingerprintV1,
  candidate_record_fingerprint: FingerprintV1,
  approval_intent_id: canonical UUIDv4,
  approval_intent_fingerprint: FingerprintV1,
  agent_request_id: canonical UUIDv4,
  agent_request_fingerprint: FingerprintV1,
  agent_validation_fingerprint: FingerprintV1,
  agent_audit_evidence_fingerprint: FingerprintV1,
  destination_fingerprint: FingerprintV1,
  source_plan_fingerprint: FingerprintV1,
  artifact_policy_fingerprint: FingerprintV1,
  execution_request_id: canonical UUIDv4,
  execution_request_fingerprint: FingerprintV1,
  dispatch_envelope_id: canonical UUIDv4,
  dispatch_envelope_fingerprint: FingerprintV1,
  simulation_request_id: canonical UUIDv4,
  intake_record_id: canonical UUIDv4,
  intake_record_fingerprint: FingerprintV1,
  intake_simulation_evidence_fingerprint: FingerprintV1,
  simulated_delivery_id: canonical UUIDv4,
  simulated_delivery_fingerprint: FingerprintV1,
  delivery_record_fingerprint: FingerprintV1,
  simulated_delivery_evidence_fingerprint: FingerprintV1,
  simulated_acknowledgement_id: canonical UUIDv4,
  simulated_acknowledgement_fingerprint: FingerprintV1,
  simulated_acknowledgement_evidence_fingerprint: FingerprintV1,
  intake_request_id: canonical UUIDv4,
  delivery_attempt_id: canonical UUIDv4,
  dormant_preparation_fingerprint: FingerprintV1,
  delivery_preparation_id: canonical UUIDv4,
  preparation_fingerprint: FingerprintV1,
  preflight_id: canonical UUIDv4,
  preflight_fingerprint: FingerprintV1
}
```

Every field must equal the exact same-owner transitive reference in the
released v0.20–v0.29 records. Core recomputes every released fingerprint from
the complete authoritative value. The v0.19 admission remains transitively
bound by v0.20 and is also recomputed, but is not duplicated here.

## Exact durable record and operation result

One accepted confirmation creates this immutable record:

```text
OperatorControlledDeliveryEnablementRecordV1 = {
  schema: "operator-controlled-delivery-enablement-record-v1",
  enablement_id: canonical UUIDv4,
  enabled_at: UtcSecond,
  expires_at: UtcSecond,
  preflight_id: canonical UUIDv4,
  preflight_fingerprint: FingerprintV1,
  delivery_preparation_id: canonical UUIDv4,
  preparation_fingerprint: FingerprintV1,
  linkage: OperatorControlledDeliveryEnablementLinkageV1,
  status_at_creation: "operator_enabled_for_later_delivery_consideration",
  confirmation: "I enable this exact delivery for later consideration only. This does not send, install, or execute anything.",
  statement: "operator_enablement_evidence_only_no_delivery_activation",
  source: "core_operator_controlled_delivery_enablement_v1",
  default_enabled: false,
  operator_enabled: true,
  agent_contacted: false,
  credentials_loaded: false,
  production_transport_registered: false,
  delivery_activated: false,
  delivery_sent: false,
  delivery_authorized: false,
  execution_admission_granted: false,
  execution_authorized: false,
  dispatch_allowed: false,
  worker_allowed: false,
  workflow_allowed: false,
  installation_allowed: false,
  deployment_allowed: false,
  mutation_allowed: false,
  replay_allowed: false,
  enablement_fingerprint: FingerprintV1
}
```

The fingerprint is SHA-256 over UTF-8 domain
`atlas:operator-controlled-delivery-enablement-record:v1`, one NUL byte, and
canonical JSON `{operator_id, record}` excluding `enablement_fingerprint`.

The service result is a closed union:

```text
OperatorControlledDeliveryEnablementOperationResultV1 =
  | {
      disposition: "created" | "exact_replay",
      record: OperatorControlledDeliveryEnablementRecordV1,
      status: OperatorControlledDeliveryEnablementStatusV1,
      audit_evidence: OperatorControlledDeliveryEnablementAuditEvidenceV1,
      error: null
    }
  | {
      disposition: "rejected" | "unavailable",
      record: null,
      status: null,
      audit_evidence: null,
      error: OperatorControlledDeliveryEnablementRedactedErrorV1
    }
```

Both variants also carry the fixed top-level values `default_enabled: false`,
`agent_contacted: false`, `credentials_loaded: false`,
`delivery_activated: false`, `delivery_sent: false`,
`delivery_authorized: false`, `execution_attempted: false`,
`mutation_attempted: false`, and `replay_allowed: false`.

Malformed, foreign, stale, ineligible, expired, mismatched, unavailable, or
already-reserved inputs create no enablement record. V0.30 does not preserve a
rejection as an affirmative operator-enable claim.

## Eligibility, lifecycle, freshness, and expiry

Creation requires, at one trusted whole-second UTC instant:

- the explicitly constructed enablement evidence service is locally enabled;
- the v0.29 record belongs to the authenticated operator and its fingerprint,
  complete linkage, fixed flags, decision, and audit evidence validate;
- the v0.29 decision is `eligible_for_later_activation` and its currently
  revalidated lifecycle is `eligible`;
- `preflight.evaluated_at <= enabled_at < preflight.expires_at`;
- every currently mutable/relevant v0.20, v0.21, v0.23, v0.24, v0.28, and
  v0.29 state remains valid under the v0.29 current-read rules; and
- no conflicting v0.27 admission or v0.30 reservation exists.

The expiry is exact:

```text
expires_at = preflight.expires_at
```

Consequently every enablement is fresh for less than or equal to the remainder
of the v0.29 30-second window. V0.30 cannot extend, renew, refresh, replace, or
rebase that window.

The read-only derived status is:

```text
OperatorControlledDeliveryEnablementStatusV1 = {
  schema: "operator-controlled-delivery-enablement-status-v1",
  enablement_id: canonical UUIDv4,
  enablement_fingerprint: FingerprintV1,
  observed_at: UtcSecond,
  lifecycle: "enabled" | "expired" | "unavailable",
  operator_enabled: true,
  delivery_activated: false,
  delivery_sent: false,
  delivery_authorized: false,
  execution_authorized: false,
  replay_allowed: false
}
```

`enabled` requires `enabled_at <= observed_at < expires_at` plus successful
current owner-scoped revalidation. `expired` is terminal when
`observed_at >= expires_at`. `unavailable` is returned for a bad clock,
corruption, ambiguity, missing/replaced evidence, linkage mismatch, or failed
current revalidation. Reads never mutate the record.

## Authentication, authorization, and ownership

Identity comes only from the existing authenticated Core operator principal.
Create requires `installation_delivery_enablement:create`; list/item read
requires `installation_delivery_enablement:read`. Neither permission implies
preflight creation, transport, credential, dispatch, execution, provider,
repository, worker, workflow, installation, or deployment authority.

Create retains existing CSRF, trusted HTTPS origin, session, body-bound,
content-type, strict JSON, duplicate-member, nesting, idempotency-header, and
per-operator mutation-rate protections. Operator ID is never caller-selected.
The preflight, entire v0.20–v0.29 chain, idempotency reservation, and result
must have the same operator owner. List and item reads are owner-scoped;
foreign IDs are indistinguishable from absence. IDs and fingerprints are not
capabilities or credentials.

## Idempotency and no replay

- `Idempotency-Key` is visible ASCII, 1–128 bytes, and scoped to operator plus
  `operator_controlled_delivery_enablement:create`.
- The append-only store atomically reserves the idempotency key, preflight ID
  and fingerprint, delivery-preparation ID and fingerprint, enablement ID, and
  enablement fingerprint.
- One v0.29 preflight and one v0.28 preparation may produce at most one v0.30
  enablement record forever.
- Exact retry returns the byte-identical original record without rereading
  evidence, changing time, extending expiry, contacting Agent, or doing work.
- Any changed input under a reserved identity returns `replay_conflict`.
- Expired records never release reservations. There is no retry-as-refresh,
  update, revoke-in-place, delete-and-recreate, replacement, consumption, or
  conversion into activation authority.
- Timeout, partial reservation, corruption, or ambiguous completion fails
  closed as unavailable and never permits a second record.

There is no v0.30 consumer. A later release must define atomic consumption,
repeat current-state validation, and its own fresh-enough safety proof; it may
not treat an expired record or identifier as delivery authority.

## Redaction and audit evidence

The only API error schema is:

```text
OperatorControlledDeliveryEnablementRedactedErrorV1 = {
  schema: "operator-controlled-delivery-enablement-error-v1",
  error_code: "malformed" | "not_found" | "unauthenticated" |
              "unauthorized" | "confirmation_mismatch" |
              "linkage_mismatch" | "fingerprint_mismatch" |
              "preflight_not_eligible" | "not_current" |
              "replay_conflict" | "quota_exceeded" | "unavailable",
  correlation_id: CorrelationId,
  preflight_id: canonical UUIDv4 | null,
  preflight_fingerprint: FingerprintV1 | null,
  redacted: true
}
```

Foreign-owner records use `not_found`. Store ambiguity/failure and corrupt or
unavailable revalidation use `unavailable`. Errors expose no operator IDs,
other-owner existence, endpoint address/host/TLS name, CA/credential path or
material, Authorization/cookie, raw Agent evidence, provider payload, command,
environment, repository/guest path, deployment content, HTTP detail, exception,
request/response body, log, or store path.

Successful operations produce:

```text
OperatorControlledDeliveryEnablementAuditEvidenceV1 = {
  schema: "operator-controlled-delivery-enablement-audit-evidence-v1",
  enablement_id: canonical UUIDv4,
  enablement_fingerprint: FingerprintV1,
  preflight_id: canonical UUIDv4,
  preflight_fingerprint: FingerprintV1,
  delivery_preparation_id: canonical UUIDv4,
  preparation_fingerprint: FingerprintV1,
  enabled_at: UtcSecond,
  expires_at: UtcSecond,
  lifecycle: "enabled" | "expired" | "unavailable",
  status: "operator_enabled_for_later_delivery_consideration",
  confirmation: "I enable this exact delivery for later consideration only. This does not send, install, or execute anything.",
  provenance: "core_operator_controlled_delivery_enablement_v1",
  delivery_activated: false,
  delivery_sent: false,
  delivery_authorized: false,
  execution_authorized: false,
  mutation_allowed: false,
  replay_allowed: false,
  evidence_fingerprint: FingerprintV1
}
```

The audit fingerprint uses domain
`atlas:operator-controlled-delivery-enablement-audit-evidence:v1` and the
canonical object excluding `evidence_fingerprint`. Logs contain only a
correlation ID, safe owned IDs/fingerprints, derived lifecycle, and one
sanitized code.

## Store, API, and Mission Control boundary

P2 may add one independent append-only, operator-scoped Core store limited to
16 records per operator and 96 KiB canonical bytes per record. It supports
atomic append and owned newest-first bounded list/item reads only. It has no
update, runtime delete, eviction, repair, outbox, callback, event, queue,
scheduler, transport status, activation column, or authority bridge. Existing
backup schemas are not widened automatically.

The only future Core API shape is:

```text
POST /api/v1/installation-delivery-enablements
GET  /api/v1/installation-delivery-enablements
GET  /api/v1/installation-delivery-enablements/{enablement_id}
```

POST accepts only the closed JSON request and existing `Idempotency-Key`
header. List is owner-scoped, newest-first, bounded, and cursor-paginated.
There is no update/delete/revoke/activate/approve/send/deliver/retry/refresh/
consume/execute/install/deploy/dispatch/rollback sibling route. Routes call
only the explicitly injected local service.

Mission Control may show a guarded **Enable exact delivery for later
consideration only** confirmation and read-only records. It must show the exact
confirmation wording, owner-scoped linkage, remaining expiry, default-off
posture, audit evidence, fixed-false flags, and the statement **Operator
enabled does not mean activated, sent, delivered, admitted, installed, or
executed.** It exposes no Activate, Send, Deliver, Run, Execute, Install,
Deploy, Dispatch, Start workflow, Retry, Refresh, Consume, Roll back,
credential, endpoint, Agent, provider, repository, or action-navigation
control. Home Assistant remains blocked, non-installable, and non-executable.

The service, store, API, and UI are default-off/default-absent until their
respective phases explicitly add reviewed construction. No phase may register
production transport or Agent routes, load secret material, or create a
deployment artifact.

## P0–P5 scope

### P0 — Enablement contract and threat model — complete

Freeze exact request/linkage/record/result/status/error/audit schemas,
confirmation wording, fingerprints, ownership/authz, freshness, expiry,
idempotency/no-replay, store/API/UI limits, authority, threats, goldens, and
must-not-change rules. Change planning documentation only.

### P1 — Closed models and pure validation — complete

Implement immutable models, canonical fingerprints, exact v0.20–v0.29 linkage
validation, confirmation validation, and pure lifecycle derivation over
injected values/time. Add no I/O, store, route, client, or registration.

### P2 — Bounded append-only enablement evidence — complete

Implement the explicitly constructed service over injected owner-scoped local
readers, trusted clock/ID factory, and independent store. Add atomic permanent
reservations, exact retry, quotas, corruption/ambiguity closure, and current
owned reads. Add no consumer or activation bridge.

### P3 — Authenticated Core-local API — complete

Add only guarded create/list/item-read with exact authentication, narrow
permissions, CSRF/origin/rate limits, strict bounds/parsing, ownership,
redaction, OpenAPI/method isolation, and default-off injected construction.
Add no Agent, transport, credential, runtime, or mutation dependency.

### P4 — Mission Control enablement evidence review — complete

Add the explicit two-step enablement confirmation and read-only lifecycle,
expiry, linkage, fingerprint, audit, no-replay, and fixed-authority display.
Add no activation, send, delivery, execution, installation, deployment,
rollback, endpoint, credential, Agent, workflow, or action navigation.

### P5 — Isolation, no-replay, and release closure — complete

Prove exact linkage/fingerprint sensitivity, confirmation, freshness/expiry,
ownership/authz, concurrency, ambiguity, quotas, corruption, redaction, exact
retry/no-replay, API/UI bounds, default-off posture, zero Agent/transport/
secret/runtime registration, zero consumers, capability parity, prior goldens,
and full regressions. Add only tests and release evidence; do not migrate, tag,
push, publish, deploy, or release automatically.

### P5 validation evidence

P5 validation started from P4 commit
`1957d1774436055ebc6f87732e51101c555a9203`. Both requested Core and Agent Ruff
gates passed. The focused Core release-isolation and delivery-enablement route
suite passed 62 tests; the full Agent suite passed 1,018 tests; and Mission
Control passed 83 test files and 540 tests, lint, and production build. The
lint run retained one pre-existing exhaustive-deps warning and the build
retained its existing chunk-size advisory; neither was an error. P5 changes
only isolation/authority tests and these four release documents. It performs
no migration, tag, push, publication, release, deployment, or rollback.

## Exact authority boundary

V0.30 may, only through an explicitly constructed local contract, revalidate
one same-owner, currently eligible v0.29 preflight and its complete v0.20–v0.29
lineage, record the authenticated operator's exact fixed confirmation, reserve
identities atomically, and create/list/read bounded durable enablement evidence.
It may truthfully state `operator_enabled_for_later_delivery_consideration`
until the inherited expiry. That evidence is its entire new authority.

V0.30 must not activate, authorize, send, deliver, or consume delivery; contact
or invoke Agent; register transport or an Agent route; load credentials,
secrets, CA material, or Authorization; resolve DNS or perform TLS/HTTP/network
I/O; dispatch; invoke a worker, workflow, scheduler, queue, callback, Docker,
Podman, Compose, containerd, shell, or process; create or execute a candidate or
job; install or run container/runtime work; mutate provider, repository, or
in-guest state; deploy; roll back; or create a Home Assistant artifact. It may
validate an already-redacted fingerprint/reference but never dereference or
read live secret material.

## What v0.30 enables later

A later, separately frozen release may require this bounded operator intent as
one prerequisite for an atomic delivery-activation decision. That later
contract must independently define current-state revalidation, fresh evidence,
single consumption, crash/ambiguity behavior, transport authentication,
delivery receipt, and cancellation/recovery. V0.30 implements none of those
capabilities, and an enablement ID or fingerprint is not an activation token.

## What remains blocked

Live Core-to-Agent connection and delivery, Agent receipt/admission, transport
and secret loading, dispatch, candidate/job consumption, worker/workflow and
runtime execution, installation, target mutation, provider/repository/in-guest
effects, deployment, rollback, Home Assistant artifacts, renewal, refresh,
revocation/update, and enablement consumption remain blocked.

## Threats and golden cases

The threat model covers forged operator identity/confirmation; foreign or
ambiguous records; stale/expired/ineligible preflight; altered linkage or fixed
flags; fingerprint substitution; clock rollback; duplicate JSON; oversized or
deep bodies; idempotency/preflight/preparation collision; concurrent creation;
partial commit; corrupt rows; stale eligible readback; exact-retry work;
cross-owner disclosure; log/error leakage; feature-flag authority escalation;
route/method expansion; UI wording/control confusion; downstream consumption;
Agent/network/secret/runtime registration; and Home Assistant exceptions.

Required goldens include: exact eligible creation; confirmation mismatch;
default-off rejection; one-second-before-expiry acceptance inheriting that
one-second expiry; at-expiry rejection; expired read; exact retry byte identity
without evidence reread; changed-key/input conflict; same preflight or
preparation under another key conflict; cross-owner indistinguishable absence;
concurrent single record; quota; corruption/ambiguous failure; every v0.20–v0.29
ID/fingerprint mutation; current upstream transition; redacted injected secret;
exact three-route OpenAPI; prohibited sibling methods; fixed-false API/UI;
zero Agent/transport/credential/worker/workflow/provider/repository consumers;
and Home Assistant blocked with no artifact.

## Must-not-change contracts

- V0.20–v0.29 schemas, fingerprints, stores, routes, ownership, lifecycle,
  freshness, idempotency/no-replay, redaction, and goldens remain exact. V0.30
  references them without migration, field addition, or trust promotion.
- V0.20 remains non-executable; v0.21 remains approval-intent evidence; v0.22
  remains validation-only/unsupported; v0.23 remains record-only; v0.24 remains
  prepared/not delivered; v0.25 remains simulation; v0.26 remains simulated;
  v0.27 remains evidence-only intake; v0.28 remains dormant/no-send; and v0.29
  remains short-lived preflight evidence, not activation authority.
- The v0.27 Agent route remains test-only/unregistered. The v0.28 client keeps
  no send method or production construction. V0.29 gains no consumer.
- Existing approvals, candidates, Provider Intent, operational dispatch,
  repository workflow, execution audit, worker, and no-replay contracts neither
  consume nor gain fields from v0.30 evidence.
- Executable capability remains `update-compose-stack` for repository work and
  `restart-service/proxmox/qemu` for operational work. `install-container`
  remains absent from executable capability and intent registries.
- Discovery remains GET-only; Provider Intent remains Proxmox QEMU
  `monitoring-policy`; the worker remains optional/default-disabled; backup and
  restore remain explicit stopped-service operator maintenance.
- No v0.30 phase may add actual transport, secret loading, Agent contact,
  activation/consumption, runtime/process work, target mutation, installation,
  deployment, rollback, migration, release action, or Home Assistant artifact.
