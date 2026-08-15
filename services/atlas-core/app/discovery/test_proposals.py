from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.discovery.compatibility import CompatibilityStatus
from app.discovery.models import (
    CapabilityReference,
    CatalogEntry,
    CatalogProvenance,
    CatalogSourceType,
    DiscoveryItem,
    DiscoveryItemType,
)
from app.discovery.proposals import (
    MAX_EVIDENCE_REFERENCES,
    MAXIMUM_PROPOSAL_LIFETIME,
    DiscoveryOperatorProposal,
    DiscoveryProposalCompatibility,
    DiscoveryProposalDestination,
    DiscoveryProposalDestinationKind,
    DiscoveryProposalProvenance,
    DiscoveryProposalReason,
    DiscoveryProposalStatus,
    DiscoveryProposalTargetHint,
    build_discovery_operator_proposal,
    catalog_source_entry_fingerprint,
)

NOW = datetime(2026, 8, 15, tzinfo=UTC)


def provenance(**changes: object) -> DiscoveryProposalProvenance:
    values = {
        "catalog_source_type": CatalogSourceType.CURATED,
        "catalog_entry_id": "frigate",
        "catalog_item_id": "frigate",
        "source_version": "2026.08",
    }
    values.update(changes)
    return DiscoveryProposalProvenance.model_validate(values)


def compatibility(**changes: object) -> DiscoveryProposalCompatibility:
    values = {
        "target_id": "atlas",
        "target_type": "atlas_environment",
        "status": CompatibilityStatus.COMPATIBLE,
        "finding_ids": ("finding-b", "finding-a"),
        "evidence_ids": ("evidence-b", "evidence-a"),
    }
    values.update(changes)
    return DiscoveryProposalCompatibility.model_validate(values)


def proposal(**changes: object) -> DiscoveryOperatorProposal:
    values = {
        "status": DiscoveryProposalStatus.CURRENT,
        "reason": DiscoveryProposalReason.COMPATIBLE,
        "provenance": provenance(),
        "source_finding_id": "discovery-frigate-atlas-review",
        "compatibility": compatibility(),
        "destination": DiscoveryProposalDestination(
            kind=DiscoveryProposalDestinationKind.COMPATIBILITY_REVIEW
        ),
        "intent_hint": None,
        "target_hints": (
            DiscoveryProposalTargetHint(catalog_target_id="atlas"),
            DiscoveryProposalTargetHint(provider_hint="proxmox", resource_type_hint="qemu"),
        ),
        "generated_at": NOW,
        "expires_at": NOW + timedelta(minutes=30),
    }
    values.update(changes)
    return build_discovery_operator_proposal(**values)


def test_valid_proposal_is_frozen_and_round_trips() -> None:
    value = proposal()
    assert value.proposal_id.endswith(value.proposal_fingerprint.rsplit(":", 1)[-1])
    assert value.compatibility.finding_ids == ("finding-a", "finding-b")
    assert DiscoveryOperatorProposal.model_validate_json(value.model_dump_json()) == value
    with pytest.raises(ValidationError):
        value.status = DiscoveryProposalStatus.STALE  # type: ignore[misc]


def test_extra_and_authoritative_security_fields_are_rejected() -> None:
    payload = proposal().model_dump()
    for field in (
        "authorization",
        "cookie",
        "csrf",
        "password",
        "api_token",
        "provider_native_payload",
        "vmgenid",
        "command",
        "environment",
        "url",
        "provider_action_id",
        "provider_parameters",
        "target_fingerprint",
    ):
        with pytest.raises(ValidationError):
            DiscoveryOperatorProposal.model_validate({**payload, field: "forbidden"})


def test_fingerprint_is_order_independent_for_references_and_hints() -> None:
    first = proposal()
    second = proposal(
        compatibility=compatibility(
            finding_ids=("finding-a", "finding-b"),
            evidence_ids=("evidence-a", "evidence-b"),
        ),
        target_hints=tuple(reversed(first.target_hints)),
    )
    assert first.proposal_fingerprint == second.proposal_fingerprint
    assert first.proposal_id == second.proposal_id


@pytest.mark.parametrize(
    "changed",
    (
        {"provenance": provenance(source_version="2026.09")},
        {"compatibility": compatibility(evidence_ids=("evidence-c",))},
        {"compatibility": compatibility(status=CompatibilityStatus.COMPATIBLE_WITH_WARNINGS)},
    ),
)
def test_security_relevant_source_changes_change_fingerprints(changed: dict[str, object]) -> None:
    original = proposal()
    updated = proposal(**changed)
    assert updated.proposal_fingerprint != original.proposal_fingerprint
    assert updated.source_state_fingerprint != original.source_state_fingerprint


def test_display_catalog_text_and_proposal_times_do_not_change_identity() -> None:
    first_entry = catalog_entry(name="Frigate", description="Camera recorder")
    second_entry = catalog_entry(name="New display name", description="Changed display text")
    assert catalog_source_entry_fingerprint(first_entry) == catalog_source_entry_fingerprint(second_entry)
    assert proposal().proposal_fingerprint == proposal(
        generated_at=NOW + timedelta(minutes=1),
        expires_at=NOW + timedelta(minutes=31),
    ).proposal_fingerprint


def test_source_state_excludes_navigation_but_tracks_source_evidence() -> None:
    first = proposal()
    different_destination = proposal(
        destination=DiscoveryProposalDestination(
            kind=DiscoveryProposalDestinationKind.DISCOVERY_DETAIL
        )
    )
    changed_evidence = proposal(
        compatibility=compatibility(evidence_ids=("different-evidence",))
    )
    assert first.source_state_fingerprint == different_destination.source_state_fingerprint
    assert first.proposal_fingerprint != different_destination.proposal_fingerprint
    assert first.source_state_fingerprint != changed_evidence.source_state_fingerprint


def test_unversioned_provenance_requires_fallback_and_versioned_rejects_it() -> None:
    fallback = catalog_source_entry_fingerprint(catalog_entry())
    assert provenance(source_version=None, source_entry_fingerprint=fallback)
    with pytest.raises(ValidationError):
        provenance(source_version=None)
    with pytest.raises(ValidationError):
        provenance(source_entry_fingerprint=fallback)


@pytest.mark.parametrize(
    ("generated", "expires"),
    (
        (NOW.replace(tzinfo=None), NOW + timedelta(minutes=1)),
        (NOW, (NOW + timedelta(minutes=1)).replace(tzinfo=None)),
        (NOW, NOW),
        (NOW, NOW + MAXIMUM_PROPOSAL_LIFETIME + timedelta(seconds=1)),
    ),
)
def test_temporal_contract_rejects_invalid_values(generated: datetime, expires: datetime) -> None:
    with pytest.raises(ValidationError):
        proposal(generated_at=generated, expires_at=expires)


def test_non_utc_timestamp_is_rejected() -> None:
    with pytest.raises(ValidationError):
        proposal(
            generated_at=datetime.fromisoformat("2026-08-15T01:00:00+01:00"),
            expires_at=datetime.fromisoformat("2026-08-15T01:30:00+01:00"),
        )


def test_reference_and_target_hint_bounds_are_enforced() -> None:
    with pytest.raises(ValidationError):
        compatibility(
            evidence_ids=tuple(f"evidence-{index}" for index in range(MAX_EVIDENCE_REFERENCES + 1))
        )
    with pytest.raises(ValidationError):
        proposal(
            target_hints=tuple(
                DiscoveryProposalTargetHint(catalog_target_id=f"target-{index}")
                for index in range(9)
            )
        )


def test_arbitrary_destination_and_intent_fail_closed() -> None:
    with pytest.raises(ValidationError):
        DiscoveryProposalDestination.model_validate({"kind": "https://evil.test/path"})
    payload = proposal().model_dump()
    payload["intent_hint"] = "run-provider-payload"
    with pytest.raises(ValidationError):
        DiscoveryOperatorProposal.model_validate(payload)


def test_expired_status_requires_expired_reason() -> None:
    with pytest.raises(ValidationError):
        proposal(status=DiscoveryProposalStatus.EXPIRED)


def test_schema_has_no_authoritative_or_security_payload_fields() -> None:
    schema = json_text(DiscoveryOperatorProposal.model_json_schema()).lower()
    for forbidden in (
        "authorization",
        "cookie",
        "csrf",
        "password",
        "token",
        "native_payload",
        "vmgenid",
        "command",
        "environment",
        "url",
        "provider_action_id",
        "provider_parameters",
        "target_fingerprint",
    ):
        assert forbidden not in schema


def catalog_entry(
    *, name: str = "Frigate", description: str = "Recorder"
) -> CatalogEntry:
    return CatalogEntry(
        item=DiscoveryItem(
            id="frigate",
            type=DiscoveryItemType.APPLICATION,
            name=name,
            description=description,
            capabilities=(CapabilityReference(id="video-recording"),),
        ),
        provenance=CatalogProvenance(
            source_type=CatalogSourceType.CURATED,
            source="catalog/frigate.yaml",
            entry_id="frigate",
        ),
    )


def json_text(value: object) -> str:
    import json

    return json.dumps(value, sort_keys=True)
