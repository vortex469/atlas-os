"""Tests for the Atlas Agent execution engine."""

import subprocess
from collections.abc import Iterator, Mapping
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.execution import (
    EnvironmentVariable,
    ExecutionEngine,
    ExecutionRequest,
    ExecutionStatus,
    ExecutionValidationError,
    RunnerOutcome,
    SubprocessRunner,
)
from app.planning.models import ImplementationPlan


def make_plan(root: Path) -> ImplementationPlan:
    return ImplementationPlan(
        checkpoint_id="A4",
        title="Execution Engine",
        goal="Execute approved implementation plans.",
        repository_root=root,
        branch="feature/atlas-agent",
        head_commit="9decfe9",
        scope_items=(),
        affected_files=(),
        required_tests=(),
        risks=(),
    )


def make_request(
    root: Path,
    *,
    identifier: str = "execution-1",
    argv: tuple[str, ...] = ("codex", "implement"),
    working_directory: Path = Path("."),
    timeout_seconds: float | None = None,
    environment: tuple[EnvironmentVariable, ...] = (),
) -> ExecutionRequest:
    return ExecutionRequest(
        identifier=identifier,
        plan=make_plan(root),
        argv=argv,
        working_directory=working_directory,
        timeout_seconds=timeout_seconds,
        environment=environment,
    )


def clock(values: tuple[float, ...]) -> Iterator[float]:
    return iter(values)


def test_success_result(tmp_path: Path) -> None:
    runner = Mock()
    runner.run.return_value = RunnerOutcome(0, "out", "err")
    values = clock((10.0, 12.5))

    result = ExecutionEngine(runner, lambda: next(values)).execute(
        make_request(tmp_path)
    )

    assert result.status is ExecutionStatus.SUCCEEDED
    assert result.return_code == 0
    assert result.stdout == "out"
    assert result.stderr == "err"
    assert result.duration_seconds == 2.5


def test_nonzero_result_is_failure(tmp_path: Path) -> None:
    runner = Mock()
    runner.run.return_value = RunnerOutcome(2, "", "failed")

    result = ExecutionEngine(runner).execute(make_request(tmp_path))

    assert result.status is ExecutionStatus.FAILED
    assert result.return_code == 2
    assert result.error is None


def test_timeout_result_preserves_output(tmp_path: Path) -> None:
    runner = Mock()
    runner.run.return_value = RunnerOutcome(
        return_code=None,
        stdout="partial out",
        stderr="partial err",
        timed_out=True,
    )

    result = ExecutionEngine(runner).execute(make_request(tmp_path))

    assert result.status is ExecutionStatus.TIMED_OUT
    assert result.stdout == "partial out"
    assert result.stderr == "partial err"
    assert result.error == "Execution timed out"


def test_launch_failure_result(tmp_path: Path) -> None:
    runner = Mock()
    runner.run.return_value = RunnerOutcome(
        return_code=None,
        stdout="",
        stderr="",
        launch_error="codex not found",
    )

    result = ExecutionEngine(runner).execute(make_request(tmp_path))

    assert result.status is ExecutionStatus.LAUNCH_FAILED
    assert result.error == "codex not found"


def test_result_preserves_plan_traceability(tmp_path: Path) -> None:
    runner = Mock()
    runner.run.return_value = RunnerOutcome(0, "", "")

    result = ExecutionEngine(runner).execute(
        make_request(tmp_path, identifier="request-42")
    )

    assert result.request_id == "request-42"
    assert result.checkpoint_id == "A4"


@pytest.mark.parametrize("identifier", ["", " ", "\t"])
def test_blank_identifier_is_rejected(
    tmp_path: Path,
    identifier: str,
) -> None:
    runner = Mock()

    with pytest.raises(ExecutionValidationError):
        ExecutionEngine(runner).execute(make_request(tmp_path, identifier=identifier))

    runner.run.assert_not_called()


def test_empty_argv_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ExecutionValidationError):
        ExecutionEngine(Mock()).execute(make_request(tmp_path, argv=()))


@pytest.mark.parametrize(
    "argv",
    [
        ("codex", ""),
        ("codex", " "),
        ("codex", "\t"),
    ],
)
def test_blank_argv_item_is_rejected(
    tmp_path: Path,
    argv: tuple[str, ...],
) -> None:
    with pytest.raises(ExecutionValidationError):
        ExecutionEngine(Mock()).execute(make_request(tmp_path, argv=argv))


@pytest.mark.parametrize(
    "argv",
    [
        ("pytest",),
        ("git", "status"),
        ("python", "-m", "pytest"),
    ],
)
def test_non_codex_executable_is_rejected(
    tmp_path: Path,
    argv: tuple[str, ...],
) -> None:
    with pytest.raises(ExecutionValidationError):
        ExecutionEngine(Mock()).execute(make_request(tmp_path, argv=argv))


@pytest.mark.parametrize(
    "executable",
    [
        "/usr/bin/codex",
        "./codex",
        "bin/codex",
        r"bin\codex",
    ],
)
def test_executable_paths_are_rejected(
    tmp_path: Path,
    executable: str,
) -> None:
    with pytest.raises(ExecutionValidationError):
        ExecutionEngine(Mock()).execute(make_request(tmp_path, argv=(executable,)))


@pytest.mark.parametrize("timeout", [0.0, -1.0])
def test_nonpositive_timeout_is_rejected(
    tmp_path: Path,
    timeout: float,
) -> None:
    with pytest.raises(ExecutionValidationError):
        ExecutionEngine(Mock()).execute(make_request(tmp_path, timeout_seconds=timeout))


def test_relative_working_directory_is_normalized(
    tmp_path: Path,
) -> None:
    runner = Mock()
    runner.run.return_value = RunnerOutcome(0, "", "")

    result = ExecutionEngine(runner).execute(
        make_request(
            tmp_path,
            working_directory=Path("services/atlas-agent"),
        )
    )

    assert result.working_directory == (tmp_path / "services/atlas-agent").resolve(
        strict=False
    )


def test_absolute_descendant_working_directory_is_allowed(
    tmp_path: Path,
) -> None:
    runner = Mock()
    runner.run.return_value = RunnerOutcome(0, "", "")
    descendant = tmp_path / "services"

    result = ExecutionEngine(runner).execute(
        make_request(tmp_path, working_directory=descendant)
    )

    assert result.working_directory == descendant.resolve(strict=False)


def test_outside_working_directory_is_rejected(
    tmp_path: Path,
) -> None:
    runner = Mock()

    with pytest.raises(ExecutionValidationError):
        ExecutionEngine(runner).execute(
            make_request(
                tmp_path,
                working_directory=Path("../outside"),
            )
        )

    runner.run.assert_not_called()


def test_environment_is_merged(tmp_path: Path) -> None:
    runner = Mock()
    runner.run.return_value = RunnerOutcome(0, "", "")

    ExecutionEngine(runner).execute(
        make_request(
            tmp_path,
            environment=(EnvironmentVariable("ATLAS_TEST_VALUE", "enabled"),),
        )
    )

    environment: Mapping[str, str] = runner.run.call_args.kwargs["environment"]
    assert environment["ATLAS_TEST_VALUE"] == "enabled"
    assert "PATH" in environment


def test_blank_environment_value_is_allowed(tmp_path: Path) -> None:
    runner = Mock()
    runner.run.return_value = RunnerOutcome(0, "", "")

    ExecutionEngine(runner).execute(
        make_request(
            tmp_path,
            environment=(EnvironmentVariable("EMPTY_VALUE", ""),),
        )
    )

    environment = runner.run.call_args.kwargs["environment"]
    assert environment["EMPTY_VALUE"] == ""


@pytest.mark.parametrize(
    "name",
    ["", " ", "1INVALID", "INVALID-NAME", "INVALID.NAME"],
)
def test_invalid_environment_name_is_rejected(
    tmp_path: Path,
    name: str,
) -> None:
    with pytest.raises(ExecutionValidationError):
        ExecutionEngine(Mock()).execute(
            make_request(
                tmp_path,
                environment=(EnvironmentVariable(name, "value"),),
            )
        )


def test_duplicate_environment_name_is_rejected(
    tmp_path: Path,
) -> None:
    with pytest.raises(ExecutionValidationError):
        ExecutionEngine(Mock()).execute(
            make_request(
                tmp_path,
                environment=(
                    EnvironmentVariable("DUPLICATE", "one"),
                    EnvironmentVariable("DUPLICATE", "two"),
                ),
            )
        )


def test_runner_is_called_exactly_once(tmp_path: Path) -> None:
    runner = Mock()
    runner.run.return_value = RunnerOutcome(0, "", "")

    ExecutionEngine(runner).execute(make_request(tmp_path))

    runner.run.assert_called_once()


def test_negative_clock_delta_is_clamped(tmp_path: Path) -> None:
    runner = Mock()
    runner.run.return_value = RunnerOutcome(0, "", "")
    values = clock((20.0, 10.0))

    result = ExecutionEngine(runner, lambda: next(values)).execute(
        make_request(tmp_path)
    )

    assert result.duration_seconds == 0.0


def test_subprocess_runner_uses_safe_options(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    run = Mock(
        return_value=subprocess.CompletedProcess(
            args=("codex",),
            returncode=0,
            stdout="out",
            stderr="err",
        )
    )
    monkeypatch.setattr(subprocess, "run", run)

    SubprocessRunner().run(
        argv=("codex",),
        cwd=tmp_path,
        environment={"PATH": "/bin"},
        timeout_seconds=10.0,
    )

    assert run.call_args.kwargs["shell"] is False
    assert run.call_args.kwargs["text"] is True
    assert run.call_args.kwargs["capture_output"] is True
    assert run.call_args.kwargs["check"] is False


def test_subprocess_runner_handles_timeout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    error = subprocess.TimeoutExpired(
        cmd=("codex",),
        timeout=1.0,
        output=b"partial",
        stderr=b"timeout error",
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        Mock(side_effect=error),
    )

    outcome = SubprocessRunner().run(
        argv=("codex",),
        cwd=tmp_path,
        environment={},
        timeout_seconds=1.0,
    )

    assert outcome.timed_out is True
    assert outcome.stdout == "partial"
    assert outcome.stderr == "timeout error"


def test_subprocess_runner_handles_launch_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        Mock(side_effect=OSError("not found")),
    )

    outcome = SubprocessRunner().run(
        argv=("codex",),
        cwd=tmp_path,
        environment={},
        timeout_seconds=None,
    )

    assert outcome.launch_error == "not found"
    assert outcome.return_code is None
