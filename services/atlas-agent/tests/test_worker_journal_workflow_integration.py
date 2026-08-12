from __future__ import annotations

import subprocess
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from app.execution.backends import WorkerExecutionBackend
from app.execution.engine import ExecutionEngine
from app.execution.patches import WorkerPatchApplier
from app.execution.worker_contracts import BoundedOutput
from app.persistence.snapshot import AgentStatePersistenceCoordinator
from tests.test_execution_patches import result_for
from tests.test_workflow_engine import (
    make_candidate_engine,
    make_candidate_request,
    make_changed_snapshot,
    make_snapshot,
)

TARGET = Path("services/atlas-agent/tests/test_execution_engine.py")


class FakeWorkerClient:
    def __init__(self, patch: str, head: str) -> None:
        self.patch = patch
        self.head = head
        self.calls = 0

    def submit(self, request):
        self.calls += 1
        template = result_for(request, self.patch, self.head)
        result = replace(
            template,
            execution_request_id=request.execution_request_id,
            changed_files=(str(TARGET),),
            patch=BoundedOutput(self.patch),
            patch_digest="sha256:" + sha256(self.patch.encode()).hexdigest(),
        )
        return {"state": "succeeded", "result": result.to_dict()}


def _repo(tmp_path: Path) -> tuple[Path, str, str]:
    root = tmp_path / "repository"
    root.mkdir()
    target = root / TARGET
    target.parent.mkdir(parents=True)
    target.write_text("old\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)
    branch = subprocess.run(["git", "branch", "--show-current"], cwd=root, text=True, capture_output=True, check=True).stdout.strip()
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=True).stdout.strip()
    return root, branch, head


def _patch() -> str:
    return """diff --git a/services/atlas-agent/tests/test_execution_engine.py b/services/atlas-agent/tests/test_execution_engine.py
--- a/services/atlas-agent/tests/test_execution_engine.py
+++ b/services/atlas-agent/tests/test_execution_engine.py
@@ -1 +1 @@
-old
+new
"""


def _fixture(tmp_path: Path, *, root: Path | None = None, state_dir: Path | None = None):
    if root is None:
        root, branch, head = _repo(tmp_path)
    else:
        branch = subprocess.run(["git", "branch", "--show-current"], cwd=root, text=True, capture_output=True, check=True).stdout.strip()
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=True).stdout.strip()
    engine, state, approvals, _execution, _, _, validator = make_candidate_engine(root)
    candidate_request = replace(
        make_candidate_request(root),
        repository_branch=branch,
        repository_head=head,
        affected_files=(TARGET,),
    )
    plan = validator.result.implementation_plan
    assert plan is not None
    plan = replace(plan, repository_root=root, branch=branch, head_commit=head, affected_files=(TARGET,))
    validator.result = replace(
        validator.result,
        implementation_request=candidate_request,
        implementation_plan=plan,
        execution_request=replace(validator.result.execution_request, plan=plan),
        repository_snapshot=make_snapshot(root),
    )
    inspector = engine._repository_inspector_factory.return_value
    clean_snapshot = replace(make_snapshot(root), branch=branch, head_commit=head)
    changed_snapshot = replace(
        make_changed_snapshot(root, modified_files=(str(TARGET),)),
        branch=branch,
        head_commit=head,
    )
    inspector.inspect.side_effect = [clean_snapshot, changed_snapshot]
    client = FakeWorkerClient(_patch(), head)
    engine._execution_engine = ExecutionEngine(
        backend=WorkerExecutionBackend(client, repository_token="atlas-repository")
    )
    persistence = AgentStatePersistenceCoordinator(
        state_dir=state_dir or tmp_path / "state",
        workflow_state=state,
        approval_repository=approvals,
    )
    persistence.initialize()
    engine._state_persistence = persistence
    return engine, state, approvals, persistence, client, root, head


def test_real_candidate_resume_uses_disk_journal_and_recovers_without_worker_rerun(tmp_path: Path) -> None:
    engine, _state, _approvals, persistence, client, root, _ = _fixture(tmp_path)
    original_apply = WorkerPatchApplier.apply
    calls = {"patch": 0}

    def interrupt_before_patch(self, *args, **kwargs):
        calls["patch"] += 1
        raise RuntimeError("crash before patch")

    with patch.object(WorkerPatchApplier, "apply", interrupt_before_patch):
        first = engine.resume("candidate-workflow-1")
    assert first.sprint.phase.value == "blocked"
    assert client.calls == 1
    assert (root / TARGET).read_text(encoding="utf-8") != "new\n"
    assert persistence.read_patch_journal() is not None

    WorkerPatchApplier.apply = original_apply
    recovered_engine, recovered_state, recovered_approvals, _recovered_persistence, recovered_client, _recovered_root, _ = _fixture(
        tmp_path / "fresh",
        root=root,
        state_dir=tmp_path / "state",
    )
    recovered = recovered_engine.resume("candidate-workflow-1")
    assert calls["patch"] == 1
    assert client.calls + recovered_client.calls == 1
    assert recovered.sprint.phase.value == "awaiting_verification_approval"
    assert recovered_state.get_session("candidate-workflow-1").worker_patch_applied is True
    assert recovered_approvals.get_request("approval-verification-candidate-workflow-1") is not None


def test_real_candidate_checkpoint_failure_leaves_recoverable_journal(tmp_path: Path) -> None:
    engine, _state, approvals, persistence, client, root, _ = _fixture(tmp_path)
    original_mutate = persistence.mutate_aggregate
    calls = {"mutate": 0}

    def fail_checkpoint(*args, **kwargs):
        calls["mutate"] += 1
        if calls["mutate"] == 3:
            raise RuntimeError("checkpoint failure")
        return original_mutate(*args, **kwargs)

    persistence.mutate_aggregate = fail_checkpoint
    result = engine.resume("candidate-workflow-1")
    assert result.sprint.phase.value == "blocked"
    assert client.calls == 1
    assert (root / TARGET).read_text(encoding="utf-8") == "new\n"
    assert persistence.read_patch_journal() is not None
    assert approvals.get_request("approval-verification-candidate-workflow-1") is None


def test_real_candidate_fixture_exposes_exact_once_counters(tmp_path: Path) -> None:
    engine, _, approvals, persistence, client, root, _ = _fixture(tmp_path)
    result = engine.resume("candidate-workflow-1")
    assert result.sprint.phase.value in {"awaiting_verification_approval", "blocked"}
    assert client.calls == 1
    assert (root / TARGET).read_text(encoding="utf-8") in {"old\n", "new\n"}
    assert approvals.get_request("approval-verification-candidate-workflow-1") is None or persistence.read_patch_journal() is None
