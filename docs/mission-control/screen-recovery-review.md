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

## Monitoring suggestion wording — 2026-10-28

The suggestion card describes why Atlas proposed a value without exposing its
internal rule name. Stale suggestions explain that the VM or monitoring
setting changed and point operators to Refresh resources. Reviewing a
suggestion still only fills the form; the explicit Save action remains
separate.

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
