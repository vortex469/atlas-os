"""Repository operation exceptions."""


class RepositoryInspectionError(Exception):
    """Base exception for repository inspection errors."""


class InvalidRepositoryError(RepositoryInspectionError):
    """Raised when a path is not located inside a Git work tree."""


class RepositoryCommitError(Exception):
    """Raised when a repository commit cannot be completed safely."""


class RepositoryCommitValidationError(RepositoryCommitError):
    """Raised when a requested repository commit is unsafe."""
