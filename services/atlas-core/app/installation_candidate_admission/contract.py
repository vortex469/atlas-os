"""Closed immutable Installation Candidate Admission v1 values."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from app.installation_plan.contract import Id64, LowerHex64, UtcSecond
from app.installation_targets.contract import CanonicalUuid4

AdmissionReason = Literal[
    "input_invalid",
    "input_unavailable",
    "installation_plan_not_review_ready",
    "destination_selection_not_active",
    "destination_selection_expired",
    "destination_identity_unavailable",
    "destination_replaced_or_moved",
    "capability_assessment_stale",
    "capability_assessment_mismatched",
    "capability_assessment_not_admissible",
    "authority_invariant_violated",
]
REASON_ORDER: tuple[AdmissionReason, ...] = (
    "input_invalid",
    "input_unavailable",
    "installation_plan_not_review_ready",
    "destination_selection_not_active",
    "destination_selection_expired",
    "destination_identity_unavailable",
    "destination_replaced_or_moved",
    "capability_assessment_stale",
    "capability_assessment_mismatched",
    "capability_assessment_not_admissible",
    "authority_invariant_violated",
)


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class InstallationCandidateRecordV1(_Closed):
    schema: Literal["installation-candidate-record-v1"] = (
        "installation-candidate-record-v1"
    )
    item_id: Id64
    catalog_entry_id: Id64
    plan_fingerprint: LowerHex64
    selection_id: CanonicalUuid4
    selected_destination_fingerprint: LowerHex64
    current_destination_fingerprint: LowerHex64
    capability_assessment_fingerprint: LowerHex64
    provider_fact_set_fingerprint: LowerHex64
    evaluated_at: UtcSecond
    valid_until: UtcSecond
    approved: Literal[False] = False
    executable: Literal[False] = False
    deployable: Literal[False] = False
    dispatchable: Literal[False] = False
    agent_execution_supported: Literal[False] = False
    record_fingerprint: LowerHex64

    @model_validator(mode="after")
    def exact_identity(self) -> InstallationCandidateRecordV1:
        if self.selected_destination_fingerprint != self.current_destination_fingerprint:
            raise ValueError("selected and current destination must be identical")
        expected = fingerprint(
            "atlas:installation-candidate-record:v1",
            self.model_dump(exclude={"record_fingerprint"}, mode="json"),
        )
        if self.record_fingerprint != expected:
            raise ValueError("record fingerprint does not match content")
        return self


class InstallationCandidateAdmissionV1(_Closed):
    schema: Literal["installation-candidate-admission-v1"] = (
        "installation-candidate-admission-v1"
    )
    plan_fingerprint: LowerHex64
    selection_fingerprint: LowerHex64
    selected_destination_fingerprint: LowerHex64
    current_destination_fingerprint: LowerHex64
    capability_assessment_fingerprint: LowerHex64
    provider_fact_set_fingerprint: LowerHex64
    evaluated_at: UtcSecond
    status: Literal["admitted_but_non_executable", "not_admitted"]
    reason_codes: tuple[AdmissionReason, ...]
    candidate_record: InstallationCandidateRecordV1 | None
    approved: Literal[False] = False
    executable: Literal[False] = False
    deployable: Literal[False] = False
    dispatchable: Literal[False] = False
    agent_execution_supported: Literal[False] = False
    candidate_creation_allowed: Literal[False] = False
    admission_fingerprint: LowerHex64

    @model_validator(mode="after")
    def exact_result(self) -> InstallationCandidateAdmissionV1:
        ordered = tuple(reason for reason in REASON_ORDER if reason in self.reason_codes)
        if self.reason_codes != ordered or len(set(self.reason_codes)) != len(ordered):
            raise ValueError("reasons must be unique and canonically ordered")
        admitted = self.status == "admitted_but_non_executable"
        if admitted != (not self.reason_codes and self.candidate_record is not None):
            raise ValueError("status, reasons, and candidate record disagree")
        expected = fingerprint(
            "atlas:installation-candidate-admission:v1",
            self.model_dump(exclude={"admission_fingerprint"}, mode="json"),
        )
        if self.admission_fingerprint != expected:
            raise ValueError("admission fingerprint does not match content")
        return self


def fingerprint(domain: str, value: dict[str, object]) -> str:
    """Restricted RFC 8785/JCS identity over closed JSON-domain values."""
    def validate(item: object) -> None:
        if isinstance(item, float):
            raise TypeError("floats are outside the restricted canonical domain")
        if isinstance(item, str) and item != unicodedata.normalize("NFC", item):
            raise ValueError("canonical strings must be NFC")
        if isinstance(item, dict):
            for key, child in item.items():
                if not isinstance(key, str):
                    raise TypeError("JSON keys must be strings")
                validate(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                validate(child)

    if not domain.isascii() or "\0" in domain:
        raise ValueError("invalid fingerprint domain")
    validate(value)
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(domain.encode() + b"\0" + encoded).hexdigest()
