# v0.55 Core evidence journal (P2)

The service is explicitly constructed and creation is default-off. Its only I/O
is a separate Core-local SQLite plan journal and an injected owner-scoped v0.54
admission reader. No production constructor, route, setting, worker or Agent
consumer is registered here.

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
false. P3-P5 remain separate work.

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
