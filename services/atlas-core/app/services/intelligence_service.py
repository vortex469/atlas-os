from app.intelligence.coordinator import collect_findings
from app.intelligence.engine import IntelligenceEngine
from app.intelligence.findings import Severity


def get_intelligence_summary() -> dict:
    engine = IntelligenceEngine()
    engine.extend(collect_findings())

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

    recommendations = list(
        dict.fromkeys(
            finding.recommendation
            for finding in findings
            if finding.recommendation
        )
    )

    sources = sorted(
        {
            finding.source
            for finding in findings
        }
    )

    return {
        "engine": {
            "name": "Atlas Cognitive Engine",
            "short_name": "ACE",
            "version": "0.3.0-alpha1",
        },
        "health": {
            "score": summary["score"],
            "status": summary["status"],
        },
        "counts": summary["counts"],
        "findings": grouped_findings,
        "recommendations": recommendations,
        "sources": sources,
    }
