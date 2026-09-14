# Local AI runtime overview integration

The current dashboard's single Local AI / Runtime card presents the configured
Atlas AI provider's health, installed and running model identities, health latency,
and runtime version from `GET /ai/status`. `LocalAiContent` consumes `evidence.ai`
from `useOverviewEvidence`; it makes no requests and owns no refresh lifecycle.
Core's `AIControlService.status` remains the authority for provider selection,
health, and inventory observations.

This semantically integrates commit `fc7dbbeb` without restoring its old dashboard
or independently fetching adapter. Shared 30-second polling and dashboard refresh
retain failed observations as explicitly stale, then replace them upon recovery.
Stale health is unknown and cached version, latency, and inventories are labeled
last-known. HTTP failures (including 404, 501, and 503) mean observation unavailable,
never proof that a runtime is offline; raw errors are not displayed.

Explicit configured provider health uses the shared healthy/degraded/unavailable/
unknown presentation. Provider health does not establish local runtime availability:
locality and dedicated runtime capability are not published by this endpoint.
Configured model identity remains unknown. Installed/running inventories do not
establish model selection, inference readiness, active execution, or current loaded
state. No status is inferred from `provider.online`, inventory counts, or missing
fields. Failed inventory actions, malformed lists, and missing inventories remain
unknown rather than zero. Explicit empty lists with no error mean none reported.
Partial model identities are marked incomplete; compact lists disclose truncation.

Only selected display fields render. Sensitive text is withheld, raw error bodies,
endpoints and arbitrary health details are omitted, and provider links use the
existing strict provider-ID validator. Models are labels, not navigation targets.
There are no SDKs, runtime connections, inference calls, lifecycle controls,
provider mutations, routing decisions, or alternate execution paths.

The existing six-card responsive layout, unified system health, worker/execution,
agent/provider overview, and source-condition attention deduplication are retained.
Runtime health is scoped to the configured provider, not a second AI aggregate.
Behavior tests cover malformed/absent/stale evidence, health states, inventories,
redaction and navigation; structural tests enforce shared observation-only wiring.
