"""Tests for reusable tool execution policy."""

from pathlib import Path

import pytest

from app.execution import (
    AllowedCommand,
    EnvironmentVariable,
    ExecutionRequest,
    PolicyViolation,
    ToolPolicy,
)
from app.planning.models import ImplementationPlan


def make_request(
    root: Path,
    *,
    identifier: str = "execution-1",
    argv: tuple[str, ...] = ("codex", "implement"),
    working_directory: Path = Path("."),
    timeout_seconds: float | None = None,
    environment: tuple[EnvironmentVariable, ...] = (),
) -> ExecutionRequest:
    plan = ImplementationPlan(
        checkpoint_id="A12.1",
        title="Tool Execution Policy",
        goal="Validate commands before execution.",
        repository_root=root,
        branch="feature/atlas-agent",
        head_commit="d6054cc",
        scope_items=(),
        affected_files=(),
        required_tests=(),
        risks=(),
    )
    return ExecutionRequest(
        identifier=identifier,
        plan=plan,
        argv=argv,
        working_directory=working_directory,
        timeout_seconds=timeout_seconds,
        environment=environment,
    )


def test_allowed_command_is_normalized(tmp_path: Path) -> None:
    decision = ToolPolicy().validate(
        make_request(
            tmp_path,
            identifier=" execution-1 ",
            working_directory=Path("services/atlas-agent"),
            environment=(EnvironmentVariable(" ATLAS_VALUE ", "enabled"),),
        )
    )

    assert isinstance(decision, AllowedCommand)
    assert decision.identifier == "execution-1"
    assert decision.working_directory == (
        tmp_path / "services/atlas-agent"
    ).resolve(strict=False)
    assert decision.environment == (
        EnvironmentVariable("ATLAS_VALUE", "enabled"),
    )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"identifier": " "}, "identifier"),
        ({"argv": ()}, "argv"),
        ({"argv": ("codex", " ")}, "argv item"),
        ({"argv": ("/usr/bin/codex",)}, "absolute path"),
        ({"argv": ("bin/codex",)}, "path components"),
        ({"argv": (r"bin\\codex",)}, "path components"),
        ({"argv": ("pytest",)}, "not allowed"),
        ({"timeout_seconds": 0.0}, "positive"),
        ({"working_directory": Path("../outside")}, "inside the repository"),
    ],
)
def test_policy_returns_violation(
    tmp_path: Path,
    overrides: dict[str, object],
    message: str,
) -> None:
    decision = ToolPolicy().validate(make_request(tmp_path, **overrides))

    assert isinstance(decision, PolicyViolation)
    assert message in decision.message


def test_policy_supports_future_executable_configuration(
    tmp_path: Path,
) -> None:
    decision = ToolPolicy(
        allowed_executables=frozenset({"future-tool"})
    ).validate(make_request(tmp_path, argv=("future-tool", "check")))

    assert isinstance(decision, AllowedCommand)
    assert decision.argv == ("future-tool", "check")


def test_invalid_environment_returns_violation(tmp_path: Path) -> None:
    decision = ToolPolicy().validate(
        make_request(
            tmp_path,
            environment=(EnvironmentVariable("INVALID-NAME", "value"),),
        )
    )

    assert isinstance(decision, PolicyViolation)
    assert decision.message == "Invalid environment variable name: INVALID-NAME"
