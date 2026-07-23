from app.intelligence.findings import Severity
from app.intelligence.homeassistant_rules import evaluate_homeassistant


def test_unexpected_unavailable_entities() -> None:
    findings = evaluate_homeassistant(
        {
            "unavailable_entities": [
                {
                    "entity_id": "sensor.expected_offline",
                    "name": "Expected Offline",
                    "state": "unavailable",
                },
                {
                    "entity_id": "sensor.failed_device",
                    "name": "Failed Device",
                    "state": "unknown",
                },
            ],
            "updates": {
                "pending_count": 3,
            },
        },
        ignored_entities_getter=lambda: [
            "sensor.expected_offline",
        ],
    )

    assert len(findings) == 2

    warning = next(
        finding
        for finding in findings
        if finding.id == "homeassistant-unavailable"
    )
    info = next(
        finding
        for finding in findings
        if finding.id == "homeassistant-updates"
    )

    assert warning.severity == Severity.WARNING
    assert warning.score_penalty == 5
    assert warning.affects_health is True
    assert warning.metric["unexpected_unavailable"] == 1
    assert warning.metric["ignored_unavailable"] == 1

    assert (
        warning.details["unavailable_entities"][0]["entity_id"]
        == "sensor.failed_device"
    )

    assert info.severity == Severity.INFO
    assert info.score_penalty == 0
    assert info.affects_health is False


def test_all_unavailable_entities_ignored() -> None:
    findings = evaluate_homeassistant(
        {
            "unavailable_entities": [
                {
                    "entity_id": "sensor.expected_offline",
                    "name": "Expected Offline",
                    "state": "unavailable",
                },
            ],
            "updates": {
                "pending_count": 0,
            },
        },
        ignored_entities_getter=lambda: [
            "sensor.expected_offline",
        ],
    )

    assert findings == []


def test_pending_updates_without_unavailable_entities() -> None:
    findings = evaluate_homeassistant(
        {
            "unavailable_entities": [],
            "updates": {
                "pending_count": 2,
            },
        },
        ignored_entities_getter=lambda: [],
    )

    assert len(findings) == 1
    assert findings[0].id == "homeassistant-updates"


if __name__ == "__main__":
    test_unexpected_unavailable_entities()
    test_all_unavailable_entities_ignored()
    test_pending_updates_without_unavailable_entities()
    print("Home Assistant intelligence rules tests passed")
