# Foundry Release Checklist

Use this checklist before creating a Foundry release tag.

## Atlas v0.8 implementation status

- [x] V0.8-P0 — Roadmap and release-state reconciliation.
- [x] V0.8-P1 — Effect-aware workflow and approval clarity.
- [x] V0.8-P2 — Unified operational lifecycle read model.
- [x] V0.8-P3 — Mission Control operational history and recovery UX.
- [x] V0.8-P4 — Provider-neutral capability and selector descriptors.
- [x] V0.8-P5 — Deployment and security ergonomics.

P0 through P5 are complete. The immutable `atlas-v0.8-rc1` candidate at
`cf09dfe1eebbd138d37ba7144d91b893f70732fa` has completed required CI,
exact-SHA production deployment, and production soak. The final
`atlas-v0.8.0` release was published at
`f83cd90982d4682ce49e60308e93dc9840984211`.

## Atlas v0.8 RC selection and sign-off

- [x] Record the exact reviewed RC SHA:
  `cf09dfe1eebbd138d37ba7144d91b893f70732fa`.
- [x] Require Quality gates to pass on that exact SHA and record run
  `31856384892`: `atlas-core`, `atlas-agent`, and `mission-control` succeeded.
- [x] Require Container release gate to pass on that exact SHA and record the
  successful run `31856384891`.
- [x] Run `./scripts/operational-capability-parity` and record the exact
  `restart-service/proxmox/qemu` result.
- [x] Confirm lifecycle response redaction and effect-aware approval security
  tests pass on the exact RC SHA.
- [x] Confirm the production registry contains exactly one tuple and no new
  mutation intent or handler exists.
- [x] Review and approve the documented v0.7.0 to v0.8 upgrade and v0.8 to
  v0.7.0 rollback procedures.
- [x] Create the immutable v0.8 RC tag: `atlas-v0.8-rc1`.
- [x] Complete and record the exact-RC production soak.
- [x] Create the final immutable `atlas-v0.8.0` tag at
  `f83cd90982d4682ce49e60308e93dc9840984211`.

## Atlas v0.9 implementation status

- [x] V0.9-P0 — Release-state reconciliation and LXC feasibility closure.
- [x] LXC feasibility investigation — complete / NO-GO.
- [x] V0.9-P1 — Read-only recovery diagnostics.
- [x] V0.9-P2 — Sanitized operational support bundle.
- [x] V0.9-P3 — Release evidence automation.
- [x] V0.9-P4 — Recovery/history operator UX.
- [x] V0.9-P5 — Release acceptance and documentation.

The dependency order is P0 → P1 → P2 → P3 → P4 → P5. The LXC identity gate
closed fail-safe: no authoritative incarnation identity was proven, no
synthetic identity was accepted, and no LXC candidate, selector, translation,
gate, handler, ACL, or mutation is enabled. The revised P1–P5 milestones are
read-only recovery, evidence, UX, and release work.

P0 through P5 implementation and release acceptance are complete. The
immutable RC was selected and passed exact-candidate CI, release-evidence
validation, exact-RC deployment, and restart soak. Only final release
publication remains pending.

## Atlas v0.9 RC selection and sign-off

- [x] Record the exact reviewed RC candidate SHA after the documentation commit.
- [x] Require Quality gates to pass on that exact SHA and record the run ID and
  Core, Agent, and Mission Control conclusions.
- [x] Require Container release gate to pass on that exact SHA and record its
  run ID.
- [x] Run `./scripts/release-evidence` against the exact SHA and annotated RC
  tag; require `atlas-release-evidence-v1` status `ready` without fabricated
  private or CI evidence.
- [x] Run `./scripts/operational-capability-parity` and require exactly
  `restart-service/proxmox/qemu`.
- [x] Confirm recovery diagnostics are deterministic and read-only for healthy,
  pending/recovery, Core-unavailable, immutable-mismatch,
  transition-mismatch, target-replaced, outcome-uncertain, and
  terminal-mismatch states.
- [x] Confirm `atlas-operational-support-bundle-v1` remains bounded,
  deterministic, redacted, explicitly partial/truncated where applicable, and
  local-only with no upload destination.
- [x] Confirm Mission Control recovery/history UX separates network failure
  from operational failure and exposes no retry, run-again, replay,
  reconciliation-write, upload, or share control.
- [x] Confirm the production mutation boundary contains exactly one tuple and
  v0.9 adds no intent or handler.
- [x] Confirm `restart-service/proxmox/lxc` remains unsupported: no synthetic
  identity, candidate, selector, translation, gate, handler, ACL, or mutation
  was added.
- [x] Review the documented v0.8.0 to v0.9 upgrade and v0.9 to v0.8.0
  fail-safe rollback procedure, including in-flight barrier handling.
- [x] Create the immutable annotated `atlas-v0.9-rc1` tag.
- [x] Complete and record exact-RC production deployment and service-restart
  soak without performing a provider mutation merely for soak validation.
- [x] Create the final immutable `atlas-v0.9.0` tag at
  `7a5beac58e1677cd97b9bcc2f160dc30573582aa`; Quality gates run
  `31861408265` and Container release gate run `31861408264` passed.

### Atlas v0.9 RC1 promotion evidence — 2026-08-15

- [x] The immutable annotated tag `atlas-v0.9-rc1` (tag object
  `5ea956e3439f0b5d2fdf088962144d9b37925964`) peels to exact RC SHA
  `bc549ff6ab57d366205c1b9eb0c36fc2f7a61ba3`; HEAD and `origin/main`
  matched that SHA.
- [x] Quality gates run `31860606490` succeeded, and Container release gate
  run `31860606478` succeeded on the exact RC SHA.
- [x] `atlas-release-evidence-v1` reported `summary.status=ready`: hardened
  Compose rendering, Edge-present/Mission-Control-absent host publication,
  capability parity, secret hygiene, annotated-tag peeling, and tracked
  worktree cleanliness passed. The only allowed untracked path was
  `compose.execution-smoke.override.yaml`.
- [x] Production was rebuilt without cache from the exact RC checkout and
  deployed using only `compose.production.yaml`, `compose.https.yaml`, and
  `compose.operator-auth.yaml`. Core and Agent checkout/container checksums
  matched, the running Mission Control image matched the newly built RC image,
  and all production services remained healthy.
- [x] Recovery diagnostics for the accepted workflow were applicable, healthy,
  consistent, transition-valid, request-correlated, and fingerprint-stable,
  with `safe_next_action=none`.
- [x] The acceptance `atlas-operational-support-bundle-v1` sample was bounded,
  canonically digest-verified, untruncated, and sanitized. It contained no raw
  provider identity, environment, commands, logs, files, or upload destination.
- [x] Mission Control operational history, recovery summary, and local-only
  support-evidence preview/download passed. No retry, run-again, reconciliation,
  upload, or repository/operational-boundary bypass control was exposed.
- [x] Sequential Atlas Agent, Atlas Core, Mission Control, and Atlas Edge
  restarts passed without redispatch or provider mutation. The accepted
  workflow remained completed, verified, consistent, and terminal.
- [x] Exactly-once evidence remained unchanged before and after soak: one
  dispatch record, six ledger transitions, one barrier crossing, one provider
  operation, one dispatch result, one verification success, no new operational
  request ID, and VM 110 `qmreboot` count 3. Target fingerprint remained
  `operational-target-fingerprint-v1:1d7fdec6d423cd4936de130860d0171bed424bf695a07e82e22f734d24b6854e`.
- [x] The production mutation boundary remained exactly
  `restart-service/proxmox/qemu`. `restart-service/proxmox/lxc` remains
  unsupported: no authoritative LXC identity, selector requestability,
  translation, execution-gate entry, handler, ACL, or synthetic identity was
  added.
- [x] RC1 is selected, immutable, deployed, soaked, and accepted for final
  promotion. The final `atlas-v0.9.0` release was subsequently published at
  `7a5beac58e1677cd97b9bcc2f160dc30573582aa`.

## Atlas v0.10 implementation status

- [x] V0.10-P0 — Release-state and D9 boundary reconciliation.
- [x] V0.10-P1 — Sanitized proposal contracts and provenance.
- [x] V0.10-P2 — Derivation, compatibility, and staleness.
- [x] V0.10-P3 — Authoritative navigation contract.
- [x] V0.10-P4 — Mission Control proposal UX.
- [x] V0.10-P5 — Boundary integration, validation, and release acceptance.

P0 establishes that Discovery proposals are derived, advisory, and
non-authoritative. They cannot create candidates, action requests, approvals,
or dispatches. Any destination must freshly resolve capability, selector,
target state/fingerprint, and operator authority. V0.10 does not widen
`update-compose-stack` repository execution or the sole production operational
tuple `restart-service/proxmox/qemu`; LXC remains unsupported.

## Atlas v0.10 RC selection and sign-off

- [x] Record the exact reviewed RC candidate SHA.
- [x] Require successful Quality gates on that exact SHA.
- [x] Require successful Container release gate on that exact SHA.
- [x] Require `atlas-release-evidence-v1` status `ready` for the exact SHA/tag.
- [x] Reconfirm operational capability parity is exactly
  `restart-service/proxmox/qemu`.
- [x] Reconfirm proposal reads/navigation create no candidate, planning session,
  approval, action request, dispatch record, or provider operation.
- [x] Reconfirm executable-candidate projection rejects compatible,
  incompatible, stale, expired, hinted, and tampered proposal context.
- [x] Reconfirm stale/tampered proposals are review-only and public/UI proposal
  projections pass redaction checks.
- [x] Reconfirm Mission Control advisory UX performs no automatic selection or
  submission and reloads current destination authority.
- [x] Reconfirm exactly one production mutation tuple and no LXC capability.
- [x] Review v0.9.0-to-v0.10 upgrade, persistence, and rollback guidance.
- [x] Create the immutable v0.10 RC tag.
- [x] Complete exact-RC production deployment and restart soak.
- [x] Create and publish the final immutable `atlas-v0.10.0` tag at
  `b19ded149f65dfb4043a1b80833e5ff64d83e55d`.

### Atlas v0.10 RC1 promotion evidence — 2026-08-15

- [x] Immutable RC tag `atlas-v0.10-rc1` (tag object
  `1c8798472ce46b2aa1fc822c1613a720c62113c4`) peels to exact RC SHA
  `95d98a4d5e0e9767dd6cb5df06c7ffdb693bf162`; HEAD, `origin/main`,
  and the tag matched exactly.
- [x] Quality gates run `31863884438` and Container release gate run
  `31863884456` succeeded on the exact RC SHA.
- [x] `atlas-release-evidence-v1` returned `summary.status=ready`: hardened
  Compose render, capability parity, and secret hygiene passed; security
  findings were empty; the tracked worktree was clean; only the intentional
  untracked `compose.execution-smoke.override.yaml` was allowed.
- [x] Production was rebuilt with `--no-cache` from the exact RC checkout and
  deployed using only `compose.production.yaml`, `compose.https.yaml`, and
  `compose.operator-auth.yaml`. The smoke override was not used.
- [x] Core
  `services/atlas-core/app/services/discovery_proposals.py` and Agent
  `candidate_planning/models.py` checkout/container SHA-256 values matched;
  the running Mission Control image matched the newly built RC1 image; all
  required services remained healthy.
- [x] Live proposal list and known detail returned HTTP 200, unknown detail
  returned controlled HTTP 404, and four deterministic proposal IDs remained
  stable through restart soak. Current production proposals evaluated as
  `current / insufficient_information / compatibility_review` with
  `actionable_navigation=false`.
- [x] Proposal output exposed no authoritative target fingerprint, `vmgenid`,
  raw/provider-native identity, provider action ID, arbitrary route/URL,
  command/environment, or credential/token/cookie/CSRF material.
- [x] Incompatible, insufficient-information, warning/review, stale, expired,
  missing-source, missing-evidence, unsupported-resource, and transport-failure
  states remained inspectable and review-only without prohibited maintenance
  navigation.
- [x] Proposal context selected only a fixed destination. The maintenance
  destination independently reloaded operator session and permission,
  capability descriptors, the server-issued selector, current resources,
  requestability/state, and authoritative fingerprint. Tampered proposal,
  destination, provider, resource, target, and intent hints changed no server
  authority and triggered no submission.
- [x] Mission Control rendered bounded proposal status/reason and compatibility
  review context with an advisory authority warning. It exposed no target
  preselection, automatic submission, Execute, Run, Restart now, Approve,
  Dispatch, retry, or replay control.
- [x] Non-authority counts remained unchanged: candidates `6 → 6`, planning
  sessions `34 → 34`, approvals `55 → 55`, operational action requests
  `1 → 1`, dispatch records `1 → 1`, transitions `6 → 6`, barrier crossings
  `1 → 1`, provider operations `1 → 1`, dispatch results `1 → 1`, and
  verification successes `1 → 1`. No automatic POST occurred.
- [x] Existing request
  `operational-action-f20b14392a0a75dcfb41ec83d230845a6b0a610a29c7d142e5842c7fd827aa4b`
  remained the only operational request. Its workflow remained completed and
  terminal, the Core ledger remained verified, and verification remained
  succeeded.
- [x] VM 110 remained running; `qmreboot` count stayed `3 → 3`; authoritative
  fingerprint remained
  `operational-target-fingerprint-v1:1d7fdec6d423cd4936de130860d0171bed424bf695a07e82e22f734d24b6854e`.
- [x] Sequential Atlas Core, Mission Control, Atlas Agent, and Atlas Edge
  restarts passed. Proposal IDs/evaluations stayed stable and no redispatch or
  provider mutation occurred.
- [x] Mission Control had no host publication, Atlas Edge was the sole browser
  ingress, and production capability remained exactly one tuple:
  `restart-service/proxmox/qemu`. No LXC tuple, new intent, handler, ACL
  expansion, or proposal-derived execution authority was introduced.
- [x] RC1 is selected, immutable, exactly deployed, soaked, and accepted for
  final promotion. The immutable `atlas-v0.10.0` release was published at
  `b19ded149f65dfb4043a1b80833e5ff64d83e55d`.

## Atlas v0.11 P0 architecture sign-off

- [x] Record final `atlas-v0.10.0` release identity.
- [x] Define the Provider Management Framework — Identity-Bound Runtime Intent
  theme and P0 through P5 dependency order.
- [x] Separate provider intent, legacy/generic provider actions, operational
  dispatch, and repository execution authority.
- [x] Limit the initial provider-intent direction to Proxmox QEMU monitoring
  intent and require provider-authoritative incarnation identity binding.
- [x] Preserve QEMU VMID-reuse protection, the LXC identity NO-GO, and the
  advisory/non-authoritative Discovery proposal boundary.
- [x] Record the complete v0.11 non-goal set without changing runtime code,
  provider state, configuration, permissions, gates, handlers, ACLs, or
  production execution.

## Atlas v0.11 P2b recovery and compatibility acceptance

The accepted implementation chain is bounded by the backup-v3 contract
(`47b6ef0`), v3 creation (`f33f70c`), transactional engine (`c4d8650`),
production recovery integration (`a8390c2`), legacy-partial guard (`cef5226`),
and compatibility/lineage guidance (`b5390ba`).

- [x] Backup v3 defines an exact, complete generation for the declared managed
  Atlas Core durable-state boundary; it is not a whole-system backup and does
  not include `atlas-agent-state`.
- [x] `operational_dispatch.db` is required and validated as safety-authoritative
  no-replay state, and restored ledger evidence retains no-replay behavior.
- [x] `operator_intents.db` is required, validated, and preserved as durable
  operator authority.
- [x] `operator_sessions.db` is excluded and invalidated on v3 restore; raw
  snapshot rollback guidance also requires session invalidation while stopped.
- [x] V3 manifests bind the explicit Provider Intent generation: inactive
  backups require `provider_intents.db` absent, while activated backups require
  the validated authority store and exact legacy-import receipt. No public
  write authority is claimed.
- [x] Backup directories and artifacts enforce private `0700`/`0600`
  permissions, including secret-bearing provider connection state.
- [x] Transactional v3 restore preserves set-wide managed-state coherence,
  exact rollback on handled failure, and durable recovery evidence on
  interruption.
- [x] Restore crash recovery and the Core startup interlock fail closed while
  unresolved transaction evidence remains.
- [x] The accepted disposable recovery gate covered audit-present and
  approved-absent branches, session invalidation, Provider Intent
  pre-activation cleanup, YAML/config/secret restoration, operational-ledger
  and operator-intent preservation, unmanaged sentinel preservation, handled
  rollback, and interrupted-restore recovery without a real provider mutation.
  It explicitly guarded and did not target the production `atlas_atlas-data`
  volume.
- [x] Format v1/v2 verification compatibility remains historical
  `legacy_partial`; only v3 is complete for the declared Core boundary.
- [x] V1/v2 restore refuses any populated managed Core path or managed SQLite
  sidecar, including operational, operator-intent, session, audit, and Provider
  Intent state.
- [x] V1/v2 restore onto managed-empty state requires `--confirm` plus explicit
  `--allow-legacy-partial-new-lineage` acknowledgement and creates only a new
  partial lineage.
- [x] Safe v0.11-to-v0.10 downgrade requires paired pre-upgrade complete Core
  and Agent snapshots plus retained operational no-replay evidence; a v2 export
  is supplemental only.
- [x] Restoring v3 and then starting v0.10 is explicitly prohibited.
- [x] Re-upgrade must either resume the preserved v0.11 Core/Agent lineage or
  continue the rolled-back v0.10 lineage into a new v3 recovery point; the two
  histories are mutually exclusive and are not automatically merged.
- [x] V0.11-P2b-4 — Legacy-partial guard, recovery compatibility guidance, and
  release-acceptance closure.
- [x] V0.11-P2b-5 — `atlas-core-recovery-evidence-v1` derives bounded,
  redacted readiness from the disposable recovery, legacy compatibility,
  startup/no-replay, cleanup, and exact execution-parity checks; an artifact is
  accepted only for its exact clean candidate SHA and must be supplied
  explicitly to release evidence.
- [x] V0.11-P2b-6 — Deterministic, atomic legacy Proxmox expectation shadow
  import persists only `legacy_unbound` evidence with no resource type,
  incarnation fingerprint, activation, source-of-truth cutover, or runtime
  authority.
- [x] V0.11-P2c-3 — Activated v3 backup, verification, transactional restore,
  startup compatibility, and recovery-evidence-v2 support preserve the exact
  Provider Intent store generation and reject mixed activation lineages. The
  disposable gate covers both activation branches.
- [x] V0.11-P2c-4 — Exact candidate
  `8ea7610d9f5ce4a33e09a3a12387ee8a23160a6b` is deployed and production
  Provider Intent read authority is activated with the validated seven-record
  `legacy_unbound` import receipt. Both identity-capable QEMU resources remain
  `needs_review` with no active intent, all 11 LXC resources remain unsupported,
  and retained `policies.yaml` is no longer Proxmox monitoring authority. The
  activated v3 backup manifest is
  `b599b1dbb510bf5b313b53417d8c36282be00f3d157796d3fab6741bf7825ad6`;
  exact-SHA recovery evidence v2 is `ready` with SHA-256
  `45aa69294ef1be4514824bd438e4f1aae2ea28a8d78056b500e3c7b8df873182`.
  The pre-activation rollback bundle remains retained. This historical P2c
  read-authority checkpoint was superseded by the accepted P3 production state
  below.

## Atlas v0.11 P3 Provider Intent mutation acceptance

- [x] V0.11-P3a — Complete.
- [x] V0.11-P3b — Complete.
- [x] V0.11-P3c — Complete.
- [x] V0.11-P3d — Exact-candidate production acceptance complete.
- [x] V0.11-P3 — P3a through P3d complete. No later milestone is started or
  marked complete by this closure.
- [x] Accepted exact candidate:
  `2169fa2683ed336e1eec7e3f4febff26895fa395`.
- [x] Production Provider Intent authority remains activated on schema v2 with
  seven preserved `legacy_unbound` records and exactly two active,
  identity-bound QEMU monitoring intents. No legacy record was automatically
  rebound.
- [x] The operator explicitly selected `running` for QEMU 110 / Frigate and
  QEMU 200 / pbs; neither value was inferred from live state or legacy
  evidence. Both were bound to current provider-authoritative identities and
  confirmed `configured` by server-authoritative read-after-write at record
  version 1.
- [x] Each first binding used the dedicated P3 Provider Intent endpoint with
  `expected_record_version=0`, explicit expectation `running`,
  `acknowledge_monitoring_suppression=false`, and a unique request ID. Exact
  replay returned the original result without duplicate history.
- [x] Only intended operator `kenny` received `provider_intent:update`.
  Existing sessions were invalidated, `kenny` reauthenticated after the
  verifier change, and authenticated provider-management-v3 confirmed mutation
  capability.
- [x] Provider Intent mutation remains an authenticated monitoring-policy
  operation and grants no infrastructure execution authority. No provider
  action, operational request, execution candidate/planning/approval, or
  provider-handler invocation was created, and execution authority did not
  expand.
- [x] `policies.yaml` remains physically retained but non-authoritative for
  Proxmox monitoring. Legacy expectation PUT remains rejected while Provider
  Intent is activated, and the seven legacy records remain review/history
  evidence only.
- [x] Execution parity remains exactly
  `operational=restart-service/proxmox/qemu` and
  `repository=update-compose-stack`.
- [x] The accepted post-mutation activated v3 backup is
  `/opt/atlas-cutover/p3d-2169fa2/post-mutation-backups/atlas-data-20260816T032919Z`
  with manifest SHA-256
  `cf90e15831bdbcf898ddda1892938d914f6bcadcddc4bffdf2ede2b155b9a397`.
- [x] `atlas-core-recovery-evidence-v3` is `ready` at
  `/opt/atlas-cutover/p3d-2169fa2/recovery-evidence/post-p3d-activated-recovery-evidence-v3.json`
  with SHA-256
  `998956ccbb56428c04f0a9ea3be0a2668ddd55f66012a925f4ba3ae4f40e04b0`.
  Disposable recovery preserved schema-v2 Provider Intent state, both active
  intent identities and versions, actor-bound audit/request/idempotency
  evidence, all seven legacy records, the import receipt, session invalidation
  and reauthentication, operational no-replay, and execution isolation.
- [x] The pre-P3 rollback anchor remains retained at
  `/opt/atlas-cutover/p3d-2169fa2/pre-p3-backups/atlas-data-20260816T030050Z`
  with paired Agent snapshot
  `/opt/atlas-cutover/p3d-2169fa2/agent-snapshots/atlas-agent-state-20260816T0301Z.tar`.
- [x] Accepted image identities: Core
  `sha256:9cd0fadf99abb4209679aa6efcb7397bfeb0e41d486a3ddac499ee382d8a9a72`,
  Agent
  `sha256:83242fbe090f45d458f6fe7d9a24c8830cebe55df0e8bea59738696a839f2f98`,
  Execution Worker
  `sha256:24b69749831dfddfdf154b819c5cf3621d494df55887a03a1c19c2cd238d0c46`,
  and Mission Control
  `sha256:feea963cc1dda442c344d626e5a97868004d75c2b6e5f5f94130869adb132605`.

## Atlas v0.11 P4 Mission Control provider experience acceptance

- [x] V0.11-P4a — Canonical provider resource and monitoring presentation,
  commit `432afe9ccf6101f7d14dd93cf90c30db7fb142eb`.
- [x] V0.11-P4b — Provider-page authority-surface separation, commit
  `5babaf105bd1530efc56a9512b093a47e37d17e3`.
- [x] V0.11-P4c — Composed provider-page, accessibility, error-state, keyboard,
  and structural-boundary acceptance complete in this closeout slice.
- [x] V0.11-P4 — P4a through P4c complete. V0.11-P5 is next and remains
  unstarted.
- [x] Public provider-management-v2 is canonical for public resource identity,
  monitoring expectation, status, reason, and legacy-review context.
  Authenticated provider-management-v3 is only the caller-specific
  mutation-readiness overlay.
- [x] Only supported, live Proxmox QEMU with authoritative identity, activated
  Provider Intent authority, write-ready schema-v2 storage, exact readiness,
  and an authenticated authorized caller exposes monitoring Save controls.
  LXC, missing resources, unavailable identity/authority/store,
  migration-required state, and unauthorized callers remain read-only.
- [x] Observed provider state and monitoring expectation are separately labeled;
  configured match, mismatch, ignored, Needs Review, replacement, missing, and
  unavailable states retain bounded textual semantics.
- [x] Replacement and legacy-review paths require a fresh explicit operator
  choice, use current identity and exact version rules, and never preselect or
  copy historical expectations.
- [x] Proxmox `policies.yaml` guest expectations remain physically retained but
  appear only as non-authoritative compatibility/history evidence; they do not
  replace current Provider Intent or automatically apply to current identities.
- [x] Diagnostics and recommendations remain non-interactive advisory surfaces.
  Compatibility actions retain only the existing provider-action API, and
  operational maintenance remains separate navigation to the authenticated
  request/candidate/planning/approval workflow.
- [x] Composed and structural UI tests prove monitoring does not invoke provider
  actions, operational requests/dispatch, candidates, planning, approval,
  Discovery proposal application, legacy expectation PUT, YAML writers, or
  automatic remediation/execution.
- [x] Execution capability parity remains exactly
  `operational=restart-service/proxmox/qemu` and
  `repository=update-compose-stack`.

### Atlas v0.8 RC1 promotion evidence — 2026-08-15

- [x] Production was rebuilt with no-cache images from the exact RC1 checkout.
- [x] Core and Agent source/image checksum parity passed, and Mission Control
  running-image parity matched the RC1 build.
- [x] The three-file deployment used `compose.production.yaml`,
  `compose.https.yaml`, and `compose.operator-auth.yaml`; Atlas Edge was the
  sole HTTPS browser ingress and Mission Control had no host-published port.
- [x] Agent, Core, Mission Control, and Atlas Edge sequential restarts passed;
  all required services remained healthy.
- [x] The completed operational workflow remained terminal and verified with
  consistent lifecycle correlation. Historical approvals remained
  non-actionable, no operational commit approval appeared, and history and
  lifecycle views remained read-only with no retry or run-again control.
- [x] Durable exactly-once evidence remained one dispatch record, six
  transitions, one dispatching/barrier transition, one provider operation, one
  dispatch result, and one verification success. VM 110 `qmreboot` count
  remained `3`; no new operational request ID appeared and the authoritative
  target fingerprint remained unchanged.
- [x] Production remained closed to exactly
  `restart-service/proxmox/qemu`; no new mutation intent or handler appeared.
  The selector remained sanitized without `vmgenid` or raw identity material,
  and private credentials and TLS material remained untracked.

## Atlas v0.8 exact-RC deployment and security checks

- [x] Render base production Compose and confirm Mission Control publishes only
  the default loopback HTTP binding.
- [x] Render the HTTPS plus operator-auth deployment and confirm Atlas Edge is
  the only host-published browser ingress while internal Mission Control routing
  remains healthy.
- [x] Confirm unauthenticated HTTPS receives the Edge authentication challenge
  and authenticated HTTPS reaches the SPA, Core API, and Agent API.
- [x] Confirm expired/unavailable sessions clear authenticated UI state;
  permission failures remain distinct; missing CSRF rotation fails closed; and
  reauthentication returns to the intended safe page.
- [x] Run `./scripts/operational-capability-parity` and require exact parity
  across Agent planning, translation and execution, plus Core execution,
  registry, and descriptor projection.
- [x] Confirm lifecycle response-model redaction tests reject credentials,
  authorization headers, cookies, CSRF, bearer tokens, raw identity,
  provider-native payloads, commands, environment data, arbitrary exceptions,
  and worker/sandbox internals.
- [x] Confirm operational history and lifecycle views remain read-only and
  expose no retry or run-again control, including ambiguous outcomes.
- [x] Confirm the production registry contains exactly one tuple:
  `restart-service / proxmox / qemu`.

## Automated gates

Generate bounded read-only RC/final provenance evidence with:

```bash
./scripts/release-evidence \
  --expected-base atlas-v0.8.0 \
  --candidate-tag atlas-v0.9-rc1 \
  --expected-sha <reviewed-commit-sha> \
  --require-main \
  --require-tag \
  --json
```

Require exit `0` and retain the JSON with the release review. Exit `1` means a
required check failed, exit `2` means required evidence is incomplete, and exit
`3` means the invocation is invalid. A green run proves only the bounded facts
reported by `atlas-release-evidence-v1`; it does not prove production soak,
container-gate completion, or human approval to create a tag. Those steps
remain explicit checklist items.

- [x] Atlas Core installs from `requirements-dev.txt`.
- [x] Atlas Core test suite passes.
- [x] Mission Control installs reproducibly with `npm ci`.
- [x] Mission Control tests, lint, and production build pass.
- [x] Production Compose configuration validates without resolving
  credential values.
- [x] Both production images build from digest-pinned bases.
- [x] Isolated containers become healthy and run as non-root users with
  read-only root filesystems, dropped capabilities, and privilege
  escalation disabled.
- [x] Mission Control, the API proxy, security headers, and SPA deep links
  pass live HTTP smoke checks.
- [x] Container-gate cleanup leaves no temporary Docker resources.
- [x] Python dependency audit reports no known vulnerabilities.
- [x] Repository scan contains no committed production credentials.

The application quality gates run in `.github/workflows/quality-gates.yml`.
The production container gate runs the same
`scripts/container-release-gate` command locally and in GitHub Actions.
Third-party actions are pinned to exact commits.

## Release artifacts

- [x] MIT license is present.
- [x] README, changelog, roadmap, architecture, deployment, and dependency
  security documentation are populated.
- [x] `.dockerignore` excludes credentials, local databases, virtual
  environments, dependencies, builds, and logs.
- [x] Tracked editor backup files are removed.
- [x] The public release identifier is consistently `Foundry`.

## Dependency security

The prior React Router RSC action CSRF exception is resolved by
`react-router-dom@7.18.2`. The final dependency review reports zero npm
vulnerabilities and no known vulnerabilities in the Core or Agent Python
requirements. The dated resolution and transitive remediation record are in
`docs/DEPENDENCY_SECURITY.md`.

## Operator approval

Complete these items immediately before tagging:

- [x] Rotate and verify any credentials exposed during pre-release
  validation.
- [x] Review deployment-specific inventory, policy, and TLS settings.
- [x] Confirm the target branch contains only intended release commits.
- [x] Run `./scripts/container-release-gate` on the release commit.
- [x] Confirm required GitHub checks pass.
- [x] Create an annotated Foundry release tag and publish release notes.

Foundry `v1.0.0` was published on 2026-07-25 from commit `b32b21d`.
Production validation reported no critical issues. The release notes record
the operator-accepted warning for unavailable or unknown Home Assistant
entities.

## Atlas v0.6 release gates

### RC1 verification artifacts

- [x] Record the exact commit checked for atlas-v0.6-rc1 packaging.
- [x] Record commands used and pass/fail status for:
  - `PATH=/opt/atlas/.venv/bin:$PATH ./scripts/rc1-python-ruff-gate services/atlas-core`
  - `cd services/atlas-core && PATH=/opt/atlas/.venv/bin:$PATH python -m pytest -q`
  - `PATH=/opt/atlas/.venv/bin:$PATH ./scripts/rc1-python-ruff-gate services/atlas-agent`
  - `PATH=/opt/atlas/.venv/bin:$PATH PYTHONPATH=services/atlas-agent python -m pytest -q services/atlas-agent/tests`
  - `cd services/mission-control && npm run lint`
  - `cd services/mission-control && npm test -- --run`
  - `cd services/mission-control && npm run build`
  - `./scripts/container-release-gate`

Validated on 2026-08-13 at commit
`70997b398727471d261a297e41831f5901b83a18`. Commands ran from
`/opt/atlas` unless a different working directory is shown:

| Command | Working directory | Exit | Result |
| --- | --- | ---: | --- |
| `PATH=/opt/atlas/.venv/bin:$PATH ./scripts/rc1-python-ruff-gate services/atlas-core` | `/opt/atlas` | 0 | All changed-file checks passed. |
| `PATH=/opt/atlas/.venv/bin:$PATH python -m pytest -q` | `/opt/atlas/services/atlas-core` | 0 | 692 passed, 1 dependency deprecation warning. |
| `PATH=/opt/atlas/.venv/bin:$PATH ./scripts/rc1-python-ruff-gate services/atlas-agent` | `/opt/atlas` | 0 | All changed-file checks passed. |
| `PATH=/opt/atlas/.venv/bin:$PATH PYTHONPATH=services/atlas-agent python -m pytest -q services/atlas-agent/tests` | `/opt/atlas` | 0 | 816 passed, 1 dependency deprecation warning. |
| `npm run lint` | `/opt/atlas/services/mission-control` | 0 | 0 errors, 1 React hook dependency warning. |
| `npm test -- --run` | `/opt/atlas/services/mission-control` | 0 | 28 files and 190 tests passed. |
| `npm run build` | `/opt/atlas/services/mission-control` | 0 | Production build passed with a chunk-size warning. |
| `./scripts/container-release-gate` | `/opt/atlas` | 0 | Compose rendering, production images, isolated hardened runtime, HTTP/HTTPS, data recovery, and Rest Server recovery passed. |

The literal Python commands were also attempted without the repository virtual
environment on this validation host. Both exited `127` because the host has no
global `python` executable. The successful commands above make the required
repository-local tool context explicit; CI supplies the equivalent Python tool
context through `actions/setup-python` and dependency installation.

### RC1 candidate execution boundary

- [x] Supported execution intent is limited to `update-compose-stack`.
- [x] Structured Compose mutation evidence is required before implementation
  approval.
- [x] Legacy planning sessions without mutation evidence are non-actionable
  and require successor planning or replanning.
- [x] Approval binding, persistence/recovery, stale/fingerprint rejection, and
  successor concurrency/idempotent reuse are validated.
- [x] Codex authentication and runtime provisioning are validated.
- [x] Codex-backed repository mutation is production-ready through the exact
  approval-gated candidate path.
- [x] A reviewed narrow seccomp/AppArmor policy or isolated execution runtime
  passes disposable workspace-write, outside-workspace denial, authenticated
  end-to-end execution, verification, review, and commit-boundary tests while
  preserving uid `10001`, `CapDrop=ALL` where applicable,
  `no-new-privileges`, and read-only rootfs.

### RC1 production execution smoke validation

Validated on commit `c333937e61343aed714a475395b41077bad86e28` using the final
production-like smoke workflow `candidate-workflow-6da0da7b4da397219e6f507ebd5439959584559529eb02a9598cdbd6a93aa866` and planning session
`candidate-plan-158f8db4f0c204de90f857ce2911cbf219dd900ae21e2b2f1a16037982baf200`.
The evidence bundle is retained at `/root/atlas-rc1-smoke-evidence/final-c333937/`.

- [x] Candidate intake, planning, candidate plan, workflow shell, shell
  approval, exact implementation approval, isolated worker execution, exact
  verification approval, deterministic RC1 verification, baseline-aware review,
  and the exact commit approval boundary were traversed successfully.
- [x] Worker execution succeeded with the worker attestation showing runtime
  uid `10001`, read-only rootfs, `no-new-privileges`, zero effective
  capabilities, and `runsc-squid` sandbox profile.
- [x] Repository HEAD remained frozen at
  `c333937e61343aed714a475395b41077bad86e28` throughout the successful
  lineage.
- [x] Exactly one approved tracked file changed:
  `services/atlas-agent/tests/test_execution_engine.py`.
- [x] The exact verification plan was persisted before approval. The gated
  RC1 zero-command verification passed without a fake or dummy command, and
  preserved repository HEAD and the validated changed-files digest.
- [x] Baseline-aware review excluded the pre-existing untracked
  `compose.execution-smoke.override.yaml`, passed with zero findings, and
  produced an exact commit approval request for branch `feature/atlas-agent`,
  the validated HEAD, and the one reviewed file.
- [x] The validation-only commit was intentionally not approved or performed.
  The marker was restored afterward and the tracked working tree is clean.
- [x] The smoke remediation set is covered by regression validation: worker
  journal exactly-once recovery, candidate audit approval-boundary projection,
  gated RC1 verification intent, baseline-aware verification, exact
  verification approval binding, candidate verification resume dispatch,
  approval-repository storage identity, AtlasCoreClient event-loop ownership,
  deterministic zero-check verification, and baseline-aware candidate review
  and commit validation.

The untracked `compose.execution-smoke.override.yaml` remains outside workflow
provenance. Recommendation: retain it as a maintained operator smoke harness
until the evidence and operator procedure are no longer needed, then remove it
through a separate reviewed cleanup decision.

## Atlas v0.7 P1.3 release-candidate readiness

### Operational capability and security boundary

- [x] Production capability is closed to `restart-service / proxmox / qemu`.
- [x] Core-owned operator sessions require authenticated HTTPS, one exact
  trusted origin, CSRF validation, and `operational_intent:create`.
- [x] Edge Basic authentication remains defense-in-depth and is not accepted as
  Core operator identity.
- [x] Agent-to-Core authentication is separate from browser authentication.
- [x] Authoritative QEMU identity and fingerprint revalidation bind planning,
  approval, dispatch, and verification.
- [x] Exact `OPERATIONAL_ACTION` approval binds the immutable action request ID,
  digest, target, provider action, verification policy, and expiry.
- [x] Core persists the dispatch barrier before provider mutation and never
  replays a crossed or ambiguous mutation boundary.
- [x] UPID-backed verification and verifier-only recovery are read-only.

### Production acceptance — 2026-08-14

- [x] Approved target: `vorex469 / VM 110 / Frigate`.
- [x] The normal operator-intent, planning, preparation-approval, exact-action
  approval, Agent dispatch, Core handler, and verification path completed.
- [x] Exactly one new `qmreboot`, one dispatching transition, one barrier
  crossing, one provider-operation capture, and one dispatch result occurred.
- [x] The production ledger reached `verified`; Agent projected the workflow as
  `completed`.
- [x] Final VM and QMP states were running and the authoritative fingerprint was
  unchanged.
- [x] No replay, sandbox path, non-production ledger, direct provider mutation,
  commit, tag, or release action occurred.

### Deployment sign-off required before an RC

- [x] Re-run and record the full Core, Agent, Mission Control, worker, Compose,
  container, dependency, and credential-hygiene gates on the final RC commit.
- [x] Push the reviewed documentation commit and require both GitHub workflows
  to pass on that exact SHA.
- [x] Document the supported
  [v0.6.0 to v0.7 upgrade and rollback](DEPLOYMENT.md#atlas-v060-to-v07-upgrade-and-rollback),
  including schema-v3 downgrade handling and in-flight dispatch preservation.
- [x] Review those v0.7 upgrade and rollback instructions and record
  release-lead sign-off.
- [x] Create an immutable RC tag only after the exact pushed SHA is green.
- [x] The final immutable `atlas-v0.7.0` tag was published at
  `8dbc43de73dda300b50c121f19324cb5174df2a9` after the documentation provenance
  fix and required CI passed on that exact final SHA.

### Final RC1 provenance and production soak — 2026-08-14

Release candidate `atlas-v0.7-rc1` resolves to
`5b1321091af0fc191844cdf71e9e0d919e4ea415`.

- [x] Quality gates run `31850208419` passed on the exact RC SHA: `atlas-core`,
  `atlas-agent`, and `mission-control` all succeeded.
- [x] Container release gate run `31850208435` passed on the exact RC SHA.
- [x] Dependency Graph run `31850211284` passed on the exact RC SHA.
- [x] Production was rebuilt from the exact RC1 checkout with no-cache images
  and deployed using only `compose.production.yaml`, `compose.https.yaml`, and
  `compose.operator-auth.yaml`. The untracked
  `compose.execution-smoke.override.yaml` was not used.
- [x] Running Core and Agent source checksums matched the RC1 checkout, and the
  running Mission Control image identity matched the exact RC1 build.
- [x] Sequential restarts of Atlas Agent, Atlas Core, Mission Control, and Atlas
  Edge passed; all production services were healthy afterward.
- [x] The completed operational workflow remained terminal, and the production
  ledger remained unchanged with exactly one historical barrier crossing, one
  historical provider operation, one historical dispatch result, and no
  replay.
- [x] VM 110's `qmreboot` count remained `3`, and its authoritative target
  fingerprint remained unchanged throughout the redeploy and soak.
- [x] Operator-auth private files remained untracked, and the trusted origin
  remained exactly `https://atlas.internal`.
- [x] Agent and Core execution gates remained exactly `restart-service`; the
  production registry remained exactly one tuple:
  `restart-service / proxmox / qemu`.

### Post-hardening RC1 execution validation

Validated on commit `0bddaf6ee46fbef94a2a1eb9f20cfcb1db0ca2be` using a fresh
isolated production-like stack, planning session
`candidate-plan-fa0a537f0715ad4f607287801dc6345e8b3f87ead146f0abb611a962ba6bd75e`,
and workflow
`candidate-workflow-783edad93fa08cf30c039b92fa94db0098b7431e170a37ee57c864adef28417d`.

- [x] Authenticated Agent-to-worker execution traversed the segmented relay.
- [x] Worker execution succeeded with uid `10001`, read-only rootfs,
  `no-new-privileges`, zero effective capabilities, and the
  `runsc-squid+atlas-workspace` sandbox profile.
- [x] Exactly `services/atlas-agent/tests/test_execution_engine.py` changed,
  with patch digest
  `sha256:8a97f55e972fadfe5d2e0a3d49456b38a057be61794da862ee4ad00c36e2455f`.
- [x] Exact zero-check verification passed, review approved with zero findings,
  and the machine-readable audit chain validated without a failure code.
- [x] The workflow stopped at `awaiting_commit_approval`; commit approval
  `approval-commit-candidate-workflow-783edad93fa08cf30c039b92fa94db0098b7431e170a37ee57c864adef28417d`
  remains pending and no validation-only commit was created.
- [x] The validation marker was restored and the isolated stack, volumes, and
  locally built smoke images were removed. The retained smoke override was not
  modified.

### RC1 Python lint baseline

The blocking RC1 Ruff gate checks Python files changed after commit
`0216b7bfe7f3b160a762269802aa34244ae70a72`, including untracked Python files,
using the pinned Ruff version in each service's development requirements. Core
checks `services/atlas-core/app`; Core has no separate `tests/` directory. Agent
checks both `services/atlas-agent/app` and `services/atlas-agent/tests`. Changed
production and test files must pass: no new Ruff violation may be introduced by
RC1 changes. Existing documented debt does not block RC1 by itself and remains
tracked for later cleanup rather than being fixed as release scope.

A fresh repository-wide informational scan with the validated toolchain on
2026-08-13 reports exactly 90 Core findings and 20 Agent findings. The Agent
count supersedes the earlier 18-finding observation; do not use the older
expected count of 22 unless it is independently reproduced.

The commands above show the repository-local virtual environment used for local
release validation. CI installs the same development requirements into the
Python environment supplied by `actions/setup-python`, so its equivalent
commands intentionally use `python` without the local `.venv` path prefix.

### Manual release sign-off

- [x] Release lead confirms changelog entry names the intended tag and scope.
- [x] Rollback path and restore procedures are reviewed and approved for this RC.
- [x] Operator confirms the upgrade and post-upgrade smoke verification
  procedure was reviewed.
- [x] Release blocker list is empty for the following:
  - no auto-approve, no auto-execute,
  - no push, tag, release publication, remote deploy, and no rollback automation.
- [x] Operator sign-off and date are recorded in release notes or issue tracker:
  - Sign-off name: Kenny Horner
  - Sign-off date: 2026-08-13
  - Release candidate commit: `0c7fde2c233799453948a81fd42b53717524f4c1`

- [x] Changelog, version, tag name, upgrade notes, and manual rollback notes are
  reviewed.
- [x] Use an immutable RC tag that does not overwrite existing release tags.
  `atlas-v0.6-rc1.9` was published at
  `6d85df5b112b4bde28ec31fc60cce88560c9dbfc` on 2026-08-13 and remains the
  immutable validated RC baseline.

### Atlas v0.6.0 final release

Authorized final tag candidate: `atlas-v0.6.0`.

- [x] Record the exact final integration commit SHA:
  `2d4a1b1929316589cdf6ea96993442b430826f10` on `main`.
- [x] Run and record the complete final technical validation. The local
  validation matrix and both required CI workflows are green.

The final local validation matrix was recorded on 2026-08-13 at
`d4abb0016f95aab3bee7ef7ce7820fb3fd941388`. Commands ran from `/opt/atlas`
unless a different working directory is shown:

| Command | Working directory | Exit | Result |
| --- | --- | ---: | --- |
| `PATH=/opt/atlas/.venv/bin:$PATH ./scripts/rc1-python-ruff-gate services/atlas-core` | `/opt/atlas` | 0 | Baseline-aware Core Ruff passed. |
| `PATH=/opt/atlas/.venv/bin:$PATH python -m pytest -q` | `/opt/atlas/services/atlas-core` | 0 | 692 passed; 1 accepted dependency deprecation warning. |
| `PATH=/opt/atlas/.venv/bin:$PATH ./scripts/rc1-python-ruff-gate services/atlas-agent` | `/opt/atlas` | 0 | Baseline-aware Agent Ruff passed. |
| `PATH=/opt/atlas/.venv/bin:$PATH PYTHONPATH=services/atlas-agent python -m pytest -q services/atlas-agent/tests` | `/opt/atlas` | 0 | 816 passed; 1 accepted dependency deprecation warning. |
| `npm ci` | `/opt/atlas/services/mission-control` | 0 | Clean install passed; 284 packages installed. |
| `npm audit --package-lock-only --audit-level=high` | `/opt/atlas/services/mission-control` | 0 | Zero vulnerabilities. |
| `npm run lint` | `/opt/atlas/services/mission-control` | 0 | 0 errors; 1 accepted hook warning. |
| `npm test -- --run` | `/opt/atlas/services/mission-control` | 0 | 28 files and 190 tests passed. |
| `npm run build` | `/opt/atlas/services/mission-control` | 0 | Production build passed with the accepted 681.92 kB chunk warning. |
| `/opt/atlas/.venv/bin/python -m pip_audit -r services/atlas-core/requirements.txt` | `/opt/atlas` | 0 | No known vulnerabilities. |
| `/opt/atlas/.venv/bin/python -m pip_audit -r services/atlas-core/requirements-dev.txt` | `/opt/atlas` | 0 | No known vulnerabilities. |
| `/opt/atlas/.venv/bin/python -m pip_audit -r services/atlas-agent/requirements.txt` | `/opt/atlas` | 0 | No known vulnerabilities. |
| `/opt/atlas/.venv/bin/python -m pip_audit -r services/atlas-agent/requirements-dev.txt` | `/opt/atlas` | 0 | No known vulnerabilities. |
| `docker compose --env-file /dev/null -f compose.production.yaml config --no-interpolate --quiet` | `/opt/atlas` | 0 | Production Compose render passed. |
| `docker compose --env-file /dev/null -f compose.production.yaml -f compose.https.yaml config --no-interpolate --quiet` | `/opt/atlas` | 0 | Production plus HTTPS Compose render passed. |
| `./scripts/data-recovery-gate` | `/opt/atlas` | 0 | Tamper rejection, backup, retention, restore, and persistence passed. |
| `./scripts/container-release-gate` | `/opt/atlas` | 0 | Images, isolated runtime, worker hardening, Codex sandbox, HTTP/HTTPS, recovery, and Rest Server gates passed. |
| `git grep -nF '# Atlas RC1 validation smoke marker.' -- .` | `/opt/atlas` | 1 | Expected: validation marker absent from tracked files. |
| `git diff --check` | `/opt/atlas` | 0 | Passed. |

The isolated container gate verified the worker runtime hardening, Codex
`atlas-workspace` write proof, and outside-workspace mutation denial. The
published RC baseline remains immutable: `atlas-v0.6-rc1.9` resolves to
`6d85df5b112b4bde28ec31fc60cce88560c9dbfc`. The local operator harness
`compose.execution-smoke.override.yaml` remained intentionally untracked and
outside release provenance.

- [x] Confirm required CI checks passed on exact validated integration commit
  `2d4a1b1929316589cdf6ea96993442b430826f10`:
  - Quality gates: SUCCESS, GitHub Actions run `31753221630`.
  - Container release gate: SUCCESS, GitHub Actions run `31753221621`.
  - Both required workflows passed on that exact SHA. Together with the local
    matrix above, the complete final technical validation is green.
- [x] Re-review dependency and accepted-advisory status for the final release.
  npm reports zero vulnerabilities, all four Python requirement audits report
  no known vulnerabilities, and no accepted security advisory remains.
- [x] Confirm the final tracked tree contains only intended release files and
  that local-only smoke artifacts remain outside release provenance.
- [x] Record final operator/release-lead sign-off name and date:
  - Sign-off name: Kenny Horner
  - Sign-off date: 2026-08-13
- [x] Confirm `atlas-v0.6.0` was unused before final tag preparation on
  2026-08-13. It must still be reconfirmed immediately before tag creation.
- [x] The immutable annotated `atlas-v0.6.0` tag was published at
  `03c1e03099b0f638dc674235312a3b3e70768c2f` after the required CI passed on
  that final documentation SHA.

### Core

- [x] `PATH=/opt/atlas/.venv/bin:$PATH ./scripts/rc1-python-ruff-gate services/atlas-core`
- [x] `cd services/atlas-core && PATH=/opt/atlas/.venv/bin:$PATH python -m pytest -q`
- [x] Execution candidate, planning-intake, and route-contract tests pass.
- [x] API/OpenAPI contract regression is current.

### Atlas Agent

- [x] `PATH=/opt/atlas/.venv/bin:$PATH ./scripts/rc1-python-ruff-gate services/atlas-agent`
- [x] `PATH=/opt/atlas/.venv/bin:$PATH PYTHONPATH=services/atlas-agent python -m pytest -q services/atlas-agent/tests`
- [x] End-to-end candidate workflow test passes.
- [x] Audit-chain validator tests pass.
- [x] Restart-recovery matrix tests pass.
- [x] Concurrency and idempotency tests pass.
- [x] Commit-path security tests pass.
- [x] Roadmap workflow regression tests pass.

### Mission Control

- [x] `cd services/mission-control && npm run lint`
- [x] `cd services/mission-control && npm test -- --run`
- [x] `cd services/mission-control && npm run build`
- [x] UI does not imply unsupported Phase 3 execution controls.

### Security and release operation

- [x] Approval-boundary review confirms exact immutable implementation, verification, and commit approvals.
- [x] No automatic approval, automatic execution, push, tag, release, remote deploy, or rollback path is enabled.
- [x] No secrets, logs, `jcode/`, local state, dependency folders, virtual environments, or generated builds are committed.
- [x] State migration and restart-recovery tests pass.
- [x] Docker or Compose smoke validation passes when deployment packaging is in scope.
- [x] `git diff --check` passes.
- [x] `git status --short` is clean except explicitly local-only ignored directories before tagging.
- [x] Review docs for RC tag/sequence selection before creating the next release tag.
