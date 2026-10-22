# v0.66 repository action implementation acceptance

## v0.66 local closeout

Status: **implementation complete and locally validated; unreleased**.
The validated implementation source is
`26c5656a8ee94e573567c5412c5d383430d5ccb3`; its final validation documentation
is `e2181444`. These are the v0.66 implementation boundary, not the current
branch tip and not a published release. The later process-lifetime change at
`d80d336b` is draft v0.67 work and is excluded from this closeout.

The selected repository-edit outcome completed with separate operator
implementation, verification and local-commit approvals and a valid terminal
audit after reload. The checks and exact fixture identities below substantiate
that bounded result. Remaining qualifications are the nested patch-helper
limitation and the unusable optional binary backup from the model run; its
terminal ledger JSON was retained and the corrected exporter was tested
separately. Neither qualification is rewritten as a pass.

Release acceptance, remote exact-SHA CI, production image parity, production
operator acceptance, activation and publication are not complete or authorized
by this record. No release tag or version publication is implied. Subsequent
versions must remain individually scoped and recorded rather than being
reported as one consolidated v0.70 or v0.77 completion.

## Selected outcome and authority

This record closes the bounded v0.66 repository-action implementation.
Earlier wording described a consolidated v0.70 target; that was not separate
completion of v0.67–v0.70. The operator has now selected the
[sequential v0.66–v0.77 plan](v0.66-v0.77-repository-action-plan.md).
The approved action remains `update-compose-stack`: prepare one bounded
repository edit, apply its patch under Agent ownership, verify and review it,
then create a separately approved local commit. Nothing here is published.

Production deployment, backend enablement, image replacement, push, tags and
publication remain excluded. Core installation activation is still deferred;
none of its seven blockers or 67 fixed-false fields are discharged. This
fixture uses a deliberately local candidate reader, not production Core
provenance. It does not prove a deployed Mission Control operator journey.

## Implementation and measurable acceptance

| Requirement | Result |
| --- | --- |
| Reject substituted repository, revision, branch, directory, file scope, explicit timeout or unsupported environment before dispatch | Covered by adapter and workflow regressions; no worker submission on refusal. |
| Prepare the reviewed request identically to native dispatch | Shared `candidate_worker_execution_context`; canonical serialized request and digest match in regression tests and the fresh model run. Existing wire hashes are preserved; integer and float JSON are not silently reinterpreted. |
| Consume only a response for the exact submitted request | Both POST and original-result GET require the recorded request digest; missing or mismatched digests remain unknown and do not apply a patch. |
| Preserve uncertain outcomes without replay | Original request is durable before submission. Operator reconciliation performs a GET only; restart, concurrency, refusal and TCP response-loss tests preserve one attempt. |
| Preserve separate implementation, verification and commit decisions | Both real fixtures reached `completed`, each with separately recorded operator approvals. The fresh fixture is detailed below. |
| Expose request identity to the operator | Existing workflow detail includes the digest; Mission Control shows an inert, collapsed worker request record. Refresh does not execute or reconcile. |
| Retain bounded diagnostic exports | Private chunked SQLite export verifies source/destination SHA-256, byte count and database integrity, refuses overwrite and removes partial files. A credential-free runsc test copied a 32 KiB database successfully. |

The shared context fixes a rehearsal preparation error: its manually duplicated
integer `120` differed from native float `120.0`. The earlier mismatch remains
in the historical record and its consumed request was never replayed. Fresh
preflight compares the complete canonical request **before** submission.

## Fresh, explicitly approved fixture

The disposable repository is
`/tmp/atlas-repository-acceptance-quwc1a0m/repository`, branch
`atlas-rehearsal`, base HEAD `40b13948e3bf6a24497e15c422a3583c63e5be28`.
Its only edit replaces `example.invalid/atlas-rehearsal:before` with `:after`
for the fixture's `atlas-agent` image in `compose.production.yaml`. No image
was pulled or deployed.

The operator approved one 120-second model invocation and saved-login use for:

- Worker request digest:
  `execution-request-digest-v1:7856dc25f20af2b08cceaca65cccfac4781a0f7bec005409ae2cf103809f4f3d`.
- Native implementation approval SHA-256:
  `a9fec677bb727a860835888ce900de7dbe76772f87cdd36a7e4c135078a1a83b`.
- Untagged local worker image:
  `sha256:0ca4a3eec12bb60cb7228dbd9936bf73a5d4e259a77f0355b970d3d635c9674f`.
- Image/native source file manifest SHA-256:
  `9afc86e56070fda30c9933a02e46fece16b800b5d52761d5de446938d11abe71`.

The pinned CLI remained 0.147.0. The worker used runsc, UID/GID 10001,
read-only root and source repository, no capabilities, no-new-privileges,
private transport and allowlisted egress. Authentication was a read-only
secret with a temporary private CLI copy, not a prompt or argv value.

Preflight, native persisted request and worker ledger digests matched.
The worker returned success and its retained terminal JSON reported one entry,
one attempt and state `completed`. The bounded patch changed only the approved
file. The workflow paused for verification; the operator separately approved
`docker compose --file compose.production.yaml config --no-env-resolution --quiet`
with a 60-second limit. Configuration verification and deterministic review
passed. Verification approval SHA-256:
`56aa923c2e7fc0f92c673ef3b66f053aeaba48166ce55df719a1069de63597ab`.

The operator then separately approved the exact reviewed local commit:
approval SHA-256
`3c8fec10671c463a5c3e624ff1c2e115277d3d2f109a0e19316690a61beddcf4`,
reviewed-content fingerprint
`42c747342084db198588d33ea4b6f2ad7c0e5b692292090153a8c6dc001f6069`.
Atlas committed only `compose.production.yaml` as
`72f65f4c957b7538ffce3b1b141435c44723170a`; native workflow state is
`completed`. A fresh persistence reload preserved completion, and the native
complete audit-chain validator returned `valid=true`. The original fixture also completed as local commit
`d427859d9a1cd9e8ccc3d7121f1763c2fded08f9`, with its digest discrepancy
retained as a historical qualification.

Evidence is private and ignored under
`.task-evidence/v070-repository-acceptance/`: reviewed request/plan, native
preflight, one-shot marker, worker result, exact approval records, verification
and commit outcomes, source manifest, service logs and cleanup records.
Do not commit these logs or credentials. The isolated model project and its
secret/state volumes and networks were removed. All seven production container
identities, image IDs and start times matched before and after the run.

## Limits and supported environment

The pinned CLI's `apply_patch` filesystem helper fails to initialize its nested
network namespace in this runsc environment (`Failed RTM_NEWADDR`). This was
reproduced with credential-free Bubblewrap. Both model runs completed the same
bounded edit through their sandboxed shell; isolation was not relaxed. The
supported demonstrated capability is **sandboxed shell repository editing**,
not successful operation of every CLI helper. Full helper compatibility remains
open and is not silently declared a pass. The operator saw this limitation
before approving the fresh run.

A single large base64 diagnostic output truncated the fresh run's optional
binary SQLite backup. That file fails integrity validation and is not a usable
backup. The complete terminal ledger JSON was retained independently. The
new `scripts/atlas-worker-ledger-export` addresses this specific transport issue
with 2 KiB binary chunks, full hash and SQLite checks; its successful 32 KiB
runsc test is synthetic, not a retroactive repair of the model run's backup.
This work does not claim production database backup/restore acceptance.

## Validation and release boundary

Local validation of the implementation passed:

- Agent: 1,090 tests; repository-defined changed-file Ruff gate.
- Execution worker: 55 tests.
- Mission Control: 2,420 tests in 175 files; lint and production build.
- Export utility: four tests, including corruption/truncation and no overwrite;
  credential-free 32 KiB runsc export with hash and SQLite integrity checks.
- Updated worker image: two real-TCP lost-response/restart tests under runsc;
  nested workspace-write, protected-state denial and authenticated wrong-peer
  denial probe, without account credentials or model calls.

UI lint retains one existing hook-dependency warning; build retains its chunk
size advisory. The full Agent suite must run from the repository root because
existing staging and isolation tests use root-relative paths. Broad unscoped
Ruff reports pre-existing import-order findings; the release's configured
changed-file Ruff gate is the validation used here.

The existing container integration gate exited 0 against clean implementation
commit `26c5656a8ee94e573567c5412c5d383430d5ccb3`. Its worker/relay probes,
container checks, five-volume data recovery and Rest Server replication/recovery
all passed with dummy authentication and a separate disposable project. This
was explicitly runc integration mode, not runsc production acceptance. The
separate hardened runsc probes above cover the selected transport and nested
boundaries. Final production identity comparison was unchanged. No remote
exact-SHA CI, release readiness, tag or publication is claimed here.

## Remaining path toward v1

Review the bounded capability and known helper limitation, then separately
select and authorize any production activation. That selection still needs
trusted Core candidate provenance, immutable repository/policy/credential
references, supported-environment image parity and operator acceptance,
including recovery and disconnect behavior. Validate the selected capability
matrix, security, upgrades, backup/restore and recovery targets against
immutable artifacts. Publish only after separately requested release work.
Installation or external workflow capabilities require their own selected
contracts and implementation; version numbers do not grant those authorities.
