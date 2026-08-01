# Atlas Runtime Architecture

Atlas Runtime Foundation defines the boundary between immutable shipped defaults and mutable user-owned runtime state. It is the storage and configuration foundation for the Provider Management Framework and future Mission Control features.

This document describes the intended architecture. Some current Foundry behavior still reads operational policy from `config/policies.yaml`; runtime policy implementation will follow this architecture in a later change.

## 1. Immutable defaults

`config/` contains shipped templates and factory defaults.

Examples include:

- `config/atlas.yaml`
- `config/policies.yaml`
- provider and operator-facing template files added in future releases

Rules:

- Files in `config/` are read-only in production.
- Defaults may be replaced by an Atlas upgrade.
- Defaults must never overwrite user-owned runtime state.
- Defaults are suitable for review, bootstrapping, and advanced operator automation.
- Normal Mission Control writes must not modify files in `config/`.

The tracked repository copy is an immutable source of defaults, not the normal write target for user intent.

## 2. Runtime state

`data/` contains everything Atlas learns or the user changes.

Recommended structure:

```text
data/
  config/
  databases/
  history/
  cache/
  knowledge/
  backups/
```

Intended ownership:

- `data/config/` stores user-owned runtime configuration initialized from templates.
- `data/databases/` stores SQLite databases and other durable data stores.
- `data/history/` stores audit, action, event, and timeline history when not database-backed.
- `data/cache/` stores rebuildable provider discovery caches and transient indexes.
- `data/knowledge/` stores local knowledge, learned preferences, and future AI memory stores.
- `data/backups/` stores local backups when the operator chooses an in-repository backup location.

Runtime state is persistent, user-owned, and authoritative once initialized.

## 3. Runtime configuration initialization

On first startup, Atlas initializes missing runtime files from tracked templates.

Rules:

1. Validate the template before copying it.
2. Create only missing runtime files.
3. Never overwrite an existing runtime file.
4. Use atomic creation where possible.
5. Validate the runtime file before serving it.
6. Fail safely with diagnostics when a template or runtime file is invalid.

Initialization is a bootstrap operation, not an upgrade overwrite mechanism.

## 4. Runtime policy storage

Operational policy must move from tracked defaults to runtime state.

Template path:

```text
/opt/atlas/config/policies.yaml
```

Runtime path:

```text
/opt/atlas/data/config/policies.yaml
```

Environment variables:

```text
ATLAS_POLICY_FILE=/opt/atlas/data/config/policies.yaml
ATLAS_POLICY_TEMPLATE_FILE=/opt/atlas/config/policies.yaml
```

The runtime policy file is the authoritative policy source after initialization. Mission Control and API writes update only the runtime policy file.

The template remains read-only and may be updated by future Atlas releases. Atlas must not silently replace the runtime policy file when the template changes.

## 5. Configuration Store

Atlas needs a configuration store pattern that separates generic product flows from provider-specific persistence details.

Rules:

- Provider-specific persistence remains behind generic service interfaces.
- Mission Control writes runtime state, not repository files.
- Provider adapters map native provider resources into generic Atlas resource contracts.
- Policy writers validate existing runtime state before writing updated runtime state.
- Writes must be atomic and auditable.
- Needs Review remains derived and is not persisted.

Provider Management Framework is a subsystem of Atlas Runtime Foundation. Runtime Foundation defines where user-owned state lives; Provider Management Framework defines how providers expose resources, expectations, actions, and diagnostics through Mission Control.

## 6. Upgrade rules

New images may ship new defaults.

Existing runtime files remain authoritative.

Future migrations must be:

- versioned;
- validated before and after mutation;
- reversible when practical;
- auditable;
- explicit about unsupported or unknown configuration.

Atlas must not silently discard unsupported user configuration. If a runtime file contains fields a new version does not understand, Atlas should preserve them when possible or stop with clear diagnostics before data loss.

## 7. Backup and restore

Runtime configuration must be backed up with Atlas data.

Rules:

- Runtime policy files under `data/config/` are part of durable Atlas state.
- Backups must include runtime configuration, not only databases.
- Restore must preserve ownership, permissions, validation, and atomicity.
- Restored runtime files must be validated before Atlas resumes normal operation.
- Existing version-1 database-only backups need backward compatibility.

A restore from an older backup may not contain runtime policy files. Atlas must handle that case by using the same safe initialization rules used by fresh installations.

## 8. Security model

Container hardening remains a core requirement.

Rules:

- Containers remain non-root.
- Root filesystems remain read-only.
- Only explicit runtime directories are writable.
- Templates, inventory, and source configuration stay read-only.
- Runtime write paths must be narrow and documented.
- Policy writes must keep existing file locking, temp-file writes, validation, fsync, and atomic replace behavior.
- Secrets must eventually use a dedicated protected runtime store.

Runtime writeability is not a reason to weaken the whole container. It should be scoped to `/opt/atlas/data` or a more specific runtime mount.

## 9. Container mount model

Production containers should follow this model:

```text
/opt/atlas/config     read-only templates and defaults
/opt/atlas/inventory  read-only inventory until a runtime inventory store exists
/opt/atlas/data       read-write persistent runtime state
```

Runtime paths should be explicitly configured through environment variables or settings. Normal configuration must not require a writable repository bind mount.

There must be no writable repository bind mount for normal Mission Control configuration.

## 10. Future stores

Atlas Runtime Foundation should support future stores without changing the immutable-defaults boundary.

Planned stores:

- Provider Connection Store
- Intent Store
- Discovery Store
- Notification Store
- User Settings Store
- AI preference and learned-intent storage

These stores may be files, SQLite databases, or another local durable backend. Regardless of storage engine, they belong under runtime state and must be covered by backup, restore, validation, and migration rules.

## 11. Product rule

Nothing a normal user changes through Mission Control should dirty the Git checkout.

Advanced operators may still edit files deliberately, review templates, and automate configuration. Normal users should express intent through Mission Control, and Atlas should persist that intent in runtime state.
