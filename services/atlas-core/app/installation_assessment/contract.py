"""Closed immutable P2 interest and assessment contracts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from app.installation_plan.contract import Id64, LowerHex64, UtcSecond
from app.installation_targets.contract import CanonicalUuid4

INTEREST_LIFETIME = timedelta(minutes=5)
INTEREST_SCHEMA_VERSION = "installation-interest-v1"
ASSESSMENT_SCHEMA_VERSION = "installation-admission-assessment-v1"


AssessmentReason = Literal[
    "installation_plan_conflicted",
    "installation_plan_missing_deployment_artifact",
    "installation_plan_incompatible",
    "installation_plan_stale_evidence",
    "installation_plan_insufficient_information",
    "destination_selection_missing",
    "destination_selection_expired",
    "destination_unavailable",
    "destination_identity_unavailable",
    "destination_replaced_or_moved",
    "destination_installation_capability_unknown",
    "installation_interest_missing",
    "installation_interest_expired",
    "installation_interest_plan_stale",
    "installation_interest_destination_stale",
    "agent_install_container_unsupported",
]

REASON_ORDER: tuple[AssessmentReason, ...] = (
    "installation_plan_conflicted",
    "installation_plan_missing_deployment_artifact",
    "installation_plan_incompatible",
    "installation_plan_stale_evidence",
    "installation_plan_insufficient_information",
    "destination_selection_missing",
    "destination_selection_expired",
    "destination_unavailable",
    "destination_identity_unavailable",
    "destination_replaced_or_moved",
    "destination_installation_capability_unknown",
    "installation_interest_missing",
    "installation_interest_expired",
    "installation_interest_plan_stale",
    "installation_interest_destination_stale",
    "agent_install_container_unsupported",
)


class AssessmentContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class InstallationInterestV1(AssessmentContractModel):
    schema_version: Literal["installation-interest-v1"] = INTEREST_SCHEMA_VERSION
    item_id: Id64
    catalog_entry_id: Id64
    installation_plan_fingerprint: LowerHex64
    interest_kind: Literal["install-container-assessment"] = (
        "install-container-assessment"
    )
    selection_id: CanonicalUuid4
    selected_destination_fingerprint: LowerHex64
    requested_at: UtcSecond
    expires_at: UtcSecond
    interest_fingerprint: LowerHex64

    @model_validator(mode="after")
    def exact_lifetime(self) -> InstallationInterestV1:
        requested = datetime.strptime(
            self.requested_at, "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=UTC)
        expires = datetime.strptime(self.expires_at, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=UTC
        )
        if expires != requested + INTEREST_LIFETIME:
            raise ValueError("expires_at must be exactly 5 minutes after requested_at")
        return self


class InstallationAdmissionAssessmentV1(AssessmentContractModel):
    schema_version: Literal["installation-admission-assessment-v1"] = (
        ASSESSMENT_SCHEMA_VERSION
    )
    item_id: Id64
    catalog_entry_id: Id64
    plan_fingerprint: LowerHex64
    selection_id: CanonicalUuid4 | None
    selected_destination_fingerprint: LowerHex64 | None
    current_destination_fingerprint: LowerHex64 | None
    interest_fingerprint: LowerHex64 | None
    assessment_status: Literal["blocked", "preconditions_satisfied_but_unsupported"]
    reason_codes: tuple[AssessmentReason, ...]
    candidate_eligibility_evaluated: Literal[False] = False
    assessment_fingerprint: LowerHex64

    @model_validator(mode="after")
    def canonical_reasons_and_status(self) -> InstallationAdmissionAssessmentV1:
        expected = tuple(reason for reason in REASON_ORDER if reason in self.reason_codes)
        if self.reason_codes != expected or len(set(self.reason_codes)) != len(
            self.reason_codes
        ):
            raise ValueError("reason_codes must be unique and canonically ordered")
        unsupported = (
            "destination_installation_capability_unknown",
            "agent_install_container_unsupported",
        )
        if (self.assessment_status == "preconditions_satisfied_but_unsupported") != (
            self.reason_codes == unsupported
        ):
            raise ValueError("assessment status does not match exact reason semantics")
        return self
