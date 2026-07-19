from app.intelligence.engine import IntelligenceEngine
from app.intelligence.findings import Severity
from app.intelligence.homeassistant_rules import evaluate_homeassistant
from app.services.homeassistant_service import get_homeassistant_status


def get_intelligence_summary() -> dict:
    engine = IntelligenceEngine()

    homeassistant_status = get_homeassistant_status()
    engine.extend(
        evaluate_homeassistant(homeassistant_status)
    )

    summary = engine.summary()
    findings = engine.findings()

    grouped_findings = {
        "critical": [
            finding.model_dump(mode="json")
            for finding in findings
            if finding.severity == Severity.CRITICAL
        ],
        "warnings": [
            finding.model_dump(mode="json")
            for finding in findings
            if finding.severity == Severity.WARNING
        ],
        "info": [
            finding.model_dump(mode="json")
            for finding in findings
            if finding.severity == Severity.INFO
        ],
    }

    recommendations = [
        finding.recommendation
        for finding in findings
        if finding.recommendation
    ]

    return {
        "health": {
            "score": summary["score"],
            "status": summary["status"],
        },
        "counts": summary["counts"],
        "findings": grouped_findings,
        "recommendations": recommendations,
        "sources": {
            "home_assistant": {
                "status": "online",
            },
        },
    }
