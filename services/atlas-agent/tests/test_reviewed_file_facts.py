"""Saved review facts remain immutable, bound, and independent of the checkout."""

import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest
from app.persistence.snapshot import (
    StatePersistenceError,
    _decode_reviewed_evidence,
    _encode_reviewed_evidence,
)
from app.repository.evidence import (
    reviewed_evidence_fingerprint,
    validate_reviewed_evidence,
)
from app.repository.models import CommitRequest, ReviewedChange, ReviewedChangeEvidence
from app.workflow.models import WorkflowSessionState
from app.workflow.state import WorkflowStateStore
from tests.routes.test_workflow import (
    candidate_workflow_session,
    commit_ready_workflow,
    make_client,
    save_candidate_workflow,
    save_commit_approval,
)
from tests.test_state_persistence import coordinator, session


def facts(root: Path) -> ReviewedChangeEvidence:
    evidence = ReviewedChangeEvidence(
        repository_root=root,
        expected_branch="feature",
        expected_head="abc123",
        reviewed_files=(Path("file.txt"),),
        commit_message="Reviewed fixture",
        changes=(ReviewedChange(Path("file.txt"), " M", "b" * 64, git_mode="100644"),),
        fingerprint="",
    )
    return replace(evidence, fingerprint=reviewed_evidence_fingerprint(evidence))


def request_for(evidence: ReviewedChangeEvidence) -> CommitRequest:
    return CommitRequest(
        evidence.repository_root,
        evidence.expected_branch,
        evidence.expected_head,
        evidence.reviewed_files,
        evidence.commit_message,
    )


def test_released_version_two_digest_is_unchanged() -> None:
    evidence = facts(Path("/repo"))
    assert (
        evidence.fingerprint
        == "6e3627800f6eabf7118eaeca27f0e5e68c54e27e977641ab361b7147267f67a3"
    )
    validate_reviewed_evidence(evidence, request_for(evidence), evidence.fingerprint)


@pytest.mark.parametrize(
    "field,value",
    [
        ("git_mode", "100755"),
        ("content_sha256", "c" * 64),
        ("path", Path("other.txt")),
        ("status", "A "),
        ("rename_source", Path("old.txt")),
        ("deletion_marker", "deleted"),
    ],
)
def test_saved_file_tampering_cannot_keep_approved_fingerprint(field, value) -> None:
    evidence = facts(Path("/repo"))
    changed = replace(
        evidence, changes=(replace(evidence.changes[0], **{field: value}),)
    )
    with pytest.raises(ValueError):
        validate_reviewed_evidence(changed, request_for(evidence), evidence.fingerprint)


@pytest.mark.parametrize(
    "field,value",
    [
        ("version", True),
        ("version", 1),
        ("changes", {}),
        ("expected_head", []),
        ("unexpected", "field"),
    ],
)
def test_malformed_saved_manifest_is_refused(field, value) -> None:
    payload = _encode_reviewed_evidence(facts(Path("/repo")))
    payload[field] = value
    with pytest.raises(StatePersistenceError):
        _decode_reviewed_evidence(payload)


def test_manifest_round_trip_never_reopens_checkout(tmp_path: Path) -> None:
    evidence = facts(tmp_path / "removed-repository")
    workflow = replace(
        session(tmp_path, WorkflowSessionState.BLOCKED),
        commit_request=request_for(evidence),
        reviewed_files=evidence.reviewed_files,
        expected_branch=evidence.expected_branch,
        expected_head=evidence.expected_head,
        reviewed_content_fingerprint=evidence.fingerprint,
        reviewed_change_evidence=evidence,
    )
    state = WorkflowStateStore()
    persistence = coordinator(tmp_path / "state", state)
    persistence.initialize()
    persistence.mutate_aggregate(
        lambda workflows, approvals: workflows.create_session(workflow)
    )
    restored = WorkflowStateStore()
    with patch(
        "app.repository.inspector.GitInspector.inspect",
        side_effect=AssertionError("No live inspection"),
    ):
        coordinator(tmp_path / "state", restored).initialize()
    assert (
        restored.get_session(workflow.identifier).reviewed_change_evidence == evidence
    )
    assert not evidence.repository_root.exists()


def test_invalid_in_memory_facts_cannot_be_persisted(tmp_path: Path) -> None:
    evidence = facts(tmp_path)
    workflow = replace(
        session(tmp_path, WorkflowSessionState.BLOCKED),
        commit_request=request_for(evidence),
        reviewed_files=evidence.reviewed_files,
        expected_branch=evidence.expected_branch,
        expected_head=evidence.expected_head,
        reviewed_content_fingerprint=evidence.fingerprint,
        reviewed_change_evidence=replace(evidence, commit_message="Different request"),
    )
    state = WorkflowStateStore()
    persistence = coordinator(tmp_path / "state", state)
    persistence.initialize()
    with pytest.raises(StatePersistenceError):
        persistence.mutate_aggregate(
            lambda workflows, approvals: workflows.create_session(workflow)
        )
    assert state.get_session(workflow.identifier) is None


def workflow_with_saved_facts(root: Path):
    workflow = commit_ready_workflow(candidate_workflow_session(root))
    request = workflow.commit_request
    evidence = ReviewedChangeEvidence(
        repository_root=request.repository_root,
        expected_branch=request.expected_branch,
        expected_head=request.expected_head,
        reviewed_files=request.paths,
        commit_message=request.message,
        changes=tuple(
            ReviewedChange(path, " M", "b" * 64, git_mode="100755")
            for path in request.paths
        ),
        fingerprint="",
    )
    evidence = replace(evidence, fingerprint=reviewed_evidence_fingerprint(evidence))
    workflow = replace(
        workflow,
        reviewed_change_evidence=evidence,
        reviewed_content_fingerprint=evidence.fingerprint,
    )
    return workflow


def test_commit_response_uses_saved_facts_without_execution_or_inspection(
    tmp_path, monkeypatch
) -> None:
    client, container, engine, orchestrator = make_client(tmp_path, monkeypatch)
    workflow = workflow_with_saved_facts(tmp_path)
    request = workflow.commit_request
    save_candidate_workflow(container, workflow)
    save_commit_approval(container, workflow)
    with (
        patch(
            "app.repository.inspector.GitInspector.inspect",
            side_effect=AssertionError("No live inspection"),
        ),
        patch(
            "app.workflow.engine.WorkflowEngine.resume",
            side_effect=AssertionError("No execution"),
        ),
    ):
        response = client.get(
            "/api/v1/agent/workflows/workflow-123/implementation-request"
        )
    engine.resume.assert_not_called()
    orchestrator.run.assert_not_awaited()
    assert response.status_code == 200
    body = response.json()["commit_request"]
    assert body["reviewed_changes"] == [
        {
            "path": str(path),
            "change": "modified",
            "executable": True,
            "content_sha256": "b" * 64,
            "rename_source": None,
        }
        for path in request.paths
    ]
    assert body["commit_approval_status"] == "pending"
    assert "git_mode" not in body["reviewed_changes"][0]
    assert (
        container.workflow_state.get_session(workflow.identifier).state
        is WorkflowSessionState.AWAITING_COMMIT_APPROVAL
    )


def persisted_facts(tmp_path):
    evidence = facts(tmp_path / "repository")
    workflow = replace(
        session(tmp_path, WorkflowSessionState.BLOCKED),
        commit_request=request_for(evidence),
        reviewed_files=evidence.reviewed_files,
        expected_branch=evidence.expected_branch,
        expected_head=evidence.expected_head,
        reviewed_content_fingerprint=evidence.fingerprint,
        reviewed_change_evidence=evidence,
    )
    persistence = coordinator(tmp_path / "state")
    persistence.initialize()
    persistence.mutate_aggregate(
        lambda workflows, approvals: workflows.create_session(workflow)
    )
    return persistence, workflow


@pytest.mark.parametrize(
    "change", ["mode", "message", "unknown", "shape", "workflow_link"]
)
def test_restart_refuses_tampered_saved_facts(tmp_path, change):
    persistence, workflow = persisted_facts(tmp_path)
    payload = json.loads(persistence.snapshot_path.read_text())
    record = payload["workflow_state"]["sessions"][workflow.identifier]
    manifest = record["reviewed_change_evidence"]
    if change == "mode":
        manifest["changes"][0]["git_mode"] = "100755"
    elif change == "message":
        manifest["commit_message"] = "Unapproved message"
    elif change == "unknown":
        manifest["changes"][0]["raw_content"] = "Never accepted"
    elif change == "shape":
        manifest["changes"][0]["git_mode"] = []
    else:
        record["expected_head"] = "different-head"
    persistence.snapshot_path.write_text(json.dumps(payload))
    restored = WorkflowStateStore()
    with pytest.raises(StatePersistenceError):
        coordinator(tmp_path / "state", restored).initialize()
    assert restored.get_session(workflow.identifier) is None


def test_older_snapshot_without_manifest_stays_readable_and_does_not_regenerate(
    tmp_path,
):
    persistence, workflow = persisted_facts(tmp_path)
    payload = json.loads(persistence.snapshot_path.read_text())
    del payload["workflow_state"]["sessions"][workflow.identifier][
        "reviewed_change_evidence"
    ]
    persistence.snapshot_path.write_text(json.dumps(payload))
    restored = WorkflowStateStore()
    coordinator(tmp_path / "state", restored).initialize()
    loaded = restored.get_session(workflow.identifier)
    assert loaded.reviewed_change_evidence is None
    assert loaded.reviewed_content_fingerprint == workflow.reviewed_content_fingerprint
    assert loaded.commit_request == workflow.commit_request


@pytest.mark.parametrize(
    "mismatch",
    ["approval_fingerprint", "approval_message", "workflow_request", "manifest_mode"],
)
def test_api_does_not_present_unbound_facts(tmp_path, monkeypatch, mismatch):
    from app.routes.workflow import _saved_reviewed_files

    _client, container, _, _ = make_client(tmp_path, monkeypatch)
    workflow = workflow_with_saved_facts(tmp_path)
    save_candidate_workflow(container, workflow)
    save_commit_approval(container, workflow)
    approval = container.approval_repository.get_request(
        "approval-commit-workflow-123"
    ).decision.request
    if mismatch == "approval_fingerprint":
        approval = replace(
            approval,
            commit_metadata=replace(
                approval.commit_metadata, reviewed_content_fingerprint="c" * 64
            ),
        )
    elif mismatch == "approval_message":
        approval = replace(
            approval,
            commit_metadata=replace(
                approval.commit_metadata, commit_message="Different message"
            ),
        )
    elif mismatch == "workflow_request":
        workflow = replace(
            workflow,
            commit_request=replace(
                workflow.commit_request, expected_head="different-head"
            ),
        )
    else:
        evidence = workflow.reviewed_change_evidence
        workflow = replace(
            workflow,
            reviewed_change_evidence=replace(
                evidence,
                changes=(
                    replace(evidence.changes[0], git_mode="100644"),
                    *evidence.changes[1:],
                ),
            ),
        )
    assert _saved_reviewed_files(workflow, approval) is None


def test_browser_fixture_matches_native_read_only_projection(tmp_path, monkeypatch):
    client, container, _, _ = make_client(tmp_path, monkeypatch)
    workflow = workflow_with_saved_facts(Path("/atlas-fixture/repository"))
    save_candidate_workflow(container, workflow)
    save_commit_approval(container, workflow)
    response = client.get("/api/v1/agent/workflows/workflow-123/implementation-request")
    fixture = (
        Path(__file__).resolve().parents[2]
        / "mission-control/e2e/fixtures/readable-commit-review.json"
    )
    assert response.status_code == 200
    assert response.json() == json.loads(fixture.read_text())
