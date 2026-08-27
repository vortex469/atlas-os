"""Operator-scoped immutable destination selection lifecycle."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from pydantic import TypeAdapter

from app.installation_targets.contract import (
    InstallationDestinationSelectionV1,
    PrincipalId,
    ProspectiveInstallationDestinationV1,
)
from app.installation_targets.fingerprint import (
    build_request_digest,
    build_selection_fingerprint,
)
from app.installation_targets.resolver import (
    TargetResolver,
    resolve_destination,
    resolve_destination_identity,
)
from app.installation_targets.store import (
    InstallationDestinationSelectionStore,
    SelectionIdempotencyConflictError,
)

_IDEMPOTENCY = re.compile(r"[\x21-\x7e]{16,128}")


class SelectionClockError(RuntimeError):
    pass


class SelectionDestinationStaleError(RuntimeError):
    pass


def utc_server_clock() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _instant(clock: Callable[[], datetime]) -> tuple[datetime, str]:
    try:
        value = clock()
        if (
            value.tzinfo is None
            or value.utcoffset() != timedelta(0)
            or value.microsecond
        ):
            raise ValueError
        return value, value.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception as error:
        raise SelectionClockError("selection clock unavailable") from error


class InstallationDestinationSelectionService:
    def __init__(
        self,
        *,
        store: InstallationDestinationSelectionStore,
        resolver: TargetResolver,
        clock: Callable[[], datetime] = utc_server_clock,
        uuid_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._store = store
        self._resolver = resolver
        self._clock = clock
        self._uuid_factory = uuid_factory

    async def enumerate_one(
        self, resource_id: str
    ) -> ProspectiveInstallationDestinationV1:
        return await resolve_destination(resource_id, resolver=self._resolver)

    async def create(
        self,
        *,
        selected_by: str,
        destination: ProspectiveInstallationDestinationV1,
        idempotency_key: str,
    ) -> InstallationDestinationSelectionV1:
        if not _IDEMPOTENCY.fullmatch(idempotency_key) or not idempotency_key.isascii():
            raise ValueError("invalid idempotency key")
        selected_by = TypeAdapter(PrincipalId).validate_python(selected_by, strict=True)
        request_digest = build_request_digest(
            selected_by=selected_by,
            enumeration_token=destination.enumeration_token,
            resource_id=destination.resource_id,
            destination_fingerprint=destination.destination_fingerprint,
            idempotency_key=idempotency_key,
        )
        replay = self._store.get_by_idempotency(
            selected_by=selected_by, idempotency_key=idempotency_key
        )
        if replay is not None:
            if replay.record.request_digest != request_digest:
                raise SelectionIdempotencyConflictError(
                    "idempotency identity conflicts"
                )
            return await self.get(
                selection_id=replay.record.selection_id, selected_by=selected_by
            )
        current = await self.enumerate_one(destination.resource_id)
        if current != destination:
            raise SelectionDestinationStaleError("enumerated destination is stale")
        selected, selected_at = _instant(self._clock)
        expires_at = (selected + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            selection_id = self._uuid_factory()
            if type(selection_id) is not UUID or selection_id.version != 4:
                raise ValueError
        except Exception as error:
            raise ValueError("selection UUID factory failed closed") from error
        base = InstallationDestinationSelectionV1(
            selection_id=str(selection_id),
            resource_id=destination.resource_id,
            selected_destination_fingerprint=destination.destination_fingerprint,
            selected_at=selected_at,
            expires_at=expires_at,
            selected_by=selected_by,
            request_digest=request_digest,
            selection_fingerprint="0" * 64,
            status="active",
            terminated_at=None,
        )
        record = InstallationDestinationSelectionV1.model_validate(
            {
                **base.model_dump(),
                "selection_fingerprint": build_selection_fingerprint(base),
            }
        )
        return self._store.create(
            record=record,
            idempotency_key=idempotency_key,
            evaluation_time=selected_at,
        )[0].record

    async def get(
        self, *, selection_id: str, selected_by: str
    ) -> InstallationDestinationSelectionV1:
        now, instant = _instant(self._clock)
        stored = self._store.get(selection_id, selected_by)
        record = stored.record
        if record.status != "active":
            return record
        expires = datetime.strptime(record.expires_at, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=UTC
        )
        if now >= expires:
            return self._store.transition(
                selection_id=selection_id,
                selected_by=selected_by,
                status="expired",
                terminated_at=instant,
            ).record
        current_fingerprint = await resolve_destination_identity(
            record.resource_id, resolver=self._resolver
        )
        if current_fingerprint != record.selected_destination_fingerprint:
            return self._store.transition(
                selection_id=selection_id,
                selected_by=selected_by,
                status="stale",
                terminated_at=instant,
            ).record
        return record

    def cancel(
        self, *, selection_id: str, selected_by: str
    ) -> InstallationDestinationSelectionV1:
        _, instant = _instant(self._clock)
        stored = self._store.get(selection_id, selected_by)
        if stored.record.status != "active":
            return stored.record
        expires = datetime.strptime(
            stored.record.expires_at, "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=UTC)
        now = datetime.strptime(instant, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        status = "expired" if now >= expires else "cancelled"
        return self._store.transition(
            selection_id=selection_id,
            selected_by=selected_by,
            status=status,
            terminated_at=instant,
        ).record
