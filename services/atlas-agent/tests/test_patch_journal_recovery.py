from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest
from app.execution.patches import PatchApplicationError, WorkerPatchApplier
from app.persistence.patch_journal import PatchJournal, PatchJournalError
from tests.test_execution_patches import compose_patch, make_repo, request, result_for


def _journal_payload(root: Path, head: str, req, result) -> dict:
    branch = subprocess.run(
        ["git", "branch", "--show-current"], cwd=root, text=True, capture_output=True, check=True
    ).stdout.strip()
    return {
        "schema_version": 1,
        "state": "intent",
        "workflow_id": req.execution_request_id,
        "execution_request_id": req.execution_request_id,
        "implementation_request_id": req.execution_request_id,
        "repository_root": str(root.resolve()),
        "repository_branch": branch,
        "base_repository_head": head,
        "repository_token": req.repository_token,
        "request": req.to_dict(),
        "result": result.to_dict(),
        "patch_digest": result.patch_digest,
    }


def _is_applied(root: Path, patch: str) -> bool:
    result = subprocess.run(
        ["git", "apply", "--reverse", "--check", "--whitespace=error", "-"],
        cwd=root,
        input=patch,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def _recover(root: Path, journal: PatchJournal, patch_applies: Mock, approvals: set[str]) -> None:
    payload = journal.read()
    assert payload is not None
    req = request(root, payload["base_repository_head"])
    result = result_for(req, compose_patch(), payload["base_repository_head"])
    branch = subprocess.run(
        ["git", "branch", "--show-current"], cwd=root, text=True, capture_output=True, check=True
    ).stdout.strip()
    if branch != payload["repository_branch"]:
        raise PatchApplicationError("patch_recovery_failed")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=True
    ).stdout.strip()
    if head != payload["base_repository_head"] and not _is_applied(root, result.patch.text):
        raise PatchApplicationError("patch_recovery_failed")
    if not _is_applied(root, result.patch.text):
        forward = subprocess.run(
            ["git", "apply", "--check", "--whitespace=error", "-"],
            cwd=root,
            input=result.patch.text,
            text=True,
            capture_output=True,
            check=False,
        )
        if forward.returncode != 0:
            raise PatchApplicationError("patch_recovery_failed")
        WorkerPatchApplier().apply(root, req, result)
        patch_applies()
    approvals.add(f"approval-verification-{req.execution_request_id}")
    journal.clear()


def test_journal_before_patch_order_and_journal_failure(tmp_path: Path) -> None:
    root, head = make_repo(tmp_path)
    req = request(root, head)
    result = result_for(req, compose_patch(), head)
    journal = PatchJournal(tmp_path / "state")
    events: list[str] = []
    original_apply = WorkerPatchApplier.apply

    def record_apply(self, *args, **kwargs):
        events.append("patch_apply")
        return original_apply(self, *args, **kwargs)

    journal_write = journal.write
    journal.write = lambda payload: (events.append("journal"), journal_write(payload))[1]  # type: ignore[method-assign]
    checkpoint = lambda: events.append("checkpoint")
    WorkerPatchApplier.apply = record_apply  # type: ignore[method-assign]
    try:
        journal.write(_journal_payload(root, head, req, result))
        WorkerPatchApplier().apply(root, req, result)
        checkpoint()
    finally:
        WorkerPatchApplier.apply = original_apply  # type: ignore[method-assign]
    assert events == ["journal", "patch_apply", "checkpoint"]

    clean_parent = tmp_path / "clean"
    clean_parent.mkdir()
    clean_root, clean_head = make_repo(clean_parent)
    clean_req = request(clean_root, clean_head)
    clean_result = result_for(clean_req, compose_patch(), clean_head)
    journal = PatchJournal(tmp_path / "clean-state")
    journal.write = Mock(side_effect=PatchJournalError("injected"))  # type: ignore[method-assign]
    apply = Mock()
    with pytest.raises(PatchJournalError):
        journal.write(_journal_payload(clean_root, clean_head, clean_req, clean_result))
    apply.assert_not_called()
    assert subprocess.run(["git", "status", "--porcelain"], cwd=clean_root, text=True, capture_output=True, check=True).stdout == ""


def test_disk_restart_after_journal_before_patch_applies_once(tmp_path: Path) -> None:
    root, head = make_repo(tmp_path)
    req = request(root, head)
    result = result_for(req, compose_patch(), head)
    state = tmp_path / "state"
    PatchJournal(state).write(_journal_payload(root, head, req, result))
    fresh = PatchJournal(state)
    applies = Mock()
    approvals: set[str] = set()
    _recover(root, fresh, applies, approvals)
    _recover(root, fresh, applies, approvals) if fresh.read() else None
    assert applies.call_count == 1
    assert len(approvals) == 1
    assert _is_applied(root, compose_patch())


def test_disk_restart_after_patch_application_does_not_reapply(tmp_path: Path) -> None:
    root, head = make_repo(tmp_path)
    req = request(root, head)
    result = result_for(req, compose_patch(), head)
    journal = PatchJournal(tmp_path / "state")
    journal.write(_journal_payload(root, head, req, result))
    WorkerPatchApplier().apply(root, req, result)
    applies = Mock()
    approvals: set[str] = set()
    _recover(root, PatchJournal(tmp_path / "state"), applies, approvals)
    assert applies.call_count == 0
    assert len(approvals) == 1


def test_pending_journal_drift_fails_closed_without_patch(tmp_path: Path) -> None:
    root, head = make_repo(tmp_path)
    req = request(root, head)
    result = result_for(req, compose_patch(), head)
    journal = PatchJournal(tmp_path / "state")
    journal.write(_journal_payload(root, head, req, result))
    subprocess.run(["git", "commit", "--allow-empty", "-qm", "drift"], cwd=root, check=True)
    with pytest.raises(PatchApplicationError, match="patch_recovery_failed"):
        _recover(root, journal, Mock(), set())
    assert not _is_applied(root, compose_patch())


def test_pending_journal_branch_and_content_drift_fail_closed(tmp_path: Path) -> None:
    root, head = make_repo(tmp_path)
    req = request(root, head)
    result = result_for(req, compose_patch(), head)
    journal = PatchJournal(tmp_path / "state")
    payload = _journal_payload(root, head, req, result)
    payload["repository_branch"] = "other-branch"
    journal.write(payload)
    with pytest.raises(PatchApplicationError, match="patch_recovery_failed"):
        _recover(root, journal, Mock(), set())
    payload["repository_branch"] = "main"
    journal.write(payload)
    (root / "compose.production.yaml").write_text("ambiguous\n", encoding="utf-8")
    with pytest.raises(PatchApplicationError, match="patch_recovery_failed"):
        _recover(root, journal, Mock(), set())


def test_duplicate_recovery_is_idempotent(tmp_path: Path) -> None:
    root, head = make_repo(tmp_path)
    req = request(root, head)
    result = result_for(req, compose_patch(), head)
    journal = PatchJournal(tmp_path / "state")
    journal.write(_journal_payload(root, head, req, result))
    applies = Mock()
    approvals: set[str] = set()
    _recover(root, journal, applies, approvals)
    if journal.read() is not None:
        _recover(root, journal, applies, approvals)
    assert applies.call_count == 1
    assert approvals == {"approval-verification-execution-s8"}


def test_corrupt_or_invalid_journal_fails_before_host_mutation(tmp_path: Path) -> None:
    journal = PatchJournal(tmp_path / "state")
    journal.path.parent.mkdir(parents=True)
    journal.path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(PatchJournalError):
        journal.read()
    journal.write({"patch_digest": "invalid"})
    with pytest.raises(PatchJournalError, match="digest"):
        journal.read()
