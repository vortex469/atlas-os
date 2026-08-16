"""Strict advisory contracts for identity-bound Provider Intent suggestions."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.provider_management import (
    PROVIDER_MANAGEMENT_FINGERPRINT_PATTERN,
    ProviderMonitoringExpectation,
)

SUGGESTION_SCHEMA_VERSION = "provider-monitoring-intent-suggestion-v1"
SUGGESTION_ID_VERSION = "provider-monitoring-intent-suggestion-id-v1"
OBSERVED_RUNNING_RULE = "qemu-observed-running-no-active-intent-v1"
OBSERVED_RUNNING_REASON = "observed_running_without_active_intent"
SUGGESTION_ID_PATTERN = (
    rf"^{SUGGESTION_ID_VERSION}:[a-f0-9]{{64}}$"
)


class ProviderIntentSuggestionModel(BaseModel):
    """Reject extension and mutation of advisory suggestion contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


def build_provider_monitoring_intent_suggestion_id(
    *,
    provider_id: str,
    resource_type: str,
    resource_id: str,
    management_fingerprint: str,
    suggested_expectation: ProviderMonitoringExpectation,
    base_record_version: int,
    source_rule: str,
    reason: str,
) -> str:
    """Bind one suggestion to its complete sanitized advisory source state."""

    payload = {
        "base_record_version": base_record_version,
        "management_fingerprint": management_fingerprint,
        "provider_id": provider_id,
        "reason": reason,
        "resource_id": resource_id,
        "resource_type": resource_type,
        "schema_version": SUGGESTION_SCHEMA_VERSION,
        "source_rule": source_rule,
        "suggested_expectation": suggested_expectation.value,
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode()
    return f"{SUGGESTION_ID_VERSION}:{hashlib.sha256(encoded).hexdigest()}"


class ProviderMonitoringIntentSuggestionV1(ProviderIntentSuggestionModel):
    """One immutable advisory produced by the accepted initial P5 rule."""

    schema_version: Literal[
        "provider-monitoring-intent-suggestion-v1"
    ] = SUGGESTION_SCHEMA_VERSION
    suggestion_id: str = Field(pattern=SUGGESTION_ID_PATTERN)
    provider_id: Literal["proxmox"]
    resource_type: Literal["qemu"]
    resource_id: str = Field(pattern=r"^[1-9][0-9]*$", max_length=20)
    management_fingerprint: str = Field(
        pattern=PROVIDER_MANAGEMENT_FINGERPRINT_PATTERN
    )
    suggested_expectation: Literal[
        ProviderMonitoringExpectation.RUNNING
    ]
    base_record_version: int = Field(ge=0)
    source: Literal["provider_intelligence_rule"]
    source_rule: Literal[
        "qemu-observed-running-no-active-intent-v1"
    ]
    reason: Literal["observed_running_without_active_intent"]
    advisory_only: Literal[True] = True
    grants_permission: Literal[False] = False
    grants_execution: Literal[False] = False

    @model_validator(mode="after")
    def validate_suggestion_identity(
        self,
    ) -> ProviderMonitoringIntentSuggestionV1:
        if self.base_record_version != 0:
            raise ValueError(
                "the initial suggestion rule requires base record version zero"
            )
        expected = build_provider_monitoring_intent_suggestion_id(
            provider_id=self.provider_id,
            resource_type=self.resource_type,
            resource_id=self.resource_id,
            management_fingerprint=self.management_fingerprint,
            suggested_expectation=self.suggested_expectation,
            base_record_version=self.base_record_version,
            source_rule=self.source_rule,
            reason=self.reason,
        )
        if self.suggestion_id != expected:
            raise ValueError(
                "suggestion ID does not match the advisory source state"
            )
        return self


def observed_running_suggestion(
    *, resource_id: str, management_fingerprint: str
) -> ProviderMonitoringIntentSuggestionV1:
    """Build the sole suggestion shape accepted by the initial P5 rule."""

    expectation = ProviderMonitoringExpectation.RUNNING
    suggestion_id = build_provider_monitoring_intent_suggestion_id(
        provider_id="proxmox",
        resource_type="qemu",
        resource_id=resource_id,
        management_fingerprint=management_fingerprint,
        suggested_expectation=expectation,
        base_record_version=0,
        source_rule=OBSERVED_RUNNING_RULE,
        reason=OBSERVED_RUNNING_REASON,
    )
    return ProviderMonitoringIntentSuggestionV1(
        suggestion_id=suggestion_id,
        provider_id="proxmox",
        resource_type="qemu",
        resource_id=resource_id,
        management_fingerprint=management_fingerprint,
        suggested_expectation=expectation,
        base_record_version=0,
        source="provider_intelligence_rule",
        source_rule=OBSERVED_RUNNING_RULE,
        reason=OBSERVED_RUNNING_REASON,
    )
