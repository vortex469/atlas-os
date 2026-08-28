"""Default-disabled Core service for preserving inert dispatch handoffs."""

from __future__ import annotations

from pydantic import TypeAdapter, ValidationError

from app.installation_candidate_lifecycle.contract import OwnerId
from app.installation_dispatch_handoff.contract import (
    InstallationDispatchEnvelopeV1,
    InstallationDispatchHandoffCreateV1,
)
from app.installation_dispatch_handoff.store import (
    InstallationDispatchHandoffStore,
    InstallationDispatchMalformedError,
    InstallationDispatchUnavailableError,
)


class InstallationDispatchHandoffService:
    """Expose only closed preparation and owned immutable reads."""

    def __init__(
        self, *, store: InstallationDispatchHandoffStore, enabled: bool = False
    ) -> None:
        self._store = store
        self._enabled = enabled is True

    @staticmethod
    def _operator(operator_id: str) -> str:
        try:
            return TypeAdapter(OwnerId).validate_python(operator_id, strict=True)
        except (ValidationError, ValueError, TypeError) as error:
            raise InstallationDispatchMalformedError() from error

    def prepare(
        self,
        *,
        operator_id: str,
        idempotency_key: str,
        create: InstallationDispatchHandoffCreateV1,
    ) -> InstallationDispatchEnvelopeV1:
        if not self._enabled:
            raise InstallationDispatchUnavailableError()
        envelope, _created = self._store.create(
            owner_id=self._operator(operator_id),
            idempotency_key=idempotency_key,
            create=create,
        )
        return envelope

    def get(
        self, *, operator_id: str, dispatch_envelope_id: str
    ) -> InstallationDispatchEnvelopeV1:
        return self._store.get(
            owner_id=self._operator(operator_id),
            dispatch_envelope_id=dispatch_envelope_id,
        )

    def list_for_operator(
        self, *, operator_id: str
    ) -> tuple[InstallationDispatchEnvelopeV1, ...]:
        return self._store.list_for_operator(self._operator(operator_id))

    def state(self, *, operator_id: str, dispatch_envelope_id: str) -> str:
        return self._store.state(
            owner_id=self._operator(operator_id),
            dispatch_envelope_id=dispatch_envelope_id,
        )
