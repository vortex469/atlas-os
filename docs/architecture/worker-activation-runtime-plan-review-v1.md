# Worker Activation Runtime Plan Review v1 contract

Status: **Atlas v0.56 P0 frozen; P1 pure Core contract, P2 durable evidence and P3 guarded API implemented; P4-P5 pending**.
This normative contract does not imply production enablement. Observed validation
is recorded in the [release checklist](../RELEASE_CHECKLIST.md).

## Decision and repository support

Exactly one boundary is selected: **Worker Activation Runtime Plan Review
evidence**. Only `worker_activation_runtime_plan_review_recorded` may newly
become true in later P1-P5 implementation. It records a deterministic Core-owned
consistency review of exactly one active same-owner v0.55 plan/status pair:
its fixed design matches its immutable admission evidence, its lineage validates,
and its unresolved-interface inventory is complete and unchanged. Review success
means evidence consistency only, never design approval, runtime readiness,
operator approval, admission to start, or satisfaction of a runtime prerequisite.
Refusal recognizes zero plans and leaves the new marker false; success recognizes
exactly one. Historical true evidence markers retain their original meanings.

The inspected released baseline is `atlas-v0.55.0`, annotated tag object
`cfe06e593a75aae5aafdc75f7f174d25a11a3410`, peeling to exact starting HEAD
`8ddd3672a3ffa5bb81b06ffb51290733cd355c5f`. It includes P0 `2a1e61e2`, P1
`2a954613`, P2 `708b880c`, P3 `6876f01a`, P4 `0e38706d`, lifecycle correction
`a36a96c0`, P4 merge `093ee0e2`, P5 `979cc49e`, and historical fingerprint
isolation maintenance `b3920e620b4084c792688203f7afcd2c28ba3c6b`. The latter
changes a historical test, not authority. Release identity proves repository
lineage, not deployment or completion of historical external validation gates.

| Released source inspected | Constraint supporting this decision |
| --- | --- |
| [v0.55 normative contract](worker-activation-runtime-plan-v1.md) | The plan is a closed reference-only design projection with undefined contacts and seven blockers; it expressly pre-authorizes no later boundary. |
| [Pure models/evaluator](../../services/atlas-core/app/worker_activation_runtime_plan/contract.py) | Exact design literals, complete embedded admission pair, versioned hashes and paired status permit a deterministic consistency review without new runtime facts. |
| [Owned reader](../../services/atlas-core/app/worker_activation_runtime_plan/readers.py), [service](../../services/atlas-core/app/worker_activation_runtime_plan/service.py), [store](../../services/atlas-core/app/worker_activation_runtime_plan/store.py) | Core-local evidence, default-off construction and permanent subjects support isolated review evidence; this reader reads v0.54 admissions, not workers. A new owned v0.55 reader is a P2 responsibility. |
| [Routes](../../services/atlas-core/app/routes/worker_activation_runtime_plan.py), [UI reader](../../services/mission-control/src/api/workerActivationRuntimePlan.ts) | Guarded evidence access and nested GET-only presentation do not supply runtime interfaces. |
| [Release closure](../../services/atlas-core/app/worker_activation_runtime_plan/test_release_closure.py), [UI isolation](../../services/atlas-core/app/worker_activation_runtime_plan/test_mission_control_isolation.py) | Durable byte-exact lineage, strict authority, restart no-replay and exact consumers must survive the successor. |
| [Agent architecture](../../services/atlas-agent/ARCHITECTURE.md), [packaged worker contract](../../services/atlas-execution-worker/README.md) | Independent approvals, authentication, intent registries and execution ledgers cannot be borrowed as installation authority. Packaging and health are not runtime evidence. |

This selection is a new architectural inference, not a claim that v0.55 names or
implements review. Its added evidence is an explicit, pinned consistency-review
result over a completed plan, rather than another plan or admission. The result
contains no new operational facts. Runtime definition, contact, activation or
worker-start admission/build would require primitives absent from this chain.
No later phase may reinterpret this review as those primitives. Any such boundary
requires a separately justified normative decision; roadmap order is not permission.

## Exact v0.55 prerequisite and review projection

The sole direct prerequisite is `WorkerActivationRuntimePlanV1` with schema
`worker-activation-runtime-plan-v1`, paired with
`WorkerActivationRuntimePlanStatusV1`, schema
`worker-activation-runtime-plan-status-v1`. Read it through an injected
owner-scoped durable Core reader. The create request pins `runtime_plan_id`,
`runtime_plan_record_fingerprint`, predecessor `status_fingerprint`, exact
`valid_until`, and scope `worker_activation_runtime_plan_review_only`.
Authenticated `operator_id` and candidate UUID4 `candidate_record_id` must match
both models. No caller-supplied nested evidence, latest-record fallback, alternate
admission selection, worker lookup or queue lookup is permitted.

Embed both complete immutable models as `worker_activation_runtime_plan` and
`worker_activation_runtime_plan_status`. Preserve every released field and value:

- `schema`, `design`, UUID5 `runtime_plan_id`, `runtime_admission_id`,
  `prerequisite_id`, `admission_id`, `operator_id`, `candidate_record_id`,
  `recorded_at`, `evaluated_at`, `valid_until`, `lifecycle`, `eligibility`,
  ordered `blockers`, `subject_fingerprint`, `idempotency_key_fingerprint`,
  `runtime_plan_record_fingerprint`, `status_fingerprint`,
  `worker_activation_runtime_admission_recorded`,
  `worker_activation_runtime_plan_recorded`, and the entire authority ceiling;
- `worker_activation_runtime_admission` and
  `worker_activation_runtime_admission_status`, including exact
  `runtime_admission_record_fingerprint` and complete recursive record/status
  evidence through v0.20, as frozen in the [v0.55 lineage contract](worker-activation-runtime-plan-v1.md#closed-plan-and-exact-v054-prerequisite-lineage).

The exact chain begins v0.55 plan -> v0.54 runtime admission -> v0.53 runtime
prerequisite -> v0.52 queue receipt -> v0.51 acknowledgement admission -> v0.50
acknowledgement prerequisite -> v0.49 claim admission, continuing unchanged
through every v0.48-v0.20 predecessor listed in that normative lineage. Preserve
all recursive IDs, owners, times, limits, abstract worker/binding/queue references,
record/status/subject/key fingerprints, adapter receipt and claim/lease/
acknowledgement receipt fingerprints. There is no separate v0.52 receipt ID;
`admission_id` is shared with v0.51, not the v0.54 admission ID. Do not invent
production UUIDs or digests: release commit identity is not per-record identity.

Reparse even constructed/copied models with strict literals and forbidden extras.
Validate with v0.55 `runtime_plan_record_fingerprint`, `status_fingerprint`,
`subject_fingerprint`, `derived_runtime_plan_id` and `derive_status`, and each
predecessor's own versioned validators. V0.55 subject binds exactly `operator_id`,
`candidate_record_id`, `runtime_admission_id`; its hash domain is
`atlas:worker-activation-runtime-plan-{kind}:v1`, ID domain
`atlas:worker-activation-runtime-plan-id:v1`. Preserve `sha256` and
`atlas-jcs-nfc-v1` metadata. Require paired status equality with
`derive_status(record, evaluated_at=status.evaluated_at)`. Never regenerate,
normalize, summarize, reparent, rebind, widen or truncate inherited evidence.

The reader may derive stable status at plan `recorded_at`, following the released
reader pattern. Independently require active eligibility at trusted whole-second
UTC Core time: no future record/status, status before recording, clock rollback,
age beyond 30 seconds or `now >= valid_until`. Historical nested eligibility stays
at its original validation time. Review expiry equals pinned plan expiry and
cannot exceed any inherited expiry or 30 seconds after review recording. Refuse
missing, foreign, ambiguous, stale, expired, corrupt, altered-authority,
fingerprint-mismatched or unsupported-capability evidence. Home Assistant remains
blocked without installation artifacts. No freshness renewal or older fallback.

The new schema is `worker-activation-runtime-plan-review-v1`, with distinct UUID5
`runtime_plan_review_id` and `runtime_plan_review_record_fingerprint`. Permanent
review subject binds exactly owner, candidate and v0.55 `runtime_plan_id`;
expiry, status, request and key changes never yield a new subject. Use separate
`atlas:worker-activation-runtime-plan-review-{kind}:v1` domains for subject,
request, record, evaluation, status, collection, idempotency-key, reservation and
audit, and `atlas:worker-activation-runtime-plan-review-id:v1` for UUID5.
Predecessor subject/key fingerprints are evidence, never successor keys.

The closed review profile is `core_owned_reference_only_runtime_plan_review_v1`.
A successful review records only the fixed findings `exact_plan_lineage`,
`fixed_design_consistent` and `unresolved_interfaces_preserved`, in that order.
They are computed checks, never caller claims. Verify every design literal in
`WorkerActivationRuntimePlanDesignV1`: Core evidence owner, owned admission
reader, separate plan journal, read-only presentation, exact embedded admission
references and both contact interfaces `undefined`. Its `unresolved_interfaces`
and every success blocker list equal the seven blockers below. Failure emits a
bounded redacted refusal, never a partial successful review or repair proposal.
No free-form findings, executable configuration, script, graph, endpoint, path,
command, credential, token, selector, payload, adapter choice or start input is
representable beyond immutable historical evidence. P1 rejects unknown fields.

## Unchanged authority ceiling

`evidence_only=true`, `reference_only=true`, `payload_bytes=0` are mandatory.
All 67 released `ClosedAuthorityV1` false authority/material fields listed in the
[v0.55 authority ceiling](worker-activation-runtime-plan-v1.md#authority-ceiling)
are incorporated here normatively, unchanged on all create/evaluation/record/
status/result/collection/reservation/audit/error models and recursive evidence.
Strict booleans and material values reject string/numeric coercion. The only
newly true marker is `worker_activation_runtime_plan_review_recorded`.
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

Runtime definition/activation, store/runtime/worker/queue contact, discovery,
registration, queue claim/lease/ack/consume/requeue/mutation, payload construction/
serialization, worker-start admission and its construction, execution-start
admission construction, worker start/invocation, Agent invocation, execution
authorization/start, process/shell execution, scheduler/workflow/dispatch,
provider/repository/in-guest mutation, installation, deployment, rollback,
publication/tag push/release, retry/resend, repair and replay bypass stay blocked.
No installation artifacts are supplied. Core-local evidence journal I/O is not
worker-store or runtime contact. Review is never a `WorkerExecutionRequest`.

## P1-P5 responsibilities and exit gates

P1 implements the pure evidence contract and P2 implements isolated durable
evidence persistence; P3 adds the guarded default-off API. P4-P5 remain pending. Implement only
this evidence ceiling, in order.

| Phase | Responsibility and required evidence |
| --- | --- |
| P1 | Pure immutable closed review models/evaluator, exact v0.55 pair, deterministic findings and domain/ID vectors. Test complete recursive lineage, strict authority, model-copy/construct bypass, extra/duplicate fields, unsupported capability, stale/future/expired/foreign/mismatched evidence and refusal without marker advancement. No I/O, clock reads, runtime imports, API or settings. |
| P2 | Explicitly constructed default-off Core service, owned durable v0.55 reader and separate bounded append-only SQLite review journal. Preserve all persistence requirements below. Test durable predecessor byte equality, quotas, locked drift, multi-process contention, corruption, partial writes, crash/audit/response loss and restart/expiry no-replay. No production construction or runtime adapter. |
| P3 | Guarded evidence-only POST/GET collection under `/api/v1/installation/candidate-records/{candidate_record_id}/worker-activation-runtime-plan-reviews` and item GET `/{runtime_plan_review_id}`. Dedicated `installation.execution.worker_activation_runtime_plan_review.evaluate` and `.read` permissions; authenticated owner/candidate, trusted Origin/CSRF on POST, 16-128 visible ASCII Idempotency-Key, strict JSON 16 KiB/nesting 16. Reparse and bind responses to exact scope/request/predecessor; collections maximum 16 and 192 KiB. Missing service 503, disabled create/replay conflict 409, foreign/missing 404, throttling 429; redacted non-retryable errors. Test methods, auth, ownership, bounds and hostile responses. No enabling setting or action/start endpoint. |
| P4 | Nested Mission Control GET-only review beneath the exact v0.55 plan; verify schemas, immutable predecessor, ownership/IDs/fingerprint metadata, lifecycle, findings, seven blockers and false authority. Core owns canonical hashes and current-time eligibility. Clear on scope change, ignore late responses, distinguish loading/missing/unavailable/expired. Say “Plan review is evidence; runtime prerequisites remain incomplete.” Collapse technical evidence. No creation/action control, polling, browser persistence, navigation or Agent/worker/execution control. Test hostile fixtures and scope races; run UI tests/build/lint. |
| P5 | Prove durable v0.55-to-v0.56 byte-exact recursive lineage, strict authority, permanent reservation and restart no-replay. Lock exact Core/API/UI consumers and zero Agent/execution-worker consumers. Run P1-P4 suites, historical closure/isolation/scope and Home Assistant golden checks, Core Ruff, UI gates, documentation consistency and hostile diff review. Record actual results and limitations; closure adds no runtime behavior or enablement. |

P2 inherits the [v0.55 persistence requirements](worker-activation-runtime-plan-v1.md#persistence-replay-ownership-concurrency-and-corruption):
owner-scoped key and permanent subject reserved atomically under SQLite write
serialization and FULL synchronous durability; committed reservation precedes
terminal record/audit append. Re-read the exact prerequisite and trusted time
under both write locks, before reservation and immediately before append; drift
fails closed. At most one reservation/record per subject across processes.
Exact duplicate returns unchanged history plus current status without predecessor
read, append or renewal; changed request/key conflicts. Reservation survives
expiry, restart and response/audit loss. Post-reservation failure is terminal
indeterminate, never resumed, released, replaced, evicted or repaired.

Limits only lower: 16 reservations per owner, 256 globally, 192 KiB per serialized
model, one terminal audit per reservation, 256 MiB main SQLite pages (not a total
filesystem quota). Incomplete reservations count; excess lineage refuses without
truncation. Validate schema/indexes, row/model linkage, ownership, hashes and
bounds on every connection; corruption closes reads and writes. Preserve bounded
redaction, duplicate-key rejection and foreign/missing indistinguishability.
No raw keys, secrets, exceptions, environment dumps or material in logs/store/UI.
Predecessor databases/reservations are never mutated or consumed by review.

Agent and execution-worker retain zero review consumers/imports/routes/settings/
clients/adapters. Preserve independent intent registries, approvals, authentication,
relay/backend defaults and no-replay ledgers. No translation into repository
workflows, Provider Intent or operational dispatch. Future historical allowlist
updates must name exact evidence-only surfaces with proof, never wildcards,
weakened scanners or relaxed fingerprint-only AST import rules. P0 changes none.

## P0 verification and change scope

P0 modifies only this architecture contract, ROADMAP and release-planning evidence.
Verify tag/ancestry, exact model fields/domains, inherited 67 false values, seven
ordered blockers, links and phase responsibilities. Run focused released plan
contract, durable closure, UI structural isolation and historical installation
release/isolation checks. Run documentation consistency, `git diff --check`, then
hostile review of the complete diff and create a real local documentation commit.
No production code, tests, settings, consumer allowlists or
`compose.execution-smoke.override.yaml` changes. No push, tag, release, publish,
deploy, runtime probe or Agent/worker invocation. Historical UI/full-suite/external
limitations remain recorded; this P0 does not claim those gates passed.
