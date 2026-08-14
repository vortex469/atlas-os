from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from app.candidate_planning.models import (
    CandidatePlanningSession,
    CandidatePlanningSessionStatus,
    CandidateSnapshot,
    CoreCandidatePlanningIntakeStatus,
    OperationalActionRequest,
    OperationalCandidatePlan,
    OperationalVerificationSpecification,
)
from app.workflow.models import (
    WorkflowEffectKind,
    WorkflowSession,
    WorkflowSessionState,
)

NOW = datetime(2026, 8, 13, tzinfo=UTC)


def verification() -> OperationalVerificationSpecification:
    return OperationalVerificationSpecification(
        pre_state="running",
        expected_post_state="running",
        identity_fingerprint="sha256:resource",
        health_requirement="healthy",
        unknown_outcome_policy="stop-and-reconcile",
    )


def operational_plan() -> OperationalCandidatePlan:
    return OperationalCandidatePlan(
        identifier="operational-plan-1",
        session_id="candidate-plan-1",
        candidate_id="candidate-1",
        candidate_fingerprint="candidate-fingerprint-v1:aaa",
        effect_kind=WorkflowEffectKind.OPERATIONAL_ACTION,
        execution_intent="restart-service",
        provider_id="proxmox",
        resource_id="qemu/101",
        resource_type="qemu",
        target_fingerprint="sha256:resource",
        target_version="1",
        expected_pre_state="running",
        intended_action="restart the exact service resource",
        disruption_scope="atlas-core service interruption",
        verification=verification(),
        failure_considerations=("Unknown outcomes require reconciliation.",),
        evidence_ids=("evidence-1",),
        created_at=NOW,
        revalidated_candidate_fingerprint="candidate-fingerprint-v1:aaa",
    )


def operational_request() -> OperationalActionRequest:
    return OperationalActionRequest(
        request_id="operational-request-1",
        request_digest="",
        idempotency_key="",
        workflow_session_id="workflow-1",
        candidate_planning_session_id="candidate-plan-1",
        candidate_id="candidate-1",
        candidate_fingerprint="candidate-fingerprint-v1:aaa",
        candidate_plan_id="operational-plan-1",
        candidate_plan_fingerprint="operational-plan-fingerprint-v1:aaa",
        effect_kind=WorkflowEffectKind.OPERATIONAL_ACTION,
        execution_intent="restart-service",
        provider_id="proxmox",
        resource_id="qemu/101",
        resource_type="qemu",
        provider_action_id="proxmox-qemu-graceful-restart-v1",
        target_fingerprint="sha256:resource",
        target_version="1",
        disruption_scope="atlas-core service interruption",
        evidence_ids=("evidence-1",),
        expected_pre_state="running",
        verification=verification(),
        expires_at=NOW + timedelta(minutes=5),
        translator_version="operational-contract-v1",
        generated_at=NOW,
    )


def test_operational_models_are_separate_and_non_executable() -> None:
    plan = operational_plan()
    request = operational_request()

    forbidden_fields = {
        "argv",
        "endpoint",
        "working_directory",
        "environment",
        "repository_root",
        "repository_branch",
        "repository_head",
        "affected_files",
    }
    assert forbidden_fields.isdisjoint(plan.__dataclass_fields__)
    assert forbidden_fields.isdisjoint(request.__dataclass_fields__)


def test_operational_models_require_operational_effect_kind() -> None:
    with pytest.raises(ValueError, match="operational plans"):
        replace(
            operational_plan(),
            effect_kind=WorkflowEffectKind.REPOSITORY_CHANGE,
        )


def test_workflow_rejects_effect_specific_request_mismatches() -> None:
    with pytest.raises(ValueError, match="repository_change"):
        WorkflowSession(
            identifier="workflow-1",
            request=None,
            plan=None,
            state=WorkflowSessionState.BLOCKED,
            effect_kind=WorkflowEffectKind.REPOSITORY_CHANGE,
            operational_action_request=operational_request(),
        )
    with pytest.raises(ValueError, match="operational_action"):
        WorkflowSession(
            identifier="workflow-1",
            request=None,
            plan=None,
            state=WorkflowSessionState.BLOCKED,
            effect_kind=WorkflowEffectKind.OPERATIONAL_ACTION,
            candidate_implementation_request=object(),  # type: ignore[arg-type]
        )


def test_planning_session_rejects_both_plan_kinds() -> None:
    with pytest.raises(ValueError, match="both repository and operational plans"):
        CandidatePlanningSession(
            identifier="candidate-plan-1",
            candidate_id="candidate-1",
            candidate_fingerprint="candidate-fingerprint-v1:aaa",
            status=CandidatePlanningSessionStatus.READY_FOR_PLANNING,
            snapshot=CandidateSnapshot(
                candidate_id="candidate-1",
                candidate_fingerprint="candidate-fingerprint-v1:aaa",
                source_recommendation_id="finding-1",
                source_subsystem="orion",
                recommendation_class="restart_service",
                catalog_item_id=None,
                target_id="atlas-core",
                target_type="service",
                execution_category="restart",
                execution_intent="restart-service",
                required_approval_level="standard",
                rationale="Restart the exact service.",
                constraints=("service-disruption",),
                evidence_ids=("evidence-1",),
                compatibility_assessment_id=None,
                compatibility_status=None,
                relationship_ids=(),
                expires_at=None,
                intake_status=CoreCandidatePlanningIntakeStatus.ACCEPTED_FOR_PLANNING,
                intake_reason_codes=(),
                intake_timestamp=NOW,
            ),
            created_at=NOW,
            plan=object(),  # type: ignore[arg-type]
            operational_plan=operational_plan(),
        )
