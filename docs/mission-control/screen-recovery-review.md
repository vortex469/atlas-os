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
| Generated frontend assets | Built pages preserve the supported operator journeys, navigation and responsive shell | `playwright.built.config.ts` reuses 42 compatible browser cases against the generated build; API requests remain bound to the configured origin and exact isolated fixtures |
| Development API routing | Core paths are preserved; the Agent prefix is removed; session/CSRF/origin headers are preserved and caller identity headers are stripped | `src/server/devProxy.test.ts` uses the actual Vite server with isolated HTTP stubs; no Atlas backend or mutation is involved |
| Dashboard | Attention and health remain distinct; optional detail does not crowd the main screen | `e2e/overview.spec.ts`, `e2e/dashboard-block.spec.ts`, `e2e/system-health.spec.ts`; overview and worker component tests |
| Workflow directory | Each card shows its current stage, latest result and approval need first; IDs and target references are optional details without a duplicate status field | `src/pages/WorkflowDashboardPage.test.tsx`, `e2e/workflow-dashboard.spec.ts` |
| Change proposal directory | Eligibility, change and target filters lead; category/source filters expand on demand and show when active; cards lead with the proposed change and keep references optional | `src/pages/ExecutionCandidatesPage.test.tsx`, `e2e/candidate-list-summary.spec.ts` |
| Change proposal details | The proposed change, target, rationale, constraints and planning boundary lead; technical IDs remain available under optional details | `src/pages/ExecutionCandidateDetailPage.test.tsx`, `e2e/candidate-detail-summary.spec.ts` |
| Providers | Registry and detail links work; unavailable data differs from absence; missing feature metadata leaves the provider view usable and does not imply there are no capabilities; resource identity, edit blockers, and monitoring suggestions use plain language; failed inventory is not shown as an empty provider; edit access is checked before controls are enabled; action-catalog read failures differ from uncertain action results; forms and late responses stay with their provider | `src/pages/ProviderPage.test.tsx`, `src/components/ProviderOverview.test.tsx`, `src/components/ProviderIntentEditor.test.tsx`, `src/components/ProviderResources.test.tsx`, `src/components/ProviderActions.test.tsx`, and route cases in `e2e/screen-recovery.spec.ts` and `e2e/overview.spec.ts` |
| Discovery and sign-in | Advisory context survives login without selecting or authorizing a maintenance target | Discovery/login/maintenance page tests; `e2e/operator-signin.spec.ts` |
| Proposals and planning | Only current search results and matching proposal/plan identities appear; preparation has four simple steps | Proposal/planning page tests; proposal recovery browser cases; both workflow journey specs |
| Repository workflow | Preparation and detail summaries show current state and approval status first; reference metadata is optional; exact requests remain reviewable; each exact approval and resume remains separate; rejection survives reload; audit follows completion | `e2e/repository-journey.spec.ts`; workflow detail, shell, timeline and audit component tests |
| Maintenance workflow | Explicit target selection and exact request submission return a proposal; operational plan and exact verification rules precede action approval; a separate run precedes lifecycle outcome and audit | `e2e/maintenance-journey.spec.ts`; planning and workflow component tests |
| Maintenance history and audit | Foreign workflow evidence is refused; unavailable results remain findable; maintenance audit avoids repository-only stages | History/audit component tests; history browser recovery and maintenance journey audit cases |
| Provider action history | Changing filters or refreshing hides previous results; failed reads do not retain an actionable retention policy; superseded responses cannot replace current results; UTC date filters are explained beside local display times | `src/pages/OperationsPage.test.tsx`, `e2e/action-history-dates.spec.ts` |
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

The health summary names its three separate inputs in plain language: Atlas
Core health, system findings, and policy settings check. The explanation says
these reports are not combined into one score and marks data over a minute old
as out of date. Focused overview tests and responsive system-health browser
checks, lint and build cover the display; health calculations are unchanged.

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
focused request-page suite passes (28 tests), the sign-in and full maintenance
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
