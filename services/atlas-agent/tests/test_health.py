"""Tests for the Atlas Agent health endpoint."""

import logging
import subprocess
from dataclasses import replace
from unittest.mock import AsyncMock, Mock

from app.config.settings import Settings
from app.main import create_app
from app.repository.exceptions import InvalidRepositoryError, RepositoryInspectionError
from app.version import AGENT_VERSION
from fastapi.testclient import TestClient


def run_git(repository, *arguments: str) -> None:
    """Run one Git command in a test repository."""

    subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )


def create_test_application(tmp_path, monkeypatch):
    """Create an Atlas Agent application bound to a temporary Git repository."""

    repository = tmp_path / "repository"
    repository.mkdir()
    run_git(repository, "init")
    settings = Settings(repository_root=repository.resolve())
    monkeypatch.setattr("app.main.load_settings", lambda: settings)
    return create_app()


def test_health() -> None:
    """The health endpoint reports that Atlas Agent is healthy."""

    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "atlas-agent",
    }


def test_lifespan_startup_exposes_application_container(
    tmp_path,
    monkeypatch,
) -> None:
    """Application startup preserves the shared dependency container."""

    application = create_test_application(tmp_path, monkeypatch)

    with TestClient(application) as client:
        assert client.app.state.container is application.state.container


def test_lifespan_shutdown_closes_core_client_once(
    tmp_path,
    monkeypatch,
) -> None:
    """Application shutdown closes the owned Atlas Core client exactly once."""

    application = create_test_application(tmp_path, monkeypatch)
    core_client = Mock()
    core_client.close = AsyncMock()
    application.state.container = replace(
        application.state.container,
        core_client=core_client,
    )

    with TestClient(application):
        pass

    core_client.close.assert_awaited_once_with()


def test_lifespan_shutdown_handles_uninitialized_core_client(
    tmp_path,
    monkeypatch,
) -> None:
    """Shutdown succeeds when the Atlas Core HTTP client was never initialized."""

    application = create_test_application(tmp_path, monkeypatch)
    core_client = application.state.container.core_client

    assert core_client._client is None

    with TestClient(application):
        pass

    assert core_client._client is None


def test_lifespan_shutdown_closes_initialized_core_client(
    tmp_path,
    monkeypatch,
) -> None:
    """Shutdown closes an owned Atlas Core HTTP client created during runtime."""

    application = create_test_application(tmp_path, monkeypatch)
    core_client = application.state.container.core_client
    http_client = core_client._get_client()

    assert not http_client.is_closed

    with TestClient(application):
        pass

    assert http_client.is_closed
    assert core_client._client is None


def test_app_lifecycle_recreation_does_not_reuse_closed_core_pool(
    tmp_path,
    monkeypatch,
) -> None:
    """A recreated application can start after the prior loop has closed."""
    first_root = tmp_path / "first"
    first_root.mkdir()
    first_application = create_test_application(first_root, monkeypatch)
    first_core_client = first_application.state.container.core_client
    first_core_client._get_client()

    with TestClient(first_application):
        pass

    second_root = tmp_path / "second"
    second_root.mkdir()
    second_application = create_test_application(second_root, monkeypatch)
    with TestClient(second_application):
        pass

    assert first_core_client._client is None


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


def test_diagnostics_returns_controlled_error_for_invalid_repository(
    tmp_path,
    monkeypatch,
) -> None:
    """Diagnostics expose stable errors when repository validation fails."""

    repository = tmp_path / "repository"
    repository.mkdir()
    run_git(repository, "init")
    settings = Settings(repository_root=repository.resolve())
    monkeypatch.setattr("app.main.load_settings", lambda: settings)
    application = create_app()
    inspector = Mock()
    inspector.inspect.side_effect = InvalidRepositoryError("invalid repository")
    application.state.container = replace(
        application.state.container,
        repository_inspector=inspector,
    )

    response = TestClient(application).get("/diagnostics")

    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "code": "repository_diagnostics_unavailable",
            "message": "Repository diagnostics are unavailable",
        }
    }


def test_diagnostics_returns_controlled_error_for_repository_inspection_failure(
    tmp_path,
    monkeypatch,
) -> None:
    """Diagnostics expose stable errors when Git inspection fails."""

    repository = tmp_path / "repository"
    repository.mkdir()
    run_git(repository, "init")
    settings = Settings(repository_root=repository.resolve())
    monkeypatch.setattr("app.main.load_settings", lambda: settings)
    application = create_app()
    inspector = Mock()
    inspector.inspect.side_effect = RepositoryInspectionError("git failed")
    application.state.container = replace(
        application.state.container,
        repository_inspector=inspector,
    )

    response = TestClient(application).get("/diagnostics")

    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "code": "repository_diagnostics_unavailable",
            "message": "Repository diagnostics are unavailable",
        }
    }


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
