# Production Deployment

Atlas ships a two-service Docker Compose deployment with two ingress
choices:

- Atlas Core runs as a non-root Python process.
- Mission Control is built once and served by unprivileged Nginx, which
  proxies `/api/v1` to Atlas Core.
- LAN HTTP publishes Mission Control on an operator-selected private
  address.
- Authenticated HTTPS adds a hardened Nginx edge container with an
  operator-supplied certificate and password file.

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

## Choose an ingress mode

The Core container accesses the host Docker API through its socket. Set
`DOCKER_GID` to the numeric group that owns that socket in either mode.

### Local or LAN HTTP

HTTP defaults to `127.0.0.1:8080`, which is reachable only from the
Docker host:

```bash
DOCKER_GID="$(stat -c '%g' /var/run/docker.sock)" \
docker compose -f compose.production.yaml up --build -d
```

To make Mission Control available on a trusted LAN, set
`ATLAS_HTTP_BIND` to the host's private address. Override the port with
`ATLAS_HTTP_PORT` when needed:

```bash
ATLAS_HTTP_BIND=10.10.50.60 \
ATLAS_HTTP_PORT=8080 \
DOCKER_GID="$(stat -c '%g' /var/run/docker.sock)" \
docker compose -f compose.production.yaml up --build -d
```

Do not use `0.0.0.0` unless every host interface is trusted or an
external firewall restricts access.

### Authenticated HTTPS

The HTTPS overlay keeps the direct HTTP listener on loopback and
publishes a TLS listener on port `443`. It requires:

- a certificate whose subject names include the Atlas hostname;
- the matching private key;
- an `htpasswd` file containing at least one authorized user.

Store these outside version control. The `secrets/` directory is ignored
for operators who keep them beside the Compose files:

```bash
mkdir -p secrets
chmod 700 secrets

atlas_password=
read -r -s -p "Atlas password: " atlas_password
printf '\n'
password_hash="$(
  printf '%s\n' "$atlas_password" | openssl passwd -apr1 -stdin
)"
unset atlas_password
printf 'atlas:%s\n' "$password_hash" >secrets/atlas.htpasswd
unset password_hash
chmod 600 secrets/atlas.htpasswd
```

Place the certificate and key at `secrets/atlas.crt` and
`secrets/atlas.key`. The edge container defaults to UID 101. Root-managed
hosts can make that UID the owner while keeping the key and password
database private:

```bash
sudo chown 101:101 \
  secrets/atlas.crt \
  secrets/atlas.key \
  secrets/atlas.htpasswd
sudo chmod 644 secrets/atlas.crt
sudo chmod 600 secrets/atlas.key secrets/atlas.htpasswd
```

Non-root operators can instead leave the files owned by their account and
set `ATLAS_EDGE_UID="$(id -u)"` when running Compose.

```bash
ATLAS_HTTP_BIND=127.0.0.1 \
ATLAS_HTTPS_BIND=0.0.0.0 \
ATLAS_EDGE_UID=101 \
ATLAS_TLS_CERT_FILE=./secrets/atlas.crt \
ATLAS_TLS_KEY_FILE=./secrets/atlas.key \
ATLAS_HTPASSWD_FILE=./secrets/atlas.htpasswd \
DOCKER_GID="$(stat -c '%g' /var/run/docker.sock)" \
docker compose \
  -f compose.production.yaml \
  -f compose.https.yaml \
  up --build -d
```

Set `ATLAS_HTTPS_PORT` to override port `443`. Certificate issuance and
renewal remain operator responsibilities; certificates from an internal
CA are suitable when every client trusts that CA.

## Operate Atlas

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

For HTTPS mode, include `-f compose.https.yaml` and set the three
required credential-file variables.

Run the complete container release gate:

```bash
./scripts/container-release-gate
```

The gate builds the images, starts an isolated stack on ephemeral HTTP
and HTTPS ports, verifies container hardening and health, checks the
UI/API proxy and SPA fallback, rejects unauthenticated HTTPS requests,
accepts authenticated requests, and removes its temporary containers,
network, volume, and credential files. The same command runs in GitHub
Actions.

Set `ATLAS_ENV_FILE` to use a credential file outside the repository for
normal deployments. It defaults to `.env`.

Stop the services without deleting telemetry:

```bash
docker compose -f compose.production.yaml down
```

Include `-f compose.https.yaml` when stopping an HTTPS deployment.

The `atlas-data` named volume contains action history and provider
intelligence telemetry. Deleting that volume permanently removes both
databases.

## Security notes

The Core container has access to the Docker socket, which is equivalent
to elevated control of the Docker host. Restrict access to Atlas,
Mission Control, and the host itself. Use authenticated HTTPS before
exposing Mission Control beyond a private network.

Configuration and inventory are mounted read-only. Containers use
read-only root filesystems, drop Linux capabilities, and disallow
privilege escalation. Provider secrets enter Core through an opaque
runtime env-file and are excluded from both Compose interpolation and
the image build context. Rotated application log files use ephemeral
memory; use the Compose `logs` command for durable host-side logging.
