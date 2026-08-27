# Prospective Installation Destination Assessment v1

Status: **Atlas v0.17 P0 frozen, with the explicit P1 conformance amendment below**.

This is the normative v0.17 contract. It grants no installation, planning,
approval, candidate, workflow, provider, repository, dispatch, Agent, worker,
or execution authority. The release baseline is `atlas-v0.16.0` at
`538a70cd34ce758bda40c5a200acdbdc837694a5`; this P0 was prepared from
`6ddb87234dae37c859216ff9c4faa564f0df7dd8`.

## P0 normative amendment — P1 conformance correction

The historical P0 contract remains frozen at commit
`20357ad1a6eb12721556ee1183fc753fa82d119d`. P1 implementation review exposed
three places where the runtime could not be made unambiguous without recording
an explicit normative correction: the immutable selection tuple and selection
fingerprint include the exact QEMU `resource_id`; every terminal timestamp is
at or after `selected_at`; and fingerprint canonicalization is the documented
restricted JCS subset (fixed ASCII object keys, NFC strings, null, booleans,
IEEE-754 safe integers, lists, and objects), not a general-purpose JCS API.

These corrections add no authority and do not rewrite the historical P0
commit. This amendment must be committed explicitly with P1, or as a separate
documentation commit before the P1 runtime commit.

## Release boundary and terminology

Atlas v0.17 is **Prospective Installation Destination Assessment**. It ends
after an authenticated operator can select one exact, currently observed
Proxmox QEMU guest incarnation as a bounded prospective installation
destination and request an ephemeral, deterministic, non-authorizing
installation admission assessment.

The contract names are `ProspectiveInstallationDestinationV1`,
`InstallationDestinationSelectionV1`, `InstallationInterestV1`, and
`InstallationAdmissionAssessmentV1`. “ApprovedInstallationTarget”, “approved
target”, “install-ready target”, and “executable target” are prohibited terms.

Installing software inside an existing QEMU guest and provisioning or creating
a QEMU VM on Proxmox are distinct execution paths. V0.17 concerns neither. It
only selects an already-observed, existing guest for possible future
assessment. V0.18 may first consider a separately frozen, authoritative
in-guest capability and identity contract covering transport, runtime,
privileges, target-scoped compatibility, and independent Agent support. No
v0.17 record can satisfy or be grandfathered into that contract.

An existing Proxmox QEMU identity establishes none of: guest OS or
architecture; guest-agent availability; hostname, IP, or DNS; credentials or
authentication; privileges; Docker, Podman, containerd, or Compose;
filesystem or deployment path; CPU, RAM, disk, or storage-class suitability;
network, firewall, or egress; SELinux, AppArmor, or cgroups; existing
application/container collisions; backup or rollback support; repository
checkout availability; a trusted in-guest runner or Agent; transport;
target-scoped compatibility; installability; readiness; or execution
permission.

## Destination identity and eligibility

`ProspectiveInstallationDestinationV1` is a sanitized, server-enumerated view
whose tuple is exactly `provider=proxmox`, `resource_type=qemu`, and
`placement_kind=existing-guest`. It follows the existing opaque operational
target fingerprint pattern as identity precedent but does not reuse
`OperationalTargetReference` and never emits raw `vmgenid` or provider payload.

Selection requires exact re-resolution of one resource and comparison of its
opaque current fingerprint. Wildcard, `all`, unknown, partial, and ambiguous
selectors are invalid. The fingerprint commits to the exact guest incarnation
and placement, including its Proxmox node. Migration or any node movement,
replacement, or fingerprint change makes the selection terminally stale.
There is no silent rebinding and no in-place identity refresh.

Running and stopped non-template guests are selectable when exact identity is
currently available. A stopped guest is not thereby installable. Templates,
locked guests, and guests observed as migrating are not selectable. Unknown
state or unavailable/ambiguous identity fails closed. A later state change may
make assessment unavailable but never refresh the selection.

## InstallationDestinationSelectionV1

This is a narrow, durable, operator-authored record with immutable identity
fields and a monotonic terminal lifecycle. Its authority
is exactly: **Atlas may remember that the operator selected this exact observed
QEMU incarnation as a prospective installation destination for future
assessment.** It grants no other authority.

The closed record contains:

- `schema_version`, literal `installation-destination-selection-v1`;
- `selection_id`, a server-generated opaque UUID;
- the literal provider/resource/placement tuple above, including the exact
  QEMU `resource_id`;
- `selected_destination_fingerprint`, an opaque lowercase SHA-256 value;
- `selected_at` and `expires_at`, server-owned UTC whole-second timestamps;
- `selected_by`, a stable, sanitized authenticated-principal ID (never a
  display name, token, credential, or provider identity);
- `request_digest`, the canonical client selection-request digest and
  idempotency identity;
- `selection_fingerprint`, the canonical immutable-record fingerprint; and
- `status`, one of `active`, `cancelled`, `expired`, or `stale`, plus
  `terminated_at` (`null` only while active).

Selections are **operator-scoped**: only the selecting principal can read,
cancel, or bind an interest to one. This permits selecting independently of an
item or plan while preventing one operator's remembered choice from silently
authorizing another's request. It is neither global, item-scoped, nor
plan-scoped.

An active selection expires at the half-open boundary
`evaluation_time >= expires_at`; `expires_at` is exactly 24 hours after
`selected_at`. Expiry, cancellation, and stale identity are irreversible
terminal states. DELETE is idempotent: it changes an active record to
`cancelled`, preserves an immutable tombstone, and does not delete audit
identity. Cancelling a terminal record returns its existing terminal state.
Every terminal transition uses a UTC whole-second `terminated_at` that is not
before `selected_at`.
Reselection always creates a new selection ID, digest, timestamps, and identity
comparison; it never reactivates or edits the old record. Multiple active
selections by one operator are permitted, bounded to 16; selection is never an
“active target” pointer.

## InstallationInterestV1

`InstallationInterestV1` is a closed, ephemeral, non-authorizing input for one
assessment request. It is not stored as durable intent, pending work, a queue
item, or a replayable instruction and has no Agent or candidate consumer.

It contains `schema_version=installation-interest-v1`, exact `item_id`, exact
`catalog_entry_id`, exact InstallationPlan fingerprint, literal
`interest_kind=install-container-assessment`, exact `selection_id`, exact
selected destination fingerprint, server-owned `requested_at`,
`expires_at=requested_at+5 minutes`, and a canonical request digest called the
interest fingerprint. All linkage is exact and operator scope must match.

A duplicate idempotency key with the same canonical request digest during its
five-minute window returns the same assessment bytes/fingerprint when the
same server evaluation instant was retained in the bounded idempotency cache;
otherwise it is recomputed as a new request. Reuse with different canonical
content is a sanitized `409 idempotency_conflict`. The cache is presentation
and retry state only, has no durable intent or authority, and is discarded at
expiry/restart. A new request after expiry requires a new idempotency key.

Plan-fingerprint mismatch yields `installation_interest_plan_stale`;
selection-ID/fingerprint mismatch or terminal replacement yields
`installation_interest_destination_stale`; an expired interest yields
`installation_interest_expired`. An expired selection independently yields
`destination_selection_expired`. A replacement is a new interest and new key,
never mutation of an earlier interest. Sanitized audit may record principal,
IDs, digests, timestamps, outcome status, and reason codes, but never an
executable payload, raw provider data, credential, hostname, IP, or durable
installation intent. V0.18 and later must not consume v0.17 interest, retry, or
audit records as authority.

## InstallationAdmissionAssessmentV1

The assessment is a pure, deterministic, immutable, non-authorizing read
model. Its exact inputs are the complete current `InstallationPlan`, its exact
fingerprint, the current selection or absence, selected destination
fingerprint or absence, exact current re-resolution result, ephemeral interest
or absence, server-owned evaluation time, and the fixed capability fact
`agent_install_container_supported=false`.

The closed output contains `schema_version=installation-admission-assessment-v1`,
plan `item_id` and `catalog_entry_id`, exact `plan_fingerprint`, `selection_id`
or null, selected destination fingerprint or null, current destination
fingerprint or null, interest fingerprint or null, `assessment_status`,
`reason_codes`, `candidate_eligibility_evaluated=false`, and the assessment
fingerprint. The only statuses are `blocked` and
`preconditions_satisfied_but_unsupported`.

Every applicable reason is returned once in this canonical order:

1. `installation_plan_conflicted`
2. `installation_plan_missing_deployment_artifact`
3. `installation_plan_incompatible`
4. `installation_plan_stale_evidence`
5. `installation_plan_insufficient_information`
6. `destination_selection_missing`
7. `destination_selection_expired`
8. `destination_unavailable`
9. `destination_identity_unavailable`
10. `destination_replaced_or_moved`
11. `destination_installation_capability_unknown`
12. `installation_interest_missing`
13. `installation_interest_expired`
14. `installation_interest_plan_stale`
15. `installation_interest_destination_stale`
16. `agent_install_container_unsupported`

Plan status maps to its matching reason except `plan_ready_for_review`. A
cancelled/stale selection is treated as unavailable and, where re-resolution
proves identity change/movement, also replaced or moved. Missing current
identity uses `destination_identity_unavailable`; a positive mismatch uses
`destination_replaced_or_moved`. Because v0.17 has no authoritative in-guest
capability contract, every otherwise resolvable destination has
`destination_installation_capability_unknown`. Because Agent lacks
install-container support, every assessment has
`agent_install_container_unsupported`.

`preconditions_satisfied_but_unsupported` is allowed only when the plan is
`plan_ready_for_review`, the selection is present/active/current, interest
linkage is present/unexpired/current, and the only reasons are
`destination_installation_capability_unknown` and
`agent_install_container_unsupported`. It implies no candidate eligibility,
planning eligibility, deployment readiness, target approval, or execution
approval. Every other result is `blocked`.

## Canonical fingerprints

All three fingerprints use SHA-256 over UTF-8 RFC 8785 JCS of a closed object
whose strings are already Unicode NFC, prefixed by the ASCII domain and one NUL
byte. Digest output is lowercase hexadecimal. Unknown fields, duplicate keys,
non-NFC text, invalid UTF-8, and non-canonical values fail before hashing.
The implementation is the frozen restricted JCS subset needed by these closed
domains: fixed ASCII object keys, NFC strings, null, booleans, IEEE-754 safe
integers, lists, and objects; it is not a general-purpose RFC 8785 API.
Timestamps use exact UTC whole seconds (`YYYY-MM-DDTHH:MM:SSZ`); no rounding,
offset, fraction, or local time is accepted. Null is the JSON literal `null`,
distinct from absence; closed fingerprint objects contain every specified key.

- Selection fingerprint domain
  `atlas:installation-destination-selection:v1` includes
  schema, selection ID, tuple including `resource_id`, selected fingerprint,
  timestamps, selecting
  principal ID, and request digest. It excludes status and
  termination time so lifecycle updates do not rewrite immutable identity,
  and excludes labels, raw identity, provider payload, display data, and
  availability.
- Interest domain `atlas:installation-interest:v1` includes schema, exact
  item/catalog/plan identities, literal kind, selection ID, selected
  fingerprint, requested/expiry times, and canonical client idempotency key.
  It excludes current provider observations, plan body, audit data, and all
  execution material.
- Assessment domain `atlas:installation-admission-assessment:v1` includes
  schema, plan/item/catalog identity, selection ID/null, selected and current
  fingerprints/null, interest fingerprint/null, exact evaluation time, fixed
  false capability fact, status, the complete reason array in canonical order,
  and `candidate_eligibility_evaluated=false`. It excludes display text, raw
  plan/provider payloads, credentials, network identifiers, audit metadata,
  cache state, and implementation diagnostics.

The selection `request_digest` uses the separate domain
`atlas:installation-destination-selection-request:v1` and includes schema,
principal ID, server-issued enumeration token, resolved provider/resource/
placement tuple, resolved selected fingerprint, and client idempotency key; it
excludes the later-generated selection ID and timestamps. The interest request
digest is its interest fingerprint. Fingerprints identify facts and requests
only and convey no authority.

## Home Assistant golden case

The normative case is `item_id=home-assistant`,
`catalog_entry_id=d5-home-assistant`, deployment artifact
`compose/home-assistant.yaml`, service `home-assistant`. The artifact is absent,
so status remains `missing_deployment_artifact` and the exact InstallationPlan
fingerprint remains
`34b55477f84fc03fa4b31c57ffc8213ba884b61791f3e6adb8f484fb67d0771a`.

A destination may be selected independently of plan readiness. An ephemeral
interest exactly bound to that plan fingerprint and selection may be assessed.
With a present/current selection and interest, the assessment remains
`blocked`, with reasons in this exact applicable order:
`installation_plan_missing_deployment_artifact`,
`destination_installation_capability_unknown`,
`agent_install_container_unsupported`. Target facts never override, repair,
or substitute for the missing repository artifact. The existing
`InstallationPlanCandidateProjection` remains exactly
`candidate_created=false`, `planning_allowed=false`, `candidate=null`.

## Dependency and authority isolation

- `installation_plan` must not import destination, interest, provider,
  execution, Agent, workflow, approval, or dispatch code.
- Destination contracts must not import execution-candidate models.
- Interest and assessment must not import candidate creation, Agent, workflow,
  approval, worker, provider mutation, repository execution, or operational
  dispatch.
- Provider and Provider Intent must not import installation contracts.
- Mission Control receives closed sanitized API models only; raw `vmgenid`,
  provider payloads, credentials, and network addresses never reach it.
- No execution subsystem may consume v0.17 selection, interest, assessment,
  retry-cache, tombstone, or audit records.

Repository execution stays exactly `update-compose-stack`; operational
capability stays exactly `restart-service/proxmox/qemu`; Provider Intent stays
identity-bound Proxmox QEMU `monitoring-policy` only. Core may recognize the
`install-container` vocabulary/classification, but Atlas Agent does not support
its planning. Discovery remains GET-only and non-authoritative. Existing
approval stages are unchanged; the execution-worker remains optional and
default-disabled; backup/restore remains operator-maintenance tooling. There
is no automatic remediation, conversational execution, automatic
commit/push/tag/release, or replay after an interrupted side effect.

## Future guarded API boundary (P3)

The conceptual routes are:

- `GET /api/v1/installation/destinations` enumerates only bounded,
  server-observed selectable destinations;
- `POST /api/v1/installation/destination-selections` creates a selection from
  a server-issued opaque enumeration token;
- `GET /api/v1/installation/destination-selections/{selection_id}` reads the
  caller's sanitized record;
- `DELETE /api/v1/installation/destination-selections/{selection_id}`
  terminally cancels it; and
- `POST /api/v1/installation/admission-assessments` accepts one bounded
  interest and returns one assessment.

All require an authenticated operator. Mutations require the existing CSRF
token and trusted-origin validation; GETs remain side-effect free. Unsupported
methods return `405` with a precise `Allow`; unauthenticated/CSRF/origin
failures use existing sanitized `401/403`; malformed, unknown-field,
oversized, non-enumerated, or ambiguous input is sanitized `400/413/422`;
missing or cross-operator IDs are indistinguishable `404`; stale/expired state
is represented by the assessment or sanitized `409`; dependency failure is
sanitized `503`. Bodies are closed JSON, maximum 8 KiB, maximum nesting 4, and
reject duplicate keys. Idempotency keys are required on POST, ASCII 16..128
bytes, and scoped to authenticated principal plus route.

Callers may supply no URL, hostname, IP, provider payload, raw identity,
`vmgenid`, command, credential, capability claim, plan body, or arbitrary
selector. Targets are server-enumerated and re-resolved. No route creates a
candidate, permits planning, creates a workflow/approval/action/dispatch,
invokes Agent/worker, or mutates a provider or repository.

## Future Mission Control boundary (P4)

The primary label is exactly **Select as prospective installation
destination**. Adjacent copy must say that selection is not approval, does not
establish guest capability or installability, and cannot install or plan.
Assessment renders status and all ordered blockers without collapsing unknown
into ready. Controls or navigation labelled or meaning Install, Execute, Plan,
Approve, Convert, Dispatch, or workflow authority are prohibited.

## Lifecycle, storage, restore, and concurrency

Selections and terminal tombstones are durable security/audit state; interests
and assessments are ephemeral except sanitized audit and the bounded retry
cache. Active selections retain until terminal; tombstones and audit retain 90
days after termination and may then be purged by explicit operator maintenance.
Expiry is evaluated from server time on every read/use and lazily records an
expired tombstone; a delayed write cannot extend validity.

Backup/restore classifies selection/tombstone/audit data as operator-maintenance
metadata, never execution state. Restore preserves IDs, fingerprints,
timestamps, terminal state, and expiry; already expired records restore as
expired and cancelled/stale/expired records never reactivate. Restore never
rebinds identity or reconstructs interest/cache authority. Downgrade must
retain unknown v0.17 records inert or require explicit operator-maintenance
removal; older code must not interpret them. Schema migration is additive and
identity-preserving; it cannot refresh fingerprints, extend expiry, or change
scope. Proxmox guest migration/node movement invalidates v1 selection.

Creation, cancellation, expiry, and stale transition use compare-and-swap on
record version. At most one concurrent transition wins; retries observe the
same terminal state. Same-key equivalent concurrent POSTs converge on one
selection/assessment result, and same-key conflicts return `409`. No expired,
cancelled, stale, restored, migrated, or superseded record is grandfathered
or reactivated.

## Threats and later validation

Later implementation must test closed schemas and bounds; exact identity and
node movement; state eligibility; expiry boundaries; cancellation/reselection;
operator isolation; idempotency convergence/conflict; stale plan/destination
linkage; canonical fingerprints; complete reason ordering and status
precedence; the Home Assistant golden; sanitized API/CSRF/method/error behavior;
UI copy and prohibited controls; persistence/restore/downgrade/concurrency;
forbidden imports; and exact capability, approval, worker, backup, GET-only,
no-remediation, no-replay, and no-side-effect regressions.
