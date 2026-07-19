from app.intelligence.findings import Finding, Severity


def evaluate_homeassistant(status: dict) -> list[Finding]:
    findings: list[Finding] = []

    unavailable = (
        status
        .get("entities", {})
        .get("unavailable_count", 0)
    )

    updates = (
        status
        .get("updates", {})
        .get("pending_count", 0)
    )

    if unavailable > 0:
        findings.append(
            Finding(
                id="homeassistant-unavailable",
                severity=Severity.WARNING,
                category="home",
                source="home_assistant",
                title="Home Assistant entities unavailable",
                message=(
                    f"Home Assistant has {unavailable} unavailable "
                    "or unknown entities."
                ),
                recommendation=(
                    "Review unavailable entities and classify expected "
                    "offline devices."
                ),
                score_penalty=5,
                details={
                    "unavailable_entities": unavailable,
                },
            )
        )

    if updates > 0:
        findings.append(
            Finding(
                id="homeassistant-updates",
                severity=Severity.INFO,
                category="updates",
                source="home_assistant",
                title="Home Assistant updates available",
                message=f"Home Assistant has {updates} pending updates.",
                recommendation="Review updates before installation.",
                affects_health=False,
                score_penalty=0,
                details={
                    "updates": updates,
                },
            )
        )

    return findings
