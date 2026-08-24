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

The milestone dependency order is P0 → P1 → P2 → P3 → P4 → P5. P0 is the
documentation-only scope-selection and boundary sign-off recorded in
[CHANGELOG.md](CHANGELOG.md) and [docs/RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md); P1 through P5 are
not started.

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
- No scheduled or startup collection of any kind.
- No update, pull, install, restart, deploy, rollback, approval, or execution
  authority of any kind.
- No automatic remediation or automatic application.
- No Discovery-to-dispatch coupling: grounding, evidence, or provenance never
  create candidates, intents, approvals, action requests, or dispatches.
- Provider Intent remains limited to Proxmox QEMU `monitoring-policy`.
- Capability parity remains exactly
  `operational=restart-service/proxmox/qemu` and
  `repository=update-compose-stack`; LXC remains unsupported.

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
