# v0.57 P1-P2 Core runtime interface prerequisite evidence

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
reservation/audit/response loss. P3-P5 API, UI and release closure remain separate
work; this package confers no Agent, worker, runtime or execution authority.
