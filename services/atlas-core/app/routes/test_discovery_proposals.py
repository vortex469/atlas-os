from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.discovery.compatibility import CompatibilityStatus
from app.discovery.models import CatalogSourceType
from app.discovery.proposals import (
    DiscoveryProposalCompatibility,
    DiscoveryProposalDestination,
    DiscoveryProposalDestinationKind,
    DiscoveryProposalProvenance,
    DiscoveryProposalReason,
    DiscoveryProposalStatus,
    DiscoveryProposalTargetHint,
    build_discovery_operator_proposal,
)
from app.main import app
from app.routes import discovery as route_module
from app.services.discovery_proposals import (
    DiscoveryProposalEvaluation,
    DiscoveryProposalNotFoundError,
)
from app.testing import ASGITestClient

client = ASGITestClient(app)


def _proposal():
    generated = datetime(2026, 8, 15, tzinfo=UTC)
    return build_discovery_operator_proposal(
        status=DiscoveryProposalStatus.CURRENT,
        reason=DiscoveryProposalReason.COMPATIBLE,
        provenance=DiscoveryProposalProvenance(
            catalog_source_type=CatalogSourceType.CURATED,
            catalog_entry_id="entry-frigate",
            catalog_item_id="frigate",
            source_version="1",
        ),
        compatibility=DiscoveryProposalCompatibility(
            target_id="atlas",
            target_type="deployment",
            status=CompatibilityStatus.COMPATIBLE,
            finding_ids=(),
            evidence_ids=(),
        ),
        destination=DiscoveryProposalDestination(
            kind=DiscoveryProposalDestinationKind.OPERATOR_MAINTENANCE_SELECTION,
        ),
        target_hints=(DiscoveryProposalTargetHint(provider_hint="proxmox"),),
        generated_at=generated,
        expires_at=generated + timedelta(minutes=30),
    )


class _ProposalReader:
    def __init__(self, evaluation: DiscoveryProposalEvaluation) -> None:
        self.evaluation = evaluation
        self.limit: int | None = None

    def list_evaluations(self, *, target: str, limit: int):
        self.limit = limit
        return (self.evaluation,)

    def get_evaluation(self, proposal_id: str, *, target: str):
        if proposal_id != self.evaluation.proposal.proposal_id:
            raise DiscoveryProposalNotFoundError
        return self.evaluation


@pytest.fixture
def current_reader(monkeypatch: pytest.MonkeyPatch) -> _ProposalReader:
    proposal = _proposal()
    reader = _ProposalReader(
        DiscoveryProposalEvaluation(
            proposal=proposal,
            status=DiscoveryProposalStatus.CURRENT,
            reason=DiscoveryProposalReason.COMPATIBLE,
            effective_destination=proposal.destination,
            actionable_navigation=True,
        )
    )
    monkeypatch.setattr(route_module, "get_discovery_proposal_service", lambda: reader)
    return reader


def test_proposal_list_is_bounded_sanitized_and_get_only(current_reader: _ProposalReader) -> None:
    response = client.get("/api/v1/discovery/proposals?limit=1")

    assert response.status_code == 200
    assert current_reader.limit == 1
    assert response.json()["total"] == 1
    navigation = response.json()["proposals"][0]
    assert navigation["destination_kind"] == "operator_maintenance_selection"
    assert navigation["actionable_navigation"] is True
    serialized = str(response.json()).lower()
    for forbidden in (
        "target_fingerprint",
        "vmgenid",
        "provider_action_id",
        "csrf",
        "cookie",
        "command",
        "environment",
    ):
        assert forbidden not in serialized
    schema = app.openapi()["paths"]["/api/v1/discovery/proposals"]
    assert set(schema) == {"get"}


def test_proposal_detail_and_controlled_not_found(current_reader: _ProposalReader) -> None:
    proposal_id = current_reader.evaluation.proposal.proposal_id
    response = client.get(f"/api/v1/discovery/proposals/{proposal_id}")
    missing = client.get("/api/v1/discovery/proposals/discovery-operator-proposal-missing")

    assert response.status_code == 200
    assert response.json()["proposal_id"] == proposal_id
    assert missing.status_code == 404
    assert missing.json()["error"]["message"] == "Discovery proposal was not found."


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        (DiscoveryProposalStatus.STALE, DiscoveryProposalReason.SOURCE_CHANGED),
        (DiscoveryProposalStatus.EXPIRED, DiscoveryProposalReason.EXPIRED),
        (DiscoveryProposalStatus.NOT_ACTIONABLE, DiscoveryProposalReason.EVIDENCE_MISSING),
    ],
)
def test_non_current_proposals_remain_inspectable_but_review_only(
    monkeypatch: pytest.MonkeyPatch,
    status: DiscoveryProposalStatus,
    reason: DiscoveryProposalReason,
) -> None:
    proposal = _proposal()
    reader = _ProposalReader(
        DiscoveryProposalEvaluation(
            proposal=proposal,
            status=status,
            reason=reason,
            effective_destination=None,
            actionable_navigation=False,
        )
    )
    monkeypatch.setattr(route_module, "get_discovery_proposal_service", lambda: reader)

    response = client.get(f"/api/v1/discovery/proposals/{proposal.proposal_id}")

    assert response.status_code == 200
    assert response.json()["status"] == status.value
    assert response.json()["destination_kind"] == "discovery_detail"
    assert response.json()["actionable_navigation"] is False
