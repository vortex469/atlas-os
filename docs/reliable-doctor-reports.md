# Reliable Doctor report display

Mission Control validates the existing Doctor response before showing it. The
status, integer score from 0 to 100, real timezone-bearing timestamp and boolean
configuration result are required. Collection checks and message arrays must
have their declared shapes. Core's optional empty arrays and null check-error
default remain compatible; additive response fields are ignored. Malformed
successful responses produce a fixed owned read error without reflecting their
contents. Transport failures are preserved and no request is automatically retried.

Core owns the reported status, score and finding impact. The browser does not
recalculate health from failed collection checks, configuration flags or finding
lists. Successful collection can still return an unhealthy service. The panel
labels that count Results collected and makes missing individual coverage explicit.
A report with no findings says that none were included, without claiming that all
services were checked. Configuration, individual collection results and notes
are available in closed Check details; critical findings and warnings stay visible.

The report timestamp and Reported score are visible. Reports more than 60 seconds
old use a neutral Needs refresh label and identify the last reported status while
current health remains unknown. This is the existing Mission Control freshness
hint, not a Core health or execution decision. One bounded relative timer ages a
fresh snapshot, accounting for its age when received. It does not poll Core and
is cleared when the snapshot changes or the panel unmounts. An old expiry callback
cannot age a newer snapshot. Moving the device clock backwards does not extend
that timer.

A timestamp ahead of the device clock when received stays unverified until a new
report is read; waiting cannot turn it into current evidence. Explicitly rerunning
Doctor clears the old report while pending and after a failed read. Refreshing,
opening the panel and opening details do not authorize provider actions or any
new execution capability. Only the existing Run Doctor button requests diagnostics.

Validation covers required and defaulted fields, malformed nested data, unchanged
Core classification, stale/future reports, clock rollback, refresh before expiry,
zero collection coverage and read-only recovery at 320, 390 and 1280 pixels. Browser
fixtures reject mutations and verify the diagnostic request count. The client
uses the controlled native error reports introduced in PR #52. Backend DTOs,
scoring, providers, approvals and runtime configuration are unchanged.
