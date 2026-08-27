"""Pure deterministic P2 admission assessment."""

from __future__ import annotations

from datetime import UTC, datetime

from app.installation_assessment.contract import (
    REASON_ORDER,
    AssessmentReason,
    InstallationAdmissionAssessmentV1,
    InstallationInterestV1,
)
from app.installation_assessment.fingerprint import build_assessment_fingerprint
from app.installation_plan.contract import InstallationPlan
from app.installation_targets.contract import InstallationDestinationSelectionV1

_PLAN_REASONS: dict[str, AssessmentReason] = {
    "conflicted": "installation_plan_conflicted",
    "missing_deployment_artifact": "installation_plan_missing_deployment_artifact",
    "incompatible": "installation_plan_incompatible",
    "stale_evidence": "installation_plan_stale_evidence",
    "insufficient_information": "installation_plan_insufficient_information",
}


def _parse_time(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def assess_installation_admission(
    *,
    plan: InstallationPlan,
    plan_fingerprint: str,
    selection: InstallationDestinationSelectionV1 | None,
    selected_destination_fingerprint: str | None,
    destination_available: bool,
    destination_identity_available: bool,
    current_destination_fingerprint: str | None,
    interest: InstallationInterestV1 | None,
    evaluation_time: str,
) -> InstallationAdmissionAssessmentV1:
    """Assess only supplied read facts; perform no acquisition or side effects.

    A supplied interest is trusted only after the internal service boundary has
    verified its fingerprint against the current client idempotency key.
    """
    now = _parse_time(evaluation_time)
    if plan_fingerprint != plan.fingerprint.value:
        raise ValueError("plan_fingerprint must be the exact current plan fingerprint")
    if (selection is None) != (selected_destination_fingerprint is None):
        raise ValueError("contradictory destination facts")
    if (
        selection is not None
        and selected_destination_fingerprint
        != selection.selected_destination_fingerprint
    ):
        raise ValueError("selected destination fingerprint must match selection")
    if selection is None and (
        destination_available
        or destination_identity_available
        or current_destination_fingerprint is not None
    ):
        raise ValueError("contradictory destination facts")
    if not destination_available and (
        destination_identity_available or current_destination_fingerprint is not None
    ):
        raise ValueError("contradictory destination facts")
    if destination_available and (
        destination_identity_available
        != (current_destination_fingerprint is not None)
    ):
        raise ValueError("contradictory destination facts")
    if interest is not None and (
        interest.item_id != plan.application.item_id
        or interest.catalog_entry_id != plan.application.catalog_entry_id
    ):
        raise ValueError("interest identifiers must match the installation plan")
    reasons: set[AssessmentReason] = {"agent_install_container_unsupported"}
    plan_reason = _PLAN_REASONS.get(plan.status)
    if plan_reason is not None:
        reasons.add(plan_reason)

    if selection is None:
        reasons.add("destination_selection_missing")
    else:
        if selection.status == "expired" or now >= _parse_time(selection.expires_at):
            reasons.add("destination_selection_expired")
        if selection.status in {"cancelled", "stale"} or not destination_available:
            reasons.add("destination_unavailable")
        if destination_available and not destination_identity_available:
            reasons.add("destination_identity_unavailable")
        if (
            selection.status == "stale"
            or (
                destination_identity_available
                and current_destination_fingerprint is not None
                and current_destination_fingerprint
                != selection.selected_destination_fingerprint
            )
        ):
            reasons.add("destination_replaced_or_moved")
        if (
            selection.status == "active"
            and now < _parse_time(selection.expires_at)
            and destination_available
            and destination_identity_available
            and current_destination_fingerprint
            == selection.selected_destination_fingerprint
        ):
            reasons.add("destination_installation_capability_unknown")

    if interest is None:
        reasons.add("installation_interest_missing")
    else:
        if now >= _parse_time(interest.expires_at):
            reasons.add("installation_interest_expired")
        if interest.installation_plan_fingerprint != plan_fingerprint:
            reasons.add("installation_interest_plan_stale")
        if (
            selection is None
            or interest.selection_id != selection.selection_id
            or interest.selected_destination_fingerprint
            != selected_destination_fingerprint
        ):
            reasons.add("installation_interest_destination_stale")

    ordered = tuple(reason for reason in REASON_ORDER if reason in reasons)
    unsupported = (
        "destination_installation_capability_unknown",
        "agent_install_container_unsupported",
    )
    status = (
        "preconditions_satisfied_but_unsupported"
        if plan.status == "plan_ready_for_review" and ordered == unsupported
        else "blocked"
    )
    base = InstallationAdmissionAssessmentV1(
        item_id=plan.application.item_id,
        catalog_entry_id=plan.application.catalog_entry_id,
        plan_fingerprint=plan_fingerprint,
        selection_id=selection.selection_id if selection else None,
        selected_destination_fingerprint=selected_destination_fingerprint,
        current_destination_fingerprint=current_destination_fingerprint,
        interest_fingerprint=interest.interest_fingerprint if interest else None,
        assessment_status=status,
        reason_codes=ordered,
        assessment_fingerprint="0" * 64,
    )
    return InstallationAdmissionAssessmentV1.model_validate(
        {
            **base.model_dump(),
            "assessment_fingerprint": build_assessment_fingerprint(
                base, evaluation_time=evaluation_time
            ),
        }
    )
