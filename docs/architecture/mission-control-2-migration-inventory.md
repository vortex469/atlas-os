# Mission Control 2.0 Migration Inventory

This inventory records the current Mission Control implementation for an
incremental Mission Control 2.0 redesign. It is an audit artifact only: it does
not grant new runtime authority, change execution semantics, or move business
logic into the client.

Mission Control remains an operator/control interface. Atlas Core, Atlas Agent,
the execution worker, and their API contracts remain authoritative for state,
admission, queueing, execution, evidence, policy, provider access, and security
boundaries.

## Current Architecture

### Entry Points And Package Structure

- Mission Control is the React/TypeScript/Vite application in
  `services/mission-control`.
- Runtime entry is `services/mission-control/src/main.tsx`, which mounts
  `App` into `#root`.
- `services/mission-control/src/App.tsx` wraps the router in
  `OperatorSessionProvider`, making operator session state available to pages
  that need authenticated mutations.
- Browser routes are defined in `services/mission-control/src/app/router.tsx`.
- Shared layout and primary navigation live in
  `services/mission-control/src/layouts/MainLayout.tsx`.
- API clients live in `services/mission-control/src/api`.
- Reusable view components live in `services/mission-control/src/components`.
- Feature-level UI lives in:
  - `services/mission-control/src/features/mission-control`
  - `services/mission-control/src/features/discovery`
  - `services/mission-control/src/features/installation`
  - `services/mission-control/src/features/forge`
- Page shells live in `services/mission-control/src/pages`.
- Client-side TypeScript DTOs live in `services/mission-control/src/types`.
- UI helpers live in `services/mission-control/src/utils`.
- Test fixtures and setup live in `services/mission-control/src/test`.
- Structural boundary tests live in `services/mission-control/src/security`.

### Routes And Navigation

`services/mission-control/src/app/router.tsx` exposes these browser routes:

- `/` -> `MissionControlPage`
- `/operations` -> `OperationsPage`
- `/operations/request` -> `MaintenanceRequestPage`
- `/operations/history` -> `OperationalHistoryPage`
- `/operations/actions/:auditId` -> `ActionHistoryDetailPage`
- `/providers/:providerId` -> `ProviderPage`
- `/discovery` -> `DiscoveryPage`
- `/discovery/items/:itemId` -> `DiscoveryItemPage`
- `/execution-candidates` -> `ExecutionCandidatesPage`
- `/execution-candidates/:candidateId` -> `ExecutionCandidateDetailPage`
- `/installation/candidate-records/:candidateRecordId/readiness-review` ->
  `InstallationReadinessReviewPage`
- `/candidate-planning/:sessionId` -> `PlanningSessionPage`
- `/candidate-planning/:sessionId/workflow` -> `WorkflowShellPage`
- `/workflows` -> `WorkflowDashboardPage`
- `/workflows/:workflowId/audit` -> `WorkflowAuditPage`
- `/workflows/:workflowId` -> `WorkflowPage`
- `/forge` -> `ForgePage`
- `/operator/login` -> `OperatorLoginPage`
- `*` -> `NotFoundPage`

`MainLayout.tsx` renders enabled navigation links for Mission Control,
Operations, Operational History, Maintenance, Discovery, Execution Candidates,
Workflows, and Forge. Knowledge, Developer, and Settings are visible disabled
navigation placeholders. The layout also calls `atlas.get("")` to display the
Atlas Core release discovered from API v1.

### Major Pages And Views

- `features/mission-control/MissionControl.tsx` is the dashboard. It displays
  ACE summary, health, provider cards, policy visibility, intelligence
  telemetry, Atlas Agent status, execution candidate counts, workflow counts,
  and a workflow inbox. It locally aggregates paged workflow and execution
  candidate data for presentation only.
- `pages/ProviderPage.tsx` presents provider registry details, diagnostics,
  recommendations, resources, provider actions, connection state, telemetry,
  and policy details. It explicitly states that monitoring expectations and
  diagnostics do not start, stop, restart, remediate, mutate policy, or
  authorize execution.
- `pages/OperationsPage.tsx`, `pages/OperationalHistoryPage.tsx`,
  `pages/ActionHistoryDetailPage.tsx`, and `pages/MaintenanceRequestPage.tsx`
  cover operational action history, recovery/support surfaces, and maintenance
  request preparation.
- `pages/DiscoveryPage.tsx` and `pages/DiscoveryItemPage.tsx` present discovery
  catalog data and discovery evidence through feature components such as
  `DiscoveryEvidencePanel`, `DiscoveryImageGroundingPanel`,
  `InstallationCapabilityAssessment`, `InstallationPlanReview`,
  `ProspectiveDestinationReview`, `InstallationApprovalIntents`,
  `InstallationExecutionRequests`, `DeliveryActivationPreflights`,
  `DeliveryEnablements`, and `InstallationDispatchHandoffs`.
- `pages/ExecutionCandidatesPage.tsx` and
  `pages/ExecutionCandidateDetailPage.tsx` expose Core-owned execution
  candidates and the operator path into Agent candidate planning.
- `pages/PlanningSessionPage.tsx`, `pages/WorkflowShellPage.tsx`,
  `pages/WorkflowDashboardPage.tsx`, `pages/WorkflowPage.tsx`, and
  `pages/WorkflowAuditPage.tsx` expose Atlas Agent planning and workflow state,
  exact approval steps, verification/review/commit artifacts, lifecycle,
  recovery diagnostics, and audit-chain views.
- `pages/InstallationReadinessReviewPage.tsx` presents a read-only readiness
  gate for candidate records.
- `pages/ForgePage.tsx` renders `features/forge/Forge.tsx`, which analyzes
  Docker Compose documents through the Atlas Core deployment analysis endpoint.
- `pages/OperatorLoginPage.tsx` handles Core-owned operator login.

### Shared UI Components

Reusable presentation components include:

- Dashboard and status primitives:
  `DashboardHeader`, `HealthCard`, `ServiceHealthCard`, `StatusBadge`,
  `RefreshIndicator`, `SectionHeader`.
- Cards and diagnostic views:
  `FindingCard`, `RecommendationCard`, `ServiceDetailsDrawer`,
  `ApprovalCard`.
- Provider surfaces:
  `ProviderCard`, `ProviderOverview`, `ProviderResources`,
  `ProviderActions`, `ProviderConnection`, `ProviderIntentEditor`,
  `ProviderPolicyDetails`, `ProviderTelemetryTrend`,
  `ProviderIntentSuggestionCard`, and
  `providerResourceComposition.ts`.
- Agent and operational surfaces:
  `AtlasAgentPanel`, `AtlasDoctorPanel`, `WorkflowMiniRail`,
  `InstallContainerValidationPanel`, `OperationalLifecyclePanel`,
  `OperationalRecoverySummary`.

These components are presentation adapters over API DTOs. MC 2.0 can reuse many
of them, but should avoid letting component-level convenience logic become a new
source of authority.

### State Management And Data Fetching

Mission Control currently uses React state/hooks rather than a global data
store:

- `hooks/useMissionControl.ts` polls Atlas Core every 30 seconds for
  `/ace/summary`, `/health`, `/providers`, `/policies`,
  `/policies/status`, `/intelligence/telemetry/history`, and
  `/intelligence/telemetry/history/retention`. It stores loading, refresh,
  error, last-updated, and sorted provider presentation state locally.
- `features/mission-control/MissionControl.tsx` fetches all workflow summaries
  from Atlas Agent and execution candidate pages from Atlas Core to compute
  dashboard counts. These counts are client presentation state and must not be
  treated as admission, execution, or eligibility authority.
- `hooks/useAtlasAgent.ts` composes Atlas Agent status, repository status,
  sprint status, verification report, and review report for display.
- `hooks/useOperatorSession.tsx` stores the current authenticated operator
  principal and CSRF token from Atlas Core session responses. It does not use
  `localStorage` or `sessionStorage`.
- Page components such as `OperationsPage`, `WorkflowDashboardPage`,
  `WorkflowPage`, `DiscoveryPage`, and `ExecutionCandidatesPage` own local
  filter, pagination, form, and transient operation-message state.

Authoritative Atlas/Core/API state includes provider registry data, policy
documents and reload health, ACE/intelligence summaries, provider resources,
provider connection descriptors/results, discovery catalog/evidence,
installation candidate records, execution candidates, installation admission
records, queue observation records, operation audit history, operator sessions,
and deployment analysis responses.

Authoritative Atlas Agent state includes candidate planning sessions, workflow
details, workflow lists, approval decisions, lifecycle status, recovery
diagnostics, support bundles, repository status, sprint status, verification
reports, and review reports.

Mission Control presentation state includes sort order, selected filters, open
forms, loading/error flags, client-generated idempotency keys, refresh timers,
download blob handling, and local count aggregation from authoritative result
sets.

### API Clients And Authoritative Data Sources

`services/mission-control/src/api/atlas.ts` creates the Atlas Core client. Its
base URL is `VITE_ATLAS_API_BASE_URL` or `/api/v1`. It also exposes provider
action history, provider actions, deployment analysis, doctor, telemetry export,
telemetry retention/prune, and shared Atlas error-message helpers.

`services/mission-control/src/api/atlas-agent.ts` creates the Atlas Agent
client. Its base URL is `VITE_ATLAS_AGENT_API_BASE_URL` or `/agent-api`. It
performs structural payload validation for several Agent responses and exposes
candidate planning, workflow, approval, operational lifecycle, recovery
diagnostic, support bundle, repository, sprint, verification, and review calls.

Other client modules map to bounded Atlas Core contracts:

- Provider and policy surfaces:
  `connections.ts`, `operatorAuth.ts`, `operatorIntent.ts`,
  `providerIntentSuggestions.ts`, `providerManagement.ts`, `resources.ts`.
- Discovery and installation surfaces:
  `discovery.ts`, `installationDestination.ts`,
  `installationCapability.ts`, `installationCandidateAdmission.ts`,
  `installationCandidateLifecycle.ts`, `installationApprovalIntent.ts`,
  `installationExecutionRequest.ts`, `installationExecutionAdmission.ts`,
  `installationDispatchHandoff.ts`, `installationReadinessReview.ts`.
- Queue, worker, admission, and evidence surfaces:
  `runnerBindingPlan.ts`, `workerAdmissionStub.ts`,
  `workerQueueReservation.ts`, `workerIntakeAdmission.ts`,
  `liveEnqueueAdmission.ts`, `oneShotLiveEnqueue.ts`,
  `queueObservation.ts`, `controlledDequeueAdmission.ts`,
  `oneShotControlledDequeue.ts`, `oneShotDequeueWorkerBinding.ts`,
  `workerBindingActivationPreflight.ts`,
  `workerBindingActivationEvidence.ts`,
  `controlledWorkerQueueClaimAdmission.ts`,
  `executionPermissionGrant.ts`.
- Execution candidate surfaces:
  `executionCandidates.ts`.

Atlas Core API v1 router registration is centralized in
`services/atlas-core/app/api/v1/router.py`. Mission Control consumes Core
routes from modules such as `routes/health.py`, `routes/ace.py`,
`routes/providers.py`, `routes/provider_connections.py`,
`routes/provider_management.py`, `routes/provider_intent_mutation.py`,
`routes/provider_resources.py`, `routes/discovery.py`,
`routes/installation*.py`, `routes/*admission*.py`,
`routes/queue_observation.py`, `routes/execution_candidates.py`,
`routes/ops.py`, `routes/operator_auth.py`, `routes/policies.py`,
`routes/intelligence.py`, and `routes/analysis.py`.

Atlas Agent routes used by Mission Control are defined in
`services/atlas-agent/app/routes/status.py`,
`services/atlas-agent/app/routes/candidate_planning.py`,
`services/atlas-agent/app/routes/workflow.py`, and
`services/atlas-agent/app/routes/approval.py`.

Production proxy ownership is in
`deploy/docker/mission-control.nginx.conf`: `/api/` proxies to `atlas-core:8643`
and `/agent-api/` proxies to `atlas-agent:8090/`. The proxy clears identity
headers such as `X-Atlas-Operator`, `X-Auth-User`, `X-User`, and `Remote-User`
before forwarding, and forwards the Core CSRF header for protected Core
mutations.

### Worker, Agent, Provider, Queue, Execution, Admission, Evidence, And Configuration Presentation

- Worker and queue presentation is implemented through installation feature
  components and API modules for worker admission stubs, worker queue
  reservations, worker intake admissions, live enqueue admissions, one-shot
  live enqueues, queue observations, controlled dequeues, one-shot controlled
  dequeues, one-shot dequeue worker bindings, worker binding activation
  preflights/evidence, controlled worker queue claim admissions, and execution
  permission grants.
- Agent presentation is handled through `AtlasAgentPanel`, candidate planning
  pages, workflow pages, workflow audit pages, operational lifecycle pages, and
  `api/atlas-agent.ts`. The Agent remains authoritative for planning/workflow
  lifecycle and repository-facing work.
- Provider presentation is centered in `ProviderPage.tsx` and provider
  components. Provider registry, resources, connection descriptors, policy
  details, suggestions, and action results come from Atlas Core provider routes.
- Execution candidate presentation reads Core-owned execution candidates and
  routes eligible operator flow into Agent planning. Client summaries do not
  determine eligibility.
- Admission and evidence surfaces preserve their bounded API contracts. The
  Mission Control client generates idempotency keys and submits CSRF-protected
  requests, but Core/Agent decide acceptance, blocking, expiry, lifecycle,
  fingerprint validity, and evidence provenance.
- Configuration presentation uses Core policy and provider resources endpoints.
  `ProviderIntentEditor` and provider management clients submit monitoring
  policy/provider intent changes only through Core-owned endpoints; Mission
  Control does not directly edit `config/policies.yaml`, `config/atlas.yaml`,
  provider secrets, inventory, or Core stores.

### Responsive And Accessibility Behavior

- Layout is Tailwind-driven. `MainLayout.tsx` uses a single-column layout on
  smaller screens and a fixed sidebar plus content grid at `lg`.
- Pages and features rely on responsive grid classes such as
  `sm:grid-cols-*`, `md:grid-cols-*`, `lg:grid-cols-*`, and `xl:grid-cols-*`.
- Route pages generally expose semantic `main`, `section`, `header`, and
  `article` containers.
- Key dashboard content includes screen-reader headings such as the
  `MissionControl` `h1.sr-only`, `aria-label`, `aria-labelledby`,
  `role="main"`, `role="status"`, `role="alert"`, and `aria-live` where
  appropriate.
- Interactive links and buttons commonly include focus rings and disabled
  states.
- Existing gaps: the desktop sidebar remains a full-height `aside` on small
  screens, several complex table-like grids flatten unevenly on mobile, and the
  app does not currently have end-to-end keyboard, focus-order, reduced-motion,
  or automated accessibility audits.

### Tests, Build, And Lint Configuration

- `services/mission-control/package.json` defines:
  - `npm run dev` -> Vite dev server
  - `npm run build` -> `tsc -b && vite build`
  - `npm run lint` -> ESLint
  - `npm test` -> `vitest run`
- `services/mission-control/vite.config.ts` configures React, Tailwind, and a
  dev proxy from `/api/v1` to `http://127.0.0.1:8643`.
- `services/mission-control/vitest.config.ts` uses jsdom and
  `src/test/setup.ts`.
- `services/mission-control/eslint.config.js` applies ESLint recommended rules,
  TypeScript ESLint, React Hooks rules, and Vite React Refresh rules.
- Coverage is broad at the unit/component/structural level: most API clients,
  pages, major provider/discovery/installation components, hooks, layout, and
  security boundaries have Vitest files beside the implementation or in
  `src/security`.
- Structural tests explicitly protect sensitive boundaries, including operator
  UI identity/header/session storage restrictions, provider authority,
  discovery image grounding isolation, installation dispatch handoff structure,
  live delivery send isolation, real/agent intake boundaries, admission and
  worker queue contracts, execution permission grant behavior, and dormant
  delivery wiring isolation.

## Migration Inventory

### 1. Reuse As-Is

- Runtime shell: `main.tsx`, `App.tsx`, `router.tsx`, and the current
  `OperatorSessionProvider` wrapping pattern.
- Axios base clients in `api/atlas.ts` and `api/atlas-agent.ts`, including
  default base URLs and request timeouts.
- Core/Agent API boundary modules and DTO files, especially the contract
  adapters in `api/*Admission*.ts`, `api/*Worker*.ts`, `api/queueObservation.ts`,
  `api/installationDispatchHandoff.ts`, `api/executionPermissionGrant.ts`, and
  `api/operatorAuth.ts`.
- Structural security tests in `src/security`.
- Shared status and card primitives where the current information hierarchy is
  sufficient: `StatusBadge`, `RefreshIndicator`, `SectionHeader`, `HealthCard`,
  `ServiceHealthCard`, `FindingCard`, and `RecommendationCard`.
- Existing production proxy separation in `deploy/docker/mission-control.nginx.conf`.
- Existing Vite/Vitest/ESLint setup.

### 2. Reuse With Refactoring

- `features/mission-control/MissionControl.tsx`: keep its dashboard role, but
  separate data aggregation from rendering before redesigning layout. Current
  local workflow/candidate aggregation should become a clearly named
  presentation adapter, not a source of truth.
- `hooks/useMissionControl.ts`: keep polling semantics and Core ownership, but
  consider splitting dashboard data, provider data, policy data, and telemetry
  data so MC 2.0 views can refresh independently without coupling unrelated
  panels.
- `MainLayout.tsx`: preserve routes and navigation authority, but refactor for
  mobile navigation and route metadata instead of hard-coded mixed enabled and
  disabled items.
- Provider components: retain `ProviderOverview`, `ProviderResources`,
  `ProviderConnection`, `ProviderActions`, `ProviderIntentEditor`, and
  `ProviderPolicyDetails`, but isolate read-only diagnostics from mutation
  panels more explicitly in the component tree.
- Discovery and installation feature components: keep the current contract
  mapping, but factor repeated loading/error/empty states and idempotency
  request controls into shared presentation helpers.
- Workflow pages: preserve Agent-owned lifecycle and approval semantics, but
  split long page components into state adapters plus focused display sections.
- `api/atlas-agent.ts`: keep defensive parsing, but centralize repeated
  response-shape validation helpers if the file continues to grow.

### 3. Replace Incrementally

- Ad hoc page-local pagination/filter state should be replaced incrementally
  with reusable URL-query-aware hooks, while keeping backend query semantics
  unchanged.
- Repeated card/table-like grid markup should be replaced with accessible,
  responsive list/table primitives that preserve current content and actions.
- Dashboard count aggregation should move to a reusable presentation summary
  module or, if a backend summary endpoint is later introduced, to a backend
  contract owned by Core/Agent. Mission Control must not independently decide
  eligibility, admission, or workflow actionability beyond displaying
  authoritative states.
- Client-side download blob helpers in operational and telemetry exports should
  become a small shared utility.
- Disabled future navigation placeholders should be replaced only when backing
  routes and authoritative APIs exist.

### 4. Do Not Change Without Explicit Architectural Authorization

- Do not change Atlas Core authority over provider registry, policies,
  provider resources, provider connection descriptors, discovery evidence,
  installation candidate records, execution candidates, admission records,
  queue/worker records, operation audit history, operator sessions, and
  deployment analysis.
- Do not change Atlas Agent authority over candidate planning, workflow
  lifecycle, exact approval stages, repository state, verification/review
  artifacts, commits, operational lifecycle, recovery diagnostics, and support
  bundles.
- Do not change execution worker, queue, admission, Core, Agent, or evidence
  semantics from Mission Control.
- Do not duplicate Core business logic in the client, including policy
  resolution, provider compatibility, admission decisions, resource risk,
  target fingerprint checks, queue claim eligibility, delivery authorization,
  evidence provenance, or fail-closed behavior.
- Do not bypass Core-owned operator authentication, CSRF protection,
  idempotency-key requirements, server-side identity, permission checks,
  exact-approval checks, or audit recording.
- Do not reintroduce browser storage for operator credentials, principals,
  bearer tokens, or CSRF tokens.
- Do not let the Mission Control proxy forward untrusted identity headers.
- Do not merge monitoring policy mutation, provider legacy actions,
  operational maintenance, repository execution, installation dispatch, or
  discovery proposal navigation into a single client-side authority path.
- Do not make discovery or image grounding execute, approve, deploy, rollback,
  remediate, or publish releases.
- Do not modify `config/atlas.yaml`, `config/policies.yaml`, provider secrets,
  Core stores, Agent stores, queues, evidence ledgers, or worker configuration
  from Mission Control outside the existing authoritative APIs.

### 5. Existing Test Coverage And Gaps

Existing coverage:

- API client tests cover endpoint paths, query parameters, encoding,
  CSRF/idempotency headers, and response parsing for many Core contracts.
- Component and page tests cover Mission Control dashboard sections, provider
  pages, discovery flows, installation/admission/evidence panels, workflow
  pages, operations pages, operator login, layout, and hooks.
- Structural security tests protect boundaries for operator auth, provider
  authority, discovery, image grounding, dormant/live delivery, real/agent
  intake, admission, queue, worker binding, execution permission, and install
  container contracts.
- Atlas Core route tests under `services/atlas-core/app/routes` verify the
  server-side contracts consumed by Mission Control.
- Atlas Agent route and service tests under `services/atlas-agent/tests` verify
  planning, workflow, approval, execution, verification, review, persistence,
  and route behavior consumed by Mission Control.

Gaps to address during MC 2.0:

- No full-browser end-to-end suite currently verifies navigation, protected
  mutations, focus behavior, or responsive layout across the operator console.
- No automated accessibility audit is wired into Mission Control validation.
- No visual regression coverage exists for dense dashboard/provider/workflow
  states.
- Polling and race behavior is tested in focused hooks/components, but there is
  no shared data-fetching abstraction with centralized retry, cancellation, or
  stale-response policy.
- Long pages and feature components still rely on local state patterns that can
  drift in behavior across surfaces.
- Mobile sidebar/navigation and complex grid views need explicit tests before a
  visual redesign.

### 6. Recommended Migration Order

1. Freeze authority boundaries by keeping the existing API modules and
   structural security tests as the MC 2.0 compatibility baseline.
2. Extract route metadata from `MainLayout.tsx` and `router.tsx` without
   changing paths, labels, enabled states, or page components.
3. Split dashboard data adapters from `MissionControl.tsx` rendering while
   preserving current polling, aggregation, counts, and error behavior.
4. Introduce shared loading/error/empty-state, pagination, filter, export, and
   responsive table/list primitives behind existing pages.
5. Refactor provider, discovery, installation, and workflow pages one surface at
   a time so each retains its current API client, tests, CSRF/idempotency
   handling, and structural boundary tests.
6. Add MC 2.0 responsive and accessibility checks after primitives exist, then
   redesign visual composition within the same authority constraints.
7. Only after the presentation refactors are covered should any new backend
   summary/read endpoints be proposed, and those must remain owned by Atlas Core
   or Atlas Agent rather than Mission Control.
