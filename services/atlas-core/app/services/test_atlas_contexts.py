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
        docker=DockerSettings(),
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
) -> LegacyAtlasContextResolver:
    return LegacyAtlasContextResolver(
        settings=config or settings(),
        inventory=inv or inventory(),
        environ=environ() if env is None else env,
        data_root=data_root,
        runtime_connection_overrides=runtime_connection_overrides,
        runtime_secret_overrides=runtime_secret_overrides,
    )


def test_proxmox_context_resolves_inventory_display_settings_connection_and_env_secrets() -> None:
    context = resolver().resolve_context("proxmox")

    assert context.metadata.name == "Proxmox Lab"
    assert context.metadata.description == "Virtualization provider."
    assert context.metadata.source == "inventory"
    assert context.connection is not None
    assert context.connection.source == "settings"
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
    assert context.connection.source == "settings"
    assert context.connection.base_url == "http://10.10.40.140:8123"
    assert context.connection.host == "10.10.40.140"
    assert context.connection.port == 8123
    assert context.secrets["token"].source == "environment"
    assert context.secrets["token"].configured is True


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


def test_connection_precedence_prefers_runtime_then_settings_then_inventory() -> None:
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
    settings_context = resolver().resolve_context("proxmox")
    inventory_context = resolver().resolve_context("hermes")

    assert runtime_context.connection is not None
    assert runtime_context.connection.source == "runtime"
    assert runtime_context.connection.host == "runtime-proxmox.invalid"
    assert settings_context.connection is not None
    assert settings_context.connection.source == "settings"
    assert settings_context.connection.host == "10.10.50.10"
    assert inventory_context.connection is not None
    assert inventory_context.connection.source == "inventory"


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

    assert [context.consumer_id for context in contexts] == ["hermes", "proxmox"]


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
    assert "settings" in sources
    assert "environment" in sources
    assert "computed" in sources
