"""Tests for Atlas Agent read-only status endpoints."""

import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.main import create_app
from app.review.models import (
    ReviewCategory,
    ReviewFinding,
    ReviewReport,
    ReviewSeverity,
    ReviewStatus,
)
from app.verification.models import (
    VerificationCheckResult,
    VerificationReport,
    VerificationStatus,
)
from app.version import AGENT_VERSION
from app.workflow.models import SprintPhase, SprintStatus


def run_git(
    repository: Path,
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )


def make_client(
    tmp_path: Path,
    monkeypatch,
) -> tuple[TestClient, object]:
    repository = tmp_path / "repository"
    repository.mkdir()

    run_git(repository, "init")
    run_git(repository, "config", "user.name", "Atlas Tests")
    run_git(
        repository,
        "config",
        "user.email",
        "atlas-tests@example.invalid",
    )

    tracked = repository / "tracked.txt"
    tracked.write_text("initial\n", encoding="utf-8")
    run_git(repository, "add", "tracked.txt")
    run_git(repository, "commit", "-m", "Initial commit")

    settings = Settings(repository_root=repository.resolve())
    monkeypatch.setattr("app.main.load_settings", lambda: settings)

    application = create_app()

    return TestClient(application), application.state.container


def test_repository_status_returns_live_git_snapshot(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client, container = make_client(tmp_path, monkeypatch)

    response = client.get("/api/v1/agent/repository")

    assert response.status_code == 200
    body = response.json()
    assert body["root"] == str(container.settings.repository_root)
    assert body["branch"] is not None
    assert body["head_commit"] is not None
    assert body["is_clean"] is True
    assert body["modified_files"] == []
    assert body["staged_files"] == []
    assert body["untracked_files"] == []


def test_sprint_returns_404_before_publication(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client, _ = make_client(tmp_path, monkeypatch)

    response = client.get("/api/v1/agent/sprint")

    assert response.status_code == 404
    assert response.json()["detail"] == ("No sprint status has been published")


def test_sprint_returns_published_status(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client, container = make_client(tmp_path, monkeypatch)
    container.workflow_state.publish_sprint(
        SprintStatus(
            checkpoint_id="A7",
            title="Mission Control Integration",
            goal="Expose Atlas Agent workflows through Mission Control.",
            phase=SprintPhase.IN_PROGRESS,
        )
    )

    response = client.get("/api/v1/agent/sprint")

    assert response.status_code == 200
    assert response.json() == {
        "checkpoint_id": "A7",
        "title": "Mission Control Integration",
        "goal": "Expose Atlas Agent workflows through Mission Control.",
        "phase": "in_progress",
    }


def test_verification_returns_404_before_publication(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client, _ = make_client(tmp_path, monkeypatch)

    response = client.get("/api/v1/agent/verification")

    assert response.status_code == 404


def test_verification_returns_published_report(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client, container = make_client(tmp_path, monkeypatch)
    repository = container.settings.repository_root

    container.workflow_state.publish_verification(
        VerificationReport(
            repository_root=repository,
            results=(
                VerificationCheckResult(
                    identifier="pytest",
                    argv=("python", "-m", "pytest"),
                    working_directory=repository,
                    status=VerificationStatus.PASSED,
                    return_code=0,
                    stdout="132 passed",
                    stderr="",
                    duration_seconds=0.43,
                ),
            ),
            status=VerificationStatus.PASSED,
            duration_seconds=0.43,
        )
    )

    response = client.get("/api/v1/agent/verification")

    assert response.status_code == 200
    body = response.json()
    assert body["repository_root"] == str(repository)
    assert body["status"] == "passed"
    assert body["results"][0]["identifier"] == "pytest"
    assert body["results"][0]["argv"] == [
        "python",
        "-m",
        "pytest",
    ]


def test_review_returns_404_before_publication(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client, _ = make_client(tmp_path, monkeypatch)

    response = client.get("/api/v1/agent/review")

    assert response.status_code == 404


def test_review_returns_published_report(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client, container = make_client(tmp_path, monkeypatch)

    container.workflow_state.publish_review(
        ReviewReport(
            request_id="review-a7",
            checkpoint_id="A7",
            status=ReviewStatus.CHANGES_REQUIRED,
            findings=(
                ReviewFinding(
                    code="out-of-scope-file",
                    category=ReviewCategory.SCOPE,
                    severity=ReviewSeverity.ERROR,
                    summary="Changed file is outside the approved plan",
                    evidence="services/example.py",
                    recommendation="Remove the out-of-scope change",
                ),
            ),
            recommendations=("Remove the out-of-scope change",),
        )
    )

    response = client.get("/api/v1/agent/review")

    assert response.status_code == 200
    assert response.json() == {
        "request_id": "review-a7",
        "checkpoint_id": "A7",
        "status": "changes_required",
        "findings": [
            {
                "code": "out-of-scope-file",
                "category": "scope",
                "severity": "error",
                "summary": ("Changed file is outside the approved plan"),
                "evidence": "services/example.py",
                "recommendation": "Remove the out-of-scope change",
            }
        ],
        "recommendations": ["Remove the out-of-scope change"],
    }


def test_agent_info_returns_runtime_information(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client, container = make_client(tmp_path, monkeypatch)

    response = client.get("/api/v1/agent/info")

    assert response.status_code == 200
    assert response.json() == {
        "app_name": "Atlas Agent",
        "version": AGENT_VERSION,
        "environment": "development",
        "repository_root": str(container.settings.repository_root),
        "supported_workflow_phases": [
            "planned",
            "awaiting_approval",
            "in_progress",
            "awaiting_verification_approval",
            "verifying",
            "awaiting_commit_approval",
            "committing",
            "reviewing",
            "completed",
            "blocked",
        ],
        "supported_verification_statuses": [
            "passed",
            "failed",
            "timed_out",
            "launch_failed",
        ],
        "install_container": {
            "contract_schema": "agent-install-container-validation-v1",
            "operation": "install-container",
            "mode": "validate-only",
            "capability_status": "unsupported",
            "default_enabled": False,
            "execution_supported": False,
            "dispatch_allowed": False,
            "mutation_allowed": False,
            "replay_allowed": False,
            "runtime": "rootless-podman; fixed limits; no runtime invocation",
            "filesystem": "read-only root; bounded /tmp tmpfs; no host mounts",
            "network": "none; no ingress, egress, DNS, ports, or image pull",
            "home_assistant_status": "blocked",
            "validation_result_available": False,
        },
    }
