# Atlas Core

Atlas Core is the central Atlas OS API and control-plane service. It loads and normalizes provider and inventory state; evaluates policy, health, findings, and intelligence; owns operator sessions, Provider Intent, Discovery projections, and durable operational lifecycle state; and exposes typed API v1 contracts to Mission Control and Atlas Agent.

Provider Intent, when explicitly activated, is monitoring-policy authority only for identity-bound Proxmox QEMU resources. Discovery combines the curated catalog with dynamic read-only evidence and rebuildable cache projections. Core dispatches only the hardened operational tuple `restart-service / proxmox / qemu` across the Agent-facing boundary; legacy provider actions remain separate. `operational_dispatch.db` preserves durable safety/audit and no-replay state.

Backup/restore format v3 is operator maintenance tooling over documented durable state. Restore invalidates existing operator sessions, and rebuildable Discovery cache data is not backup authority. Backup/restore is not an Agent execution intent.

For the v0.15 provisional closure candidate, Core also exposes the implemented
GET-only, bounded, read-only
`/api/v1/discovery/items/{item_id}/image-grounding` projection. It preserves
grounded and fail-closed statuses, returns sanitized 404/503 errors, performs no
acquisition or mutation, and grants no deployment or execution authority. P0
through P4 are complete; P5 exact-SHA release validation is in progress, and
v0.15 is not yet released.

## Runtime and local development

Atlas Core requires Python 3.12. Install the pinned development dependencies and run it locally with:

```bash
cd services/atlas-core
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8643
```

Runtime-only environments may install `requirements.txt`. Configuration comes from `config/atlas.yaml`, `inventory/services.yaml`, optional environment credentials, and `ATLAS_POLICY_FILE` (default `/opt/atlas/data/config/policies.yaml`). `config/policies.yaml` is the immutable bootstrap template. Use `.env.example` only as the credential-name reference; do not commit secrets.

Run Core tests with:

```bash
.venv/bin/pytest -q
```

## Addresses

- API: `http://atlas-host:8643`
- API documentation: `http://atlas-host:8643/docs`
- API discovery: `http://atlas-host:8643/api/v1`
- Health: `http://atlas-host:8643/api/v1/health`

Legacy unversioned routes remain for compatible integrations; new consumers should use `/api/v1`.

## Production boundary

Repository-owned production deployment is defined by `compose.production.yaml` and its documented overlays. Follow [Production Deployment](DEPLOYMENT.md) for prerequisites, activation, validation, backup, restore, and operating procedures. An operator may create host-specific service-manager wrappers, but such units are not repository-owned production deployment authority and are not a substitute for the canonical Compose path.
