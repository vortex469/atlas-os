# Simulated Handoff Delivery v1 planning contract

Status: **Atlas v0.26 P0–P5 complete**.

This document freezes the narrowest simulated Core-to-Agent delivery boundary
that binds the released v0.20 durable installation candidate, v0.21 approval
intent, v0.22 Agent install-container validation evidence, v0.23 installation
execution request, v0.24 installation dispatch handoff envelope, and v0.25
Agent intake simulation record. A later v0.26 phase may explicitly construct an
in-process coordinator that passes a closed simulation value to the existing
v0.25 simulation service and preserves a closed acknowledgement. It is not a
network transport, live receipt, admission, execution, or mutation boundary.

The authority equation for every v0.26 phase is:

`simulated delivery + simulated acknowledgement != live delivery != Agent admission != execution`.

## Repository inspection baseline

Planning starts from current `main` at `421658c`, after released tag
`atlas-v0.25.0` at `d4d7424`. V0.24 supplies a prepared, non-delivered,
owner-bound handoff envelope with a 60-second maximum lifetime. V0.25 supplies
an explicitly constructed, default-disabled Agent service that validates
injected v0.24 bytes and preserves one simulation record; it has no production
route, command, Core client, transport, container registration, or execution
consumer.

V0.26 does not widen repository execution, operational dispatch, Provider
Intent, workflow, worker, approval, audit, Core HTTP, Agent HTTP, or runtime
surfaces. Production modules may not import or construct the coordinator.

## Exact simulated delivery schemas

The prospective coordinator receives an authenticated canonical `operator_id`,
a visible-ASCII idempotency key, a trusted whole-second UTC clock, and exactly
this closed Core value:

```text
InstallationHandoffSimulatedDeliveryV1 = {
  schema: "installation-handoff-simulated-delivery-v1",
  simulated_delivery_id: canonical UUIDv4,
  simulation_request_id: canonical UUIDv4,
  dispatched_at: UtcSecond,
  valid_until: UtcSecond,
  operation: "install-container",
  mode: "simulation-only",
  sender: "atlas-core",
  recipient: {
    service: "atlas-agent",
    intake_contract: "agent-installation-intake-simulation-v1"
  },
  envelope: InstallationDispatchEnvelopeV1,
  delivery_authorized: false,
  live_admission_authorized: false,
  execution_authorized: false,
  worker_allowed: false,
  mutation_allowed: false,
  replay_allowed: false,
  simulated_delivery_fingerprint: FingerprintV1
}
```

`InstallationDispatchEnvelopeV1` is the complete exact released v0.24 value,
not a projection or reconstruction. `simulation_request_id` becomes the exact
v0.25 create identity. `dispatched_at` is coordinator-owned and `valid_until`
is exactly the embedded envelope's `valid_until`; v0.26 cannot extend it.

The delivery fingerprint is SHA-256 over UTF-8
`"atlas:installation-handoff-simulated-delivery:v1"`, one NUL byte, and
canonical JSON of `{operator_id, delivery}` excluding
`simulated_delivery_fingerprint`. The canonical value is at most 48 KiB.

Core may preserve only this closed evidence record after successful validation
and before invoking the injected Agent port:

```text
InstallationHandoffSimulatedDeliveryRecordV1 = {
  schema: "installation-handoff-simulated-delivery-record-v1",
  simulated_delivery_id: canonical UUIDv4,
  simulation_request_id: canonical UUIDv4,
  dispatch_envelope_id: canonical UUIDv4,
  dispatch_envelope_fingerprint: FingerprintV1,
  simulated_delivery_fingerprint: FingerprintV1,
  dispatched_at: UtcSecond,
  valid_until: UtcSecond,
  lifecycle_basis: "simulation_attempt_recorded",
  delivery_mode: "in_process_simulation",
  live_delivery_claimed: false,
  agent_admission_claimed: false,
  execution_authorized: false,
  mutation_authorized: false,
  replay_allowed: false,
  delivery_record_fingerprint: FingerprintV1
}
```

Its fingerprint uses domain
`"atlas:installation-handoff-simulated-delivery-record:v1"` and the same
owner-bound canonical procedure. It contains no acknowledgement fields and is
never updated. An attempt record proves only that the coordinator durably
reserved the simulation identity; it does not prove Agent invocation or
acceptance.

## Exact Agent simulated acknowledgement schema

The Agent adapter derives the exact released v0.25 create value
`{schema: "agent-installation-intake-simulation-create-v1",
simulation_request_id, envelope}` from the delivery value. It supplies the
same authenticated operator and trusted time to the existing v0.25 simulation
path. Its v0.25 idempotency key is exactly the 69-character visible-ASCII value
`"v026:" + simulated_delivery_fingerprint.value`; callers cannot
choose or replace it. A successful v0.25 result may produce only:

```text
AgentInstallationHandoffSimulatedAcknowledgementV1 = {
  schema: "agent-installation-handoff-simulated-acknowledgement-v1",
  acknowledgement_id: canonical UUIDv4,
  acknowledged_at: UtcSecond,
  valid_until: UtcSecond,
  status: "simulated_acknowledged",
  provenance: "agent_simulated_not_received",
  source: {
    simulated_delivery_id: canonical UUIDv4,
    simulated_delivery_fingerprint: FingerprintV1,
    dispatch_envelope_id: canonical UUIDv4,
    dispatch_envelope_fingerprint: FingerprintV1
  },
  intake: {
    simulation_request_id: canonical UUIDv4,
    intake_record_id: canonical UUIDv4,
    intake_record_fingerprint: FingerprintV1
  },
  statement: "agent_acknowledged_simulated_handoff_without_live_receipt",
  delivery_received: false,
  live_admission_granted: false,
  execution_authorized: false,
  worker_allowed: false,
  mutation_allowed: false,
  replay_allowed: false,
  acknowledgement_fingerprint: FingerprintV1
}
```

`acknowledged_at` is exactly the v0.25 record's `observed_at`, and
`valid_until` is exactly that record's `valid_until`. The acknowledgement
fingerprint uses domain
`"atlas:agent-installation-handoff-simulated-acknowledgement:v1"`, one NUL
byte, and canonical JSON of `{operator_id, acknowledgement}` excluding
`acknowledgement_fingerprint`. Its canonical size is at most 16 KiB.

Agent may append the acknowledgement to a new independent operator-scoped
simulation evidence store only after the v0.25 record is durably present and
fully validated. Core may then append an exact byte-for-byte copy to a new
independent operator-scoped acknowledgement-evidence store. Neither copy is a
receipt of live transport. Neither store may update the delivery-attempt
record or any v0.20–v0.25 record.

All schemas are closed and reject duplicate/unknown keys. Strings are NFC,
timestamps are UTC whole seconds, UUIDs are canonical lowercase UUIDv4, and
`FingerprintV1` and canonical JSON retain their released definitions.

Rejected delivery creates no acknowledgement. Failures expose only one of
`malformed`, `not_current`, `ownership_mismatch`, `delivery_mismatch`,
`envelope_mismatch`, `linkage_mismatch`, `recipient_mismatch`,
`intake_mismatch`, `replay_conflict`, `quota_exceeded`, or `unavailable`.

## Required fingerprints and six-release linkage

Before attempt preservation, Core recomputes the v0.26 delivery fingerprint
and the complete owner-bound v0.24 envelope fingerprint. It requires the exact
v0.24 operation, mode, recipient, statement, false authority fields, and every
released linkage member:

- v0.20 candidate record ID, candidate-envelope fingerprint, v0.19 admission
  fingerprint, and candidate-record fingerprint;
- v0.21 approval-intent ID and fingerprint;
- v0.22 Agent request, Agent validation, Agent audit-evidence, destination,
  source-plan, and artifact-policy fingerprints;
- v0.23 execution-request ID and fingerprint; and
- v0.24 dispatch-envelope ID and fingerprint.

Agent then applies the exact v0.25 validation and requires its result to bind
the same operator, `simulation_request_id`, v0.24 ID/fingerprint, complete
linkage, `intake_record_id`, and v0.25 intake-record fingerprint. It derives
the acknowledgement only from that complete durable v0.25 record plus the
complete v0.26 delivery. Core validates the complete acknowledgement and all
cross-links before preserving its copy.

This is transitive equality binding. V0.26 does not reopen or mutate upstream
stores, reconstruct raw v0.22 evidence, authenticate a remote peer, inspect a
target or repository, verify an image, or promote a fingerprint to a
signature, credential, approval, receipt, capability, or execution proof.

## Ownership and request identity

One authenticated operator must own the v0.20–v0.25 chain, delivery value,
both evidence stores, and acknowledgement. The same canonical `operator_id`
partitions every operation and fingerprint calculation. It is out-of-band,
never accepted in content, never projected, and cannot be delegated,
transferred, inferred, or replaced by administrator/global enumeration.
Foreign-owner access is indistinguishable from absence.

The idempotency key, `simulated_delivery_id`, `simulation_request_id`, v0.24
`dispatch_envelope_id`, v0.25 `intake_record_id`, and v0.26
`acknowledgement_id` are distinct identities and may never be substituted or
collapsed. None is a live delivery attempt, network request, admission, job,
execution approval, lease, nonce, retry token, or replay token.

## Lifecycle, expiry, idempotency, and no replay

Core derives one of these delivery lifecycles without storing it:

- `pending_acknowledgement`: a valid attempt record exists and no valid
  acknowledgement copy is present while `now < valid_until`;
- `simulated_acknowledged`: both exact records exist and `now < valid_until`;
- `expired_unacknowledged`: no acknowledgement exists at `now >= valid_until`;
  terminal; or
- `expired_acknowledged`: an exact acknowledgement exists at
  `now >= valid_until`; terminal.

Agent derives `simulated_acknowledged` or terminal `expired_acknowledged` for
its acknowledgement evidence. Every state remains non-live, non-admitted,
non-executable, and non-authorizing. Expiry performs no write, cleanup, event,
callback, retry, or background work.

Creation requires `envelope.prepared_at <= dispatched_at <= acknowledged_at <
envelope.valid_until`, no future timestamp, and trusted monotonic
whole-second UTC observations. V0.25 independently applies its exact freshness
contract, including `acknowledged_at == intake.observed_at` and
`ack.valid_until == intake.valid_until == min(envelope.valid_until,
acknowledged_at + 30 seconds)`. Zero-width windows, clock rollback, unavailable
time, expiry, or ambiguity fail closed. No layer renews or extends another.

Idempotency and no-replay are exact:

- keys are visible ASCII, 1–128 bytes, scoped to operator plus the v0.26
  simulated-delivery operation;
- the derived v0.25 key is fixed by the delivery fingerprint as specified
  above and is distinct from the caller's v0.26 key;
- one v0.24 envelope may have at most one v0.26 delivery identity, the same
  `simulation_request_id` must drive its sole v0.25 simulation record, and one
  delivery may have at most one acknowledgement forever;
- the Core attempt append atomically reserves the key, delivery ID and
  fingerprint, simulation request ID, and v0.24 ID and fingerprint;
- the Agent acknowledgement append atomically reserves the delivery ID and
  fingerprint, acknowledgement ID and fingerprint, and all v0.25 intake
  identities and fingerprints;
- the Core acknowledgement-copy append accepts only the exact Agent value and
  reserves the same acknowledgement identity and fingerprint;
- an exact retry reuses the attempt, invokes only the injected idempotent v0.25
  path when acknowledgement evidence is absent and still fresh, and otherwise
  returns the original acknowledgement without time extension or new work;
- changed content under any reserved identity fails with `replay_conflict`;
  expiry never releases a reservation; and
- ambiguous persistence or incomplete reservation evidence returns
  `unavailable`. No new identity is minted and no live-delivery inference is
  allowed.

Recovery is evidence reconciliation only. If Agent has the exact durable
acknowledgement but Core lacks its copy, Core may validate and append that
exact copy during an exact retry. It may not ask Agent to resimulate after
expiry, replace an acknowledgement, or treat an absent acknowledgement as
permission to deliver elsewhere.

## Stores, redaction, and audit evidence

P2 may add one bounded append-only Core attempt store and one Core
acknowledgement-copy store. P3 may add one bounded append-only Agent
acknowledgement store while reusing, not changing, the v0.25 store/service.
Each store is operator-scoped, atomically reserved, restart-durable, limited to
16 records per operator and the schema byte bound, and fail-closed on
corruption. There is no update, runtime delete, eviction, repair, migration,
queue, event, audit bridge, or expiry task. Backup v3 is not widened; file
handling remains explicit stopped-service operator maintenance.

Projections may expose only owned IDs, bounded timestamps, derived lifecycle,
fixed status/statements/authority fields, exact fingerprints, sanitized
`proxmox/qemu/existing-guest` resource identity, immutable image digest,
artifact kind, and simulation provenance. They redact operator IDs, provider
payloads, raw destination identities, addresses, credentials, tokens,
environment, commands, repository/guest paths, raw v0.22 content, deployment
content, exception serialization, and internal store paths.

Logs contain only correlation ID, owned v0.24–v0.26 IDs when available,
fingerprints, lifecycle, and one closed outcome code. Evidence and logs must
say `simulated`, never `sent`, `received`, `accepted`, `admitted`, `executed`,
`installed`, or `completed` without the simulation qualifier.

## Default-disabled API, command, and UI boundaries

V0.26 adds no production HTTP/RPC route, listener, Core-to-Agent network
client, CLI/shell command, worker message, application-container registration,
settings/environment enablement, Mission Control API call, page, control, or
navigation. The only permitted entry is an explicitly constructed in-process
coordinator used by tests or a bounded offline golden harness. Its Agent port
accepts only the closed delivery value and calls only the explicitly supplied
v0.25 service; it cannot resolve an endpoint or use network/process/runtime
facilities.

Owned evidence readback is direct in-process store access only. Any future
API, command, or UI requires a new planning decision covering authentication,
operator mapping, CSRF/origin where applicable, rate/body bounds, redaction,
and method isolation. No feature flag may expose v0.26 in production.
`install-container` remains unsupported and default-disabled.

## P0–P5 scope and acceptance

### P0 — Delivery and acknowledgement contract — complete

Freeze this exact schema, six-release linkage, authority boundary, ownership,
identities, freshness, lifecycle, idempotency/no-replay, recovery, redaction,
audit evidence, default-disabled no-surface posture, threats, goldens, and
must-not-change contracts. P0 changes planning documentation only.

### P1 — Closed models and pure validation — complete

Implement isolated immutable delivery, attempt-record, acknowledgement, and
error models; canonical fingerprints; lifecycle derivation; and hostile-input
tests. Perform no I/O, persistence, registration, network, process, runtime,
provider, repository, guest, worker, or workflow action.

### P2 — Core simulation evidence and coordinator — complete

Implement only the explicitly constructed coordinator and bounded Core stores
with atomic reservations, exact retry, acknowledgement-copy reconciliation,
quotas, restart durability, owned reads, and fail-closed ambiguity/corruption.
The Agent port is injected and cannot be resolved from production settings.

### P3 — Agent acknowledgement adapter and evidence — complete

Implement an explicitly constructed adapter that maps the exact delivery into
the unchanged v0.25 service, validates the complete durable v0.25 record, and
appends the closed acknowledgement. Add no route, listener, command, container
registration, transport, event, queue, runtime adapter, or authority consumer.

### P4 — Offline golden delivery harness — complete

Exercise the coordinator, Agent adapter, and synthetic same-owner v0.20–v0.25
chain entirely in process. Render only a bounded redacted test projection.
Mission Control remains absent. Home Assistant is a blocked golden only; add no
deployment artifact or exception.

### P5 — Isolation, no-replay, and release closure — complete

Prove exact linkage, lifecycle/freshness boundaries, one-delivery/one-intake/
one-acknowledgement behavior, exact recovery, concurrency, restart and timeout
ambiguity, ownership, quotas, corruption, redaction, zero production surface,
capability parity, all prior goldens, and full regressions. P5 does not migrate,
tag, push, publish, deploy, or release automatically.

Release-isolation tests scan production Core and Agent modules and allow v0.26
vocabulary only inside the two isolated in-process packages. They lock out
HTTP/OpenAPI, CLI/shell, application-container registration, settings
enablement, network/transport clients, workers, workflows, provider/repository/
guest mutation, candidate execution, deployment, rollback, and replay bypass.
They also prove explicit default-disabled construction, fixed-false authority,
effect-import isolation, and direct operator-owned store readback. Mission
Control structural tests lock out every v0.26 client, mutation, route,
navigation, control, prohibited action label, and evidence surface.
`install-container` remains unsupported and Home Assistant remains blocked
with no deployment artifact.

## Exact authority boundary

Core may validate and preserve one simulation-only delivery attempt and an
exact returned acknowledgement copy, but only through an explicitly
constructed coordinator. Agent may validate the delivery through the unchanged
v0.25 path and preserve v0.25 intake plus v0.26 acknowledgement evidence.

Core cannot claim live send/receipt, authenticate Agent, grant admission,
authorize execution, or cause target effects. Agent cannot claim authentic
Core origin, grant live admission, consume execution authority, create work,
or mutate anything except its bounded simulation evidence stores. No
production execution authority is granted.

## Must-not-change contracts for P0–P5

- V0.16–v0.25 schemas, fingerprints, stores, routes, ownership, lifecycle,
  freshness, idempotency, goldens, and meanings remain exact. V0.26 wraps the
  complete v0.24 envelope and references the complete v0.25 record; it changes
  neither.
- V0.20 remains non-executable; v0.21 remains approval-intent evidence; v0.22
  remains validation-only and unsupported; v0.23 remains record-only; v0.24
  remains prepared and not live-delivered; v0.25 remains injected simulation,
  not receipt or admission.
- Existing ExecutionCandidate, approvals, workflow, operational dispatch,
  repository execution, execution audit, worker, Provider Intent, and
  interrupted-side-effect no-replay contracts remain unchanged and consume no
  v0.26 evidence.
- Agent support remains `update-compose-stack` for repository work and
  `restart-service/proxmox/qemu` for operational work. `install-container`
  remains unsupported and absent from executable capability/intent sets.
- Discovery stays GET-only; Provider Intent stays Proxmox QEMU
  `monitoring-policy`; the optional worker stays default-disabled; backup and
  restore stay explicit operator maintenance.
- No Docker/Podman/container-runtime call, shell/process execution, image
  acquisition, provider mutation, repository read or mutation, in-guest read
  or mutation, workflow start, worker execution, installation, deployment,
  rollback, background work, production API/command/UI, authority event,
  migration, tag, push, publication, or release is added.

## Threats and golden cases

The threat model covers cross-operator delivery, substituted IDs or
fingerprints, stale envelopes, acknowledgement forgery or equivocation,
partial two-store persistence, replay after ambiguity or expiry, recovery
being mistaken for redelivery, simulation wording presented as live receipt,
production registration/config drift, quota or corruption fail-open behavior,
and secret/exception leakage.

The positive golden uses a synthetic exact same-owner v0.20–v0.24 chain. One
fresh v0.26 delivery creates the exact v0.25 record and one acknowledgement;
Core preserves the acknowledgement copy; every authority field is false and
provenance is `agent_simulated_not_received`. Exact retry returns identical
evidence without new work. Changed identity, fingerprint, linkage, operator,
time, recipient, authority field, or unknown key fails closed.

Home Assistant remains blocked before v0.20 because its deployment artifact is
absent and its realistic workload is outside the v0.22 policy. It may appear
only as a rejection/golden fixture. No artifact or exception is introduced.

## What v0.26 enables later and what remains blocked

V0.26 enables later design to reuse a deterministic delivery/acknowledgement
state machine, exact six-release linkage, separate Core and Agent evidence,
bounded reconciliation after ambiguous acknowledgement-copy persistence, and
tests proving one-attempt/no-replay behavior across the service boundary.

Still blocked are mutual Core/Agent authentication and authorization, network
transport and endpoints, a live delivery-attempt identity, durable live
receipt and atomic consumption/no-redelivery, independent fresh execution
approval, execution-time target/image proof, worker/runtime behavior,
Docker/Podman/shell/process use, provider/repository/in-guest mutation,
workflow start, interruption recovery for side effects, execution audit, image
acquisition, installation, deployment, rollback, and Home Assistant install.
