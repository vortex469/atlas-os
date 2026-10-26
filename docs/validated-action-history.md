# Validated and consistent action-history reads

Mission Control now checks the existing Core read responses before showing audit
records, page totals, retention policy or provider choices. Malformed successful
responses are loading problems, not evidence that an action succeeded or failed.
The existing refresh/retry buttons repeat reads only. The accepted layout is
unchanged.

The reader checks required facts, controlled outcome values, matching detail IDs,
finite nonnegative duration, real timezone-bearing dates, unique record/provider
IDs, and safe integer bounds. A status that contradicts its success flag is
unreadable evidence. Page offset and limit must match the request; page size,
total and has-more must agree. Returned provider/status values must match their
requested filters. Search semantics and remote fact truth remain Core-owned.

Published optional defaults remain compatible: absent parameter names become an
empty list, absent request correlation becomes null, absent empty-page items
become an empty list, and optional retention timestamps become null. Required
outcome facts never receive defaults. Additive response fields remain compatible.
Fixed owned errors contain no reflected response fields. HTTP failures, including
404, remain failures rather than fabricated empty reports.

Core previously assembled a page through separate list and count transactions,
pruning retention in each. A controlled retention-boundary test reproduces a
nonempty page with a zero total in the old implementation. Core now prunes once
and reads rows and count under the same lock and SQLite transaction. Both use the
same filter parameters and ordering. This guarantees one page snapshot, not a
frozen history across requests or across the independent optional metadata reads.
Older Core responses that contain inconsistent totals now fail visibly and can
be refreshed; the client does not manufacture replacement counts.

A synthetic JSON fixture generated from Core's dedicated DTOs is round-tripped
by native model tests and read through all four real UI API helpers. Further
coverage includes retention advancing between reads, another repository
appending during a page read, matching filters, malformed/partial records,
contradictory outcomes, out-of-range pages, invalid optional metadata, identity
mismatches and phone/desktop read-only recovery. Browser fixtures reject mutations.

No database migration, API route/request schema, approval, provider action,
cleanup request, export contract or execution capability changes. Existing
retention ownership and cleanup confirmation remain in place. Production runtime
acceptance and deployment are outside this change.
