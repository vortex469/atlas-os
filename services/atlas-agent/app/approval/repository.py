"""Approval repository for Atlas Agent."""

from __future__ import annotations

from collections.abc import MutableMapping
from dataclasses import dataclass

from app.approval.models import ApprovalDecision, ApprovalRequest, ApprovalResult


@dataclass(frozen=True, slots=True)
class ApprovalRepository:
    """Repository for storing approval requests and decisions."""

    # In-memory storage - this is temporary until persistence is implemented
    _storage: MutableMapping[str, ApprovalResult] = None

    def __post_init__(self) -> None:
        """Initialize the repository with empty storage if needed."""
        if self._storage is None:
            object.__setattr__(self, "_storage", {})

    def save_request(self, request: ApprovalRequest) -> str:
        """Save a new approval request and return its identifier.

        Args:
            request: The approval request to save.

        Returns:
            The identifier of the saved request.
        """
        # In a real implementation this would be persisted to storage
        identifier = request.identifier
        decision = ApprovalDecision(
            request=request,
            status="pending"
        )
        result = ApprovalResult(decision=decision)
        self._storage[identifier] = result
        return identifier

    def get_request(self, identifier: str) -> ApprovalResult | None:
        """Retrieve an approval request by identifier.

        Args:
            identifier: The identifier of the approval request.

        Returns:
            The approval result or None if not found.
        """
        return self._storage.get(identifier)

    def update_decision(self, identifier: str, decision: ApprovalDecision) -> bool:
        """Update an approval decision.

        Args:
            identifier: The identifier of the approval request.
            decision: The approval decision to update.

        Returns:
            True if the update was successful, False otherwise.
        """
        if identifier not in self._storage:
            return False

        result = ApprovalResult(decision=decision)
        self._storage[identifier] = result
        return True

    def get_pending_requests(self) -> list[ApprovalResult]:
        """Get all pending approval requests.

        Returns:
            A list of pending approval results.
        """
        pending = []
        for result in self._storage.values():
            if result.decision.status == "pending":
                pending.append(result)
        return pending
