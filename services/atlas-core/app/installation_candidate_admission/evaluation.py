"""Pure fail-closed evaluation of installation candidate admission."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pydantic import ValidationError

from app.installation_candidate_admission.contract import (
    AdmissionReason,
    InstallationCandidateAdmissionV1,
    InstallationCandidateRecordV1,
    fingerprint,
)
from app.installation_capability.assessment import InstallationCapabilityAssessmentV1
from app.installation_plan.contract import InstallationPlan
from app.installation_targets.contract import (
    InstallationDestinationSelectionV1,
    ProspectiveInstallationDestinationV1,
)


def evaluate_installation_candidate_admission(
    *,
    plan: object,
    selection: object,
    current_destination: object,
    capability_assessment: object,
    evaluated_at: datetime,
) -> InstallationCandidateAdmissionV1 | None:
    """Evaluate supplied server-owned read models without I/O or persistence.

    ``None`` is the sanitized no-result outcome when complete trustworthy closed
    inputs cannot be assembled. Structurally present but invalid exact contracts
    produce the closed ``input_invalid`` result where their identity fields remain
    safe to project.
    """
    exact_types = (
        (plan, InstallationPlan),
        (selection, InstallationDestinationSelectionV1),
        (current_destination, ProspectiveInstallationDestinationV1),
        (capability_assessment, InstallationCapabilityAssessmentV1),
    )
    if any(value is None for value, _ in exact_types):
        return None
    if any(type(value) is not expected for value, expected in exact_types):
        return None
    try:
        when = _utc(evaluated_at)
        # Revalidation detects hostile model_copy constructions and corrupted
        # nested contracts without repairing or substituting any input.
        # The three upstream values are already frozen contract instances.
        # Re-running validators would incorrectly reinterpret SkipValidation
        # nesting and is not a repair boundary; exact runtime types are the
        # closed-input proof here.
        assessment_values = capability_assessment.model_dump(mode="python")
        assessment_values.update(
            plan=capability_assessment.plan,
            selection=capability_assessment.selection,
            current_destination=capability_assessment.current_destination,
            provider_facts=capability_assessment.provider_facts,
            comparisons=capability_assessment.comparisons,
        )
        InstallationCapabilityAssessmentV1.model_validate(assessment_values)
    except (AttributeError, TypeError, ValueError, ValidationError):
        return _result(plan, selection, current_destination, capability_assessment,
                       _safe_utc(evaluated_at), ("input_invalid",), None)

    groups: tuple[tuple[AdmissionReason, ...], ...] = (
        (),
        (() if plan.status == "plan_ready_for_review" else
         ("installation_plan_not_review_ready",)),
        _destination_reasons(selection, current_destination, evaluated_at),
        _capability_reasons(
            plan, selection, current_destination, capability_assessment, evaluated_at
        ),
        _authority_reasons(capability_assessment),
    )
    reasons = next((group for group in groups if group), ())
    record = None if reasons else _record(
        plan, selection, current_destination, capability_assessment, when
    )
    return _result(
        plan, selection, current_destination, capability_assessment, when, reasons, record
    )


def _destination_reasons(selection, current, when) -> tuple[AdmissionReason, ...]:
    reasons: list[AdmissionReason] = []
    if selection.status != "active":
        reasons.append("destination_selection_not_active")
    if when < _parse(selection.selected_at) or when >= _parse(selection.expires_at):
        reasons.append("destination_selection_expired")
    identity = (current.provider, current.resource_type, current.placement_kind,
                current.resource_id, current.destination_fingerprint)
    if any(value is None for value in identity):
        reasons.append("destination_identity_unavailable")
    elif identity != (selection.provider, selection.resource_type,
                      selection.placement_kind, selection.resource_id,
                      selection.selected_destination_fingerprint):
        reasons.append("destination_replaced_or_moved")
    return tuple(reasons)


def _capability_reasons(plan, selection, current, assessment, when):
    reasons: list[AdmissionReason] = []
    facts = assessment.provider_facts
    if assessment.evaluated_at != _format(when) or not (
        _parse(facts.observed_at) <= when < _parse(facts.fresh_until)
    ):
        reasons.append("capability_assessment_stale")
    linked = (
        assessment.plan == plan
        and assessment.plan.fingerprint.value == plan.fingerprint.value
        and assessment.selection == selection
        and assessment.current_destination == current
        and facts.destination_fingerprint == current.destination_fingerprint
        and facts.resource_id == current.resource_id
    )
    if not linked:
        reasons.append("capability_assessment_mismatched")
    if assessment.assessment_status != "requirements_satisfied_but_non_authorizing":
        reasons.append("capability_assessment_not_admissible")
    return tuple(reasons)


def _authority_reasons(assessment) -> tuple[AdmissionReason, ...]:
    return ("authority_invariant_violated",) if any((
        assessment.candidate_eligibility_evaluated,
        assessment.candidate_creation_allowed,
        assessment.agent_execution_supported,
        assessment.provider_mutation_allowed,
    )) else ()


def _record(plan, selection, current, assessment, when_string):
    values = {
        "schema": "installation-candidate-record-v1",
        "item_id": plan.application.item_id,
        "catalog_entry_id": plan.application.catalog_entry_id,
        "plan_fingerprint": plan.fingerprint.value,
        "selection_id": selection.selection_id,
        "selected_destination_fingerprint": selection.selected_destination_fingerprint,
        "current_destination_fingerprint": current.destination_fingerprint,
        "capability_assessment_fingerprint": assessment.assessment_fingerprint,
        "provider_fact_set_fingerprint": _provider_fingerprint(assessment),
        "evaluated_at": when_string,
        "valid_until": min(selection.expires_at, assessment.provider_facts.fresh_until),
        "approved": False, "executable": False, "deployable": False,
        "dispatchable": False, "agent_execution_supported": False,
    }
    return InstallationCandidateRecordV1(
        **values,
        record_fingerprint=fingerprint("atlas:installation-candidate-record:v1", values),
    )


def _result(plan, selection, current, assessment, when, reasons, record):
    values = {
        "schema": "installation-candidate-admission-v1",
        "plan_fingerprint": plan.fingerprint.value,
        "selection_fingerprint": selection.selection_fingerprint,
        "selected_destination_fingerprint": selection.selected_destination_fingerprint,
        "current_destination_fingerprint": current.destination_fingerprint,
        "capability_assessment_fingerprint": assessment.assessment_fingerprint,
        "provider_fact_set_fingerprint": _provider_fingerprint(assessment),
        "evaluated_at": when,
        "status": "not_admitted" if reasons else "admitted_but_non_executable",
        "reason_codes": reasons,
        "candidate_record": record.model_dump(mode="json") if record else None,
        "approved": False, "executable": False, "deployable": False,
        "dispatchable": False, "agent_execution_supported": False,
        "candidate_creation_allowed": False,
    }
    return InstallationCandidateAdmissionV1(
        **values,
        admission_fingerprint=fingerprint(
            "atlas:installation-candidate-admission:v1", values
        ),
    )


def _provider_fingerprint(assessment):
    return fingerprint(
        "atlas:provider-installation-capability-facts:v1",
        assessment.provider_facts.model_dump(mode="json"),
    )


def _utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() != timedelta(0) or value.microsecond:
        raise ValueError("whole-second UTC evaluation time required")
    return _format(value.astimezone(UTC))


def _safe_utc(value: object) -> str:
    try:
        return _utc(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, AttributeError):
        return "1970-01-01T00:00:00Z"


def _format(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
