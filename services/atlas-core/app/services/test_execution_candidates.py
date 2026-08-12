from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.execution_candidates.models import ExecutionIntent
from app.intelligence.development_fixture import (
    DEVELOPMENT_FIXTURE_EVIDENCE_ID,
    DEVELOPMENT_FIXTURE_ID,
)
from app.intelligence.findings import Finding, Severity
from app.services import execution_candidates as service

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _untrusted_finding() -> Finding:
    return Finding(
        id="provider-homeassistant-unavailable",
        severity=Severity.WARNING,
        category="home",
        source="home_assistant",
        title="Home Assistant unavailable",
        message="Home Assistant has state drift.",
        recommendation="Investigate unavailable entities.",
        component="home_assistant",
        details={},
        affects_health=True,
        score_penalty=0,
    )


async def _provider_findings_with_telemetry() -> tuple[tuple[Finding, ...], object]:
    return (), type("Telemetry", (), {"providers": ()})()


def _for_current() -> Finding:
    return _untrusted_finding()


@pytest.mark.anyio
async def test_development_fixture_disabled_adds_no_candidate_findings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ATLAS_ENABLE_DEVELOPMENT_CANDIDATE_FIXTURE", raising=False)
    monkeypatch.delenv("ATLAS_CORE_ENVIRONMENT", raising=False)

    monkeypatch.setattr(
        service,
        "collect_findings",
        lambda: (_for_current(),),
    )
    monkeypatch.setattr(
        service,
        "collect_provider_findings_with_telemetry",
        _provider_findings_with_telemetry,
    )
    monkeypatch.setattr(
        service,
        "collect_discovery_compatibility_findings",
        lambda: (),
    )
    monkeypatch.setattr(
        service,
        "_performance_findings",
        lambda *args, **kwargs: (),
    )

    findings = await service.collect_current_findings()
    assert tuple(f.id for f in findings) == ("provider-homeassistant-unavailable",)

    candidates = await service.collect_current_execution_candidates(now=NOW)
    assert candidates == ()


@pytest.mark.anyio
async def test_development_fixture_enabled_projects_one_eligible_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATLAS_ENABLE_DEVELOPMENT_CANDIDATE_FIXTURE", "true")
    monkeypatch.setenv("ATLAS_CORE_ENVIRONMENT", "development")

    monkeypatch.setattr(
        service,
        "collect_findings",
        lambda: (_for_current(),),
    )
    monkeypatch.setattr(
        service,
        "collect_provider_findings_with_telemetry",
        _provider_findings_with_telemetry,
    )
    monkeypatch.setattr(
        service,
        "collect_discovery_compatibility_findings",
        lambda: (),
    )
    monkeypatch.setattr(
        service,
        "_performance_findings",
        lambda *args, **kwargs: (),
    )

    candidates = await service.collect_current_execution_candidates(now=NOW)
    assert len(candidates) == 1

    candidate = candidates[0]
    assert candidate.id.startswith("candidate-orion-")
    assert candidate.status == service.ExecutionCandidateStatus.ELIGIBLE
    assert candidate.execution_intent == ExecutionIntent.UPDATE_COMPOSE_STACK
    assert candidate.source_recommendation_id == DEVELOPMENT_FIXTURE_ID
    assert candidate.evidence_ids == (DEVELOPMENT_FIXTURE_EVIDENCE_ID,)


@pytest.mark.anyio
async def test_development_fixture_candidate_is_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATLAS_ENABLE_DEVELOPMENT_CANDIDATE_FIXTURE", "true")
    monkeypatch.setenv("ATLAS_CORE_ENVIRONMENT", "development")

    monkeypatch.setattr(
        service,
        "collect_findings",
        lambda: (),
    )
    monkeypatch.setattr(
        service,
        "collect_provider_findings_with_telemetry",
        _provider_findings_with_telemetry,
    )
    monkeypatch.setattr(
        service,
        "collect_discovery_compatibility_findings",
        lambda: (),
    )
    monkeypatch.setattr(
        service,
        "_performance_findings",
        lambda *args, **kwargs: (),
    )

    first = await service.collect_current_execution_candidates(now=NOW)
    second = await service.collect_current_execution_candidates(now=NOW)

    assert len(first) == len(second) == 1
    assert first[0].id == second[0].id


@pytest.mark.anyio
async def test_rc1_smoke_candidate_requires_gate_and_is_deterministic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ATLAS_ENABLE_DEVELOPMENT_CANDIDATE_FIXTURE", "true")
    monkeypatch.setenv("ATLAS_CORE_ENVIRONMENT", "development")
    monkeypatch.delenv("ATLAS_ENABLE_RC1_VALIDATION_SMOKE", raising=False)
    monkeypatch.setattr(service, "collect_findings", lambda: ())
    monkeypatch.setattr(service, "collect_provider_findings_with_telemetry", _provider_findings_with_telemetry)
    monkeypatch.setattr(service, "collect_discovery_compatibility_findings", lambda: ())
    monkeypatch.setattr(service, "_performance_findings", lambda *args, **kwargs: ())

    normal = await service.collect_current_execution_candidates(now=NOW)
    assert len(normal) == 1
    assert all(candidate.execution_intent != ExecutionIntent.RC1_VALIDATION_SMOKE for candidate in normal)

    monkeypatch.setenv("ATLAS_ENABLE_RC1_VALIDATION_SMOKE", "true")
    first = await service.collect_current_execution_candidates(now=NOW)
    second = await service.collect_current_execution_candidates(now=NOW)
    smoke = [candidate for candidate in first if candidate.execution_intent == ExecutionIntent.RC1_VALIDATION_SMOKE]
    assert len(smoke) == 1
    assert smoke[0].id == "candidate-orion-orion-dev-rc1-validation-smoke-atlas-rc1-validation-atlas-repository-update-rc1-validation-smoke"
    assert smoke[0].recommendation_class == "rc1-validation-smoke"
    assert smoke[0].target_id == "atlas-repository"
    assert smoke[0].evidence_ids == ("orion-rc1-validation-smoke-evidence-0001",)
    assert [candidate.id for candidate in first] == [candidate.id for candidate in second]


@pytest.mark.anyio
async def test_rc1_smoke_fixture_skips_external_finding_collectors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ATLAS_ENABLE_DEVELOPMENT_CANDIDATE_FIXTURE", "true")
    monkeypatch.setenv("ATLAS_ENABLE_RC1_VALIDATION_SMOKE", "true")
    monkeypatch.setattr(service, "collect_findings", lambda: (_ for _ in ()).throw(AssertionError()))
    findings = await service.collect_current_findings()
    assert {finding.id for finding in findings} == {
        DEVELOPMENT_FIXTURE_ID,
        "orion-dev-rc1-validation-smoke",
    }
