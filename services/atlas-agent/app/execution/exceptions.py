"""Execution engine exceptions."""


class ExecutionError(Exception):
    """Base exception for execution errors."""


class ExecutionValidationError(ExecutionError):
    """Raised when an execution request is invalid or prohibited."""
