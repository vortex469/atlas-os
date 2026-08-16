"""Read-only provider-management projection over existing provider adapters."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path

from app.config.settings import settings
from app.models.provider_intents import (
    PROVIDER_INTENT_STORE_P2C_SCHEMA_VERSION,
    PROVIDER_INTENT_STORE_SCHEMA_VERSION,
)
from app.models.provider_management import (
    ManagedResourceIdentityAssurance,
    ManagedResourceProjection,
    ManagedResourceProjectionV3,
    ProviderIntentMutationReadiness,
    ProviderIntentReadAuthority,
    ProviderIntentReadReason,
    ProviderIntentReadStatus,
    ProviderManagementDescriptor,
    ProviderManagementDescriptorV3,
    ProviderManagementSection,
    ProviderManagementSectionAvailability,
    ProviderManagementSectionDescriptor,
    ProviderMonitoringExpectation,
    ProviderResourceManagementSupport,
    ProviderResourceManagementSupportV3,
)
from app.models.resources import ProviderResource
from app.provider_intents.store import ProviderIntentStore, ProviderIntentStoreError
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


def _mutation_store_readiness(
    database: Path,
) -> ProviderIntentMutationReadiness:
    if database.is_symlink() or not database.is_file():
        return ProviderIntentMutationReadiness.STORE_UNAVAILABLE
    try:
        with sqlite3.connect(
            f"file:{database.resolve()}?mode=ro", uri=True
        ) as connection:
            connection.execute("PRAGMA query_only=ON")
            row = connection.execute(
                "SELECT schema_version FROM provider_intent_store_meta "
                "WHERE singleton=1"
            ).fetchone()
    except (OSError, sqlite3.Error):
        return ProviderIntentMutationReadiness.STORE_UNAVAILABLE
    if row is None:
        return ProviderIntentMutationReadiness.STORE_UNAVAILABLE
    if row[0] == PROVIDER_INTENT_STORE_SCHEMA_VERSION:
        try:
            ProviderIntentStore.open_existing(database)
        except (OSError, ValueError, ProviderIntentStoreError):
            return ProviderIntentMutationReadiness.STORE_UNAVAILABLE
        return ProviderIntentMutationReadiness.READY
    if row[0] == PROVIDER_INTENT_STORE_P2C_SCHEMA_VERSION:
        return ProviderIntentMutationReadiness.STORE_MIGRATION_REQUIRED
    return ProviderIntentMutationReadiness.STORE_UNAVAILABLE


def _resource_mutation_readiness(
    resource: ManagedResourceProjection,
    *,
    mutation_supported: bool,
    descriptor: ProviderManagementDescriptor,
    store_readiness: ProviderIntentMutationReadiness,
) -> ProviderIntentMutationReadiness:
    if not mutation_supported:
        return ProviderIntentMutationReadiness.RESOURCE_TYPE_UNSUPPORTED
    if resource.missing:
        return ProviderIntentMutationReadiness.RESOURCE_MISSING
    if (
        resource.identity_assurance
        is not ManagedResourceIdentityAssurance.AUTHORITATIVE
    ):
        return ProviderIntentMutationReadiness.IDENTITY_UNAVAILABLE
    if descriptor.provider_intent_activation != "activated":
        return ProviderIntentMutationReadiness.NOT_ACTIVATED
    if descriptor.provider_intent_authority_status != "available":
        return ProviderIntentMutationReadiness.AUTHORITY_UNAVAILABLE
    return store_readiness


async def get_authenticated_provider_management_descriptor(
    provider_id: str,
    *,
    caller_has_provider_intent_update: bool,
    provider_intent_database: Path | None = None,
    registry: ProviderResourceManagementRegistry = (
        provider_resource_management_registry
    ),
) -> ProviderManagementDescriptorV3:
    """Project authenticated edit readiness without granting authority."""

    descriptor = await get_provider_management_descriptor(
        provider_id, registry=registry
    )
    store_readiness = (
        _mutation_store_readiness(
            provider_intent_database
            or Path(settings.provider_intents.database)
        )
        if descriptor.provider_intent_activation == "activated"
        and descriptor.provider_intent_authority_status == "available"
        else ProviderIntentMutationReadiness.STORE_UNAVAILABLE
    )
    support_by_type = {
        support.resource_type: support for support in descriptor.resource_types
    }
    resources: list[ManagedResourceProjectionV3] = []
    for resource in descriptor.resources:
        support = support_by_type.get(resource.resource_type)
        mutation_supported = bool(
            provider_id == "proxmox"
            and resource.resource_type == "qemu"
            and support is not None
            and support.provider_intent_capability_supported
            and support.authoritative_identity_supported
        )
        readiness = _resource_mutation_readiness(
            resource,
            mutation_supported=mutation_supported,
            descriptor=descriptor,
            store_readiness=store_readiness,
        )
        caller_can_mutate = bool(
            caller_has_provider_intent_update
            and readiness is ProviderIntentMutationReadiness.READY
        )
        resources.append(
            ManagedResourceProjectionV3(
                **resource.model_dump(exclude={"mutation_available"}),
                resource_live=not resource.missing,
                provider_intent_mutation_supported=mutation_supported,
                mutation_readiness=readiness,
                editable_in_principle=(
                    readiness is ProviderIntentMutationReadiness.READY
                ),
                caller_can_mutate=caller_can_mutate,
            )
        )

    return ProviderManagementDescriptorV3(
        provider_id=descriptor.provider_id,
        provider_name=descriptor.provider_name,
        sections=descriptor.sections,
        resource_types=tuple(
            ProviderResourceManagementSupportV3(
                **support.model_dump(
                    exclude={"provider_intent_mutation_available"}
                ),
                provider_intent_mutation_supported=bool(
                    provider_id == "proxmox"
                    and support.resource_type == "qemu"
                    and support.provider_intent_capability_supported
                    and support.authoritative_identity_supported
                ),
            )
            for support in descriptor.resource_types
        ),
        resources=tuple(resources),
        provider_intent_activation=descriptor.provider_intent_activation,
        provider_intent_authority_status=(
            descriptor.provider_intent_authority_status
        ),
        caller_has_provider_intent_update=caller_has_provider_intent_update,
    )
