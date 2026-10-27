import json
from pathlib import Path

from app.providers.models import ProviderAction
from app.providers.serializer import serialize_action


def _expected_fixture() -> list[dict[str, object]]:
    return [
        serialize_action(ProviderAction(id="run-diagnostics", label="Run Diagnostics")),
        serialize_action(
            ProviderAction(
                id="unload-model",
                label="Unload Model",
                description="Unload a model from memory.",
                icon="power",
                requires_confirmation=True,
                destructive=True,
                enabled=False,
                parameters={
                    "model": {
                        "type": "string",
                        "required": True,
                        "description": "Loaded model name.",
                        "example": "example:model",
                        "future": {"metadata": [1, 2]},
                    }
                },
            )
        ),
    ]


def test_mission_control_action_list_fixture_matches_serializer() -> None:
    fixture = (
        Path(__file__).resolve().parents[4]
        / "services/mission-control/src/test/providerActionList.fixture.json"
    )
    assert json.loads(fixture.read_text()) == _expected_fixture()
