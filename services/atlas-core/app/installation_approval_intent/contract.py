"""Closed, non-authorizing Installation Approval Intent v1 values."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from app.installation_candidate_admission.contract import fingerprint
from app.installation_candidate_lifecycle.contract import (
    InstallationCandidateRecordEnvelopeV1,
    OwnerId,
    candidate_record_state,
)
from app.installation_plan.contract import LowerHex64, UtcSecond
from app.installation_targets.contract import CanonicalUuid4

APPROVAL_STATEMENT = "operator_approved_exact_non_executable_candidate"


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class InstallationApprovalSubjectV1(_Closed):
    """The complete identity of the historical candidate being approved."""

    candidate_record_id: CanonicalUuid4
    candidate_envelope_fingerprint: LowerHex64
    admission_fingerprint: LowerHex64
    candidate_record_fingerprint: LowerHex64


class InstallationApprovalIntentV1(_Closed):
    """Evidence of a fixed operator statement; never execution permission."""

    schema: Literal["installation-approval-intent-v1"] = (
        "installation-approval-intent-v1"
    )
    approval_intent_id: CanonicalUuid4
    operator_id: OwnerId
    recorded_at: UtcSecond
    approved_subject: InstallationApprovalSubjectV1
    statement: Literal["operator_approved_exact_non_executable_candidate"] = (
        APPROVAL_STATEMENT
    )
    intent_fingerprint: LowerHex64

    @model_validator(mode="after")
    def exact_intent(self) -> InstallationApprovalIntentV1:
        expected = fingerprint(
            "atlas:installation-approval-intent:v1",
            self.model_dump(exclude={"intent_fingerprint"}, mode="json"),
        )
        if self.intent_fingerprint != expected:
            raise ValueError("approval intent fingerprint does not match content")
        return self


def validate_approval_subject(
    envelope: InstallationCandidateRecordEnvelopeV1,
    *,
    operator_id: str,
    recorded_at: str,
) -> InstallationApprovalSubjectV1:
    """Validate exact ownership, inertness, and activity without performing I/O."""
    exact = InstallationCandidateRecordEnvelopeV1.model_validate(
        envelope.model_dump(mode="python")
    )
    if exact.owner_id != operator_id:
        raise ValueError("candidate record is not owned by operator")
    if candidate_record_state(exact, now=recorded_at) != "active":
        raise ValueError("candidate record is not active")
    record = exact.candidate_record
    if any(
        (
            record.approved,
            record.executable,
            record.deployable,
            record.dispatchable,
            record.agent_execution_supported,
        )
    ):
        raise ValueError("candidate record carries authority")
    return InstallationApprovalSubjectV1(
        candidate_record_id=exact.candidate_record_id,
        candidate_envelope_fingerprint=exact.envelope_fingerprint,
        admission_fingerprint=exact.admission_fingerprint,
        candidate_record_fingerprint=record.record_fingerprint,
    )
