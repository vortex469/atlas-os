# Mission Control

Mission Control is the Atlas OS operational interface. It is a React,
TypeScript, and Vite application backed by Atlas Core API v1.

## Current capabilities

- Unified infrastructure and ACE summary
- Live Atlas and inventory service health
- Provider catalog and provider details
- Service details drawer
- Provider-advertised actions
- Confirmation for guarded operations
- Schema-driven action parameters
- Health refresh after successful operations
- Filterable, persistent provider action history
- Request ID and execution timing visibility
- JSON and CSV audit exports
- Confirmed expired-entry pruning
- Provider and UTC date-range audit filtering
- Filter-aware exports
- Paginated audit results
- Action and request-ID search
- Audit detail views with shareable deep links
- Refresh-aware service details
- On-demand Atlas Doctor diagnostics
- OPNsense health and diagnostics through the provider workspace
- Frigate camera health and version telemetry
- Forge deployment analysis workspace
- Execution candidate browsing and planning-only Atlas Agent intake
- Read-only candidate planning session and plan viewer
- Approval-gated workflow shell creation and read-only workflow summary
- Read-only immutable implementation request review with exact approve or reject controls
- Read-only execution timeline and execution result summary
- Read-only verification plan, verification evidence, deterministic review, and exact verification approval controls
- Read-only workflow dashboard with summary counts, filters, refresh, compact workflow rails, and workflow detail links
- Read-only immutable commit request review with exact approve or reject controls and completed workflow commit result display
- Read-only workflow audit chain explorer with machine-readable stage statuses, inconsistency detection, and missing-artifact alerts

## Development

Use Node.js 20.19 or newer (Node.js 22.12+ is recommended) and npm 10 or
newer. Install the locked dependency graph and start the development server:

```bash
npm ci
npm run dev
```

The development server proxies `/api/v1` to Atlas Core at
`http://127.0.0.1:8643`.

## Validation

Run the component tests, lint checks, and production build:

```bash
npm test
npm run lint
npm run build
```

## Phase 3 boundary

Mission Control can display Atlas Agent, Discovery, execution-candidate, and persisted workflow state. It can ask Atlas Agent to create or reuse a planning-only session for an eligible candidate, generate a read-only candidate plan, create or return an approval-gated workflow shell, display the workflow shell summary, browse persisted workflow summaries, approve or reject the exact immutable implementation request returned by Atlas Agent, display a read-only execution timeline/result summary, display read-only verification and deterministic review artifacts, approve or reject exact verification, display the immutable commit request, approve or reject the exact commit request, and display completed workflow commit results. The workflow dashboard is navigation-only and does not submit approval decisions, commands, resume requests, repository paths, evidence, fingerprints, or workflow mutations. Mission Control does not expose execution controls, manual verification controls, review editing, editable commit messages, editable commit paths, push, tag, amend, release, rollback, or candidate execution controls. It must not imply support for release publication, remote deployment, rollback automation, automatic approval, or automatic execution.
Read-only workflow audit views expose chain statuses and artifacts without mutation controls.

The supported Atlas Agent candidate intent is `update-compose-stack`, and all candidate planning is revalidated authoritatively by Atlas Agent and Atlas Core.
