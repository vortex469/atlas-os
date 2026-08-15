"""Single Proxmox monitoring-intent authority selection boundary."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from threading import Lock

from app.config import policies as policy_config
from app.config.resource_policies import update_proxmox_guest_expectation
from app.config.settings import (
    ProviderIntentActivation,
    ProviderIntentSettings,
)
from app.config.settings import (
    settings as atlas_settings,
)
from app.models.provider_management import ManagedResourceProjection
from app.models.resources import (
    ProviderExpectationOption,
    ProviderResource,
    ProviderResourceCollection,
    ProviderResourceExpectation,
    ProviderResourceSummary,
    ResourceIntentAuthority,
    ResourceIntentReason,
)
from app.provider_intents.resolver import (
    ProviderIntentResolution,
    ProviderIntentResolutionSet,
    ProviderIntentResolutionStatus,
    ProviderMonitoringIntentResolver,
)
from app.provider_intents.store import ProviderIntentStore


class ProviderIntentMutationUnavailableError(RuntimeError):
    """Legacy policy writes are unavailable while Provider Intent is active."""


@dataclass(frozen=True, slots=True)
class ProxmoxMonitoringIntentSnapshot:
    """One normalized authority result for an intelligence collection pass."""

    activation: ProviderIntentActivation
    legacy_expectations: tuple[tuple[str, str], ...] = ()
    provider_intent_resolution: ProviderIntentResolutionSet | None = None

    def __post_init__(self) -> None:
        inactive = self.activation is ProviderIntentActivation.NOT_ACTIVATED
        if inactive != (self.provider_intent_resolution is None):
            raise ValueError("monitoring authority snapshot sources contradict")
        if not inactive and self.legacy_expectations:
            raise ValueError("activated authority cannot carry legacy expectations")


class ProxmoxMonitoringIntentAuthority:
    """Select exactly one monitoring authority for a complete collection pass."""

    def __init__(
        self,
        settings: ProviderIntentSettings,
        store: ProviderIntentStore | None = None,
    ) -> None:
        self.settings = settings
        self._resolver = ProviderMonitoringIntentResolver(settings, store)

    @property
    def activation(self) -> ProviderIntentActivation:
        return self.settings.activation

    def list_guest_expectations(self) -> dict[str, object]:
        """Compatibility read available only behind inactive authority selection."""

        if self.activation is ProviderIntentActivation.ACTIVATED:
            return {}
        return dict(policy_config.load_policies().proxmox.guests)

    def update_guest_expectation(self, resource_id: str, expectation: str) -> str:
        self.require_legacy_mutation_available()
        return update_proxmox_guest_expectation(resource_id, expectation)

    def require_legacy_mutation_available(self) -> None:
        """Reject the legacy write boundary without creating action evidence."""

        if self.activation is ProviderIntentActivation.ACTIVATED:
            raise ProviderIntentMutationUnavailableError(
                "Provider Intent mutation is unavailable until P3."
            )

    def resolve_collection(
        self,
        collection: ProviderResourceCollection,
    ) -> ProviderResourceCollection:
        if collection.provider_id != "proxmox":
            return collection
        if self.activation is ProviderIntentActivation.NOT_ACTIVATED:
            return self._resolve_legacy_collection(collection)

        from app.services.provider_management import project_managed_resource

        resolution = self._resolver.resolve(
            tuple(project_managed_resource(item) for item in collection.resources)
        )
        resources_by_key = {
            (item.provider_id, item.resource_type, item.resource_id): item
            for item in collection.resources
        }
        resources: list[ProviderResource] = []
        for item in resolution.resources:
            key = (item.provider_id, item.resource_type, item.resource_id)
            resource = resources_by_key.get(key)
            if resource is None:
                resource = ProviderResource(
                    provider_id=item.provider_id,
                    resource_id=item.resource_id,
                    display_name=f"Missing Proxmox QEMU {item.resource_id}",
                    resource_type=item.resource_type,
                    current_state="missing",
                    expectation=ProviderResourceExpectation(),
                    configured=False,
                    missing=True,
                )
            resources.append(
                resource.model_copy(
                    update={
                        "expectation": _provider_intent_expectation(
                            item,
                            resource.expectation.allowed_values,
                        )
                    },
                )
            )
        resources = [ProviderResource.model_validate(item.model_dump()) for item in resources]
        return collection.model_copy(
            update={
                "resources": resources,
                "summary": _resource_summary(resources),
                "intent_authority": ResourceIntentAuthority.PROVIDER_INTENT,
                "intent_authority_status": (
                    "available" if resolution.authority_available else "unavailable"
                ),
            }
        )

    def resolve_projections(
        self,
        projections: tuple[ManagedResourceProjection, ...],
    ) -> ProviderIntentResolutionSet:
        """Resolve one already-sanitized pass for intelligence consumers."""

        if self.activation is ProviderIntentActivation.NOT_ACTIVATED:
            raise RuntimeError("inactive monitoring authority uses legacy policy")
        return self._resolver.resolve(projections)

    def resolve_intelligence(
        self,
        projections: tuple[ManagedResourceProjection, ...],
    ) -> ProxmoxMonitoringIntentSnapshot:
        """Resolve exactly one source without exposing selection to consumers."""

        if self.activation is ProviderIntentActivation.NOT_ACTIVATED:
            legacy = tuple(
                sorted(
                    (
                        (str(vmid), _legacy_value(policy))
                        for vmid, policy in self.list_guest_expectations().items()
                    ),
                    key=lambda item: item[0],
                )
            )
            return ProxmoxMonitoringIntentSnapshot(
                activation=self.activation,
                legacy_expectations=legacy,
            )
        return ProxmoxMonitoringIntentSnapshot(
            activation=self.activation,
            provider_intent_resolution=self._resolver.resolve(projections),
        )

    def _resolve_legacy_collection(
        self,
        collection: ProviderResourceCollection,
    ) -> ProviderResourceCollection:
        configured = {
            str(vmid): _legacy_value(policy)
            for vmid, policy in self.list_guest_expectations().items()
        }
        seen = {item.resource_id for item in collection.resources}
        resources = [
            item.model_copy(
                update={
                    "expectation": _legacy_expectation(
                        configured.get(item.resource_id),
                        item.expectation.allowed_values,
                    )
                }
            )
            for item in collection.resources
        ]
        resources.extend(
            ProviderResource(
                provider_id="proxmox",
                resource_id=resource_id,
                display_name=f"Missing Proxmox guest {resource_id}",
                resource_type="unknown",
                current_state="missing",
                expectation=_legacy_expectation(expectation),
                configured=True,
                missing=True,
                metadata={"vmid": _metadata_vmid(resource_id)},
            )
            for resource_id, expectation in configured.items()
            if resource_id not in seen
        )
        resources = [ProviderResource.model_validate(item.model_dump()) for item in resources]
        resources.sort(key=lambda item: _resource_sort_key(item.resource_id))
        return collection.model_copy(
            update={
                "resources": resources,
                "summary": _resource_summary(resources),
                "intent_authority": ResourceIntentAuthority.LEGACY_POLICY,
                "intent_authority_status": "available",
            }
        )


def _legacy_value(value: object) -> str:
    return str(getattr(value, "expected", value))


def _legacy_expectation(
    value: str | None,
    allowed_values: list[ProviderExpectationOption] | None = None,
) -> ProviderResourceExpectation:
    if value is None:
        return ProviderResourceExpectation(allowed_values=allowed_values or [])
    return ProviderResourceExpectation(
        value=value,
        label={
            "running": "Expected Running",
            "stopped": "Expected Stopped",
            "ignored": "Ignore",
        }.get(value, value),
        state="ignored" if value == "ignored" else "configured",
        authority=ResourceIntentAuthority.LEGACY_POLICY,
        reason=ResourceIntentReason.LEGACY_POLICY_MATCH,
        allowed_values=allowed_values or [],
    )


def _provider_intent_expectation(
    resolution: ProviderIntentResolution,
    allowed_values: list[ProviderExpectationOption],
) -> ProviderResourceExpectation:
    state = {
        ProviderIntentResolutionStatus.CONFIGURED: (
            "ignored" if resolution.expectation and resolution.expectation.value == "ignored" else "configured"
        ),
        ProviderIntentResolutionStatus.MISSING: "configured",
        ProviderIntentResolutionStatus.NEEDS_REVIEW: "needs_review",
        ProviderIntentResolutionStatus.UNSUPPORTED: "unsupported",
        ProviderIntentResolutionStatus.UNAVAILABLE: "unavailable",
    }[resolution.status]
    reason = ResourceIntentReason(resolution.reason.value)
    value = resolution.expectation.value if resolution.expectation is not None else None
    return ProviderResourceExpectation(
        value=value,
        label=(
            {"running": "Expected Running", "stopped": "Expected Stopped", "ignored": "Ignore"}.get(value, value)
            if value is not None
            else {
                "unsupported": "Unsupported",
                "unavailable": "Authority Unavailable",
            }.get(state, "Needs Review")
        ),
        state=state,
        authority=ResourceIntentAuthority.PROVIDER_INTENT,
        reason=reason,
        record_version=resolution.record_version,
        legacy_review_available=resolution.legacy_review_available,
        legacy_expectation=(
            resolution.legacy_expectation.value
            if resolution.legacy_expectation is not None
            else None
        ),
        replacement_detected=resolution.replacement_detected,
        allowed_values=allowed_values,
    )


def _resource_summary(resources: list[ProviderResource]) -> ProviderResourceSummary:
    by_type = Counter(item.resource_type for item in resources)
    by_state = Counter(item.current_state for item in resources)
    return ProviderResourceSummary(
        total=len(resources),
        configured=sum(item.configured for item in resources),
        needs_review=sum(item.needs_review for item in resources),
        missing=sum(item.missing for item in resources),
        ignored=sum(item.expectation.state == "ignored" for item in resources),
        by_type=dict(sorted(by_type.items())),
        by_state=dict(sorted(by_state.items())),
    )


def _resource_sort_key(resource_id: str) -> tuple[int, int | str]:
    return (0, int(resource_id)) if resource_id.isdigit() else (1, resource_id)


def _metadata_vmid(resource_id: str) -> int | str:
    return int(resource_id) if resource_id.isdigit() else resource_id


_authority_lock = Lock()
_authority: ProxmoxMonitoringIntentAuthority | None = None


def configure_monitoring_intent_authority(
    settings: ProviderIntentSettings,
    store: ProviderIntentStore | None,
) -> ProxmoxMonitoringIntentAuthority:
    global _authority
    authority = ProxmoxMonitoringIntentAuthority(settings, store)
    with _authority_lock:
        _authority = authority
    return authority


def get_monitoring_intent_authority() -> ProxmoxMonitoringIntentAuthority:
    global _authority
    with _authority_lock:
        if _authority is None:
            _authority = ProxmoxMonitoringIntentAuthority(
                atlas_settings.provider_intents
            )
        return _authority
