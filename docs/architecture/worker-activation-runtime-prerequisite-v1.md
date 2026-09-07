# Worker Activation Runtime Prerequisite v1 contract

Status: **Atlas v0.53 P0-P5 repository implementation; external validation gates open**.

P5 recovery baseline is P4 `fe781fb`, containing P3 `7b5831c` through
reconciled merge `b78ca94`. [Release evidence](../RELEASE_CHECKLIST.md) records
observed validation and unresolved environment gates; this is not publication.

P1 implementation: [Core contract and pure evaluator](../../services/atlas-core/app/worker_activation_runtime_prerequisite/contract.py)
and [hostile contract tests](../../services/atlas-core/app/worker_activation_runtime_prerequisite/test_contract.py).
The request binds `admission_id`, `valid_until`, `receipt_record_fingerprint`
and `status_fingerprint`; the record embeds the complete immutable v0.52 pair.
Every input, including existing model instances, is recursively reparsed with
strict literal types. Successful evaluation recognizes exactly one receipt and
retains all seven blockers. Refusals recognize zero and expose bounded codes
without caller material. Subject identity binds only owner/candidate/admission;
request, record, status, reservation and audit use separate v0.53 domains.
Reservation/audit models are pure data definitions, with no persistence in P1.

P2 implementation: [explicit default-off service](../../services/atlas-core/app/worker_activation_runtime_prerequisite/service.py),
[owner-scoped durable v0.52 reader](../../services/atlas-core/app/worker_activation_runtime_prerequisite/readers.py),
[bounded SQLite journal](../../services/atlas-core/app/worker_activation_runtime_prerequisite/store.py),
and [service/store regressions](../../services/atlas-core/app/worker_activation_runtime_prerequisite/test_service_store.py).
The journal commits permanent reservations before the terminal evidence transaction,
uses FULL synchronous writes and validates schema, indexes, bounds and complete
models on every connection. Incomplete reservations never resume. P2 extends only
the redacted error vocabulary with authentication and storage failure codes; the
pure evaluator refusal vocabulary and authority ceiling are unchanged. P2 adds no production
startup composition, routes, settings or effect consumers; P3 adds only the
guarded evidence routes described below.

P3 implementation: [guarded Core routes](../../services/atlas-core/app/routes/worker_activation_runtime_prerequisite.py)
and [route/security tests](../../services/atlas-core/app/routes/test_worker_activation_runtime_prerequisite.py).
Only collection POST/GET and item GET are registered. Dedicated evaluate/read
permissions bind authenticated owner and candidate; creation also requires trusted
origin, CSRF and a bounded idempotency key. Strict request decoding and recursive
response reparsing retain the P1 authority ceiling and P2 permanent reservations.
Errors use the existing P1/P2 redacted envelope: missing service is `unavailable`
(503), disabled creation is `installation_capability_unsupported` (409), foreign
lookups are `evidence_not_found` (404), and mutation throttling is `forbidden` (429).
Production startup does not construct the service or its stores.

P4 implementation: [Mission Control guarded reader](../../services/mission-control/src/api/workerActivationRuntimePrerequisite.ts)
and [nested view](../../services/mission-control/src/features/installation/WorkerActivationRuntimePrerequisite.tsx).
The existing v0.52 receipt view lists owner/candidate-scoped prerequisite records,
selects only the exact admission and immutable receipt fingerprint, then reads its
Core status by prerequisite ID. The reader checks closed v0.53 fields, inherited
v0.52 lineage, fingerprint metadata/linkage, lifecycle consistency, seven blockers
and fixed-false authority. It does not compute canonical hashes or current-time
eligibility; Core remains authoritative. Missing evidence and unavailable reads
are distinct, bounded states. Scope changes clear evidence and ignore late responses.
The normal view says runtime prerequisites remain incomplete; collapsed details
retain IDs, timestamps, fingerprints, duplicate evidence, blockers and authority.
No create control, polling, storage, navigation or downstream effect is introduced.

## Decision and inspected baseline

V0.53 selects **Worker Activation Runtime Prerequisite evidence**. Its only
new authority is Core-local recording of a bounded prerequisite for future
runtime-boundary design over one exact active same-owner v0.52 receipt:

```text
worker_activation_runtime_prerequisite_recorded
```

This means the inherited receipt evidence is internally consistent and bound
to one worker/queue subject. It does not mean runtime prerequisites are complete,
a runtime exists, a worker is reachable, or queue effects have been independently
verified. No effect primitive is established by this contract.

The inspected repository baseline is v0.52 P5 commit
`f6e9de8e57685967541369073e45f42e804989c8`, following P1 `84abd54`, P2
`304113f`, P3 `4b99f52`, and P4 `10f0cd8`. This is the completed repository
baseline supplied for this task, not proof of a remote merge, published v0.52
tag, or production enablement. The open environment-dependent release gates in
[the release checklist](../RELEASE_CHECKLIST.md) remain open; P0 does not waive them.
The prior released v0.51 lineage is
`8d1ece090b14e6fc2d06332b14b03559b252555d` (`atlas-v0.51.0`).

Repository evidence determining this selection:

| Inspected source | Consequence for v0.53 |
| --- | --- |
| [Completed v0.52 normative contract](controlled-worker-queue-claim-lease-acknowledgement-boundary-v1.md) | Final scope is already-observed receipt evidence, superseding the original adapter proposal. |
| [Core contract](../../services/atlas-core/app/controlled_worker_queue_claim_lease_acknowledgement/contract.py) | Closed receipt/status models retain seven runtime/start blockers and fixed-false authority. |
| [Core service](../../services/atlas-core/app/controlled_worker_queue_claim_lease_acknowledgement/service.py), [reader](../../services/atlas-core/app/controlled_worker_queue_claim_lease_acknowledgement/readers.py), [store](../../services/atlas-core/app/controlled_worker_queue_claim_lease_acknowledgement/store.py) | Explicit default-off composition; receipt reader has no queue client; durable reservations prevent replay. A Core-owned evidence successor is supported. |
| [Core route](../../services/atlas-core/app/routes/controlled_worker_queue_claim_lease_acknowledgement.py) | Owner-scoped guarded evidence API, absent service 503, no production construction. |
| [Mission Control reader](../../services/mission-control/src/api/controlledWorkerQueueReceipt.ts) and [view](../../services/mission-control/src/features/installation/ControlledWorkerQueueReceipt.tsx) | Nested guarded GET evidence projection, no activation control. |
| [Agent architecture](../../services/atlas-agent/ARCHITECTURE.md) | Repository execution and operational dispatch have independent approvals/contracts; Agent does not read Core databases. |
| [Packaged worker](../../services/atlas-execution-worker/README.md) and [worker API](../../services/atlas-execution-worker/atlas_execution_worker/api.py) | Existing optional repository execution backend is separately gated; its request ledger is not an installation queue primitive. The actual directory is `services/atlas-execution-worker`; `services/execution-worker` does not exist. |
| [v0.52 closure tests](../../services/atlas-core/app/controlled_worker_queue_claim_lease_acknowledgement/test_release_closure.py), [scope tests](../../services/atlas-core/app/controlled_worker_queue_claim_lease_acknowledgement_admission/test_v052_scope.py), [service/store tests](../../services/atlas-core/app/controlled_worker_queue_claim_lease_acknowledgement/test_service_store.py) | Exact consumer allowlists, zero Agent/worker consumers, durable lineage, corruption closure and strict false authority prevent inferring a runtime bridge. |

The first remaining blocker is `worker_activation_runtime_not_defined`.
Recording its inherited evidence prerequisites is the narrow supported advance;
removing it, adding worker-start admission, or borrowing the packaged worker's
execution API would require missing runtime/contact contracts. Roadmap ordering
alone cannot supply those contracts. Even v0.52 claim/lease/ack receipt flags
are assertions of evidence, never permission to perform those queue effects.

## Exact prerequisite and lineage

The sole direct prerequisite is one Core-owned
`ControlledWorkerQueueClaimLeaseAcknowledgementV1` record with schema
`controlled-worker-queue-claim-lease-acknowledgement-v1`, paired with its
`ControlledWorkerQueueClaimLeaseAcknowledgementStatusV1` status. Both must have
matching authenticated `operator_id`, candidate UUID4 `candidate_record_id`,
and UUID5 `admission_id`. V0.52 reuses the v0.51 admission ID: do not invent a
separate v0.52 receipt ID or resolve by latest candidate/worker/queue match.

The request selects only that exact ID, exact `valid_until`,
`receipt_record_fingerprint`, and `status_fingerprint`. It cannot submit a
replacement nested receipt, worker identity, adapter, endpoint, or queue selector.
An injected owner-scoped durable v0.52 reader supplies the record/status pair;
there is no adapter receipt reader or worker reader in v0.53.

Reparse the complete immutable nested v0.52 model and validate its canonical
fingerprints using its own versioned functions. Copy these fields byte-exactly
into the new evidence (or preserve them in its immutable embedded prerequisite):

- `admission_id`, `operator_id`, `candidate_record_id`, `recorded_at`, `valid_until`;
- `receipt_record_fingerprint`, `subject_fingerprint`, `idempotency_key_fingerprint`
  and the paired `status_fingerprint` (the predecessor's idempotency fingerprint
  is evidence, never the successor's reservation key);
- `v051_admission_record_fingerprint`, `v051_admission_status_fingerprint`;
- `v050_prerequisite_record_fingerprint`, `v050_prerequisite_status_fingerprint`;
- `v049_admission_record_fingerprint`, `v049_admission_status_fingerprint`;
- `binding_subject_fingerprint`, `worker_subject_fingerprint`,
  `queue_item_reference_fingerprint`, `inherited_limits_fingerprint`;
- `adapter_identity_fingerprint`, `queue_subject_fingerprint`,
  `claim_receipt_fingerprint`, `lease_receipt_fingerprint`,
  `acknowledgement_receipt_fingerprint`, and the complete `adapter_receipt` facts;
- `controlled_worker_queue_claim_lease_acknowledgement_admission` and
  `controlled_worker_queue_claim_lease_acknowledgement_admission_status`,
  including all recursively inherited IDs, record/status fingerprints and limits.

The required predecessor chain is v0.52 receipt -> v0.51 admission -> v0.50
prerequisite -> v0.49 claim admission -> v0.48 binding activation evidence ->
v0.47 activation preflight -> v0.46 dequeue worker binding -> v0.45 controlled
dequeue receipt -> v0.44 dequeue admission -> v0.43 queue observation -> v0.42
one-shot enqueue -> v0.41 enqueue admission -> v0.40 worker intake -> v0.39
queue reservation -> v0.38 worker admission stub -> v0.37 runner binding plan ->
v0.36 execution admission -> v0.35 permission grant -> v0.34 readiness ->
v0.33 inert delivery receipt -> v0.32 live intake admission -> v0.31 live
delivery send -> v0.30 delivery enablement -> v0.29 activation preflight ->
v0.28 dormant wiring -> v0.27 real Agent intake -> v0.26 simulated handoff
delivery -> v0.25 Agent intake simulation -> v0.24 dispatch handoff -> v0.23
execution request -> v0.22 Agent install-container contract -> v0.21 approval
intent -> v0.20 candidate record. Preserve each
version's actual nested schema and identifiers; this chain is not permission to
substitute summaries for nested validation. Worker identity, abstract worker and
queue intake references, inert queue-item reference and inherited limits come
only from this chain. No rebinding, reparenting, ID regeneration, fingerprint
normalization, limit widening, or alternate historical lookup is allowed.

The status must be active at the trusted Core clock, with the exact record
fingerprint, recorded eligibility, all receipt flags true, and all seven blockers
unchanged. A stable status evaluated at the receipt's `recorded_at` may be used
for fingerprint matching, following the v0.52 reader pattern, but current-time
freshness and expiry must be checked independently. Maximum freshness is 30
seconds, never extended by read, duplicate, restart, or status regeneration.
New evidence expiry must not exceed the earliest inherited expiry.
Reject missing, future, stale, expired, foreign, ambiguous, corrupt, mismatched,
unsupported-capability or altered-authority evidence. Home Assistant remains
blocked and produces no installation/deployment artifact.

## Authority ceiling and isolation

Only `worker_activation_runtime_prerequisite_recorded` may newly become true.
Evidence remains `evidence_only=true`, `reference_only=true`, with zero payload
bytes. All existing v0.52 `ClosedAuthorityV1` literal-false fields remain strict
false in every v0.53 evaluation, record, status, result, collection and audit.
No historical marker or blocker is rewritten. Success retains exactly:

```text
worker_activation_runtime_not_defined
store_contact_not_defined
runtime_contact_not_defined
worker_start_admission_not_defined
worker_start_not_defined
agent_invocation_not_defined
execution_start_boundary_not_defined
```

In particular the new marker is unequal to runtime definition/activation,
worker-start admission, worker start, Agent invocation or execution start.
All downstream authority remains fixed false/default-off:

- Queue adapter/contact, claim, lease, acknowledgement effects; autonomous queue
  polling, discovery, consume/remove, requeue, mutation or replacement.
- Worker discovery/registration/contact, activation runtime, worker store/runtime
  contact, worker-start admission (including building it), start or invocation.
- Agent invocation, execution authorization/start (including admission building),
  dispatch, process/shell execution, scheduler/workflow start or execution.
- Caller-supplied credentials, endpoints, commands, payloads/schemas/serialization,
  queue selectors, claim/lease tokens or acknowledgement handles.
- Provider/repository/in-guest mutation, installation, deployment, rollback,
  artifact/tag/release publication, retry/resend, repair or replay bypass.

Core may access only its explicitly injected evidence stores. That local
persistence is not `worker_store_contact_allowed` or `store_contact_allowed`.
Agent and execution-worker must have zero consumers, imports, routes, settings,
clients or adapters for the new marker. No translation into `WorkerExecutionRequest`,
repository workflow, operational dispatch or Provider Intent is permitted.
Existing execution backend defaults, relay/authentication, approval, intent
registries, no-replay ledgers and historical release-isolation guarantees stay
unchanged. No runtime probe or Agent invocation is part of validation.

## Persistence, replay, concurrency and failure

P2 uses an explicitly constructed default-off Core-local append-only store
and an owner-scoped durable v0.52 reader. Production startup must never construct
or enable either automatically. No broker, transport, worker database or network
client is allowed. Pure P1 validation performs no persistence or I/O.

Use separate versioned deterministic domains for new record/status/request,
subject, reservation and audit fingerprints; preserve predecessor domains and
`sha256` / `atlas-jcs-nfc-v1` values unchanged. The permanent subject identity
binds authenticated owner, candidate and exact v0.52 admission ID; changed status,
expiry, key or fingerprints must not permit a second reservation for that subject.
Reserve subject and owner-scoped idempotency atomically before evidence append,
using SQLite write serialization and FULL synchronous durability. Re-read and
revalidate the exact prerequisite under the write lock before reservation and
immediately before append; trusted time must be checked at both boundaries.

Exact duplicates return historical evidence, including its expired status,
without prerequisite reads or new append. Same key/different request conflicts;
different key/same reserved subject conflicts. Concurrent calls and independent
store instances must admit at most one reservation/record. Reservations survive
expiry, restart and failures permanently. Pre-reservation rejection creates no
success evidence. Any failure after reservation is terminal indeterminate;
an interrupted reservation cannot retry, resume, release, replace or repair.
An audit failure must not undo the permanent reservation. Historical readback
must never renew eligibility or drive a consumer.

Limits may only be lowered from 16 reservations per owner, 256 globally,
192 KiB per serialized model, one terminal audit per reservation and 256 MiB
main database pages. Capacity includes incomplete reservations; exhaustion
rejects without eviction. Validate schema, indexes, stored models/fingerprints
and bounds on every connection; corruption closes reads and writes. Database
page limits are not a total filesystem/journal quota. Tests must cover damaged
indexes, partial append, disk/write failure, lock contention and restart.

Persist and expose only closed bounded redacted models. Unknown fields, duplicate
JSON keys, malformed fingerprint metadata and authority coercion fail closed.
No raw token, handle, selector, command, payload, endpoint, credential, exception,
environment dump or raw idempotency key may enter records, logs, audits or UI.
Errors are bounded non-retryable codes with opaque correlation fingerprints;
foreign owner/candidate lookups must not disclose record existence.

## P1-P5 implementation progression

P0 changed documentation only. P1 adds the models and pure evaluator linked
above; that phase introduced no I/O or production wiring. P3 and P4 add the
evidence API and UI described here, retaining the same authority ceiling.
The following responsibilities progress in strict P1 -> P2 -> P3 -> P4 -> P5
order. P5 adds durable predecessor-to-successor closure regressions and exact
production consumer allowlists. External validation limitations remain explicit.

| Phase | Required implementation and exit evidence |
| --- | --- |
| P1 | Closed immutable `worker-activation-runtime-prerequisite-v1` models and pure evaluator over the exact v0.52 pair; deterministic fingerprints, recognized prerequisite count exactly one on success, zero on refusal; test nested lineage tampering, limits, status/clock drift, authority coercion and redaction. No I/O. |
| P2 | Explicit default-off service/store and durable owned v0.52 reader; atomic permanent reservations, duplicate readback, quotas and corruption closure above. Prove concurrency across instances, restart/expiry no-replay and terminal post-reservation failures. No adapter or worker reader. |
| P3 | Minimum guarded evidence-only create/list/get Core API under `/installation/candidate-records/{candidate_record_id}/worker-activation-runtime-prerequisites`, with item GET `/{prerequisite_id}`. Dedicated `installation.execution.worker_activation_runtime_prerequisite.evaluate` and `.read` permissions; POST requires authenticated owner, trusted origin, CSRF, strict JSON (16 KiB, nesting 16 maximum), bounded 16-128 visible ASCII Idempotency-Key. Missing service returns redacted 503; disabled creation 409. No startup construction, activation endpoint or alternate methods. |
| P4 | Nested Mission Control read-only evidence beneath the exact v0.52 receipt using guarded GET only. Validate owner/candidate/prerequisite linkage, schema, fingerprints, lifecycle, blockers and false authority before rendering. No standalone route/navigation, create/action control, polling, browser storage, raw evidence dump or worker/Agent/execution control. Show that prerequisites remain incomplete. |
| P5 | Exact Core/API/UI consumer allowlists and zero Agent/execution-worker consumers; fixed-false authority, all P1/P2 failure cases, API auth/CSRF/scope, UI hostile fixtures, historical release isolation and Home Assistant goldens. Run focused suites, applicable Ruff and Mission Control test/build/lint gates, documentation/link checks and diff review; record environment failures without declaring them passed. Release closure adds tests/documentation only. |

Any future consumer allowlist addition must name the exact evidence module/type
and prove it cannot consume effect authority; wildcard exceptions or weakening
historical zero-consumer assertions are forbidden. P5 completion cannot itself
enable production. Later runtime/contact/start boundaries require separately
frozen prerequisites and independently validated contracts; neither this plan
nor a successful prerequisite is their authorization.

`compose.execution-smoke.override.yaml` remains absent and must not be modified.
No push, tag, release, publication, deployment or rollback is part of P0-P5.
