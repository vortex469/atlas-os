"""Closed v0.20 installation candidate envelope and pure lifecycle rules."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, model_validator

from app.installation_candidate_admission.contract import (
    InstallationCandidateAdmissionV1,
    InstallationCandidateRecordV1,
    fingerprint,
)
from app.installation_plan.contract import LowerHex64, UtcSecond
from app.installation_targets.contract import CanonicalUuid4

LifecycleState = Literal["active", "expired"]


def _owner_id(value: str) -> str:
    if not 1 <= len(value.encode("ascii", errors="ignore")) <= 200:
        raise ValueError("owner ID must be 1-200 visible ASCII bytes")
    if not value.isascii() or any(not 0x21 <= ord(character) <= 0x7E for character in value):
        raise ValueError("owner ID must be 1-200 visible ASCII bytes")
    return value


OwnerId = Annotated[str, AfterValidator(_owner_id)]


class InstallationCandidateRecordEnvelopeV1(BaseModel):
    """Immutable, advisory preservation of one exact v0.19 candidate record."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema: Literal["installation-candidate-record-envelope-v1"] = (
        "installation-candidate-record-envelope-v1"
    )
    candidate_record_id: CanonicalUuid4
    owner_id: OwnerId
    created_at: UtcSecond
    admission_fingerprint: LowerHex64
    candidate_record: InstallationCandidateRecordV1
    envelope_fingerprint: LowerHex64

    @model_validator(mode="after")
    def exact_envelope(self) -> InstallationCandidateRecordEnvelopeV1:
        if self.created_at >= self.candidate_record.valid_until:
            raise ValueError("candidate record predates its envelope")
        expected = fingerprint(
            "atlas:installation-candidate-record-envelope:v1",
            self.model_dump(exclude={"envelope_fingerprint"}, mode="json"),
        )
        if self.envelope_fingerprint != expected:
            raise ValueError("envelope fingerprint does not match content")
        return self


def validate_preservable_admission(
    admission: InstallationCandidateAdmissionV1, *, created_at: str
) -> InstallationCandidateRecordV1:
    """Return the exact positive, still-valid snapshot or fail closed."""
    # Round-trip validation prevents model subclasses or unvalidated construction
    # from crossing the durable boundary.
    exact = InstallationCandidateAdmissionV1.model_validate(
        admission.model_dump()
    )
    if (
        exact.status != "admitted_but_non_executable"
        or exact.reason_codes
        or exact.candidate_record is None
        or exact.candidate_record.valid_until <= created_at
    ):
        raise ValueError("admission is not currently preservable")
    return exact.candidate_record


def candidate_record_state(
    envelope: InstallationCandidateRecordEnvelopeV1, *, now: str
) -> LifecycleState:
    """Derive the passive half-open lifecycle state without mutation."""
    instant = _parse_utc_second(now)
    created = _parse_utc_second(envelope.created_at)
    valid_until = _parse_utc_second(envelope.candidate_record.valid_until)
    if instant < created:
        raise ValueError("lifecycle instant precedes creation")
    return "active" if instant < valid_until else "expired"


def _parse_utc_second(value: str) -> datetime:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except (TypeError, ValueError) as error:
        raise ValueError("whole-second UTC instant required") from error
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise ValueError("whole-second UTC instant required")
    return parsed
