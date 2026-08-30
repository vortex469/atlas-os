# End-to-End Inert Delivery Receipt v1 planning contract

Status: **Atlas v0.33 P0–P5 implemented and validated**.

Atlas v0.33 defines the narrowest end-to-end Core-to-Agent inert delivery
receipt. An explicitly constructed, independently default-disabled Core
composition may send exactly one v0.32 envelope to the already registered
Agent intake POST, verify the closed returned admission and acknowledgement,
and append one Core-owned receipt. Nothing in this contract admits execution.

The authority equations are:

`verified inert delivery receipt != execution admission`

and:

`Agent admission + Core receipt != install, run, deploy, mutate, or retry`.

## Repository baseline and causal boundary

Planning starts from `main` at
`8729ee658fa0082bcad0e36c8882ea432f81661e`, after annotated tag
`atlas-v0.32.0` targeting
`74264b1f8f9e20f72e8c02c262dcfa97252e2ed5`.

The repository contains the complete same-owner v0.20–v0.30 evidence chain,
the v0.31 explicitly constructed one-shot Core transport and append-only
attempt/receipt store, and the v0.32 independently default-off production
Agent admission route and append-only Agent record. V0.31 sends the older
v0.27 body, while v0.32 accepts the new outer `AgentLiveIntakeEnvelopeV1`.
They are not yet composed in production.

The causal order is fixed:

```text
v0.20–v0.30 fresh same-owner evidence
  -> v0.31 permanent send-attempt reservation
  -> exact v0.32 inert envelope
  -> v0.32 Agent admission + acknowledgement
  -> v0.33 Core verification
  -> v0.33 append-only Core end-to-end receipt
```

The Agent-local v0.32 durable record is created before Agent returns success,
but it is not sent to Core and Core must not claim to have independently read
or verified Agent storage. Core verifies only the authenticated closed response
and its fingerprints. There is no callback or second Agent route.

For this contract, “bind v0.32 receipt evidence” therefore means binding the
exact admission and acknowledgement fingerprints exported by the v0.32 result,
plus the authenticated response and the frozen v0.32 invariant that those two
objects are committed atomically inside one Agent-local receipt before success
is returned. It does not mean copying, inventing, or remotely reading the
Agent-local `record_fingerprint` or `credential_reference_fingerprint`.

## Exact end-to-end request

V0.33 introduces one internal Core request model. It is not a public API body:

```text
EndToEndInertDeliveryRequestV1 = {
  schema: "end-to-end-inert-delivery-request-v1",
  send_attempt_id: UUIDv4,
  attempt_fingerprint: FingerprintV1,
  envelope: AgentLiveIntakeEnvelopeV1,
  endpoint_fingerprint: FingerprintV1,
  idempotency_key_fingerprint: FingerprintV1,
  requested_at: UtcSecond,
  expires_at: UtcSecond,
  content_type: "application/json",
  maximum_response_bytes: 32768,
  default_enabled: false,
  one_shot_only: true,
  automatic_retries: 0,
  evidence_only: true,
  execution_authorized: false,
  installation_allowed: false,
  worker_allowed: false,
  workflow_allowed: false,
  deployment_allowed: false,
  mutation_allowed: false,
  replay_allowed: false,
  request_fingerprint: FingerprintV1
}
```

The envelope is byte-for-byte the frozen v0.32
`AgentLiveIntakeEnvelopeV1`. The caller cannot supply upstream records,
operator identity, endpoint, credential reference or material, timestamps,
authority flags, response evidence, commands, desired state, or retry policy.
Core resolves these through explicit server-owned readers and configuration.

The request fingerprint domain is
`atlas:end-to-end-inert-delivery-request:v1` over the complete closed request
excluding `request_fingerprint`, using SHA-256, one NUL byte, and canonical NFC
JSON. The canonical envelope is at most 128 KiB; the complete internal request
is at most 160 KiB. Unknown or duplicate fields, recursive/unbounded values,
non-NFC strings, non-finite numbers, and non-whole-second UTC timestamps fail
closed.

## Exact Agent response and verification

Agent returns exactly the frozen v0.32 `AgentLiveIntakeResultV1`. V0.33 adds no
Agent field, schema, action, route, callback, lookup, or read API. A successful
result contains the frozen `AgentLiveIntakeAdmissionV1` and
`AgentLiveIntakeAcknowledgementV1`; rejection contains neither.

Core records verification in:

```text
EndToEndInertDeliveryVerificationV1 = {
  schema: "end-to-end-inert-delivery-verification-v1",
  send_attempt_id: UUIDv4,
  attempt_fingerprint: FingerprintV1,
  envelope_fingerprint: FingerprintV1,
  request_fingerprint: FingerprintV1,
  response_body_fingerprint: FingerprintV1,
  agent_result_fingerprint: FingerprintV1,
  admission_id: UUIDv4,
  admission_fingerprint: FingerprintV1,
  acknowledgement_id: UUIDv4,
  acknowledgement_fingerprint: FingerprintV1,
  intake_request_id: UUIDv4,
  operator_id: CanonicalOperatorId,
  linkage_fingerprint: FingerprintV1,
  verified_at: UtcSecond,
  valid_until: UtcSecond,
  authenticated_agent_response: true,
  agent_persistence_claimed_by_core: false,
  evidence_only: true,
  execution_admission_granted: false,
  execution_authorized: false,
  installation_allowed: false,
  worker_allowed: false,
  workflow_allowed: false,
  deployment_allowed: false,
  mutation_allowed: false,
  replay_allowed: false,
  verification_fingerprint: FingerprintV1
}
```

Core must parse the response as closed JSON within 32 KiB and recompute the
v0.32 result, admission, acknowledgement, attempt, envelope, request-body, and
linkage fingerprints. It verifies exact attempt/request/operator/linkage
identity, acknowledgement-to-admission binding, fixed statements and status,
all fixed-false authority fields, trusted response time, and the authenticated
HTTPS exchange. A rejection, missing field, unknown field, mismatch, stale
response, non-2xx response, timeout, truncation, or parse ambiguity cannot
produce verified evidence.

The verification fingerprint domain is
`atlas:end-to-end-inert-delivery-verification:v1` over the complete closed
verification excluding `verification_fingerprint`.

## Exact Core receipt and audit evidence

```text
EndToEndInertDeliveryReceiptV1 = {
  schema: "end-to-end-inert-delivery-receipt-v1",
  receipt_id: UUIDv4,
  operator_id: CanonicalOperatorId,
  send_attempt_id: UUIDv4,
  attempt_fingerprint: FingerprintV1,
  prior_send_receipt_fingerprint: FingerprintV1,
  envelope_fingerprint: FingerprintV1,
  verification: EndToEndInertDeliveryVerificationV1,
  received_at: UtcSecond,
  valid_until: UtcSecond,
  lifecycle_at_creation: "verified_inert_receipt",
  default_enabled: false,
  one_shot_only: true,
  automatic_retries: 0,
  evidence_only: true,
  execution_admission_granted: false,
  execution_authorized: false,
  installation_allowed: false,
  worker_allowed: false,
  workflow_allowed: false,
  deployment_allowed: false,
  mutation_allowed: false,
  replay_allowed: false,
  receipt_fingerprint: FingerprintV1
}
```

`prior_send_receipt_fingerprint` binds the terminal v0.31 Core receipt created
for the same attempt; it does not replace or mutate that record. Receipt domain
is `atlas:end-to-end-inert-delivery-receipt:v1` over the complete receipt
excluding `receipt_fingerprint`. Records are immutable, append-only,
owner-scoped, at most 192 KiB, restart-safe, quota-bounded, and corruption
fails closed.

`EndToEndInertDeliveryAuditEvidenceV1` binds receipt, verification, v0.31
attempt/receipt, v0.32 envelope/result/admission/acknowledgement, complete
linkage, endpoint and idempotency-key fingerprints, operator by fingerprint,
correlation ID, trusted times, lifecycle, and fixed-false authority. Its domain
is `atlas:end-to-end-inert-delivery-audit-evidence:v1`. It contains no raw
body, endpoint, address, credential reference, credential material, header,
exception, command, log, provider payload, or internal path.

## Exact linkage and ownership

`EndToEndInertDeliveryLinkageV1` contains every field of the frozen v0.31
`LiveDeliverySendLinkageV1`, unchanged and without optional alternatives, plus:

```text
send_attempt_id
attempt_fingerprint
v031_send_receipt_fingerprint
v032_envelope_fingerprint
v032_agent_result_fingerprint
v032_admission_id
v032_admission_fingerprint
v032_acknowledgement_id
v032_acknowledgement_fingerprint
v032_agent_receipt_exported = false
v032_agent_receipt_atomicity_relied_upon = true
```

This binds exactly v0.20 candidate, v0.21 approval, v0.22 Agent validation,
v0.23 execution request, v0.24 handoff, v0.25 simulation, v0.26 simulated
delivery/acknowledgement, v0.27 intake, v0.28 preparation, v0.29 preflight,
v0.30 enablement, v0.31 attempt/receipt/result, and the returned v0.32
admission/acknowledgement evidence. Every fingerprint is recomputed from an
authoritative server-owned or authenticated wire value. The v0.19 admission
remains transitively bound through v0.20 and is not duplicated.

The authenticated operator owns the complete chain. Operator identity must
match every Core record and the authenticated Agent result. Foreign and absent
reads are indistinguishable; no cross-owner list, index, error, audit, or metric
reveals an identity.

## Transport, authentication, and credential references

V0.33 reuses the exact v0.31 HTTPS endpoint and credential-reference rules and
the exact v0.32 Agent path, principal, permission, and mode-0400 verification:

```text
POST /api/v1/internal/installation-intake
principal = "atlas-core/install-intake-v1"
permission = "installation_intake:create"
content-type = "application/json"
connect timeout = 1000 ms
response timeout = 5000 ms
redirects = 0
automatic retries = 0
```

Both Core composition and Agent registration are independently default-off.
The transport and credential resolver are explicit injected dependencies. No
DNS, TLS, socket, HTTP, or credential read occurs before all evidence,
freshness, ownership, endpoint, bounds, idempotency, and no-replay checks pass.
Credential material is transient only, is zeroed/discarded after use, and is
never modeled, fingerprinted, persisted, logged, returned, traced, measured,
or exposed in OpenAPI/UI. No environment fallback, registry, generic transport
framework, proxy, forwarding, redirect, alternate path, or alternate principal
is allowed.

## Freshness, lifecycle, idempotency, and ambiguity

The inherited maximum window remains exactly 30 seconds:

```text
preflight.evaluated_at <= enablement.enabled_at <= attempt.created_at
  <= intake_request.sent_at <= agent.received_at <= core.verified_at
  < attempt.expires_at == intake_request.expires_at
  == admission.valid_until == acknowledgement.valid_until
  <= preflight.evaluated_at + 30 seconds
```

No timestamp may be refreshed, renewed, extended, rebased, substituted, or
rounded. Arrival or verification at expiry fails closed. Expiry never releases
a reservation or permits replay.

Lifecycle is exactly `disabled | reserved | sending | agent_admitted |
verified_inert_receipt | rejected | ambiguous | expired | unavailable`.
`sending` and `agent_admitted` are in-process only. Durable success starts at
`verified_inert_receipt`; an unverified response never becomes success.
Timeout, connection loss, truncated/invalid response, 5xx, or uncertainty after
send is terminal `ambiguous`.

Core permanently reserves before any credential or network access the operator,
raw idempotency-key digest, all one-use IDs, attempt/envelope/request/linkage
fingerprints, and endpoint fingerprint. Agent retains its independent v0.32
reservation. Exact duplicate submission returns the byte-identical stored
terminal result with zero network I/O. Any changed value conflicts. There is no
automatic/manual retry, resend, send-again, reconciliation send, daemon,
scheduler, queue, callback, reservation release, or replay bypass.

## Redacted errors

`EndToEndInertDeliveryRedactedErrorV1` contains only schema, one closed code,
safe message, correlation ID, safe receipt/attempt fingerprints after
authentication, `redacted: true`, `retryable: false`, and fixed-false authority.
Codes are exactly `malformed | unauthenticated | unauthorized | not_found |
not_current | expired | ownership_mismatch | linkage_mismatch |
fingerprint_mismatch | already_reserved | transport_unavailable |
agent_rejected | response_invalid | ambiguous | quota_exceeded | unavailable`.
No raw exception, secret, credential reference/path, URL, host, address, header,
body, response, provider payload, command, log, repository path, or guest path
may escape.

## API, OpenAPI, and Mission Control boundaries

V0.33 adds no public or operator-facing Core API route. The composition is an
explicit internal dependency boundary only. V0.32 continues to expose exactly
one independently default-off internal Agent POST; v0.33 adds no Agent route or
sibling method. Core and Agent OpenAPI must contain no v0.33 public path and no
retry, resend, receipt-finalize, callback, consume, execute, install, deploy,
dispatch, workflow, worker, rollback, credential, or mutation route.

Mission Control adds no v0.33 client, hook, type, page, component, route,
navigation, polling, mutation, send, retry, resend, receipt-finalize, execute,
install, deploy, workflow, worker, rollback, credential display, raw envelope,
or sensitive evidence rendering. A later release may define a read-only,
operator-owned sanitized receipt projection; v0.33 does not.

Home Assistant remains a blocked golden: non-installable, non-executable, and
without a deployment artifact or UI exception.

## P0–P5 plan

### P0 — Contract and threat model — selected

Freeze the exact request, verification, receipt, linkage, fingerprint,
transport/authentication, ownership, freshness, lifecycle, no-replay,
redaction/audit, API/UI, authority, threat, golden, and must-not-change
contracts. Change planning documents only.

### P1 — Closed models and pure verification — implemented

Add strict immutable Core models for request, verification, receipt, linkage,
status, audit, error, and idempotency. Mirror only the frozen v0.32 wire models
needed for closed parsing. Add deterministic domain-separated fingerprints and
pure verification. Add no service, store, route, registration, credential read,
network, Agent behavior, or UI.

### P2 — Durable Core verification service/store — implemented

Add an explicitly constructed, default-off Core service and append-only store.
It may prepare the v0.32 envelope, validate an injected closed Agent result,
and create/list/get owner-scoped receipt evidence only. Enforce exact linkage,
freshness, permanent reservations, exact duplicate behavior, quotas, bounds,
restart readback, corruption failure, redaction, and fixed-false authority. Add
no network or production consumer.

### P3 — One-shot end-to-end composition — implemented

Through only injected v0.31 transport and credential dependencies, connect one
permanently reserved Core attempt to the exact v0.32 POST, transmit one inert
envelope, verify one closed result, and atomically append the Core receipt and
audit evidence. Preserve both independent default-off gates, bounded timeout,
one-shot/no-retry ambiguity, and secret-free persistence. Add no public Core
route, new Agent route, callback, scheduler, or effect consumer.

### P4 — Presentation absence lock — implemented

Because no guarded Core receipt API/read model is frozen, add no Mission
Control surface. Add structural absence tests for clients, hooks, types, pages,
routes, navigation, polling, mutation, send/retry/resend/finalize controls,
sensitive rendering, prohibited authority labels, and Home Assistant exception.
Update milestone status only.

### P5 — Release validation and closure — complete

Lock default-off explicit construction, exact one-shot transport and Agent
route, independent reservations, concurrent no-replay, terminal ambiguity,
restart/corruption behavior, secret-free evidence/errors/logs, zero effect
consumers, absent UI/API expansion, capability parity, prior goldens, and Home
Assistant blocking. Run full Core, Agent, and Mission Control regressions. Add
tests and release evidence only; do not migrate, tag, push, publish, deploy, or
release automatically.

Closure locks explicit internal-only construction, exact duplicate zero-I/O
behavior, durable append-only and secret-free evidence, fixed-false effect
authority, zero production consumers, v0.31 one-shot/no-retry preservation,
v0.32 admission-only preservation, absent public Core and Mission Control
surfaces, and Home Assistant blocking without a deployment artifact. Both Ruff
gates, all 3107 Core tests, all 1045 Agent tests, all 555 Mission Control tests,
Mission Control lint/build, and `git diff --check` passed. P5 adds no runtime
behavior or authority.

## Exact authority boundary

V0.33 may explicitly compose one fresh owner-bound v0.31 reserved attempt into
one exact v0.32 envelope; resolve one credential reference transiently; make
one bounded authenticated HTTPS POST to the exact existing Agent intake path;
validate one closed response; and append one Core-owned verification, receipt,
and audit record. This is the entire authority increase.

It may not install, execute, deploy, roll back, dispatch, start or enqueue a
worker/workflow/job, invoke Docker/Podman/Compose/containerd/shell/subprocess or
any process, mutate provider/repository/in-guest/candidate/desired/deployment
state, call any Agent action beyond evidence admission, retry or resend, create
a broad transport/authentication framework, or create a Home Assistant artifact.

## What v0.33 enables later

A later separately frozen release may treat a fresh, owner-bound, verified
v0.33 receipt as one prerequisite for an explicit execution-admission decision.
That later contract must define new confirmation, authorization, cancellation,
progress, failure, rollback, expiry, and audit semantics. A v0.33 receipt is not
an execution token and cannot be consumed until such a release explicitly
names it.

## What remains blocked

Installation; container/runtime/process execution; worker or workflow start;
dispatch; queues; automatic/manual retry or resend; provider, repository, or
in-guest mutation; deployment; rollback; candidate execution; public Core API;
Mission Control presentation/actions; credential management; broad transport;
and Home Assistant installation/artifacts all remain blocked.

## Threats and required goldens

- stale, cross-owner, substituted, cyclic, or partially linked evidence fails
  before credential or network access;
- concurrent duplicate requests cause at most one network opportunity and one
  append-only receipt; changed duplicates conflict permanently;
- timeout or uncertainty is terminal ambiguous and cannot be retried;
- malformed, oversized, duplicate-key, mismatched, or authority-bearing Agent
  responses cannot become verified receipts;
- secrets, references, endpoints, raw bodies, exceptions, commands, logs, and
  internal paths never enter records, errors, audit, OpenAPI, or UI;
- no receipt/result/admission/acknowledgement is imported or consumed by
  installation, dispatch, worker, workflow, provider, repository, guest,
  deployment, rollback, or candidate-execution code;
- existing v0.31 one-shot and v0.32 single-route/default-off behavior remains
  exact; and
- Home Assistant remains blocked, non-installable, non-executable, with no
  deployment artifact.

## Must-not-change contracts

- V0.20–v0.32 schemas, fingerprint domains, ownership, freshness, stores,
  routes, OpenAPI, idempotency/no-replay, redaction, and goldens remain frozen.
- V0.31 remains one-shot with permanent reservation, zero automatic retry, and
  terminal ambiguity. V0.32 remains admission-only on exactly one guarded POST.
- The v0.32 envelope and result are reused byte-for-byte; v0.33 adds no field,
  callback, read route, Agent action, or claim of direct Agent-store access.
- Existing installation, candidate, approval, execution-request, dispatch,
  worker, workflow, provider, repository, guest, deployment, rollback, and
  execution-audit consumers must not import or react to v0.33 evidence.
- `install-container` remains absent from executable intent/capability
  registries. Existing executable capabilities and all earlier release
  authority boundaries remain unchanged.
- Discovery remains GET-only; worker defaults remain off; backup/restore stays
  explicit stopped-service operator maintenance.
- No v0.33 phase may add installation, execution, mutation, deployment,
  rollback, retry scheduling, broad transport/authentication, public UI/API, or
  a Home Assistant deployment artifact.
