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

Planned provider-neutral catalog and compatibility subsystem. D0 architecture and planning docs live in [docs/discovery-center](docs/discovery-center/ARCHITECTURE.md).

- Define structured local catalog knowledge for applications, services, container images, AI models, integrations, hardware devices, and deployment methods
- Keep curated YAML as the initial authoritative source
- Evaluate compatibility through deterministic, evidence-based checks before semantic or AI-based behavior
- Preserve Orion as the owner of recommendations and Atlas Agent as the future execution boundary
- Keep Discovery Center read-only by default

## Deployment Platform

- Approval workflows
- Provider-backed execution
- Rollback support
- Live deployment monitoring

## Conversational Infrastructure

- Orion Assistant
- Guided troubleshooting
- Cross-provider reasoning
- Voice interaction
- Conversational operations

## Atlas v0.6 roadmap status

### Completed

- Phase 3 functional candidate workflow from Discovery compatibility evidence through execution candidate, planning intake, Agent planning, workflow shell, immutable implementation request, exact approvals, execution, verification evidence, deterministic review, exact commit approval, local commit, and completed workflow.
- P3.14A hardening: deterministic end-to-end coverage, machine-readable audit-chain validation, restart and recovery matrix coverage, deterministic concurrency coverage, commit-path security hardening, strict caller-controlled request validation, API route-contract regression coverage, and roadmap workflow regression coverage.

### Planned

#### Phase 4: new execution intents

Future execution intents such as `restart-service`, `backup`, `restore`, `install-provider`, and `update-image` require separate architecture, contracts, exact approvals, recovery behavior, security review, and end-to-end tests.

#### Phase 5: distributed orchestration

Distributed orchestration, clustering, cross-host recovery, and advanced provider execution require a persistence and coordination design beyond current local Agent state.

### Future ideas

Dynamic discovery sources, semantic search, Mission Control candidate controls, release workflows, and rollback automation remain future ideas. They are not part of v0.6.
