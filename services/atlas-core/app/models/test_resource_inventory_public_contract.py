import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from app.models.resources import (
    ProviderExpectationOption,
    ProviderResource,
    ProviderResourceCollection,
    ProviderResourceExpectation,
    ProviderResourceSummary,
)


def _resource(resource_id: str, state: str, authority: str) -> ProviderResource:
    value = (
        "ignored"
        if state == "ignored"
        else "running"
        if state == "configured"
        else None
    )
    reason = {
        "needs_review": "no_legacy_policy",
        "configured": "matching_active_intent",
        "ignored": "matching_active_intent",
        "unsupported": "resource_type_unsupported",
        "unavailable": "authority_store_unavailable",
    }[state]
    return ProviderResource(
        provider_id="proxmox",
        resource_id=resource_id,
        display_name=f"Resource {resource_id}",
        resource_type="qemu",
        current_state="running",
        expectation=ProviderResourceExpectation(
            value=value,
            label=f"Expected {value}" if value else "Needs Review",
            state=state,
            authority=authority,
            reason=reason,
            record_version=1 if value else None,
            allowed_values=[
                ProviderExpectationOption(value="running", label="Running")
            ],
        ),
        configured=False,
        metadata={"vmid": int(resource_id), "future": {"nested": []}},
    )


def _collection(
    rows: list[ProviderResource],
    authority: str,
    status: str = "available",
    *,
    naive: bool = False,
) -> dict[str, object]:
    refreshed_at = datetime(2026, 10, 27, tzinfo=UTC)
    if naive:
        refreshed_at = refreshed_at.replace(tzinfo=None)
    return ProviderResourceCollection(
        provider_id="proxmox",
        provider_name="Proxmox",
        refreshed_at=refreshed_at,
        resources=rows,
        summary=ProviderResourceSummary(
            total=len(rows),
            configured=sum(row.configured for row in rows),
            needs_review=sum(row.needs_review for row in rows),
            missing=sum(row.missing for row in rows),
            ignored=sum(row.expectation.state == "ignored" for row in rows),
            by_type=dict(Counter(row.resource_type for row in rows)),
            by_state=dict(Counter(row.current_state for row in rows)),
        ),
        intent_authority=authority,
        intent_authority_status=status,
    ).model_dump(mode="json")


def _expected_fixture() -> list[dict[str, object]]:
    return [
        _collection(
            [_resource("110", "needs_review", "legacy_policy")], "legacy_policy"
        ),
        _collection(
            [
                _resource(str(111 + index), state, "provider_intent")
                for index, state in enumerate(["configured", "ignored", "unsupported"])
            ],
            "provider_intent",
        ),
        _collection(
            [_resource("114", "unavailable", "provider_intent")],
            "provider_intent",
            "unavailable",
        ),
        _collection([], "legacy_policy", naive=True),
    ]


def test_mission_control_inventory_fixture_matches_public_model() -> None:
    fixture = (
        Path(__file__).resolve().parents[4]
        / "services/mission-control/src/test/resourceInventory.fixture.json"
    )
    assert json.loads(fixture.read_text()) == _expected_fixture()
