from __future__ import annotations

from pathlib import Path

import pytest

from app.config.settings import (
    AtlasSettings,
    DockerSettings,
    HomeAssistantSettings,
    InfrastructureSettings,
    InventorySettings,
    ProxmoxSettings,
    Settings,
)
from app.providers.registry import ProviderRegistry
from app.services.atlas_contexts import (
    AtlasContextResolutionError,
    LegacyAtlasContextResolver,
)


def settings(
    *,
    proxmox_host: str = "10.10.50.10",
    proxmox_port: int = 8006,
    proxmox_node: str = "vorex469",
    proxmox_verify_ssl: bool = False,
    home_assistant_url: str = "http://10.10.40.140:8123",
    docker_socket: str = "unix:///var/run/docker.sock",
) -> Settings:
    return Settings(
        atlas=AtlasSettings(release="Foundry"),
        infrastructure=InfrastructureSettings(),
        proxmox=ProxmoxSettings(
            host=proxmox_host,
            port=proxmox_port,
            node=proxmox_node,
            verify_ssl=proxmox_verify_ssl,
        ),
        home_assistant=HomeAssistantSettings(url=home_assistant_url),
        docker=DockerSettings(socket=docker_socket),
        inventory=InventorySettings(file="/opt/atlas/inventory/services.yaml"),
    )


def inventory() -> dict:
    return {
        "services": {
            "proxmox": {
                "name": "Proxmox Lab",
                "description": "Virtualization provider.",
                "host": "inventory-proxmox.invalid",
                "port": 443,
                "protocol": "https",
                "health_endpoint": "/api2/json/version",
                "expected_status": [200],
                "critical": True,
                "role": "virtualization",
            },
            "home_assistant": {
                "name": "Home Assistant",
                "host": "inventory-ha.invalid",
                "port": 8123,
                "protocol": "http",
                "health_endpoint": "/",
                "expected_status": [200],
                "critical": False,
                "role": "home-automation",
            },
            "hermes": {
                "name": "Hermes",
                "host": "10.10.50.60",
                "port": 8642,
                "protocol": "http",
                "health_endpoint": "/health",
                "expected_status": [200],
                "critical": True,
                "role": "reasoning-engine",
            },
        },
    }


def environ() -> dict[str, str]:
    return {
        "PROXMOX_USER": "root@pam",
        "PROXMOX_TOKEN_NAME": "atlas",
        "PROXMOX_TOKEN_VALUE": "proxmox-secret-token",
        "HASS_TOKEN": "home-assistant-secret-token",
    }


def resolver(
    *,
    runtime_connection_overrides: dict | None = None,
    runtime_secret_overrides: dict | None = None,
    data_root: Path = Path("/atlas-data"),
    env: dict[str, str] | None = None,
    config: Settings | None = None,
    inv: dict | None = None,
    runtime_connection_file: Path | None = None,
    runtime_secret_file: Path | None = None,
) -> LegacyAtlasContextResolver:
    return LegacyAtlasContextResolver(
        settings=config or settings(),
        inventory=inv or inventory(),
        environ=environ() if env is None else env,
        data_root=data_root,
        runtime_connection_overrides=runtime_connection_overrides,
        runtime_secret_overrides=runtime_secret_overrides,
        runtime_connection_file=runtime_connection_file,
        runtime_secret_file=runtime_secret_file,
    )


def write_yaml(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_proxmox_context_resolves_inventory_display_settings_connection_and_env_secrets() -> None:
    context = resolver().resolve_context("proxmox")

    assert context.metadata.name == "Proxmox Lab"
    assert context.metadata.description == "Virtualization provider."
    assert context.metadata.source == "inventory"
    assert context.connection is not None
    assert context.connection.source == "atlas_yaml"
    assert context.connection.host == "10.10.50.10"
    assert context.connection.port == 8006
    assert context.connection.node == "vorex469"
    assert context.connection.verify_tls is False
    assert context.secrets["user"].source == "environment"
    assert context.secrets["user"].configured is True
    assert context.secrets["token_value"].reveal() == "proxmox-secret-token"


def test_home_assistant_context_resolves_url_from_settings_and_token_from_environment() -> None:
    context = resolver().resolve_context("home_assistant")

    assert context.connection is not None
    assert context.connection.source == "atlas_yaml"
    assert context.connection.base_url == "http://10.10.40.140:8123"
    assert context.connection.host == "10.10.40.140"
    assert context.connection.port == 8123
    assert context.secrets["token"].source == "environment"
    assert context.secrets["token"].configured is True


def test_docker_context_resolves_fixed_unix_socket_from_settings() -> None:
    context = resolver(
        config=settings(docker_socket="unix:///run/custom-docker.sock"),
    ).resolve_context("docker")

    assert context.metadata.name == "Docker"
    assert context.connection is not None
    assert context.connection.mode == "unix"
    assert context.connection.source == "atlas_yaml"
    assert context.connection.path == "/run/custom-docker.sock"
    assert context.connection.metadata["socket_uri"] == "unix:///run/custom-docker.sock"
    assert context.connection.metadata["privileged_local_runtime"] is True
    assert context.connection.metadata["editable"] is False
    assert context.connection.metadata["permission_model"] == "supplemental_group"
    assert context.secrets == {}


def test_generic_inventory_provider_resolves_connection_from_inventory() -> None:
    context = resolver().resolve_context("hermes")

    assert context.metadata.name == "Hermes"
    assert context.connection is not None
    assert context.connection.source == "inventory"
    assert context.connection.mode == "http"
    assert context.connection.host == "10.10.50.60"
    assert context.connection.port == 8642
    assert context.connection.health_endpoint == "/health"
    assert context.connection.expected_status == 200


def test_missing_secret_produces_missing_marker_and_diagnostic() -> None:
    context = resolver(env={}).resolve_context("proxmox")

    assert context.secrets["token_value"].configured is False
    assert context.secrets["token_value"].source == "missing"
    assert any(
        item.code == "secret-missing" and item.field == "secrets.token_value"
        for item in context.diagnostics.items
    )


def test_secret_values_never_appear_in_repr_dump_or_diagnostics() -> None:
    context = resolver().resolve_context("proxmox")

    dumped = context.model_dump(mode="json")
    dumped_json = context.model_dump_json()
    diagnostics_json = context.diagnostics.model_dump_json()

    assert "proxmox-secret-token" not in repr(context)
    assert "proxmox-secret-token" not in dumped_json
    assert "proxmox-secret-token" not in diagnostics_json
    assert "value" not in dumped["secrets"]["token_value"]


def test_connection_precedence_prefers_runtime_then_atlas_yaml_then_inventory() -> None:
    runtime_context = resolver(
        runtime_connection_overrides={
            "proxmox": {
                "protocol": "https",
                "host": "runtime-proxmox.invalid",
                "port": 9443,
                "node": "runtime-node",
                "verify_tls": True,
            },
        },
    ).resolve_context("proxmox")
    atlas_yaml_context = resolver().resolve_context("proxmox")
    inventory_context = resolver().resolve_context("hermes")

    assert runtime_context.connection is not None
    assert runtime_context.connection.source == "runtime"
    assert runtime_context.connection.host == "runtime-proxmox.invalid"
    assert atlas_yaml_context.connection is not None
    assert atlas_yaml_context.connection.source == "atlas_yaml"
    assert atlas_yaml_context.connection.host == "10.10.50.10"
    assert inventory_context.connection is not None
    assert inventory_context.connection.source == "inventory"


def test_runtime_connection_store_merges_fields_with_legacy_fallbacks(tmp_path: Path) -> None:
    runtime_connection_file = tmp_path / "provider-connections.yaml"
    write_yaml(
        runtime_connection_file,
        """
version: 1
providers:
  proxmox:
    connection:
      host: runtime-proxmox.invalid
      verify_tls: false
""".lstrip(),
    )

    context = resolver(
        config=settings(proxmox_verify_ssl=True),
        runtime_connection_file=runtime_connection_file,
    ).resolve_context("proxmox")

    assert context.connection is not None
    assert context.connection.source == "runtime"
    assert context.connection.host == "runtime-proxmox.invalid"
    assert context.connection.port == 8006
    assert context.connection.node == "vorex469"
    assert context.connection.verify_tls is False
    assert context.connection.metadata["field_sources"]["host"] == "runtime"
    assert context.connection.metadata["field_sources"]["port"] == "atlas_yaml"
    assert context.connection.metadata["field_sources"]["verify_tls"] == "runtime"


def test_empty_runtime_connection_store_preserves_existing_behavior(tmp_path: Path) -> None:
    runtime_connection_file = tmp_path / "provider-connections.yaml"
    write_yaml(runtime_connection_file, "version: 1\nproviders: {}\n")

    context = resolver(runtime_connection_file=runtime_connection_file).resolve_context("proxmox")

    assert context.connection is not None
    assert context.connection.source == "atlas_yaml"
    assert context.connection.host == "10.10.50.10"


def test_runtime_connection_store_resolves_providers_independently(tmp_path: Path) -> None:
    runtime_connection_file = tmp_path / "provider-connections.yaml"
    write_yaml(
        runtime_connection_file,
        """
version: 1
providers:
  proxmox:
    connection:
      host: runtime-proxmox.invalid
  hermes:
    connection:
      port: 9999
""".lstrip(),
    )

    proxmox_context = resolver(runtime_connection_file=runtime_connection_file).resolve_context("proxmox")
    hermes_context = resolver(runtime_connection_file=runtime_connection_file).resolve_context("hermes")

    assert proxmox_context.connection is not None
    assert proxmox_context.connection.host == "runtime-proxmox.invalid"
    assert proxmox_context.connection.port == 8006
    assert hermes_context.connection is not None
    assert hermes_context.connection.host == "10.10.50.60"
    assert hermes_context.connection.port == 9999


def test_secret_precedence_prefers_runtime_then_environment_then_missing() -> None:
    context = resolver(
        runtime_secret_overrides={
            "proxmox": {
                "token_value": "runtime-secret-token",
            },
        },
    ).resolve_context("proxmox")
    missing = resolver(env={}).resolve_context("proxmox")

    assert context.secrets["token_value"].source == "runtime"
    assert context.secrets["token_value"].reveal() == "runtime-secret-token"
    assert context.secrets["token_name"].source == "environment"
    assert missing.secrets["token_value"].source == "missing"


def test_secret_precedence_prefers_runtime_store_then_environment_then_missing(tmp_path: Path) -> None:
    runtime_secret_file = tmp_path / "provider-connections.yaml"
    write_yaml(
        runtime_secret_file,
        """
version: 1
providers:
  proxmox:
    secrets:
      token_value: runtime-secret-token
""".lstrip(),
    )

    context = resolver(runtime_secret_file=runtime_secret_file).resolve_context("proxmox")
    missing = resolver(env={}, runtime_secret_file=runtime_secret_file).resolve_context("proxmox")

    assert context.secrets["token_value"].source == "runtime"
    assert context.secrets["token_value"].reveal() == "runtime-secret-token"
    assert context.secrets["token_name"].source == "environment"
    assert missing.secrets["token_value"].source == "runtime"
    assert missing.secrets["user"].source == "missing"


def test_runtime_secret_can_override_one_field_while_environment_supplies_others(tmp_path: Path) -> None:
    runtime_secret_file = tmp_path / "provider-connections.yaml"
    write_yaml(
        runtime_secret_file,
        """
version: 1
providers:
  proxmox:
    secrets:
      token_value: runtime-secret-token
""".lstrip(),
    )

    context = resolver(runtime_secret_file=runtime_secret_file).resolve_context("proxmox")

    assert context.secrets["token_value"].source == "runtime"
    assert context.secrets["token_name"].source == "environment"
    assert context.secrets["user"].source == "environment"


def test_secret_values_from_runtime_store_are_redacted(tmp_path: Path) -> None:
    runtime_secret_file = tmp_path / "provider-connections.yaml"
    write_yaml(
        runtime_secret_file,
        """
version: 1
providers:
  proxmox:
    secrets:
      token_value: runtime-secret-token
""".lstrip(),
    )

    context = resolver(runtime_secret_file=runtime_secret_file).resolve_context("proxmox")

    assert "runtime-secret-token" not in repr(context)
    assert "runtime-secret-token" not in context.model_dump_json()
    assert "runtime-secret-token" not in context.diagnostics.model_dump_json()


def test_identical_inputs_produce_stable_generation() -> None:
    first = resolver().resolve_context("proxmox")
    second = resolver().resolve_context("proxmox")

    assert first.generation == second.generation


def test_changed_connection_input_changes_generation() -> None:
    first = resolver().resolve_context("proxmox")
    second = resolver(
        config=settings(proxmox_host="10.10.50.11"),
    ).resolve_context("proxmox")

    assert first.generation != second.generation


def test_effective_secret_change_changes_generation(tmp_path: Path) -> None:
    first_secret_file = tmp_path / "first.yaml"
    second_secret_file = tmp_path / "second.yaml"
    write_yaml(first_secret_file, "version: 1\nproviders:\n  proxmox:\n    secrets:\n      token_value: runtime-alpha-value\n")
    write_yaml(second_secret_file, "version: 1\nproviders:\n  proxmox:\n    secrets:\n      token_value: runtime-beta-value\n")

    first = resolver(runtime_secret_file=first_secret_file).resolve_context("proxmox")
    second = resolver(runtime_secret_file=second_secret_file).resolve_context("proxmox")

    assert first.generation != second.generation
    assert "runtime-alpha-value" not in first.model_dump_json()
    assert "runtime-beta-value" not in second.model_dump_json()


def test_shadowed_legacy_connection_change_does_not_change_generation() -> None:
    first = resolver(
        runtime_connection_overrides={"proxmox": {"host": "runtime.invalid"}},
        config=settings(proxmox_host="legacy-one.invalid"),
    ).resolve_context("proxmox")
    second = resolver(
        runtime_connection_overrides={"proxmox": {"host": "runtime.invalid"}},
        config=settings(proxmox_host="legacy-two.invalid"),
    ).resolve_context("proxmox")

    assert first.generation == second.generation


def test_invalid_runtime_connection_store_blocks_resolution_safely(tmp_path: Path) -> None:
    runtime_connection_file = tmp_path / "provider-connections.yaml"
    write_yaml(runtime_connection_file, "version: 2\nproviders: {}\n")
    registry = ProviderRegistry()
    before_ids = registry.ids()

    with pytest.raises(RuntimeError, match="runtime provider connection store is invalid") as error_info:
        resolver(runtime_connection_file=runtime_connection_file).resolve_context("proxmox")

    assert str(runtime_connection_file) not in str(error_info.value)
    assert registry.ids() == before_ids


def test_invalid_runtime_secret_store_blocks_resolution_safely(tmp_path: Path) -> None:
    runtime_secret_file = tmp_path / "provider-connections.yaml"
    write_yaml(runtime_secret_file, "version: 2\nproviders:\n  proxmox:\n    secrets:\n      token_value: do-not-leak\n")
    registry = ProviderRegistry()
    before_ids = registry.ids()

    with pytest.raises(RuntimeError, match="runtime provider secret store is invalid") as error_info:
        resolver(runtime_secret_file=runtime_secret_file).resolve_context("proxmox")

    assert "do-not-leak" not in str(error_info.value)
    assert str(runtime_secret_file) not in str(error_info.value)
    assert registry.ids() == before_ids


def test_runtime_paths_are_provider_scoped_and_resolution_does_not_create_paths(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    context = resolver(data_root=data_root).resolve_context("proxmox")

    assert context.runtime.data_root == data_root
    assert context.runtime.config_root == data_root / "config"
    assert context.runtime.history_root == data_root / "history"
    assert context.runtime.consumer_data_root == data_root / "providers" / "proxmox"
    assert context.runtime.consumer_cache_root == data_root / "cache" / "providers" / "proxmox"
    assert not data_root.exists()

    with pytest.raises(Exception, match="frozen"):
        context.runtime.data_root = Path("/changed")  # type: ignore[misc]


def test_unknown_provider_returns_stable_resolution_error() -> None:
    with pytest.raises(AtlasContextResolutionError, match="not declared"):
        resolver().resolve_context("not-real")


def test_resolving_all_contexts_preserves_inventory_order_and_default_proxmox() -> None:
    contexts = resolver(inv={"services": {"hermes": inventory()["services"]["hermes"]}}).resolve_all_contexts()

    assert [context.consumer_id for context in contexts] == ["hermes", "proxmox", "docker"]


def test_resolving_contexts_does_not_mutate_provider_registry() -> None:
    registry = ProviderRegistry()
    before_ids = registry.ids()

    resolver().resolve_all_contexts()

    assert registry.ids() == before_ids
    assert len(registry) == 0


def test_validation_diagnostics_include_connection_secret_and_runtime_sources() -> None:
    context = resolver().resolve_context("proxmox")
    codes = {item.code for item in context.diagnostics.items}
    sources = {item.source for item in context.diagnostics.items}

    assert "connection-resolved" in codes
    assert "secret-configured" in codes
    assert "runtime-resolved" in codes
    assert "atlas_yaml" in sources
    assert "environment" in sources
    assert "computed" in sources
