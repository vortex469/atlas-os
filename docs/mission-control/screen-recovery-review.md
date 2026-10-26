# Mission Control screen recovery review

This review covers the simplification and repair work on
`codex/mission-control-screen-recovery`. It is a source and simulated-browser
review, not production acceptance or authorization to merge, deploy, enable a
runtime, tag, or publish a release.

## Operator outcomes and evidence

| Surface | Required behavior | Current regression evidence |
| --- | --- | --- |
| Shared navigation | Plain menu labels distinguish action history, maintenance history, request creation and proposals; only the owning destination is highlighted; links, mobile drawer, focus, skip link and missing-page recovery work | `e2e/navigation.spec.ts`, `e2e/app-shell.spec.ts`, `e2e/screen-recovery.spec.ts`; `src/layouts/MainLayout.test.tsx` includes maintenance/action-detail ownership |
| Screen loading | Secondary screens load on demand; pending navigation pauses the old page's controls while keeping navigation available; module failure offers reload and home recovery | `e2e/page-loading.spec.ts` covers delayed modules, leaving a pending screen, and direct-link failure/reload at phone and desktop widths |
| Generated frontend assets | Built pages preserve the supported operator journeys, navigation and responsive shell | `playwright.built.config.ts` reuses 42 compatible browser cases against the generated build; API requests remain bound to the configured origin and exact isolated fixtures |
| Development API routing | Core paths are preserved; the Agent prefix is removed; session/CSRF/origin headers are preserved and caller identity headers are stripped | `src/server/devProxy.test.ts` uses the actual Vite server with isolated HTTP stubs; no Atlas backend or mutation is involved |
| Dashboard | Attention and health remain distinct; optional detail does not crowd the main screen | `e2e/overview.spec.ts`, `e2e/dashboard-block.spec.ts`, `e2e/system-health.spec.ts`; overview and worker component tests |
| Providers | Registry and detail links work; unavailable data differs from absence; forms and late responses stay with their provider | Provider page/component tests; provider registry and route-switch browser cases in `e2e/screen-recovery.spec.ts` |
| Discovery and sign-in | Advisory context survives login without selecting or authorizing a maintenance target | Discovery/login/maintenance page tests; `e2e/operator-signin.spec.ts` |
| Proposals and planning | Only current search results and matching proposal/plan identities appear; preparation has four simple steps | Proposal/planning page tests; proposal recovery browser cases; both workflow journey specs |
| Repository workflow | Each exact approval and resume remains separate; rejection survives reload; audit follows completion | `e2e/repository-journey.spec.ts`; workflow detail, shell, timeline and audit component tests |
| Maintenance workflow | Explicit target selection and exact request submission return a proposal; operational plan and exact verification rules precede action approval; a separate run precedes lifecycle outcome and audit | `e2e/maintenance-journey.spec.ts`; planning and workflow component tests |
| Maintenance history and audit | Foreign workflow evidence is refused; unavailable results remain findable; maintenance audit avoids repository-only stages | History/audit component tests; history browser recovery and maintenance journey audit cases |
| Provider action history | Changing filters or refreshing hides previous results; failed reads do not retain an actionable retention policy; superseded responses cannot replace current results | `src/pages/OperationsPage.test.tsx` includes delayed-response and failure regressions |
| Atlas Doctor | Rerunning clears the previous report; pending and failed reads cannot retain an old healthy score | `src/components/AtlasDoctorPanel.test.tsx` includes healthy-to-pending-to-unavailable coverage |
| Provider connection tests | Editing inputs or reloading settings clears the old test result; tested secrets are redacted in result messages, diagnostic field names and values | `src/components/ProviderConnection.test.tsx` uses synthetic secret canaries, checks stale-result invalidation, and mocks every test/save request |
| Forge | Edited inputs invalidate results; late responses are ignored; both reported risks remain visible; unknown duration is not zero | `src/features/forge/Forge.test.tsx`, `e2e/forge-analysis.spec.ts` |
| Installation readiness | Owner evidence loads after read-only recovery, remains bound to the current record, and grants no installation authority | Readiness component/parser/structural tests; `e2e/readiness-review.spec.ts` and invalid-review browser recovery case |

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
