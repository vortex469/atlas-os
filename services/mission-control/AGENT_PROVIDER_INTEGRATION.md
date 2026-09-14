# Agent/provider overview integration

Compared d7f39f64 with the current MissionControl implementation. Ported public
identity validation, explicit registry/configuration semantics, provider detail
navigation, workflow navigation, and malformed/duplicate identity handling into
presentation-only consumers of useOverviewEvidence. Retained the six-card layout,
SystemHealthSummary, WorkerExecutionSection, HealthEvidence, source freshness,
and attention condition keys/deduplication.

The original branch inferred Agent availability from app_name. This integration
keeps health unknown because the Agent information contract supplies identity,
not health. Provider failed statuses retain the shared degraded presentation and
explicit source status; they are not collapsed into unavailable. Stale observations
remain visible as last-known evidence. Existing sanitized provider reasons remain
visible; arbitrary configuration, model assignments, and diagnostics are not read.
Provider links use validated registry identities and existing routes. No API,
execution, authentication, provider contract, or mutation path was changed.

Validation attempted in this worktree:

- Focused AgentProviderContent, Overview, useOverviewEvidence, and structural tests:
  blocked (Vitest missing).
- Full Mission Control Vitest and security tests: blocked (Vitest missing).
- npm run lint: blocked (ESLint missing).
- npm run build: blocked (project dependencies/type definitions missing; fallback
  TypeScript does not support the project compiler options).
- npm run test:e2e:list: blocked (project Playwright dependency missing).
- npm ci: registry.npmjs.org requests failed with EAI_AGAIN; stopped retries.
- git diff --check: passed.

Manual hostile review covered old dashboard restoration, duplicate state, success
inference, stale/unknown loss, malformed rows, unsafe links, authority drift, unified
health, and worker/execution integration. Automated validation and the final
post-test hostile-review gate remain pending until dependencies can be installed.
