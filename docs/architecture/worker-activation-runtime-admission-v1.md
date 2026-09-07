# Worker Activation Runtime Admission v1 contract

Status: **Atlas v0.54 P0 frozen; P1 pure Core contract, P2 durable evidence and P3 guarded API implemented; P4-P5 not implemented**.

P0 froze this normative boundary. P1 implements only the pure Core models and
evaluator; neither phase introduces runtime, API, UI, permission registration,
configuration or production startup behavior.

## Decision and released evidence

Exactly one boundary is selected: **Worker Activation Runtime Admission evidence**.
Its sole new authority is Core-local recording of
`worker_activation_runtime_admission_recorded` over one exact active same-owner
v0.53 prerequisite/status pair. Admission means that this immutable prerequisite
has been accepted for separately contracted future runtime design consideration.
It does not define a runtime, establish readiness, remove a blocker, authorize
worker-start admission, or authorize any contact or effect. Success recognizes
exactly one v0.53 prerequisite; refusal recognizes zero and grants no new marker.

The inspected released baseline is `atlas-v0.53.0`, resolving to
`b55f6520527fe37a729c6f72c183f1a3c8d26d50` (`b55f652`), also the starting HEAD.
The local tag and implementation confirm the supplied release identity; they do
not independently prove deployment or close historical external validation gates.
The [v0.53 contract](worker-activation-runtime-prerequisite-v1.md) and historical
[release evidence](../RELEASE_CHECKLIST.md) remain immutable in meaning.

| Inspected released source | Authority consequence |
| --- | --- |
| [v0.53 contract/evaluator](../../services/atlas-core/app/worker_activation_runtime_prerequisite/contract.py) | Immutable v0.52 pair, deterministic prerequisite ID, 30-second maximum freshness, strict false authority and seven unchanged blockers support an evidence admission only. |
| [Service](../../services/atlas-core/app/worker_activation_runtime_prerequisite/service.py), [reader](../../services/atlas-core/app/worker_activation_runtime_prerequisite/readers.py), [store](../../services/atlas-core/app/worker_activation_runtime_prerequisite/store.py) | Default-off construction, owned durable receipt reads and permanent SQLite reservations establish a Core evidence pattern, with no worker/queue reader or runtime bridge. |
| [Core routes](../../services/atlas-core/app/routes/worker_activation_runtime_prerequisite.py) | Guarded evidence create/list/get; no production service construction or start endpoint. |
| [Mission Control reader](../../services/mission-control/src/api/workerActivationRuntimePrerequisite.ts), [view](../../services/mission-control/src/features/installation/WorkerActivationRuntimePrerequisite.tsx) | Nested GET-only evidence reports incomplete prerequisites, never readiness or execution. |
| [v0.53 closure](../../services/atlas-core/app/worker_activation_runtime_prerequisite/test_release_closure.py), [UI isolation](../../services/atlas-core/app/worker_activation_runtime_prerequisite/test_mission_control_isolation.py) | Durable exact lineage, restart no-replay, exact production consumer allowlist and zero Agent/execution-worker consumers. |
| [Agent architecture](../../services/atlas-agent/ARCHITECTURE.md), [packaged worker](../../services/atlas-execution-worker/README.md), [worker API](../../services/atlas-execution-worker/atlas_execution_worker/api.py) | Independently approved repository execution is a separate surface; its ledger and execution request cannot stand in for installation runtime/contact contracts. |

The first blocker remains `worker_activation_runtime_not_defined`. A real runtime
or worker-start boundary would require missing identity/contact/effect contracts.
V0.52 receipt assertions and v0.53 prerequisite recording supply no such primitive.
The supported next advance is therefore acceptance of existing evidence, using
the repository's prerequisite-to-admission pattern; no effect flag advances.
Roadmap ordering, packaging and health must never substitute for authority.

## Exact v0.53 prerequisite lineage

The only direct prerequisite is `WorkerActivationRuntimePrerequisiteV1`
(schema `worker-activation-runtime-prerequisite-v1`) paired with
`WorkerActivationRuntimePrerequisiteStatusV1`
(schema `worker-activation-runtime-prerequisite-status-v1`). Both come from an
injected owner-scoped durable Core reader, never caller-supplied nested evidence.

The future create request pins `prerequisite_id`, exact `valid_until`,
`prerequisite_record_fingerprint` and predecessor `status_fingerprint`, plus the
closed scope `worker_activation_runtime_admission_only`. Authenticated
`operator_id` and candidate UUID4 `candidate_record_id` must match both models.
The UUID5 `prerequisite_id` is the v0.53 identity, distinct from its inherited
UUID5 `admission_id` (shared by v0.51/v0.52). Never select by latest candidate,
worker or queue, or invent a separate v0.52 receipt ID.

Embed the complete immutable pair as `worker_activation_runtime_prerequisite`
and `worker_activation_runtime_prerequisite_status`. Preserve byte-exact values
and canonical serialized predecessor models, including:

- `prerequisite_id`, `admission_id`, `operator_id`, `candidate_record_id`,
  `recorded_at`, `valid_until`, status `evaluated_at`, lifecycle and eligibility;
- `prerequisite_record_fingerprint`, `subject_fingerprint`,
  `idempotency_key_fingerprint`, paired `status_fingerprint`,
  `worker_activation_runtime_prerequisite_recorded` and complete ordered blockers;
- `controlled_worker_queue_claim_lease_acknowledgement` and
  `controlled_worker_queue_claim_lease_acknowledgement_status`, including
  `receipt_record_fingerprint`, v0.51/v0.50/v0.49 record/status fingerprints,
  binding/worker/queue-item/limits/adapter/queue-subject fingerprints,
  claim/lease/acknowledgement receipt fingerprints and complete `adapter_receipt`;
- Every recursively embedded predecessor record/status, identifier, fingerprint,
  owner, timestamp, abstract reference and inherited limit defined by the
  [v0.53 exact lineage](worker-activation-runtime-prerequisite-v1.md#exact-prerequisite-and-lineage).

The complete chain is v0.53 runtime prerequisite -> v0.52 queue receipt ->
v0.51 acknowledgement admission -> v0.50 acknowledgement prerequisite ->
v0.49 claim admission -> v0.48 binding activation evidence -> v0.47 activation
preflight -> v0.46 dequeue worker binding -> v0.45 controlled dequeue receipt ->
v0.44 dequeue admission -> v0.43 queue observation -> v0.42 one-shot enqueue ->
v0.41 enqueue admission -> v0.40 worker intake -> v0.39 queue reservation ->
v0.38 worker admission stub -> v0.37 runner binding plan -> v0.36 execution
admission -> v0.35 permission grant -> v0.34 readiness -> v0.33 inert delivery
receipt -> v0.32 live intake admission -> v0.31 live delivery send -> v0.30
delivery enablement -> v0.29 activation preflight -> v0.28 dormant wiring ->
v0.27 real Agent intake -> v0.26 simulated handoff delivery -> v0.25 Agent intake
simulation -> v0.24 dispatch handoff -> v0.23 execution request -> v0.22 Agent
install-container contract -> v0.21 approval intent -> v0.20 candidate record.

Reparse even model instances recursively; validate all canonical hashes using
their own versioned functions, including the v0.53 derived prerequisite ID and
`derive_status` equality. Preserve `sha256` / `atlas-jcs-nfc-v1` metadata. No
normalization, ID regeneration, rebinding, reparenting, summary substitution,
limit widening or fallback historical lookup is permitted.

An owned reader may derive stable predecessor status at its `recorded_at` for
exact fingerprint matching, following the released reader pattern. Separately
check active eligibility at trusted whole-second UTC Core time: no future
record/status, clock rollback, age beyond 30 seconds, or `now >= valid_until`.
Revalidate nested historical eligibility under its original contract and never
renew it. Success expiry must be no later than the earliest inherited expiry
and 30 seconds after admission recording. Reject missing, foreign, ambiguous,
stale, expired, corrupt, fingerprint-mismatched, altered-authority or unsupported
capability evidence. Home Assistant stays blocked without installation artifacts.

Use schema `worker-activation-runtime-admission-v1` and a separate UUID5
`runtime_admission_id`; never overload inherited `admission_id`. P1 must freeze
separate versioned domains for admission ID, subject, request, record, status,
collection, idempotency, reservation and audit, with deterministic test vectors.
The permanent subject binds owner, candidate and exact v0.53 `prerequisite_id`;
status, expiry, request/key changes cannot produce another subject. Predecessor
idempotency/subject fingerprints are immutable evidence, not successor keys.

## Authority ceiling

Only `worker_activation_runtime_admission_recorded` may newly become true.
`evidence_only=true`, `reference_only=true` and `payload_bytes=0` are mandatory.
All v0.53 `ClosedAuthorityV1` fields, recursively inherited authority and material
restrictions apply to requests, evaluation, records, statuses, results,
collections, reservations, audits and errors. Historical true evidence markers
retain their original meaning. No historical record, status or blocker is edited.
Success retains exactly these seven ordered blockers:

```text
worker_activation_runtime_not_defined
store_contact_not_defined
runtime_contact_not_defined
worker_start_admission_not_defined
worker_start_not_defined
agent_invocation_not_defined
execution_start_boundary_not_defined
```

The following released authority/material fields remain strictly false; numeric
or string coercion is forbidden:

```text
caller_supplied_credentials_allowed
caller_supplied_endpoint_allowed
caller_supplied_command_allowed
caller_supplied_payload_allowed
caller_supplied_queue_selector_allowed
caller_supplied_claim_token_allowed
caller_supplied_lease_token_allowed
caller_supplied_acknowledgement_handle_allowed
credential_material_present
endpoint_material_present
command_material_present
payload_material_present
queue_selector_material_present
claim_token_material_present
lease_token_material_present
acknowledgement_handle_material_present
payload_schema_defined
payload_constructed
payload_serialized
autonomous_queue_polling_allowed
work_discovery_allowed
queue_consume_allowed
queue_requeue_allowed
queue_mutation_allowed
worker_activation_runtime_allowed
worker_store_contact_allowed
worker_runtime_contact_allowed
worker_contact_allowed
worker_start_admission_allowed
worker_start_allowed
worker_invocation_allowed
agent_invocation_allowed
execution_authorization_allowed
execution_start_allowed
process_execution_allowed
store_contact_allowed
runtime_contact_allowed
dispatch_allowed
retry_allowed
resend_allowed
scheduler_allowed
workflow_start_allowed
shell_execution_allowed
provider_mutation_allowed
repository_mutation_allowed
in_guest_mutation_allowed
installation_allowed
deployment_allowed
rollback_allowed
replay_bypass_allowed
artifact_publication_allowed
tag_push_allowed
release_publication_allowed
worker_start_admitted
worker_started
agent_invoked
execution_started
queue_adapter_defined
queue_contact_allowed
queue_claim_allowed
queue_lease_allowed
queue_ack_allowed
worker_discovery_allowed
worker_registration_allowed
worker_start_admission_build_allowed
execution_start_admission_build_allowed
runtime_effect_allowed
```

Also blocked/default-off: queue discovery/remove/replacement, runtime definition
or activation, worker registration/discovery/contact, installation payloads,
credentials/endpoints/commands/tokens/handles, arbitrary repair, retry/resend,
publication and all unrelated effects. Core-local evidence store access is not
worker-store or runtime contact authority. Neither admission recording nor its
name grants `worker_start_admission_build_allowed` or worker-start admission.

Agent and execution-worker must have zero consumers, imports, routes, settings,
clients or adapters for this boundary. No translation into `WorkerExecutionRequest`,
repository workflows, operational dispatch, Provider Intent or process execution.
Their existing approvals, intent registries, relay/authentication, backend defaults
and no-replay ledgers remain isolated and unchanged.

## Persistence, ownership, replay, concurrency and corruption

P2 may add only an explicitly constructed, default-off Core-local append-only
SQLite journal and owned durable v0.53 reader. No startup construction, network,
broker, worker database, queue adapter or runtime probe. P1 remains pure.

Reserve subject and owner-scoped idempotency atomically under SQLite write
serialization with FULL synchronous durability. Commit permanent reservation
before the terminal evidence/audit transaction. Re-read and fully validate the
exact prerequisite and trusted time under each write lock, before reservation
and immediately before append; changes between these checks fail closed.
Concurrent requests across independent instances admit at most one reservation
and record. Never mutate predecessor stores or consume their reservations.

Exact key/request duplicates return historical evidence with current expired
status as appropriate, without predecessor reads, new append or renewed
eligibility. Same key/different request and different key/same subject conflict.
Reservations survive restart, expiry, failed response delivery and audit failure.
Pre-reservation refusal creates no success. Post-reservation interruption or
failure is terminal indeterminate: no resume, release, repair, replacement,
eviction or retry. Bounded failure audit is best effort and cannot undo a
reservation. Corrupt duplicate readback fails closed rather than returning success.

Limits may only be lowered from 16 reservations per owner, 256 globally,
192 KiB per serialized model, one terminal audit per reservation and 256 MiB
main database pages. Incomplete reservations count; capacity exhaustion rejects
without eviction. The page limit is not a filesystem/journal quota. If complete
lineage exceeds the model bound, reject; never truncate or raise limits silently.
Validate schema, indexes, ownership, row/model linkage, hashes and bounds on
every connection; corruption closes both reads and writes. Prove damaged indexes,
partial append, disk/write/audit failure, lock contention, concurrent instances,
restart and expiry cannot create new authority or bypass permanent reservation.

Unknown fields, duplicate JSON keys, malformed metadata and material fail closed.
Persist/expose only bounded closed redacted models, opaque correlation fingerprints
and non-retryable error codes. No raw idempotency key, secret, payload, selector,
exception or environment dump in storage/logs/UI. Foreign owner/candidate lookups
must be indistinguishable from missing evidence. Reads never drive consumers.

## P1-P5 responsibilities and exit gates

These are future implementation requirements, in P1 -> P2 -> P3 -> P4 -> P5 order.
P0 implements none of them.

| Phase | Required responsibility and evidence |
| --- | --- |
| P1 | Closed immutable admission models and pure evaluator over exactly one v0.53 pair; freeze domains/ID vectors and bounded redacted refusal vocabulary. Test full nested lineage, deterministic hashing, strict booleans, missing/foreign/stale/future/expired evidence, clock/status drift, unsupported capability and zero effect imports. No I/O. |
| P2 | Explicit default-off service, owned durable v0.53 reader and separate bounded journal satisfying all persistence requirements above. Test duplicate/conflict, quota, concurrency across instances, locked revalidation, crash/audit/corruption failures and restart/expiry no-replay with real predecessor stores. No production construction. |
| P3 | Only guarded evidence collection POST/GET at `/installation/candidate-records/{candidate_record_id}/worker-activation-runtime-admissions` and item GET `/{runtime_admission_id}`. Dedicated `installation.execution.worker_activation_runtime_admission.evaluate` and `.read` permissions. POST requires authenticated owner, trusted origin, CSRF, 16-128 visible ASCII Idempotency-Key and strict JSON (16 KiB, nesting 16). Reparse responses; bounded collection maximum 16. Missing service 503, disabled creation 409, foreign/missing 404, throttling 429; use redacted errors. Test authentication, scope, input bounds and exact methods. No new production service construction, enabling settings or activation/start endpoints. |
| P4 | Nested read-only Mission Control evidence beneath the exact v0.53 prerequisite. Guarded GET only; validate closed schemas, owner/candidate/prerequisite/record/status linkage, fingerprint metadata, lifecycle, blockers and false authority. Core owns hashes/current-time eligibility. Clear evidence on scope changes and ignore late responses. Distinguish loading/missing/unavailable/expired; say admission is evidence and runtime prerequisites remain incomplete. IDs/hashes/timestamps/duplicates in collapsed details. No create/action control, polling, browser persistence, standalone navigation or worker/Agent/execution controls. Test hostile fixtures and scope races; run test/build/lint. |
| P5 | Prove durable v0.53-to-v0.54 byte-exact recursive lineage, strict false fields and restart no-replay; exact Core/API/UI consumers and zero Agent/execution-worker consumers. Run P1-P4 tests, historical release/isolation/scope and Home Assistant golden checks, applicable Ruff and UI gates, documentation consistency and diff review. Record actual release evidence and environment failures; no runtime implementation in closure. |

Historical consumer allowlists may add only explicitly named evidence modules and
exact types with proof of no effect authority. No wildcard, future blanket
exception or weakening of historical isolation, including fingerprint-only import
restrictions. Production enablement and later runtime/contact/start contracts
require separate authorization; P5 or a released tag cannot supply it.

## Release isolation and P0 validation

P0 changes only this contract, ROADMAP and release checklist documentation.
Inspect the local released tag, verify links, exact predecessor fields, marker
agreement, seven blockers, closed authority inventory and documentation-only diff.
Run focused v0.53 contract/service/store/API/closure/UI structural tests and
historical installation/Agent isolation; record commands and observed results in
the [release checklist](../RELEASE_CHECKLIST.md). Run `git diff --check`, perform
hostile review and create a local documentation commit. P1-P5 remain open.

Historical external gates remain as recorded, including unavailable full-suite
and Mission Control dependency gates; this P0 does not waive or rerun them as
runtime probes. Do not modify `compose.execution-smoke.override.yaml`. No push,
tag, release, publication, deployment, rollback, worker start, Agent invocation
or execution start is authorized by this plan.


## P1 implementation reference

The [pure Core contract](../../services/atlas-core/app/worker_activation_runtime_admission/contract.py)
implements the closed create, authority, validation, evaluation, record, status,
result, collection, reservation, audit and redacted error models.
The complete v0.53 pair is recursively reparsed without modifying its canonical
representation. The distinct `runtime_admission_id` binds the permanent subject;
`prerequisite_id` and inherited `admission_id` remain separate exact identities.

P1 freezes domain strings `atlas:worker-activation-runtime-admission-{kind}:v1`
for `subject`, `request`, `record`, `status`, `collection`, `idempotency-key`,
`reservation`, `audit` and `evaluation`, using the released canonical fingerprint
envelope. UUID5 uses `atlas:worker-activation-runtime-admission-id:v1`.
[Committed vectors](../../services/atlas-core/app/worker_activation_runtime_admission/fingerprint_vectors.json)
lock these domains and the subject-derived identity.

The evaluator accepts only injected facts; its authority context and complete
predecessor pair are internal Core inputs, never a public nested-evidence request.
Required strict-false `subject_previously_reserved` and
`idempotency_key_previously_reserved` facts reject replay or unknown reservation
state. P2 must obtain these facts under its journal locks; the pure evaluator
does not establish durable uniqueness or handle historical duplicate retrieval.
The redacted refusal vocabulary is closed by `RefusalV1`; every refusal recognizes
zero prerequisites, has no expiry and grants no marker. All seven success blockers
remain byte-exact and all downstream authority remains false.

Only this exact successor contract is added to the v0.53 consumer allowlists.
P1 adds no service, reader, store, route, settings, UI or effect consumer.


## P2 implementation reference

The explicitly constructed [service](../../services/atlas-core/app/worker_activation_runtime_admission/service.py),
[owned v0.53 reader](../../services/atlas-core/app/worker_activation_runtime_admission/readers.py)
and [journal](../../services/atlas-core/app/worker_activation_runtime_admission/store.py)
implement this frozen persistence boundary. Creation defaults off. SQLite
application ID 54 separates the journal from predecessor storage. Every
connection checks exact schema/index definitions, integrity, canonical bounded
models, fingerprints, owner indexes and reservation/record/audit linkage.

Both prerequisite reads run under independent journal write locks. Permanent
subject and owner/key reservation commits before the evidence/audit transaction;
an interruption cannot resume. Exact duplicates read historical evidence without
predecessor access. Reservations, including incomplete ones, are retained without
eviction. Limits can only decrease from the frozen ceilings; the database page
limit does not claim a journal or filesystem quota.

The service preserves P1 IDs, hashes, recursive predecessor models and seven
blockers. Clock rollback between reads and malformed correlation material fail
closed. Only the exact three successor persistence modules join the historical
v0.53 consumer allowlists. No production construction or effect consumer is added.


## P3 implementation reference

The [guarded Core route](../../services/atlas-core/app/routes/worker_activation_runtime_admission.py)
registers only the frozen candidate collection POST/GET and runtime-admission
item GET. Dedicated evaluate/read permissions require an operator session. POST
also requires trusted-origin, CSRF and mutation throttling checks. Strict bounded JSON rejects
extra fields, duplicate keys, excessive nesting, ambiguous headers and material.
No query parameters or GET bodies are accepted.

Every service response is recursively reparsed through P1, including constructed
models and redacted errors. Owner/candidate/item linkage is checked at the route;
POST additionally binds prerequisite ID, expiry, both predecessor fingerprints
and the owner-scoped idempotency fingerprint to the exact request. P2 retains
exclusive responsibility for locked prerequisite revalidation, permanent
reservations and historical duplicate reads. Collections retain the P1 16-item
and 192 KiB model ceilings.

Missing service returns redacted 503; creation remains disabled unless explicitly
composed and enabled outside production startup. No enabling setting, startup
construction, runtime primitive or downstream authority is added. The exact
historical consumer allowlists name this evidence route and its registration.
The [API tests](../../services/atlas-core/app/routes/test_worker_activation_runtime_admission.py)
cover hostile requests/responses and durable v0.53 lineage through restart,
expiry and corrupt readback. P4/P5 remain separate work.
