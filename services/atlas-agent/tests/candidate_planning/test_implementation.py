"""Tests for candidate implementation translation."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from app.candidate_planning.conversion import candidate_plan_fingerprint
from app.candidate_planning.implementation import (
    TRANSLATOR_VERSION,
    CandidateImplementationTranslator,
)
from app.candidate_planning.models import (
    CandidatePlan,
    CandidatePlanningSession,
    CandidatePlanningSessionStatus,
    CandidateSnapshot,
    ComposeMutationSpecification,
    CoreCandidatePlanningIntakeStatus,
)
from app.execution.policy import ToolPolicy
from app.repository.models import RepositorySnapshot
from app.workflow.models import (
    CandidateWorkflowMetadata,
    WorkflowSession,
    WorkflowSessionState,
    WorkflowSource,
)

NOW = datetime(2026, 8, 2, tzinfo=UTC)


def plan(root: Path, *, affected_files: tuple[Path, ...] = (Path("compose.production.yaml"),)) -> CandidatePlan:
    return CandidatePlan(
        identifier="candidate-plan-output-candidate-plan-1",
        session_id="candidate-plan-1",
        candidate_id="candidate-1",
        candidate_fingerprint="candidate-fingerprint-v1:aaa",
        title="Prepare compose stack update proposal",
        objective="Create a minimal repository change proposal.",
        assumptions=("Planning is read-only.",),
        constraints=("requires-current-evidence",),
        proposed_steps=("Inspect trusted compose definitions.",),
        likely_affected_components=("atlas-compose",),
        likely_affected_files=affected_files,
        verification_strategy=("Validate later after workflow conversion.",),
        rollback_considerations=("Use version control rollback.",),
        unresolved_questions=(),
        evidence_ids=("evidence-1",),
        created_at=NOW,
        repository_root=root,
        repository_branch="feature/atlas-agent",
        repository_head="abc123",
        revalidated_candidate_fingerprint="candidate-fingerprint-v1:aaa",
        mutation=ComposeMutationSpecification(file=Path("compose.production.yaml"), service="atlas-agent", property="image", operation="update", expected_value="atlas-agent:old", desired_value="atlas-agent:new", preservation_constraints=("preserve-unrelated-services",)),
    )


def session(root: Path, *, intent: str = "update-compose-stack") -> CandidatePlanningSession:
    candidate_plan = plan(root)
    return CandidatePlanningSession(
        identifier="candidate-plan-1",
        candidate_id="candidate-1",
        candidate_fingerprint="candidate-fingerprint-v1:aaa",
        status=CandidatePlanningSessionStatus.READY_FOR_PLANNING,
        snapshot=CandidateSnapshot(
            candidate_id="candidate-1",
            candidate_fingerprint="candidate-fingerprint-v1:aaa",
            source_recommendation_id="finding-1",
            source_subsystem="orion",
            recommendation_class="update_compose_stack",
            catalog_item_id="frigate",
            target_id="atlas-compose",
            target_type="repository",
            execution_category="update",
            execution_intent=intent,
            required_approval_level="standard",
            rationale="Update compose stack.",
            constraints=("requires-current-evidence",),
            evidence_ids=("evidence-1",),
            compatibility_assessment_id="assessment-1",
            compatibility_status="compatible",
            relationship_ids=("relationship-1",),
            expires_at=None,
            intake_status=CoreCandidatePlanningIntakeStatus.ACCEPTED_FOR_PLANNING,
            intake_reason_codes=(),
            intake_timestamp=NOW,
            mutation=ComposeMutationSpecification(file=Path("compose.production.yaml"), service="atlas-agent", property="image", operation="update", expected_value="atlas-agent:old", desired_value="atlas-agent:new", preservation_constraints=("preserve-unrelated-services",)),
        ),
        created_at=NOW,
        planning_status=CandidatePlanningSessionStatus.PLAN_READY,
        plan=candidate_plan,
        candidate_plan_fingerprint=candidate_plan_fingerprint(candidate_plan),
        workflow_session_id="candidate-workflow-1",
    )


def workflow(candidate_session: CandidatePlanningSession) -> WorkflowSession:
    assert candidate_session.plan is not None
    return WorkflowSession(
        identifier="candidate-workflow-1",
        request=None,
        plan=None,
        state=WorkflowSessionState.AWAITING_APPROVAL,
        source=WorkflowSource.CANDIDATE,
        candidate_metadata=CandidateWorkflowMetadata(
            candidate_planning_session_id=candidate_session.identifier,
            candidate_id=candidate_session.candidate_id,
            candidate_fingerprint=candidate_session.candidate_fingerprint,
            candidate_plan_id=candidate_session.plan.identifier,
            candidate_plan_fingerprint=candidate_session.candidate_plan_fingerprint or "",
            source_recommendation_id=candidate_session.snapshot.source_recommendation_id,
            source_subsystem=candidate_session.snapshot.source_subsystem,
            catalog_item_id=candidate_session.snapshot.catalog_item_id,
            target_id=candidate_session.snapshot.target_id,
            target_type=candidate_session.snapshot.target_type,
            execution_category=candidate_session.snapshot.execution_category,
            execution_intent=candidate_session.snapshot.execution_intent,
            evidence_ids=candidate_session.snapshot.evidence_ids,
            compatibility_assessment_id=candidate_session.snapshot.compatibility_assessment_id,
            compatibility_status=candidate_session.snapshot.compatibility_status,
            relationship_ids=candidate_session.snapshot.relationship_ids,
            conversion_timestamp=NOW,
            core_revalidation_status="accepted_for_planning",
            core_revalidation_fingerprint=candidate_session.candidate_fingerprint,
        ),
    )


def repository(root: Path, *, head: str = "abc123") -> RepositorySnapshot:
    return RepositorySnapshot(
        root=root,
        branch="feature/atlas-agent",
        head_commit=head,
        is_clean=True,
        modified_files=(),
        staged_files=(),
        untracked_files=(),
    )


def test_translator_generates_deterministic_tool_policy_validated_request(tmp_path: Path) -> None:
    candidate_session = session(tmp_path)
    candidate_workflow = workflow(candidate_session)
    translator = CandidateImplementationTranslator(tool_policy=ToolPolicy())

    first = translator.translate(
        session=candidate_session,
        workflow=candidate_workflow,
        repository=repository(tmp_path),
        generated_at=NOW,
    )
    second = translator.translate(
        session=candidate_session,
        workflow=candidate_workflow,
        repository=repository(tmp_path),
        generated_at=NOW,
    )

    assert first.request is not None
    assert first.request == second.request
    assert first.request.argv[0] == "codex"
    assert first.request.working_directory == tmp_path
    assert first.request.affected_files == (Path("compose.production.yaml"),)
    assert first.request.translator_version == TRANSLATOR_VERSION
    assert first.request.identifier.startswith("candidate-implementation-v1-")
    assert "candidate-fingerprint-v1:aaa" in first.request.argv[-1]
    assert "File: compose.production.yaml" in first.request.argv[-1]
    assert "Service: atlas-agent" in first.request.argv[-1]
    assert "Property: image" in first.request.argv[-1]
    assert "Expected value: atlas-agent:old" in first.request.argv[-1]
    assert "Desired value: atlas-agent:new" in first.request.argv[-1]


def test_translator_returns_not_supported_for_other_intents(tmp_path: Path) -> None:
    candidate_session = session(tmp_path, intent="restart-service")

    decision = CandidateImplementationTranslator().translate(
        session=candidate_session,
        workflow=workflow(candidate_session),
        repository=repository(tmp_path),
        generated_at=NOW,
    )

    assert decision.request is None
    assert decision.failure is not None
    assert decision.failure.code.value == "implementation_not_supported"


def test_translator_rejects_unallowlisted_affected_files(tmp_path: Path) -> None:
    candidate_session = replace(
        session(tmp_path),
        plan=plan(tmp_path, affected_files=(Path("../compose.production.yaml"),)),
    )

    decision = CandidateImplementationTranslator().translate(
        session=candidate_session,
        workflow=workflow(candidate_session),
        repository=repository(tmp_path),
        generated_at=NOW,
    )

    assert decision.request is None
    assert decision.failure is not None
    assert decision.failure.code.value == "unsafe_translation"


def test_translator_rejects_repository_head_drift(tmp_path: Path) -> None:
    candidate_session = session(tmp_path)

    decision = CandidateImplementationTranslator().translate(
        session=candidate_session,
        workflow=workflow(candidate_session),
        repository=repository(tmp_path, head="def456"),
        generated_at=NOW,
    )

    assert decision.request is None
    assert decision.failure is not None
    assert decision.failure.code.value == "repository_stale"


def test_translator_rejects_missing_mutation_before_approval(tmp_path: Path) -> None:
    candidate_session = session(tmp_path)
    candidate_session = replace(
        candidate_session,
        plan=replace(candidate_session.plan, mutation=None),
    )
    decision = CandidateImplementationTranslator().translate(
        session=candidate_session,
        workflow=workflow(candidate_session),
        repository=repository(tmp_path),
        generated_at=NOW,
    )
    assert decision.request is None
    assert decision.failure is not None
    assert decision.failure.code.value == "missing_mutation_specification"
