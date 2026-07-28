"""Repository inspection exceptions."""


class RepositoryInspectionError(Exception):
    """Base exception for repository inspection errors."""


class InvalidRepositoryError(RepositoryInspectionError):
    """Raised when a path is not located inside a Git work tree."""
