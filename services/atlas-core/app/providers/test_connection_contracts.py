from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.models.connections import (
    ProviderConnectionField,
    ProviderConnectionFieldOption,
    ProviderConnectionSchema,
    UpdateProviderConnectionRequest,
    UpdateProviderConnectionResult,
)
from app.models.connections import (
    TestProviderConnectionRequest as ProviderConnectionTestRequest,
)
from app.models.connections import (
    TestProviderConnectionResult as ProviderConnectionTestResult,
)
from app.providers import Provider, ProviderHealth, ProviderMetadata, ProviderWorkspace
from app.providers.connections import ProviderConnectionAdapter


class MinimalProvider(Provider):
    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            id="minimal",
            name="Minimal",
            workspace=ProviderWorkspace.OPERATIONS,
        )

    async def get_health(self) -> ProviderHealth:
        return ProviderHealth(status="online", message="ok")


class ConnectionCapableProvider(MinimalProvider):
    def connection_schema(self) -> ProviderConnectionSchema:
        return provider_neutral_schema()

    async def test_connection(
        self,
        request: ProviderConnectionTestRequest,
    ) -> ProviderConnectionTestResult:
        return ProviderConnectionTestResult(
            provider_id="example",
            status="success",
            message="Connection succeeded.",
            tested_at=datetime.now(UTC),
        )

    async def update_connection(
        self,
        request: UpdateProviderConnectionRequest,
    ) -> UpdateProviderConnectionResult:
        return UpdateProviderConnectionResult(
            provider_id="example",
            connection_schema=self.connection_schema(),
            updated_at=datetime.now(UTC),
        )


def provider_neutral_schema() -> ProviderConnectionSchema:
    return ProviderConnectionSchema(
        provider_id="example",
        provider_name="Example Provider",
        fields=[
            ProviderConnectionField(
                key="host",
                label="Host",
                kind="host",
                required=True,
                current_value="example.local",
                source="atlas.yaml",
                help_text="Provider hostname or IP address.",
            ),
            ProviderConnectionField(
                key="port",
                label="Port",
                kind="port",
                required=True,
                current_value=443,
                validation={"minimum": 1, "maximum": 65535},
            ),
            ProviderConnectionField(
                key="mode",
                label="Mode",
                kind="select",
                current_value="https",
                options=[
                    ProviderConnectionFieldOption(value="http", label="HTTP"),
                    ProviderConnectionFieldOption(value="https", label="HTTPS"),
                ],
            ),
            ProviderConnectionField(
                key="api_token",
                label="API Token",
                kind="secret",
                required=True,
                current_value="super-secret-token",
                secret_state="configured",
                source="environment",
            ),
        ],
    )


def test_connection_schema_is_provider_neutral() -> None:
    schema = provider_neutral_schema()

    assert schema.provider_id == "example"
    assert schema.provider_name == "Example Provider"
    assert [field.key for field in schema.fields] == ["host", "port", "mode", "api_token"]
    assert schema.fields[0].kind == "host"
    assert schema.fields[1].validation == {"minimum": 1, "maximum": 65535}
    assert schema.fields[2].options[1].value == "https"


def test_provider_defined_fields_and_select_options_validate() -> None:
    field = ProviderConnectionField(
        key="protocol",
        label="Protocol",
        kind="select",
        options=[
            ProviderConnectionFieldOption(value="http", label="HTTP"),
            ProviderConnectionFieldOption(value="https", label="HTTPS"),
        ],
    )

    assert field.kind == "select"
    assert [option.label for option in field.options] == ["HTTP", "HTTPS"]


def test_duplicate_field_keys_are_rejected() -> None:
    with pytest.raises(ValidationError, match="connection field keys must be unique"):
        ProviderConnectionSchema(
            provider_id="example",
            provider_name="Example",
            fields=[
                ProviderConnectionField(key="host", label="Host", kind="host"),
                ProviderConnectionField(key="host", label="Hostname", kind="host"),
            ],
        )


def test_duplicate_option_values_are_rejected() -> None:
    with pytest.raises(ValidationError, match="connection field option values must be unique"):
        ProviderConnectionField(
            key="mode",
            label="Mode",
            kind="select",
            options=[
                ProviderConnectionFieldOption(value="https", label="HTTPS"),
                ProviderConnectionFieldOption(value="https", label="TLS"),
            ],
        )


def test_select_fields_must_define_provider_options() -> None:
    with pytest.raises(ValidationError, match="select connection fields must define options"):
        ProviderConnectionField(key="mode", label="Mode", kind="select")


def test_port_validation_metadata_can_be_represented() -> None:
    field = ProviderConnectionField(
        key="port",
        label="Port",
        kind="port",
        current_value=8443,
        validation={"minimum": 1, "maximum": 65535},
    )

    assert field.validation["minimum"] == 1
    assert field.validation["maximum"] == 65535


def test_secret_values_are_absent_from_repr_model_dump_and_json() -> None:
    field = ProviderConnectionField(
        key="password",
        label="Password",
        kind="secret",
        current_value="do-not-serialize",
        secret_state="configured",
    )

    assert field.current_value is None
    assert "do-not-serialize" not in repr(field)
    assert "do-not-serialize" not in str(field.model_dump())
    assert "do-not-serialize" not in field.model_dump_json()
    assert field.model_dump()["current_value"] is None
    assert field.model_dump()["secret_state"] == "configured"


def test_configured_and_missing_secret_states_serialize_safely() -> None:
    configured = ProviderConnectionField(
        key="token",
        label="Token",
        kind="secret",
        secret_state="configured",
    )
    missing = ProviderConnectionField(
        key="password",
        label="Password",
        kind="secret",
    )

    assert configured.model_dump()["secret_state"] == "configured"
    assert configured.model_dump()["current_value"] is None
    assert missing.model_dump()["secret_state"] == "missing"
    assert missing.model_dump()["current_value"] is None


def test_secret_state_is_rejected_for_non_secret_fields() -> None:
    with pytest.raises(ValidationError, match="secret_state is only valid"):
        ProviderConnectionField(
            key="host",
            label="Host",
            kind="host",
            secret_state="configured",
        )


def test_test_and_update_request_contracts_validate_confirmed_flag() -> None:
    assert ProviderConnectionTestRequest().confirmed is False
    assert UpdateProviderConnectionRequest(values={"host": "example.local"}, confirmed=True).confirmed is True

    with pytest.raises(ValidationError):
        ProviderConnectionTestRequest(confirmed="true")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        UpdateProviderConnectionRequest(confirmed="false")  # type: ignore[arg-type]


def test_runtime_optional_protocol_detection_works() -> None:
    assert isinstance(ConnectionCapableProvider(), ProviderConnectionAdapter)
    assert not isinstance(MinimalProvider(), ProviderConnectionAdapter)


def test_existing_provider_abc_remains_compatible() -> None:
    provider = MinimalProvider()

    assert provider.metadata.id == "minimal"
    assert not isinstance(provider, ProviderConnectionAdapter)


def test_docker_can_advertise_non_editable_path_without_special_public_model() -> None:
    schema = ProviderConnectionSchema(
        provider_id="docker",
        provider_name="Docker",
        editable=False,
        fields=[
            ProviderConnectionField(
                key="socket_path",
                label="Socket Path",
                kind="path",
                editable=False,
                current_value="/var/run/docker.sock",
                source="settings",
                help_text="Docker is a fixed privileged local-runtime connection.",
                validation={"editable": False, "permission_model": "supplemental_group"},
            ),
        ],
    )

    field = schema.fields[0]
    assert schema.editable is False
    assert field.kind == "path"
    assert field.editable is False
    assert field.current_value == "/var/run/docker.sock"
    assert field.validation["permission_model"] == "supplemental_group"
