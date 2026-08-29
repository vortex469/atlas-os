# Dormant Core-to-Agent Delivery Wiring v1 planning contract

Status: **Atlas v0.28 P0 contract frozen; P1–P5 implemented and validated**.

This document freezes the narrowest Core-side wiring boundary that can later
connect one exact v0.24 dispatch handoff envelope to the dormant v0.27 Agent
intake route. V0.28 may model and validate the future HTTPS exchange, assemble
one immutable request from authoritative evidence, preserve bounded dormant
preparation evidence, and expose an explicitly constructed client factory with
no send capability. It does not register the Agent route, provision secrets,
open a network connection, or deliver anything in production.

The authority equation for every v0.28 phase is:

`dormant request preparation + response validation != network delivery`

and:

`intake admission evidence != execution admission != installation authority`.

## Repository inspection baseline

Planning starts from current `main` at
`31f7dd1e6eb84390080195b320d87018e9589444`, after released annotated tag
`atlas-v0.27.0` targeting
`d0a36dd41eeec7a04acf500a3c21cfd98b882d4e`.

The repository currently provides:

- the v0.20 durable installation candidate and envelope fingerprints;
- the v0.21 approval-intent fingerprint;
- the v0.22 Agent install-container request, validation, audit, destination,
  source-plan, and artifact-policy fingerprints;
- the v0.23 execution-request record and fingerprint;
- the v0.24 handoff-only dispatch envelope and fingerprint;
- the v0.25 Agent intake-simulation record and evidence fingerprint;
- the v0.26 simulated-delivery, delivery-record, and simulated-
  acknowledgement fingerprints; and
- the v0.27 authenticated real-intake request, admission, acknowledgement,
  audit-evidence, redacted-error, result, and validation contracts.

The v0.27 route factory exists only inside the isolated Agent package and
explicit test applications. Production Agent `main`, container, settings,
OpenAPI, credentials, and deployment paths do not register it. Production Core
has no v0.27 request builder, endpoint setting, credential, client, transport,
consumer, route, command, worker, workflow, or Mission Control call path.

V0.28 must preserve that production state. It defines dormant wiring, not live
delivery.

## Exact dormant client and factory contract

The only contemplated Core factory is conceptually:

```text
create_dormant_agent_intake_delivery_client(
  *,
  configuration: DormantAgentIntakeDeliveryConfigurationV1,
  evidence_reader: AgentIntakeDeliveryEvidenceReader,
  preparation_store: AgentIntakeDeliveryPreparationStore,
  clock: TrustedUtcClock,
  id_factory: Uuid4Factory
) -> DormantAgentIntakeDeliveryClient
```

Construction is explicit. There is no global singleton, dependency-container
binding, settings loader, startup hook, application registration, router
dependency, workflow dependency, worker dependency, background task, event
subscription, or environment-driven auto-construction.

The client has only these operations:

```text
prepare(
  create: CoreAgentIntakeDeliveryCreateV1,
  *,
  authenticated_operator_id: CanonicalOperatorId,
  idempotency_key: IdempotencyKey
) -> CoreAgentIntakeDeliveryPreparationResultV1

validate_response(
  preparation: CoreAgentIntakeDeliveryPreparationV1,
  response: AgentInstallationIntakeResultV1
) -> CoreAgentIntakeDeliveryResponseValidationV1

get_preparation(
  *,
  authenticated_operator_id: CanonicalOperatorId,
  delivery_preparation_id: canonical UUIDv4
) -> CoreAgentIntakeDeliveryPreparationV1
```

It has no `send`, `deliver`, `post`, `request`, `retry`, `reconcile`, `consume`,
`execute`, `install`, `deploy`, `rollback`, `dispatch`, `start_workflow`, or
generic transport method. `validate_response` accepts only an already supplied
closed value; it cannot fetch one. The factory and package may not import an
HTTP/network client, socket, TLS implementation, process/runtime adapter,
provider, repository, worker, workflow, or Agent application.

## Exact endpoint, address, authentication, and disabled configuration

The closed injected configuration is:

```text
DormantAgentIntakeDeliveryConfigurationV1 = {
  schema: "dormant-agent-intake-delivery-configuration-v1",
  enabled: false,
  mode: "prepare-and-validate-only",
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
  agent_route_registered: false,
  production_transport_registered: false,
  production_delivery_allowed: false,
  execution_authorized: false,
  worker_allowed: false,
  mutation_allowed: false,
  replay_allowed: false
}
```

`CanonicalInternalDnsName` is a lowercase ASCII DNS name of at most 253 bytes.
It is not an IP literal, `localhost`, a loopback/link-local/multicast/public
address, a URL, or a name containing user information, a path, query, fragment,
wildcard, underscore, trailing dot, or percent encoding. `tls_server_name`
must equal `host`. The path, timeouts, booleans, principal, authorization, and
credential semantics are fixed, not caller choices.

`CanonicalAbsoluteFilePath` is an absolute normalized POSIX file path with no
NUL, `.`/`..` segment, symlink resolution, environment expansion, or home
shortcut. The configuration validates shape only in v0.28. It does not read
either file, provision a credential or CA, resolve DNS, inspect file mode,
build TLS state, or authorize transport. Secret values are never configuration
fields. Production settings and manifests must contain none of these fields in
v0.28.

An endpoint configuration is future transport metadata, not authority to use
the endpoint. `enabled` and every registration, delivery, execution, worker,
mutation, and replay flag are closed `false` literals. No feature flag,
environment variable, settings override, CLI argument, API value, or test
monkeypatch may turn them true.

## Exact create, wire request, and preparation schemas

The authenticated Core operator may supply only:

```text
CoreAgentIntakeDeliveryCreateV1 = {
  schema: "core-agent-intake-delivery-create-v1",
  dispatch_envelope_id: canonical UUIDv4,
  intake_record_id: canonical UUIDv4,
  simulated_delivery_id: canonical UUIDv4,
  simulated_acknowledgement_id: canonical UUIDv4
}
```

The caller cannot supply fingerprints, complete records, operator identity,
delivery/intake request identity, timestamps, endpoint/address/authentication,
headers, credential material, body bytes, timeout, retry count, command,
desired state, runtime/deployment content, or authority flags. Core resolves
all referenced values from exact authoritative owner-scoped stores.

One successful dormant preparation produces:

```text
CoreAgentIntakeDeliveryPreparationV1 = {
  schema: "core-agent-intake-delivery-preparation-v1",
  delivery_preparation_id: canonical UUIDv4,
  prepared_at: UtcSecond,
  valid_until: UtcSecond,
  endpoint_fingerprint: FingerprintV1,
  request: AgentInstallationIntakeRequestV1,
  source: {
    dispatch_envelope_id: canonical UUIDv4,
    dispatch_envelope_fingerprint: FingerprintV1,
    intake_record_id: canonical UUIDv4,
    intake_record_fingerprint: FingerprintV1,
    intake_simulation_evidence_fingerprint: FingerprintV1,
    simulated_delivery_id: canonical UUIDv4,
    simulated_delivery_fingerprint: FingerprintV1,
    delivery_record_fingerprint: FingerprintV1,
    simulated_delivery_evidence_fingerprint: FingerprintV1,
    simulated_acknowledgement_id: canonical UUIDv4,
    simulated_acknowledgement_fingerprint: FingerprintV1,
    simulated_acknowledgement_evidence_fingerprint: FingerprintV1
  },
  lifecycle_at_preparation: "prepared_dormant",
  status: "not_sent",
  statement: "core_prepared_agent_intake_delivery_wiring_only",
  default_enabled: false,
  network_attempted: false,
  delivery_authorized: false,
  delivery_received: false,
  evidence_admission_granted: false,
  execution_admission_granted: false,
  execution_authorized: false,
  worker_allowed: false,
  mutation_allowed: false,
  replay_allowed: false,
  preparation_fingerprint: FingerprintV1
}
```

The embedded `request` is byte-for-byte the closed v0.27
`AgentInstallationIntakeRequestV1`. Core assigns one new `intake_request_id`
and one new `delivery_attempt_id`, copies the exact v0.24 envelope and v0.25/
v0.26 references, asserts the authenticated operator, sets `sent_at` to the
server-owned `prepared_at`, preserves the v0.24 `valid_until` as `expires_at`,
and recomputes the owner/principal-bound v0.27 request fingerprint. In v0.28,
`sent_at` means only the immutable proposed wire timestamp required by the
v0.27 schema; `network_attempted=false` and `status=not_sent` are authoritative.
The embedded v0.27 request retains its exact `delivery_authorized=true` literal
because changing it would change the released wire contract. That literal is
conditional future authorization at the Agent intake boundary; it cannot
override the enclosing v0.28 fixed-disabled configuration or the preparation's
`delivery_authorized=false` and grants no permission to send in v0.28.

The future HTTP request shape is exact and may only be rendered for structural
or injected offline tests:

```text
POST https://{host}:{port}/api/v1/internal/installation-intake
Authorization: Bearer <credential loaded only by a future transport release>
Idempotency-Key: <the permanently reserved preparation key>
Content-Type: application/json
Content-Length: exact bounded byte length
body: canonical AgentInstallationIntakeRequestV1 JSON
```

No Authorization value may be materialized, file-read, logged, persisted, or
passed to a network library in v0.28. No query, cookie, redirect, compression,
chunking, proxy, forwarding header, operator header, multipart body, or other
method is valid. The body remains at most 64 KiB.

## Exact supplied response validation schema

The only accepted response value is the closed v0.27
`AgentInstallationIntakeResultV1`. It is supplied directly to
`validate_response`; v0.28 never retrieves it. Validation returns:

```text
CoreAgentIntakeDeliveryResponseValidationV1 = {
  schema: "core-agent-intake-delivery-response-validation-v1",
  delivery_preparation_id: canonical UUIDv4,
  intake_request_id: canonical UUIDv4,
  delivery_attempt_id: canonical UUIDv4,
  validated_at: UtcSecond,
  outcome: "valid_admission_evidence" | "valid_rejection" | "invalid",
  agent_result: AgentInstallationIntakeResultV1 | null,
  admission_fingerprint: FingerprintV1 | null,
  acknowledgement_fingerprint: FingerprintV1 | null,
  reason_code: null | CoreAgentIntakeDeliveryValidationCodeV1,
  source_was_injected: true,
  production_delivery_observed: false,
  execution_admission_granted: false,
  execution_authorized: false,
  worker_allowed: false,
  mutation_allowed: false,
  replay_allowed: false,
  validation_fingerprint: FingerprintV1
}
```

An admitted result must match the request ID, delivery-attempt ID, operator-
bound v0.20–v0.26 linkage, request fingerprint, envelope ID/fingerprint,
timestamps, fixed principal, status, statement, and every fixed authority
field. Core recomputes the v0.27 admission fingerprint and the deterministic
`AgentInstallationIntakeAcknowledgementV1` projection and acknowledgement
fingerprint. This binds the exact v0.27 admission/acknowledgement contract but
does not claim Core received it over a network or that Agent persisted it.

A valid rejected result is preserved only as its exact closed sanitized code;
it grants nothing. Invalid values return one closed code:
`malformed`, `request_mismatch`, `delivery_attempt_mismatch`,
`ownership_mismatch`, `linkage_mismatch`, `fingerprint_mismatch`,
`freshness_mismatch`, `authority_mismatch`, `replay_conflict`, or
`unavailable`. Invalid raw values are not retained.

## Deterministic fingerprints and exact linkage

All new fingerprints use SHA-256 over the UTF-8 domain string, one NUL byte,
and canonical JSON:

- endpoint: `atlas:dormant-agent-intake-endpoint:v1` over the endpoint value;
- preparation: `atlas:core-agent-intake-delivery-preparation:v1` over
  `{operator_id, preparation}` excluding `preparation_fingerprint`; and
- response validation:
  `atlas:core-agent-intake-delivery-response-validation:v1` over
  `{operator_id, validation}` excluding `validation_fingerprint`.

Credential paths are excluded from endpoint fingerprinting and all evidence;
credential bytes are never fingerprinted. Owner binding, canonical JSON,
closed-schema, duplicate-key, NFC, timestamp, UUID, integer, boolean, and size
rules retain their released meanings.

Core resolves and validates the exact same-owner chain:

- v0.20 candidate-record ID, candidate-envelope fingerprint, v0.19 admission
  fingerprint, and candidate-record fingerprint;
- v0.21 approval-intent ID and fingerprint;
- v0.22 Agent request ID and request, validation, audit-evidence, destination,
  source-plan, and artifact-policy fingerprints;
- v0.23 execution-request ID and fingerprint;
- v0.24 dispatch-envelope ID and fingerprint;
- v0.25 simulation-request ID, intake-record ID and fingerprint, and audit-
  evidence fingerprint;
- v0.26 simulated-delivery ID and fingerprint, delivery-record fingerprint,
  delivery audit-evidence fingerprint, simulated-acknowledgement ID and
  fingerprint, and acknowledgement audit-evidence fingerprint; and
- for supplied response validation only, v0.27 intake-request ID, delivery-
  attempt ID, admission ID/fingerprint, and deterministic acknowledgement
  fingerprint.

No value is reconstructed from a fingerprint, fetched from Agent, accepted
from caller-supplied linkage, or promoted to authority. All v0.20–v0.27
authority fields must retain their released fixed values.

## Ownership, identity, freshness, lifecycle, idempotency, and no replay

The authenticated Core operator must own every Core record. Its canonical
identity is copied into the v0.27 operator assertion and binds the v0.24,
v0.27, preparation, idempotency, and response-validation fingerprints. Owner
identity is never caller-selected in a header or configuration, transferable,
delegable, globally enumerable, or disclosed across partitions. Foreign-owner
access is indistinguishable from absence.

`delivery_preparation_id`, v0.27 `intake_request_id`, v0.27
`delivery_attempt_id`, the idempotency key, v0.20–v0.26 IDs, v0.27 admission
ID, and every fingerprint remain distinct. None is a job, lease, execution
nonce, approval token, capability, credential, retry token, or replay token.

Preparation requires trusted monotonic whole-second UTC time and:

- the v0.24 envelope is `prepared` and `prepared_at <= now < valid_until`;
- `request.sent_at == preparation.prepared_at == now`;
- `request.expires_at == preparation.valid_until == envelope.valid_until`;
- all v0.20–v0.27 dependency timestamps have valid released ordering;
- v0.25 and v0.26 may be expired but must predate `request.sent_at`; and
- no clock rollback, future value, extension, zero-width window, or ambiguous
  ordering exists.

Lifecycle is derived, never caller supplied:

- `disabled`: configuration is the required fixed disabled value;
- `prepared_dormant`: an exact preparation exists and
  `prepared_at <= now < valid_until`;
- `expired`: an exact preparation exists and `now >= valid_until`; terminal;
  and
- `unavailable`: dependencies, time, persistence, or validation are corrupt,
  incomplete, ambiguous, or unavailable.

There is no sending, sent, retrying, delivered, received, admitted, queued,
approved, ready, consuming, executing, installed, failed-install, rolled-back,
cancelled, renewed, or superseded Core lifecycle in v0.28.

Idempotency/no-replay is exact:

- visible-ASCII keys are 1–128 bytes, scoped to authenticated operator and
  `core_agent_intake_delivery:prepare`;
- an append-only store atomically reserves the key, v0.24 envelope ID and
  fingerprint, preparation ID/fingerprint, intake-request ID/fingerprint,
  delivery-attempt ID, and all v0.25/v0.26 references;
- one v0.24 envelope may have at most one v0.28 preparation forever;
- exact retry returns the byte-identical preparation without rereading
  evidence, changing time, rendering credentials, or doing new work;
- changed content under any reserved identity returns `replay_conflict`;
- expiry never releases or permits replacement of a reservation; and
- timeout, incomplete reservation, corruption, or ambiguity returns
  `unavailable` and never permits another preparation or delivery.

Existing v0.27 admission for the envelope makes preparation unavailable except
for exact readback of an already matching reservation. V0.28 must never use a
retry to create a second v0.27 admission or bypass Agent no-replay rules.

## Preparation store, redaction, and audit evidence

P2 may add one independent append-only, operator-scoped Core preparation store
limited to 16 records per operator and 96 KiB canonical bytes per record. It is
restart-durable and fail-closed on corruption. There is no update, runtime
delete, eviction, compaction, repair, migration, expiry task, queue, event,
callback, network outbox, delivery status poll, or authority bridge. Backup v3
is not widened; file handling remains stopped-service operator maintenance.

Evidence may expose only bounded timestamps, lifecycle, `not_sent` status,
fixed statement/authority fields, owned IDs/fingerprints, sanitized resource
class, immutable image digest, artifact kind, and provenance
`core_dormant_agent_intake_delivery_wiring_only`. It redacts operator IDs from
other owners, endpoint host, TLS name, file paths, credential material,
authorization headers, provider payloads, raw destinations, commands,
environment, repository/guest paths, deployment content, HTTP internals,
exceptions, and store paths.

Logs contain correlation ID, owned IDs when safely available, fingerprints,
lifecycle, and one sanitized result code. They never contain bodies, endpoint
configuration, headers, credential paths or bytes. Evidence may say `prepared`
or `validated_injected_response`; it may not say `sent`, `delivered`,
`received_from_agent`, `execution_admitted`, `queued`, `executed`, `installed`,
`deployed`, `rolled_back`, or `completed`.

## API, command, UI, settings, and production wiring boundaries

V0.28 adds no Core or Agent HTTP/OpenAPI route, CLI/shell command, RPC, socket,
event, queue, worker message, workflow node, callback, listener, scheduler,
startup task, application/container registration, production credential,
setting, environment variable, secret mount, deployment manifest, health
probe, Mission Control type/client/hook/page/component/navigation/control, or
readback surface.

The v0.27 Agent route factory remains isolated and test-only. The v0.28 Core
factory remains isolated and explicitly constructed in tests. Production Core
must not import it from `main`, API routers, containers, settings, workflows,
workers, candidate execution, operational dispatch, providers, repositories,
or UI-facing services. No production code may provide an injected response to
`validate_response` or consume its evidence.

## P0–P5 scope

### P0 — Dormant wiring and threat-model freeze — selected

Freeze the exact client/factory, configuration, request/preparation, supplied-
response validation, fingerprint/linkage, ownership/identity, freshness,
lifecycle, idempotency/no-replay, redaction/audit, no-surface, authority,
golden, and must-not-change contracts. Change planning documentation only.

### P1 — Closed models and pure validation — implemented

Implement isolated immutable Core models, strict duplicate/unknown rejection,
canonical fingerprints, exact v0.20–v0.27 linkage validation, lifecycle
derivation, and hostile-input bounds. Perform no I/O or registration.

### P2 — Dormant preparation service and bounded store — implemented

Implement the explicitly constructed preparation service over injected owned
evidence readers, trusted clock, ID factory, and append-only store. It may
assemble and preserve one `not_sent` request only. Add no client transport,
credential read, Agent call, route, command, worker, workflow, or consumer.

### P3 — Explicit no-send client factory — implemented

Implement the isolated factory and client with only `prepare`, direct owned
readback, and pure supplied-response validation. Validate the closed endpoint
and authentication configuration shape without reading files, resolving DNS,
creating TLS state, rendering Authorization, importing a network library, or
exposing any send-capable method. Keep production construction absent.

### P4 — Offline structural goldens — implemented

Exercise synthetic same-owner v0.20–v0.27 values and the exact proposed HTTP
shape without opening a socket or invoking the Agent application. Validate an
injected byte-exact admitted result and closed rejection values. Lock Mission
Control absence and Home Assistant as a blocked/rejected golden only.

### P5 — Isolation, no-replay, and release closure — complete

Prove exact linkage, endpoint/auth shape, freshness/lifecycle, concurrency,
restart/timeout ambiguity, ownership, quotas, corruption, redaction, one-
preparation no-replay, zero send method, zero production construction, zero
Agent registration, zero Core/Agent network path, capability parity, prior
goldens, and full regressions. Do not migrate, tag, push, publish, deploy, or
release automatically.

P1–P5 preserve this frozen contract without widening authority. Release
closure proves the client remains explicitly constructed and fixed-disabled,
the store remains append-only evidence rather than an outbox, no credential or
network capability exists, production Core and Agent remain disconnected, the
Agent route remains test-only, Mission Control has no surface, and Home
Assistant remains blocked without a deployment artifact.

## Exact authority boundary

When explicitly constructed, Core may validate the disabled endpoint and
authentication configuration shape, resolve exact owned v0.20–v0.27 evidence,
assemble and preserve one immutable `not_sent` v0.27 request, render a redacted
future HTTP shape, and validate a directly injected closed Agent result. These
are the only new powers contemplated by v0.28.

Core may not read credentials, resolve or connect to Agent, open a socket,
perform DNS/TLS/HTTP, send/retry/reconcile a request, claim network delivery or
receipt, call the Agent application in-process, register a production client,
or expose delivery through an API, command, UI, workflow, worker, event, queue,
or startup path. Agent may not register its route or accept production traffic.

Neither side may authorize or consume execution, create work, invoke Docker,
Podman, Compose, containerd or another runtime, execute shell/process commands,
read or mutate a provider/repository/guest, acquire an image, start a workflow
or worker, install, deploy, roll back, or mutate a target. Preparation-store
writes are the only allowed mutation and are evidence-only.

## Must-not-change contracts

- V0.20–v0.27 schemas, fingerprints, stores, routes, ownership, freshness,
  lifecycle, idempotency/no-replay, redaction, goldens, and meanings remain
  exact. V0.28 references them without migration or trust promotion.
- V0.20 remains non-executable; v0.21 remains an approval statement; v0.22
  remains validation-only; v0.23 remains record-only; v0.24 remains handoff-
  only; v0.25 remains simulation; v0.26 remains simulated delivery; and v0.27
  remains evidence-only intake admission, not execution admission.
- The v0.27 Agent route factory remains unregistered, test-only, and impossible
  to enable through production settings. Its method, path, request, response,
  authentication, bounds, and redaction contracts remain exact.
- Existing candidate approvals, repository workflow, operational dispatch,
  Provider Intent, execution audit, worker, and interrupted-side-effect no-
  replay contracts consume no v0.28 evidence.
- Agent executable support remains `update-compose-stack` for repository work
  and `restart-service/proxmox/qemu` for operational work. `install-container`
  remains absent from executable capability and intent registries.
- Discovery remains GET-only; Provider Intent remains Proxmox QEMU
  `monitoring-policy`; the optional worker remains default-disabled; backup and
  restore remain explicit operator maintenance.
- No production transport/client registration, credential/CA provisioning,
  network/DNS/TLS/HTTP call, Agent invocation, runtime/process call, provider/
  repository/guest access or mutation, workflow/worker execution, installation,
  deployment, rollback, background work, API/command/UI, migration, tag, push,
  publication, or release is added by v0.28.

## Threats and golden cases

The threat model covers endpoint/credential injection, SSRF, DNS rebinding,
cleartext/public/proxied ingress, redirect/proxy leakage, credential file or
header logging, cross-owner substitution, changed upstream IDs/fingerprints,
stale/future requests, duplicate or unknown fields, oversized bodies, forged
Agent results, mismatched admission/acknowledgement, response validation being
presented as observed delivery, retry after timeout/expiry, partial persistence,
corruption/quota fail-open behavior, production factory construction, a hidden
send method, Agent route registration drift, and later consumers treating
preparation or admission evidence as execution authority.

The positive golden uses synthetic same-owner v0.20–v0.27 values. One fresh
create produces one `not_sent` preparation with every delivery/execution/
mutation field false. Exact retry returns byte-identical evidence. A directly
injected matching v0.27 admitted result validates its admission and derived
acknowledgement fingerprints while retaining
`production_delivery_observed=false`. Changed owner, identity, fingerprint,
linkage, time, endpoint, result, authority field, idempotency content, or
unknown key fails closed without network or work.

Home Assistant remains blocked before v0.20 because no deployment artifact
exists and its realistic workload remains outside the v0.22 policy. It may
appear only as a rejected/golden fixture; v0.28 adds no artifact or exception.

## What v0.28 enables later and what remains blocked

V0.28 enables a later release to review a separately implemented HTTPS
transport against a stable client boundary; provision and mount a dedicated CA
and Core credential; register the already reviewed Agent route; atomically
send one exact owner-bound request; and preserve authenticated response evidence
without redesigning linkage, freshness, ownership, or no-replay rules.

Still blocked are production Core client construction, credential and TLS
rollout, DNS/network/HTTP activity, Agent route registration, live delivery,
receipt reconciliation, production response preservation/readback, execution
approval and atomic consumption, execution-time target/image proof, runtime or
worker authority, Docker/Podman/process use, provider/repository/in-guest access
or mutation, workflow start, image acquisition, installation, deployment,
rollback, side-effect recovery/audit, Mission Control delivery controls, and
Home Assistant installation.
