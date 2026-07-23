import asyncio
from typing import Any

import pytest

from app.actions import (
    ProviderActionConfirmationRequiredError,
    ProviderActionDisabledError,
    ProviderActionNotFoundError,
    ProviderActionRequest,
    ProviderActionResult,
    execute_provider_action,
)
from app.providers import (
    Provider,
    ProviderAction,
    ProviderCapability,
    ProviderHealth,
    ProviderMetadata,
    ProviderPriority,
    ProviderWorkspace,
)


class ActionTestProvider(Provider):
    def __init__(
        self,
        actions: list[ProviderAction] | None = None,
    ) -> None:
        self._metadata = ProviderMetadata(
            id="action-test",
            name="Action Test",
            workspace=ProviderWorkspace.DEVELOPER,
            priority=ProviderPriority.NORMAL,
            capabilities=frozenset(
                {
                    ProviderCapability.HEALTH,
                },
            ),
        )
        self._actions = actions

    @property
    def metadata(self) -> ProviderMetadata:
        return self._metadata

    async def get_health(self) -> ProviderHealth:
        return ProviderHealth(
            status="online",
            latency_ms=1,
            http_status=200,
        )

    async def get_actions(self) -> list[ProviderAction]:
        if self._actions is None:
            return await super().get_actions()

        return self._actions

    async def execute_action(
        self,
        action_id: str,
        parameters: dict[str, Any],
    ) -> ProviderActionResult:
        if action_id == "test-action":
            return ProviderActionResult(
                provider_id=self.metadata.id,
                action_id=action_id,
                status="succeeded",
                success=True,
                message="Test action completed.",
                data={"parameters": parameters},
            )

        return await super().execute_action(
            action_id=action_id,
            parameters=parameters,
        )


def test_default_diagnostics_action_executes() -> None:
    provider = ActionTestProvider()

    result = asyncio.run(
        execute_provider_action(
            provider=provider,
            action_id="run-diagnostics",
            request=ProviderActionRequest(),
        ),
    )

    assert result.success is True
    assert result.status == "succeeded"
    assert result.provider_id == "action-test"
    assert result.action_id == "run-diagnostics"
    assert result.data["health"]["status"] == "online"


def test_action_parameters_are_forwarded() -> None:
    provider = ActionTestProvider(
        actions=[
            ProviderAction(
                id="test-action",
                label="Test Action",
            ),
        ],
    )

    result = asyncio.run(
        execute_provider_action(
            provider=provider,
            action_id="test-action",
            request=ProviderActionRequest(
                parameters={"example": "value"},
            ),
        ),
    )

    assert result.data["parameters"] == {
        "example": "value",
    }


def test_unknown_action_is_rejected() -> None:
    provider = ActionTestProvider()

    with pytest.raises(
        ProviderActionNotFoundError,
        match="does not advertise",
    ):
        asyncio.run(
            execute_provider_action(
                provider=provider,
                action_id="missing-action",
                request=ProviderActionRequest(),
            ),
        )


def test_disabled_action_is_rejected() -> None:
    provider = ActionTestProvider(
        actions=[
            ProviderAction(
                id="disabled-action",
                label="Disabled Action",
                enabled=False,
            ),
        ],
    )

    with pytest.raises(
        ProviderActionDisabledError,
        match="is disabled",
    ):
        asyncio.run(
            execute_provider_action(
                provider=provider,
                action_id="disabled-action",
                request=ProviderActionRequest(),
            ),
        )


def test_confirmation_is_required_when_advertised() -> None:
    provider = ActionTestProvider(
        actions=[
            ProviderAction(
                id="test-action",
                label="Test Action",
                requires_confirmation=True,
            ),
        ],
    )

    with pytest.raises(
        ProviderActionConfirmationRequiredError,
        match="requires confirmation",
    ):
        asyncio.run(
            execute_provider_action(
                provider=provider,
                action_id="test-action",
                request=ProviderActionRequest(),
            ),
        )


def test_confirmed_action_executes() -> None:
    provider = ActionTestProvider(
        actions=[
            ProviderAction(
                id="test-action",
                label="Test Action",
                requires_confirmation=True,
            ),
        ],
    )

    result = asyncio.run(
        execute_provider_action(
            provider=provider,
            action_id="test-action",
            request=ProviderActionRequest(
                confirmed=True,
            ),
        ),
    )

    assert result.success is True
