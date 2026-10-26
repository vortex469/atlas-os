import json
from pathlib import Path

from app.models.provider_intents import (
    ProviderIntentCoordinateMutationResult,
    ProviderIntentMutationRequest,
)
from app.models.provider_management import ProviderMonitoringExpectation


def _expected_fixture() -> dict[str, object]:
    cases = {}
    for outcome, expectation, version, token in [
        ("created", "running", 0, "a"),
        ("updated", "stopped", 4, "b"),
        ("rebound", "ignored", 0, "c"),
    ]:
        request = ProviderIntentMutationRequest(
            request_id=f"provider-intent-mutation-{token * 32}",
            expected_management_fingerprint=(
                f"provider-management-fingerprint-v1:{'a' * 64}"
            ),
            expectation=ProviderMonitoringExpectation(expectation),
            expected_record_version=version,
            acknowledge_monitoring_suppression=expectation == "ignored",
        )
        result = ProviderIntentCoordinateMutationResult(
            outcome=outcome,
            request_id=request.request_id,
            provider_id="proxmox",
            resource_type="qemu",
            resource_id="110",
            management_fingerprint=request.expected_management_fingerprint,
            expectation=request.expectation,
            record_version=version + 1,
            superseded_previous_incarnation=outcome == "rebound",
        )
        cases[outcome] = {
            "request": request.model_dump(mode="json"),
            "result": result.model_dump(mode="json"),
        }
    return cases


def test_mission_control_monitoring_receipts_match_public_models() -> None:
    fixture = (
        Path(__file__).resolve().parents[4]
        / "services/mission-control/src/test/monitoringReceipts.fixture.json"
    )
    assert json.loads(fixture.read_text()) == _expected_fixture()
