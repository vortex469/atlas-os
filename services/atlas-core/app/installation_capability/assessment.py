"""Pure deterministic comparison of plans, destinations, and provider facts."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SkipValidation, model_validator

from app.installation_capability.provider_facts import (
    ProviderInstallationCapabilityFactsV1,
)
from app.installation_plan.contract import InstallationPlan, LowerHex64, UtcSecond
from app.installation_targets.contract import (
    InstallationDestinationSelectionV1,
    ProspectiveInstallationDestinationV1,
)

Result = Literal["satisfied", "not_satisfied", "unknown", "not_assessable"]
Reason = Literal[
    "installation_plan_blocked",
    "destination_selection_not_current",
    "destination_identity_not_current",
    "provider_facts_not_current",
    "provider_facts_unknown",
    "requirement_not_assessable",
    "requirement_not_satisfied",
    "agent_install_container_unsupported",
]
REASON_ORDER: tuple[Reason, ...] = (
    "installation_plan_blocked",
    "destination_selection_not_current",
    "destination_identity_not_current",
    "provider_facts_not_current",
    "provider_facts_unknown",
    "requirement_not_assessable",
    "requirement_not_satisfied",
    "agent_install_container_unsupported",
)


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class RequirementComparisonV1(_Frozen):
    prerequisite_id: LowerHex64
    prerequisite_kind: Literal[
        "storage", "network", "platform", "application", "operator"
    ]
    requirement_kind: Literal["cpu_cores", "memory", "storage", "unsupported"]
    requirement: str
    fact_code: (
        Literal[
            "configured_cpu_cores",
            "configured_memory_bytes",
            "configured_disk_capacity_bytes",
        ]
        | None
    )
    fact_state: (
        Literal["observed", "not_observed", "malformed", "conflicted", "unavailable"]
        | None
    )
    observed_value: int | None
    result: Result

    @model_validator(mode="after")
    def relation(self) -> RequirementComparisonV1:
        if self.requirement_kind == "unsupported":
            if (self.fact_code, self.fact_state, self.observed_value, self.result) != (
                None,
                None,
                None,
                "not_assessable",
            ):
                raise ValueError("unsupported requirement relation is invalid")
        elif (
            self.fact_code is None
            or self.fact_state is None
            or ((self.fact_state == "observed") != (self.observed_value is not None))
        ):
            raise ValueError("comparable requirement relation is invalid")
        return self


class InstallationCapabilityAssessmentV1(_Frozen):
    schema_version: Literal["installation-capability-assessment-v1"] = (
        "installation-capability-assessment-v1"
    )
    # Inputs are already-validated, frozen contracts. Avoid re-running their
    # model validators while nesting them in this immutable read model.
    plan: SkipValidation[InstallationPlan]
    selection: SkipValidation[InstallationDestinationSelectionV1]
    current_destination: SkipValidation[ProspectiveInstallationDestinationV1]
    provider_facts: SkipValidation[ProviderInstallationCapabilityFactsV1]
    comparisons: tuple[RequirementComparisonV1, ...] = Field(max_length=64)
    assessment_status: Literal[
        "blocked",
        "insufficient_provider_facts",
        "requirements_satisfied_but_non_authorizing",
    ]
    reason_codes: tuple[Reason, ...]
    evaluated_at: UtcSecond
    candidate_eligibility_evaluated: Literal[False] = False
    candidate_creation_allowed: Literal[False] = False
    agent_execution_supported: Literal[False] = False
    provider_mutation_allowed: Literal[False] = False
    assessment_fingerprint: LowerHex64

    @model_validator(mode="after")
    def canonical(self) -> InstallationCapabilityAssessmentV1:
        if not (
            isinstance(self.plan, InstallationPlan)
            and isinstance(self.selection, InstallationDestinationSelectionV1)
            and isinstance(
                self.current_destination, ProspectiveInstallationDestinationV1
            )
            and isinstance(self.provider_facts, ProviderInstallationCapabilityFactsV1)
        ):
            raise TypeError("assessment inputs must be exact frozen contracts")
        if self.reason_codes != tuple(
            r for r in REASON_ORDER if r in self.reason_codes
        ) or len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("reasons must be unique and canonically ordered")
        ids = tuple(c.prerequisite_id for c in self.comparisons)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValueError("comparisons must be sorted and unique")
        blocking = {
            "installation_plan_blocked",
            "destination_selection_not_current",
            "destination_identity_not_current",
            "provider_facts_not_current",
            "requirement_not_satisfied",
        }
        expected_status = (
            "blocked"
            if blocking & set(self.reason_codes)
            else "insufficient_provider_facts"
            if {"provider_facts_unknown", "requirement_not_assessable"}
            & set(self.reason_codes)
            else "requirements_satisfied_but_non_authorizing"
        )
        if self.assessment_status != expected_status:
            raise ValueError("assessment status does not match reasons")
        values = self.model_dump(exclude={"assessment_fingerprint"})
        # Restore contract objects so the one fingerprint routine has a
        # single frozen serialization path.
        values.update(
            plan=self.plan,
            selection=self.selection,
            current_destination=self.current_destination,
            provider_facts=self.provider_facts,
            comparisons=self.comparisons,
        )
        if self.assessment_fingerprint != _fingerprint(values):
            raise ValueError("assessment fingerprint does not match content")
        return self


_PATTERNS = (
    (
        "cpu_cores",
        "configured_cpu_cores",
        re.compile(r"Requires at least ([0-9]+(?:\.[0-9]*[1-9])?) CPU cores\."),
        Decimal(1),
    ),
    (
        "memory",
        "configured_memory_bytes",
        re.compile(r"Requires at least ([0-9]+) MB memory\."),
        Decimal(1024**2),
    ),
    (
        "storage",
        "configured_disk_capacity_bytes",
        re.compile(r"Requires at least ([0-9]+(?:\.[0-9]*[1-9])?) GB storage\."),
        Decimal(1024**3),
    ),
)


def assess_installation_capability(
    *,
    plan: InstallationPlan,
    selection: InstallationDestinationSelectionV1,
    current_destination: ProspectiveInstallationDestinationV1,
    provider_facts: ProviderInstallationCapabilityFactsV1,
    evaluated_at: datetime,
) -> InstallationCapabilityAssessmentV1:
    """Assess only supplied immutable read models; this function performs no I/O."""
    when = _utc(evaluated_at)
    selected = selection.status == "active" and _parse(
        selection.selected_at
    ) <= evaluated_at < _parse(selection.expires_at)
    identity = (
        selection.provider,
        selection.resource_type,
        selection.placement_kind,
        selection.resource_id,
        selection.selected_destination_fingerprint,
    ) == (
        current_destination.provider,
        current_destination.resource_type,
        current_destination.placement_kind,
        current_destination.resource_id,
        current_destination.destination_fingerprint,
    )
    facts_current = (
        provider_facts.provider,
        provider_facts.resource_type,
        provider_facts.placement_kind,
        provider_facts.resource_id,
        provider_facts.destination_fingerprint,
    ) == (
        current_destination.provider,
        current_destination.resource_type,
        current_destination.placement_kind,
        current_destination.resource_id,
        current_destination.destination_fingerprint,
    ) and (
        _parse(provider_facts.observed_at)
        <= evaluated_at
        < _parse(provider_facts.fresh_until)
    )
    facts = {fact.code: fact for fact in provider_facts.facts}
    comparisons = tuple(
        sorted(
            (
                _compare(p, facts, selected and identity and facts_current)
                for p in plan.prerequisites
            ),
            key=lambda c: c.prerequisite_id,
        )
    )
    reasons: set[Reason] = {"agent_install_container_unsupported"}
    if plan.status != "plan_ready_for_review":
        reasons.add("installation_plan_blocked")
    if not selected:
        reasons.add("destination_selection_not_current")
    if not identity:
        reasons.add("destination_identity_not_current")
    if not facts_current:
        reasons.add("provider_facts_not_current")
    if any(c.result == "unknown" for c in comparisons):
        reasons.add("provider_facts_unknown")
    if any(c.result == "not_assessable" for c in comparisons):
        reasons.add("requirement_not_assessable")
    if any(c.result == "not_satisfied" for c in comparisons):
        reasons.add("requirement_not_satisfied")
    if (
        plan.status != "plan_ready_for_review"
        or not selected
        or not identity
        or not facts_current
        or "requirement_not_satisfied" in reasons
    ):
        status = "blocked"
    elif reasons & {"provider_facts_unknown", "requirement_not_assessable"}:
        status = "insufficient_provider_facts"
    else:
        status = "requirements_satisfied_but_non_authorizing"
    values = {
        "schema_version": "installation-capability-assessment-v1",
        "plan": plan,
        "selection": selection,
        "current_destination": current_destination,
        "provider_facts": provider_facts,
        "comparisons": comparisons,
        "assessment_status": status,
        "reason_codes": tuple(r for r in REASON_ORDER if r in reasons),
        "evaluated_at": when,
        "candidate_eligibility_evaluated": False,
        "candidate_creation_allowed": False,
        "agent_execution_supported": False,
        "provider_mutation_allowed": False,
    }
    return InstallationCapabilityAssessmentV1(
        **values, assessment_fingerprint=_fingerprint(values)
    )


def _compare(
    prerequisite: object, facts: dict[str, object], reliable: bool
) -> RequirementComparisonV1:
    for kind, code, pattern, multiplier in _PATTERNS:
        match = pattern.fullmatch(prerequisite.description)
        if match:
            fact = facts[code]
            observed = (
                fact.value
                if fact.state == "observed" and type(fact.value) is int
                else None
            )
            result: Result = (
                "unknown"
                if not reliable or observed is None
                else (
                    "satisfied"
                    if Decimal(observed) >= Decimal(match.group(1)) * multiplier
                    else "not_satisfied"
                )
            )
            return RequirementComparisonV1(
                prerequisite_id=prerequisite.prerequisite_id,
                prerequisite_kind=prerequisite.kind,
                requirement_kind=kind,
                requirement=prerequisite.description,
                fact_code=code,
                fact_state=fact.state,
                observed_value=observed,
                result=result,
            )
    return RequirementComparisonV1(
        prerequisite_id=prerequisite.prerequisite_id,
        prerequisite_kind=prerequisite.kind,
        requirement_kind="unsupported",
        requirement=prerequisite.description,
        fact_code=None,
        fact_state=None,
        observed_value=None,
        result="not_assessable",
    )


def _fingerprint(values: dict[str, object]) -> str:
    raw = {
        key: value.model_dump(mode="json")
        if isinstance(value, BaseModel)
        else [v.model_dump(mode="json") for v in value]
        if key == "comparisons"
        else value
        for key, value in values.items()
    }
    encoded = json.dumps(
        raw, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(
        b"atlas:installation-capability-assessment:v1\0" + encoded
    ).hexdigest()


def _utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() != timedelta(0) or value.microsecond:
        raise ValueError("whole-second UTC evaluation time required")
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
