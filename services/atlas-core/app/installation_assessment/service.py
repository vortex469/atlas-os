"""Internal, ephemeral orchestration for non-authorizing P2 assessments."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.installation_assessment.assessment import assess_installation_admission
from app.installation_assessment.cache import EphemeralAssessmentRetryCache
from app.installation_assessment.contract import (
    InstallationAdmissionAssessmentV1,
    InstallationInterestV1,
)
from app.installation_assessment.fingerprint import (
    _validate_idempotency_key,
    verify_interest_fingerprint,
)
from app.installation_assessment.interest import create_installation_interest
from app.installation_plan.contract import InstallationPlan
from app.installation_targets.contract import InstallationDestinationSelectionV1

ASSESSMENT_ROUTE_SCOPE = "installation-admission-assessment-v1"


def assess_installation_request(
    *,
    plan: InstallationPlan,
    plan_fingerprint: str,
    selection: InstallationDestinationSelectionV1,
    principal_id: str,
    idempotency_key: str,
    requested_at: datetime,
    destination_available: bool,
    destination_identity_available: bool,
    current_destination_fingerprint: str | None,
    retry_cache: EphemeralAssessmentRetryCache,
    interest: InstallationInterestV1 | None = None,
) -> tuple[InstallationAdmissionAssessmentV1, bytes, datetime]:
    """Verify/construct one interest and assess it through ephemeral retry state."""
    _validate_idempotency_key(idempotency_key)
    if (
        requested_at.tzinfo is None
        or requested_at.utcoffset() != timedelta(0)
        or requested_at.microsecond
    ):
        raise ValueError("requested_at must be an exact UTC whole second")
    if principal_id != selection.selected_by:
        raise ValueError("selection is not available to this principal")
    if plan_fingerprint != plan.fingerprint.value:
        raise ValueError("plan_fingerprint must be the exact current plan fingerprint")
    if (
        not destination_available
        and (
            destination_identity_available
            or current_destination_fingerprint is not None
        )
    ) or (
        destination_available
        and destination_identity_available
        != (current_destination_fingerprint is not None)
    ):
        raise ValueError("contradictory destination facts")
    if interest is not None and not verify_interest_fingerprint(
        interest, idempotency_key=idempotency_key
    ):
        raise ValueError("interest fingerprint verification failed")
    if interest is not None and (
        interest.item_id != plan.application.item_id
        or interest.catalog_entry_id != plan.application.catalog_entry_id
    ):
        raise ValueError("interest identifiers must match the installation plan")

    supplied_interest = interest
    canonical_request = b"\x00".join(
        (
            plan_fingerprint.encode("ascii"),
            selection.selection_id.encode("ascii"),
            selection.selected_destination_fingerprint.encode("ascii"),
            str(destination_available).encode("ascii"),
            str(destination_identity_available).encode("ascii"),
            (current_destination_fingerprint or "").encode("ascii"),
            (supplied_interest.interest_fingerprint if supplied_interest else "").encode(
                "ascii"
            ),
        )
    )

    def factory(evaluation_instant: datetime) -> InstallationAdmissionAssessmentV1:
        verified_interest = supplied_interest or create_installation_interest(
            plan=plan,
            plan_fingerprint=plan_fingerprint,
            selection=selection,
            principal_id=principal_id,
            idempotency_key=idempotency_key,
            requested_at=evaluation_instant,
        )
        evaluation_time = evaluation_instant.astimezone(UTC).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        return assess_installation_admission(
            plan=plan,
            plan_fingerprint=plan_fingerprint,
            selection=selection,
            selected_destination_fingerprint=selection.selected_destination_fingerprint,
            destination_available=destination_available,
            destination_identity_available=destination_identity_available,
            current_destination_fingerprint=current_destination_fingerprint,
            interest=verified_interest,
            evaluation_time=evaluation_time,
        )

    return retry_cache.get_or_create(
        principal_id=principal_id,
        route=ASSESSMENT_ROUTE_SCOPE,
        idempotency_key=idempotency_key,
        canonical_request=canonical_request,
        now=requested_at,
        factory=factory,
        maximum_expires_at=(
            datetime.strptime(supplied_interest.expires_at, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=UTC
            )
            if supplied_interest is not None
            else None
        ),
    )
