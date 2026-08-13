# Contributing to Atlas

Atlas is a local-first infrastructure control plane. Contributions must preserve operator control, provider neutrality, and explicit approval boundaries.

## Coding standards

- Use small, production-ready changes.
- Follow existing module organization and naming.
- Prefer typed contracts and deterministic behavior.
- Avoid unrelated rewrites, broad lint cleanup, and unnecessary dependencies.
- Keep secrets out of source, logs, fixtures, and snapshots.

## Architecture rules

- Understanding comes before automation.
- Atlas Core remains authoritative for Atlas platform state.
- Discovery Center remains read-only and provider-neutral by default.
- Atlas Agent orchestrates local engineering workflows but does not own external tools or Atlas Core state.
- Mission Control must not bypass Core or Agent approval boundaries.
- New execution capabilities require an approved design, explicit contracts, recovery behavior, and tests before UI controls.

## Contract-first development

- Public APIs use dedicated DTOs.
- Caller-controlled request models must reject unknown fields.
- Error codes must be controlled and owned by the subsystem that emits them.
- Public fields should remain stable unless a compatibility impact is documented.
- Internal dataclasses and domain models should not leak into OpenAPI by accident.

## Approval philosophy

Atlas never auto-approves or auto-executes side effects. Implementation, verification, and commit stages require exact approvals bound to immutable requests. Later-generated work must not inherit earlier broader approval. Rejected, stale, mismatched, or missing approvals block the workflow.

## Testing requirements

Run the smallest meaningful focused tests while developing, then run the release gates required by the change. Phase 3 candidate workflow changes require coverage for audit linkage, restart recovery, concurrency, approval binding, and path safety.

Common gates:

```bash
cd services/atlas-core
python -m ruff check app tests
python -m pytest -q

cd ../atlas-agent
python -m ruff check app tests
python -m pytest -q

cd ../mission-control
npm run lint
npm test -- --run
npm run build

cd ../..
git diff --check
git status --short
```

## Commit expectations

- Keep commits scoped to the approved task.
- Do not commit local logs, `jcode/`, state directories, virtual environments, dependency folders, secrets, or generated build output.
- Include tests and documentation when behavior changes.
- Do not push, tag, or publish a release unless the operator explicitly requests it.
