from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.execution_candidates.models import ExecutionIntent
from app.intelligence.development_fixture import (
    DEVELOPMENT_FIXTURE_EVIDENCE_ID,
    DEVELOPMENT_FIXTURE_ID,
)
from app.intelligence.findings import Finding, Severity
from app.services import execution_candidates as service
from app.services.provider_resources import (
    OperationalTargetAmbiguousError,
    OperationalTargetIdentityUnavailableError,
    OperationalTargetMarkedMissingError,
    OperationalTargetResourceNotFoundError,
    OperationalTargetTypeMismatchError,
    ProviderResourceOperationError,
)

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


def _restart_finding(*, provider_id: str | None = "docker") -> Finding:
    details: dict[str, object] = {
        "source_subsystem": "orion",
        "recommendation_class": "restart_service",
        "target_id": "service-frigate",
        "target_type": "service",
        "evidence_ids": ("evidence-1",),
    }
    if provider_id is not None:
        details["provider_id"] = provider_id
    return Finding(
        id="finding-restart-frigate",
        severity=Severity.WARNING,
        category="runtime",
        source="orion",
        title="Restart Frigate",
        message="Restart the exact service after approval.",
        recommendation="Restart the exact service.",
        component="frigate",
        details=details,
        affects_health=False,
        score_penalty=0,
    )


@pytest.mark.anyio
async def test_operational_candidate_is_enriched_with_sanitized_authoritative_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def resolve(provider_id: str, resource_id: str, resource_type: str):
        assert (provider_id, resource_id, resource_type) == (
            "docker",
            "service-frigate",
            "service",
        )
        return SimpleNamespace(
            provider=SimpleNamespace(id="docker"),
            resource=SimpleNamespace(
                resource_id="service-frigate",
                resource_type="service",
                current_state="running",
                identity=SimpleNamespace(token="must-not-leak"),
            ),
            resource_fingerprint="operational-target-v1:abc",
        )

    monkeypatch.setattr(service, "resolve_operational_target", resolve)
    candidates = await service.collect_current_execution_candidates(
        finding_collector=lambda: (_restart_finding(),),
        available_evidence_ids=("evidence-1",),
        now=NOW,
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.status is service.ExecutionCandidateStatus.ELIGIBLE
    assert candidate.operational_target is not None
    assert candidate.operational_target.resource_fingerprint == "operational-target-v1:abc"
    assert "must-not-leak" not in candidate.model_dump_json()


@pytest.mark.anyio
async def test_operational_candidate_without_provider_is_not_eligible() -> None:
    candidate = (
        await service.collect_current_execution_candidates(
            finding_collector=lambda: (_restart_finding(provider_id=None),),
            available_evidence_ids=("evidence-1",),
            now=NOW,
        )
    )[0]

    assert candidate.status is service.ExecutionCandidateStatus.NOT_ELIGIBLE
    assert candidate.operational_target is None


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("error_type", "reason"),
    (
        (OperationalTargetResourceNotFoundError, "operational_target_not_found"),
        (OperationalTargetAmbiguousError, "operational_target_ambiguous"),
        (OperationalTargetTypeMismatchError, "operational_target_type_mismatch"),
        (OperationalTargetMarkedMissingError, "operational_target_marked_missing"),
        (
            OperationalTargetIdentityUnavailableError,
            "operational_target_identity_unavailable",
        ),
    ),
)
async def test_operational_resolution_failure_is_controlled_non_eligible(
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[Exception],
    reason: str,
) -> None:
    async def missing(*args: str):
        raise error_type("unavailable")

    monkeypatch.setattr(service, "resolve_operational_target", missing)
    candidate = (
        await service.collect_current_execution_candidates(
            finding_collector=lambda: (_restart_finding(),),
            available_evidence_ids=("evidence-1",),
            now=NOW,
        )
    )[0]

    assert candidate.status is service.ExecutionCandidateStatus.NOT_ELIGIBLE
    assert candidate.operational_target_resolution_reason.value == reason


@pytest.mark.anyio
async def test_temporary_operational_provider_failure_is_not_claimed_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unavailable(*args: str):
        raise ProviderResourceOperationError("temporary")

    monkeypatch.setattr(service, "resolve_operational_target", unavailable)
    with pytest.raises(service.ExecutionCandidateCollectionError):
        await service.collect_current_execution_candidates(
            finding_collector=lambda: (_restart_finding(),),
            available_evidence_ids=("evidence-1",),
            now=NOW,
        )


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
