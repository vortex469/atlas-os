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

Atlas treats files under `config/` as immutable defaults in production.
`config/policies.yaml` is mounted read-only as the shipped policy
template. On first use, Atlas validates that template and initializes the
runtime policy at `/opt/atlas/data/config/policies.yaml` inside the
`atlas-data` volume. Mission Control and API policy writes update the
runtime policy only, so normal user changes do not dirty the Git
checkout. Existing runtime policy files are never overwritten by a new
template during startup.

The production Compose file sets the runtime policy paths explicitly:

```dotenv
ATLAS_POLICY_FILE=/opt/atlas/data/config/policies.yaml
ATLAS_POLICY_TEMPLATE_FILE=/opt/atlas/config/policies.yaml
```

Operators may override those paths for custom deployments, but the
runtime path must be writable by the non-root Atlas Core user and the
template path should remain read-only.

Provider connection settings follow the same runtime-state boundary. The
tracked `config/atlas.yaml`, `inventory/services.yaml`, and environment
variables remain legacy fallback sources. Mission Control writes provider
connection changes to runtime files in the `atlas-data` volume only:

```dotenv
ATLAS_PROVIDER_CONNECTION_FILE=/opt/atlas/data/config/provider-connections.yaml
ATLAS_PROVIDER_CONNECTION_TEMPLATE_FILE=/opt/atlas/config/provider-connections.yaml
ATLAS_PROVIDER_SECRET_FILE=/opt/atlas/data/secrets/provider-connections.yaml
```

The non-secret provider connection store initializes as an empty validated
version-1 document when no read-only template exists. Atlas never needs a
writable bind mount for `config/atlas.yaml` or `inventory/services.yaml`.
Runtime connection values override legacy config field-by-field, so omitted
runtime values continue to fall back to shipped configuration and inventory.
Provider secrets are stored separately under
`/opt/atlas/data/secrets/provider-connections.yaml`, owned by the Atlas Core
UID/GID `10001:10001` and mode `0600`. Secret values override environment
secrets individually, are never returned by the API, and are not mounted into
Atlas Agent. Docker is modeled as a privileged local Unix-socket connection;
Mission Control may display its socket path and diagnostics, but the socket
path is not editable in this phase.

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

Validate Compose without rendering secret values. A clean checkout has no
`.env`; use the tracked `.env.example` only for Compose render validation:

```bash
ATLAS_ENV_FILE=.env.example \
ATLAS_REPOSITORY_HOST_PATH="$PWD" \
docker compose -f compose.production.yaml config --quiet
```

For HTTPS mode, include `-f compose.https.yaml` and set the three
required credential-file variables:

```bash
ATLAS_ENV_FILE=.env.example \
ATLAS_REPOSITORY_HOST_PATH="$PWD" \
ATLAS_TLS_CERT_FILE=/path/to/atlas.crt \
ATLAS_TLS_KEY_FILE=/path/to/atlas.key \
ATLAS_HTPASSWD_FILE=/path/to/atlas.htpasswd \
docker compose \
  -f compose.production.yaml \
  -f compose.https.yaml \
  config --quiet
```

`.env.example` contains placeholder values suitable for render validation
only. Real production deployments still require a real `.env` or an
operator-selected `ATLAS_ENV_FILE` containing valid credentials.

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

The `atlas-data` named volume contains action history, provider
intelligence telemetry, and runtime policy state under
`/opt/atlas/data/config/policies.yaml`. It also contains provider connection
runtime state under `/opt/atlas/data/config/provider-connections.yaml` and
provider connection secrets under
`/opt/atlas/data/secrets/provider-connections.yaml`. Deleting that volume
permanently removes databases, user-owned runtime policy changes, provider
connection overrides, and provider connection secrets. The tracked
`config/policies.yaml`, `config/atlas.yaml`, and `inventory/services.yaml`
files remain immutable defaults or legacy fallback sources.

## Atlas v0.6 RC upgrade and manual rollback

Atlas v0.6 operations are upgraded and rolled back manually. V0.6 does not
implement automatic rollback.

### Upgrade sequence

1. Before upgrading, create an online backup:

```bash
./scripts/atlas-data-backup
```

2. Stop the existing compose services:

```bash
docker compose -f compose.production.yaml down
```

Include `-f compose.https.yaml` when stopping an HTTPS deployment.

3. Check out the target Atlas tag/commit for the upgrade and ensure deployment
artifacts are current.

4. Update and start services with the supported deploy commands:

```bash
docker compose -f compose.production.yaml pull
ATLAS_REPOSITORY_HOST_PATH="$PWD" DOCKER_GID="$(stat -c '%g' /var/run/docker.sock)" docker compose -f compose.production.yaml up --build -d
```

For HTTPS, include `-f compose.https.yaml` and set certificate variables as
described above.

### Post-upgrade verification

After upgrade and before routing traffic:

```bash
docker compose -f compose.production.yaml ps
docker compose -f compose.production.yaml logs -f
./scripts/container-release-gate
```

Validate one end-to-end planning intake path for update-compose-stack candidates:

```bash
CORE_URL="${CORE_URL:-http://localhost/api/v1}"
AGENT_URL="${AGENT_URL:-http://localhost/agent-api}"

candidate_id=$(curl -sfS "$CORE_URL/execution-candidates?status=eligible&intent=update-compose-stack&limit=1" \
  | jq -r '.candidates[0].id // empty')

if [ -z "$candidate_id" ] || [ "$candidate_id" = "null" ]; then
  echo "No eligible update-compose-stack execution candidates found"
  exit 0
fi

intake=$(curl -sfS -X POST "$CORE_URL/execution-candidates/$candidate_id/planning-intake" \
  -H 'Content-Type: application/json' \
  -d '{}')

fingerprint=$(echo "$intake" | jq -r '.current_candidate_fingerprint // empty')
status=$(echo "$intake" | jq -r '.status')

if [ "$status" != "accepted_for_planning" ]; then
  echo "Planning intake rejected: $intake"
  exit 1
fi

session=$(curl -sfS -X POST "$AGENT_URL/candidate-planning" \
  -H 'Content-Type: application/json' \
  -d '{"candidate_id":"'"$candidate_id"'","expected_candidate_fingerprint":"'"$fingerprint"'"}')

echo "$session" | jq '.session_id, .status, .planning_allowed'
```

Confirm `atlas-data` remains preserved and runtime config paths remain under
`/opt/atlas/data` (including policy and provider-connection files).

### Manual rollback triggers

Rollback manually when any of these occur after upgrade:

- `./scripts/container-release-gate` fails.
- service health or startup regresses after upgrade.
- backup restore checks fail or manifest verification cannot be confirmed.
- runtime migration or startup behavior is not safe for operation.

### Rollback to prior known tag or image

Rollback by stopping current services and checking out the prior known tag/image:

```bash
docker compose -f compose.production.yaml down
git checkout <prior_atlas_tag_or_commit>
ATLAS_REPOSITORY_HOST_PATH="$PWD" DOCKER_GID="$(stat -c '%g' /var/run/docker.sock)" docker compose -f compose.production.yaml up --build -d
```

### Atlas data rollback restore sequence

If upgrade impacted durable state or runtime configuration, restore from backup:

```bash
docker compose -f compose.production.yaml down
./scripts/atlas-data-restore /path/to/backups/atlas-data-YYYYMMDDTHHMMSSZ --confirm
ATLAS_REPOSITORY_HOST_PATH="$PWD" DOCKER_GID="$(stat -c '%g' /var/run/docker.sock)" docker compose -f compose.production.yaml up --build -d
```

Use existing backup directories from `./scripts/atlas-data-backup`.

### Post-rollback smoke checks

After rollback and restart, run:

```bash
docker compose -f compose.production.yaml ps
docker compose -f compose.production.yaml logs -f
./scripts/container-release-gate
```

## Back up and restore data

Create a consistent online backup while Atlas remains available:

```bash
./scripts/atlas-data-backup
```

Backups default to timestamped directories beneath `backups/`. Pass a
different parent directory as the first argument to store them on
separate media:

```bash
./scripts/atlas-data-backup /mnt/atlas-backups
```

Each backup contains both SQLite databases, runtime policy files such as
`config/policies.yaml`, provider connection overrides such as
`config/provider-connections.yaml`, provider connection secrets such as
`secrets/provider-connections.yaml`, and a versioned `manifest.json` with
separate database and runtime file entries, sizes, modes, and SHA-256
checksums. The command uses SQLite's online backup API for databases, so
WAL-mode writes can continue without producing an inconsistent database
copy. Runtime file entries are verified by safe relative path, checksum,
expected file set, and store-specific structure. Existing version-1
database-only backups, and backups created before provider connection
stores existed, remain restorable.

Runtime policy files are owned by the Atlas container user and may be
mode `0600`. The backup command therefore reads the Atlas data volume
from a disposable helper running as the Atlas UID `10001`, with no
network, a read-only root filesystem, all capabilities dropped,
`no-new-privileges`, no Docker socket, the Atlas data volume mounted
read-only, and only the incomplete backup destination mounted writable.
Before the incomplete backup is renamed into place, a second disposable
ownership helper mounts only that incomplete backup directory and uses
only the `CHOWN` capability to set the backup directory and files back to
the invoking host UID/GID and keeps them readable by the Atlas restore
UID. Operators can then read, move, and remove the artifacts normally
without weakening live runtime permissions. Backup directories that
include `secrets/provider-connections.yaml` contain provider credentials
and must be protected like any other secret-bearing backup artifact.

Restore replaces both databases, restores included runtime files
atomically under the Atlas data root, and removes stale WAL and shared
memory sidecars. Stop every container using the volume first:

```bash
docker compose -f compose.production.yaml down
./scripts/atlas-data-restore \
  /mnt/atlas-backups/atlas-data-YYYYMMDDTHHMMSSZ \
  --confirm
docker compose -f compose.production.yaml up -d
```

Include `-f compose.https.yaml` in the `down` and `up` commands for an
HTTPS deployment. The restore command refuses to run while a container
uses the target volume, validates the manifest, checks every checksum,
rejects unsafe runtime file paths, and runs SQLite integrity checks before
replacing live database files. Version-1 database-only backups remain
valid; they simply do not restore runtime policy or provider connection
files, allowing Atlas to initialize missing runtime policy from the
read-only template and missing provider connection stores from immutable
templates or empty validated stores on next startup. Set
`ATLAS_DATA_VOLUME` only when the Compose project uses a non-default
volume name. Restore runs as the Atlas data UID, default `10001`, so
restored runtime files remain Atlas-owned. Runtime policy and provider
secret files keep mode `0600`.

### Schedule backups

Atlas includes an optional systemd timer that runs an online backup every
day at 02:15 UTC with up to 30 minutes of randomized delay. Persistent
scheduling runs a missed backup after the host returns.

Review the configuration before installation:

```bash
sudo mkdir -p /etc/atlas
sudo cp deploy/systemd/backup.env.example /etc/atlas/backup.env
sudo editor /etc/atlas/backup.env
sudo ./scripts/install-backup-timer
```

The default policy stores backups in `/opt/atlas/backups`, expires
verified backups older than 30 days, and always preserves at least the
seven newest backups. Retention ignores unrelated directories and aborts
instead of deleting a backup whose manifest, checksum, or SQLite
integrity check fails.

Inspect the schedule and recent result:

```bash
systemctl list-timers atlas-data-backup.timer
systemctl status atlas-data-backup.service
journalctl -u atlas-data-backup.service
```

Backups on `/opt/atlas/backups` share the same ZFS storage as the live
volume on a default installation. They protect against application-level
damage and accidental database loss, but not host or storage-pool loss.
For disaster recovery, replicate them to a physically separate host.

### Replicate to Rest Server

Atlas includes a pinned Restic client and a hardened Rest Server Compose
deployment. Restic encrypts backup contents before upload. The server
requires authenticated TLS, isolates each username to its own path, and
runs append-only so credentials stolen from the Atlas host cannot modify
or delete existing snapshots.

Run Rest Server on a different Docker host with storage that does not
share Atlas's failure domain. On that host:

```bash
sudo install -d -o 10001 -g 10001 -m 0700 \
  /srv/atlas-restic \
  /etc/atlas-rest-server
sudo install -o 10001 -g 10001 -m 0644 server.crt \
  /etc/atlas-rest-server/server.crt
sudo install -o 10001 -g 10001 -m 0600 server.key \
  /etc/atlas-rest-server/server.key

sudo htpasswd -B -c /etc/atlas-rest-server/htpasswd atlas
sudo chown 10001:10001 /etc/atlas-rest-server/htpasswd
sudo chmod 600 /etc/atlas-rest-server/htpasswd

cp deploy/rest-server/server.env.example deploy/rest-server/server.env
editor deploy/rest-server/server.env
docker compose \
  --env-file deploy/rest-server/server.env \
  -f deploy/rest-server/compose.yaml \
  up -d
```

Use a certificate issued by a CA trusted by Atlas when possible. Bind only
to the backup host's private or VPN address and restrict port 8000 at its
firewall to the Atlas host. The `htpasswd` utility is provided by
`apache2-utils` on Debian/Ubuntu and `httpd-tools` on Fedora/RHEL.

On the Atlas host, create two independent random passwords: the transport
password stored in the server's htpasswd file and a repository encryption
password. Copy and edit the client environment:

```bash
sudo install -d -m 0750 /etc/atlas
sudo install -m 0600 \
  deploy/systemd/restic.env.example \
  /etc/atlas/restic.env
sudo editor /etc/atlas/restic.env
```

With `--private-repos`, the path in `RESTIC_REPOSITORY` must start with
the authenticated username. For username `atlas`, use a URL ending in
`/atlas` or `/atlas/<subrepository>`. If an internal CA is not in the
client's system trust store, install its public CA certificate:

```bash
sudo install -m 0644 internal-ca.pem /etc/atlas/restic-ca.pem
```

Initialize the encrypted repository exactly once, then perform and inspect
the first replication:

```bash
sudo ./scripts/atlas-data-replicate /opt/atlas/backups init
sudo ./scripts/atlas-data-replicate /opt/atlas/backups
journalctl -u atlas-data-backup.service
```

After `/etc/atlas/restic.env` exists, the regular backup service verifies
and uploads its newest local backup on every run. Without that file, it
logs a skip and local backups continue normally.

Append-only mode deliberately prevents client-side `forget` and `prune`.
Retention and repository maintenance must be performed directly on the
trusted Rest Server host during a controlled maintenance window. Keep a
separate offline copy of the repository password: losing it makes all
snapshots unrecoverable.

Run the isolated end-to-end recovery test with:

```bash
./scripts/rest-server-gate
```

It starts a temporary TLS Rest Server, initializes a repository, uploads a
verified Atlas backup, checks the repository, restores the latest
snapshot, compares the restored database, and removes all test data.

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
