# Mission Control screen recovery review

This review covers the simplification and repair work on
`codex/mission-control-screen-recovery`. It is a source and simulated-browser
review, not production acceptance or authorization to merge, deploy, enable a
runtime, tag, or publish a release.

## Operator outcomes and evidence

| Surface | Required behavior | Current regression evidence |
| --- | --- | --- |
| Shared navigation | Working primary links, mobile drawer, keyboard focus, skip link, missing-page recovery | `e2e/navigation.spec.ts`, `e2e/app-shell.spec.ts`, `e2e/screen-recovery.spec.ts`; `src/layouts/MainLayout.test.tsx` |
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
| Provider connection tests | Editing public or secret inputs and reloading settings clears the old test result; changing the redaction input cannot reveal a previous tested secret | `src/components/ProviderConnection.test.tsx` uses synthetic secret canaries and mocks every test/save request |
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

Full UI component source checked at
`b13b9c7aeba78060302612f15cca74b31a2b1679`; subsequent readiness constant
extraction checked with the focused suite below:

- Full component suite: 2,562 passed, zero failed or skipped.
- Latest browser suite: 63 passed against synthetic local backends, including
  maintenance request-to-audit and successful readiness-review recovery.
- Readiness component/parser/structural suite: 16 passed after the constant
  extraction; the extracted values match the preceding committed values exactly.
- Maintenance request page suite: 19 passed after locking pending selection,
  clearing stale resources/results, and checking returned proposal identity,
  target and action. The complete maintenance browser fixture uses Core's
  resource-ID target contract.
- UI lint and production build passed. The build retains its existing
  large-chunk warning.
- Workflow route suite: 72 passed after the additive audit DTO change. This is
  focused Agent coverage, not a full Core/Agent release-gate result.

Reproduce UI checks from `services/mission-control` with `npm test --
--maxWorkers=2`, `npm run test:e2e -- --workers=2`, `npm run lint`, and
`npm run build`. Browser tests require the local test server and Chromium.
The existing Quality gates workflow now includes that browser command after
installing Chromium. It uploads browser failure screenshots and traces for seven
days. A local isolated failure probe confirmed both files are produced; the
changed workflow still requires its own CI result before a green-check claim.
An additional fixture audit validated nine representative synthetic responses
against native Core/Agent response models. It corrected omitted candidate effect
kinds and audit preparation approval fields. Browser tests are now included in
the TypeScript build so these required fields cannot silently disappear from
typed fixtures. This schema check does not establish real backend integration.
The development Agent proxy was also restored to match the production edge.
Thirty-five focused proxy/Discovery tests and all 63 browser checks passed.
Existing local Core/Agent health reads did not provide usable responses, so they
do not establish service health or real integration acceptance.
The bounded health change passes eight focused Core health/route/release tests.
The tests use isolated probes to establish overlap, a four-probe limit, complete
results, stable mapping/order and unchanged timeout/offline behavior; they do
not contact inventory services or establish running-service acceptance.

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
