# Mission Control

Mission Control is the Atlas OS operator interface: a React, TypeScript, and Vite application backed by Atlas Core API v1 and the proxied Atlas Agent API.

## Released v0.14 surfaces

- Infrastructure dashboard with Atlas, inventory-service, health, policy, finding, recommendation, and intelligence summaries.
- Provider workspaces for connections, resources, monitoring status, Provider Intent editing, intent suggestions, diagnostics, provider-advertised legacy actions, and filterable action history/detail.
- Discovery browse and item detail views with relationships, compatibility, dynamic evidence, freshness/health/conflicts, installed-version evidence, release evaluation, Compose/image evidence, grounding, and provenance.
- Discovery proposals with bounded navigation into supported next-step surfaces; proposals do not execute or approve work.
- Execution-candidate browsing, planning sessions, workflow-shell intake, exact repository approval stages, execution/verification/review/commit artifacts, workflow dashboards, timelines, and audit-chain views.
- Operational maintenance request preparation, operational lifecycle/history, recovery guidance, diagnostics, and support-bundle access.
- Core-owned operator login and session handling for protected mutations.
- Forge deployment analysis and planning views.

Mission Control presents and submits requests to authoritative backend contracts. It does not itself execute infrastructure changes, decide approval, expand intent sets, or bypass server-side identity, permission, target-fingerprint, and exact-approval checks.

Released mutation authorities remain separate: Provider Intent is monitoring-policy only; legacy provider actions use their provider surface; repository execution is exactly `update-compose-stack`; hardened operational dispatch is exactly `restart-service / proxmox / qemu`. Discovery is GET-only/read-only. There is no automatic approval, remediation, update, deployment, rollback, or release publication.

## Development

Use Node.js 20.19 or newer (Node.js 22.12+ recommended) and npm 10 or newer:

```bash
npm ci
npm run dev
```

The development server proxies `/api/v1` to Atlas Core at `http://127.0.0.1:8643`. Validate with:

```bash
npm test
npm run lint
npm run build
```
