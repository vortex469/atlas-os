# Complete read-only workflow directory

The dashboard previously fetched the first 200 summaries and then searched,
counted and paginated that partial collection in the browser. Workflows outside
that collection could not be found, and summary cards understated totals.

The existing `GET /api/v1/agent/workflows` endpoint now returns `state_counts`
for every matching raw lifecycle state before pagination. Counts and items are
computed from the same exported workflow-state snapshot. Existing state,
source, candidate ID, workflow ID and effect-kind filters remain supported.
The optional boolean `waiting_for_approval` selects the four existing approval
wait states, or their complement. It describes persisted state; it does not
prove that an approval request is currently actionable or grant permission.
No approval or execution request models change.

Mission Control sends submitted filters and page offsets to Agent and displays
ten records per page. Summary cards use the complete matching counts, including
the generic approval-wait state previously omitted from the cards. The filter
and cards say “Waiting for approval,” avoiding an implication that a blocked
workflow needs no operator attention. Roadmap, manual and candidate sources can
all be selected. All operations on this screen remain reads and detail links.

Same-query refreshes do not overlap. Search controls remain usable during a
pending read, while the old results and totals are hidden. A new search
supersedes the response of an older request; late success or failure cannot
replace the newer results. Leaving
the screen invalidates pending responses and stops polling. Polling considers
active states across the matching collection, including records on another page.
A failed refresh retains the last loaded page with a visible failure message.

The client checks page bounds, duplicate IDs, aggregate totals and agreement
between the page's states and the counts. A page emptied by deletion can trigger
one corrective read at the last valid offset. Further churn produces a retryable
screen error, rather than an unbounded read loop. Each page is a fresh snapshot;
this does not freeze the collection across multiple requests.

Older Agent responses without `state_counts` can still provide server paging
and the existing search filters. Their summary cards say “Unavailable,” rather
than showing partial counts as complete. Approval-wait filtering fails visibly
on that older contract and offers a working clear-filter action. No local
filter of a partial page substitutes for a complete server-side search.

Acceptance covers more than 200 records, complete filtered counts, off-page
activity refresh, query changes during refresh, late replies and failures,
initial retry, unmount/Strict Mode, shrinking pages, malformed totals and the
older contract. Native API tests assert unchanged stored state and no execution
or approval writes. Browser fixtures permit exact-origin reads only and verify
search and approval-wait filters on phone and desktop widths. Deployment and
runtime acceptance remain separate work.
