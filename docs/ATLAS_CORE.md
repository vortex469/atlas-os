# Atlas Core

Atlas Core is the central API for Atlas OS.

## Runtime

Atlas Core requires Python 3.12. Install the pinned runtime and test
dependencies from the repository:

```bash
cd services/atlas-core
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
```

Runtime-only environments may install `requirements.txt` instead.

Configuration is loaded from `config/atlas.yaml`,
`config/policies.yaml`, `inventory/services.yaml`, and optional
environment credentials. Use `.env.example` as the credential-name
reference and do not commit secrets.

## Address

- API: http://atlas-host:8643
- Documentation: http://atlas-host:8643/docs
- API discovery: http://atlas-host:8643/api/v1
- Health: http://atlas-host:8643/api/v1/health

Legacy unversioned routes remain available for existing integrations,
but new consumers should use `/api/v1`.

## Local development

```bash
cd services/atlas-core
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8643
```

Run the complete test suite with:

```bash
.venv/bin/pytest -q
```

## Service Management

The following commands assume an `atlas-core.service` unit has already
been installed by the operator:

Start:

    systemctl start atlas-core

Stop:

    systemctl stop atlas-core

Restart:

    systemctl restart atlas-core

Status:

    systemctl status atlas-core

Logs:

    journalctl -u atlas-core -f
