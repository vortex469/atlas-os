"""Backend-independent execution facade."""

from __future__ import annotations

import time
from collections.abc import Callable

from app.execution.backends import (
    ExecutionBackend,
    LocalExecutionBackend,
    WorkerExecutionContext,
)
from app.execution.models import ExecutionRequest, ExecutionResult
from app.execution.policy import ToolPolicy
from app.execution.runner import CommandRunner, SubprocessRunner


class ExecutionEngine:
    """Stable facade delegating approved requests to a configured backend."""

    def __init__(
        self,
        runner: CommandRunner | None = None,
        clock: Callable[[], float] = time.monotonic,
        policy: ToolPolicy | None = None,
        backend: ExecutionBackend | None = None,
    ) -> None:
        if backend is not None and runner is not None:
            raise ValueError("Provide runner or backend, not both")
        self._backend = backend or LocalExecutionBackend(
            runner=runner if runner is not None else SubprocessRunner(),
            clock=clock,
            policy=policy,
        )

    def execute(
        self,
        request: ExecutionRequest,
        *,
        context: WorkerExecutionContext | None = None,
    ) -> ExecutionResult:
        """Execute through the selected backend without changing request semantics."""

        return self._backend.execute(request, context=context)

    @property
    def uses_worker(self) -> bool:
        return bool(getattr(self._backend, "uses_worker", False))

    @property
    def repository_token(self) -> str:
        return str(getattr(self._backend, "repository_token", ""))
