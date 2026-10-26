from pathlib import Path

from app.discovery.api_models import (
    DiscoveryRelationshipCollectionResponse,
    DiscoveryRelationshipReferenceResponse,
    DiscoveryRelationshipResponse,
)
from app.discovery.models import DiscoveryRelationshipType


def test_mission_control_relationship_fixture_matches_public_dto_defaults() -> None:
    fixture = (
        Path(__file__).resolve().parents[4]
        / "services/mission-control/src/test/discoveryRelationships.fixture.json"
    )
    parsed = DiscoveryRelationshipCollectionResponse.model_validate_json(fixture.read_text())
    expected = DiscoveryRelationshipCollectionResponse(
        item_id="frigate",
        outgoing=tuple(
            DiscoveryRelationshipReferenceResponse(
                source_item_id="frigate",
                target=f"target-{kind.value}",
                resolved=False,
                relationship=DiscoveryRelationshipResponse(
                    type=kind, target=f"target-{kind.value}"
                ),
            )
            for kind in DiscoveryRelationshipType
        ),
    )
    assert parsed.model_dump(mode="json") == expected.model_dump(mode="json")
