"""Tests for deterministic candidate-aware planners."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.candidate_planning.models import CandidatePlanningContext
from app.candidate_planning.planner import (
    RepositoryResolver,
    UpdateComposeStackCandidatePlanner,
)
from app.repository.models import RepositorySnapshot

NOW = datetime(2026, 8, 2, tzinfo=UTC)


def context(repository: Path) -> CandidatePlanningContext:
    return CandidatePlanningContext(
        session_id="candidate-plan-session",
        candidate_id="candidate-1",
        candidate_fingerprint="candidate-fingerprint-v1:aaa",
        source_recommendation_id="finding-1",
        source_subsystem="orion",
        recommendation_class="update_compose_stack",
        catalog_item_id="frigate",
        target_id="atlas-compose",
        target_type="repository",
        execution_category="update",
        execution_intent="update-compose-stack",
        rationale="Update compose stack.",
        constraints=("requires-current-evidence",),
        evidence_ids=("evidence-1",),
        compatibility_assessment_id="assessment-1",
        compatibility_status="compatible",
        relationship_ids=("relationship-1",),
        repository_root=repository,
        repository_branch="feature/atlas-agent",
        repository_head="abc123",
        planning_timestamp=NOW,
        revalidated_candidate_fingerprint="candidate-fingerprint-v1:aaa",
    )


def snapshot(repository: Path) -> RepositorySnapshot:
    return RepositorySnapshot(
        root=repository,
        branch="feature/atlas-agent",
        head_commit="abc123",
        is_clean=True,
        modified_files=(),
        staged_files=(),
        untracked_files=(),
    )


def test_repository_resolver_uses_only_configured_repository(tmp_path: Path) -> None:
    resolver = RepositoryResolver(repository_root=tmp_path)

    assert resolver.resolve(target_id="atlas-compose", target_type="repository") == tmp_path
    assert resolver.resolve(target_id="other", target_type="repository") is None
    assert resolver.resolve(target_id="atlas-compose", target_type="container") is None


def test_update_compose_stack_plan_is_deterministic_and_descriptive(tmp_path: Path) -> None:
    planner = UpdateComposeStackCandidatePlanner()

    first = planner.create_plan(context=context(tmp_path), snapshot=snapshot(tmp_path))
    second = planner.create_plan(context=context(tmp_path), snapshot=snapshot(tmp_path))

    assert first == second
    assert first.candidate_id == "candidate-1"
    assert first.candidate_fingerprint == "candidate-fingerprint-v1:aaa"
    assert first.repository_branch == "feature/atlas-agent"
    assert Path("compose.production.yaml") in first.likely_affected_files
    assert first.evidence_ids == ("evidence-1",)


def test_update_compose_stack_plan_contains_no_executable_commands(tmp_path: Path) -> None:
    plan = UpdateComposeStackCandidatePlanner().create_plan(
        context=context(tmp_path),
        snapshot=snapshot(tmp_path),
    )

    rendered = "\n".join(
        (
            plan.title,
            plan.objective,
            *plan.proposed_steps,
            *plan.verification_strategy,
            *plan.rollback_considerations,
        )
    ).lower()
    assert "docker compose" not in rendered
    assert "docker-compose" not in rendered
    assert "sudo" not in rendered
    assert "$" not in rendered


def test_plan_model_is_immutable(tmp_path: Path) -> None:
    plan = UpdateComposeStackCandidatePlanner().create_plan(
        context=context(tmp_path),
        snapshot=snapshot(tmp_path),
    )

    with pytest.raises(FrozenInstanceError):
        plan.title = "changed"  # type: ignore[misc]
