"""Tests for the Atlas Agent verification engine."""

from collections.abc import Iterator, Mapping
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.context.models import AgentContext
from app.execution import EnvironmentVariable, RunnerOutcome
from app.verification import (
    VerificationCheck,
    VerificationEngine,
    VerificationStatus,
    VerificationValidationError,
)


def make_check(
    *,
    identifier: str = "ruff",
    argv: tuple[str, ...] = (
        "python",
        "-m",
        "ruff",
        "check",
        "app",
        "tests",
    ),
    working_directory: Path = Path("."),
    timeout_seconds: float | None = None,
    environment: tuple[EnvironmentVariable, ...] = (),
) -> VerificationCheck:
    return VerificationCheck(
        identifier=identifier,
        argv=argv,
        working_directory=working_directory,
        timeout_seconds=timeout_seconds,
        environment=environment,
    )


def clock(values: tuple[float, ...]) -> Iterator[float]:
    return iter(values)


def test_successful_suite_returns_passed_report(
    tmp_path: Path,
) -> None:
    runner = Mock()
    runner.run.return_value = RunnerOutcome(
        return_code=0,
        stdout="ok",
        stderr="",
    )
    values = clock((10.0, 11.0, 12.0, 12.5))

    report = VerificationEngine(
        runner,
        lambda: next(values),
    ).verify(
        repository_root=tmp_path,
        checks=(make_check(),),
    )

    assert report.status is VerificationStatus.PASSED
    assert report.repository_root == tmp_path.resolve(strict=False)
    assert report.duration_seconds == 2.5
    assert len(report.results) == 1
    assert report.results[0].status is VerificationStatus.PASSED
    assert report.results[0].duration_seconds == 1.0
    assert report.results[0].stdout == "ok"


def test_report_retains_context_snapshot(tmp_path: Path) -> None:
    context = AgentContext(
        atlas="online",
        assistant="Atlas",
        engine="Hermes",
        release="test",
        services={},
    )
    runner = Mock()
    runner.run.return_value = RunnerOutcome(0, "", "")

    report = VerificationEngine(runner).verify(
        repository_root=tmp_path,
        checks=(make_check(),),
        context=context,
    )

    assert report.context is context


def test_nonzero_exit_returns_failed_result(
    tmp_path: Path,
) -> None:
    runner = Mock()
    runner.run.return_value = RunnerOutcome(
        return_code=1,
        stdout="",
        stderr="failure",
    )

    report = VerificationEngine(runner).verify(
        repository_root=tmp_path,
        checks=(make_check(),),
    )

    assert report.status is VerificationStatus.FAILED
    assert report.results[0].status is VerificationStatus.FAILED
    assert report.results[0].return_code == 1


def test_timeout_returns_timed_out_result(
    tmp_path: Path,
) -> None:
    runner = Mock()
    runner.run.return_value = RunnerOutcome(
        return_code=None,
        stdout="partial",
        stderr="timeout",
        timed_out=True,
    )

    report = VerificationEngine(runner).verify(
        repository_root=tmp_path,
        checks=(make_check(),),
    )

    assert report.status is VerificationStatus.TIMED_OUT
    assert report.results[0].status is VerificationStatus.TIMED_OUT
    assert report.results[0].error == "Verification check timed out"


def test_launch_failure_returns_launch_failed_result(
    tmp_path: Path,
) -> None:
    runner = Mock()
    runner.run.return_value = RunnerOutcome(
        return_code=None,
        stdout="",
        stderr="",
        launch_error="not found",
    )

    report = VerificationEngine(runner).verify(
        repository_root=tmp_path,
        checks=(make_check(),),
    )

    assert report.status is VerificationStatus.LAUNCH_FAILED
    assert report.results[0].status is VerificationStatus.LAUNCH_FAILED
    assert report.results[0].error == "not found"


def test_all_checks_run_in_declared_order(
    tmp_path: Path,
) -> None:
    runner = Mock()
    runner.run.side_effect = (
        RunnerOutcome(0, "ruff", ""),
        RunnerOutcome(0, "pytest", ""),
        RunnerOutcome(0, "npm", ""),
    )

    report = VerificationEngine(runner).verify(
        repository_root=tmp_path,
        checks=(
            make_check(identifier="ruff"),
            make_check(
                identifier="pytest",
                argv=("python", "-m", "pytest"),
            ),
            make_check(
                identifier="npm-test",
                argv=("npm", "test"),
            ),
        ),
    )

    assert tuple(result.identifier for result in report.results) == (
        "ruff",
        "pytest",
        "npm-test",
    )
    assert tuple(result.stdout for result in report.results) == (
        "ruff",
        "pytest",
        "npm",
    )
    assert runner.run.call_count == 3


def test_report_status_uses_deterministic_precedence(
    tmp_path: Path,
) -> None:
    runner = Mock()
    runner.run.side_effect = (
        RunnerOutcome(1, "", "failed"),
        RunnerOutcome(None, "", "", timed_out=True),
        RunnerOutcome(None, "", "", launch_error="missing"),
    )

    report = VerificationEngine(runner).verify(
        repository_root=tmp_path,
        checks=(
            make_check(identifier="failed"),
            make_check(identifier="timeout"),
            make_check(identifier="launch"),
        ),
    )

    assert report.status is VerificationStatus.LAUNCH_FAILED


def test_empty_suite_is_rejected(tmp_path: Path) -> None:
    runner = Mock()

    with pytest.raises(
        VerificationValidationError,
        match="at least one check",
    ):
        VerificationEngine(runner).verify(
            repository_root=tmp_path,
            checks=(),
        )

    runner.run.assert_not_called()


@pytest.mark.parametrize("identifier", ["", " ", "\t"])
def test_blank_identifier_is_rejected(
    tmp_path: Path,
    identifier: str,
) -> None:
    runner = Mock()

    with pytest.raises(VerificationValidationError):
        VerificationEngine(runner).verify(
            repository_root=tmp_path,
            checks=(make_check(identifier=identifier),),
        )

    runner.run.assert_not_called()


def test_duplicate_identifier_is_rejected(
    tmp_path: Path,
) -> None:
    runner = Mock()

    with pytest.raises(
        VerificationValidationError,
        match="Duplicate",
    ):
        VerificationEngine(runner).verify(
            repository_root=tmp_path,
            checks=(
                make_check(identifier="test"),
                make_check(identifier="test"),
            ),
        )

    runner.run.assert_not_called()


def test_empty_argv_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(VerificationValidationError):
        VerificationEngine(Mock()).verify(
            repository_root=tmp_path,
            checks=(make_check(argv=()),),
        )


@pytest.mark.parametrize(
    "argv",
    [
        ("python", ""),
        ("python", " "),
        ("python", "\t"),
    ],
)
def test_blank_argv_item_is_rejected(
    tmp_path: Path,
    argv: tuple[str, ...],
) -> None:
    with pytest.raises(VerificationValidationError):
        VerificationEngine(Mock()).verify(
            repository_root=tmp_path,
            checks=(make_check(argv=argv),),
        )


@pytest.mark.parametrize(
    "argv",
    [
        ("/usr/bin/python",),
        ("./python",),
        ("bin/python",),
        (r"bin\python",),
    ],
)
def test_executable_paths_are_rejected(
    tmp_path: Path,
    argv: tuple[str, ...],
) -> None:
    with pytest.raises(VerificationValidationError):
        VerificationEngine(Mock()).verify(
            repository_root=tmp_path,
            checks=(make_check(argv=argv),),
        )


@pytest.mark.parametrize("timeout", [0.0, -1.0])
def test_nonpositive_timeout_is_rejected(
    tmp_path: Path,
    timeout: float,
) -> None:
    with pytest.raises(VerificationValidationError):
        VerificationEngine(Mock()).verify(
            repository_root=tmp_path,
            checks=(make_check(timeout_seconds=timeout),),
        )


def test_relative_working_directory_is_normalized(
    tmp_path: Path,
) -> None:
    runner = Mock()
    runner.run.return_value = RunnerOutcome(0, "", "")

    report = VerificationEngine(runner).verify(
        repository_root=tmp_path,
        checks=(
            make_check(
                working_directory=Path("services/atlas-agent"),
            ),
        ),
    )

    expected = (tmp_path / "services/atlas-agent").resolve(strict=False)

    assert report.results[0].working_directory == expected
    assert runner.run.call_args.kwargs["cwd"] == expected


def test_absolute_descendant_working_directory_is_allowed(
    tmp_path: Path,
) -> None:
    runner = Mock()
    runner.run.return_value = RunnerOutcome(0, "", "")
    descendant = tmp_path / "services"

    report = VerificationEngine(runner).verify(
        repository_root=tmp_path,
        checks=(make_check(working_directory=descendant),),
    )

    assert report.results[0].working_directory == descendant.resolve(strict=False)


def test_outside_working_directory_is_rejected(
    tmp_path: Path,
) -> None:
    runner = Mock()

    with pytest.raises(VerificationValidationError):
        VerificationEngine(runner).verify(
            repository_root=tmp_path,
            checks=(
                make_check(
                    working_directory=Path("../outside"),
                ),
            ),
        )

    runner.run.assert_not_called()


def test_environment_is_merged_with_process_environment(
    tmp_path: Path,
) -> None:
    runner = Mock()
    runner.run.return_value = RunnerOutcome(0, "", "")

    VerificationEngine(runner).verify(
        repository_root=tmp_path,
        checks=(
            make_check(
                environment=(
                    EnvironmentVariable(
                        "ATLAS_VERIFY_MODE",
                        "enabled",
                    ),
                ),
            ),
        ),
    )

    environment: Mapping[str, str] = runner.run.call_args.kwargs["environment"]

    assert environment["ATLAS_VERIFY_MODE"] == "enabled"
    assert "PATH" in environment


def test_blank_environment_value_is_allowed(
    tmp_path: Path,
) -> None:
    runner = Mock()
    runner.run.return_value = RunnerOutcome(0, "", "")

    VerificationEngine(runner).verify(
        repository_root=tmp_path,
        checks=(
            make_check(
                environment=(EnvironmentVariable("EMPTY_VALUE", ""),),
            ),
        ),
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
    with pytest.raises(VerificationValidationError):
        VerificationEngine(Mock()).verify(
            repository_root=tmp_path,
            checks=(
                make_check(
                    environment=(EnvironmentVariable(name, "value"),),
                ),
            ),
        )


def test_duplicate_environment_name_is_rejected(
    tmp_path: Path,
) -> None:
    with pytest.raises(VerificationValidationError):
        VerificationEngine(Mock()).verify(
            repository_root=tmp_path,
            checks=(
                make_check(
                    environment=(
                        EnvironmentVariable("DUPLICATE", "one"),
                        EnvironmentVariable("DUPLICATE", "two"),
                    ),
                ),
            ),
        )


def test_check_timeout_is_forwarded_to_runner(
    tmp_path: Path,
) -> None:
    runner = Mock()
    runner.run.return_value = RunnerOutcome(0, "", "")

    VerificationEngine(runner).verify(
        repository_root=tmp_path,
        checks=(make_check(timeout_seconds=30.0),),
    )

    assert runner.run.call_args.kwargs["timeout_seconds"] == 30.0


def test_negative_clock_deltas_are_clamped(
    tmp_path: Path,
) -> None:
    runner = Mock()
    runner.run.return_value = RunnerOutcome(0, "", "")
    values = clock((30.0, 20.0, 10.0, 0.0))

    report = VerificationEngine(
        runner,
        lambda: next(values),
    ).verify(
        repository_root=tmp_path,
        checks=(make_check(),),
    )

    assert report.results[0].duration_seconds == 0.0
    assert report.duration_seconds == 0.0
