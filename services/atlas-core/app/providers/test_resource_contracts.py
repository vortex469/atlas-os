from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models.resources import (
    ProviderExpectationOption,
    ProviderResource,
    ProviderResourceCollection,
    ProviderResourceExpectation,
    ProviderResourceSummary,
    UpdateResourceExpectationRequest,
    UpdateResourceExpectationResult,
)
from app.providers.capabilities import ProviderCapability
from app.providers.resources import ProviderResourceAdapter


def expectation_options() -> list[ProviderExpectationOption]:
    return [
        ProviderExpectationOption(
            value="running",
            label="Expected Running",
            description="Warn when the resource is not running.",
        ),
        ProviderExpectationOption(
            value="stopped",
            label="Expected Stopped",
            description="Do not warn when the resource is stopped.",
        ),
    ]


def test_resource_contract_accepts_needs_review_without_value() -> None:
    resource = ProviderResource(
        provider_id="proxmox",
        resource_id="109",
        display_name="kenny",
        resource_type="lxc",
        current_state="stopped",
        expectation=ProviderResourceExpectation(
            allowed_values=expectation_options(),
        ),
        configured=True,
        needs_review=False,
        metadata={"node": "vorex469"},
    )

    assert resource.provider_id == "proxmox"
    assert resource.resource_id == "109"
    assert resource.expectation.value is None
    assert resource.expectation.state == "needs_review"
    assert resource.needs_review is True
    assert resource.configured is False
    assert resource.metadata == {"node": "vorex469"}


def test_resource_contract_accepts_provider_defined_expectation() -> None:
    resource = ProviderResource(
        provider_id="proxmox",
        resource_id="109",
        display_name="kenny",
        resource_type="lxc",
        current_state="stopped",
        expectation=ProviderResourceExpectation(
            value="stopped",
            label="Expected Stopped",
            state="configured",
            allowed_values=expectation_options(),
        ),
        configured=False,
    )

    assert resource.expectation.value == "stopped"
    assert resource.expectation.label == "Expected Stopped"
    assert resource.needs_review is False
    assert resource.configured is True


def test_resource_contract_accepts_ignored_expectation() -> None:
    resource = ProviderResource(
        provider_id="frigate",
        resource_id="front",
        display_name="Front Camera",
        resource_type="camera",
        current_state="inactive",
        expectation=ProviderResourceExpectation(
            value="ignored",
            label="Ignore",
            state="ignored",
            allowed_values=[
                ProviderExpectationOption(
                    value="active",
                    label="Expected Active",
                ),
                ProviderExpectationOption(
                    value="ignored",
                    label="Ignore",
                ),
            ],
        ),
        configured=False,
    )

    assert resource.expectation.value == "ignored"
    assert resource.configured is True
    assert resource.needs_review is False


def test_expectation_options_must_have_unique_values() -> None:
    with pytest.raises(ValidationError, match="must be unique"):
        ProviderResourceExpectation(
            value="running",
            label="Expected Running",
            state="configured",
            allowed_values=[
                ProviderExpectationOption(
                    value="running",
                    label="Expected Running",
                ),
                ProviderExpectationOption(
                    value="running",
                    label="Duplicate Running",
                ),
            ],
        )


def test_needs_review_expectation_cannot_persist_value() -> None:
    with pytest.raises(ValidationError, match="must not persist"):
        ProviderResourceExpectation(
            value="running",
            label="Needs Review",
            state="needs_review",
        )


def test_configured_expectation_requires_value() -> None:
    with pytest.raises(ValidationError, match="must include a value"):
        ProviderResourceExpectation(
            label="Expected Running",
            state="configured",
        )


def test_resource_ids_are_required_stable_strings() -> None:
    with pytest.raises(ValidationError):
        ProviderResource(
            provider_id="",
            resource_id="",
            display_name="kenny",
            resource_type="lxc",
            current_state="stopped",
            expectation=ProviderResourceExpectation(),
            configured=False,
        )


def test_resource_collection_and_update_contracts() -> None:
    timestamp = datetime.now(timezone.utc)
    resource = ProviderResource(
        provider_id="proxmox",
        resource_id="109",
        display_name="kenny",
        resource_type="lxc",
        current_state="stopped",
        expectation=ProviderResourceExpectation(),
        configured=False,
    )

    collection = ProviderResourceCollection(
        provider_id="proxmox",
        provider_name="Proxmox",
        refreshed_at=timestamp,
        resources=[resource],
        summary=ProviderResourceSummary(
            total=1,
            configured=0,
            needs_review=1,
            missing=0,
            ignored=0,
            by_type={"lxc": 1},
            by_state={"stopped": 1},
        ),
        metadata={"node": "vorex469"},
    )
    request = UpdateResourceExpectationRequest(
        expectation="stopped",
        confirmed=True,
    )
    result = UpdateResourceExpectationResult(
        provider_id="proxmox",
        resource_id="109",
        expectation=ProviderResourceExpectation(
            value="stopped",
            label="Expected Stopped",
            state="configured",
        ),
        updated_at=timestamp,
    )

    assert collection.summary.needs_review == 1
    assert collection.metadata == {"node": "vorex469"}
    assert request.confirmed is True
    assert result.expectation.value == "stopped"


def test_provider_resource_adapter_is_optional_protocol() -> None:
    class ResourceProvider:
        def expectation_options(
            self,
            resource_type: str,
        ) -> list[ProviderExpectationOption]:
            assert resource_type == "lxc"
            return expectation_options()

        def normalize_expectation(
            self,
            resource_type: str,
            expectation: str,
        ) -> str:
            assert resource_type == "lxc"
            return expectation

        def expectation_label(
            self,
            resource_type: str,
            expectation: str | None,
        ) -> str:
            assert resource_type == "lxc"
            return expectation or "Needs Review"

        async def list_resources(self) -> ProviderResourceCollection:
            raise NotImplementedError

        async def refresh_resources(self) -> ProviderResourceCollection:
            raise NotImplementedError

        async def update_resource_expectation(
            self,
            resource_id: str,
            expectation: str,
        ) -> UpdateResourceExpectationResult:
            raise NotImplementedError

    assert isinstance(ResourceProvider(), ProviderResourceAdapter)


def test_provider_management_capabilities_are_advertisable() -> None:
    assert ProviderCapability.CONNECTION.value == "connection"
    assert ProviderCapability.DISCOVERY.value == "discovery"
    assert ProviderCapability.RESOURCES.value == "resources"
    assert ProviderCapability.MONITORING.value == "monitoring"
    assert ProviderCapability.DIAGNOSTICS.value == "diagnostics"
