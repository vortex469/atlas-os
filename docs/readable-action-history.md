# Readable and independently available action history

The Action History screen now puts recorded provider actions before export,
cleanup and health tools. Provider, action, outcome, result text and time remain
visible. Request correlation, parameter names and precise duration are in closed
technical details. Search and date/provider filters, export/cleanup, and Atlas
health checks each have a closed disclosure. UTC date semantics are explicit.
Active filters remain visible beside a Show all actions reset even when the
filter controls are closed. Opening a disclosure does not start a read, export, health check or cleanup.

Action records, retention metadata and provider choices load independently. A
slow or failed optional lookup cannot conceal already readable records. Missing
retention data disables cleanup. Missing provider choices display a scoped
message and preserve the selected provider ID, including a fallback option when
its name cannot be loaded. Refresh history retries these existing read endpoints.
Every response, including optional metadata successes and failures, is bound to
the current read generation; earlier queries cannot replace newer evidence.

History-read failures remain distinct from export and cleanup failures. The latter
stay next to their tools and leave readable records and pagination intact. Cleanup
still requires the existing confirmation and the existing Core request. Completion
refreshes the latest filter at page zero, avoiding an obsolete query captured
before an intervening filter change. No cleanup is automatically retried.

Empty searches say No matching actions and offer Show all actions. An empty page
at a nonzero offset says No actions on this page and offers Previous page, since
retention or other changes may have removed records while the operator paged.
Neither situation claims that the whole history is empty.

The backend API, permission checks, retention ownership, confirmation request,
export scope and action execution capabilities are unchanged. UI tests exercise
cleanup only through mocks; browser journeys allow exact-origin GET requests and
reject mutations. Validation includes independent pending/failing reads, stale
metadata, retained provider filters, export/cleanup errors, cleanup completion
after a filter change, empty-page recovery and 320/390/1280 pixel layouts.
Deployment and runtime acceptance remain separate work.
