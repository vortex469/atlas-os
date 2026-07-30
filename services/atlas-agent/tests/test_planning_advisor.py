"""Tests for model-assisted planning analysis."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from app.model_providers.models import ModelResponse
from app.planning.advisor import PlanningAdvisor
from app.planning.models import ImplementationPlan, PlanRisk


def make_plan(
    *,
    branch: str | None = "feature/atlas-agent",
    head_commit: str | None = "abc123",
    scope_items: tuple[str, ...] = (
        "Add planning advisor",
        "Add focused tests",
    ),
    affected_files: tuple[Path, ...] = (
        Path("app/planning/advisor.py"),
        Path("tests/test_planning_advisor.py"),
    ),
    required_tests: tuple[str, ...] = (
        "Run Ruff",
        "Run pytest",
    ),
    risks: tuple[PlanRisk, ...] = (
        PlanRisk(
            code="scope-expansion",
            summary="Model analysis could exceed approved scope",
            source="checkpoint",
        ),
    ),
) -> ImplementationPlan:
    """Create a deterministic implementation plan."""

    return ImplementationPlan(
        checkpoint_id="A13.5",
        title="Model-Assisted Plan Analysis",
        goal="Analyze deterministic plans with the configured local model.",
        repository_root=Path("/opt/atlas"),
        branch=branch,
        head_commit=head_commit,
        scope_items=scope_items,
        affected_files=affected_files,
        required_tests=required_tests,
        risks=risks,
    )


def test_analyze_sends_complete_plan_to_model_service() -> None:
    """The generated prompt contains every relevant plan field."""

    response = ModelResponse(
        text="Analysis complete",
        model="test-model",
        provider_id="test-provider",
    )
    model_service = Mock()
    model_service.generate.return_value = response

    result = PlanningAdvisor(model_service=model_service).analyze(make_plan())

    model_service.generate.assert_called_once()
    prompt = model_service.generate.call_args.kwargs["prompt"]

    assert "Checkpoint: A13.5" in prompt
    assert "Title: Model-Assisted Plan Analysis" in prompt
    assert (
        "Goal: Analyze deterministic plans with the configured local model."
        in prompt
    )
    assert "Repository root: /opt/atlas" in prompt
    assert "Branch: feature/atlas-agent" in prompt
    assert "HEAD commit: abc123" in prompt
    assert "- Add planning advisor" in prompt
    assert "- Add focused tests" in prompt
    assert "- app/planning/advisor.py" in prompt
    assert "- tests/test_planning_advisor.py" in prompt
    assert "- Run Ruff" in prompt
    assert "- Run pytest" in prompt
    assert (
        "- [checkpoint] scope-expansion: "
        "Model analysis could exceed approved scope"
        in prompt
    )
    assert "Do not modify files" in prompt
    assert result is response


def test_analyze_returns_model_response_unchanged() -> None:
    """The advisor returns the exact normalized provider response."""

    response = ModelResponse(
        text="Keep the change small.",
        model="local-model",
        provider_id="ollama",
    )
    model_service = Mock()
    model_service.generate.return_value = response

    result = PlanningAdvisor(model_service=model_service).analyze(make_plan())

    assert result is response


def test_empty_plan_collections_are_formatted_deterministically() -> None:
    """Empty plan sections use an explicit stable representation."""

    model_service = Mock()
    model_service.generate.return_value = ModelResponse(
        text="No additions",
        model="test-model",
        provider_id="test-provider",
    )
    plan = make_plan(
        scope_items=(),
        affected_files=(),
        required_tests=(),
        risks=(),
    )

    PlanningAdvisor(model_service=model_service).analyze(plan)

    prompt = model_service.generate.call_args.kwargs["prompt"]

    assert prompt.count("- None") == 4


def test_missing_repository_identity_is_described_explicitly() -> None:
    """Detached or uncommitted repository state remains understandable."""

    model_service = Mock()
    model_service.generate.return_value = ModelResponse(
        text="Repository warning",
        model="test-model",
        provider_id="test-provider",
    )

    PlanningAdvisor(model_service=model_service).analyze(
        make_plan(branch=None, head_commit=None)
    )

    prompt = model_service.generate.call_args.kwargs["prompt"]

    assert "Branch: detached HEAD" in prompt
    assert "HEAD commit: no HEAD commit" in prompt


def test_model_service_exception_propagates() -> None:
    """Model failures are not hidden or converted by the advisor."""

    model_service = Mock()
    model_service.generate.side_effect = RuntimeError("model unavailable")

    with pytest.raises(RuntimeError, match="model unavailable"):
        PlanningAdvisor(model_service=model_service).analyze(make_plan())
