# Atlas Architecture

Atlas is a local-first control plane with two runtime services.

```text
Mission Control (React/Vite)
            |
            | HTTP /api/v1
            v
Atlas Core (FastAPI)
    |       |        |
    |       |        +-- Deployment analysis, risk, and planning
    |       +----------- ACE findings, policies, and telemetry
    +------------------- Provider registry and guarded actions
            |
            v
Infrastructure providers and inventory services
```

## Atlas Core

Atlas Core owns typed API contracts, request tracing, provider
registration, deployment analysis, operational policy validation, and
local audit databases. `/api/v1` is the public API surface. Legacy
unversioned routes remain mounted for existing integrations.

Providers translate external service state into sanitized health,
capability, action, and finding contracts. ACE collects provider findings
concurrently under a configured deadline and records timing/outcome
telemetry without storing provider credentials.

Policy files are validated and reloaded at runtime. Invalid updates keep
the last valid policy snapshot active and expose sanitized diagnostics to
operators.

## Mission Control

Mission Control is a client-rendered React application. It consumes Atlas
Core rather than connecting directly to infrastructure services. It
provides health, provider, Forge, action-audit, policy, and
provider-intelligence views.

## Local state

Atlas stores action audit and provider-intelligence telemetry in separate
SQLite databases beneath the configured data directory. Both stores have
entry-count and age retention limits plus explicit, confirmed maintenance
endpoints.

Credentials are supplied through environment variables. Configuration,
policy, inventory, telemetry, and API responses must not contain secret
values.
