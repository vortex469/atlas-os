"""Default-disabled Core service for recording inert execution requests."""

from __future__ import annotations

from pydantic import TypeAdapter, ValidationError

from app.installation_candidate_lifecycle.contract import OwnerId
from app.installation_execution_request.contract import (
    InstallationExecutionRequestCreateV1,
    InstallationExecutionRequestV1,
)
from app.installation_execution_request.store import (
    ExecutionRequestMalformedError,
    ExecutionRequestUnavailableError,
    InstallationExecutionRequestStore,
)


class InstallationExecutionRequestService:
    """Expose only closed record creation and owned immutable reads."""

    def __init__(
        self, *, store: InstallationExecutionRequestStore, enabled: bool = False
    ) -> None:
        self._store = store
        self._enabled = enabled is True

    def record(
        self,
        *,
        operator_id: str,
        idempotency_key: str,
        create: InstallationExecutionRequestCreateV1,
    ) -> InstallationExecutionRequestV1:
        if not self._enabled:
            raise ExecutionRequestUnavailableError()
        try:
            operator = TypeAdapter(OwnerId).validate_python(operator_id, strict=True)
        except (ValidationError, ValueError, TypeError) as error:
            raise ExecutionRequestMalformedError() from error
        request, _created = self._store.create(
            owner_id=operator,
            idempotency_key=idempotency_key,
            create=create,
        )
        return request

    def get(
        self, *, operator_id: str, execution_request_id: str
    ) -> InstallationExecutionRequestV1:
        try:
            operator = TypeAdapter(OwnerId).validate_python(operator_id, strict=True)
        except (ValidationError, ValueError, TypeError) as error:
            raise ExecutionRequestMalformedError() from error
        return self._store.get(
            owner_id=operator, execution_request_id=execution_request_id
        )

    def list_for_operator(
        self, *, operator_id: str
    ) -> tuple[InstallationExecutionRequestV1, ...]:
        try:
            operator = TypeAdapter(OwnerId).validate_python(operator_id, strict=True)
        except (ValidationError, ValueError, TypeError) as error:
            raise ExecutionRequestMalformedError() from error
        return self._store.list_for_operator(operator)

    def state(self, *, operator_id: str, execution_request_id: str) -> str:
        try:
            operator = TypeAdapter(OwnerId).validate_python(operator_id, strict=True)
        except (ValidationError, ValueError, TypeError) as error:
            raise ExecutionRequestMalformedError() from error
        return self._store.state(
            owner_id=operator, execution_request_id=execution_request_id
        )
