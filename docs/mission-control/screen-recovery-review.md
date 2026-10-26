# Mission Control screen recovery review

This review covers the simplification and repair work on
`codex/mission-control-screen-recovery`. It is a source and simulated-browser
review, not production acceptance or authorization to merge, deploy, enable a
runtime, tag, or publish a release.

## Operator outcomes and evidence

| Surface | Required behavior | Current regression evidence |
| --- | --- | --- |
| Shared navigation | Working primary links, mobile drawer, keyboard focus, skip link, missing-page recovery | `e2e/navigation.spec.ts`, `e2e/app-shell.spec.ts`, `e2e/screen-recovery.spec.ts`; `src/layouts/MainLayout.test.tsx` |
| Dashboard | Attention and health remain distinct; optional detail does not crowd the main screen | `e2e/overview.spec.ts`, `e2e/dashboard-block.spec.ts`, `e2e/system-health.spec.ts`; overview and worker component tests |
| Providers | Registry and detail links work; unavailable data differs from absence; forms and late responses stay with their provider | Provider page/component tests; provider registry and route-switch browser cases in `e2e/screen-recovery.spec.ts` |
| Discovery and sign-in | Advisory context survives login without selecting or authorizing a maintenance target | Discovery/login/maintenance page tests; `e2e/operator-signin.spec.ts` |
| Proposals and planning | Only current search results and matching proposal/plan identities appear; preparation has four simple steps | Proposal/planning page tests; proposal recovery browser cases; both workflow journey specs |
| Repository workflow | Each exact approval and resume remains separate; rejection survives reload; audit follows completion | `e2e/repository-journey.spec.ts`; workflow detail, shell, timeline and audit component tests |
| Maintenance workflow | Operational plan is displayed; exact target and verification rules precede action approval; a separate run precedes lifecycle outcome | `e2e/maintenance-journey.spec.ts`; planning and workflow component tests |
| Maintenance history and audit | Foreign workflow evidence is refused; unavailable results remain findable; maintenance audit avoids repository-only stages | History/audit component tests; history browser recovery and maintenance journey audit cases |
| Forge | Edited inputs invalidate results; late responses are ignored; both reported risks remain visible; unknown duration is not zero | `src/features/forge/Forge.test.tsx`, `e2e/forge-analysis.spec.ts` |
| Installation readiness | Review evidence remains bound to the current record and optional details remain collapsed | Readiness component and structural tests; invalid-review browser recovery case |

Paths in the table are relative to `services/mission-control`.

The default browser fixture rejects mutations. Separate synthetic fixtures allow
only the expected login, analysis, or ordered workflow requests and reject other
mutations. Workflow fixtures simulate results: they run no model, verification
command, Git commit, deployment, or provider action.

The backend change is additive: workflow audit responses identify their
`effect_kind`, allowing maintenance audits to display the existing read-only
operational lifecycle. No execution gate or approval contract is expanded.

## Validation snapshot — 2026-10-26

UI source checked at `b13b9c7aeba78060302612f15cca74b31a2b1679`:

- Full component suite: 2,562 passed, zero failed or skipped.
- Browser suite: 61 passed against synthetic local backends.
- UI lint and production build passed. The build retains its existing
  large-chunk warning.
- Workflow route suite: 72 passed after the additive audit DTO change. This is
  focused Agent coverage, not a full Core/Agent release-gate result.

Reproduce UI checks from `services/mission-control` with `npm test --
--maxWorkers=2`, `npm run test:e2e -- --workers=2`, `npm run lint`, and
`npm run build`. Browser tests require the local test server and Chromium.

## Remaining acceptance gaps

- The maintenance browser coverage currently joins two separately tested
  segments: Discovery/sign-in/target selection and proposal/planning/exact
  approval/run/audit. One browser journey does not yet cover maintenance request
  submission through the returned proposal. Component tests cover that request
  boundary; a combined synthetic journey is still needed.
- The installation readiness browser case proves rejection and recovery for an
  invalid response, not a complete successful review journey. It does not prove
  installation execution and must not be described as doing so.
- Operator visual acceptance of the running interface, real backend integration,
  running-image parity, and production acceptance have not been established by
  these simulated checks.
- Source review and CI are review inputs. They do not authorize merging or any
  release, deployment, runtime enablement, or infrastructure operation.

Mission Control completion remains open while these applicable journey and
operator acceptance requirements are unverified. Deferred execution capabilities
and the successor control plane are not made available by this work.
