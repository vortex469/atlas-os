"""Frozen P2 fingerprint domains."""

from __future__ import annotations

from app.installation_assessment.contract import (
    InstallationAdmissionAssessmentV1,
    InstallationInterestV1,
)
from app.installation_targets.fingerprint import _canonical_hash

INTEREST_DOMAIN = "atlas:installation-interest:v1"
ASSESSMENT_DOMAIN = "atlas:installation-admission-assessment:v1"


def _validate_idempotency_key(value: str) -> None:
    if (
        not value.isascii()
        or not 16 <= len(value.encode("ascii")) <= 128
        or any(not 0x21 <= ord(character) <= 0x7E for character in value)
    ):
        raise ValueError("invalid canonical client idempotency key")


def build_interest_fingerprint(
    *,
    item_id: str,
    catalog_entry_id: str,
    installation_plan_fingerprint: str,
    selection_id: str,
    selected_destination_fingerprint: str,
    requested_at: str,
    expires_at: str,
    idempotency_key: str,
) -> str:
    _validate_idempotency_key(idempotency_key)
    value = {
        "schema_version": "installation-interest-v1",
        "item_id": item_id,
        "catalog_entry_id": catalog_entry_id,
        "installation_plan_fingerprint": installation_plan_fingerprint,
        "interest_kind": "install-container-assessment",
        "selection_id": selection_id,
        "selected_destination_fingerprint": selected_destination_fingerprint,
        "requested_at": requested_at,
        "expires_at": expires_at,
        "idempotency_key": idempotency_key,
    }
    return _canonical_hash(INTEREST_DOMAIN, value, frozenset(value))


def build_assessment_fingerprint(
    assessment: InstallationAdmissionAssessmentV1, *, evaluation_time: str
) -> str:
    value = {
        "schema_version": assessment.schema_version,
        "item_id": assessment.item_id,
        "catalog_entry_id": assessment.catalog_entry_id,
        "plan_fingerprint": assessment.plan_fingerprint,
        "selection_id": assessment.selection_id,
        "selected_destination_fingerprint": assessment.selected_destination_fingerprint,
        "current_destination_fingerprint": assessment.current_destination_fingerprint,
        "interest_fingerprint": assessment.interest_fingerprint,
        "evaluation_time": evaluation_time,
        "agent_install_container_supported": False,
        "assessment_status": assessment.assessment_status,
        "reason_codes": list(assessment.reason_codes),
        "candidate_eligibility_evaluated": False,
    }
    return _canonical_hash(ASSESSMENT_DOMAIN, value, frozenset(value))


def verify_interest_fingerprint(
    interest: InstallationInterestV1, *, idempotency_key: str
) -> bool:
    return interest.interest_fingerprint == build_interest_fingerprint(
        item_id=interest.item_id,
        catalog_entry_id=interest.catalog_entry_id,
        installation_plan_fingerprint=interest.installation_plan_fingerprint,
        selection_id=interest.selection_id,
        selected_destination_fingerprint=interest.selected_destination_fingerprint,
        requested_at=interest.requested_at,
        expires_at=interest.expires_at,
        idempotency_key=idempotency_key,
    )
