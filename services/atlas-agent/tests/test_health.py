"""Tests for the Atlas Agent health endpoint."""

import logging
import subprocess

from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.main import create_app
from app.version import AGENT_VERSION


def run_git(repository, *arguments: str) -> None:
    """Run one Git command in a test repository."""

    subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )


def test_health() -> None:
    """The health endpoint reports that Atlas Agent is healthy."""

    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "atlas-agent",
    }


def test_diagnostics_reports_runtime_capabilities(
    tmp_path,
    monkeypatch,
) -> None:
    """Diagnostics report the live branch and available engines."""

    repository = tmp_path / "repository"
    repository.mkdir()
    run_git(repository, "init", "-b", "diagnostics-test")

    settings = Settings(repository_root=repository.resolve())
    monkeypatch.setattr("app.main.load_settings", lambda: settings)

    response = TestClient(create_app()).get("/diagnostics")

    assert response.status_code == 200
    assert response.json() == {
        "version": AGENT_VERSION,
        "git_branch": "diagnostics-test",
        "approval_engine_available": True,
        "workflow_engine_available": True,
    }


def test_diagnostics_reports_null_for_detached_head(
    tmp_path,
    monkeypatch,
) -> None:
    """Diagnostics represent a detached HEAD with a null branch."""

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
    run_git(repository, "checkout", "--detach")

    settings = Settings(repository_root=repository.resolve())
    monkeypatch.setattr("app.main.load_settings", lambda: settings)

    response = TestClient(create_app()).get("/diagnostics")

    assert response.status_code == 200
    assert response.json()["git_branch"] is None


def test_create_app_logs_startup_diagnostics(
    tmp_path,
    monkeypatch,
    caplog,
) -> None:
    """Application creation logs non-secret runtime diagnostics."""

    repository = tmp_path / "repository"
    repository.mkdir()

    subprocess.run(
        ["git", "init"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )

    settings = Settings(
        app_name="Atlas Agent Test",
        environment="testing",
        log_level="INFO",
        host="127.0.0.1",
        port=8091,
        repository_root=repository.resolve(),
    )
    monkeypatch.setattr("app.main.load_settings", lambda: settings)

    with caplog.at_level(logging.INFO, logger="atlas-agent"):
        create_app()

    assert (
        "Starting Atlas Agent Test "
        f"version={AGENT_VERSION} "
        "environment=testing "
        "host=127.0.0.1 "
        "port=8091 "
        f"repository_root={repository.resolve()}"
    ) in caplog.messages


def test_create_app_uses_centralized_version_metadata(
    tmp_path,
    monkeypatch,
) -> None:
    """FastAPI metadata uses the centralized Atlas Agent version."""

    repository = tmp_path / "repository"
    repository.mkdir()

    subprocess.run(
        ["git", "init"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )

    settings = Settings(
        repository_root=repository.resolve(),
    )
    monkeypatch.setattr("app.main.load_settings", lambda: settings)

    application = create_app()

    assert application.version == AGENT_VERSION
