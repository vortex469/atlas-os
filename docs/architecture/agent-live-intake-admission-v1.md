# Agent Live Intake Admission v1 planning contract

Status: **Atlas v0.32 P0–P4 complete; P5 planned**.

Atlas v0.32 defines the narrowest production-registered Agent boundary that
may authenticate, receive, validate, and durably admit one inert v0.31 live
delivery evidence envelope. Admission remains evidence-only. It is not
execution admission and grants no installation, workflow, worker, deployment,
mutation, or runtime authority.

The authority equations are:

`authenticated delivery + durable admission != execution admission`

and:

`admission + acknowledgement != install, run, deploy, mutate, or retry`.

## Repository baseline and causal constraint

Planning starts from `main` at
`c93bf5b0790aa37f5d9bf348dca3ccdf3315baf5`, after annotated tag
`atlas-v0.31.0` targeting
`01e6fc40378f4f38f2559691768fc8880e69a96b`.

The repository already has the v0.27 closed request/admission/result/
acknowledgement models, default-disabled admission service, append-only store,
and explicitly constructed dormant route factory. Production Agent does not
register that route. V0.31 has an explicitly constructed one-shot Core send
coordinator and durable attempt/receipt evidence, but no production Core route
or production Agent registration.

The v0.31 receipt and result are causally downstream of Agent admission: Core
cannot possess them before Agent responds. V0.32 therefore must not require a
receipt or result as an admission input. The exact binding direction is:

```text
v0.20–v0.30 evidence
  -> v0.31 reserved send attempt + v0.32 intake envelope
  -> v0.32 Agent admission + acknowledgement/result
  -> v0.31 Core receipt/result evidence
```

The Agent admission binds the v0.31 reserved attempt. The returned result and
acknowledgement bind that admission. The existing Core receipt then binds the
attempt, Agent result, admission, acknowledgement, and Agent audit fingerprint.
This closes the v0.20–v0.31 graph without circular validation or a second
callback/finalization route.

## Exact request and transport envelope

V0.32 does not widen the embedded v0.27
`AgentInstallationIntakeRequestV1`. It defines one outer inert envelope so
Agent can recompute the v0.31 attempt and its complete v0.20–v0.30 linkage:

```text
AgentLiveIntakeEnvelopeV1 = {
  schema: "agent-live-intake-envelope-v1",
  send_attempt: LiveDeliverySendAttemptV1,
  intake_request: AgentInstallationIntakeRequestV1,
  request_fingerprint: FingerprintV1,
  request_body_fingerprint: FingerprintV1,
  idempotency_key_fingerprint: FingerprintV1,
  endpoint_fingerprint: FingerprintV1,
  content_type: "application/json",
  credential_reference_only: true,
  credential_material_present: false,
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
  envelope_fingerprint: FingerprintV1
}
```

The embedded `LiveDeliverySendAttemptV1` and
`AgentInstallationIntakeRequestV1` remain byte-for-byte schema compatible with
their frozen v0.31/v0.27 definitions. Agent requires:

- `send_attempt.request_fingerprint == intake_request.request_fingerprint`;
- the request body fingerprint to match canonical request bytes;
- the endpoint fingerprint to equal the server-owned configured endpoint;
- the request operator to equal the attempt operator;
- the request IDs/fingerprints to equal the v0.31 linkage; and
- every authority and replay field to retain its frozen false value.

Canonical request bodies remain at most 64 KiB. The outer envelope is closed,
duplicate-key rejecting, non-recursive beyond the fixed schema, and at most
128 KiB. The response remains at most 32 KiB. Unknown fields, non-finite
numbers, non-NFC strings, invalid timestamps, and duplicate JSON members fail
closed.

The envelope fingerprint domain is
`atlas:agent-live-intake-envelope:v1` over the complete closed envelope except
`envelope_fingerprint`, using SHA-256, one NUL byte, and canonical NFC JSON.

## Exact required linkage

The v0.32 envelope carries exactly one `LiveDeliverySendLinkageV1` inside the
v0.31 attempt. It contains no optional or alternate lineage:

```text
LiveDeliverySendLinkageV1 = {
  candidate_record_id,
  candidate_envelope_fingerprint,
  candidate_record_fingerprint,
  approval_intent_id,
  approval_intent_fingerprint,
  agent_request_id,
  agent_request_fingerprint,
  agent_validation_fingerprint,
  agent_audit_evidence_fingerprint,
  destination_fingerprint,
  source_plan_fingerprint,
  artifact_policy_fingerprint,
  execution_request_id,
  execution_request_fingerprint,
  dispatch_envelope_id,
  dispatch_envelope_fingerprint,
  simulation_request_id,
  intake_record_id,
  intake_record_fingerprint,
  intake_simulation_evidence_fingerprint,
  simulated_delivery_id,
  simulated_delivery_fingerprint,
  delivery_record_fingerprint,
  simulated_delivery_evidence_fingerprint,
  simulated_acknowledgement_id,
  simulated_acknowledgement_fingerprint,
  simulated_acknowledgement_evidence_fingerprint,
  intake_request_id,
  delivery_attempt_id,
  dormant_preparation_fingerprint,
  delivery_preparation_id,
  preparation_fingerprint,
  preflight_id,
  preflight_fingerprint,
  enablement_id,
  enablement_fingerprint
}
```

IDs are canonical UUIDv4 values and every fingerprint is the frozen
`FingerprintV1`. Agent recomputes the v0.31 attempt fingerprint, the embedded
v0.27 request fingerprint, dispatch envelope fingerprint, and all transitive
v0.20–v0.26 values available in the request. It verifies exact equality for
the v0.27–v0.30 values carried by the attempt. It must not use caller-supplied
records, headers, query parameters, or credentials as replacement evidence.

The resulting Core receipt is the downstream v0.31 binding. It must match the
same `send_attempt_id` and `attempt_fingerprint`, and its response, admission,
acknowledgement, and Agent audit fingerprints must be derived from the v0.32
response. Agent does not claim to have observed or validated that later Core
receipt.

## Exact admission, acknowledgement, result, and record

V0.32 reuses the frozen v0.27 admission and acknowledgement shapes without
adding execution authority. The wire response adds only the v0.31 attempt
identity needed for unambiguous Core validation:

```text
AgentLiveIntakeAdmissionV1 = {
  schema: "agent-live-intake-admission-v1",
  admission_id: UUIDv4,
  send_attempt_id: UUIDv4,
  attempt_fingerprint: FingerprintV1,
  envelope_fingerprint: FingerprintV1,
  intake_request_id: UUIDv4,
  request_fingerprint: FingerprintV1,
  delivery_attempt_id: UUIDv4,
  received_at: UtcSecond,
  valid_until: UtcSecond,
  operator_id: CanonicalOperatorId,
  linkage: LiveDeliverySendLinkageV1,
  status: "admitted_for_evidence_only",
  statement: "agent_admitted_authenticated_live_delivery_evidence_only",
  delivery_received: true,
  evidence_admission_granted: true,
  execution_admission_granted: false,
  execution_authorized: false,
  installation_allowed: false,
  worker_allowed: false,
  workflow_allowed: false,
  deployment_allowed: false,
  mutation_allowed: false,
  replay_allowed: false,
  admission_fingerprint: FingerprintV1
}

AgentLiveIntakeAcknowledgementV1 = {
  schema: "agent-live-intake-acknowledgement-v1",
  acknowledgement_id: UUIDv4,
  admission_id: UUIDv4,
  admission_fingerprint: FingerprintV1,
  send_attempt_id: UUIDv4,
  attempt_fingerprint: FingerprintV1,
  intake_request_id: UUIDv4,
  received_at: UtcSecond,
  valid_until: UtcSecond,
  status: "admitted_for_evidence_only",
  provenance: "authenticated_core_live_intake_evidence_only",
  execution_admission_granted: false,
  execution_authorized: false,
  installation_allowed: false,
  worker_allowed: false,
  workflow_allowed: false,
  deployment_allowed: false,
  mutation_allowed: false,
  replay_allowed: false,
  acknowledgement_fingerprint: FingerprintV1
}

AgentLiveIntakeResultV1 = {
  schema: "agent-live-intake-result-v1",
  send_attempt_id: UUIDv4 | null,
  intake_request_id: UUIDv4 | null,
  outcome: "admitted_for_evidence_only" | "rejected",
  admission: AgentLiveIntakeAdmissionV1 | null,
  acknowledgement: AgentLiveIntakeAcknowledgementV1 | null,
  reason_code: AgentLiveIntakeRejectionCodeV1 | null
}
```

For an admitted result, admission and acknowledgement are present and the
reason is null. For a rejection both evidence values are null and exactly one
closed reason is present. Authentication failures redact both IDs. The closed
reason set is `unauthenticated | unauthorized | malformed | not_current |
ownership_mismatch | request_mismatch | attempt_mismatch | linkage_mismatch |
fingerprint_mismatch | replay_conflict | quota_exceeded | unavailable`.

The append-only durable record is:

```text
AgentLiveIntakeRecordV1 = {
  schema: "agent-live-intake-record-v1",
  admission: AgentLiveIntakeAdmissionV1,
  acknowledgement: AgentLiveIntakeAcknowledgementV1,
  authenticated_principal: "atlas-core/install-intake-v1",
  permission: "installation_intake:create",
  credential_reference_fingerprint: FingerprintV1,
  lifecycle_at_creation: "admitted_for_evidence_only",
  default_enabled: false,
  evidence_only: true,
  execution_admission_granted: false,
  execution_authorized: false,
  installation_allowed: false,
  worker_allowed: false,
  workflow_allowed: false,
  deployment_allowed: false,
  mutation_allowed: false,
  replay_allowed: false,
  record_fingerprint: FingerprintV1
}
```

Fingerprint domains are:

- admission: `atlas:agent-live-intake-admission:v1` over
  `{operator_id, admission}` excluding `admission_fingerprint`;
- acknowledgement: `atlas:agent-live-intake-acknowledgement:v1` over the
  acknowledgement excluding its fingerprint; and
- record: `atlas:agent-live-intake-record:v1` over the record excluding
  `record_fingerprint`.

## Authentication and credential-reference verification

Production registration is independently default-off and server-owned:

```text
AgentLiveIntakeConfigurationV1 = {
  enabled: boolean = false,
  path: "/api/v1/internal/installation-intake",
  method: "POST",
  required_scheme: "https",
  principal: "atlas-core/install-intake-v1",
  permission: "installation_intake:create",
  credential_source: "mode-0400-file",
  credential_file: CanonicalAbsoluteFilePath,
  required_file_mode: "0400",
  maximum_credential_bytes: 4096,
  maximum_request_bytes: 131072,
  maximum_response_bytes: 32768,
  forwarded_ingress_allowed: false,
  proxy_allowed: false,
  execution_authorized: false,
  installation_allowed: false,
  worker_allowed: false,
  workflow_allowed: false,
  deployment_allowed: false,
  mutation_allowed: false,
  replay_allowed: false
}
```

Both Agent registration and the v0.32 Core envelope mode require explicit
independent enablement. Missing, malformed, or false settings register no
production route. Agent reads only the configured credential reference through
an injected verifier. It rejects symlinks, non-regular files, wrong owner or
mode, empty/oversized values, NUL/newline bytes, and file changes during read.
Comparison is constant-time. There is no environment fallback, credential
management API, generic authenticator, or reusable transport registry.

The secret may exist only transiently in authentication memory. It never
enters a model, record, fingerprint, error, log, trace, metric, response,
OpenAPI example, or UI. Authentication maps only to the fixed principal and
permission. Operator identity comes from the authenticated, validated envelope
and must equal every bound record; it is never accepted from a header, query,
path, cookie, or separate body field.

## Freshness, lifecycle, idempotency, and no replay

The trusted Agent whole-second UTC receive instant must satisfy:

```text
preflight.evaluated_at <= enablement.enabled_at <= send_attempt.created_at
  <= intake_request.sent_at <= agent_received_at
  < send_attempt.expires_at == intake_request.expires_at
  == enablement.expires_at == preflight.expires_at
  <= preflight.evaluated_at + 30 seconds
```

No phase may refresh, renew, extend, rebase, or replace this window. Arrival at
expiry is rejected. A response completed after expiry may describe an attempt
received before expiry, but grants no later action or replay.

Lifecycle is exactly `disabled | received | admitted_for_evidence_only |
rejected | expired | unavailable`. `received` is in-process only. Durable
admission starts at `admitted_for_evidence_only`, later derives `expired` after
`valid_until`, and becomes `unavailable` on corruption or failed owned read.
Rejection creates only bounded redacted audit evidence, never a partial
admission.

Before admission Agent permanently reserves the tuple of authenticated
principal, operator, raw idempotency-key digest, send attempt ID/fingerprint,
envelope fingerprint, v0.30 enablement, v0.29 preflight, v0.28 preparation,
v0.27 request, dispatch envelope, and all prior one-use identities. Exact
transport duplication returns the byte-identical stored result without
revalidation or side effects. Any changed value conflicts. Reservations are
not released by expiry, timeout, restart, corruption, quota failure, or
operator action. There is no retry endpoint, resend control, daemon, scheduler,
queue, callback, reconcile mutation, or replay bypass.

Records are owner-scoped. Foreign and absent reads are indistinguishable. No
cross-owner index, list, log, metric, or error exposes an identity.

## Redaction and audit evidence

Errors contain only schema, a closed reason code, safe message, correlation ID,
safe request/attempt fingerprints when authentication succeeded, `redacted:
true`, `retryable: false`, and fixed-false authority. They contain no raw
exception, secret, credential reference path, Authorization value, URL, host,
address, header, body, provider payload, command, log, repository path, or
guest path.

`AgentLiveIntakeAuditEvidenceV1` binds the admission/record/acknowledgement,
attempt/envelope/request/linkage fingerprints, principal and permission,
operator by fingerprint, correlation ID, trusted receive/completion times,
lifecycle, sanitized outcome, and every fixed-false authority flag. Its domain
is `atlas:agent-live-intake-audit-evidence:v1`. Audit storage is append-only and
contains neither secret material nor raw request/response bodies.

## Production registration and API/OpenAPI boundary

V0.32 may production-register exactly:

```text
POST /api/v1/internal/installation-intake
```

Registration occurs only inside the Agent application factory when the closed
startup configuration validates and `enabled` is explicitly true. There is no
module-import registration or permissive fallback. The method is POST only;
HTTPS, exact content type/length, Authorization, visible-ASCII idempotency key,
body/response bounds, duplicate-key rejection, and the fixed path are required.
Queries, cookies, redirects, compression, transfer encoding, forwarded ingress,
operator headers, alternate principals, and alternate media types fail closed.

The internal OpenAPI document exposes only that POST and the closed request/
result schemas. It contains no secret/default/example and no GET/list/item,
retry, resend, acknowledge, consume, execute, install, deploy, dispatch,
workflow, worker, credential, transport, rollback, or mutation sibling route.
Public Core OpenAPI and public Agent operator routes do not expose v0.32.

## Mission Control boundary

V0.32 adds no Mission Control client, type, page, component, route, navigation,
mutation, polling, retry, resend, send-again, or evidence display. The boundary
is internal service admission, and Core still exposes no guarded v0.31 send
read model. A later separately frozen operator-read API may present sanitized
admission evidence. It must never expose secrets, raw bodies, endpoints,
addresses, internal paths, or effect controls.

Home Assistant remains a blocked golden: non-installable, non-executable, and
without a deployment artifact or UI exception.

## P0–P5 plan

### P0 — Contract and threat model — selected

Freeze the causal binding, exact envelope/admission/acknowledgement/result/
record schemas, linkage, fingerprints, authentication/credential-reference,
freshness, lifecycle, idempotency/no-replay, ownership, redaction/audit,
registration, OpenAPI/UI boundary, threats, goldens, authority, and
must-not-change contracts. Documentation only.

### P1 — Closed v0.32 models and pure validation — complete

Add strict immutable mirrored Core/Agent models and pure validation for the
outer envelope, complete v0.20–v0.31 chain, admission, acknowledgement, result,
record, lifecycle, fingerprints, bounds, and fixed-false authority. Add no
service, store, route, registration, settings, credential read, or network.

### P2 — Durable Agent live-admission service/store — complete

Add an explicitly constructed, default-disabled service and bounded append-only
store. Validate injected authentication and the complete envelope, permanently
reserve before admission, persist admission/acknowledgement/audit atomically,
support exact-replay and owner-scoped readback, and fail corruption closed. Add
no route, registration, runtime, worker, workflow, or mutation consumer.

### P3 — Guarded production Agent registration — complete

Add the exact default-off startup configuration, injected credential verifier,
and production application-factory registration for the single internal POST.
Enforce HTTPS, fixed principal/permission/path, credential-file controls,
strict bounds/parsing, permanent no-replay, closed responses, and redaction.
Add no sibling route, generic command/transport/auth framework, or effect.

### P4 — Mission Control presentation absence — complete

The frozen boundary exposes no public Core read model or UI-facing API, so P4
does not invent a Core bridge or Mission Control surface. Structural tests
prove there is no v0.32 API client, hook, component, page, route, navigation,
read or mutation call, admit/retry/resend/send-again or effect control,
credential/token/raw-envelope/sensitive-evidence rendering, or Home Assistant
exception. Evidence admission remains non-installing, non-executing,
non-dispatching, non-workflow, non-worker, non-mutating, non-deploying,
non-rollback, and non-retry authority.

### P5 — Release validation and closure — planned

Prove exact chain/freshness, authentication and credential-file safety,
independent defaults, production registration/OpenAPI exactness, concurrent
single admission, restart/corruption/no-replay behavior, redaction, secret-free
persistence, zero effect consumers, absent UI, capability parity, prior
goldens, and Home Assistant blocking. Add tests and release evidence only; do
not migrate, tag, push, publish, deploy, or release automatically.

## Exact authority boundary

V0.32 may register one independently default-off internal Agent POST,
authenticate one fixed Core principal through one injected credential
reference, accept one bounded inert envelope for one current same-owner
v0.20–v0.31 reserved attempt, permanently reserve it, durably append one
evidence-only admission/acknowledgement/audit record, and return one closed
result. Core may adapt its explicitly constructed v0.31 one-shot composition
only enough to send and validate that envelope. This is the entire new
authority.

V0.32 may not install or execute; consume an installation execution request as
runtime authority; invoke Docker, Podman, Compose, containerd, shell,
subprocess, or process execution; start or enqueue dispatch, worker, workflow,
scheduler, retry, job, callback, or queue work; mutate provider, repository,
guest, candidate, desired, deployment, or credential state; deploy; roll back;
or create a Home Assistant artifact.

## What v0.32 enables later

A later separately frozen release may treat a current, same-owner,
cryptographically linked v0.32 admission as one prerequisite for a distinct
execution-admission decision. That future release must define new operator
confirmation, current-state revalidation, target/runtime authority,
cancellation, progress, failure, rollback, and audit semantics. No v0.32 ID,
fingerprint, admission, acknowledgement, result, or audit record is an
execution token.

## What remains blocked

Installation; container/runtime execution; Docker/Podman/shell/process calls;
operational dispatch; workers; workflows; queues; schedulers; retry/resend;
provider/repository/in-guest mutation; deployment; rollback; candidate
execution; broad commands/transports/authentication; public Core or Mission
Control surfaces; credential management; Home Assistant artifacts; and every
consumption of admission evidence as effect authority remain blocked.

## Threats and required goldens

Threats include forged Core/operator identity; credential disclosure or file
race; unauthenticated route registration; HTTP/forwarded/proxy bypass; stale,
foreign, altered, incomplete, oversized, duplicate-key, or deeply nested
envelopes; v0.31 attempt substitution; causal receipt confusion; idempotency
collision; concurrent duplicate delivery; reserve-after-admit; restart;
corruption; quota exhaustion; cross-owner reads; raw error/log leakage; route
or method expansion; downstream effect consumption; UI retry confusion; and
Home Assistant exceptions.

Required goldens include both defaults off; exact one POST only after explicit
construction; every v0.20–v0.31 ID/fingerprint mutation; one second before
expiry and at-expiry rejection; credential path/mode/owner/size/race failures;
no secret persistence or logs; strict HTTPS/header/body bounds; concurrent one
admission; exact transport duplicate with byte-identical zero-effect response;
changed replay conflict; restart readback; incomplete reservation/corruption
fail closed; foreign indistinguishable absence; closed redacted errors; exact
OpenAPI; no sibling/effect route; no Core/Agent/worker/workflow/provider/
repository/guest consumer; absent Mission Control surface; capability parity;
and Home Assistant blocked with no artifact.

## Must-not-change contracts

- V0.20–v0.31 schemas, fingerprint domains, stores, ownership, freshness,
  idempotency/no-replay, routes, redaction, and goldens remain unchanged.
- The embedded v0.27 request remains inert evidence-only. V0.28 remains dormant
  preparation, v0.29 remains a maximum-30-second preflight, v0.30 remains
  operator enablement rather than execution authority, and v0.31 remains
  one-shot with terminal ambiguity and no automatic retry.
- V0.32's outer envelope is a new versioned wrapper; it does not mutate the
  v0.27 request or v0.31 durable attempt/receipt models. The Core receipt is
  downstream and Agent never claims to have validated it before admission.
- Existing candidate, approval, execution-request, dispatch, provider intent,
  repository workflow, worker, and execution-audit consumers do not import,
  read, or react to v0.32 records.
- `install-container` remains absent from executable capability and intent
  registries. Existing executable capability remains repository
  `update-compose-stack` and operational `restart-service/proxmox/qemu`.
- Discovery stays GET-only; Provider Intent remains Proxmox QEMU
  `monitoring-policy`; worker defaults remain off; backup/restore remains
  explicit stopped-service operator maintenance.
- No v0.32 phase may add installation, runtime/process execution, worker or
  workflow start, provider/repository/in-guest mutation, deployment, rollback,
  retry scheduling, broad commands/transports/authentication, public UI, or a
  Home Assistant deployment artifact.
