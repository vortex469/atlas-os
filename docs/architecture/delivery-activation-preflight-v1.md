# Controlled Delivery Activation Preflight v1 planning contract

Status: **Atlas v0.29 P0–P5 implemented and validated**.

This document freezes the narrowest Core-local boundary that can answer one
question: whether one exact dormant v0.28 Core-to-Agent delivery preparation is
currently eligible to be considered by a later, separately released activation
contract. V0.29 may validate the complete owner-bound v0.20–v0.28 evidence chain
and preserve a bounded preflight snapshot. It does not activate, deliver, or
execute anything.

The authority equations for every v0.29 phase are:

`preflight_eligible != activation_approved != delivery_authorized`

and:

`durable preflight evidence != transport authority != execution authority`.

## Repository inspection baseline

Planning starts from current `main` at
`2ba2a14652d27b8e4c1c91297406c8de76653403`, after released annotated tag
`atlas-v0.28.0` targeting
`c95d580b3cdc9d4cb52d2cfe3e7b764506c2ae9c`.

The repository already provides the released v0.20 durable candidate, v0.21
approval intent, v0.22 Agent validation evidence, v0.23 execution request,
v0.24 dispatch handoff, v0.25 intake simulation, v0.26 simulated delivery and
acknowledgement, v0.27 real-intake evidence boundary, and v0.28 dormant
delivery preparation. Production Core and Agent remain disconnected: the
v0.28 client has no send method and no production construction, and the v0.27
Agent route remains test-only and unregistered.

V0.29 preserves that state. It is an eligibility snapshot over local evidence,
not a transport probe, readiness check against Agent, activation switch, or
execution-admission decision.

## Exact preflight request and result schemas

The authenticated operator may submit only an exact-identity confirmation:

```text
DeliveryActivationPreflightCreateV1 = {
  schema: "delivery-activation-preflight-create-v1",
  delivery_preparation_id: canonical UUIDv4,
  preparation_fingerprint: FingerprintV1
}
```

The caller cannot supply operator identity, upstream records or fingerprints,
time, endpoint/authentication data, credentials, an Agent result, desired
state, eligibility, lifecycle, reason codes, or authority flags. Core resolves
the v0.28 preparation and every upstream value through existing owner-scoped
local readers.

One successful evaluation returns and, from P2 onward, may durably preserve:

```text
DeliveryActivationPreflightResultV1 = {
  schema: "delivery-activation-preflight-result-v1",
  preflight_id: canonical UUIDv4,
  evaluated_at: UtcSecond,
  expires_at: UtcSecond,
  delivery_preparation_id: canonical UUIDv4,
  preparation_fingerprint: FingerprintV1,
  endpoint_fingerprint: FingerprintV1,
  linkage: DeliveryActivationPreflightLinkageV1,
  decision: "eligible_for_later_activation" | "ineligible",
  reason_codes: [DeliveryActivationPreflightReasonCodeV1, ...],
  lifecycle_at_evaluation: "eligible" | "ineligible",
  statement: "local_evidence_preflight_only_no_delivery_activation",
  source: "core_delivery_activation_preflight_v1",
  default_enabled: false,
  agent_contacted: false,
  credentials_loaded: false,
  production_transport_registered: false,
  delivery_activated: false,
  delivery_authorized: false,
  execution_admission_granted: false,
  execution_authorized: false,
  worker_allowed: false,
  mutation_allowed: false,
  replay_allowed: false,
  preflight_fingerprint: FingerprintV1
}
```

The exact linkage value is:

```text
DeliveryActivationPreflightLinkageV1 = {
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
  dormant_preparation_fingerprint: FingerprintV1
}
```

The v0.19 admission fingerprint remains transitively bound by the exact v0.20
candidate envelope and record fingerprints; it is recomputed and validated but
is not duplicated in the v0.29 linkage projection. No v0.27 admission or
acknowledgement is required: a genuine v0.27 admission for the envelope makes
the preparation ineligible because the dormant request is no longer an unused
pre-delivery candidate.

`reason_codes` is empty only for `eligible_for_later_activation`. For
`ineligible`, it is a non-empty, sorted, duplicate-free subset of:

```text
preflight_feature_disabled
preparation_not_found
preparation_fingerprint_mismatch
ownership_mismatch
linkage_mismatch
upstream_fingerprint_mismatch
upstream_state_invalid
preparation_not_dormant
already_admitted
expired
clock_invalid
authority_mismatch
evidence_unavailable
evidence_corrupt
replay_conflict
```

Foreign-owner records are reported as `preparation_not_found`, never
`ownership_mismatch`. The latter is an internal validation/audit code only.
Malformed requests fail before a result is created. Store ambiguity or failure
returns a sanitized no-result `unavailable` API error and must not be converted
to an `ineligible` durable claim.

## Deterministic fingerprints and exact binding

The v0.29 fingerprint is SHA-256 over UTF-8 domain string
`atlas:delivery-activation-preflight-result:v1`, one NUL byte, and canonical
JSON `{operator_id, result}` excluding `preflight_fingerprint`.

Eligibility requires Core to load and validate the complete exact same-owner
chain, not merely compare the projected fields:

- v0.20 candidate record, candidate envelope, v0.19 admission, and their exact
  fingerprints;
- v0.21 approval intent and fingerprint;
- v0.22 Agent request, validation, audit evidence, destination, source-plan,
  and artifact-policy fingerprints;
- v0.23 execution request and fingerprint;
- v0.24 dispatch envelope and fingerprint;
- v0.25 simulation request, intake record, and audit-evidence fingerprints;
- v0.26 simulated delivery, delivery record, delivery audit evidence,
  simulated acknowledgement, and acknowledgement audit evidence;
- v0.27 request identity and delivery-attempt identity embedded in v0.28; and
- v0.28 preparation, endpoint, request, source linkage, status, statement,
  fixed authority values, and preparation fingerprint.

All IDs and fingerprints must equal the exact transitive references in the
released records. Every released fingerprint is recomputed from its complete
authoritative value. No value is reconstructed from a fingerprint, accepted
from the caller beyond the v0.28 identity confirmation, fetched from Agent, or
promoted from evidence to authority.

## Decision, lifecycle, freshness, and expiry

`eligible_for_later_activation` is returned only when, at the same trusted
whole-second UTC instant:

- the feature is explicitly constructed and locally enabled for preflight
  evidence only;
- the authenticated operator owns the complete chain;
- every schema, fingerprint, identity, linkage, time ordering, fixed statement,
  provenance, and authority field validates exactly;
- v0.20 is active, v0.21 retains its released immutable meaning, v0.22 is
  `valid_but_unsupported`, v0.23 is `recorded`, and v0.24 is `prepared`;
- the v0.25/v0.26 evidence is complete and authentic only to its released
  simulation provenance; its historical lifecycle may be expired but its
  timestamps and linkage must remain valid;
- v0.28 is `not_sent`, `prepared_dormant`, fixed-disabled, unmodified, and has
  no conflicting v0.27 admission; and
- `evaluated_at < preparation.valid_until`.

The result expiry is exact:

```text
expires_at = min(preparation.valid_until, evaluated_at + 30 seconds)
```

No eligible result may be created with `expires_at <= evaluated_at`.
Ineligible results use `expires_at = evaluated_at` and are immediately terminal
evidence. A later reader derives lifecycle without mutation:

- `eligible`: eligible decision and `evaluated_at <= now < expires_at`;
- `expired`: formerly eligible and `now >= expires_at`, terminal;
- `ineligible`: ineligible decision, terminal; or
- `unavailable`: record, clock, or current owner-scoped revalidation is
  corrupt, incomplete, ambiguous, or unavailable.

Reads must re-resolve current v0.20/v0.21/v0.23/v0.24/v0.28 state. A durable
eligible snapshot never remains eligible after an upstream expiry, revocation,
superseding released lifecycle transition, conflicting admission, clock
failure, or fingerprint mismatch. Expiry cannot be extended, renewed, or
refreshed in place. A later activation release must perform its own fresh
preflight and cannot rely on a stale v0.29 record.

## Operator ownership, authentication, and authorization

One authenticated Core operator owns the request, every resolved Core record,
the preflight reservation, and the durable result. Identity comes only from the
existing authenticated Core session/principal and is included in the result
fingerprint. It is not caller-selected, transferable, delegable, or disclosed
across owner partitions. List and item reads are owner-scoped; foreign IDs are
indistinguishable from absence.

Create requires the existing authenticated operator boundary plus the narrow
Core authorization `installation_delivery_preflight:create`; read requires
`installation_delivery_preflight:read`. Neither permission implies
`installation_intake:create`, transport access, credential access, execution,
provider, repository, worker, workflow, or deployment authority. Service-to-
service Core-to-Agent credentials are neither accepted nor loaded. CSRF and
same-origin protections retain their existing Core mutation semantics.

## Idempotency, single evaluation, and no replay

- The visible-ASCII idempotency key is 1–128 bytes and scoped to operator plus
  `delivery_activation_preflight:create`.
- The append-only store atomically reserves the idempotency key, v0.28
  preparation ID/fingerprint, v0.27 intake-request and delivery-attempt IDs,
  preflight ID, and preflight fingerprint.
- One v0.28 preparation may produce at most one v0.29 preflight forever.
- Exact retry returns the byte-identical result without rereading evidence,
  changing time, extending expiry, contacting Agent, or performing new work.
- Changed input under any reserved identity returns `replay_conflict`.
- Ineligible and expired results never release reservations. There is no
  retry-as-refresh, replacement, renewal, delete-and-recreate, or conversion.
- Timeout, partial reservation, corruption, or ambiguous completion fails
  closed as unavailable and never permits a second result.

A preflight ID, idempotency key, preparation ID, intake-request ID, delivery-
attempt ID, or fingerprint is not a capability, credential, approval token,
delivery nonce, retry token, execution lease, or replay token. No downstream
consumer exists in v0.29.

## Durable store, redaction, and audit evidence

P2 may add one independent append-only, operator-scoped Core store limited to
16 records per operator and 96 KiB canonical bytes per record. It supports
atomic append and owned list/item read only and fails closed on corruption. It
has no update, runtime delete, eviction, compaction, repair, migration of prior
stores, expiry task, queue, event, callback, outbox, transport status, or
authority bridge. Backup v3 is not widened.

Durable evidence may expose only bounded timestamps, derived lifecycle,
decision and sanitized reason codes, fixed statements/authority fields,
owned IDs/fingerprints, sanitized resource class, immutable image digest,
artifact kind, and `core_delivery_activation_preflight_v1` provenance.

API, UI, logs, and errors redact other-owner existence and operator IDs;
endpoint host/TLS name; CA and credential paths or material; Authorization and
cookies; raw v0.22 evidence, destinations, provider payloads, commands,
environment, repository/guest paths, deployment content, request/response
bodies, HTTP internals, exceptions, and store paths. Logs contain only a
correlation ID, safe owned IDs/fingerprints, lifecycle, and one sanitized code.
Evidence may say `eligible_for_later_activation`; it may not say `approved`,
`activated`, `sent`, `delivered`, `received`, `execution_admitted`, `queued`,
`executed`, `installed`, `deployed`, `rolled_back`, or `completed`.

## Default-disabled, API, UI, and production boundaries

The preflight service, store, API routes, and Mission Control adapter are
default-disabled and absent from production construction until their P phase
explicitly adds reviewed local registration. The only future Core API shape in
v0.29 is:

```text
POST /api/v1/installation-delivery-preflights
GET  /api/v1/installation-delivery-preflights
GET  /api/v1/installation-delivery-preflights/{preflight_id}
```

There is no update/delete/activate/approve/send/deliver/retry/refresh/consume/
execute/install/deploy/rollback sibling. POST accepts JSON plus the existing
`Idempotency-Key` header only. List is bounded, owner-scoped, newest-first, and
cursor-paginated; item read is owner-scoped. Routes never call Agent or a
network/process/runtime dependency.

Mission Control may later provide a guarded “Run local preflight” confirmation
and read-only evidence view. It must label eligibility as temporary and non-
authorizing, show expiry and sanitized blockers, and expose no Activate,
Approve delivery, Send, Retry, Execute, Install, Deploy, Roll back, workflow,
credential, endpoint, or Agent control or action navigation.

V0.29 adds no Agent route or registration change, Core-to-Agent client or
transport registration, credential/secret/CA setting or mount, DNS/TLS/HTTP,
CLI/shell/process command, Docker/Podman/container runtime call, event, queue,
worker message, workflow node, callback, listener, scheduler, startup task,
provider/repository/guest access, deployment manifest, or Home Assistant
artifact.

## P0–P5 scope

### P0 — Preflight contract and threat model — selected

Freeze the exact request/result/linkage schemas, decision and lifecycle values,
fingerprints, ownership, authentication/authorization, freshness/expiry,
idempotency/no-replay, durable-evidence option, redaction/audit, default-
disabled API/UI boundary, threats, goldens, authority, and must-not-change
contracts. Change planning documentation only.

### P1 — Closed models and pure evaluation — complete

Implement isolated immutable Core models, canonical fingerprints, complete
v0.20–v0.28 linkage validation, deterministic decision/lifecycle derivation,
and hostile-input tests over injected values and time. Add no I/O, store,
route, client, registration, or side effect.

### P2 — Bounded append-only preflight evidence — complete

Implement the explicitly constructed evaluator over injected owner-scoped
readers, trusted clock, ID factory, and independent store. Add atomic
reservations, exact retry, restart durability, quotas, owned reads, and
fail-closed ambiguity/corruption. It may create/read durable preflight evidence
only; add no consumer or activation bridge.

### P3 — Authenticated Core-local API — complete

Add only guarded create/list/item-read, preserving exact authn/authz, bounds,
OpenAPI, redaction, methods, default-disabled registration, and dependency
isolation. The request path must never load live secrets, invoke Agent, or
reach transport, runtime, worker, workflow, dispatch, provider, repository, or
guest modules.

### P4 — Mission Control evidence review — complete

Add explicit local-preflight confirmation and read-only evidence presentation
with expiry and non-authority language. Lock out activation, delivery,
execution, installation, deployment, rollback, credential, endpoint, Agent,
workflow, and action-navigation controls. Keep Home Assistant blocked.

### P5 — Isolation, no-replay, and release closure — complete

Prove full linkage and fingerprint sensitivity, state precedence, freshness,
expiry, ownership, authz, concurrency/restart/ambiguity, quotas, corruption,
redaction, exact retry/no-replay, API/UI bounds, default-disabled posture, zero
Agent contact and transport/secret/runtime registration, zero consumers,
capability parity, prior goldens, and full regressions. Add no migration, tag,
push, publication, deployment, or release automatically.

P5 closure proves the Core service/store remains append-only evidence with no
authority bridge; production constructs no preflight service; Agent has no
preflight consumer or registration; Core exposes only guarded create/list/item
read; Mission Control has no prohibited action/navigation/mutation surface;
and Home Assistant remains blocked without a deployment artifact. P5 changes
tests and release evidence only.

## Exact authority boundary

V0.29 may, only when the local preflight contract is explicitly constructed,
resolve same-owner local durable evidence, recompute and validate the complete
v0.20–v0.28 chain, derive one bounded eligibility decision, atomically preserve
one operator-owned preflight record, and provide authenticated owner-scoped
create/list/item readback. These evidence writes and reads are its entire new
authority.

V0.29 must not activate delivery; send any request to Agent; call the Agent
application in-process; register production transport or the Agent route; load
credentials, secrets, CA material, or Authorization; resolve DNS or perform
TLS/HTTP/network I/O; invoke worker, workflow, operational dispatch, repository
execution, Docker, Podman, Compose, containerd, shell, or any process; access or
mutate provider, repository, or in-guest state; consume an approval; create a
job; install, deploy, roll back, or create a Home Assistant deployment
artifact. No feature flag or preflight result can override these prohibitions.

## Must-not-change contracts

- V0.20–v0.28 schemas, fingerprints, stores, routes, ownership, lifecycle,
  freshness, idempotency/no-replay, redaction, and goldens remain exact. V0.29
  references them without migration, field addition, trust promotion, or
  changed consumer behavior.
- V0.20 remains non-executable; v0.21 remains approval-intent evidence; v0.22
  remains validation-only and unsupported; v0.23 remains record-only; v0.24
  remains prepared and not delivered; v0.25 remains simulation; v0.26 remains
  simulated delivery; v0.27 remains evidence-only intake; and v0.28 remains
  dormant, fixed-disabled, and unable to send.
- The v0.27 Agent route remains test-only and unregistered. The v0.28 client
  remains explicitly constructed, has no send method, reads no credentials,
  and has no production registration.
- Existing approvals, candidates, Provider Intent, operational dispatch,
  repository workflow, execution audit, worker, and interrupted-side-effect
  no-replay contracts neither consume nor gain fields from v0.29 evidence.
- Executable capability remains `update-compose-stack` for repository work and
  `restart-service/proxmox/qemu` for operational work. `install-container`
  remains absent from executable capability and intent registries.
- Discovery remains GET-only; Provider Intent remains Proxmox QEMU
  `monitoring-policy`; the worker remains optional/default-disabled; backup
  and restore remain explicit stopped-service operator maintenance.
- No v0.29 phase may silently add transport, secrets, Agent contact, runtime or
  process execution, mutation, installation, deployment, rollback, migration,
  release action, or Home Assistant artifact.

## Threats and golden cases

The threat model covers stale eligibility being treated as activation,
cross-owner substitution, caller-supplied linkage, fingerprint truncation,
upstream expiry/revocation drift, forged fixed-false fields, hidden Agent
probe, transport or credential loading through validation, TOCTOU between
evaluation and later activation, duplicate/unknown fields, idempotency refresh
or replay, concurrent creation, partial persistence, corruption/quota fail
open, route registration drift, UI action smuggling, logs leaking endpoint or
credential data, and a later consumer treating evidence as a capability.

The positive golden is synthetic: one fresh exact same-owner v0.20–v0.28 chain
with no v0.27 admission produces one short-lived
`eligible_for_later_activation` result with every authority/effect field false.
Exact retry returns byte-identical evidence. At expiry, current-state readback
derives `expired`; it never refreshes the record. Any changed owner, ID,
fingerprint, linkage, state, time, authority value, reservation content, or
unknown field fails closed without contacting Agent or performing work.

Home Assistant remains the blocked golden. It cannot reach v0.20 because the
deployment artifact is absent and its realistic workload remains outside the
v0.22 policy. V0.29 creates no artifact, exception, or positive result for it.

## What v0.29 enables later and what remains blocked

V0.29 enables a later release to require one exact, fresh, owner-bound,
no-replay eligibility proof before separately considering activation of the
reviewed v0.28 wiring. It gives that later design a stable decision schema,
complete nine-release linkage, a short TOCTOU window, and auditable negative
evidence without redesigning upstream contracts.

Still blocked are the activation contract and operator activation approval;
production Core client construction; credential/CA provisioning and loading;
Agent route registration; DNS, TLS, HTTP, and live delivery; receipt and
ambiguous-send reconciliation; atomic preflight consumption/no-redelivery;
execution approval, execution-time target/image proof, job creation, runtime
or worker authority; provider/repository/in-guest effects; image acquisition;
installation, deployment, rollback, side-effect recovery/audit; delivery
controls; and Home Assistant installation.
