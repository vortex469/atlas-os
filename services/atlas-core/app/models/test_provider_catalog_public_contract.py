import json
from pathlib import Path

from app.models.contracts import ProviderHealth, ProviderResponse


def _expected_fixture() -> list[dict[str, object]]:
    return [
        ProviderResponse(
            id="proxmox",
            name="Proxmox",
            workspace="infrastructure",
            priority="critical",
            version="1",
            description="Provider evidence",
            icon="server",
            health=ProviderHealth(status="healthy"),
        ).model_dump(mode="json"),
        ProviderResponse(
            id="docker",
            name="Docker",
            workspace="future_workspace",
            priority="future_priority",
            version="future_version",
            description="More provider evidence",
            icon="future_icon",
            capabilities=["resources", "future_capability"],
            health=ProviderHealth(
                status="future_status",
                latency_ms=3.5,
                http_status=200,
                message="Reported provider condition",
                details={
                    "url": "https://example.invalid/provider",
                    "custom": {"nested": []},
                },
            ),
        ).model_dump(mode="json"),
    ]


def test_mission_control_catalog_fixture_matches_public_model() -> None:
    fixture = (
        Path(__file__).resolve().parents[4]
        / "services/mission-control/src/test/providerCatalog.fixture.json"
    )
    assert json.loads(fixture.read_text()) == _expected_fixture()
