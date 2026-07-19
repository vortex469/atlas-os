from app.intelligence.engine import IntelligenceEngine
from app.intelligence.findings import Finding, Severity


def test_engine() -> None:
    engine = IntelligenceEngine()

    engine.add(
        Finding(
            id="homeassistant-unavailable",
            severity=Severity.WARNING,
            category="home",
            source="home_assistant",
            title="Unavailable entities",
            message="Home Assistant has unavailable entities.",
            score_penalty=5,
        )
    )

    engine.add(
        Finding(
            id="homeassistant-updates",
            severity=Severity.INFO,
            category="updates",
            source="home_assistant",
            title="Updates available",
            message="Home Assistant has updates available.",
            affects_health=False,
        )
    )

    summary = engine.summary()

    assert summary["score"] == 95
    assert summary["status"] == "degraded"
    assert summary["counts"]["warning"] == 1
    assert summary["counts"]["info"] == 1
    assert len(summary["findings"]) == 2


if __name__ == "__main__":
    test_engine()
    print("Intelligence engine test passed")
