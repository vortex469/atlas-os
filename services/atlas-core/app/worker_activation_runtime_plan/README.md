# v0.55 Core runtime plan evidence (P1-P5)

The service is explicitly constructed and creation is default-off. Its only I/O
is a separate Core-local SQLite plan journal and an injected owner-scoped v0.54
admission reader. Production startup does not construct or enable this service.
The guarded P3 API accesses only an explicitly injected service.

`WorkerActivationRuntimePlanPrerequisiteStoreReader` accepts a durable v0.54
store and trusted whole-second UTC clock. It reads the exact owned admission ID,
checks its pinned expiry and freshness, reparses the complete immutable record,
and derives the stable status at the original recording time. The service
revalidates the complete pair and the P1 request under both SQLite write locks.
The predecessor store and its permanent reservations are never changed.

The journal commits an owner/key and permanent owner/candidate/admission subject
reservation before the terminal record/audit transaction. Only the reserving
call may append. An interruption leaves a permanently indeterminate subject;
there is no resume, eviction, retention deletion, repair or retry. An exact
key/request duplicate returns the unchanged record and current status without
reading predecessors, even after expiry. Other key/request or subject reuse
conflicts. SQLite `BEGIN IMMEDIATE` serializes independent processes and FULL
synchronous commits preserve reservations across restarts.

Limits can only be lowered: 16 reservations per owner, 256 globally, 192 KiB per
serialized model and 256 MiB of main database pages. Incomplete reservations
count. Capacity exhaustion refuses new reservations without eviction. The page
bound is not a filesystem or journal quota. Every connection verifies the exact
schema/indexes, SQLite integrity, canonical models, hashes, ownership/linkage,
terminal audit exclusivity and configured bounds. Corruption closes all reads
and writes. Public failures contain only closed non-retryable error codes and
opaque correlation fingerprints.

The P1 deterministic projection and all seven inherited blockers remain intact.
Runtime, queue, worker-store, worker-start, Agent and execution authority remain
false. P4 supplies nested GET-only Mission Control evidence; P5 locks durable
lineage, restart no-replay, exact consumers and normative authority inventories.
See the [normative contract](../../../../docs/architecture/worker-activation-runtime-plan-v1.md)
and [release checklist](../../../../docs/RELEASE_CHECKLIST.md) for final semantics
and observed validation, including environment limitations.

## P2 validation (2026-09-08)

Baseline `2a954613085e5216bee528858765366166447c0b` contains the committed P1
contract and is an ancestor of this work. Using the selected Python interpreter
with `PYTHONPATH=services/atlas-core`, focused pytest validation passed:

- v0.55 `test_service_store.py`: 60 tests, including independent-process races,
  both locked revalidation boundaries, durable predecessor byte equality,
  corruption, bounds, restart, response loss and permanent no-replay.
- v0.55 `test_contract.py` plus v0.54 `test_contract.py`,
  `test_service_store.py`, and `test_release_closure.py`: 213 tests.
- Atlas Core's baseline-aware Ruff gate (baseline `0216b7bf`): passed.
  An unrestricted Core scan has 84 existing findings outside this change.
- Hostile diff review and whitespace checks passed. Exact consumer scans confirm
  zero production construction and zero Agent/execution-worker consumers.

Existing Pydantic schema-shadow/deprecation warnings remain. No runtime or
external deployment validation was performed or implied.

## P3 guarded API

The versioned Core router registers exactly POST/GET collection
`/api/v1/installation/candidate-records/{candidate_record_id}/worker-activation-runtime-plans`
and GET item `/{runtime_plan_id}`. The dedicated permissions are
`installation.execution.worker_activation_runtime_plan.evaluate` and
`installation.execution.worker_activation_runtime_plan.read`.

Creation requires an authenticated operator, trusted Origin, CSRF token and one
16–128 visible ASCII character Idempotency-Key. JSON is closed, duplicate-key
rejecting, limited to 16 KiB and nesting 16. The service revalidates the exact
owned v0.54 lineage under both write locks. Routes reparse all service outputs,
including errors and constructed/copied models, and bind owner, candidate,
item identity, predecessor fingerprints, expiry and idempotency fingerprint.
Collections retain the P1 limits of 16 items and 192 KiB per model.

Missing service returns 503; disabled creation and replay conflicts return 409;
foreign/missing items return indistinguishable 404 errors; throttling returns
429. Errors are bounded, redacted and non-retryable. Exact duplicates preserve
historical evidence and return current status without rereading predecessors.
No production service construction, enabling setting or runtime primitive is
introduced. All downstream effect authority remains false.

## P3 validation (2026-09-08)

P2 commit `708b880c91a64d3c56e345b74c6d543ddb37f1b1` is the task baseline;
`git merge-base --is-ancestor` confirmed the dependency. Tests ran from the task
worktree with the selected interpreter and `PYTHONPATH=services/atlas-core`.

- Focused tests passed: all 40 v0.55 route/security tests (38 initial tests plus
  two oversized-envelope regressions). The OpenAPI/startup checks also passed
  again after the final router registration placement.
- v0.55 P1/P2, v0.54 contract/service/store/closure/UI-isolation/API, and historical
  installation release-isolation regressions: 376 passed in the combined run.
  Its three consumer checks had loaded their old allowlists before the P3 edits;
  all three passed in a fresh run with the exact new route explicitly named.
- Supplemental operator-auth and v0.53 non-durable closure checks: 23 passed,
  one durable test deselected. The legacy threaded TestClient stalled and was
  interrupted; rerunning with the existing thread-free ASGITestClient injected
  in memory passed. No repository test transport was changed.
- Atlas Core baseline-aware Ruff (baseline `0216b7bf`) and `git diff --check`
  passed. The unrestricted scan retains the 84 pre-existing findings noted in P2.
- Hostile review passed: exact methods, auth/scope checks, request and response
  bounds, immutable lineage, redacted failures and permanent no-replay remain
  enforced. Consumer scanners retain exact allowlists and unchanged detection;
  there is no production construction or Agent/execution-worker consumer.

The smoke compose override is unchanged. No runtime/effect authority, push, tag,
release, publication or deployment was introduced or performed.
