"""Review engine exceptions."""


class ReviewError(Exception):
    """Base exception for review errors."""


class ReviewValidationError(ReviewError):
    """Raised when review input is invalid."""
