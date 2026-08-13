"""Approval exceptions for Atlas Agent."""

class ApprovalError(Exception):
    """Base exception for approval errors."""


class ApprovalValidationError(ApprovalError):
    """Raised when an approval decision is invalid."""
