# Mission Control screen recovery review

This review covers the simplification and repair work on
`codex/mission-control-screen-recovery`. It is a source and simulated-browser
review, not production acceptance or authorization to merge, deploy, enable a
runtime, tag, or publish a release.

## Operator outcomes and evidence

| Surface | Required behavior | Current regression evidence |
| --- | --- | --- |
| Shared navigation | Plain menu labels distinguish action history, maintenance history, request creation and proposals; only working destinations appear; only the owning destination is highlighted; links, mobile drawer, focus, skip link and missing-page recovery work | `e2e/navigation.spec.ts`, `e2e/app-shell.spec.ts`, `e2e/screen-recovery.spec.ts`; `src/layouts/MainLayout.test.tsx` includes maintenance/action-detail ownership and omitted future placeholders |
| Screen loading | Secondary screens load on demand; pending navigation pauses the old page's controls while keeping navigation available; module failure offers reload and home recovery | `e2e/page-loading.spec.ts` covers delayed modules, leaving a pending screen, and direct-link failure/reload at phone and desktop widths |
| Generated frontend assets | Built pages preserve the supported operator journeys, navigation and responsive shell | `playwright.built.config.ts` runs 76 compatible browser cases against the generated build; API requests remain bound to the configured origin and exact isolated fixtures |
| Development API routing | Core paths are preserved; the Agent prefix is removed; session/CSRF/origin headers are preserved and caller identity headers are stripped | `src/server/devProxy.test.ts` uses the actual Vite server with isolated HTTP stubs; no Atlas backend or mutation is involved |
| Dashboard | Attention and health remain distinct; optional detail does not crowd the main screen | `e2e/overview.spec.ts`, `e2e/dashboard-block.spec.ts`, `e2e/system-health.spec.ts`; overview and worker component tests |
| Workflow directory | Each card shows its current stage and latest result, then a plain-language next step; IDs and target references are optional details without a duplicate status field | `src/pages/WorkflowDashboardPage.test.tsx`, `e2e/workflow-dashboard.spec.ts` |
| Change proposal directory | Eligibility, change and target filters lead; category/source filters expand on demand and show when active; cards lead with the proposed change and keep references optional; submitted filters, draft edits and page position survive proposal review and return | `src/pages/ExecutionCandidatesPage.test.tsx`, `e2e/candidate-list-summary.spec.ts` |
| Change proposal details | The proposed change, target, rationale, constraints and planning boundary lead; technical IDs remain available under optional details | `src/pages/ExecutionCandidateDetailPage.test.tsx`, `e2e/candidate-detail-summary.spec.ts` |
| Providers | Registry and detail links work; unavailable data differs from absence; missing feature metadata leaves the provider view usable and does not imply there are no capabilities; resource identity, edit blockers, and monitoring suggestions use plain language; failed inventory is not shown as an empty provider; simultaneous inventory/monitoring failures name their source and do not claim inventory is visible when it failed; failed refreshes identify last-loaded inventory or settings as potentially outdated; edit access is checked before controls are enabled; action-catalog read failures differ from uncertain action results; the live dashboard provider preview identifies Atlas Core as the status source, distinguishes stale from current reports, and keeps additional providers optional; forms and late responses stay with their provider | `src/pages/ProviderPage.test.tsx`, `src/features/mission-control/AgentProviderContent.test.tsx`, `src/components/ProviderOverview.test.tsx`, `src/components/ProviderIntentEditor.test.tsx`, `src/components/ProviderResources.test.tsx`, `src/components/ProviderActions.test.tsx`, and route cases in `e2e/screen-recovery.spec.ts` and `e2e/overview.spec.ts` |
| Discovery and sign-in | Advisory context survives login without selecting or authorizing a maintenance target | Discovery/login/maintenance page tests; `e2e/operator-signin.spec.ts` |
| Catalog list | Search-result and status-check failures remain separate; error disclosures identify the failed read; unavailable metadata does not imply search results loaded or show a catalog format version | `src/pages/DiscoveryPage.test.tsx` covers independent and combined failures; `e2e/catalog-screen.spec.ts` covers the catalog at phone and desktop widths |
| Proposals and planning | Only current search results and matching proposal/plan identities appear; preparation has four simple steps | Proposal/planning page tests; proposal recovery browser cases; both workflow journey specs |
| Repository workflow | Preparation and detail summaries show current state and approval status first; reference metadata is optional; exact requests remain reviewable; each approval and its explicitly named follow-up action remain separate; rejection survives reload; audit follows completion | `e2e/repository-journey.spec.ts`; workflow detail, shell, timeline and audit component tests |
| Maintenance workflow | Explicit target selection and exact request submission return a proposal; operational plan and exact verification rules precede action approval; a separate run precedes lifecycle outcome and audit | `e2e/maintenance-journey.spec.ts`; planning and workflow component tests |
| Maintenance history and audit | Foreign workflow evidence is refused; unavailable results remain findable; maintenance audit avoids repository-only stages | History/audit component tests; history browser recovery and maintenance journey audit cases |
| Action history | Changing filters or refreshing hides previous results; failed reads do not retain an actionable retention policy; superseded responses cannot replace current results; UTC date filters are explained beside local display times; error details name the affected history operation; search, filters and page position survive opening an action record and returning | `src/pages/OperationsPage.test.tsx`, `e2e/action-history-dates.spec.ts`, `e2e/action-history-search.spec.ts` |
| Atlas Doctor | Rerunning clears the previous report; pending and failed reads cannot retain an old healthy score | `src/components/AtlasDoctorPanel.test.tsx` includes healthy-to-pending-to-unavailable coverage |
| Provider connections | Saved status appears only after settings load; failed reads can be refreshed without testing or saving; field origins use plain labels; test results lead with success or failure while diagnostics stay optional; editing inputs or reloading clears the old test result; tested secrets are redacted in result messages, diagnostic field names and values | `src/components/ProviderConnection.test.tsx` covers read recovery, source labels, collapsed diagnostics, stale-result invalidation and synthetic secret canaries, and mocks every test/save request |
| Deployment analysis | The menu and page name the task; input, findings, and proposed steps are clear; the page says it does not deploy; edited inputs invalidate results; late responses are ignored; both reported risks remain visible; unknown duration is not zero | `src/features/forge/Forge.test.tsx`, `e2e/forge-analysis.spec.ts`, shell/navigation browser checks |
| Installation readiness | Review state and plain-language blockers lead; evidence IDs, linkage fingerprints and audit fields are available under optional details; owner evidence stays bound to the current record | Readiness component/parser/structural tests; `e2e/readiness-review.spec.ts` and invalid-review browser recovery case |

Paths in the table are relative to `services/mission-control`.

The default browser fixture rejects mutations. Separate synthetic fixtures allow
only the expected login, analysis, or ordered workflow requests and reject other
mutations. Workflow fixtures simulate results: they run no model, verification
command, Git commit, deployment, or provider action.

Workflow audit responses now identify their
`effect_kind`, allowing maintenance audits to display the existing read-only
operational lifecycle. Core health reads also probe at most four inventory
services concurrently per request instead of waiting for each in sequence.
Response fields, inventory order, status rules and each probe's existing HTTP
timeout are preserved. This reduces serial waiting; it does not impose a total
request deadline or guarantee that every inventory fits the UI timeout.
No execution gate or approval contract is expanded.

## Validation snapshot — 2026-10-26

Plain-navigation follow-up, based on `cb63ceb3`:

- Full component suite: 2,578 passed, zero failed or skipped.
- Full browser suite: 67 passed against synthetic local backends. This includes
  repository/maintenance journeys, readiness recovery, delayed page loading,
  leaving a pending page, and failed-module reload recovery at phone and desktop
  widths. No real model, command, commit or provider action runs in these tests.
- UI lint and production build passed, including TypeScript checks for browser
  code. All generated JavaScript chunks are below the existing warning threshold.
- The generated HTML initially requests about 484 KB of JavaScript across the
  entry and shared HTTP-client files, compared with about 1.23 MB before screen
  splitting. Secondary screen modules load on demand. These are build artifact
  sizes, not measurements of load time on a real network.
- Core's complete health-change Quality run 40265297120 passed 5,104 tests with
  one skipped. The tested Core source tree is identical to the current branch
  (`b4c17d8ce33ffad697e246f75217751e6ccef62b`). This is source validation, not a
  completed latest-head CI gate or release acceptance record. Eight focused
  health/route/release tests and the Core Ruff gate also passed locally.

The navigation follow-up also passes 106 focused layout/history/proposal/planning
tests, all 67 development-browser checks and all 42 built-app journeys, UI lint
and build. The menu highlights only its owning destination; action audit details
retain Action history ownership. Both phone and desktop built-preview captures
passed. These are simulated source checks, not operator acceptance.

The diagnostic canary test checks that a tested secret cannot appear in rendered
field names or values. The expanded built-asset follow-up passes all 42 compatible
journeys against a completed build, including repository and maintenance exact
approvals, sign-in, readiness, analysis and navigation. The fixtures reject
other origins and unexpected requests. Development-specific source-module cases
stay in the 67-check development-server suite. This
does not establish production Nginx routing or real backend integration.

Reproduce UI checks from `services/mission-control` with `npm test --
--maxWorkers=2`, `npm run test:e2e -- --workers=2`, `npm run lint`, and
`npm run build`, then `npm run test:e2e:built -- --workers=2`. Browser tests require
the local test server and Chromium.
The development proxy regression binds isolated HTTP stubs; it contacts no
running Atlas service. The Quality gates workflow also runs browser checks and
preserves failure screenshots/traces for seven days, including built-preview
failures. At preceding head `cb63ceb3`, UI CI passed 2,577 component tests, all
67 development-server checks and 42 built-app journeys, lint and build; Agent and
container checks passed. Full CI for the navigation follow-up remains required.
The preceding Core gate has passed shards 1 and 3; shards 0 and 2 remain active.

Nine representative synthetic responses were checked against native Core/Agent
models during fixture review. This corrected candidate effect kinds and audit
preparation approval fields; it does not establish real backend integration.
A read-only inspection of existing services found Agent advertising only
`/health` and `/v1/jobs/{job_id}/code`, without the current workflow audit schema.
Core's OpenAPI read timed out after five seconds. These services cannot establish
current-branch integration acceptance; neither service was restarted or changed.

## Navigation simplification follow-up — 2026-10-28

The desktop sidebar and mobile drawer now list only destinations with working
screens. The inert Knowledge, Developer and Settings placeholders were removed
so operators do not encounter menu choices that cannot be opened. The focused
layout and structural tests pass (37 tests), the application-shell browser
checks pass (8 tests), and Mission Control lint and build pass. No routes,
backend contracts, or operator permissions changed.

## Maintenance workflow timeline follow-up — 2026-10-28

Atlas Agent supplies the same nine stage names for repository and maintenance
workflows. Mission Control now keeps the repository stage rail on repository
workflows only. Maintenance progress translates the server's
`Implementation Approval` stage to “Maintenance request approval” and omits the
repository-only Review and Commit stages. Loading, unavailable, and not-found
screens no longer show a generic repository stage rail without a known
repository workflow. The maintenance browser fixture now uses the nine-stage
Agent response, so the seven-step operator view is checked against that contract.
The maintenance detail page also names its task directly and keeps repository,
verification-approval, and commit-approval fields out of its optional details.

The focused workflow/timeline component tests pass (94 tests), the maintenance
journey passes at 320, 390, and 1280 pixels, and Mission Control lint and build
pass. The change is presentational; it does not change backend contracts,
approval decisions, execution, or audit behavior.

## Maintenance audit status wording — 2026-10-28

The maintenance audit now calls its summary “Maintenance status” and describes
request approval, readiness, execution, rejection, and completion in maintenance
terms. Repository audit wording remains unchanged. The focused audit page tests
pass (26 tests), the request-through-audit browser journey passes at 320, 390,
and 1280 pixels, and lint/build pass.

## Maintenance status panel simplification — 2026-10-28

The maintenance workflow and audit now show the outcome and safe next step first.
IDs, approval records, execution counters, verification fields, and recorded
status changes are grouped under a closed “Technical evidence” disclosure.
Outcome headings and guidance now use operator terms such as “Request result
unknown” and “Approved target changed.” The no-repeat guidance and existing
approval and execution boundaries remain in place. The focused workflow,
timeline, audit, and lifecycle tests pass (135 tests); the maintenance journey
passes at 320, 390, and 1280 pixels, and lint/build pass.

## Maintenance history stage wording — 2026-10-28

Maintenance history now calls its optional disclosure “Request details” and
shows “Request stage” with plain labels such as “Waiting for maintenance
approval” and “Completed” instead of the backend state slug. The outcome
summary remains the primary status. All 17 focused history component tests, the
history browser recovery journey at 320, 390, and 1280 pixels, lint, and build
pass.

## Maintenance history refresh recovery — 2026-10-29

Refreshing the current history page keeps the last loaded requests visible and
labels them as the last successful results if the refresh fails. The warning
states that their status may have changed. When moving to another page, results
from the previous page stay hidden until the requested page loads. The focused
history component suite passes (31 tests), and two responsive browser checks
cover refresh-in-progress and refresh-failure states at 390px and 1280px. Lint
and build pass. Refresh remains a read-only request.

## Workflow directory simplification follow-up — 2026-10-28

Workflow cards now lead with the stage, latest result and approval status.
Candidate/session IDs and repository/target references are tucked under
optional details, and the duplicate status field is removed. The focused
component tests pass (8 tests), responsive browser checks pass at 390px and
1280px (2 tests), and lint/build pass. The directory remains read-only.

## Workflow review simplification follow-up — 2026-10-28

Workflow preparation and detail summaries now keep the state and applicable
approval status visible while reference IDs, fingerprints and paths stay
collapsed. The API-only creation-time message was removed. The combined focused
workflow page suites pass (95 tests); the complete repository journey passes at
390px and 1280px (4 tests), with lint/build passing. The exact request remains
visible before approval, and each approval and Resume request remains separate;
browser writes are intercepted by the synthetic journey fixture.

## Action-history time-zone clarification — 2026-10-28

Action-history date filters now explain that the selected dates cover UTC days
while entry times use the browser's local time. The explanation is associated
with both date fields for assistive technology. The focused history suite passes
(8 tests), responsive browser checks pass at 390px and 1280px (2 tests), and
lint/build pass. The existing UTC query bounds are unchanged.

## Change proposal detail simplification — 2026-10-28

Proposal detail pages now lead with the human-readable change, target, current
eligibility, rationale and constraints. Candidate and source IDs plus evidence
references stay available under collapsed technical details. Focused component
tests pass (17 tests), responsive browser checks pass at 390px and 1280px (2
tests), and lint/build pass. The browser checks cover the default collapsed
view and confirm it adds no mutation requests. Planning still requires an
explicit operator action and does not approve or apply a change.

## Change proposal directory simplification — 2026-10-28

Proposal cards now lead with a plain-language review link, target, planning
eligibility and compatibility status. Source IDs, evidence counts, approval
level and creation time remain under optional details. The focused directory
suite passes (8 tests), and responsive browser checks pass at 390px and 1280px
(2 browser tests); lint/build pass. Opening the list and its details makes no
mutation request.

The list's common filters now use operator terms for eligibility and change.
Category and source are available under a collapsed "More filters" section,
which marks advanced filters when they are applied. The same focused suites
cover expansion, active-filter visibility, and unchanged query fields.

## Installation readiness review simplification — 2026-10-28

The review now leads with its blocked or readiness-gated state, a plain-language
explanation and ordered blockers. Evidence kinds are human-readable, and UTC
expiry times remain visible. Record IDs, hashes, blocker codes, full linkage,
audit fields and fixed authority fields remain under optional details.
Permission and admission records lead with their state and blockers; IDs,
fingerprints, linkage and authority fields are expandable. Read failures and
failed record requests have separate messages. The combined component suites
pass (15 tests), responsive browser checks pass at 390px and 1280px (2 tests),
and lint/build pass. Permission-evidence confirmation and request contracts
are unchanged.

## Dashboard work activity simplification — 2026-10-28

The dashboard's work card now uses running and blocked workflow counts. It
states that worker availability is not reported, while queue size, outcome
records and data limits remain under keyboard-operable details. Workflow status
and freshness remain explicit, and the card still does not start work. The
six-card attention-first layout is unchanged. The focused overview component
suites pass (70 tests), responsive browser checks pass (6 tests across 320px,
390px, 768px and 1440px), and Mission Control lint/build pass. The browser
fixture rejects mutations; links and request behavior are unchanged.

## Provider detail recovery — 2026-10-28

Provider details no longer crash when the catalog omits its supported-feature
list. Mission Control says that some sections are hidden, keeps the provider
overview and diagnostics available, and labels the capability list as
unavailable rather than claiming no capabilities were advertised. Eleven
focused component tests, six overview browser checks, lint and build pass. The
browser fixture rejects mutations; provider actions and permission checks are
unchanged.

## Provider detail status simplification — 2026-10-28

Provider health appears once as a readable badge; the duplicate status metric
is removed. Latency, HTTP status, priority and version remain in a four-column
wide-screen layout that collapses responsively. A focused component check and
the 390px and 1280px provider detail browser checks verify the single status
and page fit. Provider data and actions are unchanged.

## Provider registry health summary — 2026-10-28

Provider registry rows no longer show an unavailable check-time placeholder
when the catalog does not supply check times. Health state and reported reason
remain visible. The focused registry test and 390px and 1280px browser checks
cover the summary; provider reads and actions are unchanged.

## Workflow action response recovery — 2026-10-28

Implementation, verification, commit approval, and workflow resume failures now
say that Mission Control could not confirm the result, that workflow status was
refreshed, and which current status the operator should review before taking
another step. Backend error text stays under collapsed Technical details. The
existing server status refresh, approval controls, separate Resume step, and
request contracts are unchanged; Mission Control adds no retry or automatic
action. Workflow page tests cover all approval stages and resume recovery. Four
focused suites pass (107 tests). The full Mission Control suite passes (2,777
tests across 181 files), and lint, build, and `git diff --check` pass. Stale
dashboard and structural assertions were aligned with the current collapsed
source details, plain-language blocker label, and local-only list expansion.
The repository journey and overview browser suites also pass (21 tests across
320px–1440px viewports); their API calls use synthetic fixtures.
An initial full browser run against an already-running dev server reported five
failures: four assertions still expected visible details or a single-choice
filter, and provider switching timed out. The provider-switch case passed against
a fresh Vite server; after updating the stale assertions, all 133 development
browser tests passed against a fresh isolated server.

## Provider detail information hierarchy — 2026-10-28

The provider detail card leads with health, available response time, workspace,
and capabilities. HTTP response code, provider priority, version, and health
endpoint are available under collapsed Technical details; missing response
time is omitted. Focused component checks and the 390px and 1280px detail
browser checks verify the hierarchy and disclosure. Provider contracts and
actions are unchanged.

## Dashboard unavailable-state clarity — 2026-10-28

Operator Attention shows a checking message during its first read and does not
report an empty result unless current evidence is complete. Unavailable and
malformed workflow or finding data use distinct, non-duplicated messages.
Common network errors use plain-language descriptions. Compact health summaries
omit empty timestamp placeholders when the source supplies no time. The focused
dashboard and health suites pass (120 tests); four browser checks pass at 320px,
390px, and 1280px; lint and build pass. Read-only behavior and backend contracts
are unchanged.

## Work activity unavailable-state clarity — 2026-10-28

The work-activity card only shows running and blocked counts when workflow
states are recognized. Initial loading, failed reads, malformed records, and
unknown future states use one clear status message instead of repeated
unavailable or unknown count values. Last-known data and freshness warnings
remain visible after a failed refresh. Focused component and dashboard browser
checks cover loading, failure, malformed evidence, future states, and responsive
layout. Workflow reads and execution boundaries are unchanged.

## Maintenance request clarity — 2026-10-28

The target picker now says “Choose a virtual machine,” labels each VM’s state,
and explains why an unavailable VM cannot be selected in operator language.
The result says a restart proposal is ready for review, confirms that nothing
has restarted, shows the expected impact and readable UTC expiry, and offers a
direct review link. Proposal IDs, target IDs and raw status values remain under
collapsed technical details. Twenty-seven focused component tests and the full
synthetic maintenance journey at 390px and 1280px pass, along with lint and
build. Target validation, request ordering, permissions and approval boundaries
are unchanged.

## Provider action recovery — 2026-10-28

Action-catalog read failures now offer a read-only reload and have their own
message. A failed action request keeps the action list visible, reports that its
result is unavailable, and links to Action history so the operator can check
before trying again. Empty catalogs use plain language. The synthetic browser
fixture now returns an empty catalog for providers without advertised actions.
Ten component tests and three browser checks pass, along with lint and build.
No action request is retried automatically, and action or approval authority is
unchanged.

## Provider connection recovery — 2026-10-28

Connection settings no longer show an "incomplete" status before Core has
loaded the provider settings. A failed read leaves the saved status hidden and
offers a plain-language refresh action. Its recovery test confirms that
refreshing performs another read and does not test or save a connection. The
field labels explain their source without showing internal identifiers such as
`atlas_yaml`. Source-label tests cover saved settings, environment variables,
missing values and absent source metadata. Existing test-result invalidation,
confirmation, and secret-redaction behavior remains covered. Test outcomes stay
visible while technical diagnostics begin collapsed; the test confirms the
redacted details can still be expanded.

## Provider resource identity wording — 2026-10-28

Provider resource cards describe identity assurance as “Provider verified,”
“Not supported,” or “Unable to verify.” The supporting text explains whether
Atlas can detect replacement, the resource type lacks a stable identity, or
the identity could not be confirmed. Inventory and monitoring disagreement
remains an explicit review state.

## Provider monitoring recovery and edit readiness — 2026-10-28

Monitoring and edit-access reads now show a pending state before values are
known; editing stays disabled while either is refreshed. A failed inventory
read retains available monitoring information without claiming the provider
has no resources, and a failed resource match suppresses the empty state.
Read-only reasons and save conflicts use plain-language descriptions while
the same server-side permissions, identity checks, and explicit Save remain in
place.

## Proxmox older settings wording — 2026-10-28

The retained Proxmox VM expectations are labeled as older settings kept for
reference. The page says they do not apply automatically to current VMs and
points operators to the current monitoring section. It no longer uses
"non-authoritative" or "resource identities" for this explanation. Focused
policy and provider-page tests, lint, and build validate the wording; provider
configuration and monitoring authority are unchanged.

## Provider check history wording — 2026-10-28

Provider telemetry now uses “Provider check history” and explains the bars,
results and time limit without the internal ACE name or “snapshots” and
“threshold” jargon. The empty state says when no checks are available. Focused
telemetry tests, lint and build cover the labels, graph description, limit and
no-limit states; collection and policy behavior are unchanged.

## Provider diagnostics wording — 2026-10-28

The provider diagnostics section now describes health and monitoring messages
without internal ACE terminology or the phrase “policy mutation.” Its empty
state simply says when there are no messages for the provider. The provider
page test covers both; diagnostic selection and action boundaries are
unchanged.

## Provider recommendations wording — 2026-10-28

Provider recommendations are labeled as Atlas suggestions, with a short
explanation that review does not change settings or run actions. The empty
state no longer mentions ACE. Provider-page and advisory-card tests cover the
suggestion label and empty state; recommendation data and action boundaries
are unchanged.

## Finding card simplification — 2026-10-28

Finding cards keep the issue and severity visible, state plainly whether it
affects system health, and place the category and score reduction under
“Technical details.” A score reduction is shown only when Core includes that
finding in health. Focused card and provider tests, lint and build cover the
collapsed details and health-impact cases; Core scoring is unchanged.

## Home attention wording — 2026-10-28

The attention panel now tells operators to follow each item's link rather than
suggesting every condition needs a workflow. Missing-data messages name the
workflow or finding information that could not be checked, and the no-issues
message keeps the limit that missing sources cannot confirm full health.
Focused overview and dashboard-block tests, lint and build cover the wording;
the six built overview browser checks also pass. Attention selection and
destinations are unchanged.

## Home health summary wording — 2026-10-28

The health summary names its three separate inputs in plain language: overall
service status, system findings, and policy settings check. The explanation says
these reports are not combined into one score and marks data over a minute old
as out of date. Focused overview tests and responsive system-health browser
checks, lint and build cover the display; health calculations are unchanged.

## Dashboard service-health labels — 2026-10-28

The main screen now calls the `/health` aggregate “Overall service status” and
the per-endpoint list “Service checks.” Its explanation says those checks do
not measure Atlas Core’s own process health. Missing check details keep operator
attention unknown instead of looking like a clear report. The AI provider card
uses a short unavailable message instead of repeating the alert and distant
Refresh control. The response and health calculations are unchanged. Focused
overview tests, responsive dashboard browser checks, lint, build, and
`git diff --check` pass.

## Health status wording — 2026-10-28

Unknown health states now say that status or check time is unavailable, and
source values are labeled “Reported status.” Timestamp labels name UTC
explicitly. Last-known status and the existing freshness cutoff remain
unchanged. Focused health and Agent/provider tests, lint, build and responsive
system-health browser checks cover current, old, invalid and missing timestamps.

## Dashboard refresh and unavailable-state wording — 2026-10-28

When a report is out of date, the badge remains “Unknown” and now says what the
last report showed and that the current status is unknown. The duplicate
“stale evidence” label is removed, and old check times read “Last checked.”
Dashboard source notes use plain language for failed refreshes and unavailable
information, and they stay hidden while the first read is pending. Recent
activity has its own checking, failed-read and last-available messages. Core
health no longer says no subsystem status was reported when its read failed.
Freshness rules and health calculations are unchanged. The focused health and
dashboard suites pass 191 tests; the complete Mission Control component suite
passes 2,635 tests. Twenty-four responsive browser checks pass across the
overview, health, unavailable-state and app-shell screens, and lint/build pass.

## AI provider overview wording — 2026-10-28

The home card is now labeled “AI provider” and describes configured provider
health and model inventory without implying that the provider runs locally or
that a model is selected or ready. Version, response time and inventory remain
under collapsed “Technical details.” Focused overview tests, lint, build and
responsive browser checks cover the wording and keyboard access; provider
evidence and action boundaries are unchanged.

## Deployment analysis findings wording — 2026-10-28

The analyzer output is labeled “Findings.” An empty list says only that no
findings were reported for the Compose file; it no longer claims that the
deployment has no security or operational concerns. A focused component test
checks the scoped empty state; analysis and deployment authority are unchanged.

## Mission Control page title — 2026-10-28

The home page title and main landmark now use “Mission Control” without the
extra “command center” wording. Shell, navigation and screen-recovery browser
checks cover the visible title and landmark; routes and page content are
unchanged.

## Deployment analysis labels — 2026-10-28

The former “Forge” menu item and page title now say “Deployment analysis.” The
page names the Docker Compose input and states that it reviews findings and
suggested steps without deploying anything. The Agent overview link uses the
same task name. Focused component, shell and route checks cover these labels;
the route and action boundaries are unchanged.

## Catalog screen simplification — 2026-10-28

Navigation and item-page breadcrumbs now say “Catalog,” and the list page says
“Browse the catalog.” Its main search shows keyword, type, and status; tag and
capability filters are under “More filters,” which marks applied filters.
Catalog format version is under optional technical details. The screen explains
that listings do not establish compatibility, install support, or permission to
make changes. Focused page, item, proposal, shell, and route checks cover these
labels and disclosures; catalog reads remain unchanged.

## Agent and provider summary wording — 2026-10-28

The Agent card says its name does not establish availability or workflow
ability. The Providers card says a saved provider may still be unavailable and
keeps connection, action-permission, and model-assignment limits under
“Technical details.” Status evidence, freshness handling, and read-only links
are unchanged; focused Agent/provider tests and responsive overview browser
checks cover the wording and keyboard-operable disclosure.

## Workflow dashboard filters and page count — 2026-10-28

The dashboard keeps workflow status and approval status visible and places
source and ID searches under a collapsed “More filters” disclosure. Applied
additional filters are marked in its summary. The page count now reports the
visible range within the loaded workflows on later pages. A duplicate page
eyebrow is removed. Filtering and workflow authority are unchanged. Focused
page tests, lint, build, and built browser checks at 390px and 1280px cover the
change.

## Workflow detail return link — 2026-10-28

The detail page now returns candidate-started workflows to the candidate list
and manual or unrecognized workflows to the workflow list. Focused workflow
page tests cover both sources and the unknown-source fallback; approval and
resume behavior is unchanged.

## Maintenance history filters — 2026-10-28

The history screen keeps “Latest result” visible and folds completion, action,
provider and resource filters under “More filters.” Applied extra filters are
marked, and “Clear filters” appears when any filter is active. Focused page
tests pass (10 tests), lint/build pass, and all 23 recovery browser checks pass,
including the history screen at 390px and 1280px. The bounded query and
maintenance action boundary are unchanged.

## Workflow audit overview — 2026-10-28

The audit overview now shows workflow status once and keeps audit validation
separate. Duplicate status readouts were removed, and the technical trust
boundary copy now explains in plain language where stage statuses come from
and that the page is read-only. The focused audit suite passes (18 tests), lint
and build pass, and the built repository journey passes all 4 cases, including
the audit view at 390px and 1280px.

## Action history filters — 2026-10-28

Action History keeps status and text search in view and places provider and
date filters under “More filters.” Active extra filters are marked and can be
cleared from the main panel. The UTC-day explanation stays with the date
controls. The focused page suite passes (8 tests), lint/build pass, and the
built responsive browser checks pass at 390px and 1280px (2 tests). Query
semantics and audit operations are unchanged.

## Action history details — 2026-10-28

The detail screen leads with the outcome, action message, provider name and
start/completion times. Status labels are human-readable. IDs, duration and
parameter names are grouped under a collapsed “Technical details” disclosure.
The focused detail suite passes (6 tests); lint and build pass. Audit reads and
copy-link behavior are unchanged.

## Main dashboard workflow attention — 2026-10-28

Operator Attention links now name the proposed action and explain the workflow
stage in plain language. Last-known evidence is labeled as such. Workflow IDs
in this list are under a collapsed “Technical details” disclosure. The focused
dashboard suites pass (68 tests), and 17 built browser checks pass across
narrow, mobile, tablet and desktop layouts. Lint and build pass; workflow links
remain read-only.

## Main dashboard work activity — 2026-10-28

Running, blocked and completed-work rows now use the action name and a
human-readable state or outcome. Workflow IDs are tucked into each row’s
collapsed technical details. Queue size and worker availability remain
explicitly unreported; the dashboard remains read-only. The focused dashboard
suites pass (71 tests), lint/build pass, and 8 built browser checks pass,
including mobile and desktop disclosure behavior.

## Main dashboard recent activity — 2026-10-28

Recent action rows now say “Succeeded” or “Failed” instead of using severity
language, and completion times use the browser’s local date and time format.
The exact UTC timestamp remains available in the time element’s title. The
screen still explains that past actions do not show current health. The focused
dashboard suites pass (68 tests), lint/build pass, and all 3 built responsive
browser checks pass.

## Recent Activity cards — 2026-10-28

Recent actions are now grouped into outlined cards, one column on phones and
two columns on wider screens. The per-row history warning was removed because
the section already states that past actions do not show current health or
alerts. Ordering, result, time and action-detail links are unchanged. The
focused dashboard suites pass (68 tests), lint/build pass, and all 3 built
responsive dashboard checks pass.

## Agent overview status — 2026-10-28

The Agent card no longer shows an “Unknown” health badge or missing check time
for information that does not report health. It summarizes loaded, unavailable,
and last-known Agent details in plain language without repeating the generic
source-state message. Existing read-only links remain. The focused suite passes
10 tests; lint/build and all 8 built responsive overview browser checks pass.
No Agent or execution capability was added.

## Health check times — 2026-10-28

Shared health summaries now show check times as readable UTC dates instead of
ISO strings. The exact source timestamp remains in the time element for
machine-readable use. The focused component suite passes 42 tests; lint and
build pass. All 8 built overview browser checks pass, including 320px, 768px
and 1440px layouts. Health status and freshness decisions are unchanged.

## Dashboard health summaries — 2026-10-28

Overview summaries no longer repeat equivalent labels such as “offline” beside
“Unavailable” or show missing-time placeholders for sources that report no
check time. Reasons, distinct severity labels, valid check times, and last-known
warnings remain visible. Full health detail views are unchanged. The focused
component suites pass 100 tests; lint/build and all 15 built responsive
overview, dashboard and system-health checks pass.

## Installation permission evidence wording — 2026-10-28

An active lifecycle is now labeled “Current evidence record” so it cannot be
read as active execution permission. Recorded, expiry, and status-check times
use readable UTC dates. The focused readiness review suite and responsive
browser checks cover the record at mobile and desktop widths; lint and build
pass. The grant's authority fields and server behavior are unchanged.

## Monitoring suggestion wording — 2026-10-28

The suggestion card describes why Atlas proposed a value without exposing its
internal rule name. Stale suggestions explain that the VM or monitoring
setting changed and point operators to Refresh resources. Reviewing a
suggestion still only fills the form; the explicit Save action remains
separate.

## Maintenance history filter scope — 2026-10-28

Maintenance history now explains that its filters narrow the requests on the
current page. Operators can browse other pages to check the rest of the
history. The filter query and bounded page loading are unchanged. The focused
page suite passes (10 tests), responsive browser checks pass at 390px and
1280px (2 tests), and lint/build pass.

## Action detail time zone — 2026-10-28

Action history detail now says that its start and completion times use the
browser’s local time, matching the explanation on the history filter screen.
The combined action and maintenance history suites pass (16 tests), and
Mission Control lint/build pass.

## Action history summary — 2026-10-28

The Action History introduction now describes provider actions and results in
plain language, with local time explained while timestamps are visible. The
advanced date filter clarifies that selected dates cover full UTC days. The
focused page suite passes (8 tests), responsive browser checks pass at 390px
and 1280px (2 tests), and lint/build pass.

## Dashboard Agent card label — 2026-10-28

The dashboard card is now titled “Agent details,” matching its identity and
read-only links. It no longer suggests that the card reports Agent health or
workflow status, which its source does not provide. The focused component
suites pass (60 tests), all 16 built app-shell and overview browser checks pass,
and lint/build pass.

## AI provider unavailable state — 2026-10-28

During the first read, the AI provider card now shows a loading message instead
of an unknown provider and status badge. If the read fails without prior data,
the card gives one refresh instruction instead of repeating the same failure
as an unknown health state and missing technical details. Last-known evidence
continues to be labeled separately. Focused evidence/dashboard suites pass
(85 tests), all 16 built app-shell and overview browser checks pass, and
lint/build pass.

## Work activity empty state — 2026-10-28

The dashboard states once that Atlas does not report worker availability.
When there are no active records, the separate empty message now only says
that no running workflows are listed. This avoids repeating the availability
uncertainty. Workflow counts, stale-data handling, and execution boundaries are
unchanged. Focused component suites pass (77 tests), all 8 built overview
browser checks pass, and lint/build pass.

## Discovery search response ordering — 2026-10-28

Discovery now applies results, errors, metadata, and loading completion only
from the latest catalog request. The previous request cannot replace newer
search results or mark a newer search complete. The focused page suite passes
(7 tests), responsive catalog browser checks pass at 390px and 1280px (2
tests), and lint/build pass. API requests and read-only behavior are unchanged.

## Proposal planning result — 2026-10-28

Starting planning now shows a plain-language outcome and a clear next link.
Session IDs, fingerprints, intake codes, and failure details are collapsed
under “Technical details.” A response that is not allowed to continue labels
its session link “Open planning session” for review, while only an allowed,
ready session says “Continue planning.” Planning still does not approve or
apply a change. The focused page suite passes (18 tests), the repository and
maintenance browser journeys pass at 390px and 1280px (6 tests), and lint and
production build pass.

## Planning session review — 2026-10-28

The planning page now leads with “Plan this change” or “Review the plan,”
describes unavailable and stale states in plain language, and keeps session
IDs, raw statuses, fingerprints, lineage, and failure codes under “Technical
details.” Workflow creation reports that no implementation ran and that
implementation still needs separate approval; workflow IDs and conversion
codes are collapsed. A saved plan that cannot create a workflow is explicitly
labeled read-only. The page suite passes (32 tests), repository and maintenance
browser journeys pass at 390px and 1280px (6 tests), and lint and production
build pass.

## Workflow review status — 2026-10-28

Workflow review now has a stable “Review workflow” title and a plain-language
summary for approval, running, blocked, completed, and unknown states. The
workflow ID and raw state are available under “Workflow details.” Approval
controls still require the exact pending stage, and each approved stage still
requires its separate Resume action. The focused workflow page suite passes
(72 tests), repository and maintenance journeys pass at 390px and 1280px, and
the reject and pending-refresh protections pass (6 browser tests). Lint and
production build pass.

## Acceptance status and remaining gaps

- Maintenance request submission through the returned proposal, planning, exact
  approval, separate run and audit is now covered by one synthetic browser
  journey at 390px and 1280px. The fixture checks ordered request bodies,
  target fingerprint, expiry and CSRF, and rejects other mutations. The separate
  Discovery sign-in test still proves that advisory context cannot preselect or
  request maintenance. These checks do not establish real provider acceptance.
- The installation readiness browser cases now cover both invalid-response
  rejection and successful review loading after an outage at 390px and 1280px.
  A restored synthetic owner session with no grant permission sees the evidence
  chain without mutation controls. The shared browser fixture rejects every
  mutation. Sixteen focused component/parser/boundary tests also pass after
  extracting unchanged evidence constants into a dependency-free module. These
  checks prove evidence presentation, not installation execution or real
  authenticated backend acceptance.
- Operator visual acceptance of the running interface, real backend integration,
  running-image parity, and production acceptance have not been established by
  these simulated checks.
- Source review and CI are review inputs. They do not authorize merging or any
  release, deployment, runtime enablement, or infrastructure operation.

Mission Control completion remains open while these applicable journey and
operator acceptance requirements are unverified. Deferred execution capabilities
and the successor control plane are not made available by this work.

## Workflow audit review — 2026-10-28

The repository audit now opens with a stable title, plain-language workflow
status, audit validity, and the stage progress grid. Workflow IDs, recorded
state, source, and validation codes are available under Technical details;
individual stage evidence is collapsed under its stage. Missing and inconsistent
stage warnings remain visible, and invalid audit records still identify that
review is needed. The maintenance audit uses plain-language workflow status and
inconsistency messaging. Audit remains read-only, with no approval or execution
controls added. Stage sections now have valid accessible names. The focused page
suite passes (20 tests), repository and maintenance journeys pass at 390px and
1280px (6 browser tests), and lint, production build, and `git diff --check`
pass.

## Maintenance history target labels — 2026-10-28

Maintenance history now presents the canonical Proxmox target reference as
“Virtual machine 110” when its provider, resource type, and ID match the lifecycle
record. The original target reference remains available under Workflow details;
other supplied labels and workflow-only target labels are preserved. Outcome
status, filtering, pagination, and read-only behavior are unchanged. The focused
history suite passes (10 tests), the responsive maintenance-history browser
checks pass at 390px and 1280px (2 tests), and lint, production build, and
`git diff --check` pass.

## Maintenance request guidance — 2026-10-28

The request screen now says that it creates a proposal for separate review and
approval, and that it does not restart the VM. A missing restart capability no
longer leaves the action summary stuck on “Loading capability.” Suggestion,
permission, and resource-loading messages use direct language while the
Discovery suggestion remains unable to select a VM or submit a request. The
VM-loading failures are reported separately from proposal-submission failures
and point to the read-only Refresh control. The focused request-page suite
passes (29 tests), the sign-in and full maintenance
journeys pass at 390px and 1280px (4 browser tests), and lint and production
build pass. Approval, CSRF, target-fingerprint, and separate run behavior are
unchanged.

## Provider action history details — 2026-10-28

Action history cards now lead with the action result, provider, and time;
parameter names, duration, and request ID are under Technical details. History
export and expired-record deletion are grouped under a collapsed Manage history
section. The confirmation says that deleting old records does not undo provider
actions. Status labels and page title use sentence case. The focused page suite
passes (8 tests), responsive browser checks pass at 390px and 1280px (2 tests),
and lint, production build, and `git diff --check` pass.

## Dashboard health scan simplification — 2026-10-28

The dashboard's health card now has one “System health” heading. Its source
reports remain separate, with source-specific unavailable and stale states.
Explanations about separate reports, the absent overall check time, and the
missing Core process-health report are available in collapsed help. The
duplicate card-level failure note was removed. No status calculation or data
source changed. The focused health and overview suites pass (100 tests), the
phone and desktop browser checks pass (2 tests at 390px and 1280px), and lint,
production build, and `git diff --check` pass. The browser fixture rejected
unexpected mutation requests.

## Provider status wording — 2026-10-28

The Providers card now labels its optional explanation “About provider status.”
It explains that a healthy report does not guarantee a working connection or
permission to run actions. The repeated note about Agent model selection was
removed because the AI provider card already explains that limitation. Provider
status and action permissions are unchanged. The focused component suite passes
(10 tests), the keyboard-accessible overview browser check passes, and lint,
production build, and `git diff --check` pass.

## Operator Attention empty state — 2026-10-28

When all current sources are checked and none reports an attention item, the
dashboard now says, “The current reports show no items needing attention.” The
incomplete-source message remains unchanged and still says Atlas cannot confirm
whether attention is needed. The overview component suite passes (51 tests),
and lint and production build pass.

## Health report scan order — 2026-10-28

The health card now lists its independent source reports before the optional
“How to read health” explanation. This lets operators see the reported status
before opening guidance. Status, freshness, source ordering, and disclosure
contents are unchanged. The focused health and overview suites pass (100 tests),
phone and desktop browser checks pass (2 tests at 390px and 1280px), and lint,
production build, and `git diff --check` pass.

## Provider summary wording — 2026-10-28

The Providers card now says, “Saved providers and the status Atlas reports for
each one.” This removes the repeated “saved provider” phrasing while keeping
clear that the card shows reported status. The focused component suite passes
(10 tests), the keyboard-accessible overview browser check passes, and lint,
production build, and `git diff --check` pass.

## Operator Attention workflow summary — 2026-10-28

The Operator Attention card no longer repeats a generic instruction above its
links. When a workflow’s recorded reason exactly repeats its approval stage,
the duplicate line is omitted; a distinct recorded reason remains visible. The
action-required cue, exact approval stage, stale-state warnings, and technical
workflow ID remain. The overview component suite passes (52 tests), the
synthetic overview and dashboard-attention browser suites pass (14 tests across
phone, tablet, and desktop widths), and lint, build, and `git diff --check`
pass. The fixture rejects unexpected mutation requests.

## Change proposal read failure — 2026-10-28

When a proposal search fails, the page now shows its error alert without a
second “Results unavailable” message beside the disabled pagination. The
screen continues to hide previous results after the failed search, and error
details remain redacted by the API error handler. The focused page suite passes
(8 tests), responsive proposal-list browser checks pass (4 tests at 390px and
1280px), and lint, production build, and `git diff --check` pass. The browser
fixture rejects unexpected mutations.

## Workflow list card names — 2026-10-28

Workflow cards now use the reported action as their heading; when it is absent,
they use a plain workflow-type fallback. The workflow ID moved under collapsed
Workflow details alongside other references. Stage, latest result, approval
status, progress, and the Open workflow link remain visible. The component suite
passes (8 tests), responsive workflow/navigation/recovery browser checks pass
(6 tests at 390px and 1280px), and lint, production build, and
`git diff --check` pass. No API contract or approval behavior changed.

## Missing change proposal recovery — 2026-10-28

The 404 screen now says that the proposal is no longer available and directs
the operator back to the proposal list. Its raw proposal ID is under collapsed
Technical details; server response details remain hidden. A missing proposal is
still distinguished from a service outage. The detail-page suite passes (18
tests), responsive recovery checks pass (2 tests at 390px and 1280px), and lint,
production build, and `git diff --check` pass.

## Workflow list empty and error states — 2026-10-28

Empty workflow lists no longer show a redundant “0 workflows” count beside the
empty-state explanation. Initial load errors no longer repeat the retry button's
“Try again” instruction. Counts for non-empty results, retry behavior, and
workflow data are unchanged. The focused page suite passes (8 tests), responsive
empty-state checks pass at 390px and 1280px, the recovery browser check passes,
and lint, production build, and `git diff --check` pass.

## Overview Agent details — 2026-10-28

The Agent details card now describes only the Agent name and version reported
by that source. It no longer repeats workflow availability already shown in
Work activity. Failed and last-known reads use shorter messages. No data source
or status calculation changed. The focused overview suite and responsive
overview browser checks pass, along with lint, production build, and
`git diff --check`.

## Operator Attention destinations — 2026-10-28

The attention panel no longer repeats general links to operations and workflows
below conditions that already link to their detail pages. General navigation
remains in System health and Work activity. The focused overview tests and
responsive browser checks pass, along with lint, production build, and
`git diff --check`.

## Agent details navigation — 2026-10-28

The Agent details card no longer repeats the workflow link shown in Work
activity. Its remaining navigation is deployment analysis; workflow review
stays in Work activity. The focused Agent/provider suite and responsive
overview browser checks pass, along with lint, production build, and
`git diff --check`.

## Action history loading status — 2026-10-28

The Manage history panel now identifies its separate retention read while the
action list is loading, and names retention details in its unavailable state.
This clarifies why the expired-entry control is disabled without repeating the
action-list loading message. The focused Operations page suite, action-history
browser checks, lint, production build, and `git diff --check` pass.

## Retry and unavailable-state wording — 2026-10-28

Provider, workflow, workflow-audit, and action-audit errors now rely on their
visible retry buttons instead of repeating retry instructions in the error
copy. Provider server details remain hidden, and retry still performs only the
provider-list read. Planning-unavailable states no longer direct operators to
technical details for a generic status; saved plans now say plainly when they
remain reviewable but cannot create a workflow. The action-history browser
fixture now matches Core's retention-summary contract, preventing undefined
counts in the screen. These changes do not alter read, planning, approval, or
workflow behavior. Focused page tests, screen-recovery browser checks, lint,
production build, and `git diff --check` pass.

## Recovery controls on error screens — 2026-10-28

Page-load, sign-in, and maintenance-history failures no longer repeat the
instruction already given by the visible Reload, Sign in, or Refresh history
control. The maintenance-history warning still distinguishes a failed read
from a failed maintenance action. Focused page tests, responsive page-recovery
browser checks, lint, production build, and `git diff --check` pass.

Planning screens also keep the reload instruction on the visible control rather
than repeating it in errors for missing or conflicting plans. A missing plan
does not offer another generation request. The planning page tests, lint, and
production build pass.

## Missing provider recovery — 2026-10-28

The missing-provider screen now uses one status heading and a short catalog
message. Its existing “All providers” navigation remains the recovery route,
and the message does not repeat refresh instructions. It does not label a
successfully loaded catalog as unavailable. Provider page and responsive
browser recovery checks, lint, production build, and `git diff --check` pass.

## Installation readiness status — 2026-10-28

The readiness-gated state now says that evidence is current while installation
cannot start because Atlas has no defined start process. Its sole technical
blocker remains available in collapsed record details. Blocked reviews continue
to list their evidence issues. Evidence review remains non-authorizing and does
not refresh evidence. The readiness component suite, responsive browser checks,
lint, production build, and `git diff --check` pass.

## Discovery results and empty states — 2026-10-28

Discovery now separates the overall catalog total from matching result counts.
“Clear filters” appears only when a draft or applied filter can be cleared.
An empty catalog no longer suggests changing filters, while no-match and empty
later-page states offer relevant next steps. Search requests and read-only
behavior are unchanged. The Discovery page suite, responsive catalog browser
checks, lint, production build, and `git diff --check` pass.

## Core API status and release label — 2026-10-28

The shell now shows whether Atlas Core's API discovery endpoint responded and
labels its configured `Foundry` value as a release label. “Release available”
could be mistaken for a published GitHub release, so availability now describes
the API connection separately from the label. No Core contract or runtime
behavior changed. Focused shell tests, shell browser checks, lint, production
build, and `git diff --check` pass.

## Dashboard Agent and provider loading — 2026-10-28

The Agent and Providers cards now distinguish the first load from unavailable,
missing, and unreadable data. A slow first response no longer looks like a
missing provider configuration, and the Agent card stops saying “Loading” once
loading ends. Stale provider lists are labeled as last available. Requests and
operator authority are unchanged. Focused component and structural tests,
responsive overview browser checks, lint, production build, and
`git diff --check` pass.

## Dashboard health-report loading — 2026-10-28

The three health reports now show “Checking…” while their first reads are in
flight, instead of displaying unknown statuses before any response arrives. A
failed read without prior data gets one unavailable message; stale reports
still identify their last-known status. The dashboard uses the same sources and
does not calculate new health results. Focused component tests, responsive
overview browser checks, lint, production build, and `git diff --check` pass.

## Change proposal search recovery — 2026-10-28

When loading or searching change proposals fails, the error now offers a
single explicit retry action. It repeats the same submitted filters and page,
including after a pagination request fails. The focused component test verifies
that a filtered search is preserved; responsive browser checks verify recovery
after a failed read at 390px and 1280px. No proposal mutation or approval
behavior changed.

## Change proposal detail recovery — 2026-10-28

Transient proposal detail read errors now offer an explicit retry. A retry
repeats only the detail GET and returns to the proposal summary on success;
HTTP 404 still uses the separate missing-proposal screen. The focused component
test and responsive browser checks verify recovery and confirm the backend
detail remains hidden at 390px and 1280px. Planning and approval behavior are
unchanged.

## Discovery related-proposal recovery — 2026-10-28

If related proposals fail to load on a catalog item, the section now offers a
retry without reloading the item or its other evidence. The proposal list stays
read-only, and the catalog context remains visible. Focused component coverage
and responsive browser checks verify the recovery at 390px and 1280px; no
proposal or installation action is introduced.

## Discovery source-evidence recovery — 2026-10-28

When supplemental release evidence is unavailable, the panel now retries that
read independently while preserving the curated catalog view. Focused panel and
page tests plus mobile and desktop browser checks verify the recovery. No other
catalog evidence is reloaded, and curated data remains authoritative.

## Discovery image-grounding recovery — 2026-10-28

Temporary image-grounding read failures now offer an in-place retry. A genuine
404 remains an unavailable projection without a retry control. Focused component
and page tests plus mobile and desktop browser checks verify both the transient
recovery and the separate missing state. No deployment action is introduced.

## Installation plan detail density — 2026-10-28

The Installation Plan panel now keeps the plan status and blocker count visible
while placing its long fingerprint, provenance, evidence, and blocker record
under a collapsed “Plan details” section. Operators can expand the complete
record when needed. Focused component coverage and mobile and desktop browser
checks verify the default summary and expanded details; installation authority
and controls are unchanged.

## Proposal compatibility and constraint wording — 2026-10-28

Compatibility states now use consistent plain language across Discovery and
Change proposals, including “Compatible with warnings,” “Not enough
information,” and “Not compatible.” Proposal constraints use operator wording
such as “May interrupt service” and “Backup required” instead of raw codes.
Unknown values remain visible as readable labels. Focused page and label tests
pass (89 tests), as do lint, production build, and `git diff --check`. Proposal
evidence and planning/approval boundaries are unchanged.

## Workflow preparation failure guidance — 2026-10-28

Workflow preparation failures now explain what changed and what the operator
can do next. Raw reason codes and failure messages are grouped under collapsed
Technical details for workflow creation, exact-request preparation, and
successor planning. The repository-stale recovery action and separate approval
flow are unchanged. The focused workflow page suite passes (30 tests), along
with lint, production build, and `git diff --check`.

## Plan generation outcome recovery — 2026-10-28

After a plan request error, Mission Control now pauses another generation
request and asks the operator to reload the planning session to check whether
the plan was saved. This avoids issuing another request against an unknown
server state; generation remains available after the session is reloaded and
reports that it is ready. The focused planning-page suite passes (32 tests), as
do lint, production build, and `git diff --check`. No approval or execution
behavior changed.

## Installation admission summary — 2026-10-28

The catalog's installation-admission panel now leads with a plain-language
result and reasons. Fingerprints, exact reason codes, and the full non-executable
candidate record are under collapsed Technical details. The page still states
that the check cannot approve or start an installation; preservation and other
authority controls are unchanged. Focused admission, lifecycle, and catalog
page tests pass (45 tests), along with lint, production build, and
`git diff --check`.

## Installation assessment wording — 2026-10-28

Prospective-destination assessments now show a readable result and blocker
explanations without exposing API status or reason codes in the main view.
Diagnostic codes remain under collapsed Technical details, and the summary
states that candidate eligibility was not evaluated and installation was not
authorized. The focused assessment suite passes (11 tests), along with lint,
production build, and `git diff --check`. Selection and assessment boundaries
are unchanged.

## Permission evidence read recovery — 2026-10-28

If the permission-evidence list cannot be read, the review now offers a reload
that repeats only that read. The retry clears the unavailable state while it
loads and does not create permission evidence. A failed record request remains
separate and does not offer a duplicate submission control. Focused readiness
review tests, lint, production build, and `git diff --check` pass.

## Stale proposal recovery — 2026-10-28

When planning reports that a proposal is out of date, the result now offers a
Refresh proposal action. It reloads the proposal details, clears the stale
planning result, and makes no second planning request. The focused proposal
detail suite verifies the refreshed content and request counts; no approval or
change action is added.

## Proposal date labels — 2026-10-28

Proposal expiry and creation timestamps now say that they are shown in the
browser's local time. Their displayed values and expiry checks are unchanged.

## Maintenance suggestion recovery — 2026-10-28

Temporary failures while loading optional suggestion details now offer an
in-place retry of that GET. A 404 stays a separate “no longer available” state
without retry. The selected VM, provider capability list, and maintenance
request state are not changed by the retry; the suggestion remains advisory.

## Maintenance history time labels — 2026-10-28

Request and result timestamps now identify that they are shown in the
browser's local time. The recorded timestamps and history queries are
unchanged.

## Action history operation failures — 2026-10-28

Export and retention-deletion errors now stay with the history-management
controls. They no longer replace or hide a successfully loaded action list and
retention summary. History-read failures continue to use the separate
unavailable state.

Action records now load independently from retention details and provider
filter options. A failure in either optional read leaves the action list
available and identifies only the affected information as unavailable.
When the action-list read fails, successfully loaded retention details and
provider filter options remain visible. Expired-record deletion stays disabled
until action history loads successfully.

Provider action failures now lead with the uncertain outcome and direct the
operator to Action history before retrying. Raw provider errors are available
under collapsed Technical details; the action is not automatically repeated.

## Planning request recovery — 2026-10-28

An uncertain planning-request result now explains that a session may have been
created and that selecting Start planning again reopens or reuses a matching
session. Raw server details stay collapsed. A response for another proposal is
refused, with guidance to refresh the current proposal before trying again.
Neither state approves or applies an infrastructure change.

Plan and workflow creation errors keep the raw response under collapsed
Technical details. A plan result that Mission Control cannot verify requires a
page reload before another generation attempt. Workflow creation explains that
a submitted request may have created a workflow and that repeating the request
retrieves or reuses it; implementation still requires separate approval.

## Discovery search recovery — 2026-10-28

Catalog status and catalog results load independently. If the status read fails,
valid results remain visible, the unavailable status and total are identified,
and a status-only retry is available. If the results read fails, previous cards
are cleared, an unavailable state is shown instead of an empty grid, and a
read-only retry repeats the exact filters and page. Malformed items use the
same retryable unavailable state, preserving the page shell and navigation.
Raw server details stay collapsed, and unavailable results are not reported
as zero matches.

## Workflow list refresh recovery — 2026-10-28

Workflow-list refresh failures now identify that the visible cards and counts
are the last successfully loaded state. The Refresh control remains available
to retry the read; raw Agent errors stay under collapsed Technical details.

## Atlas Doctor request recovery — 2026-10-28

A failed diagnostic read now says that no new report is available and points to
Run Doctor as the read-only retry. The raw request error remains available
under collapsed Technical details; a previous healthy report is still cleared
while a rerun is pending or unavailable.

## Atlas Agent status recovery — 2026-10-28

The dashboard's Atlas Agent status panel now offers an in-place retry after a
failed read. Retry repeats only the status and pending-approval reads; it does
not submit or change approval state. A missing repository commit is labeled
“Not reported” so the screen describes the received evidence without implying
that the service knows why it is absent.

## Operational lifecycle read recovery — 2026-10-28

An unavailable lifecycle now offers a read-only workflow status retry and says
that the maintenance outcome may still be unknown. The retry does not repeat
the provider action; technical error text is optional.

Maintenance history also keeps the workflow row and any successful diagnostic
visible when lifecycle details are unavailable or belong to another workflow.
It identifies target and timing details as incomplete and points to Refresh
history, which retries reads only.

## Planning session read failures — 2026-10-28

When Mission Control cannot read a planning session, the page now says its
current status is unknown. Backend error text is available under collapsed
Technical details, and Reload page remains the recovery action.

## Change proposal read failures — 2026-10-28

Unavailable proposal lists and proposal details now lead with plain-language
read-failure messages. Backend error text stays under collapsed Technical
details; the existing retry controls repeat only the corresponding read.

## Discovery item read separation — 2026-10-28

Catalog item details now load independently from related-item relationships.
If the relationship read fails or returns another item's data, the catalog
entry remains visible and the relationship section offers a read-only retry.
Catalog read errors also keep backend text under collapsed Technical details.

## Provider detail source failures — 2026-10-28

Provider detail sources now refresh independently. A diagnostics, health, or
history failure no longer hides a successfully loaded provider; unavailable
diagnostics and check history are not shown as empty results. A failed provider
catalog read is kept distinct from a confirmed missing provider.

## Workflow and proposal list response recovery — 2026-10-28

The shared workflow API validates list rows before any screen consumes them and
checks that filtered results match the requested effect kind. The workflow
directory, Maintenance History, and change-proposal directory route unreadable
responses into their existing unavailable state and read-only retry. This
preserves the page shell instead of crashing into the generic page error.
Browser checks cover recovery, shared navigation, and phone and desktop widths;
they submit no actions. The full component suite (2,708 tests), lint, build, 110
development-browser checks, and 68 built-app journeys pass. Simulated browser
coverage does not establish real backend integration or operator acceptance.

## Action history response validation — 2026-10-28

Action-history pages, entries, provider filters, and retention summaries are
validated against the Core response contracts before display. Unreadable rows
use the existing history-unavailable state and can be retried. An invalid
retention period leaves deletion disabled while preserving history browsing.
An audit record returned for a different link remains a mismatch error. The
full component suite (2,712 tests), lint, build, 114 development-browser checks,
and 68 built-app journeys pass. Browser fixtures reject all action mutations;
they do not establish real Core integration or operator acceptance.

## Maintenance lifecycle response validation — 2026-10-28

Agent operational-lifecycle and recovery-diagnostic reads are validated before
the maintenance history and workflow screens use them. Malformed lifecycle
details leave the maintenance row visible and mark target/timing information
unavailable. An unknown recovery status is shown as unavailable and does not
imply that maintenance failed. Browser fixtures reject mutations. The full
component suite (2,714 tests), lint, build, 118 development-browser checks, and
68 built-app journeys pass. These simulated checks do not establish real
Agent/Core integration or operator acceptance.

## Workflow audit response validation — 2026-10-28

Agent audit responses are checked across the workflow identity, stage timeline,
validation summary, and nested evidence before the audit screen renders them.
Malformed audit evidence gets the existing unavailable state and a read-only
retry. A structurally valid audit for a different workflow still reaches the
page's identity check and is refused. The full component suite (2,716 tests),
lint, build, 120 development-browser checks, and 68 built-app journeys pass.
Simulated responses do not establish real Agent integration or operator
acceptance.

## Workflow detail response validation — 2026-10-28

The workflow detail response is validated, including approval presentations,
execution summaries, verification evidence, review data, and commit summaries,
before it can supply stage controls. A malformed response now uses a clear
unavailable state and read-only retry; approval and Resume controls remain
hidden until a valid read succeeds. A complete response for another workflow
still reaches the page identity check. The full component suite (2,720 tests),
lint, build, 122 development-browser checks, and 68 built-app journeys pass.
Browser responses are simulated and reject mutation requests; they do not
establish real Agent integration or operator acceptance.

## Exact-request preparation response recovery — 2026-10-28

Mission Control validates the Agent response before opening the repository
workflow for exact-request review. If preparation returns a malformed,
mismatched, or incomplete result—or the request outcome cannot be confirmed—the
page pauses another preparation attempt and offers a reload to check the saved
workflow status. Explicit structured Agent failures retain their existing
retry and stale-recovery behavior. Browser checks cover phone and desktop
widths; no implementation, approval, or execution is simulated by this error
case. The component suite (2,730 tests), lint, build, 126 development-browser
checks, and 70 built-app journeys pass. These remain simulated checks, not real
Agent integration or operator acceptance.

## Candidate planning response validation — 2026-10-28

Planning-session, repository-plan, maintenance-plan, and workflow-shell
responses are validated before the planning screen uses them. Malformed saved
plan data now reaches the existing unavailable state, while malformed
generated results cannot expose workflow creation. Phone and desktop browser
checks confirm the unavailable state keeps the navigation and hides planning
controls. The component suite (2,727 tests), lint, build, 124 development-browser
checks, and 68 built-app journeys pass. Responses are simulated; this does not
establish real Agent integration or operator acceptance.

## Workflow approval response recovery — 2026-10-28

If an implementation, verification, or commit approval request errors, the
workflow page now reloads the authoritative workflow detail before re-enabling
controls. This covers timeouts where the server may have recorded a decision
even though the response did not reach Mission Control. Agent error details
accept both the existing string form and the structured `{code, message}` form;
unusable error payloads fall back to a readable request message. Tests confirm
each stage refreshes after failure and removes a stale approval control when
the server reports the decision. API and workflow page tests pass (106 tests),
with lint and production build passing. No approval or Resume boundary changed.

Successful implementation, verification, and commit approval responses are
also checked against the requested workflow ID, a non-empty workflow state,
the expected approved/rejected decision, and a nullable text message. A
malformed or mismatched response enters the same read-before-retry recovery
path. API and workflow page tests pass (109 tests). The full repository-journey
browser file passes (8 tests), including two cases for a recorded implementation
approval whose response fails, at 390px and 1280px. Both confirm that the page
refreshes status and removes both decision controls. Lint and production build
pass. The fixtures reject unexpected mutations and do not establish live Agent
integration or operator acceptance.

## Workflow read failure wording — 2026-10-28

Workflow-detail read failures now lead with a plain-language notice that the
current status is unknown. Request errors remain under collapsed Technical
details, and the read-only retry and workflow-list link stay available. The
workflow page suite passes (78 tests), and the responsive browser recovery case
passes at 390px and 1280px. Lint and production build pass. The browser fixture
tests reads only and rejects unexpected mutations.

## Operator Attention priority — 2026-10-28

When more than five conditions are reported, the dashboard now keeps blocked
conditions first, then critical findings, then workflow approvals. Routine
degraded checks no longer push a human decision out of the visible list;
unavailable information follows approvals. The overview suite passes (56
tests), with lint, production build, and `git diff --check` passing. The card
shows five items by default and has a Show all / Show fewer control for the
remaining conditions. Each row links to its owning screen; no source state or
authority changed.

## Shell product label — 2026-10-28

The visible sidebar brand now says “Mission Control” without the design-only
“2.0” suffix, which could be mistaken for the product release version. Shell
component and browser regressions check the plain product name. The shell suite
passes (33 component tests and one focused browser test), along with lint and
the production build. No routes, release metadata, or behavior changed.

## Service check list access — 2026-10-28

The dashboard now keeps its four-check summary compact while allowing the
operator to expand and collapse every reported service check. This replaces
the count-only message that hid additional checks without a way to reach them.
The overview suite passes (57 tests), and a mobile browser regression verifies
all six fixture checks can be revealed and hidden again without horizontal
overflow. Lint, production build, and `git diff --check` pass. No health
evidence or backend behavior changes.

## Work activity list access — 2026-10-28

Running, blocked, and recorded-outcome lists in the Work activity card now
start with three rows and provide an explicit control to reveal or collapse the
full returned list. The card still links to workflow review, and no approval,
execution, or backend behavior changes. The focused Work activity suite passes
(28 tests), as does a 320px browser regression covering all three lists and
horizontal overflow. Lint and production build pass.

## AI model inventory access — 2026-10-28

The AI provider card still keeps model inventory under Technical details and
shows a short three-name preview. When more names are reported, nested
disclosures now reveal the full installed or running model-name list. The
focused AI inventory suite passes (28 tests), along with lint and production
build. The inventory remains observational and does not imply selection or
readiness.

## Core connection wording — 2026-10-28

The shell now names the service whose status it reports: “Checking Atlas Core,”
“Atlas Core online,” or “Atlas Core unavailable.” The sidebar status heading
also says “Atlas Core” instead of “Atlas Core API.” This changes wording only;
the same read still determines the connection state. The layout suite passes
(33 tests), the focused unavailable-state browser test passes, and lint and
production build pass.

## Operator Attention source status — 2026-10-28

When one or more reports are missing or incomplete, the dashboard shows one
plain-language warning that the attention list may be incomplete. Per-source
status remains available under a collapsed “Source status” detail, reducing
repeated error notes while preserving the specific reason. The overview suite
passes (58 tests), the focused dashboard outage browser test passes, and lint
and production build pass. Known attention items remain visible, and no source
or approval behavior changes.

## Change proposal filter clarity — 2026-10-28

The proposal list now says when edited filters have not been applied, and
temporarily disables page navigation until the operator searches. This keeps
the displayed results and paging aligned with the submitted filters. A focused
component regression verifies the notice, disabled paging, and recovery after
search; this changes only list presentation and navigation state.

## Readiness review session gating — 2026-10-28

Permission-evidence confirmation now appears only when the signed-in operator
has the required permission and a CSRF token. Previously, an unusual session
missing that token could open the confirmation even though submission would
silently return without making a request. A focused regression verifies the
control remains unavailable in that state; backend permission and approval
contracts are unchanged.

The same guard now covers installation admission, queue observation, controlled
dequeue admission, and one-shot dequeue evidence. Each panel has a regression
that verifies the confirmation stays hidden without the session token; no
dequeue, worker, installation, or execution authority was added.

## One-time evidence action visibility — 2026-10-28

Permission grant, installation admission, queue observation, controlled
dequeue admission, and one-shot dequeue panels now wait for a successful
read-only record check before showing their one-time confirmation. They hide it
when a record already exists, the read is unavailable, or a recording attempt
fails or returns a blocked result. This follows the backend's permanent
reservation and no-retry contracts. Five focused component suites cover
loading, empty, existing, and post-submit states; no approval or runtime
authority changed.

## Discovery evidence action recovery — 2026-10-28

Installation approval, execution request, dispatch handoff, delivery preflight,
and delivery enablement panels now require their record list to load
successfully before offering a one-time evidence action. A failed submission
closes its confirmation and hides the action for that exact source in the
current view, avoiding an accidental second reservation with a new request
key. The five focused suites pass 22 tests across read failure, confirmation,
and submission failure states. No execution, delivery, or installation
authority changed.

## Action history search clarity — 2026-10-28

Action history now says when typed search text has not yet been applied and
disables page navigation until Search updates the results. Search text is
trimmed before comparison, so whitespace alone does not create a false pending
state. The focused page suite verifies the pending notice, disabled paging,
search application, and navigation with the applied query (13 tests). Browser
coverage also checks the pending state and mobile width at 390px and 1280px.

## Catalog filter clarity — 2026-10-28

Discovery now tells operators when edited filters have not been searched and
disables result paging until Search applies them. Whitespace-only edits do not
create a false pending state. The Discovery page suite passes 14 tests, and
the responsive catalog browser checks pass at 390px and 1280px. Catalog reads
and all authority boundaries are unchanged.

## Workflow filter clarity — 2026-10-28

The workflow dashboard now identifies draft filters that have not been applied
and pauses Previous and Next until the operator applies them. Applying a filter
still returns the list to its first page. The page suite passes 10 tests, and
six browser checks pass across 390px and 1280px. Workflow retrieval and
approval behavior are unchanged.

## Readiness blocker wording — 2026-10-28

The installation readiness review now explains every blocker in operator-facing
language, including incomplete evidence, ownership and record mismatches,
unclear prior status, unavailable sources, and unsupported installation. The
technical blocker codes remain under the collapsed review details. The focused
readiness page suite passes 25 tests, including coverage for all 12 blocker
explanations. Evidence collection, permissions, and execution boundaries are
unchanged.

## Action history empty results — 2026-10-28

When applied filters return no rows, Action history now says “No matching
actions” and points operators to change or clear filters. An unfiltered empty
history still explains that Atlas Core action records appear here. Focused page
tests cover both states and preserve protection against a slower old filter
response replacing the current results.

## Agent card destination — 2026-10-28

The home screen's Agent details card now stays focused on the Agent identity
report. Its deployment-analysis link was unrelated to that card's contents and
has been removed; Deployment analysis remains available from the main
navigation. No Agent status or execution capability was added.
The Agent/provider and main overview suites pass 69 tests, and the built-app
navigation journey passes all nine checks, including direct access to
Deployment analysis. Mission Control lint and production build pass.

## Operator Attention stale workflow copy — 2026-10-28

Operator Attention no longer repeats the generic stale-condition sentence
after the more specific last-known workflow warning. Stale provider, service,
and AI conditions retain their generic freshness explanation. Overview tests
cover both cases; workflow state and source evidence are unchanged.

## Planning session status refresh — 2026-10-28

When Atlas reports that it is still creating a plan, the page now offers a
“Check plan status” control that repeats only the planning-session read. It
shows the ready plan when available and does not submit another planning
request. The focused test verifies the read and confirms no generation call is
made.

## Workflow setup title — 2026-10-28

The workflow preparation screen now opens with the operator-facing title
“Workflow setup” instead of a workflow UUID. The ID is under collapsed Workflow
details beside the other references. Component tests and the repository browser
journey verify the title, hidden-by-default ID, and access to the ID when
details are opened. The workflow shell suite passes 31 tests, the repository
journey passes all eight checks at 390px and 1280px, and lint/build pass.
Approval and execution steps are unchanged.

## Maintenance request title — 2026-10-28

The maintenance page heading now says “Request a restart proposal,” matching
the actual result: a proposal for separate review and approval. The explanatory
boundary and request behavior are unchanged. The component test and sign-in and
maintenance browser journeys assert the updated title.

## Action history detail wording — 2026-10-28

The action history detail screen now uses “Action details” and plain action
history wording for its loading, unavailable, copy-link, and record-link
messages. The action list link now says “View action details.” Record IDs stay
under collapsed technical details. This is a wording change only; history reads
and retention behavior are unchanged.

## Workflow audit error wording — 2026-10-28

Failed workflow-audit reads now show a plain explanation and a read-only retry.
Parser and service errors stay under collapsed Technical details. A response
for another workflow keeps a specific mismatch message. The focused page suite
passes 20 tests; the malformed-audit browser recovery passes at 390px and
1280px, and lint/build pass. Retry still performs only the audit read.

## Maintenance status retry wording — 2026-10-28

The unavailable lifecycle panel now labels its read-only retry “Check status
again” and says plainly that it does not repeat the maintenance action. The
workflow test confirms the retry reloads status without resubmitting approval
or resuming work.

## Maintenance approval wording — 2026-10-28

The workflow now calls the operational request a “Maintenance request,” labels
its approval and rejection buttons with that request, and names the later run
button “Run approved maintenance.” The text makes clear that approval does not
run the request and that starting maintenance remains a separate step. The
maintenance page test confirms that rejection does not run it, and the browser
journey verifies the separate approval and run requests; no API contract or
permission boundary changed.

## Workflow setup preparation wording — 2026-10-28

Workflow setup now calls its action “Prepare change for review” and explains
that the request must be reviewed, approved, and started in separate steps.
Uncertain preparation results direct the operator to reload and check status;
they do not invite a duplicate request. The focused page suite passes (31
tests), both repository and maintenance browser journeys pass (10 tests across
390px and 1280px), and lint, build, and `git diff --check` pass. Request
contracts and approval/run boundaries are unchanged.

## Maintenance progress labels — 2026-10-28

Provider details now describe maintenance as a request, review, approval, and
separate start. Operational workflow details use “Maintenance progress” instead
of “Execution timeline,” translate internal stage names into plain labels, and
report approval in maintenance terms. The provider and timeline suites pass
(19 tests), the maintenance browser journey passes at 390px and 1280px (2
tests), and lint, build, and `git diff --check` pass. Lifecycle evidence and
permissions are unchanged.

## Provider action-list recovery wording — 2026-10-28

When the provider action list cannot load, the screen now says plainly that the
list is unavailable and no action was run. Service details stay collapsed, and
“Try again” repeats only the list read. The focused component suite passes (10
tests), the source-server browser recovery passes (1 test), and lint, build,
and `git diff --check` pass. Uncertain action results still use their separate
Action history guidance; no provider action behavior changed.

## Provider connection read-error wording — 2026-10-28

A failed connection-settings read now says the settings are unavailable and
that no settings changed. The service error is under collapsed Technical
details; Refresh settings continues to repeat only the read. The connection
suite passes (16 tests), along with lint, build, and `git diff --check`. Test
and save failures retain their existing secret-redacted messages.

## Provider resource-read error wording — 2026-10-28

Inventory failures now say that observed resources could not be loaded, while
monitoring failures explain that settings are unavailable and observed
inventory remains visible. Service errors are optional Technical details. The
provider resources suite passes (54 tests), along with lint, build, and
`git diff --check`. Resource and monitoring reads, edit permissions, and
monitoring mutation rules are unchanged.

## Action history read-error wording — 2026-10-28

When action history cannot be read, the page now gives a plain recovery message
and explains that the failed read did not run a provider action. Backend error
text is under collapsed Technical details. The existing Refresh history control
retries the read; expired-entry deletion remains disabled until history loads.
The focused page test checks the error detail visibility, read-only retry, and
deletion guard. No history or provider action behavior changed.

## Action detail read-error wording — 2026-10-28

When one action-history record cannot be read, the detail page now explains
that the record is unavailable and that retrying only reloads the record. The
service response stays under collapsed Technical details. Tests cover both a
transient read failure and a missing record; the retry continues to call only
the record-read endpoint. No provider action behavior changed.

## Action history export and cleanup errors — 2026-10-28

Export and expired-entry deletion failures now use plain messages with backend
responses under collapsed Technical details. If deletion returns an uncertain
result, Mission Control pauses another delete until Refresh history successfully
reloads both the records and retention summary. The page test verifies that
refresh only reads and that deletion becomes available again after both reads
succeed. The recovery refresh performs only reads and never invokes a provider
action.

## Maintenance proposal response recovery — 2026-10-28

Server and network failures during restart-proposal creation now say that the
proposal result is unconfirmed and make clear that the VM has not restarted.
The page links to Change proposals so an operator can check before retrying.
Tests cover HTTP 503 and a lost-response case, and verify the link does not
submit a second request. No approval or execution step changed.

## Provider action uncertain-result pause — 2026-10-28

When Mission Control loses the final result of a provider action, all provider
action controls on that page are paused. The message directs the operator to
Action history and says to reload the provider page before deciding whether to
retry. Tests verify enabled actions become disabled, inputs are unavailable,
and clicking again cannot submit a duplicate request. Provider execution and
approval contracts are unchanged.

## Maintenance history filters — 2026-10-28

Maintenance history hides requested-action, provider, and resource-type filters
when each has only one value on the current page. It shows a filter when the
page contains multiple values. This removes controls that could not narrow the
results while retaining the current-page filter boundary.

## Successor planning response recovery — 2026-10-28

If a successor planning request returns no usable response, Workflow setup now
says its result is unconfirmed and links to the source planning session, which
can show whether a newer session exists. The service response stays under
collapsed Technical details. The workflow-shell test covers this recovery
path; successor creation and execution behavior are unchanged.

## Built frontend verification — 2026-10-28

The built-preview Playwright suite passes all 76 compatible browser cases
against the generated frontend assets. The suite covers responsive navigation,
the repository and maintenance journeys, provider and history summaries, and
the overview. API interactions use isolated fixtures. Source-module loading and
screen-recovery cases remain in the 133-test development-server suite.

## Prospective destination mutation recovery — 2026-10-28

Selection and admission-assessment failures now lead with plain-language
uncertainty; backend responses stay under collapsed Technical details. A
failed destination selection keeps its original request key on a Retry
selection control, while other destinations remain unavailable until the
result is recovered. This lets Core replay a saved selection instead of
creating another one. Assessment retries reuse the key only while the exact
plan and selection are unchanged. The focused screen suite passes (13 tests),
the full Mission Control suite passes (2,779 tests across 181 files), lint and
production build pass, and the live-delivery structural boundary test passes.
No API contract, authorization check, installation action, approval, or
execution capability changed.

## Read-only installation check recovery — 2026-10-28

The capability and candidate-admission panels now show a plain error summary,
keep server diagnostics collapsed, and offer a retry that reloads the same
read-only GET. Their focused suites pass (11 tests), as do the full Mission
Control suite (2,779 tests across 181 files), lint and production build. No
mutation, selection, approval, installation, or execution route is added.

## Saved candidate record mutation recovery — 2026-10-28

Preservation failures now explain the uncertain result and retry with the same
idempotency key. A delete failure pauses further mutations until a read refresh
confirms whether the saved record remains; Mission Control does not repeat the
delete automatically. Backend diagnostics stay collapsed. The lifecycle suite
passes (8 tests), the full Mission Control suite passes (2,782 tests across
181 files), lint and production build pass. API and approval contracts are
unchanged.

## Saved candidate record read recovery — 2026-10-28

The saved-record list and individual record review now have separate failure
states. A failed review read leaves the saved-record list available; both read
paths show a plain summary, collapsed technical details, and a retry that
repeats only the same GET. The lifecycle suite passes (9 tests), the full
Mission Control suite passes (2,783 tests across 181 files), lint and
production build pass. Mutation, approval, and execution behavior is
unchanged.

## Saved candidate record summary — 2026-10-28

Saved records now label whether their source facts are still current or have
expired. Reviewing a record leads with that plain-language state and its
non-approval boundary; IDs, fingerprints, timestamps, and explicit authority
flags remain available under collapsed Record details. The lifecycle suite
passes (9 tests), the full Mission Control suite passes (2,783 tests across
181 files), lint and production build pass. No backend contract or action
changed.

## Approval evidence detail summary — 2026-10-28

Reviewing recorded approval evidence now leads with its historical, read-only
status and whether the source record is still available. Operator,
record, statement, and fingerprint fields remain available under collapsed
Evidence details. The focused approval-evidence suite passes (6 tests), the
full Mission Control suite passes (2,783 tests across 181 files), lint and
production build pass. No approval-recording behavior or authority changed.

## Approval evidence read recovery — 2026-10-28

Failed approval-evidence list reads now show a plain message, collapsed
diagnostics, and a retry that repeats only the list GET. Failed detail reads
stay with the selected record, keep the list available, and retry only that
record GET. The approval-evidence suite passes (7 tests), the full Mission
Control suite passes (2,784 tests across 181 files), lint and production build
pass. Approval recording and its uncertain-outcome boundary are unchanged.

## Uncertain approval evidence recording recovery — 2026-10-28

When the approval-evidence write has an unknown result, Mission Control now
says it could not confirm the outcome, keeps the candidate locked against
another write, and offers a GET-only check. A matching saved record is shown
for review; no match leaves the outcome explicitly uncertain and does not
resubmit the write. The approval-evidence suite passes (8 tests), the full
Mission Control suite passes (2,785 tests across 181 files), lint and
production build pass. No backend or authority contract changed.

## Workflow support evidence read recovery — 2026-10-28

If support evidence cannot be prepared, the same read now has an explicit
Retry support evidence action. If a local download fails after preparation,
the message directs the operator to retry the existing download; it does not
refetch or upload anything automatically. The Workflow page suite passes (80
tests), the full Mission Control suite passes (2,786 tests across 181 files),
lint and production build pass. Workflow actions and approvals are unchanged.

## Maintenance history outcome recovery — 2026-10-28

When the history read fails, the alert now states that the maintenance outcome
is unknown and directs the operator to the existing Refresh history control.
The Operational history suite passes (13 tests), the full Mission Control
suite passes (2,786 tests across 181 files), lint and production build pass.
No maintenance action or backend contract changed.

## Maintenance proposal result recovery — 2026-10-28

If proposal creation has an uncertain result or the returned proposal does not
match the selected VM, the request screen locks target selection, refresh, and
submission, then directs the operator to check the proposal list. This prevents
an immediate duplicate request from the same screen. The Maintenance request
suite passes (31 tests), the 390px synthetic browser recovery check passes,
the full Mission Control suite passes (2,786 tests across 181 files), and lint
and production build pass. Backend contracts and execution authority are
unchanged.

## Home header simplification — 2026-10-28

The home screen no longer repeats “Mission Control” in the sticky route label;
the app brand and page heading keep the screen identified. Focused layout tests
pass (33 tests), mobile development and built-preview checks pass, and the
full Mission Control suite passes (2,786 tests across 181 files), lint and
production build pass. Routes and navigation behavior are unchanged.

## Dashboard approval summary clarity — 2026-10-28

Workflow attention links now show the work name, with the specific approval
needed on a separate line. Stale workflow status remains explicitly
last-known. The two focused component suites pass (81 tests), five development
browser checks and one built-preview check pass, and the full Mission Control
suite passes (2,786 tests across 181 files), lint and production build pass.
Approval and execution behavior are unchanged.

## Maintenance resource empty state — 2026-10-28

The maintenance request screen now shows an explicit loading state before
reporting that no VMs are available. After a successful empty result, it
explains that there are no selectable VMs and keeps Refresh as the recovery;
proposal submission stays disabled. The focused page suite passes (32 tests),
the 390px fixture-backed browser check passes, the full Mission Control suite
passes (2,787 tests across 181 files), lint passes, and the production build
passes. No API contract or approval boundary changed.

## Dashboard destination naming — 2026-10-28

The home destination, main landmark, and page heading are now called
“Overview,” while “Mission Control” remains the app identity in the brand.
This removes the repeated product name from the main screen and gives the root
menu item a clear page label. The focused layout/dashboard tests pass (92
tests), and the 390px dashboard browser check passes. Shell/navigation/loading
browser checks pass (21 tests in development and 17 against the built app).
The full Mission Control suite passes (2,787 tests across 181 files), lint and
production build pass. Routes, API requests, and authority are unchanged.

## Provider action history destination — 2026-10-28

The dashboard card is now named “Recent provider actions,” distinguishing it
from workflow activity. Its “Open action history” link now opens the Action
history page instead of the separate maintenance history screen. Empty,
loading, stale, and unavailable messages use the provider-action context. The
focused dashboard suites pass (81 tests), responsive dashboard browser checks
pass (25 tests in development and 25 against the built app), the full Mission
Control suite passes (2,787 tests across 181 files), and lint and production
build pass. No API or authority contract changed.

## Health-card navigation simplification — 2026-10-28

The System health and Service checks cards no longer show generic Operations
links that led to Action history. Action history stays linked from Recent
provider actions, and workflows stay linked from Work activity. This removes
duplicate navigation from cards that summarize health. The focused overview
suite passes (59 tests), responsive dashboard browser checks pass (25 tests in
development and 25 against the built app), and the full suite passes (2,787
tests across 181 files). Lint and production build pass. No route, API, or
authority changed.

## Atlas Doctor placement — 2026-10-28

Atlas Doctor no longer interrupts Action history between retention controls
and action records. It is now under System health in a collapsed disclosure;
the diagnostic request still runs only after an explicit “Run Doctor” click.
Focused Operations/overview/Doctor tests pass (77 tests), browser checks pass
(16 tests in development and 16 against the built app), the full suite passes
(2,788 tests across 181 files), and lint and production build pass. No API or
authority behavior changed.

## Action history confirmation labels — 2026-10-28

Action history now labels the recorded confirmation as “Operator confirmed”
and the action classification as “Destructive action,” clarifying the meaning
of both badges in the list and detail view. Component and responsive browser
coverage verifies both labels. The focused list/detail suites pass (20 tests),
the responsive browser suite passes (4 checks in development), and lint and
production build pass. The audit data and action behavior are unchanged.

## Workflow progress language — 2026-10-28

Workflow rails and the repository change-progress timeline now use operator
labels such as “Change proposal,” “Change approval,” “Apply change,” and “Verify
change.” Raw statuses are presented as “Done,” “Current step,” and “Not
started.” Unrecognized statuses stay marked “Status unavailable.” Workflow
state values and approval controls are unchanged. The full Mission Control
suite passes (2,790 tests across 181 files), responsive workflow/dashboard
browser checks pass (14 tests), and lint and production build pass. Browser
workflow mutations remain intercepted by synthetic fixtures.

## Workflow verification details — 2026-10-28

The verification and review screen keeps planned checks, recorded check
results, review findings, and changed files visible. Plan IDs, verifier
versions, paths, repository references, hashes, and review fingerprints are
available under a collapsed “Technical details” disclosure. Verification
approval and Resume remain separate controls. The WorkflowPage suite passes
(80 tests), the fixture-backed repository journey passes at 390px and 1280px
(8 browser tests), the full Mission Control suite passes (2,790 tests across
181 files), and lint and production build pass. Browser workflow writes remain
intercepted by synthetic fixtures; no API contract or authority behavior
changed.

## Repository change summary — 2026-10-28

The workflow now presents the proposed tool and affected files under “Change
details.” Repository paths, translator version, and immutable request ID are
still available in collapsed technical details. When the request is missing,
the page gives a plain-language status and directs the operator to refresh.
Approval boundaries and request data are unchanged. The focused WorkflowPage
suite passes (81 tests), the responsive fixture-backed repository journey
passes (8 tests at 390px and 1280px), the full Mission Control suite passes
(2,791 tests across 181 files), and lint and production build pass. Browser
workflow writes remain intercepted by synthetic fixtures.

## Commit review details — 2026-10-28

The commit card leads with the target branch, commit message, files, and
approval status. Repository path, expected HEAD, request ID, and reviewed
content fingerprint remain available under collapsed technical details. The
card continues to describe approval and local commit as separate steps, with
no push or release action. The focused WorkflowPage suite passes (81 tests),
the responsive fixture-backed repository journey passes (8 tests at 390px and
1280px), the full Mission Control suite passes (2,791 tests across 181 files),
and lint and production build pass. Browser workflow writes remain
intercepted by synthetic fixtures.

## Workflow audit stage labels — 2026-10-28

The audit timeline uses the same operator language as the workflow journey:
“Change proposal,” “Change plan,” “Change approval,” “Apply change,” “Checks
to run,” and “Check results.” Stages that have not begun show “Not started.”
The audit remains read-only, and detailed evidence stays collapsed. The focused
WorkflowAuditPage suite passes (20 tests), the responsive fixture-backed
repository journey passes (8 tests at 390px and 1280px), the full Mission
Control suite passes (2,792 tests across 181 files), and lint and production
build pass. Browser workflow writes remain intercepted by synthetic fixtures.

## Verification progress wording — 2026-10-28

The workflow now labels the planned checks and their results in plain language.
Before verification runs, Mission Control shows the required next step and
keeps empty result and review fields off the page. After verification runs, it
shows the recorded results and review details. The review summary gives one
decision, findings, and changed files; detailed review statuses remain under
Technical details. Separate verification approval and Resume controls remain
unchanged. The focused WorkflowPage suite passes (82 tests), the responsive
fixture-backed repository journey passes (8 tests at 390px and 1280px), the
full Mission Control suite passes (2,792 tests across 181 files), and lint and
production build pass. Browser workflow writes remain intercepted by synthetic
fixtures.

## Planning plan references — 2026-10-28

The plan review keeps the target branch, affected files, proposed steps, and
verification strategy visible. The repository HEAD and evidence IDs are
available under collapsed technical details. The focused PlanningSessionPage
suite passes (35 tests), the responsive fixture-backed repository journey
passes (8 tests at 390px and 1280px), the full Mission Control suite passes
(2,792 tests across 181 files), and lint and production build pass. Browser
workflow writes remain intercepted by synthetic fixtures.

## Proposal eligibility wording — 2026-10-28

The proposal list and detail page now label eligible proposals “Eligible for
planning,” which is shorter and easier to scan. The page still states that
planning and approval are separate steps. The complete Mission Control suite
passes (2,792 tests across 181 files), proposal-list browser checks pass at
390px and 1280px (6 checks), and lint and production build pass. Browser reads
use synthetic fixtures; no API or approval behavior changed.

## Provider refresh recovery — 2026-10-28

The provider registry keeps its last loaded list on screen during refresh and
after a failed refresh. Its status is marked unknown while refreshing or after
failure, and the page explains when it is showing the last response. This
avoids both a disappearing list and a stale health value that looks current.
The full Mission Control suite passes (2,792 tests across 181 files), provider
registry browser checks pass (5 checks, including 390px and 1280px recovery),
and lint and production build pass. Browser reads use synthetic fixtures.

## Compatibility finding labels — 2026-10-28

The catalog item compatibility screen now translates finding statuses and
severity into readable labels, describes unconfirmed facts in plain language,
and keeps finding codes, checked fields, evidence records, and raw timestamps
under optional technical details. The full Mission Control suite passes (2,792
tests across 181 files), focused compatibility browser checks pass at 390px
and 1280px, and lint and production build pass. All browser API reads use
synthetic fixtures; no assessment or authorization behavior changed.

## Catalog item summary — 2026-10-28

The catalog item header now keeps the display name, type, and status up front;
the item ID is under Technical details. Capability codes display as readable
labels under “What it supports.” The full Mission Control suite passes (2,792
tests across 181 files), the compatibility and catalog summary browser checks
pass at 390px and 1280px, and lint and production build pass. Browser reads use
synthetic fixtures; catalog data and approval boundaries are unchanged.

## Missing catalog item recovery — 2026-10-28

A missing catalog item now explains that it is no longer available and gives a
direct way back to the catalog. Its item ID stays under collapsed Technical
details. Mission Control waits for the catalog entry before requesting its
related plan, relationships, evidence, compatibility, image grounding, and
proposals, so a missing item produces only the catalog lookup. The full
Mission Control suite passes (2,792 tests across 181 files), the missing-item
browser checks pass at 390px and 1280px, and lint and production build pass.
Browser checks use synthetic fixtures and reject mutations.

## Catalog card summary — 2026-10-28

Catalog cards now show capabilities and tags as readable labels. The internal
catalog item ID is available under collapsed Technical details. The full
Mission Control suite passes (2,792 tests across 181 files), catalog browser
checks pass at 390px and 1280px, and lint and production build pass. Browser
checks use synthetic fixtures and reject mutations.

## Provider action field labels — 2026-10-28

Provider action forms now turn parameter keys such as `resource_id` into
readable field labels such as “Resource ID.” Requests retain the exact
provider-supplied parameter keys. The full Mission Control suite passes (2,793
tests across 181 files), responsive browser checks pass at 390px and 1280px,
and lint and production build pass. Tests confirm no backend contract or
approval behavior changed.

## Maintenance target labels — 2026-10-28

The restart request screen labels VM identifiers as “VM ID,” the Proxmox node
as “Host,” and the capability’s QEMU value as “VM type.” The selected target,
proposal-only first step, and separate approval and execution controls remain
unchanged. The full Mission Control suite passes (2,793 tests across 181
files), the maintenance journey passes at 390px and 1280px, and lint and
production build pass.

## Action history filter accessibility — 2026-10-28

The All, Succeeded, and Failed controls are now exposed as one named filter
group, and assistive technology can identify the selected status. Filter
requests and results are unchanged. The full Mission Control suite passes
(2,793 tests across 181 files), responsive browser checks pass at 390px and
1280px, and lint and production build pass.

## Current page announcement — 2026-10-28

The shared header now exposes the current route as a polite status announcement,
including a screen-reader prefix, instead of relying on an `aria-label` on a
plain span. Browser checks confirm the route label updates after navigation.
The full Mission Control suite passes (2,793 tests across 181 files), responsive
shell and recovery browser checks pass (69 checks at 390px and 1280px), and
lint and production build pass. Browser API responses are synthetic; no
navigation or API behavior changed.

## Browser tab page title — 2026-10-28

The browser tab now identifies the current Mission Control page, including
after in-app navigation and browser back/forward. The default title is useful
before client-side code loads, and record identifiers are not included. The
full Mission Control suite passes (2,793 tests across 181 files), all 8
Mission Control shell browser checks pass, and lint and production build pass.
The browser checks cover 390px and 1280px plus route changes and browser
history. This is a presentation-only change.

## Missing-page shell context — 2026-10-28

Unknown routes now use “Page not found” in the shell announcement and browser
tab, matching the recovery screen heading. The destination menu remains
available so an operator can choose a working screen. The full Mission Control
suite passes (2,794 tests across 181 files), both missing-page browser checks
pass at 390px and 1280px, and lint and production build pass. Navigation and API
behavior are unchanged.

## Dashboard attention loading state — 2026-10-28

When only some dashboard reports have returned, Operator Attention now says
that the remaining checks are still running and that the list may change. It
shows the missing-information warning after the refresh completes, when the
source gaps are known. This removes a temporary failure message while reads
are pending. The full Mission Control suite passes (2,795 tests across 181
files), overview browser checks pass (14 tests at 320px, 390px, 768px, 1280px,
and 1440px), and lint/build pass. API reads and attention decisions are
unchanged.

## Agent summary labels — 2026-10-28

The dashboard Agent card now labels the product name and version separately,
shows “Not reported” when the version is absent, and displays the service's
`atlas-agent` identifier as “Atlas Agent.” The redundant summary sentence is
removed. The full Mission Control suite passes (2,796 tests across 181 files),
all 14 overview browser checks pass, and lint and production build pass. Browser
API reads use synthetic fixtures; no API or approval behavior changed.

## Work activity summary wording — 2026-10-28

The dashboard now says its workflow counts and results are a read-only summary,
instead of saying “this page does not start work,” which was unclear beside the
link to review workflows. The focused Work activity suite passes (28 tests),
all 14 overview browser checks pass, and lint and production build pass. No
workflow action, approval, or API behavior changed.

## Workflow directory phone spacing — 2026-10-28

The workflow list, loading, and recovery screens now use compact page padding
on phones and retain the existing desktop spacing. Browser checks cover all
three states at 320px, 390px, and 1280px (9 checks); the workflow directory
component suite passes (10 tests), as do lint and the production build. Workflow
data, navigation, and approval behavior are unchanged.

## Proposal journey phone spacing — 2026-10-28

The change-proposal directory and detail page now use compact padding on phones,
including detail-page loading and recovery states, while keeping desktop spacing.
All 12 proposal browser checks pass at 320px, 390px, and 1280px; the two focused
page suites pass (32 tests), as do lint and the production build. Planning,
approval, and proposal data behavior are unchanged.

## Action history phone layout and empty state — 2026-10-28

Action history and its empty/loading panels now use compact phone padding while
retaining desktop spacing. The empty state says “Provider actions Atlas has run
will appear here,” removing an unnecessary Core implementation detail. All 12
browser checks pass at 320px, 390px, and 1280px; the page suite passes (14
tests), as do lint and the production build. History filters and actions are
unchanged.

## Catalog detail retry and phone layout — 2026-10-28

The catalog list and item detail states now use compact phone padding while
keeping desktop spacing. If a detail response belongs to a different catalog
item, the screen refuses it and offers an in-page retry for the requested item.
Browser checks cover catalog filtering and recovery at 320px, 390px, and 1280px
(20 checks); the focused catalog page suites pass (50 tests), as do lint and the
production build. Catalog reads and all action/approval behavior are unchanged.

## Provider detail phone layout — 2026-10-28

Provider detail, loading, and missing-provider screens now use compact phone
spacing, including the provider summary card, while retaining desktop spacing.
Browser checks cover loaded details and the missing-provider route at 320px,
390px, and 1280px, plus the loading state at phone and desktop widths (8 checks);
provider action-field labels are also checked at 320px. The three focused
page/component suites pass (17 tests), as do lint and the production build.
Provider reads, actions, and approval behavior are unchanged.

## Workflow setup phone layout — 2026-10-28

The workflow setup page now uses compact outer padding on phones in its loading,
unavailable, and loaded states, while retaining desktop spacing. The full
synthetic repository journey, uncertain-approval recovery, and unreadable
preparation recovery are covered at 320px, 390px, and 1280px. Loading and
initial-read failure states are checked at phone and desktop widths (11 browser
checks). The workflow page suite, lint, and production build pass. Approval,
resume, and execution behavior are unchanged.

## Planning session recovery and phone layout — 2026-10-28

Planning-session loading, error, and review screens now use compact phone
spacing. Session-read failures can retry in place. After an uncertain plan
generation result, “Check for saved plan” re-reads the session and saved plan;
it does not run generation again. Browser coverage includes loading, read
recovery, malformed saved plans, and the synthetic approval journey at phone
and desktop widths (10 checks). The focused page suite passes (35 tests), as do
lint and the production build. No approval or infrastructure change was added.

## Maintenance request phone layout — 2026-10-28

The maintenance request and session-restoration screens now use compact phone
spacing while retaining desktop spacing. Synthetic browser checks cover session
loading, the full request-through-audit journey, uncertain proposal recovery,
and the empty resource list at 320px, 390px, and 1280px (11 checks). The
maintenance request page suite passes (32 tests), as do lint and the production
build. Target selection, proposal submission, approval, and execution behavior
are unchanged.

## Workflow review and audit phone spacing — 2026-10-28

Workflow review and both repository and maintenance audit screens now use
compact page spacing on phones across their loading, unavailable, missing, and
loaded states, while retaining desktop spacing. Synthetic browser coverage
checks the full repository and maintenance journeys, loading states, and
read-recovery flows at 320px, 390px, and 1280px (17 checks). The focused
workflow and audit page suites pass (102 tests), as do lint and the production
build. Approval, resume, audit, and execution behavior are unchanged.

## Operator sign-in phone spacing — 2026-10-28

Operator sign-in now uses compact page spacing on phones while keeping its
desktop layout. Synthetic browser checks cover Discovery-to-sign-in context
and rejected credentials at phone and desktop sizes (5 checks). The focused
login and session suites pass (14 tests), as do lint and the production build.
Password clearing, validated return context, and Core-owned authentication
behavior are unchanged.

## Maintenance history phone spacing — 2026-10-28

Maintenance history now uses compact page spacing on phones while keeping its
desktop layout. Synthetic browser checks cover loading, request results,
unavailable history, and incomplete lifecycle details at 320px, 390px, and
1280px (11 checks). The history page suite passes (13 tests), as do lint and
the production build. Filters, pagination, and all maintenance actions are
unchanged.

## Missing-page recovery phone spacing — 2026-10-28

The missing-page screen now uses compact page spacing on phones while keeping
its desktop layout. Browser checks verify the recovery link and return path at
320px, 390px, and 1280px; all 12 navigation checks pass, as do lint and the
production build. Route behavior and navigation destinations are unchanged.

## Action detail loading phone spacing — 2026-10-28

The action detail loading card now uses compact padding on phones while keeping
desktop spacing. Delayed synthetic reads verify loading and recovery into the
record at 320px and 1280px (2 browser checks). The focused action-detail suite
passes (6 tests), as do lint and the production build. Action records and
provider behavior are unchanged.

## Maintenance approval wording — 2026-10-28

The overview attention list and workflow cards now identify an operational
approval as maintenance-request approval. Repository changes retain their
implementation-approval wording, and stale maintenance records remain marked
last-known. The focused dashboard suites pass (78 tests), along with six
synthetic browser checks at 320px, 390px, and 1280px; lint and the production
build pass. Approval authority and workflow transitions are unchanged.

## Maintenance workflow summary wording — 2026-10-28

The workflow detail summary now says “Maintenance request needs approval,”
matching the exact approval control and the later approved status. The focused
workflow page suite passes (82 tests), and the synthetic maintenance journey
passes at 320px, 390px, and 1280px (3 checks); lint and the production build
pass. Approval and run steps remain separate.

## Maintenance status summary simplification — 2026-10-28

The maintenance workflow now leads with a plain-language status, explanation,
and safe next step. Recovery reasons and suggested actions use operator terms;
record consistency, target identity, dispatch, verification and support fields
are under a closed “Technical details” disclosure. Maintenance history keeps
the compact status and guidance without exposing that technical disclosure.
Focused workflow, history and summary tests pass (124 tests). Synthetic browser
coverage passes for the workflow at 320px, 390px and 1280px; history recovery
at those widths; and unavailable status at 390px and 1280px (8 checks total).
Mission Control lint and build pass. Browser requests use synthetic fixtures;
approval and execution boundaries are unchanged.

## Maintenance history detail labels — 2026-10-28

The optional request details now translate record consistency and verification
states into readable results such as “Records match,” “Request details differ,”
and “Passed.” The history no longer exposes their backend state names. The
focused history and recovery-summary suites pass (51 tests), the unavailable
history browser checks pass at 320px, 390px and 1280px (3 checks), and lint and
build pass. Filtering, request links and maintenance actions are unchanged.

## Work activity unavailable-state wording — 2026-10-28

When workflow data is incomplete or contains an unfamiliar status, Work activity
now says why its running and blocked counts are hidden. It also explains when
Mission Control cannot read a recorded execution result without calling the
evidence “malformed.” Counts remain hidden unless the full list and statuses
can be checked. The focused overview and work-activity suites pass (91 tests),
the responsive browser check passes at 320px and 1280px (2 checks), and lint
and build pass. No workflow or execution state is changed.

## Health status unknown wording — 2026-10-28

Health badges now say “Status unknown” instead of the context-free “Unknown.”
When showing an older report after refresh fails, the badge names the current
status as unknown and the accompanying line only states the last reported
status. Core health evidence and status mapping are unchanged. The full
Mission Control component suite passes (2,830 tests), the full synthetic
browser suite passes (212 tests), and lint and production build pass. These
fixtures do not establish live backend connectivity or operator acceptance.

## Core-side service check location — 2026-10-28

The active Overview service-check list now has a closed “Where Atlas checked”
disclosure for each reported service. It shows the configured address without
URL credentials or query values and explains that Atlas Core checks from its
own machine, so browser reachability alone does not establish Core reachability.
The disclosure also shows a reported HTTP response or explains that no response
was received, plus response time when Core reports one. When more than four
service checks or providers are reported, blocked and offline entries appear
before degraded, unknown, and healthy entries. The provider list uses a singular
label when one additional provider is hidden. The Overview and provider
component suites pass (79 tests across two files), all Overview browser checks
pass (23 tests, including 320px and 1280px layouts), and lint and production
build pass. The UI displays reported configuration only; it does not change
probe behavior or establish live network reachability.

## Work activity outcome priority — 2026-10-28

The recorded execution outcomes preview now puts failed executions before
completed executions. Each group keeps its workflow-ID order because the source
does not report execution times. Running and blocked workflow lists, workflow
state, and execution controls are unchanged. The Work activity component suite
passes (29 tests), the Overview browser suite passes (24 tests, including the
320px phone layout), and lint and production build pass.

## Overview service-check guidance — 2026-10-29

The active Overview's “Where Atlas checked” disclosure now suggests a next
check for connection-refused, no-route, unreachable-network, DNS, and timeout
results from Atlas Core's network location. Exact service messages remain
available in the visible health summary, while the disclosure keeps the address
and response details optional. Health state and probing behavior are unchanged.
Overview tests cover each failure type at component level and no-route in the
browser suite.

## Empty service-check summary — 2026-10-29

When Core reports no configured service checks, the empty-state explanation now
appears only in the Service checks card instead of repeating in System health.
The focused Overview test confirms the message remains with its list.

## Catalog read-failure summary — 2026-10-29

When catalog results cannot be loaded, the Discovery page no longer repeats an
“Items unavailable” count above the “Results unavailable” panel. The retry
button, selected filters, and collapsed technical error remain available.
Page and responsive browser tests cover the unavailable and retry states.

## Provider registry keyboard focus — 2026-10-29

The registry's Mission Control and provider-detail links now use the shared
visible keyboard-focus style. A focused page test checks tab order and both link
focus styles.

## Repository workflow future-stage panels — 2026-10-29

Early repository workflows keep the planned verification checks visible while
hiding empty check results, review results and verification-approval panels.
Those panels appear when their stage is current or corresponding evidence or a
decision exists. The Commit section appears when a commit request or result
exists or the workflow reaches the commit stage; missing details remain visible
as an unavailable state when commit is current. These changes do not alter
approval decisions, request bodies, resume behavior or execution authority.
When an approval is already resolved, its panel says the decision was recorded
or rejected instead of describing approval as unavailable.
The WorkflowPage suite passes (86 tests), the repository-journey browser suite
passes (11 checks at 320px, 390px and 1280px), and lint and production build
pass. Browser writes remain confined to the exact synthetic journey fixture.

## Action history labels — 2026-10-29

Navigation, page titles, filters, loading and error states, and record links use
the shorter “Action history” wording. Action-detail screens use “Action details.”
Routes, API requests, records, and authority boundaries are unchanged.
The focused layout and history page suites pass (54 tests); the action-history,
navigation, and shell browser checks pass (34 tests across phone and desktop
widths). Mission Control lint and production build pass.

## Overview and history wording — 2026-10-29

The Overview's “Where Atlas checked” guidance now explains the Core network path
in fewer steps and keeps the Docker-container check clear. Action-history
retention controls use the shorter “Export or delete history” label. A failed
health refresh continues to mark earlier service results as last reported, so
the screen does not present an unavailable response as a new service result.
The full Mission Control component suite passes (2,869 tests), all 221 local
browser checks pass, and lint and production build pass. Browser fixtures remain
isolated and reject unconfigured mutations.

## Planning page labels — 2026-10-29

The planning page now labels a maintenance plan as “Maintenance plan” at the
section heading and avoids repeating that heading inside the plan card.
Repository plans retain “Candidate plan.” This removes repository-specific
wording from the maintenance journey without changing plan requests or workflow
approval. Planning page tests and the maintenance browser journey cover both
labels.

## Readiness review boundary wording — 2026-10-29

The readiness page now distinguishes its read-only evidence review from the
separate permission-evidence section. The banner explains that saving the
separate record is permanent, requires confirmation, and does not authorize or
start installation or execution. The underlying request, confirmation, and
authority fields are unchanged; component and responsive readiness tests cover
the wording.

## Compose reachability instructions — 2026-10-29

The Overview now says to run Compose from the directory containing Atlas's
Compose file on the Atlas Core machine. This clarifies why the file may be
missing when the command is run from a service host or another directory. The
guidance remains read-only and does not change service probes. Overview tests
cover the instruction at component and phone/desktop browser level.

The same disclosure explains how to check a bridged service container's
published host port with `docker ps`. This makes an empty `PORTS` column
actionable when Atlas Core checks a service on another machine. It now says to
run `docker ps` on the machine running the app and find its container. If the
`PORTS` column is blank, add a `ports:` mapping to the service's Compose file or
use `docker run -p`, then recreate the container. The guidance does not assume
host networking or change the configured probe. The focused Overview component
tests pass (73 tests), and all 26 built Overview browser checks pass across
phone and desktop layouts. Mission Control lint and production build pass.
Browser fixtures remain isolated and issue no service configuration or
mutation requests.

The same guidance explains the Compose/Docker port order: `HOST_PORT` is the
port in Atlas's reported address, and `CONTAINER_PORT` is the application's
internal listening port, found in its Compose file or documentation. It says
the two may differ. It also clarifies that Docker's `Up` status does not mean
the container's host port is published. Overview component and phone/desktop
browser checks cover the instruction.

It also explains that a Docker port mapping beginning with `127.0.0.1:` is
reachable only from the service host. Atlas Core on another machine needs a
published address it can reach. The Overview fixture and phone/desktop browser
checks cover this distinction.

## Service attention wording — 2026-10-29

The top-level Operator Attention item now uses “Atlas Core could not connect”
for an unavailable service, matching the Service checks card. This keeps a
failed Core-side probe from reading like a claim that the service itself is
offline. Component and phone/desktop browser checks cover the shared label.

The collapsed “About service checks” note now explains in plain language that
the result is reachability from Atlas Core, separate from Atlas Core's own
health.

The service-check guidance explicitly says that testing from the service host
or browser does not establish reachability from Atlas Core. It names the Core
machine/container as the right network location while retaining the Compose
directory and published-port checks.

The collapsed check-location guidance now presents those instructions as a
three-step list: confirm the app's port, test from Atlas Core, and inspect the
published host port for a bridged container. It keeps the Compose directory
check and reported address below the steps. Health probes and status mapping
are unchanged; the steps use 14px text for phone readability. Overview
component and responsive browser checks cover the list.

Provider check history keeps its compact chart and now offers a closed
“Check details” disclosure with each timestamp, duration, and outcome. The
individual results can be opened without relying on hover, and timestamps are
labeled as local time. Collection data and policy limits are unchanged.
The component suite and a built phone-browser check cover the details list and
keyboard opening.

## Recent action time-zone label — 2026-10-29

Recent provider actions now label completion times as local time in the visible
text. The exact UTC time remains available in the time element's title and
machine-readable value. Component and responsive browser checks verify the
visible label and the UTC source value; action records and time conversion are
unchanged.

## Discovery proposal time clarity — 2026-10-29

Proposal generation and expiry times are now labeled as browser local time.
Malformed or impossible timestamps show “Time unavailable” instead of
“Invalid Date.” The underlying proposal expiry and review-only decisions are
unchanged. Component tests cover source timestamps and invalid values.

The Change proposals list uses the same local-time labels for visible expiry
and optional creation times. Invalid times show as unavailable rather than raw
date strings. Planning eligibility and expiry enforcement are unchanged;
component tests verify the source values and invalid-time fallback, while
responsive browser checks verify the labels at phone and desktop widths.

Discovery release evidence also labels published, retrieved, and freshness
expiry times as local time. Invalid timestamps show as unavailable, and the
retrieval age remains alongside its timestamp. Source trust and freshness
decisions are unchanged. A future retrieval timestamp is identified as such
instead of being reported as “less than 1 hour ago.”

## Workflow next-step wording — 2026-10-29

The workflow state that prepares a change now reads “Prepare change” and
“Prepare the change for review,” rather than implying that it is already
waiting for approval. The workflow detail summary uses the same preparation
wording. Later stages say what to review and name the approved follow-up action:
run the change, run checks, or record the commit. Maintenance still requires
its own explicit approval. The dashboard uses “Next step” rather than claiming
approval is needed; its workflow summary contract does not say whether approval
has already been recorded. Counts group preparation separately from approval
or action.
The status filter names preparation, review and run, running, blocked and
completed states in plain language instead of exposing backend state codes.
Approval gates and execution, verification and commit behavior are unchanged.

Five focused component suites pass (208 tests), and the matching responsive
browser suites pass (56 tests across 320px, 390px, 768px, 1280px and 1440px).
Mission Control lint and build pass. Browser requests use synthetic fixtures
that reject unexpected mutations; no real workflow or provider action runs.

The degraded policy message now explains that correcting the file and
refreshing Mission Control checks the policy again. The workflow directory
states that automatic refresh pauses after more than one batch is loaded, and
that Refresh returns to the first batch and turns automatic refresh back on.
The policy and workflow-directory component suites pass (28 tests); Mission
Control lint and production build pass. These wording changes do not alter
policy loading, workflow polling, or approval behavior.

Provider Policies now explains that the page lists rules Atlas uses to check
connected providers and their resources, without relying on the “ACE” acronym.
The degraded state leads with a plain issue count; raw paths, error types and
messages stay under collapsed technical details. Recovery guidance now says
when the last loaded policy settings remain visible and when policy settings
are unavailable. Its focused component suite passes (12 tests), with lint and
build passing.

## Health connection wording — 2026-10-29

The connection-refused summary now says Atlas Core's connection to the
reported address was refused, rather than attributing that response to the
service process. Timeout wording says Atlas Core received no response before
the check timed out. The check and status behavior are unchanged; component
and phone/desktop browser tests cover both messages.

## Maintenance support file simplification — 2026-10-29

Maintenance workflow details now keep the optional support file section
collapsed until requested. The description says the file can be reviewed before
sharing and is not uploaded by Atlas. Preparation and download remain separate
operator actions; completeness is stated plainly, while format, timestamp, and
digest stay under Technical details. The workflow page suite passes (87 tests),
the responsive maintenance browser journey passes at 320, 390, and 1280 pixels
(11 tests), and lint/build pass. Approval, maintenance execution, and audit
behavior are unchanged; the browser fixtures confirm no added workflow writes.

## Discovery catalog source details — 2026-10-29

Catalog provenance no longer takes a full visible panel on each Discovery item
page. Operators can expand Catalog source details when they need the source,
trust level, entry ID, or schema. Catalog review notes, compatibility findings,
and installation readiness remain visible in their existing sections. The
Discovery item component suite covers the closed-by-default state and expansion;
the phone and desktop recovery-browser check covers the same interaction.

Release claims now lead with the version, freshness, publish date, and retrieval
age. Repository, source type, trust label, exact freshness expiry, and upstream
release ID are grouped under Release source details. The Discovery evidence
component test and the phone/desktop sign-in journey verify that those records
stay available and start collapsed; release evaluation and authority remain
unchanged.

## Readiness evidence chain — 2026-10-29

The readiness result and plain-language blockers remain at the top of the page;
the long evidence chain now opens only when requested and shows its record count.
An empty evidence response now says so directly. Evidence contents, expiry
rules, permission recording, and all execution boundaries are unchanged. The
readiness component and phone/desktop browser checks cover collapsed and
expanded records.

## Attention list completeness — 2026-10-29

When a report is unavailable, the attention card now says that some checks
aren't available and that the list may be incomplete. “Which checks are
missing?” opens the affected report details. The warning still avoids claiming
the list is complete, and no attention items or statuses are synthesized.
The focused overview suites pass (95 tests), as do Mission Control lint/build
and all 26 built Overview browser checks across phone and desktop sizes.

## Work activity summary — 2026-10-29

The Work activity note now explains that it shows read-only workflow progress
and results, not whether a worker can take new work. Its collapsed detail link
is labeled “More workflow details.” Workflow counts, recorded outcomes, and
approval behavior are unchanged. The Work activity and overview component suites
pass (102 tests). Mission Control lint/build and all 26 built Overview browser
checks pass across phone and desktop sizes.

## Service connection first steps — 2026-10-29

When Atlas Core cannot connect to a service, Overview now shows the reported
address and the first two useful checks immediately: test from the Atlas Core
machine or container, and inspect Docker's `PORTS` field on a different service
computer. A blank field is explained as no published host port. Detailed
loopback, port-mapping, and Compose guidance stays collapsed under “More
connection checks.” The reported address remains sanitized, and health probes
and authority behavior are unchanged. The component test and 26 built Overview
browser checks pass across phone and desktop sizes. The provider preview browser
check now waits for its fixture data before checking ordering, removing a load
timing race.

## Health report explanation — 2026-10-29

The System health explanation now says each report updates separately, so
their check times may differ. It also states that Atlas does not combine the
reports into one score and marks reports older than a minute as out of date.
This changes the wording only; report sources, freshness rules, and health
states are unchanged. The overview and health presentation suites pass (130
tests); Mission Control lint/build and all 26 built Overview browser checks pass
across phone and desktop sizes.

## Stale health report wording — 2026-10-29

When a report is stale, the status badge remains “Status unknown” and the
accompanying line now labels the value as the last known report and says it is
out of date. This makes the retained status distinct from a current result.
Health state mapping, freshness timing, and refresh behavior are unchanged.
Six focused component and provider suites pass (206 tests), and the built
Overview and system-health browser suites pass all 30 cases across phone,
tablet, and desktop widths. Mission Control lint and build pass. The browser
check for service reachability now follows the current “More connection
checks” disclosure and its visible guidance.

## Atlas Core health label — 2026-10-29

The `/health` report sourced from `health.atlas` is now labeled “Atlas Core
health,” so it is not mistaken for an aggregate of configured service checks.
Service reachability remains a separate report. The health source, status
mapping, and freshness behavior are unchanged. The focused health and Overview
suite passes (130 tests); all 30 built Overview and system-health browser cases,
lint, and build pass.

## Atlas Doctor results — 2026-10-29

The Atlas Doctor action now says “Run health checks,” with the in-progress
state and report count described in plain language. The result labels its
health score and check count, and a failed request explains that no new report
is available. The diagnostic request, report data, and health rules are
unchanged. The focused Atlas Doctor and Overview suites pass (76 tests), as do
Mission Control lint/build and the built Overview browser suite.

## Deployment analysis port wording — 2026-10-29

The service cards now explain which port is on the host machine and which is
inside the container. They describe non-local bindings as potentially
reachable from other computers, and say that Atlas has not checked firewall,
router, or internet access. The “Public” and “Internal” labels are removed,
and service cards no longer repeat the stack-wide risk; the overall reported
risk remains in the Deployment Brief. Analysis data and deployment behavior are
unchanged. The Forge component suite passes (12 tests), as do Mission Control
lint/build and both built Forge browser checks at phone and desktop widths.

## Workflow audit stage summaries — 2026-10-29

Each audit stage now starts as one compact row with its status, and opening a
row reveals its recorded evidence. This removes the separate duplicate status
grid and closing explanation; the overview remains at the top and the audit
remains read-only. Audit fields, validation, and workflow controls are
unchanged. The WorkflowAuditPage suite passes (26 tests), as do Mission Control
lint/build and all 11 built repository journey browser checks at phone and
desktop widths.

## Workflow dashboard counts and empty states — 2026-10-29

Summary counts now follow the applied filters, so they describe the same
workflows as the list. When no workflows match, or none are loaded, the
dashboard shows the relevant empty-state message without six redundant
zero-count cards. The focused dashboard suite covers matching and empty
filters (17 tests), as do all 15 built workflow-dashboard browser checks at
320px, 390px and 1280px. Mission Control lint and production build pass.

## Provider refresh time clarity — 2026-10-29

The provider workspace and resource inventory label their refresh times as
local and include the date, so the clock value is not mistaken for a provider
event time. Each `<time>` value retains the exact UTC instant. The focused
provider page and resource suites pass (65 tests), as do all three responsive
provider detail browser checks at 320px, 390px and 1280px, Mission Control lint,
and production build.

## Maintenance evidence time clarity — 2026-10-29

Maintenance approval, dispatch, verification, and recorded status-change times
now identify their displayed values as local time. Each value remains a
semantic `<time>` element with the exact UTC instant. The Maintenance lifecycle
panel test and the repository-free simulated maintenance journey at 320px,
390px and 1280px verify the local-time label and timestamp value. The focused
maintenance component suite, Mission Control lint, and production build pass.

## Maintenance history timestamp semantics — 2026-10-29

The request and result times in maintenance history remain labeled as local
time and now expose their source UTC instants through semantic `<time>`
elements. The history page suite verifies both timestamps (28 tests); lint and
production build pass.

## Action detail timestamp semantics — 2026-10-29

The action detail page now exposes both start and completion times as semantic
`<time>` elements carrying their exact UTC instants. Its existing note explains
that displayed times use the browser's local time. All six focused action detail
tests pass, along with Mission Control lint and production build.

## Provider connection update time — 2026-10-29

Saved connection settings now identify their update time as local and include
the date. The semantic `<time>` value retains its UTC instant; malformed values
show “Time unavailable.” The focused provider connection suite, Mission Control
lint, and production build pass.

## Proposal detail time clarity — 2026-10-29

Proposal detail creation and expiry times use the validated local display from
the proposal list. Their `<time>` elements retain the source instants for
assistive technology. Malformed values show as unavailable or unverified,
instead of displaying raw dates. Focused tests cover exact timestamps and
invalid dates.

## Change execution timestamps — 2026-10-29

Execution start and completion times in the workflow summary use readable
local time and preserve their source instants in semantic `<time>` elements.
Missing times keep the existing “Not exposed” message; malformed times show
“Time unavailable.” Focused tests cover both source timestamps and the display.

## Compatibility check timestamp — 2026-10-29

Compatibility check time uses the validated local display from other evidence
screens and exposes its source instant through `<time>`. Malformed values show
“Time unavailable.” The technical reference identifies its recorded source
value as UTC. Focused tests cover valid and malformed values.

## Workflow audit timestamps — 2026-10-29

Planning and verification times in workflow audit evidence use validated local
time and retain their source instants in semantic `<time>` elements. Invalid
timestamps show as unavailable. Audit stages remain collapsed; focused tests
cover valid and malformed timestamps.

## Maintenance plan creation time — 2026-10-29

Maintenance plan references show the validated creation time in local time
while preserving its source instant for assistive technology. Invalid values
show “Time unavailable.” Plan review remains read-only, with the separate
workflow approval unchanged.

## Maintenance request timestamps — 2026-10-29

Maintenance request expiry and generated times display as validated local time
with their source instants in semantic `<time>` elements. A malformed expiry
shows “Unverified expiry.” Existing exact-request approval presentations still
control approval actions; the display change does not alter action eligibility.
The optional support file’s generated time uses the same local-time display.

## Action history time validation — 2026-10-29

Action history keeps its local-time note and now rejects malformed timestamps
instead of normalizing impossible dates. Valid completion times retain their
source instants in semantic `<time>` elements. The focused history suite covers
valid and malformed values.

## Service reachability guidance — 2026-10-29

The Overview's service-check panel tells operators to test from the machine
running Atlas Core, inside its `atlas-core` Compose service when applicable. It
shows the sanitized address Atlas checked and distinguishes reachability from
Core from the service's own state. A connection-refused result points to the
service computer's listening port, Docker port publication when used, then a
repeat test from Core. Expanded guidance explains that a blank Docker `PORTS`
field means no host mapping when the container uses port mappings; Docker host
networking uses the service computer's port directly. It also explains
loopback-only mappings and that Compose commands belong in the folder
containing Atlas's Compose file, or can name that file with `--file`. The
details drawer also shows the plain-language failure reason beside the status,
while retaining the specific next step and raw message. These instructions do
not change probe behavior or service configuration. Component and responsive
browser tests cover the guidance.

## Work activity status wording — 2026-10-29

The Work activity card says what information it shows, notes that worker
readiness is not reported, and explains in plain language when Atlas cannot
show counts because it could not load every workflow. Refreshing information
is described as possibly out of date. Expanded outcome details explain that
results cannot be shown newest first because finish times are unavailable, and
that a workflow may be blocked before it starts. Workflow evidence, ordering,
availability rules and actions are unchanged. The focused Overview and Work
activity suites pass (102 tests), all 28 built Overview browser tests pass,
and Mission Control lint and production build pass.

## Workflow output summary — 2026-10-29

The workflow review now says plainly when only part of the worker's output is
shown. Stream names and byte counts remain available under a collapsed
“Output details” disclosure. The visible reminder keeps verification and
commit as separate approvals. Workflow evidence, approval rules and execution
behavior are unchanged. The WorkflowPage suite passes (88 tests), all 11 built
repository journey browser tests pass at 320px, 390px and 1280px, and Mission
Control lint and production build pass.

## Unconfirmed worker result — 2026-10-29

When Atlas cannot confirm whether a change finished, the workflow page now
explains that the change may already have completed and tells the operator to
check its result before starting it again. Request IDs and digests stay under
collapsed request details. The progress timeline now uses the reconciliation
result to show this state instead of incorrectly saying execution is
unavailable. Checking remains an explicit operator action; approval and
execution behavior are unchanged. The WorkflowPage and timeline suites pass
(101 tests), as do Mission Control lint and production build.

## Maintenance suggestion selection — 2026-10-29

The maintenance form now says directly that Atlas will not select a VM from a
suggestion and asks the operator to choose a running VM. Request and approval
behavior are unchanged. The focused MaintenanceRequestPage suite passes
(32 tests), along with Mission Control lint and production build.

## Discovery suggestion summary — 2026-10-29

Discovery proposal cards now lead with the catalog item, current status and
compatibility. Suggestion IDs, source, reference counts, timestamps and target
hints are available under a closed “More about this suggestion” disclosure.
The permission and review-only messages use plain language. Navigation and
maintenance authority remain unchanged. The focused DiscoveryProposalCard,
DiscoveryItemPage and MaintenanceRequestPage suites pass (78 tests); the built
sign-in journey passes at 320, 390 and 1280 pixels (5 tests), as do lint and
production build.

## Planning workflow pending state — 2026-10-29

While a workflow is being created, the planning button now carries the pending
label without repeating the same message beside it. The disabled state and
separate implementation approval remain unchanged. The focused planning page
suite passes (36 tests), along with Mission Control lint and production build.

## Discovery suggestion labels — 2026-10-29

The catalog item screen now calls related proposals “Suggestions” and uses that
term in its loading, empty and recovery states. The no-authorization message
stays visible. The focused DiscoveryItemPage suite passes (37 tests), along
with the responsive suggestions recovery browser checks (2 tests), Mission
Control lint and production build.

## Discovery relationship direction — 2026-10-29

Incoming relationship rows now identify and link to the item that points to
the open catalog item, instead of linking back to the open item. The row shows
the source, relationship type and current item; only outgoing relationships
show target resolution. Section headings and empty states describe link
direction in plain language, and hyphenated identifiers render as separate
words. The DiscoveryItemPage suite passes (37 tests), along with Mission
Control lint and production build.

## Provider action refresh recovery — 2026-10-29

When a provider action returns a confirmed success but the follow-up provider
refresh fails, Mission Control keeps the success result and reports the stale
provider view separately. Further direct actions pause until the operator
refreshes provider information; a failed action request still uses the
existing uncertain-result recovery path. The ProviderActions suite passes (12
tests), along with Mission Control lint and production build.

## Service details keyboard flow — 2026-10-29

Opening service details now moves keyboard focus to Close, keeps Tab and
Shift+Tab inside the dialog, and locks background scrolling. Escape and the
backdrop close the panel and return focus to the service card. Reachability
checks and provider actions are unchanged. The service-health section suite
passes (6 tests), along with Mission Control lint and production build.

## Workflow summary counts — 2026-10-29

The workflow directory now combines the preparation, approval, and review
queues into one “Needs your input” count. Each workflow card still shows its
own next step, so the summary is shorter without hiding whether the operator
needs to prepare a change, approve it, or review a result. Running, blocked,
completed, and unavailable counts remain separate. The focused dashboard
suite passes (17 tests), along with Mission Control lint and production build.

## Provider action confirmation context — 2026-10-29

Confirmation prompts now name the provider and action, include its description,
and show the entered parameter values before an action runs. Declining still
prevents the request, and no provider action or approval contract changed. The
ProviderActions suite passes (12 tests), along with Mission Control lint and
production build.

## Service reachability scope — 2026-10-29

The service reachability section now explains that an “Unavailable” result
means Atlas Core could not reach the configured address; it does not prove the
service is stopped. The checked address remains available in the service
details drawer; health probes and status mapping are unchanged. The focused
service-health suite, Mission Control lint and production build pass.

## Deployment analysis errors — 2026-10-29

Deployment analysis failures now show a plain recovery message. The original
error stays under collapsed technical details, so parser and network errors
remain available without taking over the screen. A later retry clears the old
error and result state. Analysis remains read-only and does not grant workflow
approval. The focused Forge suite, Mission Control lint and production build
pass.

## AI provider identity fallback — 2026-10-29

When the provider report contains neither a readable name nor ID, the overview
now says “Not reported” instead of “Unknown.” This describes the returned
evidence without implying that Atlas resolved the provider's identity. Health
and model readiness remain separate. When details are stale, the card also says
that Atlas could not confirm the current version, response time, or model list.
The focused AI provider and Overview suites cover incomplete identities and
stale reports; no provider configuration or action behavior changes.

## History timestamp availability — 2026-10-29

Action and maintenance history screens now show “Time unavailable” when a
timestamp is malformed. Maintenance history keeps “Not reported” for a missing
timestamp. Action detail and maintenance lifecycle evidence use the shared
strict validator, so impossible calendar dates cannot appear as real dates.
Focused tests cover malformed timestamps across the affected screens; action
history and maintenance execution behavior are unchanged.

## Provider resource name fallback — 2026-10-29

When neither inventory nor monitoring settings include a resource name, the
resource card says “Name not reported” while keeping the known type and ID
visible. This avoids implying that Atlas cannot identify the resource at all.
The focused ProviderResources suite covers the missing-name state; provider
identity checks and monitoring controls are unchanged.

## Policy diagnostic field fallback — 2026-10-29

Expanded policy diagnostics now say “Path unavailable” and “Issue type
unavailable” when those fields cannot be read, instead of “Unknown path” and
“Unknown diagnostic type.” The diagnostics remain collapsed by default, and
policy evaluation is unchanged. The focused PolicyVisibilitySection suite
covers incomplete diagnostic records.

## Finding entity fallback — 2026-10-29

Unavailable-entity rows now identify themselves as “Entity not identified”
when both name and ID are missing, and use “Status unknown” when no readable
state is reported. Reported IDs remain visible when names are missing, and
readable state codes use title case. Malformed array entries are ignored. The
focused FindingCard suite covers these cases; finding and provider behavior is
unchanged.

## Dashboard recovery assertion — 2026-10-29

The dashboard browser test now checks the current Operator Attention summary
for incomplete source evidence. The previous assertion expected wording the
dashboard no longer renders. The source-specific recovery details and
read-only behavior remain covered by the same journey.

## Dashboard action timestamp evidence — 2026-10-29

Recent provider actions now use the shared strict timestamp validator, so
impossible calendar dates cannot appear as real completion times. The summary
distinguishes a time the service did not report from a reported time Atlas
could not parse. Action ordering and the linked history remain unchanged.

## Dashboard stale workflow wording — 2026-10-29

Stale workflow attention now says what the last report showed and that Atlas
could not confirm the current status. It removes the technical-sounding
“Last-known” link prefix and the duplicate stale-condition sentence. Other
stale health conditions retain their “Last known report (out of date)” status.
Work activity explains when its latest report could not be loaded and shows one
plain refresh message while a newer report is being checked. Workflow decisions
and action controls remain unchanged.

## Service reachability guidance — 2026-10-29

The service drawer now leads with where to test: on the Atlas Core computer, or
inside `atlas-core` when Core runs in Compose. Compose file-location help is
collapsed unless the operator needs it. The connection-refused guidance keeps
the Docker port check and host-networking exception in a shorter instruction.
Service probes and settings are unchanged.

## Repository execution status — 2026-10-29

The change-progress summary is now the single status message for execution.
Running, failed and unconfirmed results no longer get a contradictory second
status line in the detail panel. A file-change count stays visible; paths,
timestamps, tool, repository and request ID are under collapsed technical
details. When approval is present but Atlas Agent reports no execution result,
Mission Control says the run status was not reported and offers a refresh.
Unrecognized execution states also remain unconfirmed. Approval, execution and
retry behavior are unchanged.

## Installation plan destination check — 2026-10-29

The installation plan review uses simpler VM selection and check labels. It
states that selection is temporary and the check does not install or approve
anything. VM identity stays visible while selection IDs and audit timestamps
are collapsed under details. Assessment blockers use plain-language titles;
diagnostic codes remain under technical details. No assessment, approval, or
installation request contract changed.

## Installation review record check — 2026-10-29

The candidate admission check now reads as a review record check, with a plain
result, clear save action, and concise retry states. Saved records are listed
as up-to-date or outdated inputs; record IDs and fingerprints stay under
technical details. Saving or deleting a review record does not approve or run
an installation. API requests, persistence rules, and approval boundaries are
unchanged.

## Installation readiness review — 2026-10-29

The readiness page now calls its second section an operator confirmation record
and explains in plain language that saving it does not approve or start work.
The two-step confirmation, exact statement, operator checks, and saved record
behavior are unchanged. Loading, missing-record, and error messages use the
same review-record language as the preceding screen.

## Installation run review — 2026-10-29

The next installation review step now explains that its saved record does not
choose a machine or start work. Blockers and confirmation actions use plain
language, and record times use a readable UTC format. A failed record read now
offers a safe retry; a failed save does not offer another save attempt. Request
contracts and operator checks are unchanged.

## Machine and worker setup records — 2026-10-29

The installation review now describes machine, worker, and queue records as
review-only. Statuses, blockers, and timestamps use operator language; machine
references, sandbox limits, fingerprints, and authority flags are collapsed
under technical details. Failed list reads offer a safe retry. No machine,
worker, or queue is discovered, contacted, or started, and record contracts
are unchanged.

Worker intake review uses the same plain-language status and blocker style.
Worker references, blocker codes, fingerprints, sandbox limits, and authority
flags stay under collapsed technical details. A failed list read offers a safe
retry. The review does not contact a worker, enqueue work, or start execution.

The nested queue handoff review now uses a short read-only summary, plain
blockers, readable UTC times, and collapsed technical records. Failed reads
offer a safe retry. Home Assistant remains visibly blocked once at the parent
review instead of repeating the same notice on its nested queue item.

The saved queue item and receipt screens now show a plain current/expired
status, readable UTC times, and understandable blockers. IDs, blocker codes,
receipt fingerprints, and authority flags are collapsed under technical
details. A failed read offers a safe retry; an uncertain receipt save does not
resend the request. The exact two-step receipt confirmation and Core permission
checks are unchanged.

The nested queue removal review now says what its saved record does and does
not do, with plain blockers, readable times, and collapsed technical evidence.
Failed reads offer a safe retry; uncertain saves do not resend. The existing
two-step statement, authenticated permission checks, and evidence-only request
remain unchanged.

The one-time queue removal panel now shows a short result and readable UTC
timestamps. Technical lineage and authority fields remain collapsed. A failed
receipt-list read can be retried safely; an uncertain save is not resent. The
two-step confirmation, exact statement, permissions, and Core request contract
remain unchanged.

The nested worker binding now uses a short saved/expired status, readable UTC
times, and one sentence that says the worker is not enabled or contacted.
Technical lineage stays collapsed, and a failed read can be retried safely.
The panel remains read-only and creates no binding or activation action.

The nested activation review now says plainly that activation is unavailable
and no worker or queue action was taken. It shows a short recorded/expired
status, keeps technical evidence collapsed, and retries only its read request.

The nested activation evidence record now uses a short saved/expired status and
readable UTC times. Its summary says activation remains unavailable, keeps
technical lineage collapsed, and offers only a safe retry of the read request.

The nested queue and worker review now shows a short saved/expired status and
readable UTC times. Version prerequisites and blocker details stay collapsed;
a failed read retries only the Core list request. The review still grants no
queue or worker action.

The nested queue and worker status panel now uses plain language and keeps
version-specific admission details collapsed. A failed read retries only the
saved review request; the panel still has no claim, lease, acknowledgement, or
worker-start action.

The nested queue receipt now calls the saved item a review record, not a
completed queue claim, lease, or acknowledgement. It shows whether the review
is current or expired, keeps fingerprints collapsed, and safely retries its
Core read after a load failure.

The worker runtime prerequisite panel now uses a clear saved/missing/unavailable
state, explains that worker start is not available, and retries only failed
Core reads. Technical fingerprints remain collapsed and no runtime action is
introduced.

The nested runtime admission panel now separates a saved review from actual
runtime readiness. It says worker start remains unavailable, keeps lineage
collapsed, and retries only failed Core reads.

The nested runtime plan panel now shows a concise saved, missing, or unavailable
state. It clarifies that the plan is reference-only and does not set up or start
a runtime; technical evidence remains collapsed. A failed Core read can be
retried safely, while runtime start and execution remain unavailable.

The nested consistency review now has a short saved, missing, or unavailable
status and readable UTC times. It explains that the review does not define or
start a runtime, keeps technical findings collapsed, and retries only a failed
Core read.

The runtime interface inventory now shows a short saved, missing, or unavailable
status and readable UTC times. It states that the inventory does not make a
runtime ready, contact a worker, or allow start; technical lineage remains
collapsed and failed Core reads can be retried safely.

## Work activity unavailable outcomes — 2026-10-29

When workflow status cannot be loaded, opening “More workflow details” now
states that workflow outcomes are unavailable instead of showing the vague
placeholder “Unknown.” The focused Work activity suite covers the unavailable
state. Workflow reads, controls, and approval behavior are unchanged.

## Service check location guidance — 2026-10-29

Service-check help now says directly that tests must run from Atlas Core's
computer or container. It also explains that a missing Compose file points to
the command's location, not the service's health, and tells the operator to
use the Atlas folder or the file's full path. The dashboard regression test
covers both explanations; service checks remain read-only.

The short Docker hint also states the host-networking exception next to the
blank-port explanation, so a blank `PORTS` column isn't treated as proof that
the service is stopped. The focused overview test checks both cases.

## Dashboard browser checks follow the current layout — 2026-10-29

The app-shell, overview, and unavailable-data browser specs now assert the
current “Needs attention” region, source-recovery text, and service-check
guidance. They had retained selectors and copy from the removed
“Operator Attention” presentation. All 44 browser checks across those specs
pass against synthetic API fixtures at desktop and narrow viewport sizes.

The full browser suite also had old discovery and readiness assertions for
release timestamps, image checks, installation plans, and saved confirmation
records. The specs now use the current labels and verify the existing read-only
and collapsed-detail behavior. No runtime or approval behavior changed; all
228 development browser checks pass against synthetic API fixtures.

## Work activity idle summary — 2026-10-29

When no workflows are running or blocked, the dashboard now shows one plain
empty-state sentence instead of two zero counters plus a repeated no-running
message. Running and blocked counts remain visible whenever either state has
items. The focused component and overview browser checks cover both states.

## Service check location — 2026-10-29

The visible next step says to run the connection test from the computer or
container running Atlas Core and explains that the service computer uses a
different network path. The Docker hint stays short, while port mapping and
Compose steps remain in the collapsed connection checks.

## Workflow count summary — 2026-10-29

The workflow directory now shows summary tiles only for categories that have
workflows. A filter that leaves one completed workflow, for example, shows its
count without four zero tiles above the list. The zero categories remain
implicit; every workflow still appears in the list with its stage.

## AI provider unavailable wording — 2026-10-29

The AI provider card now names the missing data as provider status and says
directly when Atlas could not load it, so the message is distinct from the
separate provider registry card.

## Change proposal empty results — 2026-10-29

An empty proposal search now shows its plain-language empty state without a
second “0 proposals” count. Nonzero result totals remain visible above the
proposal list.

## Catalog empty results — 2026-10-29

Empty catalog and search results now use their clear empty-state message without
repeating it as a zero count. Positive result totals remain visible.

The catalog also shows a single loading message while results are being fetched,
instead of repeating the status above and inside the results panel.

## Workflow review summary wording — 2026-10-29

Workflow review counts now read as a short sentence, such as “No findings or
recommendations” or “2 findings and 1 recommendation,” instead of repeating the
count in the field label. Unrecognized evidence summaries remain visible as
reported.

## Empty compatibility findings — 2026-10-29

Compatibility summaries now show a findings count only when there are findings.
The “What Atlas found” panel remains the single clear empty state when none are
reported.

## Maintenance audit retry — 2026-10-29

An unavailable maintenance status now has one retry button in its status panel.
The duplicate page-level refresh button is removed; retrying still performs a
read-only status check.

## Maintenance history status summary — 2026-10-29

Maintenance history cards now show the requested action in the subtitle and
the current status once in the recovery summary. An unavailable status remains
explicit in the subtitle when no matching status summary can be shown.

## Service attention destination — 2026-10-29

When a service warning has no valid provider detail page, selecting it in
“Needs attention” now jumps to the “Service checks” card instead of opening the
generic Operations page. Services with a valid provider page keep that direct
link. The 73-test Overview component suite and two responsive browser checks
pass at 320px and 1280px; lint and build pass. This is navigation only.

## Provider attention destinations — 2026-10-29

Provider warnings without a safe provider detail ID now open the Providers
summary card, and AI provider warnings without a safe detail ID open the AI
provider card. Valid provider detail links remain direct. The Overview
component suite covers both fallback destinations.

## System finding attention destinations — 2026-10-29

Unmatched system findings now point to System health. Findings that replace a
duplicate provider or service warning retain that condition's safe detail or
summary destination, so their higher priority does not send operators to
generic action history.

## Provider registry first-load label — 2026-10-29

The disabled registry control now says “Loading…” on the first request and
“Refreshing…” only when a previously loaded list is being updated. Its focused
page suite covers both initial completion and refresh recovery.

## Overview initial loading label — 2026-10-29

The Overview refresh control now says “Loading…” until its first dashboard
read completes, then says “Refreshing…” on later reads. Hook and rendered
button tests cover first load, refresh, and idle states.

## Action history initial loading label — 2026-10-29

Action history now distinguishes its first read (“Loading history…”) from
later updates (“Refreshing history…”). Its page tests cover both states, with
the existing loading and retry messages preserved.

## Provider resources first-load label — 2026-10-29

The provider resource panel now says “Loading resources…” on its initial
inventory and monitoring reads. “Refreshing resources…” is reserved for a
later update. The focused suite verifies the initial state and recovery to the
ready control.

## Provider detail refresh labels — 2026-10-29

The provider detail control now says “Loading…” during its first Core read and
“Refreshing…” during later reads. It is disabled until the active read finishes.
The page suite covers loading, refreshing, and idle states.

## Maintenance VM list loading — 2026-10-29

The maintenance target control now says “Loading VMs…” while it reads the
available list, including after a refresh. The empty-list recovery test verifies
the disabled loading label and the ready “Refresh” state afterward.

## Workflow directory refresh state — 2026-10-29

The workflow list refresh control now says “Refreshing…” while the latest read is
pending, matching the status message and disabled state. Its page test verifies
the pending and ready labels and guards against overlapping requests.

## Dashboard provider status source — 2026-10-29

The mounted provider preview now names Atlas Core as the source of each status
and says when it is showing a prior report. Its existing compact cards already
show each provider name and normalized health state, while extra providers stay
behind an expandable list. Component and overview-browser tests cover the live
preview, status labels, stale-report wording, and mobile overflow. No API or
authority behavior changes.

## Compact provider summary — 2026-10-30

The Providers card now opens with Atlas Core's provider count and how many need
attention; unknown statuses are counted separately. The full status list starts
collapsed, since the dashboard already surfaces degraded, unavailable, and
blocked providers in “Needs attention.” Operators can expand “Show provider
status” to inspect every provider. When Core returns a cached report, the
summary says its status may have changed and avoids counting old statuses as
current. Component and mobile browser checks cover the summary, disclosure,
stale reports, and provider ordering. No API or authority behavior changes.

## Service reachability check command — 2026-10-29

When Atlas Core cannot reach a service, the dashboard now shows the exact
read-only HTTP check to run from the Atlas Core host and its
`compose.production.yaml` directory. The command runs inside the `atlas-core`
container so it checks the same network path as Core. It omits URL credentials
and query values, prints only the HTTP status, and explains that an HTTP
response differs from a timeout or connection failure. The 320px and
1280px dashboard browser checks verify the command and keep the service
computer/browser distinction visible; helper tests cover URL redaction, shell
quoting, and invalid addresses. The command performs no service mutation.

Expanded connection details now focus on Docker port mappings and Compose file
location. The Atlas Core versus service-computer/browser distinction appears
once in the visible next step instead of being repeated inside the disclosure.
The component and two browser checks verify the clearer checklist.

The Docker checklist now tells operators to run `docker ps` on the computer
running the service, then check the container's `PORTS` column. Port
interpretation, publishing, host networking, and Compose-file checks each have
their own numbered step.

## Work activity detail cleanup — 2026-10-29

Removed the “Queue size — Not reported” placeholder from optional workflow
details because Atlas does not provide queue depth. The summary still explains
that the screen reports workflow progress and results, not worker readiness;
recorded outcomes and their limitations remain available in the disclosure.
The focused component test checks that the non-actionable placeholder is absent.

## Installation plan read recovery — 2026-10-29

When a read-only installation-plan request fails, Discovery now offers
“Retry installation plan.” The failed read remains isolated to its panel, and
retry returns it to a loading state before showing the result. The page test
covers failure followed by successful recovery; the retry repeats only the GET
request and adds no installation authority.

The panel also distinguishes Core's not-found response from a temporary read
failure. A missing plan item now explains that its catalog details remain
available and does not suggest retrying a request that returned 404.

## Workflow next-step filter — 2026-10-29

The workflow filter now treats unrecognized workflow states as “Status
unavailable” instead of placing them under “No action needed.” Running and
completed workflows are listed under “No action needed right now”; approval
and blocked workflows remain under “Needs an operator step.” The focused page
test checks each group so a future backend state is not presented as resolved.
Workflow cards identify unknown states as unavailable and keep the raw reported
value under their collapsed details; browser cases cover phone and desktop widths.

## Planning session saved-plan recovery — 2026-10-29

When a planning session loads but its saved plan cannot be read, Mission
Control now keeps the known session and proposal link visible. A temporary read
failure offers a read-only check; a not-found response explains that the plan
is missing and does not offer a retry. The plan must load and match its session
before Mission Control shows workflow creation. The focused page suite covers
temporary failure and recovery, missing-plan behavior, and the existing
approval boundary.

## Service-check missing Compose file recovery — 2026-10-29

The Overview service check now explains beside the command that a missing-file
error means Compose did not run the health check, and shows how to use the
Compose directory or full file path. The same explanation remains available
in the service details drawer. The duplicate hint was removed from the
collapsed Docker checklist. Read-only service status and probe behavior are
unchanged.

## Change proposal pagination context — 2026-10-29

The proposal list now shows the visible result range and total count, so an
operator can tell which proposals are on the current page. The changing count
is announced as a status update, and singular wording is covered. An empty
later page explains that the previous page may contain matching proposals. The
focused page suite covers first-page, next-page, and empty-result summaries.

## Maintenance history state labels — 2026-10-29

Maintenance history now gives every recognized workflow stage an operator
label, including the state after a maintenance action runs and before its
result check. Unknown stages and verification results are shown as unavailable
instead of converting backend values into labels that look authoritative. The
focused page suite covers each known stage, unknown values, and verification
results; the full Mission Control test suite, lint, and build pass.

## Maintenance history unknown status recovery — 2026-10-29

An unrecognized maintenance diagnostic status now appears as “Status
unavailable” and is included by the existing “Unavailable” filter. This keeps
future backend statuses visible without presenting an unknown value as a
confirmed health state or suggesting that no action is needed. The page tells
operators to wait for the status to become clear before repeating the request.
The focused and full Mission Control suites pass; lint and build also pass.

## Maintenance recovery summary fallbacks — 2026-10-29

The recovery summary keeps showing a reason and next step when the backend
returns a newer value the screen does not recognize. Unknown next steps ask
for operator review without recommending another action. The focused recovery
and history suites, full Mission Control suite, lint, and build pass.

## Workflow state coverage — 2026-10-29

The Overview and workflow directory now recognize all workflow states already
returned by Agent or handled by workflow detail screens, including planned,
verification preparation, approved-to-run, and rejected states. These states
receive readable labels and appropriate directory counts; unknown future
states remain unavailable. Verification preparation keeps the workflow list's
read-only refresh active. This changes display and refresh behavior only; the
separate approval and run controls are unchanged. The full Mission Control
suite passes 2,973 tests across 187 files, along with lint and build.

## Work activity count scope — 2026-10-29

The Overview labels its execution count “Currently executing workflows,” so
operators can distinguish change execution from verification and commit stages.
The empty and unavailable messages use the same scope. Workflow outcomes and
execution behavior are unchanged.

## Workflow progress approval states — 2026-10-29

The progress panel now distinguishes a rejected change from one waiting for
approval and says when an approved change or maintenance request is ready for
the operator to run. The panel still performs no action; approval and run
controls remain separate. If approval is recorded while the Agent workflow
state stays at `awaiting_implementation_approval`, the progress message still
shows the approved run as the next operator step.

The approved-to-run state now shows the existing explicit run control when
approval is recorded. Maintenance additionally requires its exact request to
be reviewable. No action starts until the operator selects that control.

If a workflow reports `awaiting_execution` but the approval field is missing,
pending, or rejected, the detail summary and progress panel no longer describe
it as ready to run. They ask the operator to refresh when approval is
unconfirmed. Focused workflow-detail and progress tests pass (117 tests), along
with lint and build. Approval and execution remain separate operator actions.

## Proposal expiration filter and eligibility clarity — 2026-10-29

The proposal directory's Expired filter now uses Core's explicit `expired`
query parameter, which checks the candidate expiry timestamp. Expiration stays
separate from the two planning eligibility statuses, so the list API does not
accept `expired` as a response status. Proposal cards and details use the same
expiry-aware label; unknown or malformed eligibility evidence appears as
unavailable, and the detail page offers a read-only refresh when eligibility
cannot be confirmed. Planning remains disabled until eligibility is confirmed.
The Core candidate-route suite passes 19 tests and Ruff. The Mission Control
suite passes 2,994 tests across 188 files, with lint and build passing. The
candidate-list browser suite passes 14 cases, including the expiry query at
390px and 1280px. Browser data is synthetic; this is not production acceptance.

## Fileshare Docker port guidance — 2026-10-29

The Overview's visible Fileshare connection check explains that a blank Docker
`PORTS` column usually means no host port is published, and that a container
marked `Up` may still have an unresponsive web app. Its existing disclosure
provides one read-only `docker ps --format` command showing container status,
network, and published ports, then explains the host-networking exception
before describing port mappings. The focused Overview suite passes 75 tests;
its development and built-preview browser suites each pass 29 tests. Lint and
build pass. Browser data is synthetic; no live service was queried.

## Maintenance history status context — 2026-10-29

Maintenance history now calls each entry's diagnostic the latest recorded
maintenance status and states that it is not a live service check. The filter
and unavailable fallback use the same label. This keeps a past verification
result from reading like a current health probe. The Operational History unit
suite passes 43 tests and the screen-recovery browser suite passes 88 tests;
lint and build pass.

## Action history date zones — 2026-10-29

Action history date fields now identify UTC directly. Their help text explains
that filters include full UTC days while recorded action times display in the
browser's local time. The Operations page suite passes 16 tests and the
responsive date-filter browser suite passes at 320px, 390px, and 1280px; lint
and build pass.

## Service reachability next steps — 2026-10-29

When Atlas Core gets a connection refusal, Mission Control now advises checking
the service listener and Docker network/port configuration before changing
ports. The Docker status/network/ports command is shared with the expanded
Overview checks. The focused Overview suite passes 75 tests; its development
and built-preview browser suites each pass 29 tests. Lint and build pass.

## Maintenance request type wording — 2026-10-29

The maintenance capability summary now describes the QEMU resource type as
“Virtual machine,” matching the operator-facing target choice without exposing
the backend implementation term. The provider/resource contract and approval
flow are unchanged.

## Fileshare Docker port diagnosis — 2026-10-29

The visible connection check now explains that a blank Docker `PORTS` field on
the app container means no host port is published unless it uses host
networking. It connects that finding to the refused check and says the
published host port must match Atlas's configured address. The check remains
read-only; it does not change Docker or service configuration.

## Atlas-to-service connection check location — 2026-10-30

The connection-check instructions now distinguish the computer running Atlas
from the computer hosting the checked service. They say to run the Compose
command from Atlas's Compose folder and clarify that Compose runs the request
inside Atlas Core. This prevents a check from the service computer from being
mistaken for Atlas's network path. No health probe, network, or service
configuration changed. The focused Overview and ServiceHealthSection suites
pass (82 tests), the responsive connection-check journey passes at 320px and
1280px, and Mission Control lint and production build pass.

## Deployment port ownership wording — 2026-10-30

Deployment analysis now says host ports belong to the computer where Docker
runs, while service ports are inside the container. It also states that the
review cannot confirm access through firewalls, routers, or the internet. This
avoids implying that the uploaded file runs on the operator's computer or that
the port review proves remote reachability. The Compose file and analysis
behavior are unchanged.

## Installation review retry wording — 2026-10-29

When an installation review cannot load, its recovery panel now says Atlas
could not load the review and invites a retry instead of repeating the heading.
It continues to hide technical error details and keeps the retry limited to
reading the review; saved confirmation and installation boundaries are
unchanged.

## Provider data loading label — 2026-10-29

The provider detail timestamp area now says “Loading provider data” during its
initial read instead of “Connecting,” which could sound like Atlas was testing
the provider's network connection. No provider check or connection behavior
changed.

## Change proposal read error — 2026-10-29

The change proposal detail screen now says Atlas could not load the proposal
and that its current details are unknown, instead of using Mission Control's
internal product name in the recovery message. The existing retry still reads
the proposal only; it does not submit or approve a change.

## Discovery catalog read recovery — 2026-10-29

The catalog error now says Atlas could not load the results and identifies
that the selected filters remain in place. Its retry control is labeled
“Retry search,” describing the operator action. The retry still only reads
catalog results.

## Workflow list recovery — 2026-10-29

The workflow-list error now names Atlas and tells the operator that retry
fetches the latest list. The existing retry remains a read of the workflow
list; workflow actions and approvals are unchanged.

## Observed provider state wording — 2026-10-30

Provider resource cards now describe the observed state as provider-reported
instead of calling it live inventory. A failed refresh can leave the last
loaded inventory visible with a warning that its state may have changed, so
the card no longer suggests a continuously current reading. The focused
ProviderResources suite passes (60 tests), as do Mission Control lint and
production build. Provider access and monitoring behavior are unchanged.

## Provider action refresh confirmation — 2026-10-30

Mission Control's refresh now reports whether all reads succeeded and shares
an in-flight read with concurrent callers. After a direct provider action,
Mission Control keeps the action result visible and pauses further actions if
any source could not be refreshed. A retry re-enables actions only after a
complete refresh. The focused ProviderActions suite passes (13 tests), the
useMissionControl suite passes (6 tests), and Mission Control lint and
production build pass. Provider action and Core approval contracts are
unchanged.

## Provider catalog freshness context — 2026-10-30

When the provider catalog read fails, the provider detail panel now says that
its displayed provider details are the last loaded values. This makes cached
description and feature data visibly stale alongside the existing last-known
health status. The focused ProviderOverview suite passes; lint and production
build pass. Provider requests and action behavior are unchanged.

## Provider address display — 2026-10-30

Provider technical details now show only the origin of a valid HTTP(S) address.
Credentials, paths, query values, fragments, relative URLs, and other schemes
are omitted from the page. The focused ProviderOverview suite covers credential
and token canaries, IPv6 and ports, and unsupported URL forms. Lint and
production build pass. The stored provider URL and connection behavior are
unchanged.

## Dashboard action details wording — 2026-10-30

The recent-action card now uses the same “View action details” label as Action
History, so operators can tell that the link opens the recorded action rather
than inspecting or retrying it. The link remains a read-only navigation to the
existing action record. No provider action behavior changes.

## Provider refresh retry outcome — 2026-10-30

If an explicit refresh after a provider action fails, the alert now says that
the refresh failed and that the displayed provider information may be out of
date. Direct actions stay paused until a refresh confirms current information;
the original action is not repeated. Technical error details remain collapsed.
The focused ProviderActions suite passes 14 tests, and the changed files pass
ESLint and `git diff --check`.

## Service check diagnosis disclosure — 2026-10-30

The dashboard now keeps the service reachability result and plain-language
explanation visible while collapsing the Core-side command and Docker
troubleshooting steps under “How to check from Atlas Core.” This reduces the
default dashboard detail without implying that an unreachable service is
stopped. The focused overview suite passes (75 tests), four responsive browser
cases pass at 320px and 1280px, and Mission Control lint and production build
pass. Health checks and service configuration are unchanged.

## Service-health attention links — 2026-10-30

Service-health alerts now link to the dashboard's Service checks section. The
service inventory ID (for example, `ifileshare`) is not guaranteed to be a
registered provider ID, so sending the operator to a provider detail route
could open a missing page. Provider alerts continue to link to their provider
details. The focused overview suite passes (76 tests), two responsive
iFileshare browser cases pass at 320px and 1280px, and lint and production
build pass.

## Core API status wording — 2026-10-30

The shell status now says “Atlas Core API connected” and labels the sidebar
status “Atlas Core API.” This makes clear that the badge reports whether the
API responds; it does not summarize service health. The focused shell suite
passes (34 tests), and lint and production build pass. The shell browser
regression asserts the unavailable label; a responsive overview browser check
shows the desktop API label alongside degraded Core health. No health or API
behavior changes.

## Service troubleshooting disclosures — 2026-10-30

The dashboard keeps the Core-side connection test separate from the Docker
and network diagnosis. The explanation about blank Docker ports now appears
only in the Docker and network disclosure, which has a clearer label. The
existing read-only check commands and guidance remain available. No health
check or service configuration behavior changes.

## Maintenance status plain-language fallbacks — 2026-10-30

An unavailable maintenance result now uses “Status unavailable,” and unknown
status explanations name Atlas instead of the internal Mission Control
component. The optional evidence section is labeled “Technical details.”
Maintenance state, filters, recovery guidance, and approval behavior are
unchanged. The focused maintenance summary, history, and workflow suites pass
(163 tests), along with Mission Control lint and production build. The missing
record explanation also uses “maintenance result” instead of the backend term
“service run.”

## Maintenance request return navigation — 2026-10-30

Maintenance history now labels its detail link “Review maintenance request.”
The request page returns to the list it was opened from; a direct link falls
back to Maintenance history, rather than sending candidate-based maintenance
requests to Change proposals. Maintenance cards use the same review label, the
detail page calls its status section “Maintenance summary,” and its optional
metadata is grouped under “Technical details.” The workflow directory likewise
remains the return destination when it opened the detail page. The focused history,
workflow detail, and workflow directory suites pass (159 tests), the history
and workflow-card browser journeys pass at 320px, 390px, and 1280px, and lint/build pass.
The navigation state is presentational and does not change maintenance
approval or execution behavior.

## Action history return context — 2026-10-30

Action history now keeps its applied search, draft search, filters, date range
and page position in the URL. Opening an action record preserves that context;
both its Back link and browser Back return to the same filtered page. The
focused action-history component suites pass (24 tests), two simulated browser
journeys pass at 390px and 1280px, and Mission Control lint/build pass. The
history API queries are unchanged and the browser fixture rejects mutations.

## Change proposal return context — 2026-10-30

Change proposal search now keeps submitted filters, unfinished filter edits
and page position in the URL. Opening a proposal carries that context, and
both the detail-page link and browser Back restore it. Focused component and
responsive browser checks cover submitted filters and an unsubmitted target
edit at 390px and 1280px; the combined list/detail component suites pass 40
tests, and Mission Control lint/build pass. Proposal reads and planning
approval behavior are unchanged; browser fixtures reject unexpected mutations.

## Workflow directory return context — 2026-10-30

The workflow directory now keeps applied filters, unfinished filter edits,
and the current page in the URL. Opening a workflow carries that context to
the detail page, and the return link restores it while the detail is loading,
unavailable, or readable. The detail URL records the allowlisted return path,
so reopening it in a new tab or after a reload still leads back to Workflows;
the marker is removed on return. Unknown query parameters are retained. Discovery
item details and workflow audit links also retain their list or detail query
context. These changes affect navigation only; workflow reads, approvals, and
execution behavior are unchanged. The focused workflow directory and detail
suites pass (124 tests); the full Mission Control suite passes (3,035 tests),
and lint and production build pass.

## Workflow filter empty state — 2026-10-30

When more workflow records are available than have been loaded, an empty
filtered result now says it covers only loaded workflows and directs the
operator to load older results. Once all records are loaded, the existing
“No workflows match” message remains. This makes the client-side filter scope
clear without changing the workflow API. The WorkflowDashboardPage suite
passes (21 tests), along with Mission Control lint and production build.

## Maintenance history direct-link recovery — 2026-10-30

Maintenance request links now keep the allowlisted Maintenance history return
destination in the URL, together with the current filters and page. Opening a
request in a new tab, reloading it, or encountering a workflow read error still
offers a return to the correct list. The marker is removed when returning to
history. The focused OperationalHistoryPage and WorkflowPage suites pass (149
tests total), and Mission Control lint and production build pass. This changes
navigation only; maintenance reads, approvals, and execution behavior are
unchanged.

## Change proposal context through planning — 2026-10-30

The proposal list's filters and page now follow the operator through proposal
review, planning, workflow setup, and back from workflow review. Direct workflow
links carry an allowlisted return destination in the URL, so a reload or failed
workflow read keeps the operator on the right route with the same search.
Focused proposal, planning, workflow setup, and workflow detail suites pass
(196 tests total); lint and production build pass. This changes navigation
only; planning, approval, and execution boundaries are unchanged.

## Repository journey restores the proposal list — 2026-10-30

The responsive repository-action browser journey now follows its completed
workflow through audit and back to the original proposal list. It verifies the
eligibility and change filters and page position in the rendered list at 320px,
390px, and 1280px. All three browser checks pass; the simulated journey still
rejects unexpected writes. Approval, verification, and commit remain separate.

## Service computer troubleshooting label — 2026-10-30

The overview's collapsed Docker guidance now says “Check Docker on the service
computer,” making clear which machine should run the container check. The Core
reachability probe and status interpretation are unchanged. The focused
overview suite passes (76 tests), with lint and production build passing.

## Atlas-side service check instructions — 2026-10-30

The connection-check disclosure now leads with “Test from the Atlas computer”
and gives a shorter instruction to use Atlas's Compose folder. It explains that
the read-only request runs inside Atlas Core and follows the same network path
as the health report. This makes the command's required location clear when
the operator is checking a separate service computer. No health or provider
behavior changes.

## Maintenance history loading labels — 2026-10-30

The first-load message and screen-reader names for the filters and pagination
now use “Maintenance history,” matching the visible page title. The existing
loading recovery browser case checks the updated message. History queries and
pagination behavior are unchanged.

## Additional health check wording — 2026-10-30

The System health disclosure now says “Run additional health checks.” The
opened panel goes straight to what the checks cover and the button that runs
them, without repeating an internal feature name. The check still runs only
after an operator opens the disclosure and selects Run health checks; it
remains a read-only report request.

## Action history loading status — 2026-10-30

Action history now announces its initial load and refresh as status updates in
the results area, using the page's full name. This helps assistive technology
users distinguish the list read from the separate retention-details read.
History requests and results are unchanged.

## Dashboard work activity labels — 2026-10-30

The Work activity card now calls executing work “Running workflows” and
recorded execution outcomes “Execution results.” Its empty and unavailable
messages use the same wording. These labels describe the existing workflow
states and recorded results; they do not claim worker availability or alter
execution behavior.

## Provider settings assessment wording — 2026-10-30

The selected VM's capability panel now opens with plain status and requirement
comparisons. Provider facts, internal status codes, timestamps, identifiers,
and fingerprints remain available under collapsed Technical details. The
visible copy makes clear that provider settings do not confirm software inside
the VM is ready and do not approve an installation. This is a read-only
presentation change; API contracts and installation approval behavior are
unchanged. The focused component suite passes (7 tests), along with Mission
Control lint and production build.

## Atlas health overview wording — 2026-10-30

The health section is now titled “Atlas health,” and its issue list says
“Services needing attention.” Offline and unrecognized service states display
as “Unavailable” and “Status unknown.” Visibility follows the reported service
health state even when an HTTP check returned 200, so a response code does not
hide an offline or unknown state. Known connection errors use the existing
plain-language health guidance. No health API behavior changed. The focused
overview and health-presentation suites pass (32 tests), with Mission Control
lint and production build passing.

## Providers overview wording — 2026-10-30

The overview now groups provider counts as total, available, and needing
attention. Unknown, blocked, degraded, and unavailable states all count as
needing attention, while each provider row names its mapped health state.
Critical provider errors use the existing plain-language connection guidance.
No provider checks or health API behavior changed. The focused provider
overview suite passes (7 tests); the full Mission Control suite passes (3,039
tests), with lint and production build passing.

## Installation handoff review clarity — 2026-10-30

The handoff screen now puts saved and expired status, preparation time, and the
next safe action first. IDs, fingerprints, contract fields, and authority flags
are available under collapsed Technical details. Load and record review errors
offer a retry; an uncertain save offers a record reload and does not repeat the
save. The text makes clear that saving a record does not send it to Agent or
start work. No dispatch or execution authority changed.

## Delivery readiness check clarity — 2026-10-30

Delivery activation preflights now appear as readiness checks with a plain
status, check time, expiry, and next step. Linked record IDs, fingerprints,
contract fields, and authority flags are under collapsed Technical details.
Failed list and detail reads can be retried; an uncertain create prompts for a
record reload without repeating the request. The visible copy distinguishes a
readiness check from delivery approval or activation. No delivery or execution
authority changed.

## Delivery choice review clarity — 2026-10-30

Operator delivery enablement now appears as a saved choice, with its plain
status and expiry first. Linked record IDs, fingerprints, audit fields, and
authority flags are under collapsed Technical details. The exact required
operator confirmation remains visible at the confirmation step. Failed reads
can be retried; an uncertain save offers a record reload without repeating the
request. No delivery, installation, or execution behavior changed.

The three focused component suites pass 13 tests together. The full Mission
Control suite passes 3,039 tests across 188 files. Mission Control lint and
production build pass. Local browser verification passes 91 screen-recovery and
readiness cases, plus 2 built-readiness cases.

## Service computer troubleshooting — 2026-10-30

The Overview service-check help now starts with guidance that applies whether
an app runs directly on its computer or in Docker. Docker container, network,
and published-port checks are grouped under an explicit “If the app runs in
Docker” disclosure. This keeps the container-specific steps available for
iFileshare while avoiding the implication that every configured service uses
Docker. The copied Docker command includes stopped containers, and the guidance
explains that a missing app may be running directly on the host or in another
VM. The focused Overview suite passes 79 tests; the iFileshare troubleshooting
browser check passes at 320px and 1280px; Mission Control lint and production
build pass. Health requests and provider behavior are unchanged.

## Change proposal target labels — 2026-10-30

Change proposal cards, details, and the main target filter now say “Target”
instead of “Target ID.” The target value, API field, saved filters, and query
parameters are unchanged. The proposal list and detail component suites pass
40 tests; their responsive browser checks pass all 20 cases; Mission Control
lint and production build pass.

## Atlas-side connection check location — 2026-10-30

The service check now states the machine and folder before the command: run it
on the computer running Atlas, from the folder containing
`compose.production.yaml`. It says plainly that running the command on the
service computer checks a different connection. The read-only command and
network probe are unchanged. Operators can copy both the Atlas-side connection
check and the service-side Docker status command. A status message confirms
success or gives a manual-copy fallback. Clipboard and browser tests confirm
the connection check omits URL credentials and query values. The focused
Overview suite passes (79 tests), responsive browser checks pass at 320px and
1280px, and Mission Control lint and production build pass.

## Missing-page recovery copy — 2026-10-30

The missing-page screen no longer shows the technical “404” label. It now
explains that the address does not match a Mission Control screen and retains
navigation and the return link. Responsive recovery checks pass at 320px,
390px, and 1280px.

## Discovery list and catalog-count mismatch — 2026-10-30

When the catalog reports items but the first results page is empty, the screen
now states both facts and offers a clear way to retry the list. Filtered empty
searches and truly empty catalogs keep their existing messages. Focused
component coverage passes (17 tests), and responsive browser checks pass at
320px, 390px, and 1280px. Lint and production build pass. Catalog requests and
data are unchanged.

## Provider refresh error details — 2026-10-30

Provider detail refresh failures now lead with the plain next step: use the
page's Refresh control to check again. The list of unavailable information and
refresh summary are under collapsed Technical details. Provider status and
actions are unchanged. The focused provider-page suite passes (18 tests), as
do Mission Control lint, production build, and `git diff --check`.

## Compose analysis action label — 2026-10-30

The Forge action now says “Analyze Compose file,” matching the visible input and
the page's analysis-only purpose. It still makes the same read-only analysis
request and exposes no deployment control. The focused Forge suite and
responsive browser checks cover the updated label.

## Service reachability details — 2026-10-30

The service details drawer keeps the translated reachability status, checked
address, and next step visible. Service cards now show a visible “View details”
action and leave response time and HTTP status in the drawer's collapsed
Technical details, along with the raw service message. This keeps low-level
diagnostics out of the status summary without changing the health check or
provider behavior. The drawer's “Test from the Atlas computer” disclosure also
shows the same read-only Core connection command as Overview, with Copy and
URL credential/query redaction. Both screens explain that an HTTP status means
a server answered, while a timeout or connection error means Core received no
HTTP response. The drawer does not run the command automatically. The focused
service health suite passes all 7 tests, including the copied-command
redaction check. The full Mission Control unit suite passes all 3,044 tests;
lint and the production build also pass.

## Work activity availability wording — 2026-10-30

The Overview card now says plainly that it shows workflow progress and results,
but does not show whether a worker is free to take more work. The card's status
counts and workflow actions are unchanged. The focused Overview and Work
activity suites pass all 109 tests; lint and the production build pass. The
Overview browser suite also checks this wording across responsive journeys; all
29 cases in `e2e/overview.spec.ts` pass locally.

## Connection settings refresh recovery — 2026-10-30

If a settings refresh fails after a successful read, the screen identifies the
values as the last loaded report, warns that they may be out of date, and
disables editing, testing, and saving until a refresh succeeds. Initial read
failures still offer a refresh. The focused Provider Connection suite passes
all 18 tests, and Mission Control lint passes. The connection API and explicit
test/save confirmation boundaries are unchanged.

## Change proposal search recovery — 2026-10-30

If a search fails after earlier results loaded, the page continues to hide
those results so they cannot be mistaken for the current search. The error now
explains why the results area is empty. Initial failures keep the simpler
retry message. The focused proposal page suite passes 17 tests, the responsive
browser suite passes all 16 cases, and Mission Control lint and production
build pass. Search, filter, and proposal behavior are unchanged.

## Recent provider action details — 2026-10-30

The Overview keeps each action's outcome, name, provider, completion time, and
action-history link visible. The returned provider message is available under a
closed “More details” disclosure instead of appearing inline, where it can
include technical error text. On the action details screen, successful result
messages remain visible while failed messages stay under a closed “Failure
details” disclosure. The action history list now follows the same rule: it
keeps successful results visible and puts failed messages under a closed
“Failure details” disclosure. All three screens use the shared bounded text
filter for common credential and URL patterns; optional action-history error
details use the same filter. The audit record and action-history route are
unchanged. The focused Overview, action history, and action details suites
pass all 105 tests; Mission Control lint and production build pass.

## Proposal error detail redaction — 2026-10-30

Change proposal search, proposal reads, and planning failures keep their
plain-language recovery message visible while optional technical details use
the shared bounded text filter. Focused proposal list and detail suites pass
all 40 tests; their responsive browser suites pass all 20 cases. Mission
Control lint and production build pass.

## Workflow action error detail redaction — 2026-10-30

Approval and run failures keep their plain-language outcome visible, while
the collapsed technical detail uses the shared bounded text filter. Approval,
verification, commit, and separate run boundaries are unchanged. The focused
Workflow page suite passes all 105 tests; Mission Control lint and production
build pass.

## Atlas Doctor error detail redaction — 2026-10-30

The Overview health panel keeps its plain-language recovery guidance visible
while collapsed diagnostic details use the shared bounded text filter. Reported
health findings also filter backend-provided credential and URL text. The
focused Atlas Doctor panel suite passes all 4 tests; Mission Control lint and
production build pass.

## Installation capability error details — 2026-10-30

Provider-settings failures keep the retry guidance visible while collapsed
technical details use the shared bounded text filter. The check remains
non-authorizing. The focused assessment suite passes all 7 tests; Mission
Control lint and production build pass.

## Planning session error details — 2026-10-30

Planning-session reads, plan generation, saved-plan reads, and workflow
creation keep their recovery guidance visible while optional error details use
the shared bounded text filter. Workflow creation and implementation approval
remain separate. The focused Planning Session suite passes all 37 tests;
Mission Control lint and production build pass.

## Discovery catalog error details — 2026-10-30

Catalog load and catalog status failures keep their separate retry actions and
plain-language recovery messages, while collapsed technical details use the
shared bounded text filter. Results and status can still be retried
independently. The focused Discovery page suite passes all 17 tests; Mission
Control lint and production build pass.

## Provider action error details — 2026-10-30

Action-list, action-result, and provider-refresh failures keep their distinct
plain-language outcomes while optional technical details use the shared
bounded text filter. Duplicate-action prevention and refresh requirements are
unchanged. The focused Provider Actions suite passes all 14 tests; Mission
Control lint and production build pass.

## Workflow directory error details — 2026-10-30

Initial workflow-list and refresh failures keep their recovery guidance and
last-loaded state visible while optional technical details use the shared
bounded text filter. Refresh remains a read-only check. The focused Workflow
Dashboard suite passes all 21 tests; Mission Control lint and production
build pass.

## Workflow history error details — 2026-10-30

Audit read failures keep the plain retry message visible while optional error
details use the shared bounded text filter. The workflow history remains
read-only. The focused Workflow Audit suite passes all 29 tests; Mission
Control lint and production build pass.

## Operator-facing error detail filtering — 2026-10-30

Atlas Core and Agent error-message helpers now filter common credential and URL
patterns and cap displayed text. Workflow setup and detail, proposal planning,
action history, catalog item, maintenance status, and Compose analysis
disclosures also filter backend-provided failure text at the render boundary.
Provider action results and warnings filter the same sensitive patterns.
Failure explanations stay collapsed until opened, while sensitive canary values
remain withheld when opened. Focused unit tests cover both shared error helpers
and affected screens. This changes only Mission Control presentation; it does
not change API contracts, approval decisions, or execution behavior. Ten
focused suites pass 285 tests, with Mission Control lint and production build
passing.

## Service health diagnostic filtering — 2026-10-30

Health summaries now filter backend-provided status and reason text before it
reaches the screen. The service details drawer also filters the reported
message and optional technical metadata, while preserving the known network
failure translations and the separate redacted address check. Credential and
URL canaries stay hidden in both the summary and expanded details. Health
probing and provider behavior are unchanged. The focused health and service
health suites pass 70 tests, and the full Mission Control unit suite passes
3,052 tests across 188 files. Mission Control lint and production build pass.

## Compose analysis finding filtering — 2026-10-31

Compose analysis finding text and the expanded technical response now pass
through the shared bounded filter, so credential and URL canaries remain
withheld in both places. The proposed plan, approval checks, and analysis-only
boundary are unchanged. The focused Forge suite passes 13 tests; Mission
Control lint and production build pass.

## Advisory card text filtering — 2026-10-31

Atlas finding and recommendation titles and descriptions now pass through the
shared bounded text filter before display. Credential and URL canaries remain
hidden while ordinary advisory text stays visible. Finding severity, health
effect, and suggestion-only presentation are unchanged. The focused advisory
card, finding, and overview-attention suites pass 16 tests; Mission Control
lint and production build pass.

## Policy diagnostic text filtering — 2026-10-31

Policy validation paths, issue types, and messages now pass through the shared
bounded filter before display. The technical disclosure remains collapsed,
and ordinary policy findings remain readable. Policy settings, health state,
and refresh behavior are unchanged. The focused Policy Visibility suite passes
14 tests, including credential and URL canaries; Mission Control lint and
production build pass.

## Full Mission Control unit validation — 2026-10-31

After the service-health, Compose analysis, advisory-card, and policy diagnostic
updates, the full Mission Control unit suite passes 3,055 tests across 188
files. This is source-level unit validation; the live-service and production
acceptance gaps in the review remain open.

## Missing Compose file recovery — 2026-10-31

The service connection guidance now says that a “no such file” result means
Compose never ran the check and does not report whether the service is
reachable. It explains how to identify the Atlas computer with `docker ps
--all` by looking for a container name containing `atlas-core`, then directs
the operator to Atlas's Compose folder or the full file path when needed. The
focused Overview and service-details suites
pass 87 tests, and the full Mission Control unit suite passes 3,055 tests
across 188 files. The iFileshare browser journey passes at 320px and 1280px.
Mission Control lint and build pass. This is guidance-only; it does not alter
health probes, backend behavior, or production acceptance.

## Service check HTTP response clarity — 2026-10-31

When a service answers with an unexpected HTTP 4xx or 5xx response, the Overview
now says that the service answered and shows the response code. This
distinguishes a reachable service with an unhealthy response from a failed
connection. Health probing and status rules are unchanged. The focused Overview
suite passes 80 tests; the responsive browser check passes at 320px and 1280px;
Mission Control lint and production build pass.

## Service connection-check host clarity — 2026-10-31

The Overview and service detail help now name the service being checked and
explain that a separate check from that service's computer may use a different
connection. This avoids implying that Atlas and every service must run on
separate computers. The Overview also names Atlas Core as the source of an
unavailable result. The copied command and probe behavior are unchanged. The
focused Overview and service health suites pass 88 tests, two responsive
iFileshare browser cases pass at 320px and 1280px, and Mission Control lint and
production build pass.

## Change-planning shell labels — 2026-10-31

The shell header and browser title now distinguish the “Plan a change” screen
from “Workflow setup.” Both previously used the internal “Candidate planning”
label, which did not match the page headings or the operator's current step.
Only presentation labels changed; routes and workflow behavior are unchanged.
The MainLayout suite passes 36 tests, and four browser cases verify the labels
on the planning and workflow screens at 320px, 390px, and 1280px. Mission
Control lint and production build pass.

## Detail screen shell labels — 2026-10-31

The shell header and browser title now use specific labels for action,
provider, catalog-item, proposal, and workflow detail routes instead of
repeating their parent destination. Unknown nested URLs remain identified as
missing pages. These are page labels only; routes, sidebar ownership, and
backend behavior are unchanged. MainLayout coverage passes 43 tests. Sixteen
responsive browser cases verify the affected screens at 320px, 390px, and
1280px. Mission Control lint and production build pass.

## Catalog compatibility message redaction — 2026-10-31

Compatibility finding and evidence text now passes through the existing
sensitive-text filter in the catalog item screen. Credentials and URLs stay
withheld in both the visible finding and expanded evidence details, while
ordinary findings remain readable. Compatibility checks and their results are
unchanged. The full Mission Control unit suite passes 3,066 tests across 188
files, including the focused redaction canary; lint and production build pass.

## Atlas Core host identification — 2026-10-31

The Atlas-side connection instructions now provide a copyable, read-only Docker
status command in both the dashboard and service details. The guidance tells
operators to look for an `atlas-core` container in the Names column and `Up` in
Status, distinguishing the wrong Docker host from a stopped Core container
before they run the network check. The existing service-host command and
reachability probe are unchanged. The focused Overview and service-health
suites pass 89 tests; the responsive iFileshare browser journey passes at 320px
and 1280px. Mission Control lint and production build pass.

## Workflow directory background refresh — 2026-10-31

The workflow list now says when running workflows trigger five-second automatic
updates. Background checks no longer flash the manual “Refreshing workflows”
message or change the Refresh button label. Manual refresh still shows its
progress state. The note disappears when no workflow is running; workflow
refresh behavior and approval boundaries are unchanged. The focused workflow
directory suite passes 22 tests, and five responsive browser cases pass at
320px, 390px, and 1280px. Mission Control lint and production build pass.

The workflow detail page now explains five-second status checks during every
active workflow phase, including execution, verification, commit, and
post-change verification. Its progress summary names the active step so
verification and commit do not remain labeled as execution. Actions pause while
each check finishes; the existing live-status message remains visible during a
check, and controls still require a current status before approval or resume.
The full Mission Control unit suite passes 3,075 tests across 188 files. Two
responsive browser cases pass at 320px and 1280px, and Mission Control lint and
production build pass.

## Atlas Core connection-check guidance — 2026-10-31

The service-check instructions now first ask the operator to confirm that
`docker ps --all` lists an `atlas-core` container, then direct them to Atlas's
Compose folder before running the read-only reachability check. The missing
file help explains that Compose resolves the file path from the current folder.
This addresses confusing a service-host check or a missing Compose file with a
failed network probe. The focused Overview and service-health suites pass 88
tests, and both development and built-app iFileshare browser journeys pass at
320px and 1280px. Mission Control lint and production build pass. Health
probing and status rules are unchanged.

## Service Docker troubleshooting steps — 2026-10-31

The service-computer Docker guidance now separates container state, port
interpretation, and port publishing into shorter steps. It still explains
stopped or missing containers, host networking, unpublished ports,
localhost-only bindings, and how the published host port relates to the app's
container port. The same collapsed guidance is available from both the
Overview and service-detail drawer. Health probing and status rules are
unchanged. The focused Overview and service-health suites pass 89 tests;
four built-app browser cases pass at 320px, 390px, 1280px, and 1440px; Mission
Control lint and production build pass.

## Service computer listening-port check — 2026-10-31

The service-computer guidance now provides a copyable, read-only Linux
`ss -ltnp` command scoped to the configured service port. A short explanation
distinguishes a host listener from a running container and connects the result
to the existing Docker port checks. The same command appears in the Overview
and service-detail drawer. Invalid or missing addresses produce no command;
URL credentials and query values are never included. Health probes and status
rules are unchanged. Unit tests cover custom and default ports and unsafe
addresses. The Overview and system-health browser journeys pass at mobile and
desktop widths; Mission Control lint and build pass.

## Workflow empty list with saved filters — 2026-10-31

When no workflows are loaded, the empty message now reflects any filters
already saved in the URL. An unfiltered empty list still says “No workflows
yet”; a filtered empty list says no workflows match the current filters. This
changes only the explanation, not list loading or filter behavior. The focused
workflow page and responsive browser checks cover both states; Mission Control
lint and production build pass.

## Core build label clarity — 2026-10-31

The sidebar now labels the configured Core identifier as “Core build” and
wraps long identifiers instead of clipping them. The API availability badge
remains the source of connection status; the build label does not claim that a
GitHub release was published. Layout tests cover the full visible value and
the unavailable and unreported states. The focused MainLayout suite passes 44
tests, and 15 app-shell browser checks pass at 390px and 1280px in both the
development app and built assets; Mission Control lint and production build
pass.

## Shared Atlas Core connection instructions — 2026-10-31

The dashboard and service-detail drawer now use the same shorter Atlas-side
connection checklist. It identifies which computer to use, explains `Up`,
`Exited`, and a missing `atlas-core` row, and says the HTTP check must run from
Atlas's Compose folder. The text also distinguishes that connection from a
check run on the service computer. Missing-Compose-file help is collapsed and
consistent on both screens. The commands only inspect container status or send
a GET request; address credentials and query values remain hidden. The full
Mission Control unit suite passes 3,094 tests across 188 files. Focused browser
journeys pass at 320px and 1280px against both the development app and built
assets; lint and the production build pass. Provider browser checks now use the
active loading and “Last checked” labels rather than stale copy.

## Catalog review wording — 2026-10-31

Discovery item notes now use the plain label “Catalog notes.” The screen no
longer exposes the undefined internal `reviewed_for_d5` flag; the API response
and catalog data remain unchanged. The full Mission Control suite passes 3,094
tests across 188 files; two responsive browser checks confirm the notes remain
visible and the internal flag is omitted at 390px and 1280px. Lint and build
pass.

## Docker connection warning wording — 2026-10-31

The provider connection screen now explains the Docker socket warning in terms
operators can act on: Atlas can still issue commands that change containers
even when the socket mount is read-only. Connection settings, test behavior,
and permissions are unchanged. The full Mission Control suite passes 3,094
tests across 188 files, including the warning and read-only settings case; lint
and build pass.

## Catalog readiness summary order — 2026-10-31

The catalog item page now shows the compatibility result and item requirements
directly after the item summary, before installation-plan and release/image
supporting details. This brings the suitability check forward without changing
any check, API request, permission, or installation boundary. The focused item
suite passes 40 tests; responsive browser checks verify the ordering at 390px
and 1280px. Lint and build pass.

## Provider resource editor phone-width layout — 2026-10-31

The monitoring editor no longer forces a 256px minimum width inside a nested
resource card. A read-only browser fixture with a real resource card now checks
both the card's content width and the page width at 320px and 1280px; the old
layout overflowed its 236px card by 40px at 320px. The two responsive browser
checks pass, as do the focused Provider Resources and Intent Editor suites (77
tests), Mission Control lint, and production build. The fixture has no operator
session and makes no settings changes.

## Provider inventory labels — 2026-10-31

The section description and loading/recovery copy now refer to the resources
reported by the provider rather than internal inventory terminology. The
timestamp says when provider resources were last checked, and a successful
empty result says “This provider has not reported any resources.” A failed
read keeps its separate message, so an unavailable list is not presented as
empty. All 61 focused Provider Resources tests pass, including the
empty-versus-failed distinction; Mission Control lint and build pass.

## Service reachability explanation — 2026-10-31

The Overview now explains once that an unavailable service did not respond to
Atlas Core and may still be running on its own computer. Repeating the same
warning beneath every unavailable service has been removed; the individual
service checks and troubleshooting steps remain available. The focused
Overview suite passes 81 tests; Mission Control lint and production build
pass. This changes presentation only; health probes and status rules are
unchanged.

## AI provider model-list wording — 2026-10-31

The Overview now explains that model names do not show which model Atlas will
use or whether the provider can answer requests. The location of the provider
remains explicitly unreported. This keeps the visible health summary from
implying that a running-model entry is ready for operator work. Focused
Overview and AI-provider tests, Mission Control lint, and the production build
pass. No provider settings or requests change.

## Workflow return-link wording — 2026-10-31

Proposal-based workflow details now return to “Change proposals,” matching the
navigation and proposal screens instead of exposing the old internal route
name “execution candidates.” A missing audit now returns to “All workflows,”
matching the workflow directory instead of calling it a dashboard. Destination
selection and preserved filters are unchanged. The focused workflow and audit
page suites, Mission Control lint, and build pass. The workflow directory also
explains that refreshing after loading older records resumes automatic checks
only while a workflow in the refreshed list is running.

## Workflow list empty-page recovery — 2026-10-31

If Atlas reports existing workflows but returns no entries on the first page,
the directory now explains the mismatch and offers Refresh. It no longer says
there are no workflows or offers a “Load more” action that repeats the empty
page. The focused workflow directory suite covers recovery; lint and build
pass. Workflow reads and approval behavior are unchanged.
