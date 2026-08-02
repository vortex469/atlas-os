from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.execution_candidates.fingerprint import build_candidate_fingerprint
from app.execution_candidates.intake import (
    CandidatePlanningIntakeReasonCode,
    CandidatePlanningIntakeRequest,
    CandidatePlanningIntakeStatus,
)
from app.execution_candidates.models import (
    ApprovalLevel,
    ExecutionCandidate,
    ExecutionCandidateStatus,
    ExecutionCategory,
    ExecutionConstraint,
    ExecutionIntent,
    build_execution_candidate_id,
)
from app.intelligence import development_fixture as fixture
from app.services.execution_candidate_intake import (
    ExecutionCandidatePlanningIntakeError,
    validate_candidate_planning_intake,
)
from app.services.execution_candidates import (
    ExecutionCandidateCollectionError,
    ExecutionCandidateNotFoundError,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def candidate(**overrides: object) -> ExecutionCandidate:
    values: dict[str, object] = {
        "source_recommendation_id": "finding-1",
        "source_subsystem": "orion",
        "recommendation_class": "restart-service",
        "catalog_item_id": None,
        "target_id": "service-frigate",
        "target_type": "service",
        "execution_category": ExecutionCategory.RESTART,
        "execution_intent": ExecutionIntent.RESTART_SERVICE,
        "status": ExecutionCandidateStatus.ELIGIBLE,
        "required_approval_level": ApprovalLevel.STANDARD,
        "rationale": "Restart the service after approval.",
        "constraints": (ExecutionConstraint.SERVICE_DISRUPTION,),
        "evidence_ids": ("evidence-1",),
        "compatibility_assessment_id": None,
        "compatibility_status": None,
        "relationship_ids": (),
        "created_at": NOW,
        "expires_at": None,
    }
    values.update(overrides)
    values["id"] = build_execution_candidate_id(
        source_subsystem=str(values["source_subsystem"]),
        source_recommendation_id=str(values["source_recommendation_id"]),
        catalog_item_id=values["catalog_item_id"] if isinstance(values["catalog_item_id"], str) else None,
        target_id=str(values["target_id"]),
        execution_category=values["execution_category"],  # type: ignore[arg-type]
        execution_intent=values["execution_intent"],  # type: ignore[arg-type]
    )
    return ExecutionCandidate(**values)


def resolver(current: ExecutionCandidate):
    async def _resolve(candidate_id: str, **kwargs: object) -> ExecutionCandidate:
        del kwargs
        if candidate_id != current.id:
            raise ExecutionCandidateNotFoundError("missing")
        return current

    return _resolve


@pytest.mark.anyio
async def test_current_eligible_candidate_is_accepted_for_planning() -> None:
    current = candidate()

    result = await validate_candidate_planning_intake(
        current.id,
        CandidatePlanningIntakeRequest(requested_by="operator"),
        now=NOW,
        candidate_resolver=resolver(current),
        evidence_resolver=lambda candidate: candidate.evidence_ids,
    )

    assert result.status == CandidatePlanningIntakeStatus.ACCEPTED_FOR_PLANNING
    assert result.planning_allowed is True
    assert result.reason_codes == (CandidatePlanningIntakeReasonCode.ACCEPTED_FOR_PLANNING,)
    assert result.current_candidate is not None
    assert result.current_candidate.id == current.id


@pytest.mark.anyio
async def test_missing_candidate_returns_not_found() -> None:
    async def missing(candidate_id: str, **kwargs: object) -> ExecutionCandidate:
        del candidate_id, kwargs
        raise ExecutionCandidateNotFoundError("missing")

    result = await validate_candidate_planning_intake(
        "candidate-missing",
        CandidatePlanningIntakeRequest(),
        now=NOW,
        candidate_resolver=missing,
    )

    assert result.status == CandidatePlanningIntakeStatus.NOT_FOUND
    assert result.planning_allowed is False
    assert result.current_candidate is None


@pytest.mark.anyio
async def test_expected_fingerprint_mismatch_returns_stale_without_diff() -> None:
    current = candidate()

    result = await validate_candidate_planning_intake(
        current.id,
        CandidatePlanningIntakeRequest(expected_candidate_fingerprint="candidate-fingerprint-v1:stale"),
        now=NOW,
        candidate_resolver=resolver(current),
        evidence_resolver=lambda candidate: candidate.evidence_ids,
    )

    assert result.status == CandidatePlanningIntakeStatus.STALE
    assert result.reason_codes == (CandidatePlanningIntakeReasonCode.FINGERPRINT_MISMATCH,)
    assert result.current_candidate_fingerprint == build_candidate_fingerprint(current)
    dumped = result.model_dump()
    assert "diff" not in dumped
    assert "changes" not in dumped


@pytest.mark.anyio
async def test_missing_independent_evidence_returns_evidence_unavailable() -> None:
    current = candidate(evidence_ids=("evidence-1",))

    result = await validate_candidate_planning_intake(
        current.id,
        CandidatePlanningIntakeRequest(),
        now=NOW,
        candidate_resolver=resolver(current),
        evidence_resolver=lambda candidate: (),
    )

    assert result.status == CandidatePlanningIntakeStatus.EVIDENCE_UNAVAILABLE
    assert result.planning_allowed is False
    assert result.reason_codes == (CandidatePlanningIntakeReasonCode.EVIDENCE_UNAVAILABLE,)


@pytest.mark.anyio
async def test_missing_fixture_evidence_is_not_resolved_when_fixture_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ATLAS_ENABLE_DEVELOPMENT_CANDIDATE_FIXTURE", raising=False)
    current = candidate(evidence_ids=(fixture.DEVELOPMENT_FIXTURE_EVIDENCE_ID,))

    result = await validate_candidate_planning_intake(
        current.id,
        CandidatePlanningIntakeRequest(),
        now=NOW,
        candidate_resolver=resolver(current),
    )

    assert result.status == CandidatePlanningIntakeStatus.EVIDENCE_UNAVAILABLE
    assert result.reason_codes == (CandidatePlanningIntakeReasonCode.EVIDENCE_UNAVAILABLE,)


@pytest.mark.anyio
async def test_fixture_evidence_is_resolved_for_planning_intake_when_fixture_is_enabled_and_valid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ATLAS_ENABLE_DEVELOPMENT_CANDIDATE_FIXTURE", "true")
    monkeypatch.setenv("ATLAS_CORE_ENVIRONMENT", "development")
    monkeypatch.delenv("ATLAS_CONFIRM_DEVELOPMENT_CANDIDATE_FIXTURE", raising=False)

    current = candidate(evidence_ids=(fixture.DEVELOPMENT_FIXTURE_EVIDENCE_ID,))

    result = await validate_candidate_planning_intake(
        current.id,
        CandidatePlanningIntakeRequest(),
        now=NOW,
        candidate_resolver=resolver(current),
    )

    assert result.status == CandidatePlanningIntakeStatus.ACCEPTED_FOR_PLANNING
    assert result.planning_allowed is True


@pytest.mark.anyio
async def test_fixture_candidate_in_production_without_confirmation_is_not_resolved_for_intake(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ATLAS_ENABLE_DEVELOPMENT_CANDIDATE_FIXTURE", "true")
    monkeypatch.setenv("ATLAS_CORE_ENVIRONMENT", "production")
    monkeypatch.delenv("ATLAS_CONFIRM_DEVELOPMENT_CANDIDATE_FIXTURE", raising=False)

    current = candidate(evidence_ids=(fixture.DEVELOPMENT_FIXTURE_EVIDENCE_ID,))

    result = await validate_candidate_planning_intake(
        current.id,
        CandidatePlanningIntakeRequest(),
        now=NOW,
        candidate_resolver=resolver(current),
    )

    assert result.status == CandidatePlanningIntakeStatus.EVIDENCE_UNAVAILABLE
    assert result.reason_codes == (CandidatePlanningIntakeReasonCode.EVIDENCE_UNAVAILABLE,)


@pytest.mark.anyio
async def test_candidate_evidence_ids_alone_are_not_sufficient_for_default_planning_intake_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ATLAS_ENABLE_DEVELOPMENT_CANDIDATE_FIXTURE", raising=False)
    current = candidate(evidence_ids=("non-fixture-evidence-id",))

    result = await validate_candidate_planning_intake(
        current.id,
        CandidatePlanningIntakeRequest(),
        now=NOW,
        candidate_resolver=resolver(current),
    )

    assert result.status == CandidatePlanningIntakeStatus.EVIDENCE_UNAVAILABLE
    assert result.reason_codes == (CandidatePlanningIntakeReasonCode.EVIDENCE_UNAVAILABLE,)


@pytest.mark.anyio
async def test_explicit_evidence_resolver_remains_authoritative_for_fixture_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ATLAS_ENABLE_DEVELOPMENT_CANDIDATE_FIXTURE", "true")
    monkeypatch.setenv("ATLAS_CORE_ENVIRONMENT", "development")
    monkeypatch.delenv("ATLAS_CONFIRM_DEVELOPMENT_CANDIDATE_FIXTURE", raising=False)
    current = candidate(evidence_ids=(fixture.DEVELOPMENT_FIXTURE_EVIDENCE_ID,))

    result = await validate_candidate_planning_intake(
        current.id,
        CandidatePlanningIntakeRequest(),
        now=NOW,
        candidate_resolver=resolver(current),
        evidence_resolver=lambda candidate: (),
    )

    assert result.status == CandidatePlanningIntakeStatus.EVIDENCE_UNAVAILABLE


@pytest.mark.anyio
async def test_non_eligible_candidate_returns_not_eligible() -> None:
    current = candidate(status=ExecutionCandidateStatus.NOT_ELIGIBLE)

    result = await validate_candidate_planning_intake(
        current.id,
        CandidatePlanningIntakeRequest(),
        now=NOW,
        candidate_resolver=resolver(current),
        evidence_resolver=lambda candidate: candidate.evidence_ids,
    )

    assert result.status == CandidatePlanningIntakeStatus.NOT_ELIGIBLE
    assert CandidatePlanningIntakeReasonCode.CANDIDATE_NOT_ELIGIBLE in result.reason_codes


@pytest.mark.anyio
async def test_expired_candidate_returns_expired() -> None:
    current = candidate(created_at=NOW - timedelta(minutes=5), expires_at=NOW)

    result = await validate_candidate_planning_intake(
        current.id,
        CandidatePlanningIntakeRequest(),
        now=NOW,
        candidate_resolver=resolver(current),
        evidence_resolver=lambda candidate: candidate.evidence_ids,
    )

    assert result.status == CandidatePlanningIntakeStatus.EXPIRED
    assert result.reason_codes == (CandidatePlanningIntakeReasonCode.CANDIDATE_EXPIRED,)


@pytest.mark.anyio
async def test_requested_by_is_not_used_as_authorization() -> None:
    current = candidate()

    first = await validate_candidate_planning_intake(
        current.id,
        CandidatePlanningIntakeRequest(requested_by="operator-a"),
        now=NOW,
        candidate_resolver=resolver(current),
        evidence_resolver=lambda candidate: candidate.evidence_ids,
    )
    second = await validate_candidate_planning_intake(
        current.id,
        CandidatePlanningIntakeRequest(requested_by="operator-b"),
        now=NOW,
        candidate_resolver=resolver(current),
        evidence_resolver=lambda candidate: candidate.evidence_ids,
    )

    assert first == second


@pytest.mark.anyio
async def test_repeated_intake_is_deterministic() -> None:
    current = candidate(expires_at=NOW + timedelta(minutes=5))
    request = CandidatePlanningIntakeRequest(expected_candidate_fingerprint=build_candidate_fingerprint(current))

    first = await validate_candidate_planning_intake(
        current.id,
        request,
        now=NOW,
        candidate_resolver=resolver(current),
        evidence_resolver=lambda candidate: candidate.evidence_ids,
    )
    second = await validate_candidate_planning_intake(
        current.id,
        request,
        now=NOW,
        candidate_resolver=resolver(current),
        evidence_resolver=lambda candidate: candidate.evidence_ids,
    )

    assert first == second


@pytest.mark.anyio
async def test_global_candidate_collection_failure_is_sanitized() -> None:
    async def failing(candidate_id: str, **kwargs: object) -> ExecutionCandidate:
        del candidate_id, kwargs
        raise ExecutionCandidateCollectionError("/private/path/catalog.yaml failed")

    with pytest.raises(ExecutionCandidatePlanningIntakeError) as error:
        await validate_candidate_planning_intake(
            "candidate-any",
            CandidatePlanningIntakeRequest(),
            now=NOW,
            candidate_resolver=failing,
        )

    assert "/private/path" not in str(error.value)
    assert "catalog.yaml" not in str(error.value)


def test_intake_service_imports_no_agent_workflow_approval_persistence_or_http_modules() -> None:
    source = Path("app/services/execution_candidate_intake.py").read_text()

    forbidden_imports = (
        "app.agent",
        "atlas_agent",
        "app.workflows",
        "app.approvals",
        "app.persistence",
        "httpx",
        "requests",
        "subprocess",
    )
    assert all(forbidden not in source for forbidden in forbidden_imports)
