"""Pure, bounded projection of sanitized Proxmox QEMU configuration facts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from app.installation_targets.contract import LowerHex64, QemuResourceId, UtcSecond
from app.installation_targets.fingerprint import build_destination_fingerprint
from app.services.provider_resource_identity import ResolvedOperationalTarget

FACT_SCHEMA_VERSION = "provider-installation-capability-facts-v1"
FACT_FRESHNESS = timedelta(minutes=5)
MAX_CPU_CORES = 65_536
MAX_CAPACITY_BYTES = 2**63 - 1
ObservationState = Literal[
    "observed", "not_observed", "malformed", "conflicted", "unavailable"
]
FactCode = Literal[
    "current_destination_identity",
    "current_lifecycle_state",
    "configured_cpu_cores",
    "configured_memory_bytes",
    "configured_disk_capacity_bytes",
    "guest_agent_configured",
]


def _lifecycle(value: str) -> str:
    if value not in {"running", "stopped", "unknown"}:
        raise ValueError("closed lifecycle value required")
    return value


Lifecycle = Annotated[str, AfterValidator(_lifecycle)]
FactValue = bool | int | Lifecycle


class _FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ProviderCapabilityFactV1(_FrozenModel):
    code: FactCode
    state: ObservationState
    value: FactValue | None
    source: Literal["proxmox-qemu-control-plane"] = "proxmox-qemu-control-plane"
    observed_at: UtcSecond
    destination_fingerprint: LowerHex64

    @model_validator(mode="after")
    def validate_value(self) -> ProviderCapabilityFactV1:
        if (self.state == "observed") != (self.value is not None):
            raise ValueError("only observed facts carry values")
        if self.code == "current_destination_identity" and self.value is not True:
            raise ValueError("current identity fact must be observed true")
        if self.code in {
            "configured_cpu_cores", "configured_memory_bytes",
            "configured_disk_capacity_bytes",
        } and self.value is not None:
            maximum = MAX_CPU_CORES if self.code == "configured_cpu_cores" else MAX_CAPACITY_BYTES
            if type(self.value) is not int or not 0 < self.value <= maximum:
                raise ValueError("configured capacity is outside the bounded range")
        if self.code == "guest_agent_configured" and self.value is not None and type(self.value) is not bool:
            raise ValueError("guest-agent configuration must be boolean")
        return self


class ProviderInstallationCapabilityFactsV1(_FrozenModel):
    schema_version: Literal["provider-installation-capability-facts-v1"] = FACT_SCHEMA_VERSION
    provider: Literal["proxmox"] = "proxmox"
    resource_type: Literal["qemu"] = "qemu"
    placement_kind: Literal["existing-guest"] = "existing-guest"
    resource_id: QemuResourceId
    destination_fingerprint: LowerHex64
    observed_at: UtcSecond
    fresh_until: UtcSecond
    facts: tuple[ProviderCapabilityFactV1, ...] = Field(min_length=6, max_length=6)

    @model_validator(mode="after")
    def validate_set(self) -> ProviderInstallationCapabilityFactsV1:
        observed = _parse_time(self.observed_at)
        if _parse_time(self.fresh_until) != observed + FACT_FRESHNESS:
            raise ValueError("fact freshness must be exactly five minutes")
        expected = list(FactCode.__args__)  # type: ignore[attr-defined]
        if [fact.code for fact in self.facts] != expected:
            raise ValueError("facts must use the complete canonical vocabulary")
        if any(
            fact.observed_at != self.observed_at
            or fact.destination_fingerprint != self.destination_fingerprint
            for fact in self.facts
        ):
            raise ValueError("facts must share observation identity and time")
        return self


def adapt_proxmox_qemu_capability_facts(
    target: ResolvedOperationalTarget,
    *,
    expected_destination_fingerprint: str,
    observed_at: datetime,
) -> ProviderInstallationCapabilityFactsV1:
    """Adapt one already-resolved target without I/O or authority-bearing calls."""
    resource = target.resource
    if (
        target.provider.id != "proxmox"
        or resource.provider_id != "proxmox"
        or resource.resource_type != "qemu"
        or resource.missing
        or resource.identity is None
    ):
        raise ValueError("exact current Proxmox QEMU identity required")
    current_fingerprint = build_destination_fingerprint(
        resource_id=resource.resource_id,
        operational_fingerprint=target.resource_fingerprint,
    )
    if current_fingerprint != expected_destination_fingerprint:
        raise ValueError("current destination identity does not match")
    if observed_at.tzinfo is None or observed_at.utcoffset() != timedelta(0) or observed_at.microsecond:
        raise ValueError("whole-second UTC observation time required")
    timestamp = observed_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh_until = (observed_at + FACT_FRESHNESS).strftime("%Y-%m-%dT%H:%M:%SZ")
    projection = resource.metadata.get("installation_capability")
    entries = projection if isinstance(projection, dict) else {}
    values: list[tuple[FactCode, ObservationState, FactValue | None]] = [
        ("current_destination_identity", "observed", True),
        ("current_lifecycle_state", "observed", resource.current_state)
        if resource.current_state in {"running", "stopped", "unknown"}
        else ("current_lifecycle_state", "malformed", None),
    ]
    for code, key in (
        ("configured_cpu_cores", "cpu_cores"),
        ("configured_memory_bytes", "memory_bytes"),
        ("configured_disk_capacity_bytes", "disk_capacity_bytes"),
        ("guest_agent_configured", "guest_agent_configured"),
    ):
        values.append(
            (code, *_bounded_entry(
                entries.get(key), boolean=code == "guest_agent_configured",
                maximum=MAX_CPU_CORES if code == "configured_cpu_cores" else MAX_CAPACITY_BYTES,
            ))
        )
    facts = tuple(
        ProviderCapabilityFactV1(
            code=code, state=state, value=value, observed_at=timestamp,
            destination_fingerprint=current_fingerprint,
        )
        for code, state, value in values
    )
    return ProviderInstallationCapabilityFactsV1(
        resource_id=resource.resource_id,
        destination_fingerprint=current_fingerprint,
        observed_at=timestamp,
        fresh_until=fresh_until,
        facts=facts,
    )


def _bounded_entry(
    value: object, *, boolean: bool, maximum: int
) -> tuple[ObservationState, FactValue | None]:
    if not isinstance(value, dict):
        return "unavailable", None
    state = value.get("state")
    fact_value = value.get("value")
    if state not in {"observed", "not_observed", "malformed", "conflicted", "unavailable"}:
        return "malformed", None
    if state != "observed":
        return state, None
    if boolean:
        if type(fact_value) is not bool:
            return "malformed", None
    elif type(fact_value) is not int or not 0 < fact_value <= maximum:
        return "malformed", None
    return "observed", fact_value


def _parse_time(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
