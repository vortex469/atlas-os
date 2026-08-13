"""Reusable policy validation for subprocess commands."""

import re
from pathlib import Path

from app.execution.models import (
    AllowedCommand,
    EnvironmentVariable,
    ExecutionRequest,
    PolicyViolation,
)

_ENVIRONMENT_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_DEFAULT_ALLOWED_EXECUTABLES = frozenset({"codex"})


class ToolPolicy:
    """Normalize commands and reject operations outside configured boundaries."""

    def __init__(
        self,
        allowed_executables: frozenset[str] = _DEFAULT_ALLOWED_EXECUTABLES,
    ) -> None:
        self._allowed_executables = allowed_executables

    def validate(
        self,
        request: ExecutionRequest,
    ) -> AllowedCommand | PolicyViolation:
        """Return a normalized command or a policy violation."""

        identifier = request.identifier.strip()
        if not identifier:
            return PolicyViolation(
                message="Execution request identifier must not be blank"
            )

        if not request.argv:
            return PolicyViolation(message="Execution argv must not be empty")

        for index, argument in enumerate(request.argv):
            if not argument.strip():
                return PolicyViolation(
                    message=f"Execution argv item {index} must not be blank"
                )

        executable = request.argv[0]
        executable_path = Path(executable)
        if executable_path.is_absolute():
            return PolicyViolation(
                message="Execution executable must not be an absolute path"
            )
        if (
            executable_path.name != executable
            or "/" in executable
            or "\\" in executable
        ):
            return PolicyViolation(
                message="Execution executable must not contain path components"
            )
        if executable not in self._allowed_executables:
            return PolicyViolation(
                message=f"Execution executable is not allowed: {executable}"
            )

        if request.timeout_seconds is not None and request.timeout_seconds <= 0:
            return PolicyViolation(message="Execution timeout must be positive")

        repository_root = request.plan.repository_root.resolve(strict=False)
        if request.working_directory.is_absolute():
            working_directory = request.working_directory.resolve(strict=False)
        else:
            working_directory = (
                repository_root / request.working_directory
            ).resolve(strict=False)

        if not working_directory.is_relative_to(repository_root):
            return PolicyViolation(
                message="Execution working directory must be inside the repository"
            )

        environment = self._normalize_environment(request.environment)
        if isinstance(environment, PolicyViolation):
            return environment

        return AllowedCommand(
            identifier=identifier,
            plan=request.plan,
            argv=request.argv,
            working_directory=working_directory,
            timeout_seconds=request.timeout_seconds,
            environment=environment,
        )

    @staticmethod
    def _normalize_environment(
        variables: tuple[EnvironmentVariable, ...],
    ) -> tuple[EnvironmentVariable, ...] | PolicyViolation:
        normalized: list[EnvironmentVariable] = []
        names: set[str] = set()

        for variable in variables:
            name = variable.name.strip()
            if not name:
                return PolicyViolation(
                    message="Environment variable name must not be blank"
                )
            if _ENVIRONMENT_NAME.fullmatch(name) is None:
                return PolicyViolation(
                    message=f"Invalid environment variable name: {name}"
                )
            if name in names:
                return PolicyViolation(
                    message=f"Duplicate environment variable name: {name}"
                )

            names.add(name)
            normalized.append(
                EnvironmentVariable(name=name, value=variable.value)
            )

        return tuple(normalized)
