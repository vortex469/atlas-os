"""Closed, immutable P1 destination and selection contracts."""

from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

DESTINATION_SCHEMA_VERSION = "prospective-installation-destination-v1"
SELECTION_SCHEMA_VERSION = "installation-destination-selection-v1"
SELECTION_LIFETIME = timedelta(hours=24)

_HEX64 = re.compile(r"[0-9a-f]{64}")
_UUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)
_UTC = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
_SAFE_ID = re.compile(r"[A-Za-z0-9._@:-]+")
_QEMU_RESOURCE_ID = re.compile(r"[1-9][0-9]*")


def _nfc(value: str) -> str:
    if value != unicodedata.normalize("NFC", value):
        raise ValueError("string must be NFC normalized")
    return value


def _hex64(value: str) -> str:
    if not _HEX64.fullmatch(value):
        raise ValueError("lowercase SHA-256 hex required")
    return value


def _utc_second(value: str) -> str:
    if not _UTC.fullmatch(value):
        raise ValueError("exact UTC whole-second timestamp required")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as error:
        raise ValueError("exact UTC whole-second timestamp required") from error
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise ValueError("exact UTC whole-second timestamp required")
    return value


def _safe_id(value: str) -> str:
    _nfc(value)
    if not 1 <= len(value.encode()) <= 200 or not _SAFE_ID.fullmatch(value):
        raise ValueError("stable sanitized principal ID required")
    return value


def _qemu_resource_id(value: str) -> str:
    if not _QEMU_RESOURCE_ID.fullmatch(value):
        raise ValueError("positive decimal QEMU resource ID required")
    return value


def _uuid4(value: str) -> str:
    if not _UUID.fullmatch(value):
        raise ValueError("lowercase canonical UUIDv4 required")
    return value


LowerHex64 = Annotated[str, AfterValidator(_hex64)]
UtcSecond = Annotated[str, AfterValidator(_utc_second)]
PrincipalId = Annotated[str, AfterValidator(_safe_id)]
QemuResourceId = Annotated[
    str, Field(max_length=20), AfterValidator(_qemu_resource_id)
]
CanonicalUuid4 = Annotated[str, AfterValidator(_uuid4)]


class DestinationContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ProspectiveInstallationDestinationV1(DestinationContractModel):
    """Sanitized current QEMU identity; no readiness or capability claims."""

    schema_version: Literal["prospective-installation-destination-v1"] = (
        DESTINATION_SCHEMA_VERSION
    )
    provider: Literal["proxmox"] = "proxmox"
    resource_type: Literal["qemu"] = "qemu"
    placement_kind: Literal["existing-guest"] = "existing-guest"
    resource_id: QemuResourceId
    destination_fingerprint: LowerHex64
    enumeration_token: LowerHex64


class InstallationDestinationSelectionV1(DestinationContractModel):
    schema_version: Literal["installation-destination-selection-v1"] = (
        SELECTION_SCHEMA_VERSION
    )
    selection_id: CanonicalUuid4
    provider: Literal["proxmox"] = "proxmox"
    resource_type: Literal["qemu"] = "qemu"
    placement_kind: Literal["existing-guest"] = "existing-guest"
    resource_id: QemuResourceId
    selected_destination_fingerprint: LowerHex64
    selected_at: UtcSecond
    expires_at: UtcSecond
    selected_by: PrincipalId
    request_digest: LowerHex64
    selection_fingerprint: LowerHex64
    status: Literal["active", "cancelled", "expired", "stale"]
    terminated_at: UtcSecond | None

    @model_validator(mode="after")
    def validate_lifecycle(self) -> InstallationDestinationSelectionV1:
        selected = datetime.strptime(self.selected_at, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=UTC
        )
        expires = datetime.strptime(self.expires_at, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=UTC
        )
        if expires != selected + SELECTION_LIFETIME:
            raise ValueError("expires_at must be exactly 24 hours after selected_at")
        if (self.status == "active") != (self.terminated_at is None):
            raise ValueError("terminated_at must be null only while active")
        if self.terminated_at is not None:
            terminated = datetime.strptime(
                self.terminated_at, "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=UTC)
            if terminated < selected:
                raise ValueError("terminated_at must not be before selected_at")
        return self
