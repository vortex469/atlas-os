"""Tests for deterministic implementation planning."""

import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.context.models import (
    ActionHistoryContext,
    ActionHistoryEntry,
    ActionHistoryFailure,
    AgentContext,
    IntelligenceAssessment,
    IntelligenceContext,
    IntelligenceFailure,
    IntelligenceFinding,
    IntelligenceRecommendation,
    ServiceHealth,
)
from app.planning.engine import PlanningEngine
from app.planning.exceptions import PlanningValidationError
from app.planning.models import PlanRisk, RoadmapCheckpoint
from app.repository.models import RepositorySnapshot


def make_snapshot(
    *,
    is_clean: bool = True,
    branch: str | None = "feature/atlas-agent",
    head_commit: str | None = "abc123",
) -> RepositorySnapshot:
    """Create a repository snapshot without accessing Git."""

    return RepositorySnapshot(
        root=Path("/opt/atlas"),
        branch=branch,
        head_commit=head_commit,
        is_clean=is_clean,
        modified_files=() if is_clean else ("modified.py",),
        staged_files=(),
        untracked_files=(),
    )


def make_checkpoint(**overrides: object) -> RoadmapCheckpoint:
    """Create a valid checkpoint with optional field overrides."""

    values: dict[str, object] = {
        "identifier": "A3",
        "title": "Planning Engine",
        "goal": "Create deterministic implementation plans.",
        "scope_items": ("Add planning models", "Add planning engine"),
        "affected_files": (
            Path("app/planning/models.py"),
            Path("app/planning/engine.py"),
        ),
        "required_tests": ("Run Ruff", "Run pytest"),
        "risks": ("Incorrect checkpoint data",),
    }
    values.update(overrides)
    return RoadmapCheckpoint(**values)  # type: ignore[arg-type]


def make_context(
    services: dict[str, ServiceHealth],
    intelligence: IntelligenceContext | None = None,
) -> AgentContext:
    """Create Atlas context with supplied service health."""

    return AgentContext(
        atlas="atlas",
        assistant="atlas-agent",
        engine="deterministic",
        release="development",
        services=services,
        intelligence=intelligence,
    )


def make_service(
    provider_id: str,
    status: str,
) -> ServiceHealth:
    """Create service health for planning tests."""

    return ServiceHealth(
        provider_id=provider_id,
        status=status,
    )


def make_action_entry(
    entry_id: str,
    *,
    status: str = "failed",
    success: bool = False,
    destructive: bool = False,
    request_id: str | None = None,
) -> ActionHistoryEntry:
    timestamp = datetime(2026, 7, 31, 16, 0, tzinfo=timezone.utc)
    return ActionHistoryEntry(
        identifier=entry_id,
        provider_id="docker",
        provider_name="Docker",
        action_id="restart-container",
        action_label="Restart Container",
        status=status,
        success=success,
        message="Free-form message must not qualify risks.",
        confirmed=True,
        destructive=destructive,
        parameter_names=("container",),
        request_id=request_id,
        started_at=timestamp,
        completed_at=timestamp,
        duration_ms=1.0,
    )


def test_generates_valid_plan() -> None:
    """Explicit checkpoint data becomes a traceable plan."""

    plan = PlanningEngine().plan(make_checkpoint(), make_snapshot())

    assert plan.checkpoint_id == "A3"
    assert plan.title == "Planning Engine"
    assert plan.repository_root == Path("/opt/atlas")
    assert plan.branch == "feature/atlas-agent"
    assert plan.head_commit == "abc123"
    assert plan.affected_files == (
        Path("app/planning/models.py"),
        Path("app/planning/engine.py"),
    )


def test_no_context_preserves_existing_plan() -> None:
    """Omitted context and explicit None produce equal plans."""

    engine = PlanningEngine()
    checkpoint = make_checkpoint()
    snapshot = make_snapshot()

    assert engine.plan(checkpoint, snapshot) == engine.plan(
        checkpoint,
        snapshot,
        context=None,
    )


def test_healthy_services_add_no_risks() -> None:
    """Healthy Atlas services do not add planning risks."""

    context = make_context(
        {
            "atlas-core": make_service("atlas-core", "healthy"),
            "ollama": make_service("ollama", "healthy"),
        }
    )

    plan = PlanningEngine().plan(
        make_checkpoint(risks=()),
        make_snapshot(),
        context=context,
    )

    assert plan.risks == ()


def test_unhealthy_services_add_atlas_core_risks() -> None:
    """Non-healthy services become Atlas Core planning risks."""

    context = make_context(
        {
            "ollama": make_service("ollama", "degraded"),
        }
    )

    plan = PlanningEngine().plan(
        make_checkpoint(risks=()),
        make_snapshot(),
        context=context,
    )

    assert plan.risks == (
        PlanRisk(
            code="atlas-service-unhealthy",
            summary="Atlas service 'ollama' reports status 'degraded'",
            source="atlas-core",
        ),
    )


def test_context_risks_are_ordered_by_service_name() -> None:
    """Context risks are ordered deterministically by service name."""

    context = make_context(
        {
            "zeta": make_service("zeta", "unhealthy"),
            "alpha": make_service("alpha", "degraded"),
            "healthy": make_service("healthy", "healthy"),
        }
    )

    plan = PlanningEngine().plan(
        make_checkpoint(risks=()),
        make_snapshot(),
        context=context,
    )

    assert tuple(risk.summary for risk in plan.risks) == (
        "Atlas service 'alpha' reports status 'degraded'",
        "Atlas service 'zeta' reports status 'unhealthy'",
    )


def test_context_risks_follow_existing_risk_sources() -> None:
    """Context risks use the existing ordered risk pipeline."""

    context = make_context(
        {
            "ollama": make_service("ollama", "unhealthy"),
        }
    )

    plan = PlanningEngine().plan(
        make_checkpoint(risks=("Checkpoint concern",)),
        make_snapshot(is_clean=False),
        context=context,
    )

    assert tuple(risk.source for risk in plan.risks) == (
        "checkpoint",
        "repository",
        "atlas-core",
    )


def test_unavailable_intelligence_adds_one_stable_risk() -> None:
    context = make_context(
        {},
        intelligence=IntelligenceContext(
            failure=IntelligenceFailure(
                code="timeout",
                message="Atlas intelligence request timed out.",
            )
        ),
    )

    plan = PlanningEngine().plan(
        make_checkpoint(risks=()),
        make_snapshot(),
        context=context,
    )

    assert plan.risks == (
        PlanRisk(
            code="atlas-intelligence-unavailable",
            summary="Atlas intelligence request timed out.",
            source="atlas-knowledge",
        ),
    )


def test_legacy_context_adds_no_intelligence_risk() -> None:
    plan = PlanningEngine().plan(
        make_checkpoint(risks=()),
        make_snapshot(),
        context=make_context({}),
    )

    assert plan.risks == ()


def test_intelligence_risks_are_ordered_deduplicated_and_capped() -> None:
    finding_one = IntelligenceFinding(
        identifier="finding-1",
        severity="warning",
        category="reliability",
        source="ace",
        title="Finding one",
        message="Evidence one",
        component="provider-a",
        affects_health=False,
    )
    context = make_context(
        {},
        intelligence=IntelligenceContext(
            findings=(
                IntelligenceFinding(
                    identifier="ignored",
                    severity="info",
                    category="operations",
                    source="ace",
                    title="Informational",
                    message="No action required",
                    affects_health=False,
                ),
                finding_one,
                finding_one.model_copy(
                    update={"title": "Changed free-form title"}
                ),
                IntelligenceFinding(
                    identifier="finding-2",
                    severity="info",
                    category="health",
                    source="ace",
                    title="Health finding",
                    message="Health evidence",
                    affects_health=True,
                ),
            ),
            assessments=(
                IntelligenceAssessment(
                    title="Ignored assessment",
                    priority="low",
                ),
                IntelligenceAssessment(
                    title="High assessment",
                    priority="high",
                ),
            ),
            recommendations=tuple(
                IntelligenceRecommendation(
                    title=f"Recommendation {index}",
                    reason=f"Reason {index}",
                    priority="medium",
                    confidence=0.8,
                    estimated_effort="small",
                )
                for index in range(1, 4)
            ),
        ),
    )

    plan = PlanningEngine().plan(
        make_checkpoint(risks=()),
        make_snapshot(),
        context=context,
    )

    assert tuple(risk.summary for risk in plan.risks) == (
        "Finding one",
        "Health finding",
        "High assessment",
        "Recommendation 1",
        "Recommendation 2",
    )
    assert len(plan.risks) == 5


def test_intelligence_evidence_does_not_change_plan_execution_inputs() -> None:
    checkpoint = make_checkpoint(risks=())
    snapshot = make_snapshot()
    baseline = PlanningEngine().plan(checkpoint, snapshot)
    enriched = PlanningEngine().plan(
        checkpoint,
        snapshot,
        context=make_context(
            {},
            intelligence=IntelligenceContext(
                recommendations=(
                    IntelligenceRecommendation(
                        title="Run an untrusted command",
                        reason="Advisory evidence only",
                        priority="high",
                        confidence=1.0,
                        estimated_effort="small",
                    ),
                )
            ),
        ),
    )

    assert enriched.repository_root == baseline.repository_root
    assert enriched.branch == baseline.branch
    assert enriched.head_commit == baseline.head_commit
    assert enriched.scope_items == baseline.scope_items
    assert enriched.affected_files == baseline.affected_files
    assert enriched.required_tests == baseline.required_tests


def test_failed_action_history_adds_bounded_structured_risks() -> None:
    entries = tuple(
        make_action_entry(f"entry-{index}", request_id=f"request-{index}")
        for index in range(7)
    )
    context = make_context(
        {},
        intelligence=None,
    ).model_copy(
        update={
            "action_history": ActionHistoryContext(entries=entries),
        }
    )

    plan = PlanningEngine().plan(
        make_checkpoint(risks=()),
        make_snapshot(),
        context=context,
    )

    assert len(plan.risks) == 5
    assert {risk.code for risk in plan.risks} == {
        "atlas-action-history-failure"
    }
    assert all("Free-form" not in risk.summary for risk in plan.risks)


def test_successful_destructive_action_history_adds_no_risk() -> None:
    context = make_context(
        {},
        intelligence=None,
    ).model_copy(
        update={
            "action_history": ActionHistoryContext(
                entries=(
                    make_action_entry(
                        "destructive-success",
                        status="succeeded",
                        success=True,
                        destructive=True,
                    ),
                )
            ),
        }
    )

    plan = PlanningEngine().plan(
        make_checkpoint(risks=()),
        make_snapshot(),
        context=context,
    )

    assert plan.risks == ()


def test_action_history_risks_are_deduplicated_by_structured_key() -> None:
    first = make_action_entry("first", request_id="request-1")
    duplicate = first.model_copy(update={"identifier": "second"})
    context = make_context(
        {},
        intelligence=None,
    ).model_copy(
        update={
            "action_history": ActionHistoryContext(
                entries=(first, duplicate),
            ),
        }
    )

    plan = PlanningEngine().plan(
        make_checkpoint(risks=()),
        make_snapshot(),
        context=context,
    )

    assert len(plan.risks) == 1


def test_action_history_failure_adds_one_stable_risk() -> None:
    context = make_context(
        {},
        intelligence=None,
    ).model_copy(
        update={
            "action_history": ActionHistoryContext(
                failure=ActionHistoryFailure(
                    code="timeout",
                    message="Atlas action history request timed out.",
                )
            ),
        }
    )

    plan = PlanningEngine().plan(
        make_checkpoint(risks=()),
        make_snapshot(),
        context=context,
    )

    assert plan.risks == (
        PlanRisk(
            code="atlas-action-history-unavailable",
            summary="Atlas action history request timed out.",
            source="atlas-knowledge",
        ),
    )


def test_normalizes_whitespace_and_duplicates() -> None:
    """Repeated normalized values are removed while order is preserved."""

    checkpoint = make_checkpoint(
        scope_items=(" First ", "Second", "First"),
        affected_files=(Path("one.py"), Path("two.py"), Path("one.py")),
        required_tests=(" pytest ", "ruff", "pytest"),
        risks=(" Risk one ", "Risk two", "Risk one"),
    )

    plan = PlanningEngine().plan(checkpoint, make_snapshot())

    assert plan.scope_items == ("First", "Second")
    assert plan.affected_files == (Path("one.py"), Path("two.py"))
    assert plan.required_tests == ("pytest", "ruff")
    assert tuple(risk.summary for risk in plan.risks) == (
        "Risk one",
        "Risk two",
    )


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("identifier", " "),
        ("title", ""),
        ("goal", "\t"),
    ),
)
def test_rejects_blank_required_fields(
    field_name: str,
    value: str,
) -> None:
    """Required checkpoint text must contain meaningful content."""

    checkpoint = make_checkpoint(**{field_name: value})

    with pytest.raises(PlanningValidationError):
        PlanningEngine().plan(checkpoint, make_snapshot())


def test_rejects_blank_collection_item() -> None:
    """Optional collections cannot contain blank entries."""

    checkpoint = make_checkpoint(scope_items=("valid", " "))

    with pytest.raises(PlanningValidationError):
        PlanningEngine().plan(checkpoint, make_snapshot())


def test_rejects_absolute_affected_path() -> None:
    """Affected files must be repository-relative."""

    checkpoint = make_checkpoint(
        affected_files=(Path("/opt/atlas/file.py"),)
    )

    with pytest.raises(PlanningValidationError, match="repository-relative"):
        PlanningEngine().plan(checkpoint, make_snapshot())


def test_rejects_parent_traversal() -> None:
    """Affected files cannot escape the repository through parent traversal."""

    checkpoint = make_checkpoint(
        affected_files=(Path("../outside.py"),)
    )

    with pytest.raises(PlanningValidationError, match="traverse"):
        PlanningEngine().plan(checkpoint, make_snapshot())


def test_rejects_repository_root_as_affected_file() -> None:
    """The repository root itself is not a valid affected file."""

    checkpoint = make_checkpoint(affected_files=(Path("."),))

    with pytest.raises(PlanningValidationError, match="file path"):
        PlanningEngine().plan(checkpoint, make_snapshot())


def test_adds_dirty_working_tree_risk() -> None:
    """A dirty snapshot adds a repository-derived risk."""

    plan = PlanningEngine().plan(
        make_checkpoint(risks=()),
        make_snapshot(is_clean=False),
    )

    assert PlanRisk(
        code="dirty-working-tree",
        summary="Repository contains staged, modified, or untracked files",
        source="repository",
    ) in plan.risks


def test_adds_detached_head_risk() -> None:
    """Detached HEAD state adds a repository-derived risk."""

    plan = PlanningEngine().plan(
        make_checkpoint(risks=()),
        make_snapshot(branch=None),
    )

    assert any(risk.code == "detached-head" for risk in plan.risks)


def test_adds_missing_head_risk() -> None:
    """A repository without a commit adds a repository-derived risk."""

    plan = PlanningEngine().plan(
        make_checkpoint(risks=()),
        make_snapshot(head_commit=None),
    )

    assert any(risk.code == "missing-head" for risk in plan.risks)


def test_preserves_explicit_risk_before_repository_risks() -> None:
    """Checkpoint risks remain traceable and retain their input order."""

    plan = PlanningEngine().plan(
        make_checkpoint(risks=("Explicit risk",)),
        make_snapshot(is_clean=False),
    )

    assert plan.risks[0] == PlanRisk(
        code="checkpoint-risk",
        summary="Explicit risk",
        source="checkpoint",
    )
    assert plan.risks[1].source == "repository"


def test_identical_inputs_produce_equal_plans() -> None:
    """Planning is deterministic for identical immutable inputs."""

    checkpoint = make_checkpoint()
    snapshot = make_snapshot()
    engine = PlanningEngine()

    assert engine.plan(checkpoint, snapshot) == engine.plan(
        checkpoint,
        snapshot,
    )


def test_planner_does_not_execute_git_or_access_filesystem(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Planning uses supplied values without external inspection."""

    def fail_subprocess(
        *args: object,
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        raise AssertionError("Planning must not execute subprocesses")

    def fail_exists(self: Path) -> bool:
        raise AssertionError("Planning must not inspect the filesystem")

    monkeypatch.setattr(subprocess, "run", fail_subprocess)
    monkeypatch.setattr(Path, "exists", fail_exists)

    plan = PlanningEngine().plan(make_checkpoint(), make_snapshot())

    assert plan.checkpoint_id == "A3"
