"""Verification engine exceptions."""


class VerificationError(Exception):
    """Base exception for verification errors."""


class VerificationValidationError(VerificationError):
    """Raised when a verification request is invalid."""
