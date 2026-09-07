# v0.52 P2 evidence persistence

Explicit construction is required; create is disabled by default. The service
reads one owner-scoped v0.51 admission and injected, already-observed redacted
adapter receipt facts. It has no queue, worker, Agent, or execution client.
The adapter fact's reservation-before-effect assertion is evidence supplied by
the reader; this service does not perform or authorize those effects.

Before committing a reservation, the service rereads the exact prerequisite
under the store's write lock and applies P1 validation at the current Core time.
It repeats this check immediately before inserting the receipt; failure after
reservation is terminal and indeterminate.
The supplied status fingerprint must still match. The optional durable v0.51
reader returns a stable recorded-time status while independently checking expiry.
An exact duplicate returns historical evidence, including expired evidence,
without rereading dependencies or writing another receipt.

The dedicated SQLite journal permanently retains reservations and receipts.
There is no eviction, release, replacement, or retry API. Limits can only be
lowered: 16 reservations per owner, 256 overall, 192 KiB per serialized model,
one terminal audit per reservation, and a 256 MiB main database page limit.
Capacity exhaustion rejects new subjects; reservations survive receipt expiry.
Every connection uses FULL synchronous durability and a serialized transaction,
validates the schema and bounded persisted state, and closes deterministically.
Corruption closes all reads and writes, including lookups whose index was damaged.

A reservation is committed before receipt append. A crash or uncertain append
leaves a permanent reservation; an exact retry may return a verified committed
receipt, otherwise it remains indeterminate. No subsequent request can reuse the
subject to make another append attempt. The store never repairs malformed state.

## P3 guarded Core API

The registered candidate-record surface is
`/api/v1/installation/candidate-records/{candidate_record_id}/controlled-worker-queue-claim-lease-acknowledgements`:
POST records receipt evidence, GET lists at most 16 owned records, and
GET `/{admission_id}` reads one owned receipt under the exact candidate.
POST requires the dedicated
`installation.execution.controlled_worker_queue_claim_lease_acknowledgement.evaluate`
permission, trusted origin, CSRF token, strict bounded JSON, and one bounded
Idempotency-Key. Reads require the corresponding `.read` permission.

Routes use only an explicitly supplied
`app.state.controlled_worker_queue_claim_lease_acknowledgement_service`.
Production startup does not construct it. Missing service returns a redacted
503; disabled creation returns 409. P1 validates request and response models,
and P2 retains exact lineage validation and permanent reservation semantics.
Exact duplicates return historical evidence without another effect or append.
No queue primitive or later effect authority is added.
