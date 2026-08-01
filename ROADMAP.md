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
