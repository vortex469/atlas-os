# Agent Intake Simulation v1 planning contract

Status: **Atlas v0.25 P0–P5 complete**.

This document freezes the narrowest simulation-only Agent intake boundary that
can bind the released v0.20 durable installation candidate, v0.21 approval
intent, v0.22 Agent install-container validation evidence, v0.23 installation
execution request, and v0.24 installation dispatch handoff. It permits a later
Atlas v0.25 phase to parse, validate, and preserve evidence that an explicitly
injected handoff would satisfy the simulation contract. It does not receive a
live Core delivery, admit execution, consume execution authority, or perform
work.

The authority equation for every v0.25 phase is:

`simulated intake != delivery receipt != live Agent admission != execution`.

## Repository inspection baseline

Planning starts from current `main` at `e6265a7`, after released tag
`atlas-v0.24.0` at `a15ab39`. V0.24 provides one immutable, operator-owned,
60-second-maximum, non-delivered dispatch envelope and a contract-only Agent
parser/admission vocabulary. It explicitly leaves trusted transport, durable
receipt, atomic live consumption, execution approval, and runtime behavior
blocked.

V0.25 does not widen the existing repository workflow, operational dispatch,
Provider Intent, execution worker, Core-to-Agent client, or Agent execution
surfaces. None may import or consume this simulation contract.

## Exact simulation input and durable record

The prospective in-process simulation boundary receives an authenticated
operator identity, a visible-ASCII idempotency key, and exactly this closed
value:

```text
AgentInstallationIntakeSimulationCreateV1 = {
  schema: "agent-installation-intake-simulation-create-v1",
  simulation_request_id: canonical UUIDv4,
  envelope: InstallationDispatchEnvelopeV1
}
```

`InstallationDispatchEnvelopeV1` is the exact released v0.24 value, without
extension, projection, or reconstruction. The caller cannot submit an owner
field, receive time, lifecycle, status, reason, delivery attempt, endpoint,
credential, command, desired state, authority override, or execution token.
The authenticated canonical `operator_id` is an out-of-band service argument
and mandatory store partition; it is never accepted from the JSON value.

A successful simulation may atomically append only this closed record:

```text
AgentInstallationIntakeSimulationV1 = {
  schema: "agent-installation-intake-simulation-v1",
  intake_record_id: canonical UUIDv4,
  simulation_request_id: canonical UUIDv4,
  observed_at: UtcSecond,
  valid_until: UtcSecond,
  operation: "install-container",
  mode: "simulation-only",
  source: {
    dispatch_envelope_id: canonical UUIDv4,
    dispatch_envelope_fingerprint: FingerprintV1
  },
  linkage: InstallationDispatchLinkageV1,
  status: "simulated_valid",
  reason_codes: [],
  statement: "agent_validated_injected_handoff_without_admission",
  delivery_received: false,
  live_admission_granted: false,
  execution_authorized: false,
  worker_allowed: false,
  mutation_allowed: false,
  replay_allowed: false,
  intake_record_fingerprint: FingerprintV1
}
```

`InstallationDispatchLinkageV1`, `FingerprintV1`, UUID, timestamp, string,
canonical JSON, duplicate-key, and unknown-field rules remain exactly those
released in v0.24. The create value is at most 40 KiB canonical bytes and the
durable record at most 32 KiB. The record contains no complete candidate,
approval, v0.22 request or evidence, execution-request body, deployment
artifact, provider payload, destination raw identity, address, path, image
credential, token, environment, command, runtime output, arbitrary metadata,
workflow/job identity, delivery nonce, retry token, or replay token.

The record fingerprint is SHA-256 over UTF-8
`"atlas:agent-installation-intake-simulation:v1"`, one NUL byte, and canonical
JSON of `{operator_id, record}` excluding `intake_record_fingerprint`. The
operator binding is therefore mandatory even though it is not publicly
projected.

Rejected input creates no durable intake record. It returns only one sanitized
code from the closed vocabulary `malformed`, `not_current`,
`ownership_mismatch`, `envelope_mismatch`, `linkage_mismatch`,
`recipient_mismatch`, `replay_conflict`, `quota_exceeded`, or `unavailable`.
There is no partially valid record and no caller-visible failed snapshot.

## Exact fingerprints, linkage, and validation

At the trusted injected `observed_at`, simulation must require and preserve all
of these exact identities from the v0.24 envelope:

- v0.20 `candidate_record_id`, candidate-envelope fingerprint, v0.19
  admission fingerprint, and candidate-record fingerprint;
- v0.21 `approval_intent_id` and approval-intent fingerprint;
- v0.22 `agent_request_id`, request fingerprint, validation fingerprint,
  audit-evidence fingerprint, destination fingerprint, source-plan
  fingerprint, and artifact-policy fingerprint;
- v0.23 `execution_request_id` and execution-request fingerprint; and
- v0.24 `dispatch_envelope_id` and dispatch-envelope fingerprint.

The Agent validates the complete closed v0.24 envelope, recomputes its
owner-bound fingerprint using the authenticated operator identity, requires
the exact `install-container`/`handoff-only`/`atlas-agent`/
`agent-installation-dispatch-intake-v1` tuple, requires all five v0.24
authority fields false, and requires every linkage member above to be present
and well formed. It copies the linkage byte-for-byte into the simulation
record.

This is transitive binding, not independent provenance verification. V0.25
does not contact Core or reopen the v0.20–v0.23 stores, reconstruct raw v0.22
evidence, inspect a repository, re-resolve a destination, verify an image, or
claim that the injected envelope was authentically delivered. A structurally
valid fingerprint proves equality under the frozen canonical contract; it is
not a signature, credential, approval, receipt, or capability.

## Ownership and request identity

Exactly one authenticated operator owns the entire simulated record. The
operator identity used to validate the v0.24 fingerprint, partition the Agent
store, enforce reads, calculate the v0.25 fingerprint, and scope idempotency
must be identical. It cannot be delegated, transferred, supplied in content,
inferred from an envelope field, or replaced by global enumeration. Foreign-
operator create or lookup is indistinguishable from absence.

`simulation_request_id` identifies only one operator's request to perform this
offline simulation. It is not the v0.22 Agent request ID, v0.23 execution
request ID, v0.24 dispatch envelope ID, a delivery attempt, a receipt, a job,
an execution approval, or a live-intake nonce. IDs from different layers may
not be substituted or collapsed.

## Lifecycle, freshness, idempotency, and no replay

Lifecycle is derived during reads and never stored:

- `simulated`: `observed_at <= now < valid_until`; and
- `expired`: `now >= valid_until`.

Both states are non-delivered, non-admitted, non-executable, and
non-authorizing. `expired` is terminal. No renew, refresh, resimulate,
supersede, update, delete, cancel, consume, send, retry, admit, execute, or
status-transition operation exists. Expiry performs no write, callback,
event, queueing, cleanup, probe, or background work.

Creation requires a trusted whole-second UTC clock,
`envelope.prepared_at <= observed_at < envelope.valid_until`, and no future
source timestamp. `valid_until` is exactly
`min(envelope.valid_until, observed_at + 30 seconds)`. Zero-width validity,
clock rollback, unavailable trusted time, an already expired envelope, or any
timestamp ambiguity fails closed. Simulation never extends an upstream
deadline.

Idempotency/no-replay is exact:

- visible-ASCII idempotency keys are 1–128 bytes and scoped to operator plus
  the simulation-create operation;
- exact retry returns the original record without revalidation, time
  extension, logging a second acceptance, or work;
- the append atomically reserves the operator-scoped idempotency key,
  `simulation_request_id`, v0.24 dispatch-envelope ID and fingerprint, and
  v0.25 intake-record fingerprint;
- one v0.24 envelope can create at most one simulation record forever,
  including after expiry, restart, timeout, lost response, or source removal;
- reuse of any reserved identity with different content fails closed; and
- ambiguous append completion or missing durable reservation evidence returns
  unavailable and is never retried as new work.

These reservations exist only in the simulation namespace. They are not live
delivery consumption and grant no later redelivery or execution right. A
future live-intake release must define an independent authenticated delivery-
attempt identity and atomic single-use consume barrier; it may not interpret a
v0.25 reservation or exact retry as delivery authority.

## Store, redaction, and audit evidence

P3 may add one independent append-only, operator-scoped Agent simulation store
with atomic creation, restart durability, and complete-record validation. It
is bounded to 16 retained records per operator and 32 KiB canonical bytes per
record. There is no eviction, compaction, update, runtime delete, repair,
migration, expiry task, queue, event, callback, or bridge to existing approval
or execution audit stores. Backup v3 is not widened; file-level retention,
copy, restore, or removal is explicit operator maintenance while Agent is
stopped. Older releases ignore and cannot consume the store.

The v0.25 record is audit evidence only of local validation of explicitly
injected bytes. Projections may expose only owned IDs, bounded timestamps,
derived lifecycle, fixed statement/status/authority fields, exact
fingerprints, sanitized `proxmox/qemu/existing-guest` resource identity,
immutable image digest, artifact kind, and provenance
`agent_simulated_not_received`. They redact other operators, provider payload,
raw destination identity, addresses, credentials, tokens, environment,
commands, repository or guest paths, raw v0.22 content, deployment content,
and exception serialization.

Logs contain only correlation ID, owned simulation/intake/envelope IDs when
available, fingerprints, lifecycle, and one closed outcome code. Neither a
record nor a log may claim network receipt, authentication of Core, admission,
dispatch, execution, mutation, or completion.

## Default-disabled API, command, and UI boundaries

V0.25 adds no HTTP route, listener, Core client call, RPC registration, CLI or
shell command, worker message, Mission Control API call, control, or
navigation. The only allowed future v0.25 entry is an explicitly constructed
in-process simulation service called by tests or a bounded offline golden
harness with injected operator identity, clock, envelope, and store. It must
not be registered in the production Agent application container or selected
by configuration/environment drift.

Readback is likewise an in-process owned store operation only. There is no
public list/get endpoint and no UI. Any later API, command, or UI requires a
new planning decision with authentication, CSRF/origin where applicable,
rate/body bounds, operator mapping, redaction, and method-isolation tests. It
must not silently expose the v0.25 service.

The capability diagnostic continues to report `install-container` as
unsupported and default-disabled. No switch can enable live intake or
execution because no transport, consumer, worker, runtime, or execution
adapter may exist in this release.

## P0–P5 scope and acceptance

### P0 — Simulation contract and threat model — selected

Freeze this exact schema, five-release linkage, authority boundary, ownership,
request identity, freshness, lifecycle, idempotency/no-replay, redaction,
audit evidence, default-disabled posture, interface absence, goldens, and
must-not-change contracts. P0 changes planning documentation only.

### P1 — Closed models and canonical fingerprints — complete

Implement isolated immutable input/record/error models, strict parsing,
canonical fingerprints, lifecycle derivation, and boundary/hostile-input
tests. Perform no I/O, registration, persistence, network, filesystem, or
runtime action.

### P2 — Pure injected simulation validation — complete

Implement deterministic validation over injected operator identity, trusted
time, and complete v0.24 envelope. Prove exact transitive linkage, recipient,
authority, expiry, and sanitized failure behavior. Do not call Core, Agent
routes, repositories, providers, guests, registries, or runtimes.

### P3 — Bounded simulation evidence store and no-surface lock — complete

Implement only the isolated append-only Agent store, atomic reservations,
idempotency, quotas, restart durability, owned reads, and fail-closed
corruption/ambiguity behavior. Add no production container registration,
route, command, UI, event, queue, audit bridge, or consumer.

P3 release-hardening locks the latter absence structurally: the production
Agent OpenAPI, application container, settings, and command entrypoints expose
no simulation intake; no production module consumes or registers the package;
and the isolated package imports no Core client, network, runtime, process,
provider, repository, worker, workflow, or route dependency. Filesystem access
is confined to the explicitly constructed evidence store. Readback remains an
owner-scoped in-process store operation only.

### P4 — Offline golden harness and evidence review — complete

Exercise the in-process service using synthetic fixtures and render a bounded
text/structured evidence projection for tests. The harness accepts injected
values only and cannot invoke shell/process, Docker/Podman, network, provider,
repository, guest, workflow, worker, deployment, or rollback behavior.

The frozen no-UI decision takes precedence at the Mission Control boundary:
the structured projection remains test-harness evidence only. P4 adds no UI
presentation, API client, hook, type, route, navigation, or control. Structural
Mission Control and cross-service tests lock that absence, prohibit v0.25
mutation calls and action navigation, and prove that no simulation evidence or
sensitive intake detail can be rendered. Home Assistant remains blocked by the
absent deployment artifact and is non-installable and non-executable.

### P5 — Isolation, no-replay, and release closure — complete

Prove lifecycle boundaries, one-simulation-per-envelope behavior,
concurrency/restart/timeout ambiguity, quotas, corruption, ownership,
redaction, zero route/command/UI/consumer registration, default-disabled
capability parity, v0.20–v0.24 contract goldens, Home Assistant blocked golden,
and full regression gates. P5 does not migrate, tag, push, publish, deploy, or
release automatically.

Release-isolation tests scan Core and Agent production modules and permit the
v0.25 vocabulary only inside the isolated Agent package. They lock out live
Core-to-Agent delivery, HTTP/OpenAPI, CLI/shell commands, production container
registration, settings enablement, worker/workflow/runtime adapters,
provider/repository/guest mutation, candidate execution, deployment,
rollback, and replay bypass. Readback is limited to direct operator-owned
`get` and lifecycle calls on the in-process store. Mission Control structural
tests lock out every v0.25 API client, mutation, route, navigation, control,
action label, and evidence rendering path. `install-container` remains
unsupported and Home Assistant remains blocked with no deployment artifact.

## Exact authority boundary

V0.25 may later answer only: **Would these explicitly injected bytes, under
this injected operator identity and trusted time, satisfy the frozen Agent
simulation contract, and has that simulation already been recorded?**

It may parse, recompute fingerprints, compare exact identities, apply
freshness rules, reserve simulation-only identities, append immutable
simulation evidence, and read that evidence through an in-process owner
boundary. It cannot establish authentic Core origin, acknowledge delivery,
grant admission, approve execution, consume a live attempt, create work, or
cause any external or mutable system effect.

## Must-not-change contracts for P0–P5

- V0.16–v0.24 schemas, fingerprints, routes, stores, ownership, lifecycle,
  freshness, idempotency, goldens, and meanings remain exact. Upstream
  packages do not import v0.25 or gain fields or consumers.
- V0.20 remains non-executable; v0.21 remains historical approval-intent
  evidence; v0.22 remains validation-only and unsupported; v0.23 remains a
  record only; v0.24 remains prepared but not delivered. V0.25 mutates none.
- Existing ExecutionCandidate, approval, workflow, operational dispatch,
  repository execution, worker, execution audit, Provider Intent, and
  interrupted-side-effect no-replay contracts remain unchanged and do not
  consume v0.25 data.
- Agent repository support remains exactly `update-compose-stack`; operational
  support remains exactly `restart-service/proxmox/qemu`; `install-container`
  remains unsupported and absent from executable intent/capability sets.
- Discovery remains GET-only; Provider Intent remains Proxmox QEMU
  `monitoring-policy`; the optional execution worker remains default-disabled;
  backup/restore remains explicit operator maintenance.
- No live Core-to-Agent call, network intake, HTTP/RPC/CLI surface, Docker,
  Podman, shell or process execution, image acquisition, provider mutation,
  repository read or mutation, in-guest read or mutation, workflow start,
  worker execution, installation, deployment, rollback, background work,
  authority event, migration, tag, push, publication, or release is added.

## Threats and golden cases

The threat model covers forged or cross-operator envelopes, confused request
identities, fingerprint omission/substitution, malformed or stale envelopes,
recipient changes, authority-bit changes, simulation being presented as live
receipt, simulation reservation being reused as consumption authority, replay
after expiry or ambiguous persistence, parser/config drift exposing production
intake, quota/corruption fail-open behavior, and secret or exception leakage.

The positive golden is synthetic: one exact same-owner v0.20–v0.24 chain,
injected before the envelope deadline, produces one `simulated` record with
all six v0.25 authority fields false and provenance
`agent_simulated_not_received`. Exact retry returns the same record without
work. Any changed operator, request/envelope ID, fingerprint, linkage,
recipient, timestamp, authority field, or unknown field fails closed and
creates no record.

Home Assistant remains a blocked golden. It cannot reach v0.20 because the
required deployment artifact is absent, and its realistic workload remains
outside the v0.22 single-container/no-network policy. No Home Assistant
deployment artifact or exception is introduced.

## What v0.25 enables later and what remains blocked

V0.25 enables a later release to reuse a tested Agent-side closed parser,
owner-bound five-release linkage validator, short freshness window,
simulation-only identity reservations, sanitized evidence record, and
no-replay test corpus when designing a real authenticated intake boundary.

Still blocked are mutual Core/Agent authentication and authorization, a live
transport and endpoint, delivery attempts and receipts, durable live
acceptance, atomic consumption/no-redelivery, independent fresh execution
approval, execution-time destination and image proof, worker/runtime behavior,
Docker/Podman/shell/process use, provider/repository/in-guest mutation,
workflow start, interruption recovery, side-effect audit, image acquisition,
installation, deployment, rollback, and Home Assistant installation.
