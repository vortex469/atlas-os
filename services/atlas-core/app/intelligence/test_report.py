from app.intelligence.report import (
    Assessment,
    Recommendation,
    SituationReport,
)


def test_situation_report_defaults():
    report = SituationReport(
        score=100,
        status="healthy",
        summary="Everything looks good.",
    )

    assert report.score == 100
    assert report.status == "healthy"
    assert report.findings == []
    assert report.assessments == []
    assert report.recommendations == []
    assert report.telemetry.providers == []
    assert report.telemetry.provider_collection_duration_ms == 0


def test_assessment():
    assessment = Assessment(
        title="Infrastructure Healthy",
        priority="info",
    )

    assert assessment.title == "Infrastructure Healthy"


def test_recommendation():
    recommendation = Recommendation(
        title="Review Updates",
        reason="Updates available",
        priority="low",
    )

    assert recommendation.priority == "low"
