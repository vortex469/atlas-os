"""Deterministic implementation verification."""

import os
import re
import time
from collections.abc import Callable
from pathlib import Path

from app.execution.models import EnvironmentVariable, RunnerOutcome
from app.execution.runner import CommandRunner
from app.verification.exceptions import VerificationValidationError
from app.verification.models import (
    VerificationCheck,
    VerificationCheckResult,
    VerificationReport,
    VerificationStatus,
)

_ENVIRONMENT_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


class VerificationEngine:
    """Run an ordered suite of repository verification checks."""

    def __init__(
        self,
        runner: CommandRunner,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._runner = runner
        self._clock = clock

    def verify(
        self,
        *,
        repository_root: Path,
        checks: tuple[VerificationCheck, ...],
    ) -> VerificationReport:
        """Run all checks and return an immutable structured report."""

        normalized_root = Path(repository_root).resolve(strict=False)
        normalized_checks = self._normalize_checks(
            repository_root=normalized_root,
            checks=checks,
        )

        started_at = self._clock()
        results = tuple(self._run_check(check) for check in normalized_checks)
        duration = max(0.0, self._clock() - started_at)

        return VerificationReport(
            repository_root=normalized_root,
            results=results,
            status=self._report_status(results),
            duration_seconds=duration,
        )

    def _run_check(
        self,
        check: VerificationCheck,
    ) -> VerificationCheckResult:
        environment = dict(os.environ)

        for variable in check.environment:
            environment[variable.name] = variable.value

        started_at = self._clock()

        outcome = self._runner.run(
            argv=check.argv,
            cwd=check.working_directory,
            environment=environment,
            timeout_seconds=check.timeout_seconds,
        )

        duration = max(0.0, self._clock() - started_at)
        status, error = self._check_status(outcome)

        return VerificationCheckResult(
            identifier=check.identifier,
            argv=check.argv,
            working_directory=check.working_directory,
            status=status,
            return_code=outcome.return_code,
            stdout=outcome.stdout,
            stderr=outcome.stderr,
            duration_seconds=duration,
            error=error,
        )

    def _normalize_checks(
        self,
        *,
        repository_root: Path,
        checks: tuple[VerificationCheck, ...],
    ) -> tuple[VerificationCheck, ...]:
        if not checks:
            raise VerificationValidationError(
                "Verification suite must contain at least one check"
            )

        normalized: list[VerificationCheck] = []
        identifiers: set[str] = set()

        for check in checks:
            identifier = check.identifier.strip()

            if not identifier:
                raise VerificationValidationError(
                    "Verification check identifier must not be blank"
                )

            if identifier in identifiers:
                raise VerificationValidationError(
                    f"Duplicate verification check identifier: {identifier}"
                )

            identifiers.add(identifier)

            if not check.argv:
                raise VerificationValidationError(
                    f"Verification check '{identifier}' argv must not be empty"
                )

            for index, argument in enumerate(check.argv):
                if not argument.strip():
                    raise VerificationValidationError(
                        f"Verification check '{identifier}' argv item "
                        f"{index} must not be blank"
                    )

            executable = check.argv[0]

            if Path(executable).is_absolute():
                raise VerificationValidationError(
                    f"Verification check '{identifier}' executable "
                    "must not be an absolute path"
                )

            if (
                Path(executable).name != executable
                or "/" in executable
                or "\\" in executable
            ):
                raise VerificationValidationError(
                    f"Verification check '{identifier}' executable "
                    "must not contain path components"
                )

            if check.timeout_seconds is not None and check.timeout_seconds <= 0:
                raise VerificationValidationError(
                    f"Verification check '{identifier}' timeout must be positive"
                )

            if check.working_directory.is_absolute():
                working_directory = check.working_directory.resolve(strict=False)
            else:
                working_directory = (repository_root / check.working_directory).resolve(
                    strict=False
                )

            if not working_directory.is_relative_to(repository_root):
                raise VerificationValidationError(
                    f"Verification check '{identifier}' working directory "
                    "must be inside the repository"
                )

            environment = self._normalize_environment(
                identifier=identifier,
                variables=check.environment,
            )

            normalized.append(
                VerificationCheck(
                    identifier=identifier,
                    argv=check.argv,
                    working_directory=working_directory,
                    timeout_seconds=check.timeout_seconds,
                    environment=environment,
                )
            )

        return tuple(normalized)

    @staticmethod
    def _normalize_environment(
        *,
        identifier: str,
        variables: tuple[EnvironmentVariable, ...],
    ) -> tuple[EnvironmentVariable, ...]:
        normalized: list[EnvironmentVariable] = []
        names: set[str] = set()

        for variable in variables:
            name = variable.name.strip()

            if not name:
                raise VerificationValidationError(
                    f"Verification check '{identifier}' environment "
                    "variable name must not be blank"
                )

            if _ENVIRONMENT_NAME.fullmatch(name) is None:
                raise VerificationValidationError(
                    f"Verification check '{identifier}' has invalid "
                    f"environment variable name: {name}"
                )

            if name in names:
                raise VerificationValidationError(
                    f"Verification check '{identifier}' has duplicate "
                    f"environment variable name: {name}"
                )

            names.add(name)
            normalized.append(
                EnvironmentVariable(
                    name=name,
                    value=variable.value,
                )
            )

        return tuple(normalized)

    @staticmethod
    def _check_status(
        outcome: RunnerOutcome,
    ) -> tuple[VerificationStatus, str | None]:
        if outcome.launch_error is not None:
            return VerificationStatus.LAUNCH_FAILED, outcome.launch_error

        if outcome.timed_out:
            return VerificationStatus.TIMED_OUT, "Verification check timed out"

        if outcome.return_code == 0:
            return VerificationStatus.PASSED, None

        return VerificationStatus.FAILED, None

    @staticmethod
    def _report_status(
        results: tuple[VerificationCheckResult, ...],
    ) -> VerificationStatus:
        statuses = {result.status for result in results}

        if VerificationStatus.LAUNCH_FAILED in statuses:
            return VerificationStatus.LAUNCH_FAILED

        if VerificationStatus.TIMED_OUT in statuses:
            return VerificationStatus.TIMED_OUT

        if VerificationStatus.FAILED in statuses:
            return VerificationStatus.FAILED

        return VerificationStatus.PASSED
