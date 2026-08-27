# Installation Capability Assessment v1 planning contract

Status: **Atlas v0.18 P0 planning selected; no implementation exists**.

This document is the planning boundary for Atlas v0.18, **Installation
Capability Assessment**. It grants no installation, target approval,
candidate, workflow, dispatch, Agent, worker, provider, repository, or other
mutation authority.

## Repository inspection baseline

This plan starts from current `main` at `5731b9f`, after the released
`atlas-v0.17.0` tag. V0.16 already supplies the immutable target-free plan and
closed requirement inputs. V0.17 already supplies operator-owned selection,
its 24-hour lifecycle, exact selected/current identity comparison, and
sanitized Proxmox/QEMU existing-guest resolution.

The released provider projection currently supplies exact identity,
lifecycle, template/lock/migration state, and a sanitized configured-memory
total. It does not yet publish configured CPU count, configured virtual-disk
capacity, or the QEMU guest-agent configuration bit as capability facts.
Those are prospective P1 adapter work, not P0 evidence and not permission to
query inside the guest. P0 is documentation only.

## Release boundary

V0.18 combines three read-side inputs for one exact item and one exact current
prospective destination:

1. the complete v0.16 `InstallationPlan` and exact plan fingerprint;
2. the caller-owned v0.17 `InstallationDestinationSelectionV1`, exact selected
   destination fingerprint, and exact current destination re-resolution; and
3. bounded, sanitized provider capability facts observed through the existing
   Proxmox control-plane read path.

The result is an ephemeral, deterministic, immutable
`InstallationCapabilityAssessmentV1`. It answers only: **which installation
requirements are supported, contradicted, or still unknown according to the
facts Atlas can read now?** It does not answer whether Atlas may install, and
it cannot make an installation possible.

The assessment is not an extension of Provider Intent, operational dispatch,
repository execution, or Agent capability. It is not an approved target,
installation intent, proposal, candidate, workflow, approval, action request,
dispatch, deployment specification, command, or executable recipe. It has no
consumer outside its GET-only/read-only projection and presentation surface.

## Provider capability fact boundary

`ProviderInstallationCapabilityFactsV1` is a closed, sanitized observation
bound to the exact provider/resource/placement tuple, current destination
fingerprint, and server-owned observation time. V1 is limited to
`provider=proxmox`, `resource_type=qemu`, and
`placement_kind=existing-guest`.

Facts may be derived only from already-permitted Proxmox control-plane reads
used to resolve the selected QEMU guest. A later adapter may read the same
guest configuration resource, but may not add a guest-agent API, guest network
access, or provider write. The bounded initial fact vocabulary is:

- current destination identity and placement are exact;
- current lifecycle state is observed;
- configured virtual CPU count, configured memory, and provider-visible
  virtual-disk capacity are observed when unambiguous; and
- the Proxmox QEMU guest-agent configuration flag is observed as configured,
  not configured, or unknown.

Each fact carries its closed fact code, `observed`, `not_observed`,
`malformed`, `conflicted`, or `unavailable` observation state, a validated
typed value or null, sanitized provider source identity, observation time, and
destination fingerprint. Unknown, absent, malformed, stale, partial,
ambiguous, mismatched, moved, or conflicting data fails closed and is never
silently omitted or converted to support.

The guest-agent configuration flag proves only a provider configuration bit.
It proves none of guest-agent process health, reachability, command support,
authentication, transport, credentials, privileges, operating system,
architecture, hostname, address, DNS, Docker, Podman, containerd, Compose,
filesystem or deployment paths, storage class or free space, network/egress,
firewall, security policy, collisions, backup/rollback, repository checkout,
trusted runner, Atlas Agent presence, target-scoped compatibility,
installability, readiness, or permission.

V0.18 performs no guest-agent call, SSH connection, network scan, credential
lookup, in-guest command, runtime probe, package query, filesystem read, write,
or provider mutation. Raw provider payloads, raw VM generation identity,
addresses, hostnames, credentials, tokens, URLs, paths, and commands never
enter a fact or reach Mission Control.

Inventory utilization (`cpu`, `mem`) is monitoring data and must not be used
as configured capacity. Inventory `maxmem` may corroborate configured memory
only under a P0-frozen reconciliation rule. Disk capacity means only the sum
of unambiguously parsed configured virtual-disk sizes; it is not filesystem
size, allocated bytes, free space, storage health, or proof of a deployment
path. Unsupported syntax, ambiguity, or disagreement fails closed rather than
producing a partial total.

## Requirement comparison and outcome

The pure comparison layer maps only explicit, compatible
`InstallationPlan` requirements to facts in the closed provider vocabulary.
It must preserve the plan's blockers, risks, assumptions, missing facts,
provenance, and freshness without repairing, overriding, or reclassifying the
plan. Item-scoped or target-free compatibility is not promoted to
target-scoped compatibility.

Every requirement comparison has one of four non-authorizing results:
`satisfied`, `not_satisfied`, `unknown`, or `not_assessable`. Positive results
require an exact current destination identity, an unexpired observation, a
single valid value, and an explicit comparison rule. Unsupported requirement
kinds are `not_assessable`; missing or unreliable facts are `unknown`;
contradictions are `not_satisfied`. No default, inference, provider label, or
display string may create `satisfied`.

For v1 the only numeric requirements eligible for `satisfied` or
`not_satisfied` are CPU cores, memory, and storage minimums compared with
like-unit configured-capacity facts. Lifecycle and guest-agent configuration
are displayed observations and may be assessment gates, but neither satisfies
a plan prerequisite. Capability IDs, GPU, GPU memory, architecture, operating
system, runtime, device, port, internet, LAN, application relationship, and
every in-guest requirement are always `not_assessable`. Any unit conversion
must be exact and P0-frozen; rounding cannot create a positive result.

The closed assessment statuses are:

- `blocked`: the plan is not `plan_ready_for_review`, the selection is not
  active/current, identity is unavailable or changed, or any assessed
  requirement is `not_satisfied`;
- `insufficient_provider_facts`: the plan and destination linkage are current
  but at least one required comparison is `unknown` or `not_assessable`; and
- `requirements_satisfied_but_non_authorizing`: every requirement that v1 is
  permitted to compare is `satisfied`, no plan/destination blocker applies,
  and required in-guest and execution facts remain explicitly outside the
  provider fact contract.

`requirements_satisfied_but_non_authorizing` does not mean capable,
installable, ready, supported, approved, executable, or deployable. Every
assessment includes `candidate_eligibility_evaluated=false`,
`candidate_creation_allowed=false`, `agent_execution_supported=false`, and
`provider_mutation_allowed=false`. These are invariants, not caller inputs.

The fingerprint is domain-separated SHA-256 over the repository's frozen
restricted-JCS/NFC subset and includes the exact plan, selection, selected and
current destination, provider-fact-set, comparison, status, evaluation-time,
and fixed-false invariant fields. It identifies read facts only and conveys no
authority. A new observation or evaluation produces a new ephemeral
assessment; there is no persistence, lifecycle, idempotency identity, replay,
approval, or conversion semantics.

## API and presentation boundary

P3 may add one authenticated, bounded GET-only projection under the existing
installation assessment namespace. The final path and closed wire schema must
be frozen before implementation. It accepts no caller capability facts,
provider payload, address, credential, artifact, command, plan body, target
selector, or arbitrary source material. POST, PUT, PATCH, and DELETE siblings
must be rejected and absent from OpenAPI.

Mission Control may present exact plan linkage, selected/current destination
linkage, sanitized provider facts, comparisons, unknowns, contradictions, and
the non-authorizing outcome. It must not expose Install, Prepare, Approve,
Execute, Convert, Create candidate, Start workflow, Dispatch, Retry action, or
equivalent controls or authority-suggesting navigation.

## Must-not-change contracts

All P0-P5 work must preserve these contracts exactly:

- v0.16 `InstallationPlan v1` remains item-scoped, ephemeral, immutable,
  target-free, and non-authorizing; its schema, statuses, fingerprint,
  precedence, Home Assistant golden, and fail-closed candidate projection do
  not change.
- v0.17 selection, interest, and admission-assessment schemas, identity,
  lifecycle, storage, expiry, fingerprint, routes, and non-authority semantics
  do not change and are not grandfathered into authority. V0.18 may read the
  selection and current re-resolution; it must not widen v0.17 interest or
  mutate the v0.17 assessment.
- No assessment creates or enables a candidate, approval, workflow, action
  request, dispatch, Agent execution, worker invocation, provider mutation,
  repository mutation, install, update, restart, deployment, rollback,
  remediation, release, or replay.
- Atlas Agent repository support remains exactly `update-compose-stack` and
  Agent operational handling remains exactly `restart-service`;
  `install-container` remains unsupported.
- Production operational capability remains exactly
  `restart-service/proxmox/qemu`; Provider Intent remains identity-bound
  Proxmox QEMU `monitoring-policy`; repository execution remains exactly
  `update-compose-stack`.
- Discovery remains GET-only and non-authoritative. Provider facts are
  observations, not curated authority, approval, permission, or execution
  capability, and cannot override curated catalog data.
- Existing independent approval stages, interrupted-side-effect no-replay
  behavior, optional default-disabled execution worker, and operator-only
  backup/restore contracts remain unchanged.
- No automatic remediation, conversational execution, commit, push, tag,
  publication, data migration, new durable intent, queue, worker job, or
  background/startup/scheduled capability probe is introduced.

## P0-P5 acceptance shape

P0 is documentation-only and freezes the exact schemas, fact vocabulary,
comparison table, freshness and conflict precedence, fingerprint, route,
presentation, dependency, threat, and golden-case contracts before runtime
work. P1-P5 must not begin by inventing a broader authority interpretation.

The Home Assistant golden remains anchored to the absent
`compose/home-assistant.yaml` and exact v0.16 plan fingerprint
`34b55477f84fc03fa4b31c57ffc8213ba884b61791f3e6adb8f484fb67d0771a`.
Provider facts cannot repair that blocker. Its v0.18 assessment therefore
remains `blocked`, candidate eligibility is not evaluated, and all candidate,
Agent, workflow, dispatch, worker, repository, and provider mutation fields
remain false or absent.
