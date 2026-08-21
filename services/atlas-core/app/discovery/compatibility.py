from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import Field, field_validator, model_validator

from app.discovery.models import (
    DiscoveryCenterModel,
    DiscoveryItem,
    DiscoveryRelationship,
    DiscoveryRelationshipType,
)
from app.discovery.release_evaluation import parse_strict_numeric_version
from app.discovery.repository import DiscoveryRepository


class CompatibilityStatus(StrEnum):
    """Deterministic Discovery compatibility assessment status."""

    COMPATIBLE = "compatible"
    COMPATIBLE_WITH_WARNINGS = "compatible_with_warnings"
    INSUFFICIENT_INFORMATION = "insufficient_information"
    INCOMPATIBLE = "incompatible"


class CompatibilityFindingSeverity(StrEnum):
    """Severity for compatibility findings, independent of health findings."""

    BLOCKER = "blocker"
    WARNING = "warning"
    INFO = "info"
    UNKNOWN = "unknown"


class CompatibilityCheckType(StrEnum):
    """Kinds of deterministic compatibility checks."""

    CAPABILITY = "capability"
    RESOURCE = "resource"
    PLATFORM = "platform"
    NETWORK = "network"
    RELATIONSHIP = "relationship"
    CATALOG = "catalog"
    VERSION = "version"


class ObservedFact(DiscoveryCenterModel):
    """Provider-neutral fact observed about a compatibility target."""

    id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    value: str | int | float | bool | None = None
    source: str = Field(min_length=1)
    metadata: Mapping[str, Any] = Field(default_factory=dict)


class ObservedPort(DiscoveryCenterModel):
    """Provider-neutral observed network port fact."""

    port: int = Field(ge=1, le=65535)
    protocol: str = "tcp"
    direction: str = "inbound"
    source: str = Field(min_length=1)

    @field_validator("protocol", "direction", mode="before")
    @classmethod
    def normalize(cls, value: str) -> str:
        if not isinstance(value, str):
            return value
        return value.strip().lower()


class ObservedService(DiscoveryCenterModel):
    """Provider-neutral observed service or resource fact.

    ``installed_version`` is an advisory raw observation preserved as
    provided; comparability is determined separately and only strict
    canonical ``X.Y.Z`` versions are comparable evidence.
    """

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    capabilities: tuple[str, ...] = ()
    status: str = "unknown"
    source: str = Field(min_length=1)
    installed_version: str | None = Field(
        default=None, min_length=1, max_length=64
    )

    @field_validator("capabilities", mode="before")
    @classmethod
    def normalize_capabilities(cls, value: Any) -> tuple[str, ...]:
        return _normalize_unique_strings(value)


class CompatibilityContext(DiscoveryCenterModel):
    """Provider-neutral observed facts for a compatibility target."""

    target_id: str = "atlas"
    target_type: str = "atlas_environment"
    facts: tuple[ObservedFact, ...] = ()
    capabilities: tuple[str, ...] | None = None
    runtimes: tuple[str, ...] | None = None
    operating_system: str | None = None
    architecture: str | None = None
    cpu_cores: float | None = Field(default=None, ge=0)
    memory_mb: int | None = Field(default=None, ge=0)
    storage_gb: float | None = Field(default=None, ge=0)
    gpu_available: bool | None = None
    gpu_memory_gb: float | None = Field(default=None, ge=0)
    devices: tuple[str, ...] | None = None
    open_ports: tuple[ObservedPort, ...] | None = None
    installed_services: tuple[ObservedService, ...] | None = None

    @field_validator("capabilities", "runtimes", "devices", mode="before")
    @classmethod
    def normalize_optional_string_tuple(cls, value: Any) -> tuple[str, ...] | None:
        if value is None:
            return None
        return _normalize_unique_strings(value)

    @model_validator(mode="after")
    def validate_unique_fact_ids(self) -> CompatibilityContext:
        fact_ids = [fact.id for fact in self.facts]
        if len(fact_ids) != len(set(fact_ids)):
            raise ValueError("observed fact ids must be unique.")
        return self

    def fact(self, fact_id: str) -> ObservedFact | None:
        return next((fact for fact in self.facts if fact.id == fact_id), None)


class CompatibilityEvidence(DiscoveryCenterModel):
    """Evidence produced by one deterministic compatibility check."""

    id: str = Field(min_length=1)
    check_type: CompatibilityCheckType
    subject: str = Field(min_length=1)
    status: CompatibilityStatus
    message: str = Field(min_length=1)
    source: str = Field(min_length=1)
    requirement: str | None = None
    observed: str | None = None
    observed_fact_id: str | None = None


class CompatibilityFinding(DiscoveryCenterModel):
    """Compatibility issue or note referencing assessment evidence."""

    id: str = Field(min_length=1)
    check_type: CompatibilityCheckType
    severity: CompatibilityFindingSeverity
    status: CompatibilityStatus
    subject: str = Field(min_length=1)
    message: str = Field(min_length=1)
    evidence_ids: tuple[str, ...]

    @field_validator("evidence_ids")
    @classmethod
    def validate_evidence_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if not values:
            raise ValueError("findings must reference at least one evidence item.")
        if len(values) != len(set(values)):
            raise ValueError("finding evidence ids must be unique.")
        return values


class CompatibilityAssessment(DiscoveryCenterModel):
    """Deterministic compatibility result for one item and target context."""

    item_id: str
    target_id: str
    target_type: str
    status: CompatibilityStatus
    checked_at: datetime
    findings: tuple[CompatibilityFinding, ...] = ()
    evidence: tuple[CompatibilityEvidence, ...] = ()
    unknown_facts: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_findings_reference_evidence(self) -> CompatibilityAssessment:
        evidence_ids = {item.id for item in self.evidence}
        for finding in self.findings:
            missing = set(finding.evidence_ids) - evidence_ids
            if missing:
                raise ValueError("findings must reference existing evidence ids.")
        return self


@runtime_checkable
class CompatibilityContextBuilder(Protocol):
    """Build a provider-neutral compatibility context from external observations."""

    def build_context(self, target: str = "atlas") -> CompatibilityContext:
        """Return observed facts for the requested target."""


def assess_compatibility(
    item: DiscoveryItem,
    context: CompatibilityContext,
    repository: DiscoveryRepository,
    *,
    checked_at: datetime | None = None,
) -> CompatibilityAssessment:
    """Evaluate item compatibility using only provider-neutral observed facts."""

    builder = _AssessmentBuilder(item, context, repository)
    builder.evaluate()
    return CompatibilityAssessment(
        item_id=item.id,
        target_id=context.target_id,
        target_type=context.target_type,
        status=_aggregate_status(builder.findings),
        checked_at=checked_at or datetime.now(UTC),
        findings=tuple(builder.findings),
        evidence=tuple(builder.evidence),
        unknown_facts=tuple(sorted(builder.unknown_facts)),
    )


def installed_version_key(
    service: ObservedService,
) -> tuple[int, int, int] | None:
    """Strict numeric comparison key for an observed installed version.

    Only strict canonical ``X.Y.Z`` observations are comparable installed-
    version evidence. A missing or malformed version returns ``None`` and
    must be treated as unknown; it can never yield a positive version
    assertion.
    """
    return parse_strict_numeric_version(service.installed_version)


class _AssessmentBuilder:
    def __init__(
        self,
        item: DiscoveryItem,
        context: CompatibilityContext,
        repository: DiscoveryRepository,
    ) -> None:
        self.item = item
        self.context = context
        self.repository = repository
        self.evidence: list[CompatibilityEvidence] = []
        self.findings: list[CompatibilityFinding] = []
        self.unknown_facts: set[str] = set()

    def evaluate(self) -> None:
        self._evaluate_catalog_status()
        self._evaluate_capabilities()
        self._evaluate_resources()
        self._evaluate_platform()
        self._evaluate_network()
        self._evaluate_relationships()

    def _evaluate_catalog_status(self) -> None:
        if self.item.status.value == "active":
            self._add_evidence(
                check_type=CompatibilityCheckType.CATALOG,
                subject="item.status",
                status=CompatibilityStatus.COMPATIBLE,
                message="Catalog item status is active.",
                source="catalog",
                requirement="active",
                observed=self.item.status.value,
            )
            return

        evidence = self._add_evidence(
            check_type=CompatibilityCheckType.CATALOG,
            subject="item.status",
            status=CompatibilityStatus.COMPATIBLE_WITH_WARNINGS,
            message=f"Catalog item status is {self.item.status.value}.",
            source="catalog",
            requirement="active",
            observed=self.item.status.value,
        )
        self._add_finding(
            check_type=CompatibilityCheckType.CATALOG,
            severity=CompatibilityFindingSeverity.WARNING,
            status=CompatibilityStatus.COMPATIBLE_WITH_WARNINGS,
            subject="item.status",
            message=f"Catalog item status is {self.item.status.value}.",
            evidence_ids=(evidence.id,),
        )

    def _evaluate_capabilities(self) -> None:
        requirements = self.item.requirements.capabilities
        if not requirements:
            return

        observed = self.context.capabilities
        for capability in requirements:
            subject = f"requirements.capabilities.{capability.id}"
            if observed is None:
                self._unknown(
                    check_type=CompatibilityCheckType.CAPABILITY,
                    subject=subject,
                    requirement=capability.id,
                    fact_name="capabilities",
                    message=(
                        f"Required capability '{capability.id}' cannot be evaluated "
                        "because observed capabilities are unknown."
                    ),
                )
            elif capability.id in observed:
                self._add_evidence(
                    check_type=CompatibilityCheckType.CAPABILITY,
                    subject=subject,
                    status=CompatibilityStatus.COMPATIBLE,
                    message=f"Required capability '{capability.id}' is present.",
                    source="compatibility_context",
                    requirement=capability.id,
                    observed=capability.id,
                    observed_fact_id=_fact_id("capability", capability.id),
                )
            else:
                self._incompatible(
                    check_type=CompatibilityCheckType.CAPABILITY,
                    subject=subject,
                    requirement=capability.id,
                    observed=", ".join(observed) if observed else "none",
                    message=f"Required capability '{capability.id}' is not present.",
                    observed_fact_id=_fact_id("capability", capability.id),
                )

    def _evaluate_resources(self) -> None:
        resources = self.item.requirements.resources
        self._evaluate_minimum(
            check_type=CompatibilityCheckType.RESOURCE,
            subject="requirements.resources.cpu_cores_min",
            requirement=resources.cpu_cores_min,
            observed=self.context.cpu_cores,
            fact_name="cpu_cores",
            unit="CPU cores",
        )
        self._evaluate_minimum(
            check_type=CompatibilityCheckType.RESOURCE,
            subject="requirements.resources.memory_mb_min",
            requirement=resources.memory_mb_min,
            observed=self.context.memory_mb,
            fact_name="memory_mb",
            unit="MB memory",
        )
        self._evaluate_minimum(
            check_type=CompatibilityCheckType.RESOURCE,
            subject="requirements.resources.storage_gb_min",
            requirement=resources.storage_gb_min,
            observed=self.context.storage_gb,
            fact_name="storage_gb",
            unit="GB storage",
        )

        if resources.gpu_required:
            if self.context.gpu_available is None:
                self._unknown(
                    check_type=CompatibilityCheckType.RESOURCE,
                    subject="requirements.resources.gpu_required",
                    requirement="true",
                    fact_name="gpu_available",
                    message="GPU requirement cannot be evaluated because GPU availability is unknown.",
                )
            elif self.context.gpu_available:
                self._add_evidence(
                    check_type=CompatibilityCheckType.RESOURCE,
                    subject="requirements.resources.gpu_required",
                    status=CompatibilityStatus.COMPATIBLE,
                    message="Required GPU availability is present.",
                    source="compatibility_context",
                    requirement="true",
                    observed="true",
                    observed_fact_id="gpu_available",
                )
            else:
                self._incompatible(
                    check_type=CompatibilityCheckType.RESOURCE,
                    subject="requirements.resources.gpu_required",
                    requirement="true",
                    observed="false",
                    message="Required GPU availability is not present.",
                    observed_fact_id="gpu_available",
                )

        self._evaluate_minimum(
            check_type=CompatibilityCheckType.RESOURCE,
            subject="requirements.resources.gpu_memory_gb_min",
            requirement=resources.gpu_memory_gb_min,
            observed=self.context.gpu_memory_gb,
            fact_name="gpu_memory_gb",
            unit="GB GPU memory",
        )

    def _evaluate_platform(self) -> None:
        platform = self.item.requirements.platform
        self._evaluate_allowed_values(
            subject="requirements.platform.architectures",
            required=platform.architectures,
            observed=self.context.architecture,
            fact_name="architecture",
        )
        self._evaluate_allowed_values(
            subject="requirements.platform.operating_systems",
            required=platform.operating_systems,
            observed=self.context.operating_system,
            fact_name="operating_system",
        )
        self._evaluate_required_set(
            subject="requirements.platform.runtimes",
            required=platform.runtimes,
            observed=self.context.runtimes,
            fact_name="runtimes",
        )
        self._evaluate_required_set(
            subject="requirements.platform.devices",
            required=platform.devices,
            observed=self.context.devices,
            fact_name="devices",
        )

    def _evaluate_network(self) -> None:
        network = self.item.requirements.network
        if network.requires_internet:
            self._unknown(
                check_type=CompatibilityCheckType.NETWORK,
                subject="requirements.network.requires_internet",
                requirement="true",
                fact_name="internet_reachability",
                message="Internet reachability cannot be evaluated from current observed facts.",
            )
        if network.requires_lan:
            self._unknown(
                check_type=CompatibilityCheckType.NETWORK,
                subject="requirements.network.requires_lan",
                requirement="true",
                fact_name="lan_reachability",
                message="LAN reachability cannot be evaluated from current observed facts.",
            )

        for port in network.ports:
            subject = f"requirements.network.ports.{port.protocol}.{port.port}.{port.direction}"
            requirement = f"{port.direction} {port.protocol}/{port.port}"
            if self.context.open_ports is None:
                if port.required:
                    self._unknown(
                        check_type=CompatibilityCheckType.NETWORK,
                        subject=subject,
                        requirement=requirement,
                        fact_name="open_ports",
                        message=(
                            f"Required port {requirement} cannot be evaluated "
                            "because observed ports are unknown."
                        ),
                    )
                else:
                    self._add_evidence(
                        check_type=CompatibilityCheckType.NETWORK,
                        subject=subject,
                        status=CompatibilityStatus.COMPATIBLE,
                        message=f"Optional port {requirement} is documented but not required.",
                        source="catalog",
                        requirement=requirement,
                        observed="not required",
                    )
                continue

            matching = any(
                observed.port == port.port
                and observed.protocol == port.protocol
                and observed.direction == port.direction
                for observed in self.context.open_ports
            )
            if matching:
                self._add_evidence(
                    check_type=CompatibilityCheckType.NETWORK,
                    subject=subject,
                    status=CompatibilityStatus.COMPATIBLE,
                    message=f"Observed port {requirement} is present.",
                    source="compatibility_context",
                    requirement=requirement,
                    observed=requirement,
                    observed_fact_id=f"port:{port.protocol}:{port.port}:{port.direction}",
                )
            elif port.required:
                self._incompatible(
                    check_type=CompatibilityCheckType.NETWORK,
                    subject=subject,
                    requirement=requirement,
                    observed="not observed",
                    message=f"Required port {requirement} is not observed.",
                    observed_fact_id=f"port:{port.protocol}:{port.port}:{port.direction}",
                )
            else:
                self._add_evidence(
                    check_type=CompatibilityCheckType.NETWORK,
                    subject=subject,
                    status=CompatibilityStatus.COMPATIBLE,
                    message=f"Optional port {requirement} is not required.",
                    source="catalog",
                    requirement=requirement,
                    observed="not observed",
                )

    def _evaluate_relationships(self) -> None:
        for relationship in self.item.relationships:
            subject = f"relationships.{relationship.type}.{relationship.target}"
            target = self.repository.get_item(relationship.target)
            if target is None:
                if relationship.required:
                    self._unknown(
                        check_type=CompatibilityCheckType.RELATIONSHIP,
                        subject=subject,
                        requirement=relationship.target,
                        fact_name=f"relationship:{relationship.target}",
                        message=(
                            f"Required relationship target '{relationship.target}' "
                            "is not resolved in the Discovery repository."
                        ),
                    )
                else:
                    self._add_evidence(
                        check_type=CompatibilityCheckType.RELATIONSHIP,
                        subject=subject,
                        status=CompatibilityStatus.COMPATIBLE,
                        message=(
                            f"Optional relationship target '{relationship.target}' "
                            "is unresolved and not required."
                        ),
                        source="catalog",
                        requirement=relationship.target,
                        observed="optional unresolved",
                    )
                continue

            if not relationship.required:
                self._add_evidence(
                    check_type=CompatibilityCheckType.RELATIONSHIP,
                    subject=subject,
                    status=CompatibilityStatus.COMPATIBLE,
                    message=(
                        f"Optional relationship target '{relationship.target}' "
                        "is present in the catalog."
                    ),
                    source="catalog",
                    requirement=relationship.target,
                    observed=target.id,
                )
                continue

            if relationship.type in {
                DiscoveryRelationshipType.DEPENDS_ON,
                DiscoveryRelationshipType.INTEGRATES_WITH,
                DiscoveryRelationshipType.RUNS_ON,
                DiscoveryRelationshipType.DEPLOYED_BY,
                DiscoveryRelationshipType.COMPATIBLE_WITH,
            }:
                if self.context.installed_services is None:
                    self._unknown(
                        check_type=CompatibilityCheckType.RELATIONSHIP,
                        subject=subject,
                        requirement=relationship.target,
                        fact_name="installed_services",
                        message=(
                            f"Required relationship target '{relationship.target}' "
                            "cannot be evaluated because installed services are unknown."
                        ),
                    )
                    continue

                service = _service_named(target.id, self.context.installed_services)
                if service is not None:
                    self._add_evidence(
                        check_type=CompatibilityCheckType.RELATIONSHIP,
                        subject=subject,
                        status=CompatibilityStatus.COMPATIBLE,
                        message=f"Required relationship target '{relationship.target}' is observed.",
                        source="compatibility_context",
                        requirement=relationship.target,
                        observed=target.id,
                        observed_fact_id=_fact_id("service", target.id),
                    )
                    self._evaluate_version_bounds(relationship, target, service)
                else:
                    self._incompatible(
                        check_type=CompatibilityCheckType.RELATIONSHIP,
                        subject=subject,
                        requirement=relationship.target,
                        observed="not observed",
                        message=f"Required relationship target '{relationship.target}' is not observed.",
                        observed_fact_id=_fact_id("service", target.id),
                    )
            elif relationship.type is DiscoveryRelationshipType.CONFLICTS_WITH:
                if self.context.installed_services is None:
                    self._unknown(
                        check_type=CompatibilityCheckType.RELATIONSHIP,
                        subject=subject,
                        requirement=f"absence of {relationship.target}",
                        fact_name="installed_services",
                        message=(
                            f"Conflict relationship target '{relationship.target}' "
                            "cannot be evaluated because installed services are unknown."
                        ),
                    )
                elif _service_present(target.id, self.context.installed_services):
                    self._incompatible(
                        check_type=CompatibilityCheckType.RELATIONSHIP,
                        subject=subject,
                        requirement=f"absence of {relationship.target}",
                        observed=target.id,
                        message=f"Conflicting relationship target '{relationship.target}' is observed.",
                        observed_fact_id=_fact_id("service", target.id),
                    )
                else:
                    self._add_evidence(
                        check_type=CompatibilityCheckType.RELATIONSHIP,
                        subject=subject,
                        status=CompatibilityStatus.COMPATIBLE,
                        message=f"Conflicting target '{relationship.target}' is not observed.",
                        source="compatibility_context",
                        requirement=f"absence of {relationship.target}",
                        observed="not observed",
                        observed_fact_id=_fact_id("service", target.id),
                    )

    def _evaluate_version_bounds(
        self,
        relationship: DiscoveryRelationship,
        target: DiscoveryItem,
        service: ObservedService,
    ) -> None:
        minimum = relationship.minimum_version
        maximum = relationship.maximum_version
        if minimum is None and maximum is None:
            return

        subject = f"relationships.{relationship.type}.{relationship.target}.version"
        fact_name = _fact_id("installed_version", target.id)
        requirement = _version_bound_requirement(minimum, maximum)
        version_key = installed_version_key(service)
        minimum_key = (
            parse_strict_numeric_version(minimum) if minimum is not None else None
        )
        maximum_key = (
            parse_strict_numeric_version(maximum) if maximum is not None else None
        )
        if (
            version_key is None
            or (minimum is not None and minimum_key is None)
            or (maximum is not None and maximum_key is None)
        ):
            self._unknown(
                check_type=CompatibilityCheckType.VERSION,
                subject=subject,
                requirement=requirement,
                fact_name=fact_name,
                message=(
                    f"Version bounds {requirement} for required relationship target "
                    f"'{relationship.target}' cannot be evaluated because a version "
                    "is missing or not a strict numeric X.Y.Z version."
                ),
            )
            return

        if minimum_key is not None and version_key < minimum_key:
            self._incompatible(
                check_type=CompatibilityCheckType.VERSION,
                subject=subject,
                requirement=requirement,
                observed=service.installed_version,
                message=(
                    f"Observed installed version '{service.installed_version}' "
                    f"is below required minimum version '{minimum}'."
                ),
                observed_fact_id=fact_name,
            )
        elif maximum_key is not None and version_key > maximum_key:
            self._incompatible(
                check_type=CompatibilityCheckType.VERSION,
                subject=subject,
                requirement=requirement,
                observed=service.installed_version,
                message=(
                    f"Observed installed version '{service.installed_version}' "
                    f"is above required maximum version '{maximum}'."
                ),
                observed_fact_id=fact_name,
            )
        else:
            self._add_evidence(
                check_type=CompatibilityCheckType.VERSION,
                subject=subject,
                status=CompatibilityStatus.COMPATIBLE,
                message=(
                    f"Observed installed version '{service.installed_version}' "
                    f"satisfies version bounds {requirement}."
                ),
                source="compatibility_context",
                requirement=requirement,
                observed=service.installed_version,
                observed_fact_id=fact_name,
            )

    def _evaluate_minimum(
        self,
        *,
        check_type: CompatibilityCheckType,
        subject: str,
        requirement: float | None,
        observed: float | None,
        fact_name: str,
        unit: str,
    ) -> None:
        if requirement is None:
            return
        if observed is None:
            self._unknown(
                check_type=check_type,
                subject=subject,
                requirement=f"{requirement:g} {unit}",
                fact_name=fact_name,
                message=(
                    f"Requirement {subject} cannot be evaluated because "
                    f"observed {fact_name} is unknown."
                ),
            )
        elif observed >= requirement:
            self._add_evidence(
                check_type=check_type,
                subject=subject,
                status=CompatibilityStatus.COMPATIBLE,
                message=f"Observed {observed:g} {unit} satisfies required {requirement:g} {unit}.",
                source="compatibility_context",
                requirement=f"{requirement:g} {unit}",
                observed=f"{observed:g} {unit}",
                observed_fact_id=fact_name,
            )
        else:
            self._incompatible(
                check_type=check_type,
                subject=subject,
                requirement=f"{requirement:g} {unit}",
                observed=f"{observed:g} {unit}",
                message=f"Observed {observed:g} {unit} is below required {requirement:g} {unit}.",
                observed_fact_id=fact_name,
            )

    def _evaluate_allowed_values(
        self,
        *,
        subject: str,
        required: tuple[str, ...],
        observed: str | None,
        fact_name: str,
    ) -> None:
        if not required:
            return
        if observed is None:
            self._unknown(
                check_type=CompatibilityCheckType.PLATFORM,
                subject=subject,
                requirement=", ".join(required),
                fact_name=fact_name,
                message=f"Requirement {subject} cannot be evaluated because {fact_name} is unknown.",
            )
        elif observed in required:
            self._add_evidence(
                check_type=CompatibilityCheckType.PLATFORM,
                subject=subject,
                status=CompatibilityStatus.COMPATIBLE,
                message=f"Observed {fact_name} '{observed}' is allowed.",
                source="compatibility_context",
                requirement=", ".join(required),
                observed=observed,
                observed_fact_id=fact_name,
            )
        else:
            self._incompatible(
                check_type=CompatibilityCheckType.PLATFORM,
                subject=subject,
                requirement=", ".join(required),
                observed=observed,
                message=f"Observed {fact_name} '{observed}' is not allowed.",
                observed_fact_id=fact_name,
            )

    def _evaluate_required_set(
        self,
        *,
        subject: str,
        required: tuple[str, ...],
        observed: tuple[str, ...] | None,
        fact_name: str,
    ) -> None:
        if not required:
            return
        if observed is None:
            self._unknown(
                check_type=CompatibilityCheckType.PLATFORM,
                subject=subject,
                requirement=", ".join(required),
                fact_name=fact_name,
                message=f"Requirement {subject} cannot be evaluated because {fact_name} are unknown.",
            )
            return

        for required_value in required:
            value_subject = f"{subject}.{required_value}"
            if required_value in observed:
                self._add_evidence(
                    check_type=CompatibilityCheckType.PLATFORM,
                    subject=value_subject,
                    status=CompatibilityStatus.COMPATIBLE,
                    message=f"Required {fact_name} value '{required_value}' is present.",
                    source="compatibility_context",
                    requirement=required_value,
                    observed=required_value,
                    observed_fact_id=_fact_id(fact_name.rstrip("s"), required_value),
                )
            else:
                self._incompatible(
                    check_type=CompatibilityCheckType.PLATFORM,
                    subject=value_subject,
                    requirement=required_value,
                    observed=", ".join(observed) if observed else "none",
                    message=f"Required {fact_name} value '{required_value}' is not present.",
                    observed_fact_id=_fact_id(fact_name.rstrip("s"), required_value),
                )

    def _unknown(
        self,
        *,
        check_type: CompatibilityCheckType,
        subject: str,
        requirement: str,
        fact_name: str,
        message: str,
    ) -> None:
        self.unknown_facts.add(fact_name)
        evidence = self._add_evidence(
            check_type=check_type,
            subject=subject,
            status=CompatibilityStatus.INSUFFICIENT_INFORMATION,
            message=message,
            source="compatibility_context",
            requirement=requirement,
            observed="unknown",
            observed_fact_id=fact_name,
        )
        self._add_finding(
            check_type=check_type,
            severity=CompatibilityFindingSeverity.UNKNOWN,
            status=CompatibilityStatus.INSUFFICIENT_INFORMATION,
            subject=subject,
            message=message,
            evidence_ids=(evidence.id,),
        )

    def _incompatible(
        self,
        *,
        check_type: CompatibilityCheckType,
        subject: str,
        requirement: str,
        observed: str,
        message: str,
        observed_fact_id: str | None = None,
    ) -> None:
        evidence = self._add_evidence(
            check_type=check_type,
            subject=subject,
            status=CompatibilityStatus.INCOMPATIBLE,
            message=message,
            source="compatibility_context",
            requirement=requirement,
            observed=observed,
            observed_fact_id=observed_fact_id,
        )
        self._add_finding(
            check_type=check_type,
            severity=CompatibilityFindingSeverity.BLOCKER,
            status=CompatibilityStatus.INCOMPATIBLE,
            subject=subject,
            message=message,
            evidence_ids=(evidence.id,),
        )

    def _add_evidence(
        self,
        *,
        check_type: CompatibilityCheckType,
        subject: str,
        status: CompatibilityStatus,
        message: str,
        source: str,
        requirement: str | None = None,
        observed: str | None = None,
        observed_fact_id: str | None = None,
    ) -> CompatibilityEvidence:
        evidence = CompatibilityEvidence(
            id=f"e{len(self.evidence) + 1:04d}",
            check_type=check_type,
            subject=subject,
            status=status,
            message=message,
            source=source,
            requirement=requirement,
            observed=observed,
            observed_fact_id=observed_fact_id,
        )
        self.evidence.append(evidence)
        return evidence

    def _add_finding(
        self,
        *,
        check_type: CompatibilityCheckType,
        severity: CompatibilityFindingSeverity,
        status: CompatibilityStatus,
        subject: str,
        message: str,
        evidence_ids: tuple[str, ...],
    ) -> CompatibilityFinding:
        finding = CompatibilityFinding(
            id=f"f{len(self.findings) + 1:04d}",
            check_type=check_type,
            severity=severity,
            status=status,
            subject=subject,
            message=message,
            evidence_ids=evidence_ids,
        )
        self.findings.append(finding)
        return finding


def _aggregate_status(
    findings: Iterable[CompatibilityFinding],
) -> CompatibilityStatus:
    statuses = tuple(finding.status for finding in findings)
    if CompatibilityStatus.INCOMPATIBLE in statuses:
        return CompatibilityStatus.INCOMPATIBLE
    if CompatibilityStatus.INSUFFICIENT_INFORMATION in statuses:
        return CompatibilityStatus.INSUFFICIENT_INFORMATION
    if CompatibilityStatus.COMPATIBLE_WITH_WARNINGS in statuses:
        return CompatibilityStatus.COMPATIBLE_WITH_WARNINGS
    return CompatibilityStatus.COMPATIBLE


def _normalize_unique_strings(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        candidates = [value]
    else:
        candidates = list(value)

    normalized = []
    for candidate in candidates:
        if not isinstance(candidate, str):
            raise TypeError("values must be strings.")
        item = candidate.strip().lower()
        if item and item not in normalized:
            normalized.append(item)
    return tuple(normalized)


def _fact_id(kind: str, value: str) -> str:
    return f"{kind}:{value}"


def _version_bound_requirement(
    minimum: str | None,
    maximum: str | None,
) -> str:
    bounds = []
    if minimum is not None:
        bounds.append(f">={minimum}")
    if maximum is not None:
        bounds.append(f"<={maximum}")
    return " ".join(bounds)


def _service_named(
    item_id: str,
    services: tuple[ObservedService, ...],
) -> ObservedService | None:
    return next((service for service in services if service.id == item_id), None)


def _service_present(
    item_id: str,
    services: tuple[ObservedService, ...],
) -> bool:
    return any(service.id == item_id for service in services)
