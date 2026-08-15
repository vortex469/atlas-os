"""Explicit, non-authoritative import of legacy Proxmox policy evidence."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, ValidationError, model_validator
from yaml.nodes import MappingNode, Node, ScalarNode
from yaml.tokens import AliasToken, AnchorToken

from app.config.policy_models import Policies
from app.models.provider_intents import (
    LEGACY_POLICY_IMPORT_VERSION,
    ProviderIntentKind,
    ProviderIntentModel,
    ProviderIntentValue,
    build_legacy_policy_source_digest,
    build_legacy_policy_source_reference,
)
from app.provider_intents.store import ProviderIntentStore

_CANONICAL_VMID = re.compile(r"^[1-9][0-9]*$")


def _digest(prefix: str, payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return f"{prefix}:{hashlib.sha256(encoded).hexdigest()}"


class LegacyPolicyImportEntry(ProviderIntentModel):
    provider_id: Literal["proxmox"] = "proxmox"
    resource_id: str = Field(min_length=1, max_length=200)
    intent_kind: Literal[ProviderIntentKind.MONITORING_EXPECTATION] = (
        ProviderIntentKind.MONITORING_EXPECTATION
    )
    intent_value: ProviderIntentValue
    source_reference: str = Field(
        pattern=(
            r"^provider-intent-legacy-policy-source-reference-v1:[a-f0-9]{64}$"
        )
    )

    @model_validator(mode="after")
    def validate_entry(self) -> LegacyPolicyImportEntry:
        if not _CANONICAL_VMID.fullmatch(self.resource_id):
            raise ValueError("legacy Proxmox VMID must be a canonical positive integer")
        return self


class LegacyPolicyImportCommand(ProviderIntentModel):
    import_id: str = Field(
        pattern=r"^provider-intent-legacy-policy-import-v1:[a-f0-9]{64}$"
    )
    import_digest: str = Field(
        pattern=r"^provider-intent-legacy-policy-import-request-v1:[a-f0-9]{64}$"
    )
    source_policy_digest: str = Field(
        pattern=r"^atlas-policy-source-v1:[a-f0-9]{64}$"
    )
    entries: tuple[LegacyPolicyImportEntry, ...]

    @model_validator(mode="after")
    def validate_command(self) -> LegacyPolicyImportCommand:
        if tuple(entry.resource_id for entry in self.entries) != tuple(
            sorted((entry.resource_id for entry in self.entries), key=int)
        ):
            raise ValueError("legacy import entries must be deterministically sorted")
        if len({entry.resource_id for entry in self.entries}) != len(self.entries):
            raise ValueError("legacy import entries contain duplicate VMIDs")
        payload = {
            "entries": [entry.model_dump(mode="json") for entry in self.entries],
            "source_policy_digest": self.source_policy_digest,
            "version": LEGACY_POLICY_IMPORT_VERSION,
        }
        expected_id = _digest(LEGACY_POLICY_IMPORT_VERSION, payload)
        expected_digest = _digest(
            "provider-intent-legacy-policy-import-request-v1", payload
        )
        if self.import_id != expected_id or self.import_digest != expected_digest:
            raise ValueError("legacy import identity or digest is invalid")
        return self


class LegacyPolicyImportResult(ProviderIntentModel):
    outcome: Literal["imported"]
    import_id: str
    source_policy_digest: str
    record_count: int = Field(ge=0)
    records_digest: str = Field(
        pattern=r"^provider-intent-legacy-policy-records-v1:[a-f0-9]{64}$"
    )


def load_legacy_policy_import(source_path: Path) -> LegacyPolicyImportCommand:
    """Validate one explicit policy source and project only Proxmox expectations."""

    try:
        metadata = source_path.lstat()
    except FileNotFoundError as error:
        raise ValueError("legacy policy source does not exist") from error
    if source_path.is_symlink() or not source_path.is_file():
        raise ValueError("legacy policy source must be a regular non-symlink file")
    if metadata.st_size > 1_048_576:
        raise ValueError("legacy policy source exceeds the size limit")
    try:
        source_text = source_path.read_text(encoding="utf-8")
        if any(
            isinstance(token, (AnchorToken, AliasToken))
            for token in yaml.scan(source_text)
        ):
            raise ValueError("legacy policy source cannot contain anchors or aliases")
        _reject_duplicate_mapping_keys(yaml.compose(source_text))
        raw_policy = yaml.safe_load(source_text) or {}
        _validate_import_source_shape(raw_policy)
        policies = Policies.model_validate(raw_policy)
    except (OSError, ValidationError, yaml.YAMLError) as error:
        raise ValueError("legacy policy source is invalid") from error
    policy_payload = {
        "proxmox": {
            "guests": {
                vmid: {"expected": guest.expected}
                for vmid, guest in sorted(
                    policies.proxmox.guests.items(), key=lambda item: int(item[0])
                )
            }
        }
    }
    source_digest = build_legacy_policy_source_digest(policy_payload)
    entries = tuple(
        LegacyPolicyImportEntry(
            resource_id=vmid,
            intent_value=ProviderIntentValue(guest.expected),
            source_reference=build_legacy_policy_source_reference(
                source_policy_digest=source_digest,
                provider_id="proxmox",
                resource_id=vmid,
                intent_kind=ProviderIntentKind.MONITORING_EXPECTATION,
                intent_value=ProviderIntentValue(guest.expected),
            ),
        )
        for vmid, guest in sorted(policies.proxmox.guests.items(), key=lambda item: int(item[0]))
    )
    payload = {
        "entries": [entry.model_dump(mode="json") for entry in entries],
        "source_policy_digest": source_digest,
        "version": LEGACY_POLICY_IMPORT_VERSION,
    }
    return LegacyPolicyImportCommand(
        import_id=_digest(LEGACY_POLICY_IMPORT_VERSION, payload),
        import_digest=_digest(
            "provider-intent-legacy-policy-import-request-v1", payload
        ),
        source_policy_digest=source_digest,
        entries=entries,
    )


def _reject_duplicate_mapping_keys(node: Node | None) -> None:
    if node is None:
        return
    if isinstance(node, MappingNode):
        seen: set[str] = set()
        for key_node, value_node in node.value:
            if (
                not isinstance(key_node, ScalarNode)
                or key_node.value == "<<"
                or key_node.value in seen
            ):
                raise ValueError("legacy policy source contains duplicate or complex keys")
            seen.add(key_node.value)
            _reject_duplicate_mapping_keys(value_node)
    else:
        for child in getattr(node, "value", ()):  # sequences only
            if isinstance(child, Node):
                _reject_duplicate_mapping_keys(child)


def _validate_import_source_shape(value: object) -> None:
    if not isinstance(value, dict):
        raise TypeError("legacy policy source must be a mapping")
    if any(not isinstance(key, str) for key in value):
        raise ValueError("legacy policy top-level keys must be strings")
    unknown_top_level = set(value) - set(Policies.model_fields)
    if unknown_top_level:
        raise ValueError("legacy policy source contains unknown top-level sections")
    proxmox = value.get("proxmox", {})
    if not isinstance(proxmox, dict) or set(proxmox) - {"guests"}:
        raise ValueError("legacy Proxmox policy structure is invalid")
    guests = proxmox.get("guests", {})
    if not isinstance(guests, dict):
        raise TypeError("legacy Proxmox guests policy must be a mapping")
    for vmid, guest in guests.items():
        if not isinstance(vmid, str):
            raise TypeError("legacy Proxmox VMID keys must be strings")
        if not isinstance(guest, dict) or set(guest) != {"expected"}:
            raise ValueError("legacy Proxmox guest policy structure is invalid")


def import_legacy_policy(
    source_path: Path,
    store_path: Path,
    *,
    now: datetime | None = None,
) -> LegacyPolicyImportResult:
    command = load_legacy_policy_import(source_path)
    store = ProviderIntentStore(store_path)
    return store.import_legacy_policy(command, now=now)
