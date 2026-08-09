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


def test_patch_applies_only_after_validation(tmp_path: Path) -> None:
    root, head = make_repo(tmp_path)
    patch = """diff --git a/compose.production.yaml b/compose.production.yaml
index 42c1c24..3e6c3af 100644
--- a/compose.production.yaml
+++ b/compose.production.yaml
@@ -1 +1 @@
-image: example/app:1.0
+image: example/app:1.1
"""
    req = request(root, head)
    outcome = WorkerPatchApplier().apply(root, req, result_for(req, patch, head))
    assert outcome.changed_files == ("compose.production.yaml",)
    assert (root / "compose.production.yaml").read_text(encoding="utf-8") == "image: example/app:1.1\n"
    assert git(root, "rev-parse", "HEAD") == head
    assert git(root, "status", "--porcelain") == "M compose.production.yaml"


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
