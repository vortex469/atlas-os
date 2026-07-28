"""Tests for deterministic implementation planning."""

import subprocess
from pathlib import Path

import pytest

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
