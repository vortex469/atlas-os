"""Server-owned service for recording non-authorizing approval evidence."""

from __future__ import annotations

from pydantic import TypeAdapter

from app.installation_approval_intent.contract import InstallationApprovalIntentV1
from app.installation_approval_intent.store import InstallationApprovalIntentStore
from app.installation_candidate_lifecycle.contract import OwnerId


class InstallationApprovalIntentService:
    """Expose only operator-scoped creation and immutable evidence reads."""

    def __init__(self, *, store: InstallationApprovalIntentStore) -> None:
        self._store = store

    def record(
        self,
        *,
        operator_id: str,
        candidate_record_id: str,
        idempotency_key: str,
    ) -> InstallationApprovalIntentV1:
        """Record the fixed statement for one current, owned candidate."""
        operator = TypeAdapter(OwnerId).validate_python(operator_id, strict=True)
        intent, _created = self._store.create(
            operator_id=operator,
            candidate_record_id=candidate_record_id,
            idempotency_key=idempotency_key,
        )
        return intent

    def get(
        self, *, operator_id: str, approval_intent_id: str
    ) -> InstallationApprovalIntentV1:
        operator = TypeAdapter(OwnerId).validate_python(operator_id, strict=True)
        return self._store.get(
            operator_id=operator, approval_intent_id=approval_intent_id
        )

    def list_for_operator(
        self, *, operator_id: str
    ) -> tuple[InstallationApprovalIntentV1, ...]:
        operator = TypeAdapter(OwnerId).validate_python(operator_id, strict=True)
        return self._store.list_for_operator(operator)
