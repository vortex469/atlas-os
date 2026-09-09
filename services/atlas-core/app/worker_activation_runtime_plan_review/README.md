# v0.56 P1 Core runtime plan review evidence

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

There is no service, reader, persistence, API, setting, UI, Agent or execution
integration in this package. Replay checks consume trusted injected facts;
durable reservation, atomicity and owned reads remain P2 responsibilities.
Historical isolation tests allow precisely this contract as a v0.55 consumer and
retain the exact `FingerprintV1`-only historical import check, including hostile
extra-import tests for the new file.

Validation commands run from the repository root with the selected interpreter
and `PYTHONPATH=services/atlas-core`. Test evidence and review outcomes are recorded
in the [release checklist](../../../../docs/RELEASE_CHECKLIST.md).
