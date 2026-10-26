import json
from datetime import UTC, datetime
from pathlib import Path
from typing import get_args

from app.models.connections import (
    ProviderConnectionField,
    ProviderConnectionFieldKind,
    ProviderConnectionFieldOption,
    ProviderConnectionSchema,
    UpdateProviderConnectionResult,
)
from app.models.connections import (
    TestProviderConnectionResult as ConnectionTestResult,
)


def _expected_fixture() -> dict[str, object]:
    schema = ProviderConnectionSchema(
        provider_id="proxmox",
        provider_name="Proxmox",
        fields=[
            ProviderConnectionField(
                key=kind,
                label=kind.title(),
                kind=kind,
                current_value=(
                    True
                    if kind == "boolean"
                    else 443
                    if kind == "port"
                    else "native-secret-canary"
                    if kind == "secret"
                    else None
                ),
                options=[
                    ProviderConnectionFieldOption(value="fixture", label="Fixture")
                ]
                if kind == "select"
                else [],
            )
            for kind in get_args(ProviderConnectionFieldKind)
        ],
    )
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    return {
        "schema": schema.model_dump(mode="json"),
        "test": ConnectionTestResult(
            provider_id="proxmox", status="success", tested_at=timestamp
        ).model_dump(mode="json"),
        "save": UpdateProviderConnectionResult(
            provider_id="proxmox", connection_schema=schema, updated_at=timestamp
        ).model_dump(mode="json"),
    }


def test_mission_control_connection_fixture_matches_public_models() -> None:
    fixture = (
        Path(__file__).resolve().parents[4]
        / "services/mission-control/src/test/connections.fixture.json"
    )
    assert json.loads(fixture.read_text()) == _expected_fixture()
