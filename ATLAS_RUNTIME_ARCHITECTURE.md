# Atlas Runtime Architecture

Atlas Runtime Foundation defines the boundary between immutable shipped defaults and mutable operator-owned runtime state. This document specializes in that storage boundary; the current component and deployment topology remains in [ARCHITECTURE.md](ARCHITECTURE.md), and operational procedures remain in [Production Deployment](docs/DEPLOYMENT.md).

## 1. Immutable defaults

Tracked files under `config/`, the curated Discovery catalog, accepted image-release evidence, and other reviewed repository knowledge are shipped defaults. Production mounts these inputs read-only. An upgrade may replace them, but it must not overwrite operator-owned runtime state.

Accepted image evidence is checked-in, immutable knowledge admitted through review. `CURATED` and verified `REGISTRY_ATTESTED` assertions retain their provenance and trust class. They are informational and grant no approval, dispatch, deployment, update, or rollback authority.

## 2. Mutable runtime state

`data/` contains state Atlas or an operator changes at runtime. The principal layout is:

```text
data/
  config/       operator-owned runtime configuration
  databases/    authoritative durable stores
  history/      durable history not held in a database
  cache/        rebuildable, non-authoritative projections
  knowledge/    future operator-owned knowledge stores
  backups/      operator-selected local backup output
```

Durable runtime stores can be authoritative for their declared domain. That rule does not make all mutable data authoritative: the dynamic Discovery cache is rebuildable evidence, can be discarded and reconstructed, and is excluded from backup format v3.

## 3. Bootstrap and policy files

Missing runtime configuration is initialized from validated tracked templates. Initialization creates only missing files, validates before serving, and must not overwrite an existing runtime file. Writes use narrow permissions, locking, validation, temporary files, `fsync`, and atomic replacement where applicable.

The tracked `config/policies.yaml` is the immutable bootstrap template. `ATLAS_POLICY_FILE` defaults to `/opt/atlas/data/config/policies.yaml`; policy domains that still use that file treat the initialized runtime copy as authoritative.

## 4. Provider Intent

Released v0.14 Provider Intent is explicitly activated through the production overlay and schema-v2 store. When activated, that store is authoritative only for identity-bound Proxmox QEMU `monitoring-policy`. Legacy Proxmox guest values in `policies.yaml` remain compatibility evidence, not competing authority.

Provider Intent mutation requires its dedicated operator permission. It does not own provider actions or infrastructure execution. A QEMU intent binds to provider-authoritative incarnation identity (`vmgenid`) and fails closed if a reused VMID identifies another incarnation. Atlas has no accepted LXC identity for this purpose and must not synthesize one.

Needs Review and status are derived from observed resource identity plus stored intent; they are not separate mutable authority.

## 5. Discovery runtime evidence

The curated catalog remains authoritative. Dynamic Frigate evidence is stored in a rebuildable cache with explicit freshness, health, conflict, and provenance semantics. Dynamic facts supplement but never silently replace curated facts. Compatibility, installed-version evidence, release evaluation, proposals, Compose observation, image grounding, and provenance are read-only derivations and add no operational authority.

Private and community catalogs are future work. If introduced, they require explicit trust, provenance, validation, migration, and backup decisions; they must not be inferred from the current dynamic cache.

## 6. Operational dispatch ledger

`operational_dispatch.db` is durable safety and audit state for the hardened operational path. It records request identity and lifecycle evidence needed to preserve exact approval, reconciliation, and no-replay behavior for the sole released tuple `restart-service / proxmox / qemu`.

The ledger is not a queue whose rows authorize replay. An interrupted or uncertain dispatch is recovered conservatively and is never automatically relaunched. Legacy provider-action history is a separate surface, and repository execution remains exactly `update-compose-stack` through Atlas Agent.

## 7. Backup and restore

Backup format v3 covers the documented durable Core state and runtime configuration, including Provider Intent and operational-dispatch safety state. It excludes rebuildable Discovery cache data. Older supported formats are validated through explicit compatibility rules rather than assumed to contain newer stores.

Restore is operator maintenance tooling, not an Agent execution intent. Restore validates the archive and target state, preserves ownership and atomicity, coordinates the runtime interlock, and invalidates existing operator sessions so pre-restore authentication state cannot survive the restored control-plane boundary. Atlas must not resume normal operation from partially restored or unvalidated state.

## 8. Upgrade, rollback, and migration rules

Shipped defaults may change on upgrade; existing operator-owned state remains authoritative for its declared domain. Migrations must be versioned, validated before and after mutation, auditable, explicit about unsupported data, and reversible where practical. Unknown configuration must be preserved when safe or rejected before loss.

Rollback and restore are explicit operator procedures. Atlas does not automatically deploy, roll back, remediate, update, approve, or publish a release.

## 9. Container mount and security model

Production follows the repository-owned Compose deployment path and keeps write access narrow:

```text
/opt/atlas/config       read-only templates and defaults
/opt/atlas/inventory    read-only inventory
/opt/atlas/data         read-write runtime state
```

Containers remain non-root where specified, use read-only root filesystems, and receive only documented writable mounts. Normal Mission Control configuration must not require a writable repository bind mount. Secrets belong in protected runtime inputs, never tracked defaults or backup metadata not designed to contain them.

## 10. Product rule

Normal operator changes through Mission Control write the authoritative runtime store for that domain and do not dirty the Git checkout. Advanced operators may still review templates and use documented maintenance tooling, but immutable defaults and mutable runtime state must remain visibly distinct.
