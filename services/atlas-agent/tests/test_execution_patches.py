"""Tests for Agent-owned worker patch application."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest
from app.execution.patches import PatchApplicationError, WorkerPatchApplier
from app.execution.worker_contracts import (
    BoundedOutput,
    WorkerAttestation,
    WorkerExecutionRequest,
    WorkerExecutionResult,
    WorkerExecutionStatus,
)


def git(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=check)
    return result.stdout.strip()


def request(root: Path, head: str, files: tuple[str, ...] = ("compose.production.yaml",)) -> WorkerExecutionRequest:
    return WorkerExecutionRequest.build(
        execution_request_id="execution-s8",
        workflow_id="workflow-s8",
        candidate_id="candidate-s8",
        candidate_fingerprint="candidate-fingerprint-s8",
        plan_id="plan-s8",
        plan_fingerprint="plan-fingerprint-s8",
        execution_intent="update-compose-stack",
        repository_token="atlas-repository",
        expected_repository_head=head,
        repository_branch="main",
        argv=("codex", "exec", "approved prompt"),
        working_directory=".",
        allowed_affected_files=files,
        timeout_seconds=120,
    )


def make_repo(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "trusted"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "user.email", "test@example.invalid")
    git(root, "config", "user.name", "S8 Test")
    (root / "compose.production.yaml").write_text("image: example/app:1.0\n", encoding="utf-8")
    (root / "forbidden.txt").write_text("unchanged\n", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-qm", "base")
    return root, git(root, "rev-parse", "HEAD")


def result_for(req: WorkerExecutionRequest, patch: str, head: str, files: tuple[str, ...] = ("compose.production.yaml",)) -> WorkerExecutionResult:
    return WorkerExecutionResult(
        schema_version=1,
        execution_request_id=req.execution_request_id,
        status=WorkerExecutionStatus.SUCCEEDED,
        return_code=0,
        stdout=BoundedOutput(""),
        stderr=BoundedOutput(""),
        changed_files=files,
        patch_digest="sha256:" + hashlib.sha256(patch.encode()).hexdigest(),
        patch_size_bytes=len(patch.encode()),
        patch_truncated=False,
        duration_seconds=1,
        failure_code=None,
        workspace_head=head,
        base_repository_head=head,
        patch=BoundedOutput(patch),
        worker_attestation=WorkerAttestation(10001, True, True, "0000000000000000", "runsc"),
    )


def compose_patch() -> str:
    return """diff --git a/compose.production.yaml b/compose.production.yaml
--- a/compose.production.yaml
+++ b/compose.production.yaml
@@ -1 +1 @@
-image: example/app:1.0
+image: example/app:1.1
"""


def test_patch_applies_only_after_validation(tmp_path: Path) -> None:
    root, head = make_repo(tmp_path)
    patch = compose_patch()
    req = request(root, head)
    outcome = WorkerPatchApplier().apply(root, req, result_for(req, patch, head))
    assert outcome.changed_files == ("compose.production.yaml",)
    assert (root / "compose.production.yaml").read_text(encoding="utf-8") == "image: example/app:1.1\n"
    assert git(root, "rev-parse", "HEAD") == head
    assert git(root, "status", "--porcelain") == "M compose.production.yaml"


def test_same_patch_is_idempotent_after_first_application(tmp_path: Path) -> None:
    root, head = make_repo(tmp_path)
    patch = compose_patch()
    req = request(root, head)
    result = result_for(req, patch, head)
    first = WorkerPatchApplier().apply(root, req, result)
    second = WorkerPatchApplier().apply(root, req, result)
    assert first == second
    assert git(root, "status", "--porcelain") == "M compose.production.yaml"


def test_malformed_patch_is_rejected_without_mutation(tmp_path: Path) -> None:
    root, head = make_repo(tmp_path)
    patch = "not a unified diff"
    req = request(root, head)
    with pytest.raises(PatchApplicationError, match="patch_invalid"):
        WorkerPatchApplier().apply(root, req, result_for(req, patch, head))
    assert git(root, "status", "--porcelain") == ""


def test_stale_patch_is_rejected_without_mutation(tmp_path: Path) -> None:
    root, head = make_repo(tmp_path)
    patch = """diff --git a/compose.production.yaml b/compose.production.yaml
--- a/compose.production.yaml
+++ b/compose.production.yaml
@@ -1 +1 @@
-image: example/app:1.0
+image: example/app:1.1
"""
    req = request(root, head)
    git(root, "checkout", "-qb", "change")
    (root / "forbidden.txt").write_text("changed\n", encoding="utf-8")
    git(root, "add", "forbidden.txt")
    git(root, "commit", "-qm", "drift")
    with pytest.raises(PatchApplicationError, match="patch_stale"):
        WorkerPatchApplier().apply(root, req, result_for(req, patch, head))
    assert (root / "compose.production.yaml").read_text(encoding="utf-8") == "image: example/app:1.0\n"


def test_out_of_scope_patch_is_rejected(tmp_path: Path) -> None:
    root, head = make_repo(tmp_path)
    patch = """diff --git a/forbidden.txt b/forbidden.txt
--- a/forbidden.txt
+++ b/forbidden.txt
@@ -1 +1 @@
-unchanged
+changed
"""
    req = request(root, head)
    out = result_for(req, patch, head, ("forbidden.txt",))
    with pytest.raises((PatchApplicationError, ValueError), match="(patch_out_of_scope|changed file is outside approved scope)"):
        WorkerPatchApplier().apply(root, req, out)
    assert (root / "forbidden.txt").read_text(encoding="utf-8") == "unchanged\n"


def test_preexisting_untracked_file_is_preserved(tmp_path: Path) -> None:
    root, head = make_repo(tmp_path)
    (root / "compose.execution-smoke.override.yaml").write_text("local\n")
    req = request(root, head)
    outcome = WorkerPatchApplier().apply(root, req, result_for(req, compose_patch(), head))
    assert outcome.changed_files == ("compose.production.yaml",)
    assert (root / "compose.execution-smoke.override.yaml").read_text() == "local\n"


def test_preexisting_modified_file_is_preserved(tmp_path: Path) -> None:
    root, head = make_repo(tmp_path)
    (root / "forbidden.txt").write_text("local\n")
    req = request(root, head)
    WorkerPatchApplier().apply(root, req, result_for(req, compose_patch(), head))
    assert (root / "forbidden.txt").read_text() == "local\n"


def test_patch_touching_baseline_dirty_file_is_rolled_back(tmp_path: Path) -> None:
    root, head = make_repo(tmp_path)
    (root / "forbidden.txt").write_text("local\n")
    patch = compose_patch() + """diff --git a/forbidden.txt b/forbidden.txt
--- a/forbidden.txt
+++ b/forbidden.txt
@@ -1 +1 @@
-local
+tampered
"""
    req = request(root, head)
    with pytest.raises(PatchApplicationError, match="post_apply_scope_mismatch"):
        WorkerPatchApplier().apply(root, req, result_for(req, patch, head))
    assert (root / "compose.production.yaml").read_text() == "image: example/app:1.0\n"
    assert (root / "forbidden.txt").read_text() == "local\n"


def test_patch_introducing_unapproved_file_is_rolled_back(tmp_path: Path) -> None:
    root, head = make_repo(tmp_path)
    patch = compose_patch() + """diff --git a/unapproved.txt b/unapproved.txt
new file mode 100644
--- /dev/null
+++ b/unapproved.txt
@@ -0,0 +1 @@
+secret
"""
    req = request(root, head)
    with pytest.raises(PatchApplicationError, match="post_apply_scope_mismatch"):
        WorkerPatchApplier().apply(root, req, result_for(req, patch, head))
    assert not (root / "unapproved.txt").exists()
    assert (root / "compose.production.yaml").read_text() == "image: example/app:1.0\n"


def test_changed_files_must_match_actual_patch_delta(tmp_path: Path) -> None:
    root, head = make_repo(tmp_path)
    req = request(root, head)
    with pytest.raises(PatchApplicationError, match="post_apply_scope_mismatch"):
        WorkerPatchApplier().apply(root, req, result_for(req, compose_patch(), head, ()))
    assert git(root, "status", "--porcelain") == ""


def test_changed_files_cannot_claim_unchanged_approved_file(tmp_path: Path) -> None:
    root, head = make_repo(tmp_path)
    req = request(root, head, ("compose.production.yaml", "forbidden.txt"))
    with pytest.raises(PatchApplicationError, match="post_apply_scope_mismatch"):
        WorkerPatchApplier().apply(
            root,
            req,
            result_for(req, compose_patch(), head, ("compose.production.yaml", "forbidden.txt")),
        )
    assert git(root, "status", "--porcelain") == ""


def test_rc1_baseline_shape_succeeds_without_filename_special_case(tmp_path: Path) -> None:
    root, head = make_repo(tmp_path)
    target = root / "services/atlas-agent/tests/test_execution_engine.py"
    target.parent.mkdir(parents=True)
    target.write_text("old\n")
    git(root, "add", str(target.relative_to(root)))
    git(root, "commit", "-qm", "target")
    head = git(root, "rev-parse", "HEAD")
    (root / "compose.execution-smoke.override.yaml").write_text("local\n")
    patch = """diff --git a/services/atlas-agent/tests/test_execution_engine.py b/services/atlas-agent/tests/test_execution_engine.py
--- a/services/atlas-agent/tests/test_execution_engine.py
+++ b/services/atlas-agent/tests/test_execution_engine.py
@@ -1 +1 @@
-old
+new
"""
    req = request(root, head, ("services/atlas-agent/tests/test_execution_engine.py",))
    result = result_for(req, patch, head, ("services/atlas-agent/tests/test_execution_engine.py",))
    outcome = WorkerPatchApplier().apply(root, req, result)
    assert outcome.changed_files == ("services/atlas-agent/tests/test_execution_engine.py",)
    assert (root / "compose.execution-smoke.override.yaml").read_text() == "local\n"
