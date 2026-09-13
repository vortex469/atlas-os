# Dashboard evidence boundaries

The six overview cards use existing read APIs. The shell, route context, drawer,
sidebar, and route definitions are unchanged. Attention and activity follow the
summary grid, with no dashboard execution or inference controls.

| Presentation | Existing source | Limits |
| --- | --- | --- |
| Atlas state / Core services | GET /health | Display `atlas` directly; no aggregate computed from services. No source timestamp or distinct Core-process health is supplied. |
| Worker / execution | Agent listWorkflows, first 200 records | Counts describe only the returned workflow page. No worker liveness, queue depth, admission, or idle claim. |
| Agent identity | Agent getAgentInfo | Information API is not an agent-health contract. |
| Providers | GET /providers | Configuration and reported health are separate; no provider-specific coupling. |
| Local AI / runtime | GET /ai/status | Configured AI provider health and reported running model labels. Locality, configured model selection, and the future dedicated runtime are unknown. |
| Attention | GET /ace/summary, service/provider health, workflows | Existing warning/critical/blocked findings and approval waits only. Exact source/message matches deduplicated; no fuzzy alert inference. |
| Activity | GET /ops/actions/page, first 5 records | Historical action outcomes, authoritative completion times, existing audit-detail links. Old events are historical, not proof of current failure or health. |

Each source loads independently and refreshes every 30 seconds. Failed refreshes
retain data as explicitly stale observations and suppress current health badges.
Missing, unrecognized, and malformed states remain unknown. Receipt time is never
presented as an authoritative update timestamp. Historical activity older than
five minutes is labeled as such; the threshold is a display convention, not an
Atlas health or expiry decision.

Only allowlisted identity, status, and reason fields render. Arbitrary details,
configuration, headers, endpoints, and raw exception payloads do not render.
Sensitive-looking free text is withheld. No new Core authority, API contracts,
queue operations, inference, or provider mutations are introduced.

Browser regression coverage includes 320, 768, and 1440 pixel layouts and existing
detail routes. In the managed task sandbox, browser execution was blocked by
`listen EPERM` when Vite attempted to bind 127.0.0.1:5173. Run `npm run test:e2e`
in an environment that permits the local test server.
