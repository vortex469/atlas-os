# Atlas OS Roadmap

Atlas is in the Foundry development phase. Completed work is recorded in
`CHANGELOG.md`; this file describes direction rather than a release
promise. Product direction is guided by the
[Atlas Design Principles](ATLAS_DESIGN_PRINCIPLES.md) and the [Atlas Runtime Architecture](ATLAS_RUNTIME_ARCHITECTURE.md).

## Foundry release hardening

- Release documentation and configuration consistency
- Reproducible dependency installation and security review
- API, Mission Control, and packaging release gates
- Operational deployment guidance


## Atlas Runtime Foundation

Active major Atlas milestone.

- Define immutable defaults under `config/` and mutable runtime state under `data/`
- Keep shipped templates read-only in production
- Move normal Mission Control writes to runtime state so they must not dirty the Git checkout
- Initialize missing runtime configuration from validated templates without overwriting existing user state
- Make runtime policy storage explicit with `ATLAS_POLICY_FILE` and `ATLAS_POLICY_TEMPLATE_FILE`
- Include runtime configuration in backup and restore with backward compatibility for version-1 database-only backups

## Provider Management Framework

Runtime Foundation subsystem.

- Build an intent-driven Mission Control experience for provider management
- Discover provider resources automatically before asking users for policy
- Introduce Needs Review workflows for newly discovered resources
- Let users set monitoring intent without editing YAML
- Keep files available for advanced operators and automation
- Make provider pages consistent across connection, discovery, resources, monitoring, actions, and diagnostics
- Allow AI suggestions for intent changes while requiring user approval before policy updates

## Knowledge Engine

- Expand the application knowledge catalog
- Resource estimation
- Best-practice recommendations
- Cross-provider infrastructure relationships

## Discovery Center

Provider-neutral catalog and compatibility subsystem. D0 architecture and planning docs live in [docs/discovery-center](docs/discovery-center/ARCHITECTURE.md).

- Define structured local catalog knowledge for applications, services, container images, AI models, integrations, hardware devices, and deployment methods
- Keep curated YAML as the initial authoritative source
- Evaluate compatibility through deterministic, evidence-based checks before semantic or AI-based behavior
- Preserve the recommendation interface ownership boundary and keep execution control in Atlas Agent pathways
- Keep Discovery Center read-only by default

### Current implementation status

- ✅ Implemented: curated catalog models, loader, repository/search, read-only API, compatibility engine, and Orion-consumed compatibility findings in intelligence pipeline.
- ✅ Implemented: Mission Control discovery API client, typed contracts, and read-only Discovery Center UI pages for browsing catalog items and viewing item details with relationships, provenance, and compatibility evidence.
- 📌 Planned / Future: dynamic catalog sources, semantic discovery, Atlas Agent handoff protocol, community/private catalogs, and broader execution candidate affordances.

## Deployment Platform

- Approval workflows
- Provider-backed execution
- Rollback support
- Live deployment monitoring

## Conversational Infrastructure

- Orion Assistant *(Planned)*
- Guided troubleshooting
- Cross-provider reasoning
- Voice interaction
- Conversational operations

## Atlas v0.6 roadmap status

### Completed

- Phase 3 `update-compose-stack` candidate workflow through structured planning intake, deterministic Compose mutation evidence, workflow shell, immutable implementation request, exact approvals, persistence/recovery, concurrency protection, verification evidence, deterministic review, and commit-boundary validation, including Codex-backed repository mutation through the hardened execution sandbox.
- P3.14A hardening: deterministic end-to-end coverage, machine-readable audit-chain validation, restart and recovery matrix coverage, deterministic concurrency coverage, commit-path security hardening, strict caller-controlled request validation, API route-contract regression coverage, and roadmap workflow regression coverage.
- Codex execution sandbox hardening: named workspace permission profile,
  runsc-isolated worker, authenticated and network-segmented control plane, and
  disposable workspace/outside-workspace runtime proofs, followed by an
  authenticated end-to-end candidate execution through verification, review,
  and the pending commit-approval boundary.

### Planned

- v0.7+ carries the v0.6 deferrals for execution and release operations:
  - `restart-service`
  - `backup`
  - `restore`
  - `install-provider`
  - `update-image`
  - automated rollback, tag/release automation, and remote deploy automation.

#### Phase 4: new execution intents

Future execution intents such as `restart-service`, `backup`, `restore`, `install-provider`, and `update-image` require separate architecture, contracts, exact approvals, recovery behavior, security review, and end-to-end tests.

#### Phase 5: distributed orchestration

Distributed orchestration, clustering, cross-host recovery, and advanced provider execution require a persistence and coordination design beyond current local Agent state.

### Future ideas

Dynamic discovery sources, semantic search, Mission Control candidate controls, release workflows, and rollback automation remain future ideas. They are not part of v0.6.
