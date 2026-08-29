"""P3 locks for explicit, disabled dormant delivery configuration."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from app.dormant_agent_intake_delivery_wiring import (
    CoreAgentIntakeDeliveryCreateV1,
    DormantAgentIntakeDeliveryClient,
    DormantAgentIntakeDeliveryPreparationStore,
    StrictContractError,
    create_dormant_agent_intake_delivery_client,
    parse_delivery_configuration_json,
)
from app.dormant_agent_intake_delivery_wiring.test_contract import configuration

APP_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = Path(__file__).resolve().parent


class UnusedEvidenceReader:
    def resolve(
        self, *, operator_id: str, create: CoreAgentIntakeDeliveryCreateV1
    ) -> None:
        raise AssertionError("construction must not resolve evidence")


def _configuration_json() -> str:
    return configuration().model_dump_json()


def test_injected_configuration_is_closed_disabled_and_reference_only() -> None:
    parsed = parse_delivery_configuration_json(_configuration_json())

    assert parsed == configuration()
    assert parsed.enabled is False
    assert parsed.mode == "prepare-and-validate-only"
    assert parsed.agent_route_registered is False
    assert parsed.production_transport_registered is False
    assert parsed.production_delivery_allowed is False
    assert parsed.execution_authorized is False
    assert parsed.worker_allowed is False
    assert parsed.mutation_allowed is False
    assert parsed.replay_allowed is False
    assert parsed.authentication.credential_source == "mode-0400-file"
    assert parsed.authentication.maximum_credential_bytes == 4096


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("enabled", True),
        ("agent_route_registered", True),
        ("production_transport_registered", True),
        ("production_delivery_allowed", True),
        ("execution_authorized", True),
        ("worker_allowed", True),
        ("mutation_allowed", True),
        ("replay_allowed", True),
    ],
)
def test_configuration_authority_flags_are_fixed_false(
    field: str, value: bool
) -> None:
    raw = configuration().model_dump(mode="json")
    raw[field] = value

    with pytest.raises(StrictContractError, match="^malformed$"):
        parse_delivery_configuration_json(json.dumps(raw))


def test_configuration_rejects_unknown_duplicate_and_oversized_values() -> None:
    raw = configuration().model_dump(mode="json")
    raw["unknown"] = "forbidden"
    with pytest.raises(StrictContractError, match="^malformed$"):
        parse_delivery_configuration_json(json.dumps(raw))

    duplicate = _configuration_json().replace(
        '"enabled":false', '"enabled":false,"enabled":false', 1
    )
    with pytest.raises(StrictContractError, match="^malformed$"):
        parse_delivery_configuration_json(duplicate)

    with pytest.raises(StrictContractError, match="^malformed$"):
        parse_delivery_configuration_json(b"{" + b" " * (16 * 1024))


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("endpoint", "scheme", "http"),
        ("endpoint", "host", "127.0.0.1"),
        ("endpoint", "tls_server_name", "other.internal"),
        ("endpoint", "ca_bundle_file", "relative/ca.pem"),
        ("authentication", "scheme", "Basic"),
        ("authentication", "credential_file", "~/secret"),
        ("authentication", "maximum_credential_bytes", 8192),
    ],
)
def test_configuration_rejects_invalid_endpoint_and_authentication_references(
    section: str, field: str, value: object
) -> None:
    raw = configuration().model_dump(mode="json")
    raw[section][field] = value

    with pytest.raises(StrictContractError, match="^malformed$"):
        parse_delivery_configuration_json(json.dumps(raw))


def test_explicit_factory_is_inert_and_does_not_read_referenced_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parsed = parse_delivery_configuration_json(_configuration_json())
    store = DormantAgentIntakeDeliveryPreparationStore(tmp_path / "evidence.sqlite3")

    def forbidden_open(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("configuration construction must not read files")

    monkeypatch.setattr("builtins.open", forbidden_open)
    client = create_dormant_agent_intake_delivery_client(
        configuration=parsed,
        evidence_reader=UnusedEvidenceReader(),  # type: ignore[arg-type]
        preparation_store=store,
        clock=lambda: None,  # type: ignore[arg-type,return-value]
        id_factory=lambda: "unused",
    )

    assert isinstance(client, DormantAgentIntakeDeliveryClient)
    assert client.configuration == parsed
    assert {name for name in dir(client) if not name.startswith("_")} == {
        "configuration",
        "get_preparation",
        "prepare",
        "validate_response",
    }


def test_isolated_package_has_no_transport_secret_or_runtime_capability() -> None:
    forbidden_import_roots = {
        "aiohttp",
        "docker",
        "httpx",
        "podman",
        "requests",
        "socket",
        "ssl",
        "subprocess",
        "urllib",
    }
    forbidden_calls = {"open", "getaddrinfo", "create_connection", "Popen", "run"}

    for path in PACKAGE_ROOT.glob("*.py"):
        if path.name.startswith("test_"):
            continue
        tree = ast.parse(path.read_text())
        imports = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in (node.names if isinstance(node, ast.Import) else [ast.alias(name=node.module or "")])
        }
        calls = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert imports.isdisjoint(forbidden_import_roots), path
        assert calls.isdisjoint(forbidden_calls), path


def test_production_paths_do_not_construct_or_consume_dormant_wiring() -> None:
    excluded = {PACKAGE_ROOT}
    markers = {
        "dormant_agent_intake_delivery_wiring",
        "DormantAgentIntakeDeliveryClient",
        "create_dormant_agent_intake_delivery_client",
        "dormant-agent-intake-delivery-configuration-v1",
    }
    production_files = [
        path
        for path in APP_ROOT.rglob("*.py")
        if not path.name.startswith("test_")
        and not any(root in path.parents or root == path for root in excluded)
    ]

    for path in production_files:
        source = path.read_text()
        assert markers.isdisjoint(marker for marker in markers if marker in source), path


def test_production_settings_and_app_expose_no_delivery_fields_or_route() -> None:
    paths = [
        APP_ROOT / "main.py",
        APP_ROOT / "config" / "settings.py",
        *sorted((APP_ROOT / "container").glob("*.py")),
        *sorted((APP_ROOT / "api").rglob("*.py")),
    ]
    forbidden = {
        "agent_intake_endpoint",
        "agent_intake_credential",
        "production_delivery_allowed",
        "installation-intake",
    }
    for path in paths:
        if path.name.startswith("test_"):
            continue
        source = path.read_text()
        assert forbidden.isdisjoint(marker for marker in forbidden if marker in source), path
