from app.intelligence.coordinator import build_report


async def get_intelligence_summary() -> dict:
    """Return the current ACE Situation Report."""
    report = await build_report()
    return report.model_dump(mode="json")
