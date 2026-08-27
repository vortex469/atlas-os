"""Frozen restricted canonical-JSON fingerprint domains for P1.

This is deliberately not a general RFC 8785 implementation. For P1's closed
domain (NFC strings, null, booleans, safe integers, lists, and string-keyed objects),
compact UTF-8 JSON with lexicographically sorted fixed ASCII keys produces the
frozen bytes required by the P0 contract.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata

from app.installation_targets.contract import InstallationDestinationSelectionV1

REQUEST_DOMAIN = "atlas:installation-destination-selection-request:v1"
SELECTION_DOMAIN = "atlas:installation-destination-selection:v1"
DESTINATION_DOMAIN = "atlas:prospective-installation-destination:v1"
ENUMERATION_DOMAIN = "atlas:prospective-installation-destination-enumeration:v1"


def _canonical_hash(domain: str, value: dict[str, object], keys: frozenset[str]) -> str:
    """Hash the deliberately restricted P1 canonical-JSON subset."""
    if not domain.isascii() or "\0" in domain:
        raise ValueError("invalid fingerprint domain")

    def validate(item: object) -> None:
        if item is None or isinstance(item, bool):
            return
        if isinstance(item, int):
            if not -(2**53) + 1 <= item <= 2**53 - 1:
                raise ValueError("canonical integers must be IEEE-754 safe integers")
            return
        if isinstance(item, str):
            if item != unicodedata.normalize("NFC", item):
                raise ValueError("canonical strings must be NFC")
            if any(
                ord(character) < 0x20 or 0xD800 <= ord(character) <= 0xDFFF
                for character in item
            ):
                raise ValueError("canonical strings must be valid printable UTF-8 text")
            return
        if isinstance(item, list):
            for child in item:
                validate(child)
            return
        if isinstance(item, dict):
            if any(not isinstance(key, str) or not key.isascii() for key in item):
                raise TypeError("canonical object keys must be ASCII strings")
            for key, child in item.items():
                validate(key)
                validate(child)
            return
        raise TypeError("value is outside the restricted JCS domain")

    if type(value) is not dict or set(value) != keys:
        raise ValueError("canonical object does not match its closed domain")
    validate(value)
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(domain.encode("ascii") + b"\0" + encoded).hexdigest()


def build_destination_fingerprint(
    *, resource_id: str, operational_fingerprint: str
) -> str:
    return _canonical_hash(
        DESTINATION_DOMAIN,
        {
            "placement_kind": "existing-guest",
            "provider": "proxmox",
            "resource_id": resource_id,
            "resource_type": "qemu",
            "operational_fingerprint": operational_fingerprint,
        },
        frozenset(
            {
                "placement_kind",
                "provider",
                "resource_id",
                "resource_type",
                "operational_fingerprint",
            }
        ),
    )


def build_enumeration_token(*, resource_id: str, destination_fingerprint: str) -> str:
    return _canonical_hash(
        ENUMERATION_DOMAIN,
        {
            "destination_fingerprint": destination_fingerprint,
            "placement_kind": "existing-guest",
            "provider": "proxmox",
            "resource_id": resource_id,
            "resource_type": "qemu",
        },
        frozenset(
            {
                "destination_fingerprint",
                "placement_kind",
                "provider",
                "resource_id",
                "resource_type",
            }
        ),
    )


def build_request_digest(
    *,
    selected_by: str,
    enumeration_token: str,
    resource_id: str,
    destination_fingerprint: str,
    idempotency_key: str,
) -> str:
    return _canonical_hash(
        REQUEST_DOMAIN,
        {
            "schema_version": "installation-destination-selection-v1",
            "selected_by": selected_by,
            "enumeration_token": enumeration_token,
            "provider": "proxmox",
            "resource_type": "qemu",
            "placement_kind": "existing-guest",
            "resource_id": resource_id,
            "selected_destination_fingerprint": destination_fingerprint,
            "idempotency_key": idempotency_key,
        },
        frozenset(
            {
                "schema_version",
                "selected_by",
                "enumeration_token",
                "provider",
                "resource_type",
                "placement_kind",
                "resource_id",
                "selected_destination_fingerprint",
                "idempotency_key",
            }
        ),
    )


def build_selection_fingerprint(record: InstallationDestinationSelectionV1) -> str:
    return _canonical_hash(
        SELECTION_DOMAIN,
        {
            "schema_version": record.schema_version,
            "selection_id": record.selection_id,
            "provider": record.provider,
            "resource_type": record.resource_type,
            "placement_kind": record.placement_kind,
            "resource_id": record.resource_id,
            "selected_destination_fingerprint": record.selected_destination_fingerprint,
            "selected_at": record.selected_at,
            "expires_at": record.expires_at,
            "selected_by": record.selected_by,
            "request_digest": record.request_digest,
        },
        frozenset(
            {
                "schema_version",
                "selection_id",
                "provider",
                "resource_type",
                "placement_kind",
                "resource_id",
                "selected_destination_fingerprint",
                "selected_at",
                "expires_at",
                "selected_by",
                "request_digest",
            }
        ),
    )
