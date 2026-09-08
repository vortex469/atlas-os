# Worker Activation Runtime Plan v1 contract

Status: **Atlas v0.55 P0 frozen; P1 implemented; P2-P5 pending**. This contract
plans one boundary only. P0 changes documentation; it creates no runtime, model, service,
API, UI, permission, setting or startup behavior.

## Decision derived from the released repository

Exactly one boundary is selected: **Worker Activation Runtime Plan evidence**.
Only `worker_activation_runtime_plan_recorded` may newly become true. This means
Core has recorded a deterministic, reference-only design projection of one exact
active same-owner v0.54 admission/status pair. It records where evidence is owned
and which runtime interfaces remain undefined. It does not establish a runtime,
readiness, worker identity/contact protocol, executable configuration or a start
contract. Success recognizes exactly one admission; refusal recognizes zero and
leaves the new marker false. The inherited
`worker_activation_runtime_admission_recorded` marker retains its v0.54 meaning.
All seven inherited blockers remain unchanged.

The inspected baseline is released `atlas-v0.54.0`, whose annotated tag object
`262e8e2c383510c9486450b8e7fb200e84fafce3` peels to starting HEAD
`ddec6f16dc2fef0632bd398cfc2d6f4a06ccaf87`. Its ancestry includes P5 closure
`54bb37a`, the Mission Control immutable-authority fixture correction `7c08eff`,
and the Core quality-gate timeout change at release HEAD. These latter changes
add no installation runtime primitive. Local tag/ancestry verification confirms
repository release identity; it does not prove deployment or waive historical
external validation limitations in the [release checklist](../RELEASE_CHECKLIST.md).

| Released source inspected | Decision supported |
| --- | --- |
| [v0.54 normative contract](worker-activation-runtime-admission-v1.md) | Admission explicitly accepts evidence for separately contracted future runtime design consideration; no blocker is removed. A closed design projection is the next supported evidence advance. |
| [Core contract/evaluator](../../services/atlas-core/app/worker_activation_runtime_admission/contract.py) | Exact immutable admission/status, UUID5 identity, canonical hashes, 30-second freshness and inherited false fields support pure deterministic planning. No contact or runtime interface exists here. |
| [Service](../../services/atlas-core/app/worker_activation_runtime_admission/service.py), [store](../../services/atlas-core/app/worker_activation_runtime_admission/store.py), [reader](../../services/atlas-core/app/worker_activation_runtime_admission/readers.py) | Default-off owned Core evidence and permanent reservations support another isolated evidence journal. The released reader reads v0.53 evidence, not a queue or worker. |
| [Routes](../../services/atlas-core/app/routes/worker_activation_runtime_admission.py), [UI reader](../../services/mission-control/src/api/workerActivationRuntimeAdmission.ts) | Guarded evidence create/list/get and nested GET-only presentation provide no production service construction or runtime bridge. |
| [Closure](../../services/atlas-core/app/worker_activation_runtime_admission/test_release_closure.py), [UI isolation](../../services/atlas-core/app/worker_activation_runtime_admission/test_mission_control_isolation.py) | Byte-exact durable lineage, unchanged predecessor database, restart no-replay, exact consumers and zero Agent/worker consumers constrain successors. |
| [Agent architecture](../../services/atlas-agent/ARCHITECTURE.md), [packaged worker](../../services/atlas-execution-worker/README.md), [worker API](../../services/atlas-execution-worker/atlas_execution_worker/api.py) | Separately approved repository execution has independent requests, authentication and ledger. Packaging/health cannot supply installation authority or satisfy its missing runtime contracts. |

The selection is an architectural inference from those released contracts, not a
claim that v0.54 already implements or names a v0.55 plan. Repeating admission
would add no design information. Runtime definition/activation, worker-start
admission (including its construction), or a bridge to the packaged worker would
require identity, contact and effect primitives absent from this chain. This
plan freezes only the supported reference-only design projection; it does not
pre-authorize any later boundary or turn roadmap ordering into permission.

## Closed plan and exact v0.54 prerequisite lineage

The sole direct prerequisite is `WorkerActivationRuntimeAdmissionV1`
(schema `worker-activation-runtime-admission-v1`) paired with
`WorkerActivationRuntimeAdmissionStatusV1`
(schema `worker-activation-runtime-admission-status-v1`). Obtain both through an
injected owner-scoped durable Core reader; never accept caller-supplied nested
evidence, a latest-candidate selection or a worker/queue lookup.

The future create request pins UUID5 `runtime_admission_id`, exact `valid_until`,
`runtime_admission_record_fingerprint`, predecessor `status_fingerprint`, and
closed scope `worker_activation_runtime_plan_only`. Authenticated `operator_id`
and candidate UUID4 `candidate_record_id` must match both predecessor models.
Preserve inherited UUID5 `prerequisite_id` (v0.53) and UUID5 `admission_id`
(shared by v0.51/v0.52); neither is the v0.54 `runtime_admission_id`. There is
no separate v0.52 receipt ID. These are per-record identities, not release
commit IDs; no production instance UUID or digest is invented by P0.

Embed the complete immutable pair as `worker_activation_runtime_admission` and
`worker_activation_runtime_admission_status`. Preserve every field, including:

- `runtime_admission_id`, `prerequisite_id`, `admission_id`, `operator_id`,
  `candidate_record_id`, `recorded_at`, `valid_until`, status `evaluated_at`,
  lifecycle, eligibility, ordered blockers and admission-recorded marker;
- `runtime_admission_record_fingerprint`, `subject_fingerprint`,
  `idempotency_key_fingerprint` and paired `status_fingerprint`;
- `worker_activation_runtime_prerequisite` and
  `worker_activation_runtime_prerequisite_status`, their
  `prerequisite_record_fingerprint`, subject/key/status fingerprints and all
  recursively embedded v0.52 receipt/status fields, `receipt_record_fingerprint`,
  v0.51/v0.50/v0.49 record/status fingerprints, binding/worker/queue-item/limits/
  adapter/queue-subject fingerprints, claim/lease/acknowledgement receipt
  fingerprints and complete `adapter_receipt`;
- All historical owners, IDs, timestamps, abstract references, inherited limits,
  strict authority/material values and canonical serialized predecessor models,
  as specified by the [v0.54 exact lineage](worker-activation-runtime-admission-v1.md#exact-v053-prerequisite-lineage).

The complete chain is v0.54 runtime admission -> v0.53 runtime prerequisite -> v0.52 queue receipt ->
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

Validate v0.54 with its own `runtime_admission_record_fingerprint`,
`status_fingerprint`, `subject_fingerprint`, `derived_runtime_admission_id` and
`derive_status` functions. Its subject binds exactly `operator_id`,
`candidate_record_id`, `prerequisite_id`. Its fingerprint domain is
`atlas:worker-activation-runtime-admission-{kind}:v1` and ID domain is
`atlas:worker-activation-runtime-admission-id:v1`. Preserve `sha256` /
`atlas-jcs-nfc-v1` metadata and recursively validate each predecessor with its
own versioned functions. Reparse even constructed/copied model instances.
Require status equality with `derive_status(record, evaluated_at=status.evaluated_at)`.
Never regenerate inherited IDs, normalize evidence values, reparent/rebind,
substitute summaries, widen limits or fall back to older evidence on failure.

An owned reader may derive the stable exact status at admission `recorded_at`,
following the released durable-reader pattern. Independently check active
eligibility at trusted whole-second UTC Core time: no future record/status,
status before recording, clock rollback, age beyond 30 seconds or
`now >= valid_until`. Preserve nested historical eligibility at its original
validation time; do not renew it. Plan expiry must equal the pinned predecessor
expiry and be no later than any inherited expiry or 30 seconds after plan
recording. Refuse missing, foreign, ambiguous, stale, expired, corrupt,
fingerprint-mismatched, altered-authority or unsupported-capability evidence.
Home Assistant remains blocked without installation artifacts.

The new schema is `worker-activation-runtime-plan-v1`, with distinct UUID5
`runtime_plan_id` and `runtime_plan_record_fingerprint`. The permanent v0.55
subject binds exactly owner, candidate and v0.54 `runtime_admission_id`;
expiry/status/request/key changes cannot create another subject. P1 must freeze
separate versioned plan ID, subject, request, record, evaluation, status,
collection, idempotency, reservation and audit domains with deterministic vectors.
Predecessor subject/key fingerprints remain evidence, never successor keys.

The plan is a closed deterministic projection, not caller-authored design text.
Its fixed profile is `core_owned_reference_only_runtime_plan_v1`; it binds the
exact admission pair and inherited worker/queue references without new selectors.
Its design facts name Core as evidence owner and distinguish the owned admission
reader, separate plan journal and read-only presentation. Worker-store and
worker-runtime contact interfaces remain `undefined`; the seven ordered blockers
are the complete
unresolved-interface inventory. These facts are literals or exact inherited
references. Beyond immutable inherited evidence, no new script, executable
graph, scheduler, plugin/adapter selection, endpoint, filesystem path, command,
credential, token, free-form configuration, payload or operational instruction
is representable. P1 must reject extra fields.
The plan is never consumable as a `WorkerExecutionRequest` or worker-start input.

## P1 immutable model implementation

The [pure Core module](../../services/atlas-core/app/worker_activation_runtime_plan/contract.py)
implements closed create, authority context, injected validation input, evaluation,
design, record, status, result, collection, reservation, audit and redacted error
models. The evaluator receives trusted Core facts; it does not obtain evidence,
read a clock or reserve anything. Both previously-reserved flags must explicitly
be false. Durable ownership and replay checks remain P2 responsibilities.

`WorkerActivationRuntimePlanDesignV1` fixes `profile` to
`core_owned_reference_only_runtime_plan_v1`, `evidence_owner` to `atlas_core`,
`admission_reader` to `core_owned_runtime_admission_reader`, `plan_journal` to
`separate_core_owned_plan_journal`, and `presentation` to `read_only`.
`inherited_references=exact_embedded_admission_pair` identifies the complete
immutable source of worker/queue references; there are no additional selectors
or duplicated, independently editable references. Both contact interfaces remain
`undefined`; `unresolved_interfaces` equals the seven ordered blockers.

The evaluation uses `plan_state=recorded|blocked`, recognizes exactly one or zero
v0.54 admissions, and preserves the historical admission marker's evidence-only
meaning. Record and status preserve all four distinct IDs: `runtime_plan_id`,
`runtime_admission_id`, `prerequisite_id` and `admission_id`. Record expiry equals
the exact predecessor expiry. Status derivation never renews historical evidence.

The hash domains are `atlas:worker-activation-runtime-plan-{kind}:v1`, where
`kind` is `subject`, `request`, `record`, `evaluation`, `status`, `collection`,
`idempotency-key`, `reservation` or `audit`. UUID5 uses the distinct domain
`atlas:worker-activation-runtime-plan-id:v1`. The committed
[deterministic vectors](../../services/atlas-core/app/worker_activation_runtime_plan/fingerprint_vectors.json)
freeze all these domains plus an owner/candidate/admission subject and plan ID.
These are test vectors, never production prerequisite identities.

## Authority ceiling

Only `worker_activation_runtime_plan_recorded` may newly become true.
`evidence_only=true`, `reference_only=true`, `payload_bytes=0` are mandatory.
Historical true evidence markers retain only their original meanings. Every
v0.54 `ClosedAuthorityV1` field remains unchanged in create/evaluation/record/
status/result/collection/reservation/audit/error models and all nested evidence.
Strict boolean/material typing is required; numeric/string coercion is forbidden.
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

The following released authority/material fields remain strictly false:

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

Also blocked/default-off: runtime definition/activation, queue discovery/remove/
replacement, worker registration/discovery/contact, installation artifacts,
arbitrary repair, retry/resend, publication and all unrelated effects. The plan
never removes `worker_activation_runtime_not_defined`. Core-local evidence
journal I/O is not worker-store, runtime, queue or network contact authority.
No service enablement, schema name, evidence marker, UI display or release tag
can confer worker-start admission or execution authorization.

## Persistence, replay, ownership, concurrency and corruption

P2 may provide only an explicitly constructed default-off Core-local append-only
SQLite plan journal and owned durable v0.54 reader. No production construction,
network, broker, worker database, runtime probe or queue adapter. Do not mutate
predecessor stores or consume/release their reservations. P1 remains pure.

Reserve owner-scoped idempotency and permanent subject atomically under SQLite
write serialization, with FULL synchronous durability. Commit the permanent
reservation before the terminal record/audit transaction. Under each write lock,
re-read the exact prerequisite and revalidate trusted time before reservation and
immediately before append. Any drift fails closed. For each permanent subject,
across independent processes and service instances, at most one reservation and
one record may succeed.

An exact key/request duplicate returns unchanged historical evidence plus current
status, including expired status, without predecessor reads, append or renewed
eligibility. Same key/different request and different key/same subject conflict.
Reservation survives restart, expiry, response loss and append/audit failure.
Pre-reservation refusal records no success. After reservation, interruption or
failure is terminal indeterminate: no resume, release, repair, replacement,
eviction or retry. Bounded failure audit is best effort and cannot undo reservation.
Corrupt duplicate readback fails closed. Reads never trigger consumers.

Limits may only be lowered from 16 reservations per owner, 256 globally,
192 KiB per serialized model, one terminal audit per reservation and 256 MiB main
SQLite database pages. Incomplete reservations count. Reject excess capacity
without eviction; the page bound is not a journal/filesystem quota. If complete
lineage exceeds the envelope, refuse instead of truncating it or raising limits.
Validate schema, indexes, ownership, row/model linkage, canonical hashes and
bounds on every connection. Corruption closes reads and writes. Test damaged
indexes, partial writes, disk/full/locked database failures and cross-instance
races; no corruption or recovery path may grant new authority.

Reject unknown fields, duplicate JSON keys, malformed metadata and forbidden
material. Persist/expose only bounded closed redacted evidence, opaque correlation
fingerprints and non-retryable errors. No raw idempotency key, secret, payload,
selector, exception or environment dump in storage/logs/UI. Foreign owner or
candidate lookup is indistinguishable from missing evidence.

## P1-P5 responsibilities and exit gates

Implement P1 -> P2 -> P3 -> P4 -> P5 only within this ceiling; all were pending at
P0. P1 now implements only the pure contract described above. Neither future
implementation nor closure authorizes production enablement.

| Phase | Responsibility and required evidence |
| --- | --- |
| P1 | Pure immutable closed plan models/evaluator over exactly one v0.54 pair, fixed design projection, strict authority, complete recursive lineage, deterministic ID/domain vectors and bounded redacted refusals. Test unsupported capability, model-copy/construct bypass, duplicate keys, stale/future/expired/foreign evidence and exact plan derivation. No I/O, runtime imports, API, settings or permission registration. |
| P2 | Explicit default-off service, owned durable v0.54 reader and separate bounded plan journal meeting every persistence requirement above. Test real durable predecessor byte equality, duplicate/conflict, quotas, two-lock revalidation, independent-instance concurrency, corruption, crash/audit/response loss and restart/expiry no-replay. No production construction. |
| P3 | Guarded evidence-only POST/GET collection `/installation/candidate-records/{candidate_record_id}/worker-activation-runtime-plans` and item GET `/{runtime_plan_id}`. Dedicated `installation.execution.worker_activation_runtime_plan.evaluate` and `.read` permissions; authenticated owner/candidate, trusted Origin/CSRF, 16-128 visible ASCII Idempotency-Key, strict JSON maximum 16 KiB/nesting 16. Reparse/bind responses; collections maximum 16 and 192 KiB. Missing service 503, disabled creation 409, foreign/missing 404, throttling 429; bounded redacted errors. Test exact route methods/authentication/scope/bounds. No production construction, enabling setting or action/start endpoint. |
| P4 | Nested Mission Control GET-only evidence beneath the exact v0.54 admission, checking closed schemas, owner/candidate/admission linkage, exact immutable predecessor, fingerprint metadata, lifecycle, seven blockers and false authority. Core owns hashes and current-time eligibility. Clear evidence on scope change, ignore late responses and distinguish loading/missing/unavailable/expired. Say “Runtime plan is evidence; runtime prerequisites remain incomplete.” Collapse IDs/hashes/times/duplicates. No creation/action control, polling, browser persistence, navigation or worker/Agent/execution controls. Test hostile fixtures, scope races; run UI test/build/lint. |
| P5 | Prove complete durable v0.54-to-v0.55 byte-exact recursive lineage, strict authority, permanent reservation and restart no-replay. Lock exact Core/API/UI consumers and zero Agent/execution-worker consumers. Run P1-P4 suites, historical release/isolation/scope and Home Assistant golden checks, Core Ruff, UI gates, documentation consistency and hostile diff review. Record actual outcomes and limitations; no new runtime behavior or enablement in closure. |

Agent and `services/atlas-execution-worker` must have zero boundary consumers,
imports, routes, settings, clients or adapters. No translation to repository
workflows, operational dispatch, Provider Intent or process execution. Preserve
their independent approvals, intent registries, relay/authentication, backend
defaults and no-replay ledgers. Tests may inspect these surfaces without invoking
them or starting a worker/execution.

Historical consumer allowlists may later add only explicitly named evidence
modules and exact types with proof of no effect authority. No wildcard, blanket
future exclusion, weakened scanner or relaxation of fingerprint-only AST import
restrictions. P0 changes no allowlist. Preserve all historical release and golden
semantics; never rewrite old unchecked gates as passes.

## P0 validation and release isolation

P0 changes only this contract, ROADMAP and release-planning evidence. Verify the
released tag/ancestry, document links, exact v0.54 fields/domains, complete false
inventory and ordered blockers. Run focused released contract/service/store/API,
closure and UI structural checks plus historical installation isolation and
applicable Atlas Core Ruff. Run `git diff --check` and hostile review; verify
only these three documentation paths changed and create a real local commit.
Commands and observed results belong in the [release checklist](../RELEASE_CHECKLIST.md).

Historical environment-dependent UI/full-suite/production gates remain as
recorded. P0 does not probe runtime or claim those gates passed. Do not modify
`compose.execution-smoke.override.yaml`. No Agent invocation, worker/execution
start, installation, deployment, rollback, push, tag, release, publication,
retry/resend or unrelated effect is authorized.
