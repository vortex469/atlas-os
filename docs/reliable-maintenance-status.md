# Reliable maintenance status in Mission Control

Maintenance history must keep requests with missing recovery reports visible when
Status is set to Unavailable. A missing report (HTTP 404) remains distinct from a
failed or unreadable response: neither establishes an operational failure.

Completion filters require an explicit boolean from the matching lifecycle.
Missing lifecycle evidence is neither Finished nor In progress. Clear filters
returns to the complete current page. These filters still apply only to the
bounded page, as stated by the empty-results message.

The shared recovery-diagnostic reader checks the existing Agent response contract
before returning evidence to history or workflow detail. It requires the requested
workflow identity, all required nested facts, controlled status/reason/action
values, and correctly typed nullable evidence. Missing fields, unknown controlled
values, and foreign identities produce a fixed owned error without displaying raw
response data. Valid unavailable and non-applicable reports remain readable;
additive response fields remain compatible. This validates the response shape,
not the truth of remote facts or production acceptance.

No request, approval, dispatch, reconciliation, recovery action, or execution
permission changes. Filtering and disclosure remain local read-only interactions.

Validation covers complete reports, nullable and non-applicable evidence, absent
required fields, malformed/foreign responses, 404 versus service failure, missing
completion evidence, and read-only phone/desktop browser journeys at 320, 390,
and 1280 pixels. The browser cases use both missing reports and incomplete reports
that claim a healthy status, exercising the real response reader.
