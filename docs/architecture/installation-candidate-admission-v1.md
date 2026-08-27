# Installation Candidate Admission v1 planning contract

Status: **Atlas v0.19 P0 documentation-only planning**.

This document freezes the proposed boundary for Atlas v0.19, **Installation
Candidate Admission**. It introduces no runtime behavior. It grants no
installation, execution-candidate, approval, workflow, dispatch, Agent, worker,
provider, repository, in-guest, deployment, rollback, or release authority.

## Repository inspection baseline

Planning starts from current `main` at `a21154b`, after released tag
`atlas-v0.18.0` at `f12a89c`. V0.16 supplies a target-free immutable
`InstallationPlan`; v0.17 supplies an operator-owned expiring selection of one
exact observed Proxmox QEMU existing-guest incarnation; v0.18 supplies an
ephemeral provider capability assessment whose strongest result is explicitly
non-authorizing. None currently creates installation authority.

The existing `ExecutionCandidate` subsystem predates these contracts and is
out of scope. V0.19 must not reuse its model name, store, intake, planning,
approval, workflow, audit, route, or execution consumers.

## Narrow admission boundary

V1 is a pure, server-owned, read-side decision over exactly three complete
records:

1. one v0.16 `InstallationPlan v1` and exact fingerprint;
2. one caller-owned v0.17 `InstallationDestinationSelectionV1`, its exact
   selected fingerprint, and exact current re-resolution; and
3. one v0.18 `InstallationCapabilityAssessmentV1` bound to that exact plan,
   selection, current destination fingerprint, provider fact set, and
   evaluation time.

The result is an ephemeral `InstallationCandidateAdmissionV1`. It answers only:
**do these exact read-side records meet the closed prerequisites for Atlas to
describe one bounded, non-executable installation candidate now?** It does not
answer whether the target is approved or whether Atlas may, can, or will
install anything.

The closed statuses are:

- `not_admitted`: no candidate record is returned; and
- `admitted_but_non_executable`: the closed prerequisites match and a bounded
  candidate record is returned, but no approval or execution authority exists.

Admission is positive only when all of the following hold at one server-owned
evaluation time:

- plan status is exactly `plan_ready_for_review`;
- the selection is caller-owned, active, unexpired, and exactly current;
- selected and current destination fingerprints are equal;
- the capability assessment is unexpired, internally fingerprint-valid,
  exactly linked to the same plan, item, catalog entry, selection, selected and
  current destination, and is exactly
  `requirements_satisfied_but_non_authorizing`;
- every fixed-false v0.18 authority invariant remains false; and
- every input is closed-schema valid, complete, unambiguous, and within its
  frozen freshness window.

No partial success exists. Missing, malformed, stale, expired, conflicted,
blocked, unknown, `not_assessable`, moved, replaced, cross-operator,
fingerprint-mismatched, or linkage-mismatched input is `not_admitted` with
`candidate_record=null`. Inputs are never repaired, refreshed, inferred, or
silently substituted during evaluation.

## Closed reason precedence

P0 freezes this first-applicable group order; all applicable reasons within a
group use their frozen lexical enum order:

1. `input_invalid` or `input_unavailable`;
2. `installation_plan_not_review_ready`;
3. `destination_selection_not_active`, `destination_selection_expired`,
   `destination_identity_unavailable`, or `destination_replaced_or_moved`;
4. `capability_assessment_stale`, `capability_assessment_mismatched`, or
   `capability_assessment_not_admissible`; and
5. `authority_invariant_violated`.

Any reason produces `not_admitted`. Sanitized dependency/reader failures are
no-result errors, not admission results, when trustworthy closed inputs cannot
be assembled. Authentication and ownership failures remain indistinguishable
under existing API conventions.

## InstallationCandidateRecordV1

The positive record is a closed immutable value containing only:

- `schema="installation-candidate-record-v1"`;
- `item_id` and `catalog_entry_id`;
- exact plan fingerprint;
- selection ID, selected destination fingerprint, and equal current
  destination fingerprint;
- capability-assessment and provider-fact-set fingerprints;
- `evaluated_at` and `valid_until`, where `valid_until` is the earliest frozen
  expiry across its inputs;
- fixed literals `approved=false`, `executable=false`, `deployable=false`,
  `dispatchable=false`, and `agent_execution_supported=false`; and
- a domain-separated record fingerprint.

It contains no arbitrary text; command; executable payload; Compose or artifact
body; repository ref or mutation instruction; URL, address, hostname, raw
provider payload, raw identity, credential, token, or secret; approval or
confirmation; installation intent; proposal; workflow, action, dispatch,
worker-job, deployment, rollback, retry, or replay identifier; or extension
map. Unknown fields are rejected.

The record fingerprint uses SHA-256 over UTF-8 restricted RFC 8785 JCS with
NFC strings, prefixed by `atlas:installation-candidate-record:v1` and one NUL
byte. It includes every record field except the fingerprint itself. The
admission result fingerprint uses the separate domain
`atlas:installation-candidate-admission:v1` and includes the exact input
fingerprints, evaluation time, status, complete ordered reasons, nullable
record fingerprint, and fixed-false authority invariants. Fingerprints convey
identity only, never authority.

The record is not persisted. It has no ID separate from its fingerprint, CRUD
lifecycle, idempotency key, tombstone, approval state, conversion method,
retry/replay semantics, queue, event, background refresh, or consumer. Expiry
requires a new read and complete re-evaluation; it never triggers work.

## API and presentation boundary

P3 may add one authenticated GET-only projection under the installation
namespace after the exact path and wire schema are frozen. The server assembles
all inputs. The caller may provide bounded identifiers only, never a plan,
selection body, capability facts, assessment body, candidate body, target
selector, command, artifact, credential, address, or arbitrary source data.
POST, PUT, PATCH, and DELETE siblings are absent from OpenAPI and rejected.

Mission Control may show exact source linkage, freshness, ordered reasons, the
nullable record, and explicit language that admitted means neither approved nor
executable. It exposes no Admit, Create, Approve, Install, Prepare, Execute,
Convert, Start workflow, Dispatch, Deploy, Retry, Rollback, or equivalent
control, navigation, or mutation call.

## Dependency and authority isolation

- V0.16, v0.17, and v0.18 packages must not import v0.19 admission code.
- Admission code may import only their closed read models and reviewed
  read-side assemblers; it must not import existing execution-candidate,
  approval, workflow, dispatch, Agent, worker, provider-mutation,
  repository-execution, deployment, rollback, or release modules.
- No production subsystem may consume an admission result or candidate record.
- Provider, Provider Intent, Agent, worker, and execution packages must not
  import v0.19 contracts or recognize their record markers.
- Evaluation performs no network access, provider refresh, guest-agent call,
  SSH, scan, credential lookup, filesystem or repository mutation, in-guest
  read/write, persistence, audit write, event emission, or clock-derived
  extension of input validity.

## Home Assistant golden case

The existing Home Assistant artifact `compose/home-assistant.yaml` remains
absent. Its v0.16 plan remains `missing_deployment_artifact` at fingerprint
`34b55477f84fc03fa4b31c57ffc8213ba884b61791f3e6adb8f484fb67d0771a`.
Neither a destination nor provider facts repair that blocker. Its v0.18
assessment remains blocked and its v0.19 result is therefore exactly
`not_admitted`, includes `installation_plan_not_review_ready`, and has
`candidate_record=null`. Atlas Agent continues to reject `install-container`.

## P0-P5 scope

- **P0, documentation only:** freeze schemas, linkage, precedence,
  fingerprints, freshness, API/UI, threats, isolation, and golden cases. Make
  no runtime or release change.
- **P1, pure evaluation:** implement deterministic fail-closed input validation
  and admission with exhaustive unit and hostile-input tests; no I/O or state.
- **P2, bounded record:** implement the closed ephemeral candidate record and
  canonical fingerprints; prove payload exclusion and absence of consumers.
- **P3, GET-only Core:** add one authenticated server-assembled read projection
  with ownership, bounds, redaction, OpenAPI, method, and zero-mutation tests.
- **P4, read-only Mission Control:** render linkage, reasons, expiry, and
  non-authority without action controls, navigation, or mutation calls.
- **P5, isolation and closure:** run structural, behavioral, API/UI, security,
  golden, parity, full-regression, and exact-source release gates; do not
  automatically commit, tag, push, publish, deploy, or release.

## Must-not-change contracts

- V0.16 `InstallationPlan v1`, its Home Assistant golden, and its existing
  fail-closed candidate projection remain exact and non-authorizing.
- V0.17 selection, interest, and assessment identity, ownership, lifecycle,
  expiry, storage, routes, and non-authority remain exact. Selection is not
  target approval.
- V0.18 fact and assessment schemas, comparisons, routes, fixed-false fields,
  strongest non-authorizing status, ephemerality, and lack of consumers remain
  exact.
- Existing `ExecutionCandidate` models, intake, stores, approvals, workflows,
  routes, and execution behavior do not change and never consume v0.19 data.
- Repository execution stays exactly `update-compose-stack`; operational
  capability stays exactly `restart-service/proxmox/qemu`; Provider Intent
  stays identity-bound Proxmox QEMU `monitoring-policy`; `install-container`
  stays unsupported by Atlas Agent; Discovery stays GET-only/non-authoritative.
- No automatic admission, approval, confirmation acceptance, candidate
  execution, Agent install-container execution, worker invocation, provider or
  repository mutation, in-guest read or mutation, workflow, action request,
  dispatch, installation, deployment, rollback, remediation, replay,
  migration, background probe, commit, tag, push, publication, or release is
  introduced.
- Independent approvals, interrupted-side-effect no-replay, the optional
  default-disabled worker, and operator-maintenance-only backup/restore remain
  unchanged.
