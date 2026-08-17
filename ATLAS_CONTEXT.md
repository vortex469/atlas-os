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

Current behavior reads operational policy from runtime state in `data/config/policies.yaml` when available. For Proxmox monitoring, those YAML guest values are retained legacy evidence only; the activated schema-v2 Provider Intent Store is authoritative. Tracked `config/` files are treated as immutable bootstrap templates. The Atlas Runtime Foundation boundary is:

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

- Identity-bound Proxmox QEMU monitoring expectations from Provider Intent;
  retained YAML guest values are non-authoritative legacy evidence
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

Atlas v0.11 — Provider Management Framework — Identity-Bound Runtime Intent

V0.11 release acceptance is complete. The exact evidence-bound implementation
SHA is `f8b2c8a202ca1c7316361e0c6b0ba72ee83eb9e2`; no V0.11 implementation
milestone remains. Production Provider Intent authority is active on schema v2.
QEMU 110 / Frigate and QEMU 200 / pbs each have an explicit identity-bound
`running` monitoring expectation. Public provider-management-v2 is canonical
for monitoring and identity presentation; authenticated v3 supplies only
caller-specific edit readiness.

P5 advisory suggestions remain non-authoritative and explicit-review only:
Review and Save require a fresh authenticated operator decision, and no
suggestion automatically mutates intent or causes remediation. Monitoring,
advisory diagnostics, compatibility actions, and operational maintenance remain
distinct authority surfaces. V0.11 added no execution capability: operational
execution remains exactly `restart-service/proxmox/qemu`, and repository
execution remains `update-compose-stack`.

Current behavior initializes `/opt/atlas/data/config/policies.yaml` from the
tracked template. Runtime YAML remains authoritative for policy domains that
still use it, but Proxmox guest YAML is compatibility/history evidence rather
than current monitoring authority. Mission Control changes must not dirty the
Git checkout.

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

## Atlas v0.8 RC1 validation

The v0.8 theme is **Operational Control Plane Clarity and Observability**. It
makes the existing operational capability understandable, auditable,
recoverable, and safely extensible without widening the mutation boundary.
P0 roadmap reconciliation, P1 effect-aware workflow and approval clarity, P2 a
unified read-only lifecycle model, P3 Mission Control history and recovery UX,
P4 provider-neutral read-only capability and selector descriptors, and P5
deployment and security ergonomics are complete. The immutable
`atlas-v0.8-rc1` candidate at
`cf09dfe1eebbd138d37ba7144d91b893f70732fa` passed Quality gates run
`31856384892`, Container release gate run `31856384891`, exact-SHA production
deployment, source/image parity, and sequential service-restart soak
validation. The completed operational workflow remained terminal, verified,
and lifecycle-consistent without replay. The final `atlas-v0.8.0` release was
published at `f83cd90982d4682ce49e60308e93dc9840984211`.

V0.8 adds no execution intent or provider mutation handler. Repository change
execution remains separately gated as `update-compose-stack`; operational
execution remains exactly `restart-service / proxmox / qemu`, independently
allowed by the Agent and Core and backed by exactly one production handler.

## Atlas v0.9 scope

Atlas v0.9 has the theme **Operational Recovery and Evidence Automation**. Its
objective is to make the existing durable operational lifecycle easier to
diagnose, recover, support, and release safely without adding provider mutation
capability. Production remains exactly `restart-service / proxmox / qemu`.

The read-only LXC feasibility investigation completed successfully with a
NO-GO: Atlas-visible Proxmox APIs expose no provider-authoritative,
configuration-independent LXC incarnation identity comparable to QEMU
`vmgenid`. Node/VMID, configuration digest, rootfs naming, MAC values, and task
history are mutable, reusable, or not bound to the current incarnation. Atlas
will not synthesize an identity from them. LXC remains unsupported and
non-requestable, and the former tuple-expansion P2–P5 do not proceed for LXC.
It may be reconsidered only if a provider-authoritative identity source is
independently demonstrated.

V0.9-P0 through V0.9-P5 are complete. The implemented scope is a strictly
read-only recovery diagnostic derived from existing lifecycle/ledger facts, a
bounded sanitized local support bundle, check-only release-evidence automation,
and Mission Control recovery/history UX. None adds a provider call,
reconciliation write, mutation endpoint, handler, gate change, upload
destination, or synthetic LXC identity. V0.9-P5 release acceptance and
documentation is complete. The immutable `atlas-v0.9-rc1` candidate at
`bc549ff6ab57d366205c1b9eb0c36fc2f7a61ba3` passed required CI,
`atlas-release-evidence-v1`, exact-SHA no-cache production deployment,
source/image parity, and sequential Agent/Core/Mission Control/Edge restart
soak. The accepted workflow and exactly-once ledger evidence remained
unchanged. The final `atlas-v0.9.0` release was published at
`7a5beac58e1677cd97b9bcc2f160dc30573582aa`; final Quality gates run
`31861408265` and Container release gate run `31861408264` passed.

## Atlas v0.10 scope

Atlas v0.10 has the theme **Discovery-to-Operator Proposal Handoff**. Atlas
Core's Discovery/intelligence layer derives, rather than persists, sanitized and
stale-aware advisory proposals from trusted catalog, provenance, finding, and
compatibility evidence. D9 is navigation-only: proposals cannot create a
candidate or action request, approve, dispatch, select an authoritative target,
assert its fingerprint, supply provider actions or arbitrary parameters, or
bypass operator authentication and existing capability/selector boundaries.

At any authoritative destination, Atlas freshly reloads current capability
descriptors, the authoritative resource selector, target state and fingerprint,
and operator permission. Proposal identity binds versioned catalog provenance,
source finding and compatibility evidence, closed hints, and destination while
excluding display and timestamp/UI state. Expired or source-mismatched proposals
remain inspectable but non-actionable. Compatibility is evidence, not execution
permission. V0.10 adds no execution intent or handler; production remains
exactly `restart-service / proxmox / qemu`, repository execution remains
`update-compose-stack`, and LXC remains unsupported.

V0.10-P0 through V0.10-P5 implementation and acceptance are complete.
Core exposes bounded GET-only proposal reads; Mission Control presents
sanitized proposal, provenance, compatibility, and stale-state context while
using closed navigation only. Maintenance selection independently reloads the
operator session and permission, production capability descriptor,
authoritative selector, current state/requestability, and target fingerprint.
Proposal observations are bounded and process-local; no durable schema or
Agent state changed. The immutable `atlas-v0.10-rc1` tag (tag object
`1c8798472ce46b2aa1fc822c1613a720c62113c4`) peels to exact RC SHA
`95d98a4d5e0e9767dd6cb5df06c7ffdb693bf162`. Exact-SHA CI,
`atlas-release-evidence-v1`, hardened no-cache production deployment,
source/image parity, proposal non-authority acceptance, and sequential service
restart soak passed. The existing workflow remained terminal and verified,
exactly-once and VM reboot counts were unchanged, and production capability
remained exactly `restart-service/proxmox/qemu`. The immutable
`atlas-v0.10.0` release was published at
`b19ded149f65dfb4043a1b80833e5ff64d83e55d`.

## Atlas v0.11 scope

Provider intent is durable control-plane monitoring/policy state, not
infrastructure execution. Provider actions remain the existing legacy/generic
subsystem and are not equivalent to hardened operational dispatch; v0.11 does
not expand them. Operational production execution remains exactly
`restart-service / proxmox / qemu`; repository execution remains
`update-compose-stack`.

For identity-capable resources, intent must bind to provider-authoritative
incarnation identity rather than reusable coordinates. A reused Proxmox QEMU
VMID must not inherit intent when its authoritative identity changes. LXC has
no accepted authoritative incarnation identity, remains unsupported for
operational execution, and receives no synthetic identity. Discovery proposals
remain sanitized, advisory, non-authoritative, and incapable of directly
creating policy or execution authority.
