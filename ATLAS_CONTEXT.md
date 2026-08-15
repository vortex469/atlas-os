# Atlas OS

## Vision

Atlas OS is a local-first, intent-driven infrastructure operating system designed to monitor,
reason about, and automate a homelab environment. Other tools show what is; Atlas understands what should be. See [Atlas Design Principles](ATLAS_DESIGN_PRINCIPLES.md) and [Atlas Runtime Architecture](ATLAS_RUNTIME_ARCHITECTURE.md).

Assistant: Orion

Reasoning Engine: ACE (Atlas Cognitive Engine)

Release: Foundry

---

# Architecture

Atlas Core
    ↓
Providers
    ↓
Findings
    ↓
Assessment Engine
    ↓
Situation Report
    ↓
REST API

---

# Current Providers

Implemented

- Proxmox
- Docker
- Home Assistant
- Ollama
- OPNsense
- Frigate
- Obsidian
- Qdrant
- n8n
- Inventory-backed services

---

# Configuration

Current behavior reads operational policy from runtime state in `data/config/policies.yaml` when available. Tracked `config/` files are treated as immutable bootstrap templates. The Atlas Runtime Foundation boundary is:

Immutable defaults

config/

    atlas.yaml

    policies.yaml

Mutable runtime state

data/

    config/

    databases/

    history/

    cache/

    knowledge/

inventory/

    services.yaml

---

# Policy System

ACE supports operational policy.

Current

- Expected Proxmox guest state
- Ignored Home Assistant entities
- Expected Docker container state
- OPNsense firmware posture
- OPNsense firmware severity thresholds
- Frigate camera health thresholds
- Obsidian vault health
- Qdrant collection expectations
- n8n workflow expectations
- Provider intelligence performance thresholds

---

# Development Standards

- Production-quality code
- Type hints everywhere
- Pydantic models
- Unit tests for every feature
- Small incremental commits
- Architecture first
- Reusable components
- No duplicated logic

---

# Current Milestones

✔ Situation Report

✔ Structured Findings

✔ Assessments

✔ Recommendations

✔ Policy Engine

✔ Proxmox Expected State

✔ Home Assistant Expected State

✔ Atlas API v1

✔ Unified Dashboard API

✔ Provider Action Engine

✔ Mission Control Service Health

✔ Confirmed and Parameterized Operations

✔ Action History and Audit Visibility

✔ Persistent Audit Storage and Retention

✔ Audit Export and Retention Administration

✔ Provider and Date-Range Audit Filtering

✔ Audit Pagination and Action/Request Search

✔ Audit Detail Views and Shareable Deep Links

✔ Dashboard Refresh and Service Detail Coverage

✔ Dynamic Policy Reload

✔ Docker Expected State

✔ Atlas Doctor Integration

✔ OPNsense Provider

✔ Provider-Backed ACE Findings

✔ OPNsense Policy Thresholds

✔ Provider Intelligence Time Budgets

✔ Frigate Provider

✔ Frigate Camera Health Policies

✔ Provider Intelligence Timing Telemetry

✔ Obsidian Provider

✔ Qdrant Provider

✔ Obsidian Vault Policies

✔ n8n Provider

✔ Qdrant Collection Policies

✔ n8n Workflow Policies

✔ Mission Control Provider Intelligence Telemetry

✔ Provider Policy API and Mission Control Visibility

✔ Provider Policy Detail Views

✔ Policy Reload Health Telemetry

✔ Persistent Provider Intelligence Trend History

✔ Structured Policy Validation Diagnostics

✔ Provider Telemetry History Filtering

✔ Policy Diagnostics Operator Examples

✔ Provider Telemetry History Export

✔ Provider Telemetry Retention Administration

✔ Provider Telemetry Retention Detail View

✔ Provider-Specific Telemetry Trends

✔ Provider Intelligence Performance Policies

✔ Provider Performance Threshold Overlays

✔ Atlas Core Full-Suite Hang Remediation

✔ Foundry Dependency and Packaging Audit

✔ Foundry Release Documentation Audit

✔ Foundry Release Identifier Consistency

✔ Foundry Production Deployment Packaging

✔ Foundry Container Release Gates

✔ Foundry Release Candidate Audit

✔ Operator Credential Rotation Verified

260 Atlas Core tests collected.

36 Mission Control component tests passing.

---

# Current Sprint

Atlas Runtime Foundation

Active major milestone

- Define immutable defaults in `config/` and runtime state in `data/`
- Make runtime policy storage explicit with `ATLAS_POLICY_FILE`
- Preserve Provider Management Framework as the subsystem for provider resources and user intent
- Implement Discovery Center as the provider-neutral catalog and compatibility subsystem; design foundations remain in [docs/discovery-center](docs/discovery-center/ARCHITECTURE.md)
- Mission Control policy management for provider resources must write runtime state, not repository files
- Needs Review workflows for newly discovered resources remain derived, not persisted
- AI suggests intent changes; users decide and approve policy updates

Current behavior initializes `/opt/atlas/data/config/policies.yaml` from the tracked template and then treats runtime state as authoritative. Mission Control changes must not dirty the Git checkout.

---

# Repository

GitHub

vortex469/atlas-os

## Atlas v0.6 project status

Atlas v0.6.0 is the final release line for the completed Phase 3 candidate workflow. Atlas remains local-first, provider-neutral, and approval-gated.

Current supported capability:

- `update-compose-stack`

RC1 release boundary: candidate planning requires structured Compose mutation
evidence identifying the file, service, property, expected value where
available, desired value, operation, and preservation constraints before
approval. Legacy planning sessions without mutation evidence are safely
non-actionable and require successor planning or replanning. Exact approval
binding, durable persistence and recovery, stale/fingerprint rejection, and
successor idempotency/concurrency protections are validated.

Codex CLI installation, authentication provisioning, and ephemeral runtime
state are production-ready. Actual Codex-backed repository mutation is not
production-ready: the hardened Docker seccomp/AppArmor policy prevents
bubblewrap/Codex `workspace-write` sandbox initialization. Unconfined
profiles, `CAP_SYS_ADMIN`, root execution, and `danger-full-access` were
deliberately rejected. This work is deferred to **Codex Execution Sandbox
Hardening**.

Unsupported capabilities:

- `restart-service`
- `backup`
- `restore`
- `install-provider`
- `update-image`
- push
- tag
- release publication
- remote deployment
- rollback automation
- automatic approval
- automatic execution

Design principles: Core remains authoritative for candidate source state; Agent executes only exact immutable requests with exact approval; side-effect stages are restart-safe and at-most-once; audit links are machine-readable; Mission Control must not bypass Core or Agent trust boundaries.

## Atlas v0.7 project status

Atlas v0.7 is complete. The immutable final release `atlas-v0.7.0` resolves to
`8dbc43de73dda300b50c121f19324cb5174df2a9`; its immutable RC
`atlas-v0.7-rc1` resolves to
`5b1321091af0fc191844cdf71e9e0d919e4ea415`.

P1.3 completed one closed production capability:

- `restart-service / proxmox / qemu`

Core owns operator authentication, exact authoritative target resolution,
operator-intent persistence, the production dispatch ledger, the provider
handler, and read-only verification. Agent owns candidate planning, preparation
approval, immutable `OperationalActionRequest` translation, exact action
approval, authenticated dispatch, and terminal lifecycle projection. Mission
Control exposes login and sanitized maintenance-request views without accepting
commands, provider action IDs, native identities, endpoints, or arbitrary
parameters.

Production operator mutations require HTTPS, one exact trusted origin, CSRF,
and a Core-owned session carrying `operational_intent:create`. Agent-to-Core
authentication is a separate internal trust boundary. Proxmox access for this
capability is least-privilege: `VM.Audit` and `VM.PowerMgmt` scoped to the
approved VM target.

The 2026-08-14 normal-path production acceptance restarted approved VM 110
(`Frigate`) exactly once. Core recorded one durable barrier, one provider UPID,
one dispatch result, successful verification, and no replay. The final VM and
QMP states were running and the authoritative fingerprint was unchanged.

Still unsupported: `backup`, `restore`, `install-provider`, `update-image`,
push, tag/release publication, remote deployment, automated rollback, automatic
approval, and unrestricted operational actions.

## Atlas v0.8 project direction

The v0.8 theme is **Operational Control Plane Clarity and Observability**. It
makes the existing operational capability understandable, auditable,
recoverable, and safely extensible without widening the mutation boundary.
Work proceeds through P0 roadmap reconciliation, P1 effect-aware workflow and
approval clarity, P2 a unified read-only lifecycle model, P3 Mission Control
history and recovery UX, P4 provider-neutral read-only capability and selector
descriptors, and P5 deployment and security ergonomics.

V0.8 adds no execution intent or provider mutation handler. Repository change
execution remains separately gated as `update-compose-stack`; operational
execution remains exactly `restart-service / proxmox / qemu`, independently
allowed by the Agent and Core and backed by exactly one production handler.
