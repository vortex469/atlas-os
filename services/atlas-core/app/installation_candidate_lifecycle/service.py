"""Server-owned preservation service for inert installation candidates."""

from __future__ import annotations

from typing import Protocol

from pydantic import TypeAdapter

from app.installation_candidate_admission.contract import (
    InstallationCandidateAdmissionV1,
)
from app.installation_candidate_lifecycle.contract import (
    InstallationCandidateRecordEnvelopeV1,
    LifecycleState,
    OwnerId,
)
from app.installation_candidate_lifecycle.store import (
    InstallationCandidateRecordStore,
)


class AdmissionAssembler(Protocol):
    """The reviewed v0.19 read-side boundary used for re-admission."""

    async def assemble(
        self, *, item_id: str, selection_id: str, principal_id: str
    ) -> InstallationCandidateAdmissionV1: ...


class InstallationCandidateLifecycleService:
    """Resolve current facts and preserve only an operator-owned admission."""

    def __init__(
        self,
        *,
        store: InstallationCandidateRecordStore,
        admissions: AdmissionAssembler,
    ) -> None:
        self._store = store
        self._admissions = admissions

    async def preserve(
        self,
        *,
        owner_id: str,
        item_id: str,
        selection_id: str,
        idempotency_key: str,
    ) -> InstallationCandidateRecordEnvelopeV1:
        """Recompute, validate, and atomically preserve the current admission."""
        owner = TypeAdapter(OwnerId).validate_python(owner_id, strict=True)
        admission = await self._admissions.assemble(
            item_id=item_id,
            selection_id=selection_id,
            principal_id=owner,
        )
        envelope, _created = self._store.preserve(
            owner_id=owner,
            idempotency_key=idempotency_key,
            admission=admission,
        )
        return envelope

    def get(
        self, *, owner_id: str, candidate_record_id: str
    ) -> InstallationCandidateRecordEnvelopeV1:
        return self._store.get(
            owner_id=owner_id, candidate_record_id=candidate_record_id
        )

    def list_for_operator(
        self, *, owner_id: str
    ) -> tuple[InstallationCandidateRecordEnvelopeV1, ...]:
        return self._store.list_for_operator(owner_id)

    def state(self, *, owner_id: str, candidate_record_id: str) -> LifecycleState:
        return self._store.state(
            owner_id=owner_id, candidate_record_id=candidate_record_id
        )

    def delete(self, *, owner_id: str, candidate_record_id: str) -> None:
        self._store.delete(
            owner_id=owner_id, candidate_record_id=candidate_record_id
        )
