from __future__ import annotations

import hashlib
import json

from app.models.resources import ProviderResource
from app.providers.models import ProviderMetadata

OPERATIONAL_TARGET_FINGERPRINT_VERSION = "operational-target-fingerprint-v1"


class OperationalTargetIdentityUnavailableError(ValueError):
    """Raised when a resource has no provider-authoritative identity."""


def build_operational_target_fingerprint(
    provider: ProviderMetadata,
    resource: ProviderResource,
) -> str:
    """Fingerprint only controlled, provider-authoritative target identity."""

    identity = resource.identity
    if identity is None:
        raise OperationalTargetIdentityUnavailableError(
            "Resource has no provider-authoritative identity."
        )
    if resource.provider_id != provider.id:
        raise ValueError("Resource provider_id does not match provider metadata.")

    payload = {
        "fingerprint_version": OPERATIONAL_TARGET_FINGERPRINT_VERSION,
        "identity_token": identity.token,
        "identity_token_version": identity.token_version,
        "provider_id": provider.id,
        "provider_version": provider.version,
        "resource_id": resource.resource_id,
        "resource_type": resource.resource_type,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    return f"{OPERATIONAL_TARGET_FINGERPRINT_VERSION}:{digest}"
