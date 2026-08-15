# Production Deployment

Atlas ships a hardened Docker Compose deployment with private internal service
networks and two ingress choices:

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

### Atlas Agent RC1 deployment boundary

The RC1 candidate workflow supports only `update-compose-stack`. Candidate
planning must include structured Compose mutation evidence before an
implementation approval is created. Legacy planning sessions without that
evidence are safely non-actionable and require successor planning or
replanning.

The production Agent deployment requires:

- `ATLAS_REPOSITORY_HOST_PATH` set to the repository bind source;
- that repository source writable by runtime uid/gid `10001:10001`;
- `ATLAS_CODEX_AUTH_HOST_PATH` set to an external Codex auth file;
- the host auth file kept root-owned and mode `0600`; the one-shot
  `atlas-agent-auth-stager` service copies it into the dedicated staging
  volume with ownership `10001:10001` and mode `0600` before Agent startup;
- the runtime gate `./scripts/atlas-agent-codex-runtime-gate` run after
  deployment;
- a container rebuild after Atlas Agent source or image changes. Recreating
  an old container without rebuilding does not deploy new Agent code.

Codex CLI installation, authentication provisioning, and ephemeral `CODEX_HOME`
runtime state are validated. The Agent reaches the execution worker over
private TCP on `atlas-execution-worker-net`; port `8081` is not host-published.
The worker repository source is mounted read-only and execution occurs in a
disposable workspace. Codex-backed repository mutation uses the immutable
`atlas-workspace` permission profile inside a runsc-isolated worker. Agent
requests traverse an authenticated relay on a segmented transport network;
the worker control plane rejects direct non-relay peers. Do not replace this
boundary with unconfined seccomp/AppArmor, `CAP_SYS_ADMIN`, root execution, or
Codex `danger-full-access`.

RC1 smoke-test evidence includes correct stale/fingerprint and repository
freshness rejection, immutable blocked workflows, restart/container-recreation
persistence, deterministic successor lineage reuse, and validated Codex
authentication/runtime provisioning. Post-hardening evidence additionally
records successful Codex-backed mutation in a disposable workspace,
outside-workspace denial, exact verification and review, a valid audit chain,
and a pending commit approval that was intentionally not approved.

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

The HTTPS overlay removes Mission Control's inherited host HTTP publication and
publishes Atlas Edge as the only browser ingress on port `443`. Mission Control
port `8080` remains available only on the Compose network so Atlas Edge can
serve the SPA and proxy Agent/Core APIs. It requires:

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

### Core-owned operator authentication

Sensitive browser mutation boundaries are disabled in the base deployment.
Enable the Core-owned operator session boundary only with authenticated HTTPS
and the explicit `compose.operator-auth.yaml` overlay. Atlas Edge HTTP Basic
remains defense-in-depth; Core independently authenticates its own operator
session and never trusts a proxy identity header.

Provision a private verifier outside version control. The following command
prompts without echoing the password and writes the Argon2id verifier directly
to the file without printing the password or hash:

```bash
mkdir -p secrets
chmod 700 secrets
services/atlas-core/.venv/bin/python - <<'PY'
import getpass
import json
from pathlib import Path

from argon2 import PasswordHasher

password = getpass.getpass("Atlas operator password: ")
confirmation = getpass.getpass("Confirm Atlas operator password: ")
if password != confirmation or not password:
    raise SystemExit("Passwords did not match or were empty.")
payload = {
    "schema_version": 1,
    "operators": [{
        "operator_id": "atlas-operator",
        "password_hash": PasswordHasher().hash(password),
        "enabled": True,
        "permissions": ["operational_intent:create"],
    }],
}
path = Path("secrets/atlas-operators.json")
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
path.chmod(0o400)
PY
sudo chown 10001:10001 secrets/atlas-operators.json
sudo chmod 0400 secrets/atlas-operators.json
```

Start Atlas with one exact HTTPS origin; wildcard and HTTP origins are rejected:

```bash
ATLAS_HTTP_BIND=127.0.0.1 \
ATLAS_OPERATOR_AUTH_VERIFIER_HOST_PATH=./secrets/atlas-operators.json \
ATLAS_OPERATOR_AUTH_TRUSTED_ORIGINS=https://atlas.example.internal \
ATLAS_TLS_CERT_FILE=./secrets/atlas.crt \
ATLAS_TLS_KEY_FILE=./secrets/atlas.key \
ATLAS_HTPASSWD_FILE=./secrets/atlas.htpasswd \
docker compose \
  -f compose.production.yaml \
  -f compose.https.yaml \
  -f compose.operator-auth.yaml \
  up --build -d
```

The verifier must be a regular, non-symlink file owned by Core's runtime UID
10001 with mode `0400`. Core stores only opaque-session and CSRF digests in the
private `atlas-data` volume. In this three-file deployment the browser path is
always `browser -> Atlas Edge HTTPS -> Mission Control -> Agent/Core`; there is
no direct Mission Control host listener. Base production without the HTTPS
overlay retains loopback HTTP for local compatibility.

Expired sessions, failed CSRF rotation, missing permission, and Core
unavailability fail closed in Mission Control. Reauthentication returns the
operator to the originally requested maintenance or history page. Atlas does
not store passwords, cookies, CSRF values, or bearer tokens in browser storage,
and it never automatically retries a maintenance mutation.

### Read-only operational support evidence

Collect only the evidence needed to correlate an incident, and retain it under
the site's existing restricted support-data policy:

1. Record the exact release tag/SHA and running service/image identities.
2. Record health status plus the workflow and immutable action-request IDs.
3. Export or transcribe the sanitized lifecycle projection, ledger state and
   ordered transitions, approval state, target fingerprint, and relevant audit
   event IDs.
4. Confirm barrier/provider-operation counts and whether the lifecycle is
   terminal. Evidence collection is read-only and must not resume, retry, or
   reconcile a mutation through an execution endpoint.

Never include credentials, Authorization headers, cookies, CSRF or bearer
tokens, TLS private keys, operator-verifier hashes, provider-native secrets,
raw `vmgenid` values, or identity tokens. Atlas defines no automatic upload
destination; transfer and retention remain an operator-controlled process.

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

> **Historical procedure boundary:** The v0.6 through v0.10 upgrade sections
> below record the tooling and data contracts available to those releases.
> Their format-v1/v2 “Atlas data backup” artifacts are legacy-partial, not
> complete Core generations, and current v0.11 tooling will not overlay them on
> populated managed state. Do not reuse those procedures for a v0.11 downgrade;
> follow [Atlas v0.10.0 to v0.11 rollback and re-upgrade lineage](#atlas-v0100-to-v011-rollback-and-re-upgrade-lineage).

## Atlas v0.6.0 upgrade and manual rollback

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

## Atlas v0.6.0 to v0.7 upgrade and rollback

The supported starting point for the Atlas v0.7 release line is the immutable
`atlas-v0.6.0` release at
`03c1e03099b0f638dc674235312a3b3e70768c2f`. Atlas does not perform this
upgrade or its rollback automatically.

### Before upgrading

Require all of the following before changing the checked-out release:

- the tracked worktree is clean;
- Atlas Core, Atlas Agent, Mission Control, and the configured ingress are
  healthy;
- the production Compose environment and existing credential paths are
  available;
- the Proxmox provider is reachable through Atlas;
- TLS keys, the edge `htpasswd`, and operator verifier material are stored
  outside Git; and
- a current verified Atlas data backup exists.

Create the Atlas data backup while v0.6.0 is still running and record its exact
path:

```bash
./scripts/atlas-data-backup /path/to/protected-atlas-backups
```

The Agent state volume is separate from `atlas-data` and is not included by
that command. Before the upgrade, preserve a storage-level snapshot or verified
offline archive of the `atlas-agent-state` named volume using the host's
approved volume-backup mechanism. Record the Compose project name, volume
identity, snapshot identifier, and creation time. This pre-upgrade Agent-state
snapshot is required for a fail-safe downgrade because v0.6 is not guaranteed
to decode v0.7 schema-v3 state.

Do not put either backup in the Git repository. Treat Atlas backups as secret
material because they can contain provider connection secrets and operational
history.

### New v0.7 deployment requirements

Operator mutations require all three Compose files:

```text
compose.production.yaml
compose.https.yaml
compose.operator-auth.yaml
```

They also require:

- a browser-trusted TLS certificate and matching private key;
- an edge `htpasswd` file for defense-in-depth HTTP Basic authentication;
- one exact HTTPS browser origin in
  `ATLAS_OPERATOR_AUTH_TRUSTED_ORIGINS` (no wildcard and no HTTP origin);
- a Core operator verifier supplied through
  `ATLAS_OPERATOR_AUTH_VERIFIER_HOST_PATH`;
- an enabled operator carrying exactly the required
  `operational_intent:create` permission; and
- a dedicated Proxmox identity with `VM.Audit` and `VM.PowerMgmt` scoped to
  each approved `/vms/<VMID>` target.

The Core verifier must be a regular non-symlink file owned by UID/GID
`10001:10001` with mode `0400`. The TLS private key and edge password database
must remain private and readable only by the configured edge runtime identity;
the certificate may be mode `0644`. Follow the provisioning commands in
[Core-owned operator authentication](#core-owned-operator-authentication) and
[Authenticated HTTPS](#authenticated-https). Do not grant `Sys.PowerMgmt`,
permission-management, cluster-root, broad `VM.Config.*`, or administrative
roles for the restart capability.

### Upgrade procedure

1. Confirm the starting release and clean tracked tree:

```bash
test "$(git rev-parse atlas-v0.6.0^{})" = \
  "03c1e03099b0f638dc674235312a3b3e70768c2f"
git diff --quiet
git diff --cached --quiet
```

2. Fetch the reviewed v0.7 release reference, verify its expected immutable
   SHA, and check it out. Set both values from the signed release record rather
   than discovering the expected SHA from the fetched tag itself:

```bash
ATLAS_V07_REF=atlas-v0.7-rc1
ATLAS_V07_EXPECTED_SHA=replace-with-reviewed-release-sha
git fetch origin tag "$ATLAS_V07_REF"
test "$(git rev-parse "$ATLAS_V07_REF^{}")" = "$ATLAS_V07_EXPECTED_SHA"
git switch --detach "$ATLAS_V07_REF^{}"
```

3. Reconfirm that the pre-upgrade Atlas data backup and Agent-state snapshot
   are present and verified. Do not continue if either artifact is missing.

4. Export the existing production environment and the new private file paths.
   Use the exact HTTPS origin operators will enter in their browsers:

```bash
export ATLAS_REPOSITORY_HOST_PATH="$PWD"
export DOCKER_GID="$(stat -c '%g' /var/run/docker.sock)"
export ATLAS_TLS_CERT_FILE=/path/to/atlas.crt
export ATLAS_TLS_KEY_FILE=/path/to/atlas.key
export ATLAS_HTPASSWD_FILE=/path/to/atlas.htpasswd
export ATLAS_OPERATOR_AUTH_VERIFIER_HOST_PATH=/path/to/atlas-operators.json
export ATLAS_OPERATOR_AUTH_TRUSTED_ORIGINS=https://atlas.example.internal
```

5. Render the complete configuration before changing containers:

```bash
docker compose \
  -f compose.production.yaml \
  -f compose.https.yaml \
  -f compose.operator-auth.yaml \
  config --quiet
```

6. Build and recreate the deployment with the same three-file Compose set:

```bash
docker compose \
  -f compose.production.yaml \
  -f compose.https.yaml \
  -f compose.operator-auth.yaml \
  up --build --detach
```

7. Require Core, Agent, Mission Control, and Atlas Edge to report healthy:

```bash
docker compose \
  -f compose.production.yaml \
  -f compose.https.yaml \
  -f compose.operator-auth.yaml \
  ps
```

8. Confirm the closed operational capability and production handler contract:

```bash
docker compose \
  -f compose.production.yaml \
  -f compose.https.yaml \
  -f compose.operator-auth.yaml \
  exec -T atlas-agent python -c \
  'from app.candidate_planning.models import OPERATIONAL_EXECUTION_INTENTS; assert OPERATIONAL_EXECUTION_INTENTS == frozenset({"restart-service"})'

docker compose \
  -f compose.production.yaml \
  -f compose.https.yaml \
  -f compose.operator-auth.yaml \
  exec -T atlas-core python -c \
  'from app.operational_dispatch.registry import OPERATIONAL_EXECUTION_INTENTS; assert OPERATIONAL_EXECUTION_INTENTS == frozenset({"restart-service"})'
```

Confirm through the deployed Core startup log or release diagnostic that the
production registry contains exactly one tuple:
`restart-service / proxmox / qemu`. A missing or additional tuple is a failed
upgrade check.

9. Open the exact trusted HTTPS origin through a client that trusts the issuing
   CA. Confirm edge Basic authentication, then log in through Mission Control.
   Require the Core-owned session to identify the intended operator and expose
   only its configured permissions. Require a same-origin, CSRF-protected
   `/api/v1/operator-auth/probe` request to succeed; missing/wrong CSRF and a
   different Origin must remain rejected. Never print or retain the password,
   cookie, CSRF value, or verifier hash in release evidence.

10. Load the maintenance resource selector through that authenticated session.
    Confirm it is read-only, contains only sanitized resource fields, and marks
    only authoritative, running, unlocked, non-migrating QEMU targets as
    requestable. Loading or selecting a resource must not create a candidate,
    approval, dispatch record, or provider operation.

Ordinary upgrade validation stops here. Do not request or perform a live
restart merely to validate an installation.

### Persistence and downgrade compatibility

Atlas Agent writes aggregate snapshot schema v3 in v0.7. Its implemented
decoder accepts schemas v1, v2, and v3, so existing v0.6 repository workflows
remain supported when upgrading. This is forward compatibility in v0.7; it is
not proof that v0.6 can open a schema-v3 snapshot.

V0.7 also creates persistent Core databases in the `atlas-data` volume for:

- operational dispatch records, transitions, results, and audit events;
- operator-intent records and audit events;
- operator sessions; and
- operator security audit events.

These databases are separate from the existing action-history and provider
intelligence databases. The current `atlas-data-backup` format protects the
established v0.6 databases and runtime configuration, but does not claim to be
a downgrade archive for Agent schema-v3 state or all new v0.7 databases.

Consequently, in-place mutable-data downgrade compatibility is **not
guaranteed**. A rollback to v0.6.0 must restore the verified pre-upgrade Atlas
data backup and the pre-upgrade `atlas-agent-state` volume snapshot. Before
doing so, preserve a separate offline snapshot/archive of the complete v0.7
`atlas-data` and `atlas-agent-state` volumes so operational evidence is not
lost.

### In-flight operational actions

Before rollback, inspect the production operational ledger. If no request is
in a non-terminal state, proceed with the normal rollback sequence below.

If any request reached `dispatching` or crossed the durable dispatch barrier:

- do not retry, recreate, or replace the mutation request;
- do not assume an interrupted HTTP response means the provider rejected it;
- preserve the production ledger, request digest, transition history, captured
  UPID, and sanitized audit evidence;
- use the existing v0.7 read-only lifecycle/status reconciliation until the
  request reaches `verified`, `verification_failed`, `target_replaced`, or
  `outcome_unknown`; and
- begin rollback only after the operator has reviewed that terminal result.

An unresolved barrier-crossed request blocks ordinary rollback. Downgrading
Core first would remove the verifier needed to establish the durable outcome
and could invite an unsafe manual replay.

### Rollback to atlas-v0.6.0

This is a code/container **and mutable-data** rollback. Do not delete or
overwrite the v0.7 volumes until their complete offline preservation has been
verified.

1. Confirm there is no in-flight operational request using the rules above.
2. Record the running v0.7 SHA and preserve full offline snapshots/archives of
   both `atlas-data` and `atlas-agent-state`.
3. Stop the v0.7 three-overlay deployment:

```bash
docker compose \
  -f compose.production.yaml \
  -f compose.https.yaml \
  -f compose.operator-auth.yaml \
  down
```

4. Restore the pre-upgrade `atlas-agent-state` volume snapshot using the same
   host-approved volume restore mechanism used to create it. Restore the
   pre-upgrade Atlas data backup while services are stopped:

```bash
./scripts/atlas-data-restore \
  /path/to/protected-atlas-backups/atlas-data-YYYYMMDDTHHMMSSZ \
  --confirm
```

5. Check out and verify the immutable v0.6.0 release:

```bash
git switch --detach atlas-v0.6.0^{}
test "$(git rev-parse HEAD)" = \
  "03c1e03099b0f638dc674235312a3b3e70768c2f"
```

6. Render the v0.6 production deployment using only the overlays supported by
   that release, then rebuild and recreate it:

```bash
export ATLAS_REPOSITORY_HOST_PATH="$PWD"
export DOCKER_GID="$(stat -c '%g' /var/run/docker.sock)"
docker compose -f compose.production.yaml config --quiet
docker compose -f compose.production.yaml up --build --detach
```

Include `compose.https.yaml` and its private file variables when HTTPS was part
of the v0.6 deployment. Do not include `compose.operator-auth.yaml`; it is a
v0.7 overlay.

7. Require all v0.6 services to become healthy and confirm that
   `restart-service` is absent from Agent and Core operational execution
   capabilities and that no v0.7 operational handler is registered. Do not
   perform a provider mutation as a rollback smoke test.

The v0.7 operator verifier, TLS material, and `htpasswd` may remain in their
private, ignored host locations. V0.6 does not consume the operator-auth
overlay or Core verifier. Deleting those files is not required for rollback;
normal credential-retention and rotation policy still applies.

## Atlas v0.7.0 to v0.8 upgrade and rollback

The supported starting point is immutable release `atlas-v0.7.0` at
`8dbc43de73dda300b50c121f19324cb5174df2a9`. Atlas does not automatically
upgrade or roll back a deployment.

The reviewed upgrade target is final release `atlas-v0.8.0` at
`f83cd90982d4682ce49e60308e93dc9840984211`, promoted from immutable candidate
`atlas-v0.8-rc1` at
`cf09dfe1eebbd138d37ba7144d91b893f70732fa`.

### Pre-upgrade requirements

Before selecting a reviewed v0.8 release reference, require:

- a clean tracked worktree;
- a current verified Atlas data backup;
- a current host-approved snapshot or offline archive of the
  `atlas-agent-state` volume;
- operator-auth verifier, TLS key/certificate, and edge `htpasswd` material
  preserved outside Git;
- healthy Core, Agent, Mission Control, Edge, worker, relay, and egress proxy;
- the configured provider reachable through Atlas; and
- the exact production Compose environment and private paths available.

Record backup/snapshot identities and retain them outside the repository. Atlas
data and Agent state may contain operational history or secrets and must be
handled as restricted material.

### Upgrade procedure

1. Verify the starting release and clean tracked state:

```bash
test "$(git rev-parse 'atlas-v0.7.0^{}')" = \
  "8dbc43de73dda300b50c121f19324cb5174df2a9"
git diff --quiet
git diff --cached --quiet
```

2. Create and verify the Atlas data backup, then snapshot
   `atlas-agent-state` with the approved host mechanism:

```bash
./scripts/atlas-data-backup /path/to/protected-atlas-backups
```

3. Fetch the reviewed v0.8 reference and verify it against the independently
   recorded release SHA before checking it out:

```bash
ATLAS_V08_REF=atlas-v0.8.0
ATLAS_V08_EXPECTED_SHA=f83cd90982d4682ce49e60308e93dc9840984211
git fetch origin tag "$ATLAS_V08_REF"
test "$(git rev-parse "$ATLAS_V08_REF^{}")" = "$ATLAS_V08_EXPECTED_SHA"
git switch --detach "$ATLAS_V08_REF^{}"
```

4. Export the existing production paths and exact browser origin. Do not print
   private file contents:

```bash
export ATLAS_REPOSITORY_HOST_PATH="$PWD"
export DOCKER_GID="$(stat -c '%g' /var/run/docker.sock)"
export ATLAS_TLS_CERT_FILE=/path/to/atlas.crt
export ATLAS_TLS_KEY_FILE=/path/to/atlas.key
export ATLAS_HTPASSWD_FILE=/path/to/atlas.htpasswd
export ATLAS_OPERATOR_AUTH_VERIFIER_HOST_PATH=/path/to/atlas-operators.json
export ATLAS_OPERATOR_AUTH_TRUSTED_ORIGINS=https://atlas.example.internal
```

5. Render, build, and recreate the same three-file production deployment:

```bash
docker compose \
  -f compose.production.yaml \
  -f compose.https.yaml \
  -f compose.operator-auth.yaml \
  config --quiet
docker compose \
  -f compose.production.yaml \
  -f compose.https.yaml \
  -f compose.operator-auth.yaml \
  up --build --detach
docker compose \
  -f compose.production.yaml \
  -f compose.https.yaml \
  -f compose.operator-auth.yaml \
  ps
```

6. Require every service to become healthy. Run
   `./scripts/operational-capability-parity` and require exactly
   `restart-service / proxmox / qemu`. Through authenticated HTTPS, confirm
   session restore/CSRF rotation, the protected probe, the sanitized capability
   descriptor, resource selector, and read-only operational history.

7. Confirm the hardened browser path is
   `browser -> Atlas Edge HTTPS -> Mission Control -> Agent/Core`. The HTTPS
   overlay intentionally removes Mission Control's direct host publication;
   internal Edge-to-Mission-Control routing remains available.

V0.8 adds effect-aware approval presentation, a unified lifecycle read model,
operational history/recovery UX, and provider-neutral descriptors. These are
read/presentation controls and do not widen execution. Do not request a live VM
restart merely to validate an ordinary upgrade.

### Persistence and data compatibility

V0.8 does not change Atlas Agent's aggregate snapshot schema: it remains schema
v3 with the implemented v1/v2/v3 readers. Core's operational dispatch table,
event table, and transition table definitions are also unchanged. P2 adds
ordered read queries and sanitized projections; P3 is UI/read behavior; P4
descriptors and P5 ingress/session ergonomics add no persistent migration.

Those facts establish forward upgrade without a v0.8 migration, but the project
does not provide an explicit end-to-end guarantee that v0.7.0 can safely open
every state written while v0.8 is running. Fail-safe rollback therefore
requires restoring both the pre-upgrade Atlas data backup and the pre-upgrade
`atlas-agent-state` snapshot. Preserve complete v0.8 copies of both volumes
before restoration so lifecycle and audit evidence are not lost.

### In-flight action handling

Normal rollback requires no in-flight operational request. If a request reached
`dispatching` or crossed the durable barrier:

- do not retry, recreate, or replace it;
- preserve its ledger, digest, transitions, provider-operation reference, and
  sanitized audit evidence;
- use v0.8 read-only lifecycle/status views to determine the durable outcome;
- wait for `verified`, `verification_failed`, `target_replaced`, or
  `outcome_unknown`; and
- require operator review of that terminal state before rollback.

An unresolved barrier-crossed request blocks ordinary rollback.

### Rollback to atlas-v0.7.0

1. Confirm no operational request is in flight under the rules above.
2. Record the v0.8 SHA and preserve offline copies of the complete v0.8
   `atlas-data` and `atlas-agent-state` volumes.
3. Stop the v0.8 three-file deployment:

```bash
docker compose \
  -f compose.production.yaml \
  -f compose.https.yaml \
  -f compose.operator-auth.yaml \
  down
```

4. Restore the pre-upgrade `atlas-agent-state` snapshot with the same approved
   host mechanism and restore the pre-upgrade Atlas backup while services are
   stopped:

```bash
./scripts/atlas-data-restore \
  /path/to/protected-atlas-backups/atlas-data-YYYYMMDDTHHMMSSZ \
  --confirm
```

5. Check out the immutable v0.7.0 release, render, and recreate its supported
   three-file production deployment:

```bash
git switch --detach 'atlas-v0.7.0^{}'
test "$(git rev-parse HEAD)" = \
  "8dbc43de73dda300b50c121f19324cb5174df2a9"
docker compose \
  -f compose.production.yaml \
  -f compose.https.yaml \
  -f compose.operator-auth.yaml \
  config --quiet
docker compose \
  -f compose.production.yaml \
  -f compose.https.yaml \
  -f compose.operator-auth.yaml \
  up --build --detach
```

6. Require all services to become healthy and confirm v0.8-only lifecycle
   history, descriptor, and effect-presentation surfaces are absent. Confirm
   the v0.7 production boundary remains exactly
   `restart-service / proxmox / qemu`. Do not perform a provider mutation as a
   rollback smoke test.

The v0.8 operator verifier, TLS material, and edge `htpasswd` may remain in
their private ignored locations; v0.7 already consumes the three-file
operator-auth deployment. Deletion is not required for rollback.

## Atlas v0.8.0 to v0.9 upgrade and rollback

The supported starting point is the immutable `atlas-v0.8.0` release at
`f83cd90982d4682ce49e60308e93dc9840984211`. Before upgrading, require a clean
tracked worktree, a current Atlas data backup, a current `atlas-agent-state`
snapshot, preserved operator-auth and TLS private material outside Git, healthy
services, a reachable configured provider, and the exact production Compose
environment.

### Upgrade to v0.9

1. Confirm there is no in-flight operational request. Preserve any terminal
   lifecycle and audit evidence needed for support or release review.
2. Create an Atlas data backup and snapshot `atlas-agent-state` using the
   approved host mechanism:

```bash
./scripts/atlas-data-backup /path/to/protected-atlas-backups
```

3. Fetch the reviewed v0.9 release reference, compare it with the independently
   recorded release SHA, and check out that exact commit:

```bash
ATLAS_V09_REF=atlas-v0.9.0
ATLAS_V09_EXPECTED_SHA='<independently-recorded-release-sha>'
git fetch origin tag "$ATLAS_V09_REF"
test "$(git rev-parse "$ATLAS_V09_REF^{}")" = "$ATLAS_V09_EXPECTED_SHA"
git switch --detach "$ATLAS_V09_REF^{}"
```

4. Export the existing private file paths and exact trusted HTTPS origin, then
   render and deploy the same three-file hardened stack:

```bash
docker compose \
  -f compose.production.yaml \
  -f compose.https.yaml \
  -f compose.operator-auth.yaml \
  config --quiet
docker compose \
  -f compose.production.yaml \
  -f compose.https.yaml \
  -f compose.operator-auth.yaml \
  up --build --detach
docker compose \
  -f compose.production.yaml \
  -f compose.https.yaml \
  -f compose.operator-auth.yaml \
  ps
```

5. Require all services to become healthy. Run
   `./scripts/operational-capability-parity` and require exactly
   `restart-service/proxmox/qemu`. Through authenticated Edge HTTPS, verify the
   operator session/probe, read-only lifecycle diagnostic, bounded operational
   history, and local support-bundle preview. Do not perform a provider
   mutation merely to validate an ordinary upgrade.

V0.9 adds read-only recovery diagnostics, bounded sanitized support bundles,
check-only release-evidence collection, and Mission Control recovery/history
presentation. Support bundles download locally only; release evidence is
written only when an operator explicitly redirects or retains command output.

### Persistence and compatibility

Atlas Agent snapshot schema remains v3, with the existing v1/v2/v3 readers.
Core operational dispatch schema version and the dispatch, event, and
transition table definitions are unchanged. V0.9 adds read queries and derived
projections only. Support bundles and release evidence have no runtime database
and are not automatically persisted. Mission Control additions are UI-only and
use no durable browser state.

No migration is required for forward upgrade. End-to-end downgrade
compatibility is not explicitly guaranteed, however. A fail-safe rollback must
preserve the complete v0.9 data/state first, then restore both the pre-upgrade
Atlas data backup and the pre-upgrade `atlas-agent-state` snapshot.

### In-flight action handling

Normal rollback requires no in-flight operational request. If a request has
reached `dispatching` or crossed the durable barrier, do not retry or recreate
the mutation. Preserve its ledger, request digest, transitions, provider
operation reference, diagnostic, and sanitized support evidence. Reconcile it
read-only to a terminal `verified`, `verification_failed`, `target_replaced`,
or `outcome_unknown` state and require operator review before rollback. An
unresolved barrier-crossed request blocks ordinary rollback.

### Rollback to atlas-v0.8.0

1. Confirm no operational request is in flight under the rule above.
2. Record the v0.9 SHA and preserve offline copies of the complete v0.9 Atlas
   data and Agent-state volumes.
3. Stop the three-file v0.9 deployment with `docker compose ... down` using the
   same three Compose files.
4. Restore the pre-upgrade `atlas-agent-state` snapshot and Atlas data backup
   while services are stopped:

```bash
./scripts/atlas-data-restore \
  /path/to/protected-atlas-backups/atlas-data-YYYYMMDDTHHMMSSZ \
  --confirm
```

5. Check out and verify the immutable v0.8.0 release, then render and recreate
   its three-file production deployment:

```bash
git switch --detach 'atlas-v0.8.0^{}'
test "$(git rev-parse HEAD)" = \
  "f83cd90982d4682ce49e60308e93dc9840984211"
docker compose \
  -f compose.production.yaml \
  -f compose.https.yaml \
  -f compose.operator-auth.yaml \
  config --quiet
docker compose \
  -f compose.production.yaml \
  -f compose.https.yaml \
  -f compose.operator-auth.yaml \
  up --build --detach
```

6. Require all services healthy and confirm v0.9 diagnostic, support-bundle,
   release-evidence, and recovery-summary surfaces are absent. Confirm the
   operational capability remains exactly `restart-service/proxmox/qemu`; do
   not use a live provider mutation as a rollback smoke test.

Existing TLS, edge `htpasswd`, and operator-verifier files may remain in their
private ignored locations. They are still used by the v0.8 three-file hardened
deployment and need not be deleted for rollback.

## Atlas v0.9.0 to v0.10 upgrade and rollback

The supported starting point is immutable release `atlas-v0.9.0` at
`7a5beac58e1677cd97b9bcc2f160dc30573582aa`. Before upgrading, require a clean
tracked worktree, a current Atlas data backup, a current `atlas-agent-state`
snapshot, preserved operator-auth and TLS private material outside Git, healthy
services, a reachable configured provider, and the exact production Compose
environment.

### Upgrade to v0.10

1. Confirm no operational request is in flight and preserve terminal lifecycle
   and audit evidence required for support or release review.
2. Create an Atlas data backup and snapshot `atlas-agent-state` using the
   approved host mechanism:

```bash
./scripts/atlas-data-backup /path/to/protected-atlas-backups
```

3. Fetch the reviewed release, compare it with the independently recorded
   release SHA, and check out that exact commit:

```bash
ATLAS_V010_REF=atlas-v0.10.0
ATLAS_V010_EXPECTED_SHA='<independently-recorded-release-sha>'
git fetch origin tag "$ATLAS_V010_REF"
test "$(git rev-parse "$ATLAS_V010_REF^{}")" = "$ATLAS_V010_EXPECTED_SHA"
git switch --detach "$ATLAS_V010_REF^{}"
```

4. Export the existing private paths and trusted HTTPS origin. Render and
   deploy the same hardened three-file stack:

```bash
docker compose \
  -f compose.production.yaml \
  -f compose.https.yaml \
  -f compose.operator-auth.yaml \
  config --quiet
docker compose \
  -f compose.production.yaml \
  -f compose.https.yaml \
  -f compose.operator-auth.yaml \
  up --build --detach
docker compose \
  -f compose.production.yaml \
  -f compose.https.yaml \
  -f compose.operator-auth.yaml \
  ps
```

5. Require all services healthy. Run
   `./scripts/operational-capability-parity` and require exactly
   `restart-service/proxmox/qemu`. Through authenticated Edge HTTPS, verify the
   operator session, read-only Discovery proposal list/detail, Discovery item
   proposal presentation, and authoritative maintenance selector reload. Do
   not submit an operator intent or perform a provider mutation merely to
   validate an ordinary upgrade.

V0.10 adds immutable advisory proposal contracts, read-only stale-aware
derivation, GET-only proposal APIs, closed navigation, and Mission Control
proposal presentation. Proposal context cannot create candidates, action
requests, approvals, dispatch records, or provider operations.

### Persistence and compatibility

V0.10 does not change Atlas Agent snapshot schema v3 or its v1/v2/v3 readers.
It does not change the Core operational dispatch, event, or transition schema,
and adds no durable proposal database. Previously observed proposals use only a
bounded process-local cache and disappear on Core restart. Mission Control
proposal state is UI-only. No forward data migration is required.

End-to-end downgrade compatibility is still not explicitly guaranteed. A
fail-safe rollback must preserve complete v0.10 data and Agent state first,
then restore both the pre-upgrade Atlas data backup and pre-upgrade
`atlas-agent-state` snapshot.

### In-flight action handling

Normal rollback requires no in-flight operational request. If a request has
reached `dispatching` or crossed the durable barrier, do not retry or recreate
the mutation. Preserve its ledger, request digest, transitions, provider
operation reference, diagnostic, and sanitized support evidence. Reconcile it
read-only to a terminal `verified`, `verification_failed`, `target_replaced`,
or `outcome_unknown` state and require operator review before rollback. An
unresolved barrier-crossed request blocks ordinary rollback.

### Rollback to atlas-v0.9.0

1. Confirm no operational request is in flight under the rule above.
2. Record the v0.10 SHA and preserve offline copies of complete v0.10 Atlas
   data and Agent-state volumes.
3. Stop the v0.10 deployment using the same three Compose files.
4. Restore the pre-upgrade `atlas-agent-state` snapshot and Atlas data backup
   while services are stopped:

```bash
./scripts/atlas-data-restore \
  /path/to/protected-atlas-backups/atlas-data-YYYYMMDDTHHMMSSZ \
  --confirm
```

5. Check out and verify the immutable v0.9.0 release, then render and recreate
   its hardened three-file deployment:

```bash
git switch --detach 'atlas-v0.9.0^{}'
test "$(git rev-parse HEAD)" = \
  "7a5beac58e1677cd97b9bcc2f160dc30573582aa"
docker compose \
  -f compose.production.yaml \
  -f compose.https.yaml \
  -f compose.operator-auth.yaml \
  config --quiet
docker compose \
  -f compose.production.yaml \
  -f compose.https.yaml \
  -f compose.operator-auth.yaml \
  up --build --detach
```

6. Require all services healthy, confirm v0.10 proposal API/UI surfaces are
   absent, and reconfirm the sole operational tuple remains
   `restart-service/proxmox/qemu`. Do not use a live provider mutation as a
   rollback test.

Existing TLS, Edge `htpasswd`, and operator-verifier files remain private and
may stay in place; v0.9.0 uses the same hardened three-file deployment.

## Atlas v0.10.0 to v0.11 rollback and re-upgrade lineage

The supported v0.10 starting point is immutable release `atlas-v0.10.0` at
`b19ded149f65dfb4043a1b80833e5ff64d83e55d`. A safe downgrade from v0.11 is a
paired code-and-data rollback to a preserved v0.10 generation. It is **not** a
Git checkout against current v0.11 state, a format-v2 restore treated as
complete, or a format-v3 restore followed by a v0.10 start.

Before upgrading, retain all of the following as one externally recorded
downgrade anchor:

- a verified offline snapshot of the complete v0.10 `atlas-data` volume;
- a coordinated offline snapshot of `atlas-agent-state`;
- the exact v0.10 release SHA or immutable image identity;
- snapshot identifiers, timestamps, and checksums;
- a pre-upgrade format-v2 backup as supplemental legacy-partial evidence, not
  as the complete Core recovery point; and
- operational-ledger review evidence proving that restoring the snapshots will
  not forget safety-critical request identity or dispatch history.

Core backup format v3 does not contain `atlas-agent-state`. Every fail-safe
downgrade or re-upgrade therefore requires a compatible paired Agent snapshot;
a Core backup alone is not a whole-stack rollback.

### Roll back v0.11 to the preserved v0.10 generation

1. Stop new operator and automated mutation activity.
2. Stop and detach every Core and Agent container that uses either persistent
   volume. Stopped attached containers also block the restore wrapper.
3. Preserve complete offline snapshots of the current v0.11 Core and Agent
   state before changing either lineage.
4. Compare operational activity since the v0.10 rollback snapshot with the
   retained ledger evidence. Block ordinary rollback if the old generation
   would forget a crossed dispatch barrier, an ambiguous result, a request
   identity, or other evidence needed to prevent replay.
5. Restore the paired pre-upgrade v0.10 `atlas-data` and `atlas-agent-state`
   snapshots using the approved offline volume-snapshot mechanism. Do not use a
   legacy-partial backup as a replacement for the complete Core snapshot.
6. While services remain stopped, invalidate sessions by removing
   `operator_sessions.db`, `operator_sessions.db-wal`, and
   `operator_sessions.db-shm`, unless the Core snapshot was explicitly captured
   after session invalidation. Never resurrect sessions from either lineage.
7. Start only the exact accepted v0.10 release or immutable images recorded
   with the downgrade anchor.
8. Retain the preserved v0.11 Core and Agent state until an explicit re-upgrade
   lineage decision is recorded.

Never restore an Atlas Core format-v3 backup and then start Atlas v0.10 against
that volume. V0.10 does not understand v3 completeness and restore semantics,
lacks the v0.11 startup restore interlock, cannot interpret future Provider
Intent authority, and may interpret operational evidence under incompatible
assumptions. Restore the preserved pre-upgrade v0.10 snapshots instead.

### Operational rollback review

Request state alone is not sufficient: the selected rollback generation must
retain request identity and no-replay evidence wherever losing it could make an
old request appear fresh.

- `claimed` or `revalidated`: no provider mutation barrier is known to have
  been crossed, but rollback remains unsafe if the request identity disappears
  and could later be accepted as new.
- `dispatching`: ordinary rollback is blocked. Current recovery semantics
  reconcile it to `outcome_unknown` without replay.
- `outcome_unknown`: require explicit operator review and read-only provider
  verification. Never retry automatically.
- `succeeded` or `verifying`: preserve the evidence and finish read-only
  verification before ordinary rollback.
- terminal states: the rollback generation must still retain identity and
  no-replay evidence when losing it could permit replay.

Monitoring intent, historical records, or restored state never creates new
approval or execution authority.

### Choose one re-upgrade lineage

The two safe choices are mutually exclusive. Atlas does not merge lineages
automatically.

**Resume the preserved v0.11 lineage:** restore the preserved v0.11 Core state
or accepted v3 backup, restore its matching Agent snapshot, and run a compatible
v0.11 release. Abandon activity performed on the temporary rolled-back v0.10
lineage.

**Continue the rolled-back v0.10 lineage:** treat the restored v0.10 state and
all subsequent v0.10 activity as authoritative. Before upgrading, take a new
complete Core volume snapshot and matching Agent snapshot, upgrade forward
normally, and establish a new accepted v3 recovery point. Do not overlay or
merge the old preserved v0.11 state.

Record lineage externally rather than adding a runtime marker. Evidence must
include immutable snapshot IDs, backup IDs and checksums, timestamps, release
SHA or image digest, the paired Core/Agent relationship, and the operational
ledger review.

Pin these anchors for the supported downgrade window so generic retention does
not prune them:

- the pre-upgrade v0.10 full Core volume snapshot and matching Agent snapshot;
- the pre-upgrade v2 export as supplemental evidence;
- the first accepted v0.11 v3 backup and its matching Agent snapshot;
- complete v0.11 Core and Agent snapshots captured before any rollback; and
- normal rolling verified v3 backups.

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

Backup compatibility is determined by the manifest schema, format version,
completeness semantics, Provider Intent activation semantics, and the restore
tool's declared supported-format set. Do not infer compatibility from a backup
directory name or assume an arbitrary future release can restore a current
format.

| Restoring Atlas release | Format v1 | Format v2 | Format v3 |
| --- | --- | --- | --- |
| v0.6.0 through v0.10.0 | supported, `legacy_partial` | supported, `legacy_partial` | unsupported |
| v0.11 | supported, `legacy_partial` | supported, `legacy_partial` | supported, Core `complete` |

Format v1 contains only `action_history.db` and
`provider_intelligence.db`. Format v2 contains those databases plus only the
runtime YAML files represented in that backup. Neither format is a complete
Core recovery point.

Format v3 is complete for the declared Atlas Core managed durable-state
boundary. Its required state is:

- `action_history.db`;
- `provider_intelligence.db`;
- `operational_dispatch.db`;
- `operator_intents.db`;
- `config/policies.yaml`;
- `config/provider-connections.yaml`; and
- `secrets/provider-connections.yaml`.

`operator_security_audit.db` is conditional on operator-auth initialization.
`operator_sessions.db` is deliberately excluded and invalidated on restore.
While `provider_intent_activation=not_activated`, `provider_intents.db` is
required absent and is not created by restore or normal Core startup. The
manifest records required, conditionally absent, invalidated, and
pre-activation stores with sizes and SHA-256 checksums.

Core `complete` does not mean a whole-system backup. Format v3 excludes
`atlas-agent-state`, external provider and infrastructure state, the repository
and worktree, container images, host state outside managed Core paths, remote
deployments, caches, and other disposable state.

The command uses SQLite's online backup API, so WAL-mode writes can continue
without producing an inconsistent database copy. Runtime files are checked by
safe relative path, checksum, exact inventory, and store-specific structure.
Version-1 and version-2 backups retain their historical legacy-partial restore
semantics; they do not gain format-v3 invalidation or complete-set behavior.

Runtime policy files are owned by the Atlas container user and may be
mode `0600`. The backup command therefore reads the Atlas data volume
from a disposable helper running as the Atlas UID `10001`, with no
network, a read-only root filesystem, all capabilities dropped,
`no-new-privileges`, no Docker socket, the Atlas data volume mounted
read-only, and only the incomplete backup destination mounted writable.
Before the incomplete backup is renamed into place, a second disposable
ownership helper mounts only that incomplete backup directory and uses
only the `CHOWN` capability to set the backup directory and files back to
the invoking host UID/GID. Published directories remain mode `0700` and
artifacts remain mode `0600`. Operators can read, move, and remove their
artifacts without weakening live runtime permissions. Backup directories that
include `secrets/provider-connections.yaml` contain provider credentials
and must be protected like any other secret-bearing backup artifact.

Format-v3 restore transactionally adopts the complete managed generation and
removes stale WAL/SHM sidecars, operator sessions, and pre-activation Provider
Intent state. Stop and remove every running or stopped container attached to
the target volume first:

```bash
docker compose -f compose.production.yaml down
./scripts/atlas-data-restore \
  /mnt/atlas-backups/atlas-data-YYYYMMDDTHHMMSSZ \
  --confirm
docker compose -f compose.production.yaml up -d
```

Include `-f compose.https.yaml` in the `down` and `up` commands for an HTTPS
deployment. Restore refuses while any container—even a stopped one—is attached
to the volume. It verifies the host backup before mounting the target writable,
then uses a networkless, Docker-socket-free helper with a read-only source mount
to copy the private `0700`/`0600` backup into a disposable private staging
volume owned by `10001:10001`. Source permissions and contents are unchanged.

The unprivileged restore process recovers or finalizes any prior transaction,
stages and validates every artifact, quarantines the prior managed generation,
installs and independently verifies the new generation, then durably commits
before deleting `.atlas-restore` evidence. Core refuses startup while any
non-empty restore transaction namespace remains and directs the operator back
to the restore command; Core never performs recovery itself. Do not delete the
journal manually. Restored files are `10001:10001` mode `0600`, and managed
private directories are mode `0700`. Unmanaged cache, history, knowledge,
provider, and root files are not recursively changed or removed.

Version-1 and version-2 restore is allowed only onto a managed-empty Core target
and requires both normal confirmation and explicit acknowledgement:

```bash
./scripts/atlas-data-restore \
  /mnt/atlas-backups/atlas-data-YYYYMMDDTHHMMSSZ \
  --confirm \
  --allow-legacy-partial-new-lineage
```

Verification and container-attachment checks still apply. Restore refuses if
any managed Core path or any managed SQLite `-wal` or `-shm` sidecar exists;
the acknowledgement cannot override populated state. A successful restore
creates a new partial lineage, restores only the two v1 databases and, for v2,
only represented runtime YAML, and is not complete disaster recovery. Missing
runtime policy or provider connection files may still be initialized from
immutable templates or empty validated stores on later startup. Set
`ATLAS_DATA_VOLUME` only for a non-default Compose volume name.

When Provider Intent becomes authoritative, an activated v3 backup must include
`provider_intents.db` and a missing store must fail closed. Downgrade to a
release without Provider Intent support will require a preserved pre-activation
lineage; do not delete `provider_intents.db` to manufacture compatibility. Old
YAML expectations must not automatically regain authority, and legacy shadow
import remains separate from restore mechanics. Provider Intent is not
activated in the current release.

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

## Read-only release evidence

Use the local release-evidence collector during RC selection and final-tag
preparation to replace manual transcription of provenance checks:

```bash
./scripts/release-evidence \
  --expected-base atlas-v0.8.0 \
  --candidate-tag atlas-v0.9-rc1 \
  --expected-sha <reviewed-commit-sha> \
  --require-main \
  --require-tag
```

Add `--json` for the bounded `atlas-release-evidence-v1` representation. Add
`--check-running-images` only on a host with the intended production deployment;
the option performs Docker inspection only and never rebuilds or recreates a
container. Unknown options fail closed.

The collector reads Git identity and worktree state, peels annotated tags,
requires CI evidence to match the exact candidate SHA, reuses
`scripts/operational-capability-parity`, renders the base and hardened Compose
configurations, checks Edge-only hardened ingress, inspects tracked path names
and presence-only private-key/verifier signatures for release-sensitive
material without printing matched values, and runs bounded local syntax and
diff checks. Missing GitHub CLI access, unavailable private Compose inputs, and
unavailable requested image inspection are reported as incomplete rather than
invented as passing evidence. The allowed untracked exception is exactly
`compose.execution-smoke.override.yaml`.

Exit status is deterministic:

- `0`: ready; all evidence required by this tool passed.
- `1`: blocked; at least one required check failed.
- `2`: incomplete; required evidence was unavailable or pending.
- `3`: invalid invocation or collector configuration error.

This command is evidence automation, not deployment or release automation. It
does not run the container release gate, deploy or restart services, create or
modify tags, push commits, mutate GitHub state, or perform provider actions.
The container release gate, exact-SHA production soak, operator review, and
human approval to create immutable RC/final tags remain separate release
steps.

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
