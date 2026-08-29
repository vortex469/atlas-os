# Real Agent Intake Boundary v1 planning contract

Status: **Atlas v0.27 P0 selected; documentation only**.

This document freezes the narrowest guarded Agent boundary that may later
receive one authentic Core delivery of the exact released installation handoff
chain. Atlas v0.27 may implement closed models, pure admission, bounded evidence
preservation, and a dormant route factory. It does not enable Core delivery,
register the route in the production Agent, or create installation authority.

The authority equation for every v0.27 phase is:

`authenticated receipt + evidence-only admission != execution admission`

and

`evidence-only admission != installation authority != target mutation`.

## Repository inspection baseline

Planning starts from current `main` at `4a5ff02`, after released tag
`atlas-v0.26.0` at `4d51aee`. V0.26 supplies default-disabled, in-process
simulated delivery and acknowledgement evidence. It supplies no live transport,
production endpoint, authentic Core receipt, or execution authority.

V0.27 binds, without changing or reconstructing, exactly:

- v0.20 durable installation candidate record;
- v0.21 installation approval intent;
- v0.22 Agent install-container validation and audit evidence;
- v0.23 installation execution request record;
- v0.24 installation dispatch handoff envelope;
- v0.25 Agent intake simulation record and evidence; and
- v0.26 simulated delivery and acknowledgement evidence.

The v0.25 and v0.26 values are required lineage evidence, not live-delivery
authority. Production Core must not construct or send a v0.27 request until a
later release explicitly enables delivery and provisions the authentication
boundary. Production Agent must not register or expose the v0.27 route in this
release.

## Exact real intake request schema

The future authenticated Core caller supplies the hardened idempotency header
and exactly this closed body:

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
  prior_evidence: {
    intake_simulation: {
      simulation_request_id: canonical UUIDv4,
      intake_record_id: canonical UUIDv4,
      intake_record_fingerprint: FingerprintV1
    },
    simulated_delivery: {
      simulated_delivery_id: canonical UUIDv4,
      simulated_delivery_fingerprint: FingerprintV1,
      delivery_record_fingerprint: FingerprintV1,
      acknowledgement_id: canonical UUIDv4,
      acknowledgement_fingerprint: FingerprintV1
    }
  },
  delivery_authorized: true,
  evidence_admission_requested: true,
  execution_authorized: false,
  worker_allowed: false,
  mutation_allowed: false,
  replay_allowed: false,
  request_fingerprint: FingerprintV1
}
```

`InstallationDispatchEnvelopeV1` is the complete exact v0.24 envelope. The
caller may not project it, rebuild it, alter its `handoff-only` meaning, or add
an endpoint, credential, command, desired state, execution token, runtime
configuration, arbitrary metadata, or deployment content. The body is at most
64 KiB canonical bytes.

`CanonicalOperatorId` is visible ASCII, 1–128 bytes, and uses the existing
canonical Core operator identity. It is a Core assertion accepted only after
the dedicated Core service identity authenticates. It is never inferred from
the v0.24 body, a TLS peer address, a generic administrator role, or a caller-
chosen header.

The request fingerprint is SHA-256 over UTF-8
`"atlas:agent-installation-intake-request:v1"`, one NUL byte, and canonical
JSON of `{authenticated_core_principal, request}` excluding
`request_fingerprint`. The principal is exactly `atlas-core/install-intake-v1`.
Consequently a request cannot move between service principals even when its
JSON is identical.

All schemas are closed and reject unknown or duplicate keys. Strings are NFC;
timestamps are UTC whole seconds; UUIDs are canonical lowercase UUIDv4; and
`FingerprintV1`, canonical JSON, integer, boolean, and size rules retain their
released definitions.

## Exact admission evidence and result schemas

Successful validation may atomically append only this Agent-owned record:

```text
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
```

`valid_until` is exactly the request `expires_at`. `linkage` is the complete
exact v0.24 linkage copied byte-for-byte. `prior_evidence` is the request's
closed v0.25/v0.26 reference value copied byte-for-byte. The record is at most
32 KiB canonical bytes and contains no complete candidate, approval, v0.22
body, execution-request body, provider payload, raw destination identity,
address, credential, token, environment, command, repository or guest path,
deployment artifact, runtime output, workflow/job identity, lease, retry token,
or replay token.

The admission fingerprint uses domain
`"atlas:agent-installation-intake-admission:v1"` and the same owner-bound
canonical procedure over `{operator_id, admission}` excluding
`admission_fingerprint`. The authenticated Core principal is also preserved as
a fixed field; no caller-selected principal is accepted.

The synchronous response is exactly:

```text
AgentInstallationIntakeResultV1 = {
  schema: "agent-installation-intake-result-v1",
  intake_request_id: canonical UUIDv4 | null,
  outcome: "admitted_for_evidence_only" | "rejected",
  admission: AgentInstallationIntakeAdmissionV1 | null,
  reason_code: null | IntakeRejectionCodeV1
}
```

The admitted form includes the complete admission and a null `reason_code`.
The rejected form includes no admission and exactly one sanitized code:
`unauthenticated`, `unauthorized`, `malformed`, `not_current`,
`ownership_mismatch`, `request_mismatch`, `envelope_mismatch`,
`linkage_mismatch`, `simulation_evidence_mismatch`,
`delivery_evidence_mismatch`, `recipient_mismatch`, `replay_conflict`,
`quota_exceeded`, or `unavailable`. Authentication failures return the same
external status and body shape, omit `intake_request_id`, and reveal no
credential, operator, reservation, or record existence.

No durable rejection snapshot is created. A bounded sanitized audit event may
record time, correlation ID, authenticated sender class when known, request ID
when safely parsed, request fingerprint when fully validated, and one rejection
code. It never stores the rejected body.

## Required fingerprints and seven-release linkage

Before admission, Agent must validate the complete request and preserve these
exact identities:

- v0.20 `candidate_record_id`, candidate-envelope fingerprint, v0.19
  admission fingerprint, and candidate-record fingerprint;
- v0.21 `approval_intent_id` and approval-intent fingerprint;
- v0.22 `agent_request_id`, request fingerprint, validation fingerprint,
  audit-evidence fingerprint, destination fingerprint, source-plan
  fingerprint, and artifact-policy fingerprint;
- v0.23 `execution_request_id` and execution-request fingerprint;
- v0.24 `dispatch_envelope_id` and dispatch-envelope fingerprint;
- v0.25 `simulation_request_id`, `intake_record_id`, and intake-record
  fingerprint; and
- v0.26 `simulated_delivery_id`, simulated-delivery fingerprint,
  delivery-record fingerprint, `acknowledgement_id`, and acknowledgement
  fingerprint.

Agent recomputes the owner-bound v0.24 and v0.27 fingerprints, requires the
exact `install-container`/`handoff-only`/`atlas-agent` v0.24 tuple, and requires
all v0.24 authority fields to remain false. The authenticated operator
assertion must match the owner binding used by every owner-bound fingerprint.

Agent must resolve its own exact durable v0.25 intake record and v0.26
acknowledgement under that operator and require every referenced ID,
fingerprint, linkage member, statement, provenance, and fixed-false authority
field to match. It does not trust caller-supplied references alone. It does not
call Core, reopen Core stores, fetch missing evidence, reconstruct upstream
bodies, inspect a repository or target, or verify an image.

This is authenticated receipt plus transitive equality binding. Fingerprints
remain integrity/linkage values, not signatures, credentials, execution
approval, capabilities, or proof that upstream facts are still true.

## Authentication, authorization, ownership, and identity

The later live HTTP deployment must satisfy all of these independent gates:

1. HTTPS terminates at the reviewed internal Agent boundary; cleartext and
   forwarded public ingress are rejected.
2. `Authorization: Bearer` carries a dedicated high-entropy credential loaded
   from an Agent-readable mode-`0400` file. It authenticates only the fixed
   principal `atlas-core/install-intake-v1`. The operational-dispatch token,
   worker token, operator session, cookies, and generic Agent credentials are
   invalid here.
3. The principal is authorized only for `installation_intake:create`; no read,
   execution, workflow, provider, repository, runtime, or administrative
   permission follows.
4. Core asserts the canonical operator in the authenticated request body. Agent binds
   that operator to the request, v0.24 fingerprint, local v0.25/v0.26 evidence,
   store partition, idempotency namespace, admission fingerprint, and reads.

V0.27 does not provision the credential, add its setting, register middleware,
or expose the route. A later enabling release must define credential issuance,
rotation, revocation, TLS topology, deployment secret mounting, rate limiting,
and production acceptance. A bearer token observed without the required
internal HTTPS boundary is insufficient and fails closed.

The idempotency key, `intake_request_id`, `delivery_attempt_id`, v0.20–v0.26
IDs, and `admission_id` are distinct and cannot be collapsed or substituted.
`delivery_attempt_id` is the sole real delivery-attempt identity. It is not a
job, lease, approval, capability, execution nonce, or replay token. Operator
ownership cannot be delegated, transferred, globally enumerated, or changed;
foreign-owner access is indistinguishable from absence.

## Freshness, lifecycle, idempotency, and no replay

Admission requires trusted monotonic whole-second UTC time and:

- `envelope.prepared_at <= sent_at <= received_at < expires_at`;
- `expires_at == envelope.valid_until`;
- `received_at - sent_at <= 10 seconds`;
- the v0.25 record and v0.26 acknowledgement exist, match exactly, and were
  created before `sent_at`; and
- no timestamp is future-valued, ambiguous, or extended by v0.27.

The v0.25/v0.26 evidence may be expired when sent: it proves the tested lineage,
not current authority. The v0.24 envelope itself must still be current. Clock
rollback, unavailable trusted time, zero-width validity, expired envelope, or
ambiguous ordering fails closed.

Lifecycle is derived, never stored:

- `admitted`: exact admission exists and `received_at <= now < valid_until`;
- `expired`: exact admission exists and `now >= valid_until`; terminal; and
- `unavailable`: evidence is corrupt, incomplete, or cannot be validated.

Every lifecycle is evidence-only, non-executable, and non-mutating. There is no
queued, approved, ready, consuming, executing, installed, failed-install,
rollback, cancelled, renewed, superseded, or retrying state. Expiry performs no
write, cleanup, callback, event, queueing, or background work.

Idempotency and no replay are exact:

- `Idempotency-Key` is visible ASCII, 1–128 bytes, and scoped to authenticated
  Core principal, operator, and `installation_intake:create`;
- the store atomically reserves the idempotency key, request ID/fingerprint,
  delivery-attempt ID, v0.24 envelope ID/fingerprint, all v0.25/v0.26 evidence
  identities/fingerprints, and admission ID/fingerprint;
- one v0.24 envelope may produce at most one real v0.27 admission forever;
- exact retry returns the byte-identical original result without revalidation,
  time extension, a second audit acceptance, or any new work;
- changed content under any reserved identity returns `replay_conflict`;
- expiry never releases a reservation; and
- ambiguous persistence, timeout, corruption, or incomplete reservation returns
  `unavailable`; it never authorizes a new attempt.

V0.25 simulation and v0.26 simulated-delivery reservations are separate and do
not count as the one v0.27 real delivery. Once v0.27 admission exists, however,
neither Core nor Agent may redeliver it. A later execution release must consume
the admission through a new atomic, independently approved contract; it may not
reinterpret an exact intake retry as execution permission.

## Evidence store, redaction, and audit

P3 may add one independent append-only, operator-scoped Agent admission store.
It is restart-durable, atomically reserved, fail-closed on corruption, limited
to 16 records per operator and 32 KiB per record. There is no update, runtime
delete, eviction, compaction, repair, migration, expiry task, queue, event,
callback, execution bridge, or audit-store bridge. Backup v3 is not widened;
file handling remains explicit stopped-service operator maintenance.

Owned projections may expose only bounded timestamps, lifecycle, fixed status,
statement and authority fields, owned IDs and fingerprints, sanitized
`proxmox/qemu/existing-guest` resource identity, immutable image digest,
artifact kind, and provenance `authenticated_core_intake_evidence_only`. They
redact operator IDs, bearer material, provider payloads, raw destination
identities, addresses, credentials, tokens, environment, commands, repository
or guest paths, raw v0.22 content, deployment content, exception serialization,
HTTP internals, and store paths.

Logs contain correlation ID, fixed authenticated sender class, owned v0.24–
v0.27 IDs when safely available, fingerprints, lifecycle, and one outcome code.
They never contain request bodies or credentials. Evidence may say `received`
and `admitted_for_evidence_only`; it may not say `execution_admitted`,
`approved`, `queued`, `executed`, `installed`, `deployed`, `rolled_back`, or
`completed`.

## API, command, and UI boundaries

The sole frozen future API is:

```text
POST /api/v1/internal/installation-intake
Authorization: Bearer <dedicated Core intake credential>
Idempotency-Key: <visible ASCII, 1..128 bytes>
Content-Type: application/json
body: AgentInstallationIntakeRequestV1
response: AgentInstallationIntakeResultV1
```

The route accepts JSON only, rejects compressed and chunked/unbounded bodies,
enforces 64 KiB before parsing, and permits only `POST`; other methods return
`405` with `Allow: POST`. It accepts no query parameters, cookies, browser
sessions, redirects, multipart data, or caller-selected owner header. The later
enabling release must freeze exact HTTP status mapping and rate limits before
production registration.

In v0.27 the route factory may exist only in the isolated package and test app.
The production `main`, application container, OpenAPI document, settings,
deployment manifests, and Core client must not import, register, configure, or
discover it. There is no feature flag capable of enabling it. Consequently
production requests see no v0.27 route and Core has no destination to call.

V0.27 adds no CLI or shell command, Unix socket, RPC, worker message, event,
queue, Mission Control API client, page, component, navigation, control, or
readback UI. Owned readback is direct in-process store access in tests only.
Any production list/get API, command, UI, or Core delivery requires a later
planning decision.

## P0–P5 scope

### P0 — Contract and threat-model freeze — selected

Freeze these exact request, admission, result, fingerprint, seven-release
linkage, authentication/authorization, ownership, identity, freshness,
lifecycle, idempotency/no-replay, redaction, evidence, dormant-API, authority,
golden, and must-not-change rules. P0 changes planning documentation only.

### P1 — Closed models and pure validation — planned

Implement isolated immutable models, strict parsing, canonical fingerprints,
lifecycle derivation, failure precedence, and hostile-input tests. Perform no
I/O, persistence, application registration, network, process, runtime,
provider, repository, guest, worker, or workflow action.

### P2 — Authenticated admission service — planned

Implement an explicitly constructed service over injected authenticated Core
principal, operator assertion, trusted clock, local v0.25/v0.26 evidence
readers, and admission-store port. Validate only and return the closed result.
It cannot resolve Core, a target, repository, runtime, worker, or executor.

### P3 — Bounded intake evidence store — planned

Implement only the independent append-only store, atomic reservations, exact
idempotency, one-envelope no-replay, quotas, restart durability, owned reads,
and fail-closed corruption/ambiguity. Add no consumer or authority bridge.

### P4 — Dormant route factory and offline goldens — planned

Implement the exact bounded internal POST adapter and dedicated authentication
contract only in an explicitly constructed test application. Exercise
synthetic same-owner v0.20–v0.26 goldens. Do not register production Agent or
Core wiring, credential/settings support, CLI, UI, or deployment configuration.
Home Assistant remains a blocked/golden case with no deployment artifact.

### P5 — Isolation, no-replay, and release closure — planned

Prove exact linkage, authentication separation, lifecycle/freshness,
single-admission behavior, concurrency/restart/timeout ambiguity, ownership,
quotas, corruption, redaction, route bounds, zero production registration,
zero Core delivery, capability parity, prior goldens, and full regressions. Do
not migrate, tag, push, publish, deploy, or release automatically.

## Exact authority boundary

If explicitly constructed with its dependencies, Agent may authenticate the
fixed Core intake principal, accept one request, validate the exact seven-
release chain, and preserve one bounded evidence-only admission. Those are the
only new powers contemplated by v0.27.

Agent may not treat admission as execution approval, create or start work,
invoke Docker, Podman, Compose, containerd, or any container runtime, execute a
shell or process, access or mutate a provider, read or mutate a repository,
read or mutate an in-guest filesystem or service, acquire an image, deploy,
roll back, start a workflow, invoke a worker, install Home Assistant, or mutate
the target. Filesystem writes are limited to the explicitly constructed intake
evidence store.

Core may not construct, send, retry, reconcile, or expose a v0.27 delivery in
this release. Production Agent may not expose the route. A later release must
explicitly enable both sides; v0.27 evidence alone cannot do so.

## Must-not-change contracts

- V0.20–v0.26 schemas, fingerprints, stores, routes, ownership, freshness,
  lifecycle, idempotency, goldens, and meanings remain exact. V0.27 references
  them without migration or trust promotion.
- V0.20 remains non-executable; v0.21 remains an immutable approval statement;
  v0.22 remains validation-only; v0.23 remains record-only; v0.24 remains a
  handoff-only envelope; v0.25 remains simulation, not receipt; and v0.26
  remains simulated, not live delivery or acknowledgement.
- Existing candidate approvals, repository workflow, operational dispatch,
  Provider Intent, execution audit, worker, and interrupted-side-effect no-
  replay contracts consume no v0.27 evidence.
- Agent executable support remains `update-compose-stack` for repository work
  and `restart-service/proxmox/qemu` for operational work. `install-container`
  remains absent from executable capability and intent registries.
- Discovery stays GET-only; Provider Intent stays Proxmox QEMU
  `monitoring-policy`; the optional worker stays default-disabled; backup and
  restore stay explicit operator maintenance.
- No Docker/Podman/container-runtime call, shell/process execution, image
  acquisition, provider mutation, repository read or mutation, in-guest read
  or mutation, workflow start, worker execution, installation, deployment,
  rollback, background work, production API registration, Core client,
  credential provisioning, UI, migration, tag, push, publication, or release
  is added by v0.27.

## Threats and golden cases

The threat model covers forged Core identity, reuse of operational or worker
credentials, cleartext/public ingress, operator spoofing, cross-owner access,
substituted IDs/fingerprints, missing local v0.25/v0.26 evidence, stale or
future requests, slow delivery, duplicate/unknown fields, oversized bodies,
credential/body logging, admission wording presented as execution, replay
after timeout/expiry, partial persistence, corruption/quota fail-open behavior,
production registration drift, and later consumers treating admission as a
job or capability.

The positive golden uses a synthetic exact same-owner v0.20–v0.26 chain and an
injected fixed Core principal. One fresh request creates one admission with
`delivery_received=true`, `evidence_admission_granted=true`, and every execution
and mutation field false. Exact retry returns byte-identical evidence. Changed
principal, owner, identity, fingerprint, linkage, time, recipient, authority
field, idempotency content, or unknown key fails closed without work.

Home Assistant remains blocked before v0.20 because its deployment artifact is
absent and its realistic workload is outside the v0.22 policy. It may appear
only as a rejected/golden fixture. No artifact or exception is introduced.

## What v0.27 enables later and what remains blocked

V0.27 enables later work to register a reviewed, bounded Agent intake route;
provision a dedicated Core identity; deliver one exact owner-bound handoff;
and reuse deterministic authentication, freshness, linkage, evidence custody,
and atomic no-redelivery rules. It creates a stable input to a future,
separately approved execution-admission design.

Still blocked are production route registration, credentials and TLS rollout,
Core request construction and delivery, production receipt, list/read UI or
API, independent fresh execution approval, atomic execution consumption,
execution-time target/image proof, runtime/worker authority, Docker/Podman or
process use, provider/repository/in-guest access or mutation, workflow start,
side-effect recovery/audit, image acquisition, installation, deployment,
rollback, and Home Assistant installation.
