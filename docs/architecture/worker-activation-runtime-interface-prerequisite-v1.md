# Provisional v0.57 Worker Activation Runtime Interface Prerequisite evidence

Status: **P0 planning evidence only; candidate boundary, not a normative freeze.
P1-P5 are unstarted and depend on the v0.56 confirmation gate below.**

## Inspection and decision

The requested baseline `atlas-v0.55.0` has annotated tag object
`cfe06e593a75aae5aafdc75f7f174d25a11a3410`, peeling to
`8ddd3672a3ffa5bb81b06ffb51290733cd355c5f`. Its contract was inspected directly
from that tag. The task checkout begins at
`292dbd298468112b37c384f19d2b302149ea5ae7`, a descendant of that baseline.
It already includes local v0.56 P1-P5 integration, including P5 `6f18b957`.
Local annotated tag `atlas-v0.56.0` has object
`1896db71bc8ce5acfc204b06574fc1f83e41b8f0` and peels to that starting HEAD.
This is newer evidence than the task's “while v0.56 progresses” premise; it
does not establish remote publication, deployment or completion of external gates.
The historical [release evidence](../RELEASE_CHECKLIST.md) remains authoritative
for what was actually validated. This proposal does not rewrite its limitations.

The likely next narrow boundary is **Worker Activation Runtime Interface
Prerequisite evidence**: Core could record, for exactly one reviewed plan, a
closed inventory of the contracts that must be supplied before any runtime
interface definition can be considered. This is an architectural inference,
not a successor selected or authorized by v0.55/v0.56. A tentative marker is
`worker_activation_runtime_interface_prerequisite_recorded`; it means inventory
recorded, never prerequisites satisfied. No v0.57 model or marker exists as a
result of P0.

The proposed incremental information is a fixed mapping of unresolved blockers
to owning subsystems and required proof obligations, pinned to the exact review.
It adds no operational observation. P0 supplies that mapping below; a later
normative decision must establish whether persisting it has value beyond the
v0.56 review's existing inventory. If it does not, retain documentation only and
defer implementation rather than creating another indistinguishable evidence stage.

| Inspected repository evidence | Implication for v0.57 |
| --- | --- |
| [v0.55 plan contract](worker-activation-runtime-plan-v1.md) and [pure model](../../services/atlas-core/app/worker_activation_runtime_plan/contract.py) | The reference-only design names both contact interfaces `undefined`; its seven blockers are not a runtime protocol. |
| [v0.56 review contract](worker-activation-runtime-plan-review-v1.md) and [evaluator](../../services/atlas-core/app/worker_activation_runtime_plan_review/contract.py) | Only exact lineage, fixed design consistency and preserved unresolved interfaces are reviewed. Success is neither approval nor readiness. |
| [Owned reader](../../services/atlas-core/app/worker_activation_runtime_plan_review/readers.py), [service](../../services/atlas-core/app/worker_activation_runtime_plan_review/service.py), [store](../../services/atlas-core/app/worker_activation_runtime_plan_review/store.py) | The available primitive is default-off durable Core evidence. The existing reader reads v0.55 plans; a v0.57 reader of v0.56 reviews would be new work. |
| [Core route](../../services/atlas-core/app/routes/worker_activation_runtime_plan_review.py) and [Mission Control reader](../../services/mission-control/src/api/workerActivationRuntimePlanReview.ts) | Guarded evidence access and GET-only presentation supply no worker client or runtime composition. |
| [v0.56 closure](../../services/atlas-core/app/worker_activation_runtime_plan_review/test_release_closure.py) | Exact durable lineage, unchanged authority, permanent no-replay and exact consumer isolation constrain any successor. |
| [Agent architecture](../../services/atlas-agent/ARCHITECTURE.md) and [worker contract](../../services/atlas-execution-worker/README.md) | Repository execution has separate intent, approval, authentication and ledger boundaries. Packaging, health and repository execution cannot stand in for installation runtime authority. |

An additional review alone repeats v0.56. Plan approval or worker-start admission
would imply a decision for which the chain supplies neither an installation
runtime nor contact/start contracts. Implementing a store/runtime adapter would
introduce identity, authentication, side effects and recovery semantics absent
from these evidence models. None is justified merely by release ordering.

## Exact predecessor requirements (subject to v0.56 confirmation)

The proposed sole direct predecessor is one active same-owner
`WorkerActivationRuntimePlanReviewV1` / `WorkerActivationRuntimePlanReviewStatusV1`
pair, with schemas `worker-activation-runtime-plan-review-v1` and
`worker-activation-runtime-plan-review-status-v1`. A future request would pin
`runtime_plan_review_id`, `runtime_plan_review_record_fingerprint`, paired
`status_fingerprint` and exact `valid_until`. Owner comes from authentication;
candidate scope must match both models. No caller-provided nested evidence,
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
Proposed successor expiry equals the pinned predecessor expiry and remains
within every inherited limit. An expired historical review is evidence only.

If frozen later, use separate versioned successor hash/UUID domains and a
permanent subject binding owner, candidate and exact review ID. Expiry, new keys
or changed request content cannot create a replacement subject. Exact wire names,
domains, vectors and inventory literals require a normative freeze before P1.

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

The proposed closed inventory would map those blockers as follows. These are
obligations for separate future decisions, not interfaces implemented by v0.57.
Worker-side ownership entries are proposed responsibility boundaries requiring
confirmation in those decisions, not claims of existing installation interfaces.

| Blocker / authoritative subsystem | Required proof before a later boundary may remove it |
| --- | --- |
| Runtime definition / Core installation authority | Exact installation runtime identity, supported capability, composition ownership and fail-closed lifecycle contract. |
| Store contact / worker-owned storage boundary | Authenticated owner/subject binding, bounded protocol, allowed operations and corruption/recovery semantics; a Core evidence SQLite journal is not this interface. |
| Runtime contact / worker runtime boundary | Exact authenticated peer and request identity, bounded contact protocol, effect limits and ambiguous-outcome behavior. |
| Worker-start admission / Core admission authority | Separately validated runtime/contact prerequisites and immutable admission decision tied to the exact subject; evidence review is not operator approval. |
| Worker start / worker authority | One-shot start protocol, reservation-before-effect, durable no-replay and terminal uncertainty handling. |
| Agent invocation / Agent authority | Independently accepted installation intent, authentication and exact approvals; no translation into the existing repository or operational registry. |
| Execution start / execution authority | Exact execution request, capability/approval checks and durable execution ledger; no reuse of a review as `WorkerExecutionRequest`. |

Core would own only inventory evaluation, persistence, hashes and eligibility.
Mission Control would remain a non-authoritative nested read-only projection.
Agent, execution worker/relay, Provider Intent, operational dispatch, repository
workflows, Discovery, installation artifacts and deployment configuration retain
their existing authority and gain no consumer or implementation responsibility.
Home Assistant remains blocked without installation artifacts.

Review recorded != interface prerequisites satisfied != runtime defined.
Inventory recorded != contact authorized != worker-start admitted != worker started.
Worker started != Agent invoked != execution authorized or started.

Preserve `evidence_only=true`, `reference_only=true`, `payload_bytes=0`, all 67
released false authority/material fields and the meanings of historical true
evidence markers. No runtime activation, worker/store/runtime/queue contact,
queue claim/lease/ack/consume/requeue, payload/command/credential/endpoint input,
worker-start admission/build, start/invocation, Agent invocation, execution-start
admission/build, execution authorization/start, process/shell execution,
scheduler/workflow/dispatch, provider/repository/in-guest mutation, installation,
deployment, rollback, publication/tag push/release, retry/resend, repair or replay
bypass is authorized. No adapter, production wiring, enabling setting or change
to `compose.execution-smoke.override.yaml` belongs to this boundary.

## Assumptions requiring v0.56 confirmation before a normative freeze

| Gate | Current evidence and required confirmation |
| --- | --- |
| A1: predecessor identity and closure | Local v0.56 tag and integrated P1-P5 exist. Confirm the accepted final v0.56 commit, its contract and actual validation results; reconcile any later changes. Local tags alone prove no external release gate. |
| A2: unchanged semantic ceiling | Inspected review retains three fixed findings, seven blockers, 67 false fields and no approval/readiness meaning. Confirm these against accepted v0.56 models, API/UI and closure tests. Any drift requires re-analysis, not silent promotion. |
| A3: exact owned durable predecessor | Review persistence exists. Confirm stable owned read/status semantics, both-lock revalidation, byte-exact lineage, expiry and permanent no-replay before designing the new reader. No predecessor journal mutation or consumption. |
| A4: bounded successor is feasible | Verify complete recursive embedding plus the proposed inventory fits the inherited 192 KiB bound and the inherited freshness window. Refuse overflow/expiry; never widen limits, truncate lineage or renew evidence to make the stage fit. |
| A5: distinct useful boundary | Confirm that a durable blocker-to-owner/proof inventory is needed beyond v0.56's existing review. If redundant, leave this as planning evidence and defer P1-P5. No operational primitive may be substituted without a new authority decision. |

Resolving these gates requires a recorded normative selection with exact schemas,
closed inventory, domains, API scope and acceptance tests. This provisional P0
does not authorize P1 automatically, even though local v0.56 code is present.

## Conditional P1-P5 responsibilities and exit evidence

| Phase | Responsibility after confirmation and normative selection |
| --- | --- |
| P1 | Pure immutable closed Core inventory models/evaluator, injected exact v0.56 pair and deterministic fixed mapping. Freeze separate domains/UUID vectors and strict authority. Test recursive lineage, extras/duplicate keys, copied/constructed models, wrong owner/subject/hash, stale/future/expired evidence, refusal without marker advancement and size bounds. No I/O or runtime imports. |
| P2 | Explicitly constructed default-off service, owner-scoped durable review reader and separate bounded append-only journal. Atomically reserve owner/key and permanent subject before append; revalidate predecessor/time under both write locks. Exact duplicates return history without predecessor reads or renewal. Post-reservation ambiguity is terminal, with no retry/repair/replacement/eviction. Test multiprocess contention, restart/expiry, incomplete reservations, partial writes/audit/response loss, corruption and unchanged predecessor bytes. Retain ceilings of 16 reservations per owner, 256 global, 192 KiB per model, one terminal audit per reservation and 256 MiB main database pages (not a filesystem quota); limits may only decrease. |
| P3 | Minimum guarded candidate/owner-scoped evidence POST/list GET/item GET, only after exact route/permission freeze. Dedicated evaluate/read permissions, trusted Origin/CSRF, strict bounded JSON and idempotency, redacted failures and response reparsing/binding. Missing service and disabled creation fail closed. Test authentication, foreign/missing equivalence, hostile responses and exact OpenAPI surface. No production construction or enabling setting. |
| P4 | Nested GET-only Mission Control evidence under the exact v0.56 review. Validate closed response, immutable predecessor, owner/IDs, blockers, inventory and authority; Core owns hashes/time eligibility. Distinguish loading/missing/unavailable/expired, reset on scope change and ignore late responses. Explain that prerequisites remain incomplete; collapse technical details. No create/start action, polling, browser persistence, standalone route or navigation. Run hostile fixtures, scope-race tests, build and lint. |
| P5 | Prove durable v0.56-to-v0.57 byte-exact lineage, permanent no-replay, strict authority, default-off construction and exact Core/API/UI consumers with zero Agent/worker consumers. Run P1-P4 and historical closure/isolation/Home Assistant gates, documentation consistency and hostile diff review. Record actual results and remaining external gates; no publication, deployment or runtime enablement. |

Historical isolation allowlists must remain exact and justified if later phases
add evidence consumers. No wildcard exclusions, relaxed fingerprint-only import
checks or pre-authorized future consumers. This P0 changes no allowlist or test.

## P0 validation scope

Only this proposal, the roadmap and release-planning evidence change. Check local
tag identities/ancestry, predecessor contract and authority inventories, relative
links, documentation-only diff and whitespace. Run focused v0.55/v0.56 contract,
durable closure and v0.55 Mission Control structural isolation regressions, then
review the complete diff adversarially and create a real local documentation
commit. Results belong in the [release checklist](../RELEASE_CHECKLIST.md).
These tests validate planning assumptions against the checkout; they prove no
v0.57 implementation or external release/production readiness.
