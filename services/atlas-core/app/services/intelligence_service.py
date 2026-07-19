from app.intelligence.coordinator import build_report


def get_intelligence_summary() -> dict:
    """Return the current ACE Situation Report."""
    report = build_report()
    return report.model_dump(mode="json")
