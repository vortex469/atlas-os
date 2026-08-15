"""Read-only provider-management projection over existing provider adapters."""

from __future__ import annotations

import hashlib
import json
import re

from app.models.provider_management import (
    ManagedResourceIdentityAssurance,
    ManagedResourceProjection,
    ProviderIntentReadAuthority,
    ProviderIntentReadReason,
    ProviderIntentReadStatus,
    ProviderManagementDescriptor,
    ProviderManagementSection,
    ProviderManagementSectionAvailability,
    ProviderManagementSectionDescriptor,
    ProviderMonitoringExpectation,
    ProviderResourceManagementSupport,
)
from app.models.resources import ProviderResource
from app.providers.capabilities import ProviderCapability
from app.providers.management import (
    ProviderResourceManagementNotRegisteredError,
    ProviderResourceManagementRegistry,
    provider_resource_management_registry,
)
from app.providers.proxmox_identity import PROXMOX_QEMU_IDENTITY_VERSION
from app.providers.resources import ProviderResourceAdapter
from app.services.provider_resources import get_provider, list_provider_resources

_FINGERPRINT_VERSION = "provider-management-fingerprint-v1"
_QEMU_IDENTITY_TOKEN = re.compile(
    rf"^{re.escape(PROXMOX_QEMU_IDENTITY_VERSION)}:[a-f0-9]{{64}}$"
)
_SECTIONS = tuple(ProviderManagementSection)
_SECTION_CAPABILITIES = {
    ProviderManagementSection.CONNECTION: ProviderCapability.CONNECTION,
    ProviderManagementSection.DISCOVERY: ProviderCapability.DISCOVERY,
    ProviderManagementSection.RESOURCES: ProviderCapability.RESOURCES,
    ProviderManagementSection.MONITORING: ProviderCapability.MONITORING,
    ProviderManagementSection.DIAGNOSTICS: ProviderCapability.DIAGNOSTICS,
    ProviderManagementSection.ACTIONS: ProviderCapability.ACTIONS,
}


def _management_fingerprint(
    resource: ProviderResource,
    support: ProviderResourceManagementSupport | None,
) -> str | None:
    identity = resource.identity
    if support is None or not support.authoritative_identity_supported:
        return None
    if resource.provider_id != "proxmox" or resource.resource_type != "qemu":
        return None
    if identity is None or not _has_authoritative_qemu_identity(resource):
        return None
    values = {
        "identity_token": identity.token,
        "identity_version": identity.token_version,
        "provider_id": resource.provider_id,
        "resource_type": resource.resource_type,
        "version": _FINGERPRINT_VERSION,
    }
    encoded = json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
    return f"{_FINGERPRINT_VERSION}:{hashlib.sha256(encoded).hexdigest()}"


def _identity_assurance(
    resource: ProviderResource,
    support: ProviderResourceManagementSupport | None,
) -> ManagedResourceIdentityAssurance:
    if support is None:
        return ManagedResourceIdentityAssurance.UNSUPPORTED
    if not support.authoritative_identity_supported:
        return ManagedResourceIdentityAssurance.UNAVAILABLE
    if not _has_authoritative_qemu_identity(resource):
        return ManagedResourceIdentityAssurance.UNAVAILABLE
    return ManagedResourceIdentityAssurance.AUTHORITATIVE


def _has_authoritative_qemu_identity(resource: ProviderResource) -> bool:
    identity = resource.identity
    return bool(
        resource.provider_id == "proxmox"
        and resource.resource_type == "qemu"
        and identity is not None
        and identity.token_version == PROXMOX_QEMU_IDENTITY_VERSION
        and _QEMU_IDENTITY_TOKEN.fullmatch(identity.token)
    )


def project_managed_resource(
    resource: ProviderResource,
    *,
    registry: ProviderResourceManagementRegistry = (
        provider_resource_management_registry
    ),
) -> ManagedResourceProjection:
    """Allow-list management fields and keep native identity opaque."""

    try:
        support = registry.get(resource.provider_id, resource.resource_type)
    except ProviderResourceManagementNotRegisteredError:
        support = None

    return ManagedResourceProjection(
        provider_id=resource.provider_id,
        resource_id=resource.resource_id,
        resource_type=resource.resource_type,
        display_name=resource.display_name,
        current_state=resource.current_state,
        missing=resource.missing,
        identity_assurance=_identity_assurance(resource, support),
        management_fingerprint=_management_fingerprint(resource, support),
        intent_authority=ProviderIntentReadAuthority(
            resource.expectation.authority.value
        ),
        intent_status=ProviderIntentReadStatus(
            "missing" if resource.missing else resource.expectation.state
        ),
        intent_reason=ProviderIntentReadReason(resource.expectation.reason.value),
        expectation=(
            ProviderMonitoringExpectation(resource.expectation.value)
            if resource.expectation.value is not None
            else None
        ),
        record_version=resource.expectation.record_version,
        legacy_review_available=resource.expectation.legacy_review_available,
        legacy_expectation=(
            ProviderMonitoringExpectation(resource.expectation.legacy_expectation)
            if resource.expectation.legacy_expectation is not None
            else None
        ),
        replacement_detected=resource.expectation.replacement_detected,
    )


async def get_provider_management_descriptor(
    provider_id: str,
    *,
    registry: ProviderResourceManagementRegistry = (
        provider_resource_management_registry
    ),
) -> ProviderManagementDescriptor:
    """Describe management surfaces without granting mutation or execution."""

    provider = get_provider(provider_id)
    capabilities = provider.metadata.capabilities
    resources: tuple[ManagedResourceProjection, ...] = ()
    if isinstance(provider, ProviderResourceAdapter):
        collection = await list_provider_resources(provider_id)
        resources = tuple(
            sorted(
                (
                    project_managed_resource(resource, registry=registry)
                    for resource in collection.resources
                ),
                key=lambda resource: (
                    resource.provider_id,
                    resource.resource_type,
                    resource.resource_id,
                ),
            )
        )

    return ProviderManagementDescriptor(
        provider_id=provider.metadata.id,
        provider_name=provider.metadata.name,
        sections=tuple(
            ProviderManagementSectionDescriptor(
                section=section,
                availability=(
                    ProviderManagementSectionAvailability.AVAILABLE
                    if _SECTION_CAPABILITIES[section] in capabilities
                    else ProviderManagementSectionAvailability.UNAVAILABLE
                ),
            )
            for section in _SECTIONS
        ),
        resource_types=registry.for_provider(provider_id),
        resources=resources,
        provider_intent_activation=(
            collection.intent_authority.value == "provider_intent"
            and "activated"
            or "not_activated"
        ) if isinstance(provider, ProviderResourceAdapter) else "not_activated",
        provider_intent_authority_status=(
            collection.intent_authority_status
            if isinstance(provider, ProviderResourceAdapter)
            else "available"
        ),
    )
