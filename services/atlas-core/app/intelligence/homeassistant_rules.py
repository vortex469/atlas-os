from app.config.policies import get_ignored_entities
from app.intelligence.findings import Finding, Severity


def evaluate_homeassistant(
    status: dict,
    ignored_entities_getter=get_ignored_entities,
) -> list[Finding]:
    findings: list[Finding] = []

    unavailable_entities = status.get("unavailable_entities", [])
    ignored_entities = set(ignored_entities_getter())

    unexpected_unavailable = [
        entity
        for entity in unavailable_entities
        if entity.get("entity_id") not in ignored_entities
    ]

    ignored_count = (
        len(unavailable_entities)
        - len(unexpected_unavailable)
    )

    updates = (
        status
        .get("updates", {})
        .get("pending_count", 0)
    )

    if unexpected_unavailable:
        findings.append(
            Finding(
                id="homeassistant-unavailable",
                severity=Severity.WARNING,
                category="home",
                source="home_assistant",
                title="Home Assistant entities unavailable",
                message=(
                    f"Home Assistant has "
                    f"{len(unexpected_unavailable)} unexpected "
                    "unavailable or unknown entities."
                ),
                recommendation=(
                    "Review unexpected unavailable entities and add "
                    "intentional offline entities to policy."
                ),
                score_penalty=5,
                metric={
                    "unexpected_unavailable": len(
                        unexpected_unavailable
                    ),
                    "ignored_unavailable": ignored_count,
                },
                details={
                    "unavailable_entities": unexpected_unavailable,
                    "ignored_entities_count": ignored_count,
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
