# Production Deployment

Atlas ships a two-service Docker Compose deployment:

- Atlas Core runs as a non-root Python process.
- Mission Control is built once and served by unprivileged Nginx, which
  proxies `/api/v1` to Atlas Core.

## Prerequisites

- Docker Engine with the Compose plugin
- Access to the infrastructure networks referenced by
  `inventory/services.yaml`
- A local `.env` containing the required base credentials and any
  credentials used by enabled providers

Copy and edit the example configuration before starting:

```bash
cp config/atlas.example.yaml config/atlas.yaml
cp .env.example .env
```

Do not commit `.env`. Review `config/policies.yaml` and
`inventory/services.yaml`; the repository values are examples and may
contain environment-specific addresses.

## Start Atlas

The Core container accesses the host Docker API through its socket. Set
`DOCKER_GID` to the numeric group that owns that socket:

```bash
DOCKER_GID="$(stat -c '%g' /var/run/docker.sock)" \
docker compose -f compose.production.yaml up --build -d
```

Mission Control is available on port `8080`. Override it with
`ATLAS_HTTP_PORT`, for example:

```bash
ATLAS_HTTP_PORT=8088 \
DOCKER_GID="$(stat -c '%g' /var/run/docker.sock)" \
docker compose -f compose.production.yaml up --build -d
```

Inspect health and logs:

```bash
docker compose -f compose.production.yaml ps
docker compose -f compose.production.yaml logs -f
```

Validate Compose without rendering secret values:

```bash
docker compose -f compose.production.yaml \
  config --no-env-resolution --quiet
```

Stop the services without deleting telemetry:

```bash
docker compose -f compose.production.yaml down
```

The `atlas-data` named volume contains action history and provider
intelligence telemetry. Deleting that volume permanently removes both
databases.

## Security notes

The Core container has access to the Docker socket, which is equivalent
to elevated control of the Docker host. Restrict access to Atlas,
Mission Control, and the host itself. Place TLS and authentication at a
trusted reverse proxy before exposing Mission Control beyond a private
network.

Configuration and inventory are mounted read-only. Containers use
read-only root filesystems, drop Linux capabilities, and disallow
privilege escalation. Provider secrets enter Core through an opaque
runtime env-file and are excluded from both Compose interpolation and
the image build context. Rotated application log files use ephemeral
memory; use the Compose `logs` command for durable host-side logging.
