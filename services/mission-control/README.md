# Mission Control

Mission Control is the Atlas OS operator interface: a React, TypeScript, and Vite application backed by Atlas Core API v1 and the proxied Atlas Agent API.

## Current surfaces

- Infrastructure dashboard with Atlas, inventory-service, health, policy, finding, recommendation, and intelligence summaries.
- A read-only provider registry at `/providers`, with local name search, refresh/retry, and links to the existing provider detail screens.
- Provider workspaces for connections, resources, monitoring status, Provider Intent editing, intent suggestions, diagnostics, provider-advertised legacy actions, and filterable action history/detail.
- Discovery browse and item detail views with relationships, compatibility, dynamic evidence, freshness/health/conflicts, installed-version evidence, release evaluation, Compose/image evidence, grounding, and provenance.
- The additive v0.15 Image Grounding panel presents status, release, deployment binding, observed image, accepted evidence, source class, source identity, and attestation time. It is advisory, grants no deployment or execution authority, and adds no action controls.
- Discovery proposals with bounded navigation into supported next-step surfaces; proposals do not execute or approve work.
- Execution-candidate browsing, planning sessions, workflow-shell intake, exact repository approval stages, execution/verification/review/commit artifacts, workflow dashboards, timelines, and audit-chain views.
- Operational maintenance request preparation, operational lifecycle/history, recovery guidance, diagnostics, and support-bundle access.
- Core-owned operator login and session handling for protected mutations.
- Forge deployment analysis and planning views.

Mission Control presents and submits requests to authoritative backend contracts. It does not itself execute infrastructure changes, decide approval, expand intent sets, or bypass server-side identity, permission, target-fingerprint, and exact-approval checks.

Released mutation authorities remain separate: Provider Intent is monitoring-policy only; legacy provider actions use their provider surface; repository execution is exactly `update-compose-stack`; hardened operational dispatch is exactly `restart-service / proxmox / qemu`. Discovery is GET-only/read-only. There is no automatic approval, remediation, update, deployment, rollback, or release publication.

Screen recovery keeps shared navigation available for missing pages and page
rendering failures, with plain-language recovery actions. An initial workflow
load failure offers a read-only retry. Provider absence is shown only after a
successful catalog load; a loading or unavailable catalog is not reported as a
missing provider. Maintenance history keeps unavailable diagnostics findable,
leaves recovery guidance visible, and places secondary metadata under optional
workflow details. Local filters can be cleared without fetching or executing
work, and empty later pages retain a route back to earlier results. These
presentation changes grant no new action authority.

Proposed-change screens keep loading and planning state scoped to the proposal
in the current URL. Mismatched response identities are refused, late results
cannot attach to another proposal, and malformed explicit expiry times keep
planning unavailable. Optional expiry remains supported. The planning entry
uses plain-language labels and still sends only the candidate ID for backend
revalidation; it grants no approval or execution permission.

Planning and workflow summaries also keep state tied to the current session.
Responses for another session or plan are refused. Failed workflow validation
removes cached action controls, and late implementation or recovery responses
cannot navigate away from a newer session. Planning requires the backend's
explicit availability flag; missing saved plans offer a reload instead of
presenting another generation action. Workflow creation and later exact
approvals remain separate steps.

The exact-approval workflow detail resets when its URL changes and rejects
details bearing another workflow ID. An unavailable read offers a read-only
retry and a link to the workflow list; retry does not submit approval or resume
an execution.

Read-only workflow audits and Discovery details reset when their subject URL
changes. Audits check both reported workflow identities. Discovery checks the
catalog, relationships, compatibility, source evidence, image grounding and
installation plan against the requested item before displaying them. A missing
catalog item requires a 404 from the catalog read itself; supporting-read
failures remain unavailable information. Failed reads offer a retry or reload
and retain a way back. These displays do not grant installation authority.

Operator sign-in returns to the supported maintenance selector. Discovery
navigation preserves only a validated advisory proposal ID across sign-in,
then reloads its current status; target hints, selected resources and approval
fields are never carried forward. Arbitrary return destinations are ignored.
Leaving a pending sign-in does not navigate the operator back afterward, and
unexpected sign-in failures clear the password and offer a controlled retry.
Browser coverage uses a separate fixture allowing only an exact synthetic
login; all operational mutations remain rejected. No real credentials or
maintenance actions are used by these checks.

The overview places operator attention before the six status cards and recent
activity. Source failures remain visible and name the affected source. Runtime
inventory and historical execution observations are expandable with the
keyboard; provider health, unknown runtime readiness, active and blocked work,
and freshness warnings stay in the main view. Expanding observations performs
no requests and changes no execution or approval state.
Approval waits use workflow-stage labels rather than degraded-health badges.
Stale approval requirements remain explicitly last-known, and workflow stage
update times remain unknown when the source does not supply them.

Provider-action audit details and installation readiness reviews reset when
their record URL changes and reject responses for another record. Read-only
retry controls recover failed reads without submitting permission evidence or
starting work. Changing readiness candidates also clears any open evidence
confirmation. Provider-action history links remain shareable while records
are retained; they do not promise permanent storage.

Provider action, connection and monitoring panels reset when the provider
changes. Previous action parameters, connection form values and secrets, and
monitoring selections cannot appear under the next provider. Late action
results do not populate or refresh a different provider's panel. Previously
submitted actions remain associated with their original provider and its
recorded action history. Confirmation and backend permission checks remain
in their existing controls.

Browser acceptance covers the repository-change journey from a current
proposal through planning, implementation approval, verification approval,
local commit approval and the completed audit. A separate synthetic backend
fixture accepts only the exact ordered request paths and bodies expected by
that journey. Each approval requires a separate Resume step; rejection remains
blocked after reload. Current-stage prompts follow the refreshed server state
and disappear when the workflow advances. These tests run no model, command,
verification tool, Git operation or provider action and do not establish
production acceptance.

Workflow status checks pause during an in-flight check or operator action.
Approval and Resume controls stay disabled until the current check finishes,
with a visible checking message. A read attempt publishes the workflow and its
maintenance projections together; superseded responses are ignored, and
projections bearing another workflow ID are refused. An absent optional
diagnostic stops loading when the read finishes. Resume keeps its pending
status visible without allowing duplicate submissions. These are presentation
and read-coordination rules; backend approvals still govern every effect.

Mission Control completion requires the supported operator journey to have
working navigation, useful empty and unavailable states, recovery controls,
and readable layouts on desktop and mobile. Proposal, planning, workflow and
exact-approval screens must keep displayed evidence and actions tied to the
current server-validated subject, including when responses arrive late or
refreshes fail. Regression checks cover these cases without granting real
execution authority. Deferred screens and capabilities remain outside this
completion scope. Source validation does not establish production acceptance.

The menu separates Action history (recorded provider actions), Maintenance
history (past maintenance requests), Request maintenance (start a request), and
Change proposals (review proposed work). Existing addresses remain valid. Only
the destination that owns the current page is highlighted; audit details remain
under Action history.

Secondary screens load on demand. Navigation stays available while the next
screen loads, and the previous screen's controls pause until navigation finishes.
If a screen module cannot load, the recovery view offers a page reload and a
return to Mission Control. Reload retries the module after the connection or
asset availability is restored; it does not resubmit an operator action.

The deferred v0.65 successor control-plane projection is absent. Mission
Control has no client, route, nested view, or action surface for that
unselected API; retained v0.64 GET-only evidence must not be promoted or
relabeled as v0.65.

Historical release reference: Atlas v0.15.0 was recorded as `atlas-v0.15.0`
at `850480ce6c5f86a5bf4a783e33f7e08a7f29a2ab`. This historical reference does
not establish acceptance of the current branch.

The [screen recovery review](../../docs/mission-control/screen-recovery-review.md)
maps the current operator outcomes to regression checks and identifies the
remaining acceptance gaps.

## Development

Use Node.js 20.19 or newer (Node.js 22.12+ recommended) and npm 10 or newer:

```bash
npm ci
npm run dev
```

The development server proxies `/api/v1` to Atlas Core at
`http://127.0.0.1:8643` and `/agent-api` to Atlas Agent at
`http://127.0.0.1:8090`, removing the Agent prefix as the production edge does.
Both proxies strip caller-supplied identity headers and preserve session cookies,
origin and CSRF headers; backends still authenticate and authorize requests.
Core and Agent must already be running for real integration; the proxy does not
start either service. The proxy regression test uses ephemeral local HTTP stubs.

To preview Mission Control from another device on a trusted LAN, bind Vite to the
host's network interfaces:

```bash
npm run dev -- --host 0.0.0.0
```

Open the `Network` URL printed by Vite on the other device. Core and Agent remain
on the machine running Vite because the API proxies still target loopback. Allow
the printed port through the host firewall only for the trusted LAN if needed.
The Vite development server is for local development, not public or production
access.

Validate with:

```bash
npm test
npm run lint
npm run build
npm run test:e2e -- --workers=2
npm run test:e2e:built -- --workers=2
```

The existing Quality gates workflow also installs Chromium and runs the
simulated browser journeys with two workers. It then reuses 42 compatible
journeys against generated assets through a temporary local preview, including
repository and maintenance approvals, sign-in, readiness, analysis and navigation.
The fixtures remain bound to the configured test origin and exact expected
requests. Only development-specific source-module tests stay in the dev suite.
Run the build before the built-asset checks. This preview checks frontend assets,
not production Nginx routing or a running Atlas backend.
Browser failures retain a screenshot
and trace in a seven-day workflow artifact. The fixtures reject unexpected
mutations; these checks do not exercise a real provider or deploy Atlas.
The build type-checks the browser tests as well as the application. Candidate
fixtures include the backend-required effect kind, and audit fixtures keep the
workflow-preparation approval separate from implementation approval.


The v0.57 interface prerequisite inventory is displayed beneath the exact v0.56
runtime plan review. It reads Core collection/item evidence with credentials,
preserves immutable review lineage, and displays Core-reported expiry. All
runtime prerequisites remain incomplete. Advanced evidence stays collapsed;
there are no create/start controls, polling, browser persistence or new routes.

An earlier v0.57 worktree recorded a dependency-install failure (`EAI_AGAIN`).
That historical environment note is not the validation status of the current
branch; see the screen recovery review above for the current review scope.
