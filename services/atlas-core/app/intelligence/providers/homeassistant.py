from app.intelligence.findings import Finding, Severity
from app.intelligence.homeassistant_rules import evaluate_homeassistant
from app.services.homeassistant_service import get_homeassistant_status


def collect_homeassistant_findings() -> list[Finding]:
    try:
        status = get_homeassistant_status()
        return evaluate_homeassistant(status)
    except Exception as error:
        return [
            Finding(
                id="homeassistant-provider-failure",
                severity=Severity.CRITICAL,
                category="infrastructure",
                source="home_assistant",
                title="Home Assistant monitoring failed",
                message=(
                    "ACE could not collect Home Assistant status: "
                    f"{error}"
                ),
                recommendation=(
                    "Verify Home Assistant connectivity, credentials, "
                    "and API availability."
                ),
                score_penalty=20,
                details={
                    "error": str(error),
                },
            )
        ]
