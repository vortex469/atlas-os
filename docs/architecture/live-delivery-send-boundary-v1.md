# Live Delivery Send Boundary v1 planning contract

Status: **Atlas v0.31 P0–P5 implemented and validated; Mission Control remains
absent because no guarded Core API/read model exists**.

This document freezes the narrowest first production Core-to-Agent send. One
authenticated operator may cause Core to transmit one closed, inert v0.27
`AgentInstallationIntakeRequestV1` evidence envelope to the production-
registered v0.27 intake boundary. Agent may authenticate, validate, durably
admit the evidence, and return the already-defined closed admission and
acknowledgement. Neither side may install, execute, deploy, dispatch work, or
mutate a target.

The authority equations for every v0.31 phase are:

`live evidence delivery != execution admission != installation authority`

and:

`operator enablement + one send != workflow, runtime, or mutation authority`.

## Repository inspection baseline

Planning starts from `main` at
`2d379a21d4d637af360bf2de608f14dfba0daca5`, after annotated tag
`atlas-v0.30.0` targeting
`9fe2f9e9b8d3e7332abaa013fb5893beb916f290`.

The repository provides the exact owner-bound v0.20 candidate, v0.21 approval
intent, v0.22 Agent validation, v0.23 record-only execution request, v0.24
prepared dispatch handoff, v0.25 intake simulation, v0.26 simulated delivery
and acknowledgement, v0.27 authenticated evidence-only intake contract and
dormant route factory, v0.28 no-send preparation and response validation,
v0.29 30-second activation preflight, and v0.30 short-lived operator
enablement evidence. Production Core and Agent remain disconnected at this
baseline. No released record is execution authority.

## Exact operator request and wire request

The authenticated Core operator may submit only:

```text
LiveDeliverySendCreateV1 = {
  schema: "live-delivery-send-create-v1",
  enablement_id: canonical UUIDv4,
  enablement_fingerprint: FingerprintV1,
  delivery_preparation_id: canonical UUIDv4,
  preparation_fingerprint: FingerprintV1
}
```

The caller cannot supply operator identity, upstream records, the wire body,
endpoint, address, headers, credential material, timestamps, retry count,
response, status, lifecycle, authority flags, command, desired state, runtime,
or deployment data. Core resolves the exact same-owner records through
server-owned readers.

The transmitted body is byte-for-byte canonical JSON for the existing closed
v0.27 `AgentInstallationIntakeRequestV1` already preserved inside the exact
v0.28 preparation. V0.31 adds no field to that request. Its schema remains:

```text
AgentInstallationIntakeRequestV1 = {
  schema: "agent-installation-intake-request-v1",
  intake_request_id: canonical UUIDv4,
  delivery_attempt_id: canonical UUIDv4,
  sent_at: UtcSecond,
  expires_at: UtcSecond,
  operation: "install-container",
  mode: "intake-evidence-only",
  sender: "atlas-core",
  recipient: {
    service: "atlas-agent",
    intake_contract: "agent-installation-intake-v1"
  },
  operator_assertion: {
    operator_id: CanonicalOperatorId,
    asserted_by: "atlas-core"
  },
  envelope: InstallationDispatchEnvelopeV1,
  prior_evidence: AgentInstallationIntakePriorEvidenceV1,
  delivery_authorized: true,
  evidence_admission_requested: true,
  execution_authorized: false,
  worker_allowed: false,
  mutation_allowed: false,
  replay_allowed: false,
  request_fingerprint: FingerprintV1
}
```

`operation: "install-container"` is inherited descriptive linkage and grants
no install authority; the fixed `mode`, request flags, and Agent validation
keep it evidence-only. Core must recompute its v0.27 request fingerprint and
the v0.28 preparation fingerprint before any network I/O. Canonical request
bytes are bounded by the existing v0.27 64 KiB maximum.

## Exact required linkage and fingerprints

`LiveDeliverySendLinkageV1` is the exact v0.30 linkage without omission plus
the v0.30 enablement identity:

```text
LiveDeliverySendLinkageV1 = {
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
  preflight_fingerprint: FingerprintV1,
  enablement_id: canonical UUIDv4,
  enablement_fingerprint: FingerprintV1
}
```

Every value must equal the complete same-owner v0.20–v0.30 transitive chain.
Core recomputes every released fingerprint from the complete authoritative
record. Agent independently validates the unchanged v0.27 request and its
transitive v0.20–v0.26 evidence. The v0.19 admission remains transitively
bound through v0.20 and is recomputed without duplication.

Fingerprints added by v0.31 use SHA-256 over a UTF-8 domain, one NUL byte, and
RFC 8785-style canonical JSON with no insignificant whitespace:

- attempt: `atlas:live-delivery-send-attempt:v1` over
  `{operator_id, attempt}` excluding `attempt_fingerprint`;
- receipt: `atlas:live-delivery-send-receipt:v1` over the closed receipt
  excluding `receipt_fingerprint`; and
- audit: `atlas:live-delivery-send-audit-evidence:v1` over the closed evidence
  excluding `evidence_fingerprint`.

## Exact Agent result, admission, and acknowledgement

The only successful HTTP response body is the existing closed v0.27
`AgentInstallationIntakeResultV1`. V0.31 must not widen it:

```text
AgentInstallationIntakeResultV1 = {
  schema: "agent-installation-intake-result-v1",
  intake_request_id: canonical UUIDv4 | null,
  outcome: "admitted_for_evidence_only" | "rejected",
  admission: AgentInstallationIntakeAdmissionV1 | null,
  reason_code: IntakeRejectionCodeV1 | null
}

AgentInstallationIntakeAdmissionV1 = {
  schema: "agent-installation-intake-admission-v1",
  admission_id: canonical UUIDv4,
  intake_request_id: canonical UUIDv4,
  delivery_attempt_id: canonical UUIDv4,
  received_at: UtcSecond,
  valid_until: UtcSecond,
  operation: "install-container",
  mode: "intake-evidence-only",
  authenticated_sender: "atlas-core/install-intake-v1",
  source: {
    request_fingerprint: FingerprintV1,
    dispatch_envelope_id: canonical UUIDv4,
    dispatch_envelope_fingerprint: FingerprintV1
  },
  linkage: InstallationDispatchLinkageV1,
  prior_evidence: AgentInstallationIntakePriorEvidenceV1,
  status: "admitted_for_evidence_only",
  reason_codes: [],
  statement: "agent_accepted_authenticated_handoff_for_intake_evidence_only",
  delivery_received: true,
  evidence_admission_granted: true,
  execution_admission_granted: false,
  execution_authorized: false,
  worker_allowed: false,
  mutation_allowed: false,
  replay_allowed: false,
  admission_fingerprint: FingerprintV1
}

AgentInstallationIntakeAcknowledgementV1 = {
  schema: "agent-installation-intake-acknowledgement-v1",
  admission_id: canonical UUIDv4,
  admission_fingerprint: FingerprintV1,
  intake_request_id: canonical UUIDv4,
  received_at: UtcSecond,
  valid_until: UtcSecond,
  status: "admitted_for_evidence_only",
  provenance: "authenticated_core_intake_evidence_only",
  execution_admission_granted: false,
  execution_authorized: false,
  worker_allowed: false,
  mutation_allowed: false,
  replay_allowed: false,
  acknowledgement_fingerprint: FingerprintV1
}
```

For an admitted result, `admission` is present and `reason_code` is null. For a
rejection, `admission` is null and exactly one existing sanitized v0.27 reason
is present; authentication failures also redact the request ID. Agent durably
creates the acknowledgement atomically with admission, but the wire response
remains the existing result and does not add the acknowledgement. Core derives
and validates its fingerprint from the admitted response using the existing
v0.28 validator. The existing v0.27 constants, fingerprints, 32 KiB admission
bound, fixed evidence-only fields, and false execution/mutation/replay flags
are normative. Admission and acknowledgement are not execution admission.

## Exact attempt, receipt, and lifecycle

Before network I/O, Core atomically appends a permanent reservation and this
immutable attempt:

```text
LiveDeliverySendAttemptV1 = {
  schema: "live-delivery-send-attempt-v1",
  send_attempt_id: canonical UUIDv4,
  created_at: UtcSecond,
  expires_at: UtcSecond,
  operator_id: CanonicalOperatorId,
  linkage: LiveDeliverySendLinkageV1,
  endpoint_fingerprint: FingerprintV1,
  request_fingerprint: FingerprintV1,
  request_body_fingerprint: FingerprintV1,
  lifecycle_at_creation: "reserved",
  default_enabled: false,
  network_attempted: false,
  evidence_only: true,
  execution_requested: false,
  installation_requested: false,
  mutation_requested: false,
  replay_allowed: false,
  attempt_fingerprint: FingerprintV1
}
```

The append-only terminal receipt is:

```text
LiveDeliverySendReceiptV1 = {
  schema: "live-delivery-send-receipt-v1",
  send_attempt_id: canonical UUIDv4,
  attempt_fingerprint: FingerprintV1,
  completed_at: UtcSecond,
  lifecycle: "admitted_evidence_only" | "rejected" | "ambiguous",
  http_status_class: "2xx" | "4xx" | "5xx" | "none",
  response_fingerprint: FingerprintV1 | null,
  admission_fingerprint: FingerprintV1 | null,
  acknowledgement_fingerprint: FingerprintV1 | null,
  agent_audit_evidence_fingerprint: FingerprintV1 | null,
  redacted_error: LiveDeliverySendRedactedErrorV1 | null,
  agent_contacted: true,
  evidence_admitted: boolean,
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

Externally derived lifecycle is exactly `reserved | sending | admitted_evidence_only
| rejected | ambiguous | expired | unavailable`. `sending` is an in-process
observation only and is never reconstructed as permission to retry. A reserved
attempt with no terminal receipt after process loss or timeout becomes
`ambiguous`; it is never resent. `expired` applies only when no attempt was
reserved before expiry. Corruption or failed current validation is
`unavailable`. Records are append-only and reads have no side effect.

## Freshness, ownership, idempotency, and no replay

At the one trusted whole-second UTC reservation instant, Core requires the
same authenticated owner across the complete chain; exact v0.29 decision
`eligible_for_later_activation`; exact v0.30 lifecycle `enabled`; and:

```text
preflight.evaluated_at <= enabled_at <= reserved_at <
enablement.expires_at == preflight.expires_at <=
preflight.evaluated_at + 30 seconds
```

No phase may extend, renew, refresh, rebase, or replace this window. Agent must
receive and authenticate the request before `expires_at`; a response arriving
after expiry may close an already-started attempt but cannot authorize another
attempt or any later effect.

Create requires one visible-ASCII `Idempotency-Key` of 1–128 bytes. Core
atomically and permanently reserves `(operator_id, idempotency_key)`, the
v0.30 enablement, v0.29 preflight, v0.28 preparation, and v0.27 request before
I/O. An exact retry returns the stored attempt/receipt without network I/O.
Any changed input conflicts. Timeout, connection loss, invalid response,
process loss, 5xx, or indeterminate Agent commit is terminal `ambiguous` and
must never be automatically or manually resent. Agent retains its permanent
v0.27 request/envelope no-replay rules; its `exact_replay` response is accepted
only as reconciliation evidence for the same request fingerprint, never as
permission for Core to initiate another send.

List and item reads are owner-scoped. Foreign and absent item reads are
indistinguishable 404s. Operator identity is never caller-controlled or
written to logs, errors, URLs, or cross-owner indexes.

## Transport, authentication, and credential-reference boundary

V0.31 permits exactly one production HTTPS `POST` adapter from Core to the
fixed path `/api/v1/internal/installation-intake` and production registration
of exactly that Agent `POST` route. No generic transport registry, arbitrary
URL, alternate method/path, redirect, proxy, forwarded ingress, streaming,
websocket, callback, polling, retry, discovery, or background scheduler exists.

Configuration is server-owned, closed, startup-validated, and default-disabled:

```text
LiveDeliveryTransportConfigurationV1 = {
  schema: "live-delivery-transport-configuration-v1",
  enabled: boolean = false,
  endpoint: {
    scheme: "https",
    host: CanonicalInternalDnsName,
    port: integer[1, 65535],
    path: "/api/v1/internal/installation-intake",
    tls_server_name: CanonicalInternalDnsName,
    ca_bundle_file: CanonicalAbsoluteFilePath,
    connect_timeout_ms: 1000,
    response_timeout_ms: 5000,
    follow_redirects: false,
    proxy_allowed: false,
    forwarded_ingress_allowed: false
  },
  authentication: {
    scheme: "Bearer",
    principal: "atlas-core/install-intake-v1",
    authorization: "installation_intake:create",
    credential_source: "mode-0400-file",
    credential_file: CanonicalAbsoluteFilePath,
    required_file_mode: "0400",
    maximum_credential_bytes: 4096
  },
  maximum_request_bytes: 65536,
  maximum_response_bytes: 32768,
  maximum_redirects: 0,
  automatic_retries: 0
}
```

Core may read only the named CA bundle and bearer credential at explicit send
time after reservation. It must use no environment-secret fallback. It rejects
symlinks, non-regular files, wrong owner/mode, empty/oversized values, NUL or
line breaks, and file changes during the read. Secret bytes may exist only in
the request Authorization header and must never enter models, stores,
fingerprints, errors, logs, traces, metrics, UI, or API responses. Agent maps
the credential to the fixed principal and permission using an injected,
constant-time authenticator; it never returns credential details.

Both Core send construction and Agent route registration require explicit
independent `enabled=true` settings. Defaults and missing/invalid settings are
off and fail startup closed. This is not a reusable credential loader or broad
transport framework.

## API and Mission Control boundary

Core exposes only:

```text
POST /api/v1/installation-delivery-sends
GET  /api/v1/installation-delivery-sends
GET  /api/v1/installation-delivery-sends/{send_attempt_id}
```

Create requires authenticated operator identity, dedicated
`installation_delivery_send:create`, CSRF, trusted origin, strict content
type/length/JSON/duplicate/nesting checks, idempotency, and per-operator rate
limits. Reads require `installation_delivery_send:read`. There is no retry,
resend, cancel, consume, activate, execute, install, deploy, rollback, dispatch,
workflow, credential, endpoint, or generic transport sibling route.

Mission Control may show owner-scoped attempt lifecycle, exact linkage and
fingerprints, remaining freshness before send, sanitized receipt/audit
evidence, no-replay posture, and fixed-false authority. If P4 exposes create,
its label is exactly **Send inert evidence envelope once** and a separate
confirmation must state: **This sends evidence to Atlas Agent. It does not
install, execute, deploy, start a workflow, or mutate any system. A lost or
ambiguous response cannot be retried.** No secret, endpoint, address, raw
request/response, header, command, provider payload, log, or internal path is
rendered.

There is no Install, Run, Execute, Deploy, Dispatch, Start workflow, Retry,
Resend, Roll back, provider, repository, guest, or Home Assistant action or
navigation. Home Assistant remains blocked, non-installable, non-executable,
and has no deployment artifact.

## Redaction and audit evidence

Errors are a closed `LiveDeliverySendRedactedErrorV1` with only schema, stable
code, safe message, correlation ID, send-attempt ID/fingerprint when safe,
retryable `false`, and all authority flags false. Codes are limited to
`malformed | unauthenticated | unauthorized | not_found | not_current |
expired | linkage_mismatch | fingerprint_mismatch | already_reserved |
rate_limited | transport_unavailable | agent_rejected | response_invalid |
ambiguous | unavailable`. No raw exception, URL, host, address, credential,
header, body, response, file/path, provider payload, command, or log text is
allowed.

Append-only audit evidence binds operator ID by fingerprint (not display),
correlation ID, idempotency-key fingerprint, attempt/linkage/request/endpoint/
receipt fingerprints, trusted timestamps, lifecycle, Agent disposition, and
fixed evidence-only/non-execution/non-mutation/no-replay flags. Audit evidence
contains no secret or raw transport payload.

## P0–P5 scope

### P0 — Live-send contract and threat model — frozen

Freeze the exact schemas, linkage, fingerprints, transport/authentication/
credential-reference boundary, lifecycle, ownership, freshness, idempotency,
no-replay, redaction/audit, API/UI limits, authority, threats, goldens, and
must-not-change contracts. Change planning documents only.

### P1 — Closed live-send models and pure validation — implemented

Add immutable Core request/attempt/receipt/status/audit/error/configuration
models, canonical fingerprints, and pure exact v0.20–v0.30 validation over
injected records/time. Reuse v0.27 request/result and v0.28 response validation
without I/O, registration, settings, route, or send behavior.

### P2 — Durable Core reservation service and store — implemented

Add the explicitly constructed default-off Core reservation service and
append-only attempt store with exact linkage/freshness, owner scope, permanent
idempotency/no-replay, bounded restart-safe reads, and fail-closed corruption.
Add no route, Agent invocation, network, credential read, or runtime authority.

### P3 — One-shot Core send service — implemented

Add an explicitly constructed, default-off synchronous HTTPS adapter and
append-only attempt/receipt store. Reserve permanently before I/O; load only
the fixed credential/CA references; perform at most one POST; validate the
closed response; and fail ambiguous without retry. Add no generic transport,
background task, worker, workflow, dispatch, runtime, or mutation integration.

### P4 — Guarded operator API and evidence presentation — absence locked

The guarded create/list/item-read Core routes planned by this contract are not
implemented after P3. P4 therefore adds no Mission Control client, read model,
page, component, route, navigation, mutation, confirmation, or evidence view.
Structural tests lock that absence, including no retry/resend, install,
execute, workflow, deploy, mutation, credential, endpoint, raw-envelope, or
Home Assistant exception surface. Presentation remains blocked until the
separately guarded Core API exists.

### P5 — Isolation, no-replay, and release closure — complete

Release-isolation tests lock exact linkage/fingerprint/freshness, independent
defaults, injected transport/authentication, request/response bounds,
permanent reservation before I/O, timeout/crash/ambiguity no-replay,
secret-free persistence, ownership, redaction, and fixed-false effect
authority. They prove no live-send evidence consumer across Core, Agent, or
the execution worker; no production Core route or Agent intake registration;
no Mission Control v0.31 surface; capability parity; and Home Assistant
blocking with no artifact. P5 adds tests and release evidence only and performs
no migration, tag, push, publication, deployment, or release action.

## Exact authority boundary

V0.31 may authenticate one operator, revalidate one current same-owner
v0.20–v0.30 chain, permanently reserve it, load only the configured transport
credential and CA under the closed file rules, perform at most one synchronous
authenticated HTTPS POST of the inert v0.27 evidence envelope, let Agent admit
that evidence, validate the closed Agent result, and preserve redacted durable
attempt/receipt/audit evidence. This is the entire new authority.

V0.31 must not install or execute; start or enqueue dispatch, worker, workflow,
scheduler, job, callback, or retry; invoke Docker, Podman, Compose, containerd,
shell, subprocess, or process execution; mutate provider, repository, guest,
candidate, desired, or deployment state; deploy; roll back; create a Home
Assistant artifact; expose arbitrary transport; or treat evidence admission,
acknowledgement, enablement, or receipt as execution authority.

## What v0.31 enables later

A later separately frozen release may require a successfully admitted v0.31
receipt as one prerequisite for an explicit Agent-side execution admission or
installation decision. That release must independently define consumable
authority, cancellation/recovery, current-state revalidation, execution target,
runtime isolation, progress, failure, and rollback. V0.31 implements none of
those capabilities; its IDs and fingerprints are not execution tokens.

## What remains blocked

Installation, container/runtime execution, Docker/Podman/shell/process calls,
candidate/job execution, operational dispatch, workers, workflows, queues,
schedulers, retries/resends, provider/repository/in-guest mutation, deployment,
rollback, Home Assistant artifacts, arbitrary endpoints/transports, credential
management, and any consumption of the receipt as authority remain blocked.

## Threats and required goldens

Threats include forged operator/service identity; foreign, stale, altered, or
expired evidence; endpoint or DNS substitution; CA/credential symlinks or file
races; secret leakage; redirects/proxies; duplicate JSON; oversized/deep
bodies; idempotency collisions; reserve-after-send; concurrent sends; timeout,
crash, partial Agent commit, malformed/truncated/oversized response, replay,
clock rollback, corrupt rows, cross-owner disclosure, route/method expansion,
UI retry confusion, downstream authority consumption, and Home Assistant
exceptions.

Required goldens include exact one-send admission; every v0.20–v0.30 ID and
fingerprint mutation; one second before expiry; at-expiry rejection; both-side
default-off; authentication and TLS failure; credential mode/owner/size/race;
no secret persistence/logging; reservation before transport; concurrent single
send; exact retry with zero I/O; timeout/crash/invalid response terminal
ambiguity; Agent exact-replay reconciliation without Core resend; response
bounds/redaction; foreign indistinguishable absence; exact three Core routes
and one Agent POST; no sibling/retry controls; capability parity; zero runtime/
mutation consumers; and Home Assistant blocked with no artifact.

## Must-not-change contracts

- V0.20–v0.30 schemas, fingerprints, stores, routes, ownership, lifecycle,
  freshness, idempotency/no-replay, redaction, and goldens remain exact and
  gain no fields or authority from v0.31.
- V0.20 remains non-executable; v0.21 remains intent evidence; v0.22 remains
  validation-only; v0.23 remains record-only; v0.24 remains a handoff; v0.25
  and v0.26 remain simulations; v0.27 admission remains evidence-only; v0.28
  preparation remains no-send; v0.29 remains a 30-second preflight; and v0.30
  remains short-lived operator enablement, not execution authority.
- The v0.27 request/result contract and intake no-replay behavior are reused
  without widening. The v0.28 dormant client remains no-send; v0.31 adds an
  independent narrowly named adapter rather than changing that contract.
- Existing candidate, approval, Provider Intent, operational dispatch,
  repository workflow, worker, and execution-audit consumers do not import,
  read, or react to v0.31 records.
- Executable capability remains repository `update-compose-stack` and
  operational `restart-service/proxmox/qemu`; `install-container` remains
  absent from executable capability and intent registries.
- Discovery remains GET-only; Provider Intent remains Proxmox QEMU
  `monitoring-policy`; existing worker defaults remain off; backup/restore
  remains explicit stopped-service operator maintenance.
- No v0.31 phase may add installation, runtime/process execution, worker/
  workflow start, provider/repository/in-guest mutation, deployment, rollback,
  generic transport, background retry, release action, or Home Assistant
  deployment artifact.
