from __future__ import annotations

from pathlib import Path

import pytest
from app.persistence.patch_journal import PatchJournal, PatchJournalError


def test_patch_journal_round_trips_bounded_intent_and_uses_private_permissions(tmp_path: Path) -> None:
    journal = PatchJournal(tmp_path / "state")
    payload = {
        "schema_version": 1,
        "workflow_id": "workflow-1",
        "execution_request_id": "execution-1",
        "implementation_request_id": "implementation-1",
        "base_repository_head": "a" * 40,
        "repository_branch": "main",
        "changed_files": ["services/atlas-agent/tests/test_execution_engine.py"],
        "patch_digest": "sha256:" + "b" * 64,
        "state": "intent",
        "patch": "bounded patch body",
    }
    journal.write(payload)
    assert journal.read() == payload
    assert journal.path.stat().st_mode & 0o777 == 0o600
    journal.clear()
    assert journal.read() is None


def test_patch_journal_rejects_corrupt_payload(tmp_path: Path) -> None:
    journal = PatchJournal(tmp_path / "state")
    journal.path.parent.mkdir(parents=True)
    journal.path.write_text("[]", encoding="utf-8")
    with pytest.raises(PatchJournalError, match="invalid"):
        journal.read()


def test_patch_journal_rejects_invalid_digest(tmp_path: Path) -> None:
    journal = PatchJournal(tmp_path / "state")
    journal.write({"patch_digest": "not-a-digest"})
    with pytest.raises(PatchJournalError, match="digest"):
        journal.read()
