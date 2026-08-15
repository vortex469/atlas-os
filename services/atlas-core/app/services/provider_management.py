"""Read-only provider-management projection over existing provider adapters."""

from __future__ import annotations

import hashlib
import json
import re

from app.models.provider_management import (
    ManagedResourceIdentityAssurance,
    ManagedResourceProjection,
    ProviderManagementDescriptor,
    ProviderManagementSection,
    ProviderManagementSectionAvailability,
    ProviderManagementSectionDescriptor,
)
from app.models.resources import ProviderResource
from app.providers.capabilities import ProviderCapability
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


def _management_fingerprint(resource: ProviderResource) -> str | None:
    identity = resource.identity
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
) -> ManagedResourceIdentityAssurance:
    if resource.provider_id != "proxmox":
        return ManagedResourceIdentityAssurance.UNSUPPORTED
    if resource.resource_type == "lxc":
        return ManagedResourceIdentityAssurance.UNAVAILABLE
    if resource.resource_type != "qemu":
        return ManagedResourceIdentityAssurance.UNSUPPORTED
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
) -> ManagedResourceProjection:
    """Allow-list management fields and keep native identity opaque."""

    return ManagedResourceProjection(
        provider_id=resource.provider_id,
        resource_id=resource.resource_id,
        resource_type=resource.resource_type,
        display_name=resource.display_name,
        current_state=resource.current_state,
        missing=resource.missing,
        identity_assurance=_identity_assurance(resource),
        management_fingerprint=_management_fingerprint(resource),
    )


async def get_provider_management_descriptor(
    provider_id: str,
) -> ProviderManagementDescriptor:
    """Describe management surfaces without granting mutation or execution."""

    provider = get_provider(provider_id)
    capabilities = provider.metadata.capabilities
    resources: tuple[ManagedResourceProjection, ...] = ()
    if isinstance(provider, ProviderResourceAdapter):
        collection = await list_provider_resources(provider_id)
        resources = tuple(
            project_managed_resource(resource)
            for resource in collection.resources
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
        resources=resources,
    )
