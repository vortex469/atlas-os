from __future__ import annotations

from pathlib import Path

import pytest

from app.clients import docker_client
from app.context import AtlasContext, ConnectionContext, MetadataContext, RuntimeContext


def docker_context(path: str = "/var/run/docker.sock") -> AtlasContext:
    return AtlasContext(
        metadata=MetadataContext(
            consumer_id="docker",
            consumer_type="provider",
            name="Docker",
        ),
        connection=ConnectionContext(
            mode="unix",
            path=path,
            source="settings",
            timeout_seconds=10.0,
            metadata={
                "privileged_local_runtime": True,
                "editable": False,
                "permission_model": "supplemental_group",
            },
        ),
        runtime=RuntimeContext(),
        generation=f"docker-{path}",
    )


def test_docker_client_uses_resolved_socket_not_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeDockerClient:
        def __init__(self, *, base_url: str) -> None:
            captured["base_url"] = base_url

    def fail_from_env() -> None:
        raise AssertionError("docker.from_env must not be used")

    monkeypatch.setattr(docker_client.docker, "DockerClient", FakeDockerClient)
    monkeypatch.setattr(docker_client.docker, "from_env", fail_from_env)

    docker_client.create_docker_client(docker_context("/run/docker.sock"))

    assert captured == {"base_url": "unix:///run/docker.sock"}


def test_changing_context_changes_docker_client_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_urls: list[str] = []

    class FakeDockerClient:
        def __init__(self, *, base_url: str) -> None:
            base_urls.append(base_url)

    monkeypatch.setattr(docker_client.docker, "DockerClient", FakeDockerClient)

    docker_client.create_docker_client(docker_context("/first.sock"))
    docker_client.create_docker_client(docker_context("/second.sock"))

    assert base_urls == ["unix:///first.sock", "unix:///second.sock"]


def test_invalid_context_blocks_client_construction() -> None:
    context = AtlasContext(
        metadata=MetadataContext(
            consumer_id="docker",
            consumer_type="provider",
            name="Docker",
        ),
        runtime=RuntimeContext(),
        generation="docker-invalid",
    )

    with pytest.raises(RuntimeError, match="Docker Unix socket is not configured"):
        docker_client.create_docker_client(context)


def test_docker_connection_diagnostics_are_sanitized_and_read_only_metadata(
    tmp_path: Path,
) -> None:
    socket_path = tmp_path / "missing.sock"

    diagnostics = docker_client.docker_connection_diagnostics(
        docker_context(str(socket_path)),
    )

    assert diagnostics["socket_configured"] is True
    assert diagnostics["socket_path"] == str(socket_path)
    assert diagnostics["socket_exists"] is False
    assert diagnostics["permission_available"] is False
    assert diagnostics["privileged_local_runtime"] is True
    assert diagnostics["editable"] is False
    assert diagnostics["permission_model"] == "supplemental_group"
    assert "read-only" in diagnostics["warning"]
