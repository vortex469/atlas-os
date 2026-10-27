# Mission Control screen recovery review

This review covers the Mission Control simplification and reliability changes,
including their combined local integration checks. It is a source and simulated-browser
review, not production acceptance or authorization to merge, deploy, enable a
runtime, tag, or publish a release.

## Operator outcomes and evidence

| Surface | Required behavior | Current regression evidence |
| --- | --- | --- |
| Shared navigation | Plain menu labels distinguish action history, maintenance history, request creation and proposals; only the owning destination is highlighted; links, mobile drawer, focus, skip link and missing-page recovery work | `e2e/navigation.spec.ts`, `e2e/app-shell.spec.ts`, `e2e/screen-recovery.spec.ts`; `src/layouts/MainLayout.test.tsx` includes maintenance/action-detail ownership |
| Screen loading | Secondary screens load on demand; pending navigation pauses the old page's controls while keeping navigation available; module failure offers reload and home recovery | `e2e/page-loading.spec.ts` covers delayed modules, leaving a pending screen, and direct-link failure/reload at phone and desktop widths |
| Generated frontend assets | Built pages preserve the supported operator journeys, navigation and responsive shell | `playwright.built.config.ts` reuses compatible operator journeys against the generated build; API requests remain bound to the configured origin and exact isolated fixtures |
| Development API routing | Core paths are preserved; the Agent prefix is removed; session/CSRF/origin headers are preserved and caller identity headers are stripped | `src/server/devProxy.test.ts` uses the actual Vite server with isolated HTTP stubs; no Atlas backend or mutation is involved |
| Dashboard | Attention and health remain distinct; optional detail does not crowd the main screen | `e2e/overview.spec.ts`, `e2e/dashboard-block.spec.ts`, `e2e/system-health.spec.ts`; overview and worker component tests |
| Providers | Registry and detail links work; unavailable data differs from absence; forms and late responses stay with their provider | Provider page/component tests; provider registry and route-switch browser cases in `e2e/screen-recovery.spec.ts` |
| Discovery and sign-in | Advisory context survives login without selecting or authorizing a maintenance target | Discovery/login/maintenance page tests; `e2e/operator-signin.spec.ts` |
| Proposals and planning | Only current search results and matching proposal/plan identities appear; proposal details support read-only retry/refresh; preparation has four simple steps | Proposal/planning page tests; `e2e/proposal-detail-recovery.spec.ts`, `e2e/existing-workflow-review.spec.ts`; proposal search recovery cases; both workflow journey specs |
| Repository workflow | Each exact approval and resume remains separate; rejection survives reload; audit follows completion | `e2e/repository-journey.spec.ts`; workflow detail, shell, timeline and audit component tests |
| Maintenance workflow | Explicit target selection and exact request submission return a proposal; operational plan and exact verification rules precede action approval; a separate run precedes lifecycle outcome and audit | `e2e/maintenance-journey.spec.ts`; planning and workflow component tests |
| Maintenance history and audit | Foreign workflow evidence is refused; unavailable results remain findable; maintenance audit avoids repository-only stages | History/audit component tests; history browser recovery and maintenance journey audit cases |
| Provider action history | Changing filters or refreshing hides previous results; failed reads do not retain an actionable retention policy; superseded responses cannot replace current results | `src/pages/OperationsPage.test.tsx` includes delayed-response and failure regressions |
| Atlas Doctor | Rerunning clears the previous report; pending and failed reads cannot retain an old healthy score | `src/components/AtlasDoctorPanel.test.tsx` includes healthy-to-pending-to-unavailable coverage |
| Provider connection tests | Editing inputs or reloading settings clears the old test result; tested secrets are redacted in result messages, diagnostic field names and values | `src/components/ProviderConnection.test.tsx` uses synthetic secret canaries, checks stale-result invalidation, and mocks every test/save request |
| Forge | Edited inputs invalidate results; late responses are ignored; both reported risks remain visible; unknown duration is not zero | `src/features/forge/Forge.test.tsx`, `e2e/forge-analysis.spec.ts` |
| Installation readiness | Owner evidence loads after read-only recovery, remains bound to the current record, and grants no installation authority | Readiness component/parser/structural tests; `e2e/readiness-review.spec.ts` and invalid-review browser recovery case |

Provider detail follow-up: health status and its message remain visible while
latency, HTTP status, priority, version, workspace, capabilities and endpoint are
collapsed under **Technical details**. Native disclosure controls support Enter
and Space. `e2e/provider-overview.spec.ts` checks healthy and offline views at
320, 390 and 1280 pixels, including keeping the monitoring heading in the initial
900-pixel viewport. Opening details sends no mutation requests. A failed page refresh marks the
retained provider health unknown and labels its status/message as last reported.
Successful reads restore the normalized current health state. Provider health uses
the shared health-state mapping; unrecognized codes do not imply success.
`e2e/provider-health-recovery.spec.ts` verifies failed-refresh recovery through
reads without provider mutations. Diagnostics and recommendations from the
same retained snapshot are labeled as last reported, including empty results;
failed refreshes never claim there are no current findings. Successful refreshes
clear these notices. `e2e/provider-advisories.spec.ts` covers both retained records
and empty snapshots. Optional collection-history read failures are
reported separately from provider health. A failed history read preserves prior
points with a last-reported label, or shows an unavailable state when no points
were loaded. A successful refresh restores the chart or a confirmed empty state.
`e2e/provider-history.spec.ts` checks recovery without provider mutations. Policy-read failures likewise label
retained settings, show an unavailable state before any settings are loaded, and
suspend chart threshold comparisons until settings refresh successfully. This
changes display behavior only; backend policy enforcement is unchanged.
`e2e/provider-policies.spec.ts` checks these independent read states. Reference-panel
layout uses complete final rows for odd setting counts, wraps long values within
the panel, and places history metrics two across on narrow screens.
`e2e/provider-panel-layout.spec.ts` checks one/three-setting layouts and long
container names at 320, 390 and 1280 pixels. Collection-history responses are
validated before publication to the page: malformed rows, dates, statuses or
numeric fields make the optional read unavailable while preserving valid prior
history. The reader projects known fields and honors Core telemetry defaults and
naive/aware datetime serialization. Finding counts must be exactly representable
browser integers, and duplicate snapshot IDs are rejected to avoid ambiguous
chart keys. Native DTO fixture checks cover the public response shape. Chart
averages use incremental arithmetic so large finite durations do not overflow.
`e2e/provider-history.spec.ts` includes malformed successful-response recovery.


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

Provider settings responses are validated before replacing the last readable
snapshot. The reader follows the complete serialized Core `Policies` model,
including all nine sections and native defaults captured by a golden fixture.
Unknown extensions are discarded; malformed sections, invalid enums, non-finite
metrics, invalid counts and invalid native collection/workflow lists use the
existing unavailable/last-reported settings path. Provider health and readable
collection history remain independently available, and threshold comparisons
remain paused until a valid settings response returns. The Proxmox `ignored`
guest setting is supported as legacy evidence, matching Core's public model.
No setting is written, and no monitoring authority is inferred from this data.

Provider advisory summaries are validated as complete public `AceSummary`
snapshots before any part of the shared refresh is published. Invalid findings,
recommendations, assessments or collection timing data preserve the prior
coherent snapshot and its last-successful-refresh time, using the existing
unavailable/last-reported presentation until Refresh succeeds. Native public
model fixtures cover defaults, all timing outcomes, open severity/priority
strings, unconstrained native score/confidence ranges and free-form details.
Only finite browser-safe numbers are accepted where the public model requires
integers; no additional native enum or range restrictions are invented.
Entity-detail renderers read only string labels from the open details dictionary,
ignore non-object rows and use existing unknown labels for unreadable fields.
Neither this advisory evidence nor its recovery authorizes any mutation.

Advisory cards keep the issue title, reported message/reason and severity/priority
visible. Secondary finding and recommendation metadata lives in closed native
disclosures with keyboard access. Headers, badges and entity rows wrap inside the
card, including long native string values; entity names and identifiers remain
readable instead of being truncated. Finding entity expansion still shows the
initial five rows and can reveal or collapse the complete list. Browser checks
cover closed/open metadata, Enter/Space interaction, text and viewport bounds,
and six-entity expansion at 320/390/1280 pixels. This presentation change leaves
advisory data, permissions, reads and execution boundaries intact.

The provider directory retains its last successful list through pending refreshes,
HTTP failures and malformed root responses. Search and existing detail links stay
available; retained health uses the shared unknown/stale badge and last-reported
reasons. An empty retained list is scoped to the last successful refresh instead
of claiming the current registry is empty. A successful retry replaces the list
and clears the stale presentation, including transitions to empty or unavailable
providers. Initial-load failures still show recovery without claiming an empty
registry. Browser checks cover listed/empty snapshots, delayed reads, both failure
kinds, local search, three reads per recovery and zero mutations at three widths.

Provider detail refreshes validate catalog metadata and capability arrays before
publishing the shared snapshot. Invalid entries and duplicate IDs preserve the
previous coherent snapshot and refresh time, using the existing unavailable/
last-reported recovery; initial failures do not claim a provider is missing.
Duplicate rejection follows Core's registry invariant. Public metadata and
capability strings remain open; unreadable health retains the existing unknown
fallback independently of otherwise valid identity. Known public fields are
projected, and the native model fixture covers serialized defaults and future
string values. Browser checks cover initial/retained failures, malformed names,
capabilities, duplicate identities and roots at 320/390/1280 pixels, recovery to
fresh offline evidence and no mutation requests.

Provider-page read failures say that the latest provider details are unavailable,
without declaring Atlas Core itself unavailable. The existing Refresh control is
named as the recovery step. Monitoring, diagnostic, recommendation and maintenance
explanations use plain language while keeping the same boundaries: monitoring
saves do not operate resources, advisory reports do not change settings or run
actions, and maintenance requires review of the proposal/plan and approval of the
exact action. Existing initial/retained error, recovery and authority assertions
exercise these messages; no backend decisions or controls change.

Provider action lists are read as unknown data and validated before publishing
controls. Complete serialized metadata, native action ID syntax, strict boolean
flags and unique selectable action IDs are required. Core's parameter dictionary
is open: the UI checks object definitions and the string/bool fields its form
consumes, preserving unrelated extensions. Unreadable definitions use the existing
action-list error and Reload control rather than presenting a guessed form.
Native serializer fixtures cover default actions, disabled/destructive/confirmed
flags and parameter extensions. Browser cases cover malformed roots, flags,
parameter descriptions, duplicate IDs and transport errors at three widths;
reloading restores the required-input and confirmation gates. Dismissing the
confirmation sends no action request. No execution behavior or backend authority
is added or relaxed.

Resource cards label retained inventory values as last reported while an inventory
refresh is pending or has failed. Missing observations and Core's native unknown
status fallback do not produce a match/mismatch claim. Configured expectations
and verified identity remain separate facts; the comparison resumes only with a
usable observation. The inventory timestamp is explicitly the last successful
refresh. Browser recovery cases cover initially unavailable and retained running
observations against running/stopped expectations at three widths, two exact
mocked discovery-refresh POSTs, and no monitoring writes or provider actions.
Editing permissions, fingerprints, save approvals and uncertain-save recovery
continue through their existing independent contracts.

Observed inventory responses are validated on both the ordinary read and manual
discovery-refresh paths before replacing the current snapshot. The read-only view
is bound to the requested provider, checks row identities and unique coordinates,
rejects NUL-delimited coordinate aliases, validates display fields, real datetime
strings, legacy expectation shapes and browser-safe nonnegative counts, and
projects known view fields while preserving open metadata. The native unavailable
expectation state and naive/aware datetime serialization are supported. Inventory
identity/authority extensions do not become editing permission; management APIs
remain the source for those decisions. Malformed successful responses now retain
the previous inventory and its timestamp through the existing error/retry path.
Native public-model fixtures and browser recovery cases cover these boundaries.

Public monitoring reloads now distinguish retained identity/expectation values
from a confirmed current descriptor. Pending or failed reads mark retained facts
as “Last reported”, suppress current match comparisons and pause editing and
suggestion review. A read failure does not claim a changed resource incarnation.
Only the latest public read may publish state; save callbacks also require the
current descriptor and resource. Successful unchanged reloads preserve drafts;
failed reads reset drafts and suppression acknowledgements. Browser checks cover
HTTP and malformed-success failures, pending reads and recovery at phone and
desktop widths with only the two exact mocked discovery-refresh requests.

Permission rechecks now pause monitoring edits even when the public descriptor
has already refreshed. The draft remains visible through a successful unchanged
recheck, with a short explanation for disabled controls. A save callback must
reference the latest successful private read and resource. Failed or revoked
permissions remove editing and reset suppression acknowledgement on recovery.
Browser coverage includes pending, ready, failed and revoked rechecks, plus
session expiry before a late private reply; these fixtures never submit a policy
write and allow only their exact synthetic discovery-refresh requests.

Resource inventory reads now publish only the latest request's result. A late
older success cannot replace newer observations, their refresh timestamp or a
newer failed read. A late older error cannot hide a successful snapshot or end
a newer loading state. The same ordering applies to initial reads and manual
inventory refreshes. Browser coverage overlaps reads through a provider catalog
refresh and verifies both reply orders at phone and desktop widths using GETs
only; monitoring permission and save contracts remain unchanged.

Public monitoring responses are now bound to the requested provider ID before
replacing the view, including otherwise-valid empty descriptors. An unrelated
provider response follows the existing unavailable/retry path: observed inventory
remains visible, retained monitoring facts are labelled as last reported and
editing stays paused. Recovery restores current settings and requires a new
suppression acknowledgement. Browser coverage checks initial and retained views
at phone and desktop widths and excludes unrelated resource names/rows. Display
name changes remain valid; backend permission and execution rules are unchanged.

Resource monitoring guidance uses plain language for reported states, monitoring
suggestions and recovery. It explains that Ignored hides findings about the
resource's expected state, describes a stale suggestion without “incarnation”
jargon, and keeps review separate from saving. Choice labels and retry guidance
name the action the operator can take. The layout, option values, acknowledgement
requirement, permissions and requests are unchanged. Existing interaction tests
retain their save and suppression checks with updated accessible text; phone and
desktop previews use synthetic data without submitting any writes.


Proposal details now offer Try again after failed, missing or mismatched reads
and Refresh proposal on a loaded view. Refresh clears prior proposal/planning
feedback, keeps directory navigation available, and announces loading while
planning controls are absent. Updated eligibility is checked before planning can
be requested again. Refresh is paused during a pending planning request; queued
events cannot start planning from an unconfirmed read or refresh over the pending
request. A stale planning result points to the actual refresh control. Recovery
never resubmits planning automatically and grants no execution approval. Browser
fixtures cover initial failures, changed eligibility and one exact synthetic
planning POST followed by read-only recovery at phone and desktop widths.


Existing workflows can be reviewed directly from proposal results and saved
planning sessions. Agent's planning response now includes the persisted
`workflow_session_id` as an optional read-only reference, including orphaned
planning-session recovery. This field grants no approval or execution authority.
The normal planning GET also preserves the saved maintenance plan and predecessor
and successor references that were previously omitted by its response projection.
No planning state is created or changed by these reads.

Mission Control treats a reported existing workflow as a completed planning
outcome, keeps saved plans available for review and suppresses duplicate
plan/workflow creation controls. Its link opens the existing `/workflows/:id`
read view directly, avoiding the workflow-shell creation route. Older responses
that report an existing workflow without a usable reference offer the workflow
directory instead. A
saved plan without a workflow offers plan review rather than a false failure.
Tests cover persisted/orphan/legacy responses, unusable references, maintenance
plan retention, reload and exact request allowlists at phone and desktop widths.
These are source and simulated-browser checks, not production acceptance.


Opening or reloading workflow preparation now uses
`GET /candidate-planning/{session_id}/workflow`. The additive Agent read endpoint
projects the saved workflow and current state using its persisted planning linkage,
including orphaned-session recovery. It returns 404 for no workflow and 409 for
ambiguous linkage, and never converts a plan, revalidates with Core, generates an
approval or writes state. A failed read offers Try again; it never falls back to
a creation POST. Deployments need the matching Agent read endpoint before using
this UI change.

Create Workflow remains an explicit planning-page action. Preparing an exact
request, approving it and running the approved request remain separate actions.
The browser journey allowlists remove only the former duplicate conversion POST;
all later approvals and resumes retain their exact method, body and ordering.
Summary tests cover direct entry, reload and failed-read recovery at 320, 390 and
1280 pixels with zero mutation requests.


A saved candidate workflow in the initial `awaiting_approval` preparation state
now offers Review preparation when both exact request summaries are absent.
The link uses the workflow's reported planning session and opens the read-only
preparation summary; it does not create another workflow or prepare a request on
navigation. Missing or unusable linkage offers Check workflow status, a GET-only
retry. Later approval/execution states, other workflow sources and workflows with
an existing request retain their normal views.

The unfinished preparation view replaces unavailable-request and approval prompts
with a single explanation of the next step. Repository verification and commit
controls stay out of this initial view. Preparing the request still requires its
own explicit click; approving it and running it remain separate. Browser cases
resume both repository and maintenance preparation from a saved workflow, reload
both views without writes, and allow one exact synthetic request-preparation POST
only after the operator's click, with no approval or resume.

The unfinished view uses a short heading and puts its next step before saved
facts. Workflow identifiers, source information and progress remain available in
collapsed disclosures. Later-stage workflow views retain their existing layout.

Execution timeline summaries now use one repository-outcome presentation for
both the timeline header and execution details. Only `succeeded` displays green
completion. Failures, timeouts and launch failures have distinct error messages;
unknown outcomes retain the instruction to check the original result without
resubmitting. Unrecognized future statuses remain uncertain rather than appearing
successful. A reported final result takes precedence over an executing workflow
state, preventing simultaneous running and completion messages.

Missing results are not treated as successful or generically unavailable.
An approved initial request explains the separate resume step; rejected or
blocked workflows keep their own explanation. Backend stages, result fields,
approval checks, refresh requests and execution controls are unchanged. Tests
cover every current terminal execution status, unknown future values, conflicting
state/result observations, and read-only refresh at phone and desktop widths.

Repository implementation decisions now wait for a readable exact-request
summary. Mission Control checks the existing public DTO's request identity,
tool, working directory, repository, file list and nullable translator metadata
before rendering it. Missing or malformed summaries show Check request instead
of broken fields, implementation approval/rejection or implementation resume.
Empty file lists and nullable translator metadata remain valid. Additional
metadata is tolerated; this does not introduce a new backend contract.

Check request performs the existing workflow GET refresh, pauses while that read
is pending and never replays a decision. A successful read can restore the
separate approval or resume action. Existing approvals remain recorded while the
request is unavailable. Later verification/commit decisions and original-worker
result reconciliation keep their existing boundaries. The implementation request
explanation now uses plain language instead of listing internal editors and argv.

Commit approval and commit resume now wait for a readable exact-request summary.
The existing public commit DTO is checked for its request ID, commit message,
reviewed-content fingerprint, approval status, reviewed file list and nullable
repository/branch/HEAD metadata. Empty reviewed file lists and nullable metadata
remain valid. Additional response metadata is preserved for existing displays.

When the workflow is waiting for commit approval but its request is unreadable,
Check commit request performs the existing read-only refresh. It pauses during a
pending read and never approves or commits automatically. A previously recorded
approval remains recorded; a successful read only restores the separate action.
Earlier stages do not warn about commit requests that have not been created yet.
Commit approval wording describes the operator's decision rather than internal
HTTP payload fields. Backend approval binding and commit execution are unchanged.

Verification approval and verification resume now wait for an identified,
readable public plan summary. A null plan ID is the existing Agent sentinel for
no plan. Mission Control checks the current display DTO's ID, status, check lists
and nullable metadata before rendering it. Nullable metadata and empty check
lists remain compatible when a plan is identified; readiness still belongs to
Agent's exact approval boundary.

An unreadable plan at the verification approval stage offers Check verification
plan through the existing workflow GET. A successful read restores the separate
action without running checks. Earlier stages keep a plain empty state rather
than an alert about a plan that has not been created yet. Approval feedback for
verification and commit only suggests Resume when the corresponding review data
is available; recorded approvals remain visible when it is not.

Browser fixtures cover read-only recovery before/after approval at phone and
desktop widths. Two additional fixtures allow one exact synthetic approval POST,
then return unavailable review data and verify that no resume is submitted or
suggested. They never run verification or commit an actual repository change.

Workflow review now uses a short effect-specific heading and keeps workflow IDs,
source facts, translator metadata and request IDs in keyboard-accessible details.
The loaded page uses one authoritative execution-stage list rather than showing
a second progress rail. Execution status and Refresh stay visible while stage
and result metadata can be expanded when needed.

Implementation approval sits directly after the request being reviewed, followed
by its separately approved resume action when available. Repository views keep
the current review stage open and put inactive implementation, verification and
commit sections in disclosures. Blocked workflows retain their detail views;
preparation, approval decisions, resume guards, error feedback and request bodies
are unchanged. Earlier facts remain available for review without sending writes.

Phone and desktop fixtures cover pending and approved implementation,
maintenance, verification and commit views, opening identifiers and progress with
the keyboard while asserting zero mutations. Existing rejection, identity,
pending-refresh and full repository/maintenance journeys retain their assertions.

The workflow summary now names the approval for the current stage. Repository
verification/verifying states use verification approval, and commit/committing
states use commit approval. Implementation and maintenance states retain their
own approval labels. Blocked, completed and unrecognized stages use neutral
review guidance rather than presenting a past implementation approval as the
current decision. Recorded approval details remain available below. No action
handler, request, capability or approval/resume guard changes.

Workflow history puts recorded execution, verification and commit outcomes first,
alongside validation and any blocked reason. Routine artifact fields and record
identifiers remain available in keyboard-accessible disclosures; current, missing
and inconsistent stages stay open. The stage overview lists each stage once,
while all individual artifact records remain available. Return navigation is at
the top of the page.

Repository and maintenance history both announce failed audit validation even
when the response contains no failure code. Workflow state remains separate from
validation, and missing facts are not reconstructed. Read-only browser fixtures
cover completed, blocked, invalid and missing-record views at phone and desktop
widths, keyboard access to records, and zero mutation requests. Existing full
journeys still verify the recorded commit and exact approval/resume sequence.

The main dashboard now includes source-reported Atlas aggregate, system
assessment and policy problems in Operator Attention. These are observations,
not a new combined health score or execution permission. Healthy, unknown and
unsupported statuses do not become alerts. Links move to the corresponding
recorded health source on the same page, with keyboard focus and no extra action.

Policy timestamps use the same freshness presentation in both locations. Failed
refreshes retain explicit last-known warnings, and explanations use the existing
sensitive-text filter. Tests cover all three sources, stale recovery, malformed
statuses, keyboard navigation and zero writes at phone and desktop widths.

Operator Attention keeps five conditions visible and makes every remaining
reported condition available in a More conditions disclosure. Its count follows
source deduplication; expanded rows use the same status, safe text, source links,
workflow decision details and stale warnings as the first five. Refreshing the
page data keeps an existing disclosure open while updating the count and rows.
Keyboard and phone fixtures cover added conditions, failed refresh, collapse and
reopen, and direct navigation to a workflow that was initially below the cutoff.
This is local presentation only and submits no mutations or extra reads.

Recent Activity validates completion times with the shared strict calendar and
timezone parser and does not present future timestamps as known completions.
Unverifiable dates display Completion time unknown, remain inspectable, and sort
after records with known completion times. Recorded action outcomes remain
unchanged. Valid leap days, fractional seconds and timezone offsets preserve the
source instant. Browser fixtures cover impossible, timezone-free, future and
valid offset dates with read-only navigation at phone and desktop widths.

The shell labels Core's returned release metadata as Version reported rather
than Release available. This endpoint supplies a version string, not an update
check. Missing or failed version reads show Version unknown and Version not
reported with neutral styling, independently of subsystem health. The version
value, existing read request and navigation behavior are unchanged.

Recent Activity uses Failed and Succeeded for recorded action results and keeps
Unknown outcome for unsupported statuses. The introduction explains plainly that
past results do not show current health. Outcome classification, timestamp
validation, deduplication, retained history and read-only links are unchanged.

Workflow directory cards keep current state, target, latest result, approval state
and the Open Workflow link visible. Source, candidate and planning identifiers
are available in Workflow details; the existing progress rail is available in
Workflow progress. Blocked cards start with progress open. Search, totals,
paging, stale-read handling, result values and approval boundaries are unchanged.
Phone and desktop fixtures cover pending, completed and blocked cards, keyboard
access to all records, direct workflow navigation and zero mutation requests.
