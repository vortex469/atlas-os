"""Tests for the Atlas Agent health endpoint."""

from fastapi.testclient import TestClient

from app.main import create_app
from app.version import AGENT_VERSION


def test_health() -> None:
    """The health endpoint reports that Atlas Agent is healthy."""

    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "atlas-agent",
    }


def test_create_app_logs_startup_diagnostics(
    tmp_path,
    monkeypatch,
    caplog,
) -> None:
    """Application creation logs non-secret runtime diagnostics."""

    import logging
    import subprocess

    from app.config.settings import Settings

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

    import subprocess

    from app.config.settings import Settings

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
