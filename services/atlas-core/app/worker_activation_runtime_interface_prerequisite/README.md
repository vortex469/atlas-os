# v0.57 P1-P3 Core runtime interface prerequisite evidence

`contract.py` defines the closed immutable inventory contract. `readers.py`,
`service.py` and `store.py` add explicitly constructed, default-off evidence
persistence. No production startup constructs the service. All seven blockers,
67 false authority/material fields and inherited expiry remain unchanged.

The review reader gets exactly one owner/candidate/review-scoped durable v0.56
record, strictly reparses it, checks current eligibility, and derives stable
status at the review's `recorded_at`. Create pins that status fingerprint; an
item-GET projection at another time is not a substitute. Complete recursive
predecessor evidence is retained without rewriting historical status or storage.

The separate application-ID-57 SQLite journal uses FULL synchronous transactions.
The first write lock checks key/subject absence, capacity, exact predecessor and
trusted time, then atomically reserves the owner/key and owner/candidate/review
subject. The second write lock rechecks exact predecessor and time before
appending immutable evidence and its terminal audit together. Clock rollback,
expiry and lineage drift close the append. Committed incomplete reservations are
permanent: there is no resume, repair, replacement, release or eviction.

Exact key/request duplicates return unchanged history plus current status,
including after expiry and restart, without reading predecessors. Changed
requests conflict with their key; new keys cannot replay a reserved subject.
Post-reservation append/audit/response ambiguity cannot renew eligibility.
Failure audits are bounded best effort and cannot undo a reservation.

Ceilings may only decrease: 16 reservations per owner, 256 globally (including
incomplete reservations), 192 KiB per complete model and 256 MiB of main database
pages. The page limit is not a journal or filesystem quota. Collections refuse
oversized complete evidence rather than truncating it. Every connection validates
schema/indexes, integrity, row ownership/linkage, canonical models and hashes,
and retained bounds. Corruption closes reads and writes. Errors expose only
closed non-retryable codes and opaque correlation fingerprints; raw keys and
exception details are never persisted or returned.

Run tests from the repository root with the selected Python interpreter,
`PYTHONPATH=services/atlas-core`, and `-m pytest` on this package. Persistence tests
cover durable predecessor byte equality, two-lock checks, independent process and
instance contention, restart, expiry, quotas, corruption, partial writes and
reservation/audit/response loss. P4 now includes nested GET-only Mission Control
source and regressions; its required UI validation is blocked by dependency
installation (registry DNS failure). P5 release closure remains separate work; this package confers no Agent, worker, runtime or execution authority.

P3 exposes only POST/list GET and item GET beneath
`/api/v1/installation/candidate-records/{candidate_record_id}/worker-activation-runtime-interface-prerequisites`.
Dedicated evaluate/read permissions bind the authenticated owner. POST requires
trusted Origin/CSRF and one 16-128 visible ASCII Idempotency-Key. JSON is strictly
parsed within 16 KiB and nesting 16; queries and GET bodies are rejected. Full
responses are reparsed within 192 KiB, bound to owner/candidate and exact item or
create pins. Failures remain redacted and non-retryable. Missing service returns
503; disabled creation returns 409. Production construction remains absent.
