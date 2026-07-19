from app.intelligence.findings import Severity
from app.intelligence.homeassistant_rules import evaluate_homeassistant


def test_homeassistant_rules() -> None:
    findings = evaluate_homeassistant(
        {
            "entities": {
                "unavailable_count": 103,
            },
            "updates": {
                "pending_count": 3,
            },
        }
    )

    assert len(findings) == 2

    warning = findings[0]
    info = findings[1]

    assert warning.severity == Severity.WARNING
    assert warning.score_penalty == 5
    assert warning.affects_health is True

    assert info.severity == Severity.INFO
    assert info.score_penalty == 0
    assert info.affects_health is False


if __name__ == "__main__":
    test_homeassistant_rules()
    print("Home Assistant intelligence rules test passed")
