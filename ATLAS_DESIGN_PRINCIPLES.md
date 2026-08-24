# Atlas Design Principles

Atlas is an intent-driven infrastructure operating system. It combines observed state with explicit operator intent while keeping evidence, recommendations, approvals, and execution as separate authorities. The runtime-state boundary is defined in [Atlas Runtime Architecture](ATLAS_RUNTIME_ARCHITECTURE.md); released topology and authority are summarized in [ARCHITECTURE.md](ARCHITECTURE.md).

## Enduring principles

### Intent over state

Observed state alone does not determine health. Atlas evaluates it against declared intent and explains the observed value, expected value, reason, and available next step.

### Discover before asking

Atlas should discover provider resources and relevant evidence before asking operators to encode normal inventory or policy. Unknown or unsupported evidence fails closed; it is not treated as success.

### Ask once and retain identity

New resources can enter Needs Review. Atlas records approved intent against authoritative identity where one exists so reusable provider coordinates do not silently transfer policy to a different resource incarnation.

### Mission Control for normal operation

Normal operators should use Mission Control rather than edit tracked YAML. Runtime mutations write narrow, validated operator-owned stores and do not dirty the checkout. Files remain useful for immutable defaults, advanced review, and documented maintenance.

### Evidence is not authority

Curated facts, dynamic observations, compatibility results, grounding, diagnostics, and AI suggestions must retain provenance and explain uncertainty. Evidence and recommendations do not grant approval or operational execution.

### Explicit authority and exact approval

Every mutation surface has a bounded contract and its own permission or approval rules. Approval for one surface never implies authority for another. Interrupted side effects fail conservatively and must not be replayed merely because work appears incomplete.

### Safe and explainable by default

Read-only discovery and explanation precede mutation. Warnings should show what Atlas observed, what it expected, why the finding exists, and which separately authorized actions are available.

### AI suggests; operators decide

AI may summarize evidence or suggest changes, but it never silently changes policy, approves work, or expands an allowed command, intent, target, or deployment boundary.

### Consistency without false equivalence

Providers should share understandable concepts—connection, resources, monitoring, actions, diagnostics, and history—while preserving provider-specific capabilities and authority. A uniform UI must not pretend unsupported behavior exists.

## Implemented through v0.14

- Provider Management presents provider and resource state, diagnostics, legacy provider actions, and history through typed Core APIs and Mission Control.
- Explicitly activated Provider Intent owns only identity-bound Proxmox QEMU `monitoring-policy`; it is no longer merely planned and does not authorize provider or operational actions.
- Discovery combines an authoritative curated catalog with dynamic evidence, freshness, health, conflicts, compatibility, proposals, release evaluation, Compose observation, accepted image evidence, grounding, and provenance. Its public surface is GET-only/read-only.
- Repository candidate execution is exactly `update-compose-stack`. Hardened operational dispatch is separately limited to `restart-service / proxmox / qemu`; legacy provider actions remain separate.
- Backup/restore v3 is explicit operator maintenance, invalidates operator sessions on restore, and preserves operational no-replay safety state while excluding rebuildable Discovery cache data.
- The production Agent backend is local. The packaged isolated worker path is default-disabled and requires separate activation and validation.

Atlas does not automatically approve, remediate, update, deploy, roll back, or publish releases.

## Future design direction

Provider consistency may broaden only as reviewed provider contracts support it. Semantic Discovery (D11), private/community catalogs (D12), richer AI assistance, broader automation, and additional orchestration remain future direction—not released behavior. Any future capability must preserve provenance, explicit authority, exact approval, no-replay safety, and the immutable-defaults/runtime-state boundary.
