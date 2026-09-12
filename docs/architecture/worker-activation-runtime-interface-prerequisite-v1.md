# Worker Activation Runtime Interface Prerequisite v1 contract

Status: **v0.57 P1 pure Core contract and P2 isolated durable service/store implemented
against the synchronized v0.56 boundary. P3-P5 remain unimplemented; no runtime
or downstream authority.**

P1 adds the [closed contract and evaluator](../../services/atlas-core/app/worker_activation_runtime_interface_prerequisite/contract.py),
[independent fingerprint vectors](../../services/atlas-core/app/worker_activation_runtime_interface_prerequisite/fingerprint_vectors.json)
and hostile regressions. P2 adds isolated durable evidence persistence. The Sync
inspection and phase requirements below
remain the boundary specification; historical documentation-only statements describe
the Sync change, not the P1/P2 implementation.

## Inspection and decision

Exactly one v0.57 boundary is selected: **Worker Activation Runtime Interface
Prerequisite evidence**. Core records a closed, deterministic blocker-to-owner/proof
inventory for exactly one active same-owner v0.56 review/status pair. The sole new
success marker is `worker_activation_runtime_interface_prerequisite_recorded`.
It means inventory recorded, never prerequisites satisfied. This is a normative
selection for future implementation, not a claim that a v0.57 model, route,
permission, reader, journal or marker is implemented by this synchronization.

The synchronization baseline is commit
`1371cd369c2dc416eae7b9d4bdac504700888935`. Its first-parent integration contains
v0.56 P0 `cb0ff6c7`, P1 `01328ff3`, P2 `9d6f5a0c`, P3 `8426e4c8`, P4
`7430fef4` and P5 `6f18b957`. These are repository integration identities;
historical phase-task hashes in the [release checklist](../RELEASE_CHECKLIST.md)
are retained as historical evidence, not substituted for these commits.
Local `atlas-v0.56.0` tag object `1896db71bc8ce5acfc204b06574fc1f83e41b8f0`
peels to `292dbd298468112b37c384f19d2b302149ea5ae7`, an ancestor of this baseline,
not the current HEAD. The provisional document entered at `c850bdc5`.
The v0.55 tag object `cfe06e593a75aae5aafdc75f7f174d25a11a3410` still peels to
`8ddd3672a3ffa5bb81b06ffb51290733cd355c5f`. Local ancestry establishes repository
support only; external release, publication, deployment and historical validation
limitations are unchanged.

The incremental evidence is an immutable explicit mapping of each unresolved
blocker to a responsibility and proof obligation, pinned to the reviewed plan.
V0.56 supplies fixed consistency findings and blockers, but no such closed mapping.
V0.57 records that mapping without repeating review as a new approval or adding
operational observations. This task selects this narrow advance; release ordering
alone did not authorize it. Runtime definition, contact adapters and worker-start
admission need facts and authority absent from this chain and are excluded.

| Integrated source inspected | Confirmed constraint |
| --- | --- |
| [v0.55 plan contract](worker-activation-runtime-plan-v1.md) and [model](../../services/atlas-core/app/worker_activation_runtime_plan/contract.py) | Reference-only design, both contact interfaces `undefined`, seven unresolved blockers. |
| [v0.56 contract](worker-activation-runtime-plan-review-v1.md) and [model/evaluator](../../services/atlas-core/app/worker_activation_runtime_plan_review/contract.py) | Closed review/status, three ordered findings, exact recursive lineage and inherited 67 false fields. |
| [Reader](../../services/atlas-core/app/worker_activation_runtime_plan_review/readers.py), [service](../../services/atlas-core/app/worker_activation_runtime_plan_review/service.py), [store](../../services/atlas-core/app/worker_activation_runtime_plan_review/store.py) | Default-off durable evidence, owner-scoped v0.55 reads, two locked revalidations and permanent reservation. The existing prerequisite reader does not read v0.56 reviews. |
| [Route](../../services/atlas-core/app/routes/worker_activation_runtime_plan_review.py) and [API tests](../../services/atlas-core/app/routes/test_worker_activation_runtime_plan_review.py) | Guarded evidence POST/list GET/item GET, exact response binding, no runtime composition. |
| [Closure tests](../../services/atlas-core/app/worker_activation_runtime_plan_review/test_release_closure.py) and [Mission Control reader](../../services/mission-control/src/api/workerActivationRuntimePlanReview.ts) | Immutable lineage, no-replay and exact isolated consumers; UI is GET-only. |
| [Agent architecture](../../services/atlas-agent/ARCHITECTURE.md) and [worker contract](../../services/atlas-execution-worker/README.md) | Independent intent, authentication, approval and execution ledger boundaries supply no installation runtime authority. |

## Exact integrated v0.56 predecessor requirements

The sole direct predecessor is one active same-owner
`WorkerActivationRuntimePlanReviewV1` / `WorkerActivationRuntimePlanReviewStatusV1`
pair, with schemas `worker-activation-runtime-plan-review-v1` and
`worker-activation-runtime-plan-review-status-v1`. The future create request must pin
`runtime_plan_review_id`, `runtime_plan_review_record_fingerprint`, paired
`status_fingerprint` and exact `valid_until`. Owner comes from authentication;
`candidate_record_id` (canonical UUID4) and authenticated `operator_id` must match
both models. No caller-provided nested evidence,
latest-record fallback, alternate plan, queue lookup or worker lookup is allowed.

Preserve the complete immutable review/status and embedded v0.55 plan/status:
v0.56 review -> v0.55 plan -> v0.54 runtime admission -> v0.53 runtime
prerequisite -> v0.52 queue receipt -> v0.51 acknowledgement admission ->
v0.50 acknowledgement prerequisite -> v0.49 claim admission -> every inherited
v0.48-v0.20 record/status in the [v0.55 lineage](worker-activation-runtime-plan-v1.md#closed-plan-and-exact-v054-prerequisite-lineage).
Preserve all IDs, owner/candidate, times, abstract subjects, limits and versioned
record/status/subject/key/receipt fingerprints byte-exactly. The v0.52
`admission_id` is shared with v0.51, distinct from v0.54 `runtime_admission_id`;
do not invent a receipt ID or use a release commit as record identity.
The [v0.52 receipt boundary](controlled-worker-queue-claim-lease-acknowledgement-boundary-v1.md)
records injected already-observed assertions; Core did not perform or independently
verify queue effects. Inheriting that receipt supplies no live queue primitive.

Reparse strict closed models even after model-copy/construct, verify hashes and
UUID derivation using each predecessor's own validators, and verify paired
status with v0.56 `derive_status` at its recorded evaluation time. Independently
check eligibility using trusted whole-second UTC Core time: reject future,
stale (over 30 seconds), expired (`now >= valid_until`), foreign, missing,
ambiguous, corrupt, altered-authority or mismatched evidence. Preserve historical
nested validation times; no normalization, lineage truncation or freshness renewal.
Successor expiry equals the pinned predecessor expiry and remains
within every inherited limit. An expired historical review is evidence only.

The v0.56 record and status share five canonical UUID5 identities:
`runtime_plan_review_id`, `runtime_plan_id`, `runtime_admission_id`,
`prerequisite_id` (v0.53), and `admission_id` (v0.51/v0.52). Preserve all five;
none is interchangeable with candidate UUID4 or the new successor ID.
The review also preserves `profile=core_owned_reference_only_runtime_plan_review_v1`
and ordered findings `exact_plan_lineage`, `fixed_design_consistent`,
`unresolved_interfaces_preserved`. Status adds `evaluated_at` and can be expired;
the immutable record retains `lifecycle=active`. An expired status retains the
recorded marker and blockers; that marker alone cannot establish current eligibility.

V0.56 subject binds exactly `operator_id`, `candidate_record_id`, `runtime_plan_id`.
Its domains are `atlas:worker-activation-runtime-plan-review-{kind}:v1`, where
kind is `subject`, `request`, `record`, `evaluation`, `status`, `collection`,
`idempotency-key`, `reservation`, `audit` (and `correlation` for redaction).
Use v0.56 `subject_fingerprint`, `derived_runtime_plan_review_id`,
`runtime_plan_review_record_fingerprint`, `status_fingerprint` and `derive_status`;
all recursive predecessors retain their own validators and domains.
Fingerprints retain `algorithm=sha256`, `canonicalization=atlas-jcs-nfc-v1` and
lowercase digest `value`. The ID domain is
`atlas:worker-activation-runtime-plan-review-id:v1`; the shared UUID5 helper hashes
that domain with the complete subject fingerprint before namespace derivation.
The [frozen vectors](../../services/atlas-core/app/worker_activation_runtime_plan_review/fingerprint_vectors.json)
are authoritative test identities, never production record identities.

The existing P2 reader derives v0.55 status at the plan's `recorded_at`. P3 item
GET instead returns the v0.56 record plus status evaluated at trusted current time;
list GET returns records without paired statuses. Neither is an existing durable
v0.56 prerequisite reader. P2 adds an injected owner-scoped review
reader, derives stable v0.56 status at review `recorded_at`, and separately checks
current eligibility. Pin that stable status fingerprint in create; do not assume
an arbitrary item-GET status fingerprint equals it. Do not rewrite historical
embedded v0.55 status or renew expiry. Duplicate successor requests return history
without predecessor reads; fresh creation revalidates under both journal write locks.

## Frozen v0.57 contract and API scope (Core P1 implemented; API remains future)

The schema prefix is `worker-activation-runtime-interface-prerequisite`.
The record schema is that prefix plus `-v1`; companion schemas append
`-create-v1`, `-authority-context-v1`, `-evaluation-v1`, `-status-v1`,
`-result-v1`, `-collection-v1`, `-reservation-v1`, `-audit-v1`, `-error-v1`.
Models use `WorkerActivationRuntimeInterfacePrerequisite` plus the corresponding
v0.56 model suffix (`V1`, `CreateV1`, `AuthorityContextV1`, `EvaluationV1`,
`StatusV1`, `ResultV1`, `CollectionV1`, `SubjectReservationV1`,
`AuditEvidenceV1`, `RedactedErrorV1`). All envelopes are closed, immutable,
strictly reparsed and inherit the unchanged authority ceiling below.

Create pins only `runtime_plan_review_id`, `runtime_plan_review_record_fingerprint`,
predecessor `status_fingerprint`, exact `valid_until` and
`requested_scope=worker_activation_runtime_interface_prerequisite_only`, plus
schema/authority constants. Owner comes from authentication and candidate from
the route; inventory and nested evidence are never caller-supplied.
Record embeds complete `worker_activation_runtime_plan_review` and
`worker_activation_runtime_plan_review_status`, retains the five predecessor IDs,
and adds UUID5 `runtime_interface_prerequisite_id`,
`runtime_interface_prerequisite_record_fingerprint`, successor `subject_fingerprint`
and `idempotency_key_fingerprint`. It retains owner, candidate, recording/expiry,
active lifecycle, seven blockers and historical true evidence markers.
Record carries the exact fixed `inventory` below and the new true marker; its
`eligibility` equals that marker.
Profile is `core_owned_reference_only_runtime_interface_prerequisite_v1`.
Success evaluation recognizes exactly one review (`recognized_v056_review_count=1`),
records the fixed `inventory` below and sets eligibility to the new marker.
Refusal recognizes zero, leaves the marker false and emits no partial inventory.
Status binds the exact record fingerprint and IDs, adds `evaluated_at` and its own
`status_fingerprint`, derives active/expired without changing recorded evidence,
and must equal canonical derivation at its recorded evaluation time. Status
preserves the fixed profile, inventory, blockers and recorded marker even at expiry.
Result is the exact record/status pair plus `exact_duplicate`; collection is an
owner/candidate-bound tuple of unique records with count and collection fingerprint.

Permanent successor subject binds exactly `operator_id`, `candidate_record_id`,
`runtime_plan_review_id`. Expiry, status, content or key changes cannot replace it.
Successor hash domains are
`atlas:worker-activation-runtime-interface-prerequisite-{kind}:v1` for the same
kinds listed above; UUID domain is
`atlas:worker-activation-runtime-interface-prerequisite-id:v1`. Apply the existing
canonical hash algorithm (domain UTF-8, NUL, canonical JSON) and UUID5 helper with
namespace `7bdf38b6-89a9-5d12-a0c1-33db5f733183` to the complete successor subject
fingerprint. Model hashes omit only their own fingerprint field; request binds
owner/candidate/create, and key hash binds owner/visible ASCII key as in v0.56.
P1 must lock independently calculated vectors before accepting implementation;
no successor digest or UUID is claimed to exist in the integrated repository.

For comparison, the **implemented v0.56** API base is
`/api/v1/installation/candidate-records/{candidate_record_id}/worker-activation-runtime-plan-reviews`:
POST returns `WorkerActivationRuntimePlanReviewResultV1` (201, including exact
duplicates), list GET returns `WorkerActivationRuntimePlanReviewCollectionV1`,
and item GET `/{runtime_plan_review_id}` returns the result pair.
Its create schema is `worker-activation-runtime-plan-review-create-v1`, pinning
v0.55 plan ID/record fingerprint/status fingerprint/expiry and
`requested_scope=worker_activation_runtime_plan_review_only`.
Permissions are `installation.execution.worker_activation_runtime_plan_review.evaluate`
and `.read`. Missing service is 503; disabled creation is 409; foreign/missing is
404. Authentication/permission/throttle errors are 401/403/429; malformed,
oversized and wrong-content-type requests are 422/413/415. Errors are redacted,
non-retryable; no queries or GET bodies are accepted. Responses are reparsed and
bound to owner/candidate, item ID or exact create pins and key fingerprint.

The **future v0.57** API has exactly POST/list GET at
`/api/v1/installation/candidate-records/{candidate_record_id}/worker-activation-runtime-interface-prerequisites`
and item GET `/{runtime_interface_prerequisite_id}`. Use the corresponding frozen
successor create/result/collection/error schemas, 201 POST semantics and the same
v0.56 guards/error mapping. Dedicated permissions are
`installation.execution.worker_activation_runtime_interface_prerequisite.evaluate`
and `.read`. POST requires trusted Origin/CSRF, one 16-128 visible ASCII
Idempotency-Key and strict JSON bounded to 16 KiB/nesting 16. Collection maximum
is 16 and every full response remains within 192 KiB. No alternate route, action,
start endpoint, production construction or enabling setting is selected.

## Blocked authority and affected authoritative subsystems

All seven success blockers remain ordered and unchanged:

```text
worker_activation_runtime_not_defined
store_contact_not_defined
runtime_contact_not_defined
worker_start_admission_not_defined
worker_start_not_defined
agent_invocation_not_defined
execution_start_boundary_not_defined
```

The closed inventory maps those blockers as follows. These are
obligations for separate future decisions, not interfaces implemented by v0.57.
Worker-side ownership entries are proposed responsibility boundaries requiring
confirmation in those decisions, not claims of existing installation interfaces.

`inventory` is exactly seven entries in blocker order, each a closed triple
`blocker`, `owner`, `required_proof` with the literal values below. No free text,
optional entries, caller choices or satisfied/approved flag is allowed. These
owner values name future responsibility, not deployed interface ownership.

| `blocker` | `owner` | `required_proof` |
| --- | --- | --- |
| `worker_activation_runtime_not_defined` | `core_installation_authority` | `installation_runtime_identity_capability_composition_lifecycle` |
| `store_contact_not_defined` | `worker_storage_authority` | `authenticated_store_subject_protocol_operations_recovery` |
| `runtime_contact_not_defined` | `worker_runtime_authority` | `authenticated_runtime_peer_request_effect_limits_uncertainty` |
| `worker_start_admission_not_defined` | `core_admission_authority` | `validated_runtime_contact_prerequisites_exact_subject_admission` |
| `worker_start_not_defined` | `worker_authority` | `one_shot_start_reservation_durability_no_replay_uncertainty` |
| `agent_invocation_not_defined` | `agent_authority` | `installation_intent_authentication_exact_approvals` |
| `execution_start_boundary_not_defined` | `execution_authority` | `exact_execution_request_capability_approval_durable_ledger` |

The proof literals require, respectively: an exact installation runtime identity,
supported capability, composition ownership and fail-closed lifecycle; an
authenticated owner/subject-bound store protocol with bounded operations and
corruption/recovery semantics; an authenticated runtime peer/request with bounded
effects and ambiguous-outcome handling; independently validated runtime/contact
prerequisites and an immutable admission for the exact subject; reservation before
one-shot start with durable no-replay and terminal uncertainty; independently
accepted installation intent, authentication and exact Agent approvals; and an
exact execution request with capability/approval checks and durable ledger.
A Core evidence SQLite journal does not satisfy store contact, review does not
satisfy operator approval, and inventory cannot become `WorkerExecutionRequest`
or an intent in the existing repository/operational registry.

Core owns only inventory evaluation, persistence, hashes and eligibility.
Mission Control remains a non-authoritative nested read-only projection.
Agent, execution worker/relay, Provider Intent, operational dispatch, repository
workflows, Discovery, installation artifacts and deployment configuration retain
their existing authority and gain no consumer or implementation responsibility.
Home Assistant remains blocked without installation artifacts.

Review recorded != interface prerequisites satisfied != runtime defined.
Inventory recorded != contact authorized != worker-start admitted != worker started.
Worker started != Agent invoked != execution authorized or started.

Preserve `evidence_only=true`, `reference_only=true`, `payload_bytes=0`, all 67
released false authority/material fields from the normative
[v0.55 authority inventory](worker-activation-runtime-plan-v1.md#authority-ceiling)
and the meanings of historical true evidence markers. Strict booleans/material
values reject numeric and string coercion on every envelope and recursively
embedded model. No runtime activation, worker/store/runtime/queue contact,
queue claim/lease/ack/consume/requeue, payload/command/credential/endpoint input,
worker-start admission/build, start/invocation, Agent invocation, execution-start
admission/build, execution authorization/start, process/shell execution,
scheduler/workflow/dispatch, provider/repository/in-guest mutation, installation,
deployment, rollback, publication/tag push/release, retry/resend, repair or replay
bypass is authorized. No adapter, production wiring, enabling setting or change
to `compose.execution-smoke.override.yaml` belongs to this boundary.

## Provisional assumptions reconciled

| Former gate | Sync disposition |
| --- | --- |
| A1: predecessor identity/closure | Resolved for repository scope: integrated P0-P3 and subsequent P4/P5 are present at the exact baseline above. Historical external gates remain external; no remote acceptance is inferred from a local tag. |
| A2: semantic ceiling | Resolved: exact schemas, five IDs, three findings, seven blockers and 67 false fields match the integrated Core contract and guarded API. |
| A3: owned durable predecessor | Resolved as a design constraint: durable review get exists, but the existing prerequisite reader consumes v0.55. P2 now implements the separate owner-scoped v0.56 reader and stable-status binding specified above. Permanent reservation and both-lock validation are inherited unchanged. |
| A4: bounds/freshness | Frozen fail-closed requirement, not a claim of measured v0.57 capacity: complete expanded record/result/collection must fit 192 KiB and the inherited 30-second window. P1/P2 must prove representative and overflow cases before closure; overflow/expiry refuses, never truncates or renews. |
| A5: distinct boundary | Resolved by this selection: a fixed explicit owner/proof inventory pinned to review adds information absent from v0.56 findings. No runtime prerequisite is satisfied and no interface is defined. |

P0 selection is complete. Implementation acceptance remains gated by the tests
below; this documentation synchronization implements none of P1-P5.

## P1-P5 responsibilities and exit evidence

| Phase | Responsibility under this frozen boundary |
| --- | --- |
| P1 | Pure immutable closed Core inventory models/evaluator, injected exact v0.56 pair and deterministic fixed mapping. Lock vectors for the frozen domains/UUID derivation and strict authority. Test recursive lineage, extras/duplicate keys, copied/constructed models, wrong owner/subject/hash, stale/future/expired evidence, refusal without marker advancement and size bounds. No I/O or runtime imports. |
| P2 (implemented) | Explicitly constructed default-off service, owner-scoped durable review reader and separate bounded append-only journal. Atomically reserve owner/key and permanent subject before append; revalidate predecessor/time under both write locks. Exact duplicates return history without predecessor reads or renewal. Post-reservation ambiguity is terminal, with no retry/repair/replacement/eviction. Test multiprocess contention, restart/expiry, incomplete reservations, partial writes/audit/response loss, corruption and unchanged predecessor bytes. Retain ceilings of 16 reservations per owner, 256 global, 192 KiB per model, one terminal audit per reservation and 256 MiB main database pages (not a filesystem quota); limits may only decrease. |
| P3 | Minimum guarded candidate/owner-scoped evidence POST/list GET/item GET, using the exact frozen routes/permissions. Dedicated evaluate/read permissions, trusted Origin/CSRF, strict bounded JSON and idempotency, redacted failures and response reparsing/binding. Missing service and disabled creation fail closed. Test authentication, foreign/missing equivalence, hostile responses and exact OpenAPI surface. No production construction or enabling setting. |
| P4 | Nested GET-only Mission Control evidence under the exact v0.56 review. Validate closed response, immutable predecessor, owner/IDs, blockers, inventory and authority; Core owns hashes/time eligibility. Distinguish loading/missing/unavailable/expired, reset on scope change and ignore late responses. Explain that prerequisites remain incomplete; collapse technical details. No create/start action, polling, browser persistence, standalone route or navigation. Run hostile fixtures, scope-race tests, build and lint. |
| P5 | Prove durable v0.56-to-v0.57 byte-exact lineage, permanent no-replay, strict authority, default-off construction and exact Core/API/UI consumers with zero Agent/worker consumers. Run P1-P4 and historical closure/isolation/Home Assistant gates, documentation consistency and hostile diff review. Record actual results and remaining external gates; no publication, deployment or runtime enablement. |

Historical isolation allowlists must remain exact and justified if later phases
add evidence consumers. No wildcard exclusions, relaxed fingerprint-only import
checks or pre-authorized future consumers. This P0 changes no allowlist or test.

## Sync validation scope

Only this contract, the roadmap and release-planning evidence change. Check local
tag identities/ancestry, predecessor contract and authority inventories, relative
links, documentation-only diff and whitespace. Run focused v0.56 contract,
durable service/store, closure and guarded API regressions, then
review the complete diff adversarially and create a real local documentation
commit. Results belong in the [release checklist](../RELEASE_CHECKLIST.md).
These tests validate the synchronized prerequisite claims against the checkout;
they prove no v0.57 implementation or external release/production readiness.

## P2 durable implementation

The [service](../../services/atlas-core/app/worker_activation_runtime_interface_prerequisite/service.py),
[review reader](../../services/atlas-core/app/worker_activation_runtime_interface_prerequisite/readers.py)
and [journal](../../services/atlas-core/app/worker_activation_runtime_interface_prerequisite/store.py)
implement the P2 boundary above with a separate application-ID-57 database.
Construction is explicit and creation defaults off. The reader preserves durable
v0.56 bytes and stable recorded-at status. Both write locks validate lineage and
trusted time; committed reservations permanently deny replay, including incomplete
appends and expired history. Exact duplicates bypass predecessor reads.

Retention refuses new reservations at the frozen ceilings without eviction.
Schema, indexes, canonical evidence, ownership, hashes and bounds are checked on
every connection. Corruption closes both reads and writes. Terminal record/audit
writes are atomic, failure audits are best effort, and all public errors remain
redacted and non-retryable. The
[persistence regressions](../../services/atlas-core/app/worker_activation_runtime_interface_prerequisite/test_service_store.py)
exercise these guarantees with real predecessor storage and process contention.
No route, production composition, Agent/worker consumer or downstream authority
is added. Actual test results are recorded in the release checklist.
