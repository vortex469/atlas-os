# v0.56 P1-P5 Core runtime plan review evidence

`contract.py` implements the [frozen P0 contract](../../../../docs/architecture/worker-activation-runtime-plan-review-v1.md)
as pure immutable models and deterministic validation. The sole new true marker
is `worker_activation_runtime_plan_review_recorded`. Successful review recognizes
one plan and records exactly `exact_plan_lineage`, `fixed_design_consistent`, and
`unresolved_interfaces_preserved`. All seven blockers and 67 false authority and
material fields remain unchanged. Review is evidence consistency, not design
approval or runtime readiness.

The input pins one complete v0.55 plan/status pair, authenticated owner,
candidate, permission, trusted whole-second UTC time and explicit unreserved
subject/key facts. Every nested model is reparsed, including copied/constructed
instances; its original version validates all recursive lineage. Exact paired
status, fixed design, UUIDs, fingerprints, current freshness and inherited expiry
must agree. Failure produces bounded redacted evidence with zero recognized
plans, no findings and no review marker advancement. The pure builder revalidates
its input; it does not establish durable uniqueness by itself.

The create, authority, evaluation, record, status, result, collection,
reservation, audit and error envelopes forbid extras and enforce strict authority
types. JSON decoding rejects duplicate keys. Models are bounded to 192 KiB;
create JSON is bounded to 16 KiB and nesting 16. Collections hold at most 16
unique same-owner/candidate records. Permanent subject identity binds exactly
owner, candidate and plan ID, independent of expiry, status and idempotency key.
The nine hash domains and distinct UUID5 ID domain have frozen independent test
vectors in `fingerprint_vectors.json`.

`service.py`, `store.py` and `readers.py` implement explicitly constructed,
default-off Core evidence persistence. The owner-scoped reader returns the complete
durable v0.55 plan and stable status without modifying its journal. Both SQLite
write transactions re-read exact lineage and trusted time. FULL synchronous commit
makes the owner-scoped key and permanent owner/candidate/plan subject durable before
terminal record/audit append. A failed or interrupted append is never resumed.
Exact duplicates return unchanged history and current status without reading the
predecessor or renewing freshness, including after restart and expiry.

The separate application-ID-56 journal retains at most 16 reservations per owner
and 256 globally, including incomplete reservations; limits can only decrease.
Models are limited to 192 KiB and main database pages to 256 MiB. There is no
retention eviction. Each connection checks schema/indexes, integrity, bounds,
canonical models, hashes and row linkage; corruption closes reads and writes.
Errors contain closed codes and hashed correlation only. No raw keys are stored.

P3 exposes authenticated collection POST/GET and item GET under
`/api/v1/installation/candidate-records/{candidate_record_id}/worker-activation-runtime-plan-reviews`.
Dedicated `.evaluate` and `.read` permissions use the
`installation.execution.worker_activation_runtime_plan_review` namespace.
POST requires a trusted Origin, CSRF token and one 16-128 visible-ASCII
Idempotency-Key. Strict duplicate-free JSON is limited to 16 KiB and nesting 16.
Every response is reparsed through P1, bounded to 192 KiB (collections at most
16), and bound to the authenticated owner, candidate and requested item or exact
predecessor/key/expiry pins. Errors are closed, redacted and non-retryable.

The API accesses only the explicitly injected
`app.state.worker_activation_runtime_plan_review_service`. Missing service returns
503; disabled creation and conflicting replay return 409. Foreign/missing evidence
returns 404 and mutation throttling 429. There is no production construction,
enabling setting, Agent or execution integration. P4 adds only nested GET-only
Mission Control review beneath the exact v0.55 plan. It validates closed evidence,
shows Core lifecycle, and collapses lineage, findings, IDs and reason codes;
it supplies no creation or action control. Exact historical consumer
allowlists name the guarded route, router, permission registry and exact
evidence-only UI consumers; the
historical `FingerprintV1`-only AST restriction is unchanged.

Validation commands run from the repository root with the selected interpreter
and `PYTHONPATH=services/atlas-core`. Test evidence and review outcomes are recorded
in the [release checklist](../../../../docs/RELEASE_CHECKLIST.md).

P5 `test_release_closure.py` combines durable exact v0.55 lineage and unchanged
predecessor bytes with restart/expiry no-replay and strict false authority. It
locks the exact Core/API/UI consumers, zero Agent/worker/configuration/deployment/
script consumers, and normative authority/blocker inventories. These checks do
not construct a production service or grant any runtime or operational authority.
