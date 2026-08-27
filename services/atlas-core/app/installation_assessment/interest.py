"""Service-layer construction of operator-compatible ephemeral interest."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from app.installation_assessment.contract import InstallationInterestV1
from app.installation_assessment.fingerprint import build_interest_fingerprint
from app.installation_plan.contract import InstallationPlan
from app.installation_targets.contract import InstallationDestinationSelectionV1

_IDEMPOTENCY = re.compile(r"[\x21-\x7e]{16,128}")


def create_installation_interest(
    *,
    plan: InstallationPlan,
    plan_fingerprint: str,
    selection: InstallationDestinationSelectionV1,
    principal_id: str,
    idempotency_key: str,
    requested_at: datetime,
) -> InstallationInterestV1:
    if principal_id != selection.selected_by:
        raise ValueError("selection is not available to this principal")
    if plan_fingerprint != plan.fingerprint.value:
        raise ValueError("plan_fingerprint must be the exact current plan fingerprint")
    if not idempotency_key.isascii() or not _IDEMPOTENCY.fullmatch(idempotency_key):
        raise ValueError("invalid idempotency key")
    if (
        requested_at.tzinfo is None
        or requested_at.utcoffset() != timedelta(0)
        or requested_at.microsecond
    ):
        raise ValueError("requested_at must be an exact UTC whole second")
    requested = requested_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    expires = (requested_at + timedelta(minutes=5)).astimezone(UTC).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    fingerprint = build_interest_fingerprint(
        item_id=plan.application.item_id,
        catalog_entry_id=plan.application.catalog_entry_id,
        installation_plan_fingerprint=plan_fingerprint,
        selection_id=selection.selection_id,
        selected_destination_fingerprint=selection.selected_destination_fingerprint,
        requested_at=requested,
        expires_at=expires,
        idempotency_key=idempotency_key,
    )
    return InstallationInterestV1(
        item_id=plan.application.item_id,
        catalog_entry_id=plan.application.catalog_entry_id,
        installation_plan_fingerprint=plan_fingerprint,
        selection_id=selection.selection_id,
        selected_destination_fingerprint=selection.selected_destination_fingerprint,
        requested_at=requested,
        expires_at=expires,
        interest_fingerprint=fingerprint,
    )
