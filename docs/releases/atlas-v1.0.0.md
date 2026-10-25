# Atlas v1.0.0: approved repository actions

This release selects the bounded repository-edit capability implemented through
v0.66–v1.00. It preserves operator ownership of implementation, verification,
review and local commit as distinct exact-request approval boundaries.

## Operator-visible capability

An approved repository edit runs in an isolated disposable workspace against
an immutable request and expected repository revision. Only the allowed changes
can become a reviewed candidate. Verification and local commit require their
own later exact approvals. Lost responses are reconciled by original request
identity without resubmission, automatic replay or local fallback. Durable
terminal results survive restart; uncertain execution stays unknown.

Worker health separates configuration, observed isolation and authority. It
reports all five durable states and refuses unreadable/corrupt state instead
of implying healthy emptiness. Health, diagnostic reports and source hashes do
not grant execution permission. Relay connections, process lifetimes, request
bodies, output and patches have explicit bounds.

## Validation and release identity

The local closeout at `79fe41e3` records 1,147 Agent tests, 175 worker tests,
27 script tests, 72 guarded workflow checks, configured lint, independent runsc
observations and existing isolated container/recovery gates. The tested source
is `7b4363a4ad669da52d7ad8214d948ce6628ff4d4`; later closeout edits were docs only.
See the [detailed acceptance record](../architecture/v0.91-v1.00-repository-action-plan.md).

Local tests are not final GitHub release acceptance. Before tagging, both
GitHub workflows must pass on the exact resulting main commit and the existing
pre-tag evidence command must return ready. The annotated `atlas-v1.0.0` tag
records that final SHA and CI run IDs. See the
[release procedure](../RELEASE_CHECKLIST.md#v100-repository-action-release-acceptance).

## Known limitations and excluded authority

Pinned Codex CLI 0.147.0 still reports the nested patch-helper network namespace
unavailable under runsc. Sandboxed shell edits have separate observed support;
full runtime readiness is not proven. This release does not turn on a backend,
run a model, consume account credentials or approve a new native request.

The seven installation blockers and 67 fixed-false fields remain unchanged.
Installation/external workflows need their own selected contracts and
implementation. The successor control plane remains deferred. Running-image
parity, supported-environment production operator acceptance, and production
activation were not evaluated by this release selection. Security, upgrade,
backup and recovery-target acceptance for production remain separate.

No deployment, runtime enablement or GitHub release-page publication is part of
the selected merge/tag operation. Existing production containers stay unchanged.
