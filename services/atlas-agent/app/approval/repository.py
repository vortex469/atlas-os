"""Approval repository for Atlas Agent."""

from __future__ import annotations

from collections.abc import MutableMapping
from threading import RLock

from app.approval.models import (
    ApprovalDecision,
    ApprovalRequest,
    ApprovalResult,
    ApprovalStatus,
)


class ApprovalRepository:
    """Repository for storing approval requests and decisions."""

    def __init__(
        self,
        storage: MutableMapping[str, ApprovalResult] | None = None,
    ) -> None:
        self._storage = storage if storage is not None else {}
        self._lock = RLock()

    def export_snapshot(self) -> dict[str, ApprovalResult]:
        """Return a shallow immutable snapshot of approvals."""

        with self._lock:
            return dict(self._storage)

    def replace_snapshot(
        self,
        snapshot: MutableMapping[str, ApprovalResult],
    ) -> None:
        """Replace current approvals with a validated snapshot."""

        with self._lock:
            self._storage = dict(snapshot)

    def save_request(self, request: ApprovalRequest) -> str:
        """Save a new approval request and return its identifier.

        Args:
            request: The approval request to save.

        Returns:
            The identifier of the saved request.
        """
        identifier = request.identifier
        with self._lock:
            if identifier in self._storage:
                raise ValueError(
                    f"Approval request already exists: {identifier}"
                )
            decision = ApprovalDecision(
                request=request,
                status=ApprovalStatus.PENDING,
            )
            self._storage[identifier] = ApprovalResult(decision=decision)
        return identifier

    def get_request(self, identifier: str) -> ApprovalResult | None:
        """Retrieve an approval request by identifier.

        Args:
            identifier: The identifier of the approval request.

        Returns:
            The approval result or None if not found.
        """
        with self._lock:
            return self._storage.get(identifier)

    def update_decision(self, identifier: str, decision: ApprovalDecision) -> bool:
        """Update an approval decision.

        Args:
            identifier: The identifier of the approval request.
            decision: The approval decision to update.

        Returns:
            True if the update was successful, False otherwise.
        """
        with self._lock:
            current = self._storage.get(identifier)
            if current is None:
                return False
            if current.decision.status is not ApprovalStatus.PENDING:
                return False
            if decision.request != current.decision.request:
                return False

            self._storage[identifier] = ApprovalResult(decision=decision)
            return True

    def get_pending_requests(self) -> list[ApprovalResult]:
        """Get all pending approval requests.

        Returns:
            A list of pending approval results.
        """
        with self._lock:
            return [
                result
                for result in self._storage.values()
                if result.decision.status is ApprovalStatus.PENDING
            ]
