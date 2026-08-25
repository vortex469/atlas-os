# Atlas OS Roadmap

## 1. Current released baseline — v0.14

Atlas v0.14.0 is released as `atlas-v0.14.0` at
`4d2526e1b022c5c36eaced65bf5b71703da5d2d7` (2026-08-24).

The released system includes the hardened production topology; repository
candidate execution (`update-compose-stack`); operational dispatch
(`restart-service / proxmox / qemu`); identity-bound Proxmox QEMU
`monitoring-policy` Provider Intent; and Discovery through dynamic evidence,
compatibility/upgrade intelligence, exact Compose image observation, accepted
image evidence, grounding, and provenance.

## 2. Enduring architectural constraints

- Local-first, provider-neutral evidence precedes mutation.
- Curated authority and dynamic evidence remain distinguishable.
- Discovery stays GET-only/read-only and grants no operational authority.
- Legacy provider actions, Provider Intent, hardened operational dispatch, and
  repository execution remain separate authority surfaces.
- Provider Intent is limited to monitoring policy unless a future released
  contract deliberately changes it.
- Backup/restore remains operator maintenance tooling.
- No automatic remediation, approval, update, deployment, rollback, or release
  publication.
- New authority must fail closed, be explicitly activated, and be independently
  enforceable at each trust boundary.

## 3. Released history summary

- v0.6 completed the approval-gated repository candidate path for
  `update-compose-stack`.
- v0.7 introduced hardened operational restart for Proxmox QEMU.
- v0.8 improved effect clarity, lifecycle views, recovery UX, descriptors,
  and hardened ingress.
- v0.9 added recovery diagnostics, support bundles, and release evidence; LXC
  operational restart was rejected for lack of authoritative identity.
- v0.10 added advisory Discovery-to-operator proposal handoff.
- v0.11 released identity-bound Provider Intent for Proxmox QEMU monitoring.
- v0.12 released dynamic Discovery evidence, caching, freshness, and
  provenance.
- v0.13 released compatibility and upgrade intelligence.
- v0.14 released trusted Compose image observation and informational image
  grounding/provenance while leaving the generic collector inactive.

The detailed v0.6-v0.14 milestone plans are historical and completed. Their
release records remain in [CHANGELOG.md](CHANGELOG.md), the release checklist,
and Git history; they are not current work queues.

## 4. Selected v0.15 scope — Deployment Image Grounding Operator Surface

Atlas v0.15 has the theme **Deployment Image Grounding Operator Surface**. It
extends the released v0.14 read-only image grounding (exact repository Compose
image observation, accepted image-release evidence, and informational
grounding/provenance) into a bounded operator-facing presentation surface.

The milestone dependency order is P0 → P1 → P2 → P3 → P4 → P5. P0 is this
documentation-only, decision-complete architecture and boundary sign-off,
recorded in [CHANGELOG.md](CHANGELOG.md) and
[docs/RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md). P0 through P4 are
complete. P5 is in progress. `atlas-v0.14.0` remains the latest released Atlas
version; `atlas-v0.15.0` has not yet been created, and v0.15 is not yet
released.

### Scope

- The surface is read-only and informational. It presents already-accepted
  grounding and provenance to the operator; presentation derives no new
  authority.
- Initial evidence breadth is the accepted Home Assistant `2026.8.3`
  registry-attested proof only. No other release evidence is in scope.
- Discovery remains GET-only. Grounding, evidence, and provenance remain
  evidence, not authority, and never override curated data.

### Non-goals (binding for v0.15)

- No generic image collectors and no collector activation.
- No startup, scheduled, or request-time collection of any kind.
- No update, pull, install, restart, deploy, rollback, approval, or execution
  authority of any kind.
- No automatic remediation or automatic application.
- No Discovery-to-dispatch coupling: grounding, evidence, or provenance never
  create candidates, intents, approvals, action requests, or dispatches.
- Provider Intent remains limited to Proxmox QEMU `monitoring-policy`.
- Capability parity remains exactly
  `operational=restart-service/proxmox/qemu` and
  `repository=update-compose-stack`; LXC remains unsupported.

### P1 — Binding-driven image-grounding read model

Implemented: one deterministic, fail-closed, local read-only composition path
for each catalog item. It consumes the item's existing `DeploymentBinding`, the
existing bounded repository Compose observation, the existing accepted image
evidence, and the existing `ground_deployment_image` semantics. The result
must preserve the observation and evidence provenance and every existing
non-grounded/conflict status; it must not add fallback precedence or infer a
positive result from missing, malformed, mutable, mismatched, untrusted, or
conflicting input.

P1 is composition only. Home Assistant `2026.8.3` remains the sole accepted
registry-attested proof. P1 must add neither evidence rows nor
`DeploymentBinding` entries, and must perform no network access, registry
acquisition, Sigstore runtime verification, collector activation, persistence,
clock-derived authority, mutation, or execution. Focused tests must prove
determinism, provenance preservation, the complete fail-closed status mapping,
and isolation from collectors and authority modules.

### P2 — GET-only Core grounding/provenance projection

Implemented at `GET /api/v1/discovery/items/{item_id}/image-grounding` as an
additive, bounded Core GET-only projection. The projection is redacted and
retains the exact fail-closed status and provenance distinctions;
unavailable data is represented explicitly rather than omitted in a way that
implies success. It has no mutation sibling.

The request path must not persist state, depend on Atlas Agent, mutate a
provider, or create a proposal, candidate, intent, workflow, approval, action
request, or dispatch. Contract, OpenAPI, method-rejection, route-isolation,
redaction, and authority-import tests are required. In particular, no route or
schema addition may make collector, provider, operational, repository, Agent,
or execution modules reachable from the projection.

### P3 — Mission Control advisory image-evidence surface

Implemented an explicitly **informational/advisory** presentation on the existing
Discovery item experience. It displays grounding status and sanitized evidence
provenance, visibly preserves `REGISTRY_ATTESTED` versus `CURATED`, and renders
grounded, conflict, missing, unknown, and other fail-closed states without
turning absence into a positive claim.

The surface has no Apply, Execute, Update, Pull, Restart, Remediate, approval,
or workflow-conversion control. It cannot create or navigate through a
proposal/candidate/workflow as a substitute for such a control. Tests must
cover status/provenance rendering, source-class distinction, missing and error
responses, accessibility, and the absence of mutation controls and requests.

### P4 — Security, isolation, and authority gates

Completed the authoritative structural and behavioral validation matrix proving
all of the following together:

- production image-collector descriptor and adapter registries remain empty,
  with no startup, scheduled, or request-time acquisition wiring;
- a grounding/provenance GET consumes only already-accepted local evidence and
  reviewed local readers and cannot trigger GHCR access, registry acquisition,
  Sigstore verification, collector execution, or evidence refresh;
- grounding/provenance imports and request paths cannot reach mutation or
  execution modules, and projected data excludes secrets, credentials, raw
  provider payloads, and commands;
- curated catalog authority is not silently displaced: `REGISTRY_ATTESTED`
  remains distinct from `CURATED`, conflicts fail closed, and no silent source
  precedence is introduced;
- Provider Intent remains identity-bound Proxmox QEMU `monitoring-policy`
  only; operational capability remains `restart-service/proxmox/qemu`,
  repository execution remains `update-compose-stack`, and LXC remains
  unsupported;
- independent, stage-specific approvals and interrupted-side-effect no-replay
  behavior remain unchanged;
- the execution-worker backend remains optional and default-disabled; and
- backup/restore remains explicit operator maintenance, outside Agent and
  Discovery authority.

### P5 — Release validation and closure

P5 is in progress. Run and record focused Core grounding/API/isolation tests, the full Core suite,
Agent regression tests, and Mission Control tests, lint, and production build.
Prove capability parity and run CI and container release gates against the
same recorded exact candidate SHA. Production acceptance is read-only: verify
the projected Home Assistant proof and fail-closed states, verify collector
registries remain empty and acquisition remains inactive, and verify no
mutation/execution request occurs.

Reconcile the roadmap, current context, README, changelog, Discovery docs, and
release checklist to the observed result. Record commands, outcomes, exact
SHA, image identities/digests, capability evidence, production read-only
acceptance, collector-inactivity evidence, and rollback guidance. Rollback is
the normal image/configuration rollback to the previously accepted release;
there is no data migration, evidence rollback, replay, or automated remediation
to perform because v0.15 adds no durable state or execution authority.

## 5. Uncommitted future directions

The following remain uncommitted directions, not commitments:

- D11 semantic Discovery grounded in deterministic catalog/evidence results.
- D12 private and community catalogs with explicit provenance and trust rules.
- Additional provider, operational, or repository capabilities only after
  explicit identity, authority, approval, recovery, and validation contracts.
- Broader Agent knowledge and distributed orchestration where trust boundaries
  can remain local-first and reviewable.
- Generic image acquisition only if production activation, registry ownership,
  egress, verification, and non-authority contracts are separately approved.

No item above inherits commitment from an older deferred bullet.
