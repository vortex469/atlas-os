# Agent Install-Container Contract v1

Status: **Atlas v0.22 P0–P3 complete; P4–P5 not started**.

This document freezes the narrowest Agent-side contract that may later validate
one future Core request to install one container. Atlas v0.22 adds only the
closed contract, pure validation, and non-authorizing audit evidence described
below. It does not add a Core request route, Core-to-Agent dispatch, worker
invocation, or any execution path. `install-container` remains unsupported and
default-disabled in production.

The binding equation for every phase is:

`valid contract != approved execution != dispatch != installation`.

## Repository inspection baseline

Planning starts from current `main` at
`8be5d7f27438147e32f49805ff032af5f6e72aa6`, after the v0.21 implementation
merge. The released `atlas-v0.21.0` tag points to
`1ca708198bb0098a64ed442dd50c4ad9171d69e5`. V0.21 records an immutable
operator statement about one exact v0.20 non-executable candidate, but no
production subsystem consumes it.

Atlas Agent currently supports repository work only for
`update-compose-stack`, operational handling only for
`restart-service/proxmox/qemu`, and no `install-container` intent. Existing
candidate planning, approvals, audit, workflow, dispatch, execution, worker,
provider, and repository packages remain separate and unchanged.

## Exact request schema

The only prospective input is the closed `AgentInstallContainerRequestV1`.
All fields are required, JSON objects reject duplicate and unknown keys, JSON
numbers are prohibited, strings are NFC, and canonicalization is the existing
restricted RFC 8785 JCS/NFC subset. Timestamps are UTC whole seconds. IDs use
the bounds already frozen by their source contracts. `lowerhex[64]` matches
`[0-9a-f]{64}`. `Sha256Digest` matches `sha256:[0-9a-f]{64}`.

```text
AgentInstallContainerRequestV1 = {
  schema: "agent-install-container-request-v1",
  operation: "install-container",
  mode: "validate-only",
  request_id: canonical UUIDv4,
  issued_at: UtcSecond,
  expires_at: UtcSecond,
  subject: InstallationSubjectV1,
  approval: ApprovedCandidateProofV1,
  artifact: InstallContainerArtifactV1,
  limits: InstallContainerLimitsV1,
  request_fingerprint: FingerprintV1
}

InstallationSubjectV1 = {
  provider: "proxmox",
  resource_type: "qemu",
  placement_kind: "existing-guest",
  resource_id: Id[1..64],
  destination_fingerprint: lowerhex[64]
}

ApprovedCandidateProofV1 = {
  candidate_record_id: canonical UUIDv4,
  candidate_envelope_fingerprint: FingerprintV1,
  admission_fingerprint: FingerprintV1,
  candidate_record_fingerprint: FingerprintV1,
  approval_intent_id: canonical UUIDv4,
  approval_intent_fingerprint: FingerprintV1
}

InstallContainerArtifactV1 = {
  kind: "single-oci-container-v1",
  source_plan_fingerprint: FingerprintV1,
  source_repository_path: RepoPath,
  source_service: Id[1..255],
  source_content_digest: Sha256Digest,
  image: OciRepository + "@" + Sha256Digest,
  runtime: "rootless-podman",
  container_name: "atlas-" + lowerhex[16],
  command: null,
  entrypoint: null,
  environment: [],
  secrets: [],
  host_mounts: [],
  devices: [],
  published_ports: [],
  network_mode: "none",
  privileged: false,
  read_only_root_filesystem: true,
  capabilities_add: [],
  capabilities_drop: ["ALL"],
  no_new_privileges: true,
  tmpfs: [{container_path:"/tmp",size_bytes:"67108864",
           options:["nodev","noexec","nosuid"]}],
  restart_policy: "no"
}

InstallContainerLimitsV1 = {
  cpu_count: "1",
  memory_bytes: "536870912",
  pids: "128",
  tmpfs_bytes: "67108864"
}

FingerprintV1 = {
  algorithm: "sha256",
  canonicalization: "atlas-jcs-nfc-v1",
  value: lowerhex[64]
}
```

`RepoPath` and `OciRepository` retain the exact v0.16 definitions. Decimal
resource values are strings and the four v1 values above are literals, not
caller-selected ranges. The request fingerprint is SHA-256 over UTF-8
`"atlas:agent-install-container-request:v1"`, one NUL byte, and canonical JSON
of every request field except `request_fingerprint`. Fingerprints identify
exact bytes and relationships; none conveys authority.

The request is at most 32 KiB in canonical form, must satisfy
`issued_at <= validation_time < expires_at`, and `expires_at` must be exactly
five minutes after `issued_at`. The Agent uses a trusted whole-second clock.
There is no extension map, arbitrary metadata, labels, notes, URL, address,
hostname, credential, token, registry authentication, raw YAML, Compose body,
shell, executable blob, package, script, hook, health-check command, or
runtime-specific escape hatch.

## Allowed installation subject and proof linkage

The sole subject class is one already-existing Proxmox QEMU guest incarnation
with `placement_kind=existing-guest`. The exact `resource_id` and current
opaque destination fingerprint must equal the values embedded through the
v0.17 selection and v0.19 candidate lineage. Wildcards, provider aliases,
node fallback, moved or replacement guests, templates, LXC, the Proxmox host,
the Atlas host, Kubernetes, remote Docker endpoints, newly provisioned guests,
and multiple destinations are rejected.

All six proof identifiers and fingerprints are mandatory. Validation requires
one complete fingerprint-valid v0.20 envelope and one complete fingerprint-
valid v0.21 intent owned by the same authenticated operator in a future Core
boundary. The envelope must be active; its embedded candidate must exactly
match the admission and candidate fingerprints; the intent's approved-subject
tuple must exactly match the candidate record ID and all three candidate
fingerprints. The subject and artifact plan fingerprint must exactly match the
candidate's destination and plan lineage. No proof may be omitted, supplied as
a mutable alias, refreshed, reconstructed, inferred from item identity, or
substituted with an older approval system.

V0.22 has no Core adapter and therefore cannot perform those authoritative
lookups in production. Pure validators may accept only complete already-
validated contract fixtures supplied directly by tests. Any runtime request is
unsupported regardless of syntactic validity.

## Permitted artifact and runtime boundary

V1 permits only the normalized single-container projection above. It is not a
generic Docker Compose contract. It cannot represent multiple services,
builds, profiles, dependencies, extensions, configs, secrets, environment,
commands, entrypoints, health-check commands, devices, published ports,
host/bridge/custom networks, host mounts, Docker or Podman sockets, privileged
mode, added capabilities, writable root filesystems, or restart behavior.
The image is immutable and digest-qualified; tags alone are rejected. The
source path, service, content digest, and plan fingerprint preserve provenance
but authorize no repository read or mutation.

The eventual boundary, if separately enabled by a later release, is one
rootless Podman container inside the exact existing guest, never a container
on the Agent or Proxmox host. The only writable mount in v1 is the bounded
`/tmp` tmpfs. No host path, persistent volume, socket, device, guest system
directory, repository checkout, or other container may be read or changed.
The runtime must enforce the fixed CPU, memory, PID, tmpfs, capability,
privilege, and read-only limits rather than treating them as advisory.

Network mode is exactly `none`: no egress, ingress, DNS, LAN, host networking,
port publication, service discovery, proxy inheritance, registry pull, or
control-plane connection is permitted. V1 therefore assumes the exact image
is already present in a future trusted guest-side content store. Image
acquisition, registry authentication, pulling, loading, copying, and
verification transport are outside the contract and cannot happen during
validation or execution.

## Validation-only and default-disabled behavior

P1–P5 may implement only deterministic pure parsing, canonicalization,
fingerprinting, linkage validation over injected closed values, and result
construction. Validation performs no Core, provider, guest-agent, SSH,
filesystem, repository, registry, DNS, or network access. It creates no
directory, container, image, volume, network, process, store row, queue item,
workflow, action request, dispatch, or worker job.

The closed result is:

```text
AgentInstallContainerValidationV1 = {
  schema: "agent-install-container-validation-v1",
  request_id: canonical UUIDv4,
  request_fingerprint: FingerprintV1,
  validated_at: UtcSecond,
  status: "valid_but_unsupported" | "rejected",
  reason_codes: ReasonCode[0..32],
  execution_supported: false,
  dispatch_allowed: false,
  mutation_allowed: false,
  replay_allowed: false,
  evidence: AgentInstallContainerAuditEvidenceV1,
  validation_fingerprint: FingerprintV1
}
```

`valid_but_unsupported` requires complete success and an empty reason list;
it still has every authority field false. `rejected` contains unique reason
codes in the first-applicable group order below. No partial success, warning
acceptance, coercion, default filling, fallback, or best-effort projection is
allowed.

1. `contract_malformed`, `contract_unknown_field`, `contract_out_of_bounds`,
   `request_fingerprint_mismatch`;
2. `request_not_current`, `request_replay_or_duplicate`;
3. `candidate_proof_missing`, `candidate_proof_mismatch`,
   `candidate_not_active`, `approval_proof_missing`,
   `approval_proof_mismatch`;
4. `subject_unsupported`, `destination_identity_mismatch`;
5. `artifact_unsupported`, `artifact_source_mismatch`,
   `image_not_digest_pinned`, `runtime_boundary_violated`,
   `filesystem_boundary_violated`, `network_boundary_violated`;
6. `validation_dependency_unavailable`, `validation_contract_failure`.

Malformed or hostile input receives no echo. Internal exceptions and
dependency failures are sanitized as unavailable/contract-failure outcomes;
logs and metrics contain only bounded reason code, request ID, fingerprint,
and correlation ID. They never contain artifact source text, image credentials,
paths beyond the bounded relative source path, provider payload, destination
raw identity, environment, command, token, or exception serialization.

## Idempotency, no replay, and audit evidence

Pure validation is deterministic for the same request, injected proofs, and
whole-second validation time. `request_id` is unique and immutable but is not
an idempotency key, retry token, lease, capability, or replay token. A future
acceptance boundary must atomically reserve both request ID and request
fingerprint before returning a result. Exact duplicate submission returns the
original validation evidence without revalidation or work; reuse of either ID
or fingerprint with different content is rejected. Concurrent duplicates
produce one logical result.

No validation result can be converted, retried, resumed, dispatched, or
executed. Expiry, restart, timeout, interrupted validation, missing durable
reservation evidence, or ambiguous completion is terminally non-executable.
A later execution release must require a new request and a new independent
execution approval; it may not replay a v0.22 request or validation. V0.22
adds no durable reservation store, so runtime intake remains absent.

`AgentInstallContainerAuditEvidenceV1` contains only:

- `evidence_schema="agent-install-container-audit-evidence-v1"`;
- request ID and request fingerprint;
- all six approved-candidate proof IDs/fingerprints;
- the exact sanitized subject tuple and destination fingerprint;
- artifact kind, source plan/path/service/content digest, image digest, and
  runtime/limit-policy fingerprint (not artifact source or runtime output);
- validation time, status, complete ordered reason codes, and all four fixed
  false authority fields; and
- a domain-separated evidence fingerprint over every preceding field.

Evidence is returned as a value only. V0.22 does not append to the existing
execution audit store or any new durable store, emit an event, or create an
authority consumer. Log presence is never proof of permission or completion.

## Exact risks and threats

- **Approval substitution:** an item-level, stale, foreign-operator, partial,
  or legacy approval is presented as execution authority. All exact v0.20 and
  v0.21 proofs and same-owner linkage are mandatory.
- **Destination replacement or confused deputy:** a resource ID is reused,
  moved, aliased, or resolved to another guest. Exact current incarnation
  fingerprint equality is required; no rebinding exists.
- **Artifact equivocation:** reviewed source and executable projection differ.
  Plan, path, service, content, normalized artifact, and immutable image
  identities are all fingerprint-bound; raw YAML is never accepted.
- **Container escape:** privileged mode, capabilities, devices, sockets,
  mounts, writable host paths, commands, or runtime extensions cross the
  boundary. The schema cannot represent them and validation fails closed.
- **Filesystem destruction or persistence:** traversal, symlink, absolute
  paths, volumes, host binds, or guest-system writes create hidden mutation.
  Only the bounded in-container tmpfs exists; validation performs no I/O.
- **Network exfiltration or lateral movement:** host/LAN/egress networking,
  DNS, published ports, proxy inheritance, and runtime pulls are prohibited.
- **Resource exhaustion:** unbounded memory, CPU, PID, tmpfs, document size,
  nesting, or arrays exhaust Agent, guest, or host resources. Closed literal
  limits and the 32 KiB request bound reject expansion.
- **Replay after ambiguity:** retries after timeout, crash, or lost response
  duplicate side effects. V0.22 performs none and later work must require
  durable atomic reservation plus a fresh independently approved request.
- **Validation as authority:** a successful dry-run is consumed as dispatch or
  permission. Status is `valid_but_unsupported`, every authority flag is
  false, and no production consumer or conversion path may exist.
- **Secret/error leakage:** hostile fields or runtime errors expose payloads,
  credentials, provider identities, paths, or exception details. Unknown
  fields are rejected and outputs/logs use the closed redacted vocabulary.
- **Feature activation drift:** configuration, environment, worker startup, or
  an old route silently enables installation. No v0.22 runtime flag or route
  exists; `install-container` remains outside supported intent sets.

## P0–P5 scope and acceptance

### P0 — Contract and threat-model freeze — complete

Freeze this exact schema, subject, proof linkage, artifact, runtime,
filesystem/network limits, validation result, reason precedence, idempotency,
no-replay, redaction, audit evidence, default-disabled posture, goldens, and
must-not-change contracts. P0 changes planning documentation only.

### P1 — Closed models and canonical fingerprints — complete

Add isolated Agent contract models and pure canonicalization/fingerprint
functions. Exhaust unknown fields, duplicate keys, type/bound violations,
fingerprint sensitivity, hostile strings, and determinism. Do not register a
route, intent, adapter, service, or worker.

### P2 — Pure proof and boundary validator — complete

Validate complete injected v0.20/v0.21 proof fixtures, subject lineage,
artifact normalization, freshness, fixed runtime/filesystem/network policy,
reason precedence, and redacted failures. Perform no I/O and preserve all
authority fields false.

### P3 — Validation evidence and dry-run service boundary — complete

Expose an internal dependency-injected validation service callable only from
tests and local composition, returning the closed result/evidence. Add no HTTP
route, Core client call, persistence, audit-store bridge, queue, or dispatch.

### P4 — Agent operator diagnostics — planned

Expose capability/status documentation showing `install-container` as
unsupported and default-disabled, plus bounded local validation diagnostics if
they can be proven non-authorizing. Add no enable switch, request intake,
execution control, Mission Control install UI, or mutation.

### P5 — Isolation and refusal closure — planned

Prove zero Core routes/callers, zero Core-to-Agent dispatch, zero supported
Agent intent registration, zero worker/provider/repository/guest/runtime
invocation, no production consumer of validation evidence, exact redaction,
no-replay, and full regression gates. Reconfirm the Home Assistant blocked
golden and do not tag, push, publish, deploy, or release automatically.

## Must-not-change contracts for P0–P5

- V0.16–v0.21 schemas, fingerprints, ownership, lifecycle, routes, stores,
  goldens, and non-authority semantics remain exact. V0.22 may validate copied
  closed values in pure code but may not mutate or add consumers to them.
- Existing ExecutionCandidate, legacy approval, audit, workflow, action,
  dispatch, execution, repository candidate, operational handling, and
  interrupted-side-effect no-replay contracts remain unchanged.
- Agent support remains exactly `update-compose-stack` for repository work and
  `restart-service` for operational handling. `install-container` is not added
  to supported planning, conversion, action, dispatch, or execution sets.
- Production operational capability remains exactly
  `restart-service/proxmox/qemu`; Provider Intent remains Proxmox QEMU
  `monitoring-policy`; Discovery remains GET-only and non-authoritative.
- No Core execution request route, Core-to-Agent dispatch, worker invocation,
  actual install, provider mutation, repository read/mutation, guest read or
  mutation, runtime probe, image pull/load, container creation, deployment,
  rollback, remediation, replay, workflow, background task, or authority event
  is introduced.
- The optional worker remains default-disabled. Backup/restore remains explicit
  operator maintenance and no backup schema is widened.

## Golden cases and later enablement

The positive golden is synthetic only: a complete same-owner active v0.20
envelope and exact v0.21 approval intent, an unchanged existing QEMU
incarnation, and the exact closed networkless artifact produce
`valid_but_unsupported` with no reasons and all authority fields false.
Fingerprint, ownership, freshness, destination, source, image, filesystem,
network, limit, or approval changes produce `rejected` and no work.

Home Assistant remains the blocked golden. Its v0.16 deployment artifact is
absent, so no v0.19 positive candidate, v0.20 envelope, or v0.21 approval
exists. Even a synthetic Home Assistant artifact requiring `/config`, host
networking, published ports, devices, privilege, environment, restart policy,
or image acquisition is outside this v1 artifact shape and must be rejected.

V0.22 enables later work to reuse a frozen Agent parser, validator, policy
boundary, proof linkage, and audit-evidence shape when designing a separate
Core execution request and dispatch release. It still refuses every runtime
request, all installation and mutation, all artifact acquisition, all
networked or persistent workloads, all general Compose behavior, Home
Assistant deployment, and every execution attempt lacking a new independently
frozen authority, durable no-replay reservation, recovery, and rollback
contract.
