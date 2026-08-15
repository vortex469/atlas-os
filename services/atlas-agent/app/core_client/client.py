import asyncio
import json
from types import TracebackType
from typing import TYPE_CHECKING, Self, TypeAlias

import httpx
from pydantic import ValidationError

from app.approval.models import ApprovalResult

from ..config.settings import Settings
from .exceptions import (
    AtlasCoreConnectionError,
    AtlasCorePayloadError,
    AtlasCoreResponseError,
    AtlasCoreTimeoutError,
)
from .models import (
    AtlasCoreActionHistoryEntry,
    AtlasCoreHealth,
    AtlasCoreIntelligenceSummary,
    AtlasCoreStatus,
    CoreCandidatePlanningIntakeResponse,
    CoreOperationalApprovalBinding,
    CoreOperationalDispatchRequest,
    CoreOperationalDispatchResult,
    CoreOperationalLifecycleRead,
    CoreOperationalLifecycleStatus,
    CoreOperationalVerificationSpecification,
)

if TYPE_CHECKING:
    from app.candidate_planning.models import OperationalActionRequest

__all__ = [
    'AtlasCoreClient',
]

# Type aliases for better readability
HTTPStatus: TypeAlias = int
ResponseBody: TypeAlias = dict[str, object]

class AtlasCoreClient:
    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self._client = client
        self._owns_client = client is None
        self._client_loop: asyncio.AbstractEventLoop | None = None
        self._base_url = f"http://{settings.atlas_core_host}:{settings.atlas_core_port}"
        self._timeout = httpx.Timeout(settings.atlas_core_timeout_seconds)

    async def get_health(self) -> AtlasCoreHealth:
        url = f"{self._base_url}/api/v1/health"
        try:
            response = await self._get_client().get(url, timeout=self._timeout)
            response.raise_for_status()
            return AtlasCoreHealth.model_validate(response.json())
        except httpx.TimeoutException as e:
            raise AtlasCoreTimeoutError(f"Timeout fetching health from {url}: {e!s}")
        except httpx.ConnectError as e:
            raise AtlasCoreConnectionError(f"Connection error fetching health from {url}: {e!s}")
        except httpx.RequestError as e:
            raise AtlasCoreConnectionError(f"Request error fetching health from {url}: {e!s}")
        except httpx.HTTPStatusError as e:
            raise AtlasCoreResponseError(
                f"HTTP {response.status_code} fetching health from {url}: {e!s}"
            )
        except (json.JSONDecodeError, ValidationError) as e:
            raise AtlasCorePayloadError(f"Invalid payload fetching health from {url}: {e!s}")

    async def get_status(self) -> AtlasCoreStatus:
        url = f"{self._base_url}/api/v1/status/"
        try:
            response = await self._get_client().get(url, timeout=self._timeout)
            response.raise_for_status()
            return AtlasCoreStatus.model_validate(response.json())
        except httpx.TimeoutException as e:
            raise AtlasCoreTimeoutError(f"Timeout fetching status from {url}: {e!s}")
        except httpx.ConnectError as e:
            raise AtlasCoreConnectionError(f"Connection error fetching status from {url}: {e!s}")
        except httpx.RequestError as e:
            raise AtlasCoreConnectionError(f"Request error fetching status from {url}: {e!s}")
        except httpx.HTTPStatusError as e:
            raise AtlasCoreResponseError(
                f"HTTP {response.status_code} fetching status from {url}: {e!s}"
            )
        except (json.JSONDecodeError, ValidationError) as e:
            raise AtlasCorePayloadError(f"Invalid payload fetching status from {url}: {e!s}")

    async def get_intelligence_summary(
        self,
    ) -> AtlasCoreIntelligenceSummary:
        url = f"{self._base_url}/api/v1/intelligence/summary"
        try:
            response = await self._get_client().get(url, timeout=self._timeout)
            response.raise_for_status()
            return AtlasCoreIntelligenceSummary.model_validate(response.json())
        except httpx.TimeoutException as e:
            raise AtlasCoreTimeoutError(
                f"Timeout fetching intelligence from {url}: {e!s}"
            )
        except httpx.ConnectError as e:
            raise AtlasCoreConnectionError(
                f"Connection error fetching intelligence from {url}: {e!s}"
            )
        except httpx.RequestError as e:
            raise AtlasCoreConnectionError(
                f"Request error fetching intelligence from {url}: {e!s}"
            )
        except httpx.HTTPStatusError as e:
            raise AtlasCoreResponseError(
                f"HTTP {response.status_code} fetching intelligence "
                f"from {url}: {e!s}"
            )
        except (json.JSONDecodeError, ValidationError) as e:
            raise AtlasCorePayloadError(
                f"Invalid payload fetching intelligence from {url}: {e!s}"
            )

    async def get_action_history(
        self,
        *,
        limit: int = 25,
    ) -> tuple[AtlasCoreActionHistoryEntry, ...]:
        url = f"{self._base_url}/api/v1/ops/actions"
        try:
            response = await self._get_client().get(
                url,
                params={"limit": limit},
                timeout=self._timeout,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                raise AtlasCorePayloadError(
                    f"Invalid payload fetching action history from {url}: expected list"
                )
            return tuple(
                AtlasCoreActionHistoryEntry.model_validate(item)
                for item in payload
            )
        except httpx.TimeoutException as e:
            raise AtlasCoreTimeoutError(
                f"Timeout fetching action history from {url}: {e!s}"
            )
        except httpx.ConnectError as e:
            raise AtlasCoreConnectionError(
                f"Connection error fetching action history from {url}: {e!s}"
            )
        except httpx.RequestError as e:
            raise AtlasCoreConnectionError(
                f"Request error fetching action history from {url}: {e!s}"
            )
        except httpx.HTTPStatusError as e:
            raise AtlasCoreResponseError(
                f"HTTP {response.status_code} fetching action history "
                f"from {url}: {e!s}"
            )
        except (json.JSONDecodeError, ValidationError) as e:
            raise AtlasCorePayloadError(
                f"Invalid payload fetching action history from {url}: {e!s}"
            )

    async def validate_candidate_planning_intake(
        self,
        candidate_id: str,
        *,
        expected_candidate_fingerprint: str | None = None,
        expected_operational_target_fingerprint: str | None = None,
    ) -> CoreCandidatePlanningIntakeResponse:
        url = f"{self._base_url}/api/v1/execution-candidates/{candidate_id}/planning-intake"
        payload = {
            "expected_candidate_fingerprint": expected_candidate_fingerprint,
        }
        if expected_operational_target_fingerprint is not None:
            payload["expected_operational_target_fingerprint"] = (
                expected_operational_target_fingerprint
            )
        try:
            response = await self._get_client().post(
                url,
                json=payload,
                timeout=self._timeout,
            )
            response.raise_for_status()
            return CoreCandidatePlanningIntakeResponse.model_validate(response.json())
        except httpx.TimeoutException as e:
            raise AtlasCoreTimeoutError(
                f"Timeout validating candidate planning intake from {url}: {e!s}"
            )
        except httpx.ConnectError as e:
            raise AtlasCoreConnectionError(
                f"Connection error validating candidate planning intake from {url}: {e!s}"
            )
        except httpx.RequestError as e:
            raise AtlasCoreConnectionError(
                f"Request error validating candidate planning intake from {url}: {e!s}"
            )
        except httpx.HTTPStatusError as e:
            raise AtlasCoreResponseError(
                f"HTTP {response.status_code} validating candidate planning intake "
                f"from {url}: {e!s}"
            )
        except (json.JSONDecodeError, ValidationError) as e:
            raise AtlasCorePayloadError(
                f"Invalid payload validating candidate planning intake from {url}: {e!s}"
            )

    async def validate_connection(self) -> None:
        await self.get_health()

    async def dispatch_operational_action(
        self,
        action_request: "OperationalActionRequest",
        approval_result: ApprovalResult,
    ) -> CoreOperationalDispatchResult:
        """Submit one exact approved request over the dedicated internal boundary."""

        if not approval_result.approved:
            raise AtlasCorePayloadError("Operational dispatch requires exact approval.")
        approval_request = approval_result.decision.request
        approval = approval_request.operational_metadata
        if approval is None:
            raise AtlasCorePayloadError("Operational approval metadata is unavailable.")
        payload = CoreOperationalDispatchRequest(
            request_id=action_request.request_id,
            request_digest=action_request.request_digest,
            idempotency_key=action_request.idempotency_key,
            workflow_session_id=action_request.workflow_session_id,
            candidate_planning_session_id=action_request.candidate_planning_session_id,
            candidate_id=action_request.candidate_id,
            candidate_fingerprint=action_request.candidate_fingerprint,
            candidate_plan_id=action_request.candidate_plan_id,
            candidate_plan_fingerprint=action_request.candidate_plan_fingerprint,
            effect_kind=action_request.effect_kind.value,
            execution_intent=action_request.execution_intent,
            provider_id=action_request.provider_id,
            resource_id=action_request.resource_id,
            resource_type=action_request.resource_type,
            provider_action_id=action_request.provider_action_id,
            target_fingerprint=action_request.target_fingerprint,
            target_version=action_request.target_version,
            expected_pre_state=action_request.expected_pre_state,
            disruption_scope=action_request.disruption_scope,
            evidence_ids=action_request.evidence_ids,
            verification=CoreOperationalVerificationSpecification(
                pre_state=action_request.verification.pre_state,
                expected_post_state=action_request.verification.expected_post_state,
                identity_fingerprint=(
                    action_request.verification.identity_fingerprint
                ),
                health_requirement=action_request.verification.health_requirement,
                unknown_outcome_policy=(
                    action_request.verification.unknown_outcome_policy
                ),
            ),
            generated_at=action_request.generated_at,
            expires_at=action_request.expires_at,
            translator_version=action_request.translator_version,
            approval=CoreOperationalApprovalBinding(
                approval_request_id=approval_request.identifier,
                action_request_id=approval.action_request_id,
                action_request_digest=approval.action_request_digest,
                candidate_id=approval.candidate_id,
                candidate_fingerprint=approval.candidate_fingerprint,
                operational_plan_fingerprint=approval.operational_plan_fingerprint,
                provider_id=approval.provider_id,
                resource_id=approval.resource_id,
                resource_type=approval.resource_type,
                target_fingerprint=approval.target_fingerprint,
                target_version=approval.target_version,
                operation_intent=approval.operation_intent,
                disruption_scope=approval.disruption_scope,
                verification_digest=approval.verification_digest,
                generated_at=approval.generated_at,
                expires_at=approval.expires_at,
            ),
        )
        url = f"{self._base_url}/api/v1/internal/operational-actions/dispatch"
        try:
            token = self.settings.operational_dispatch_auth_file.read_text(
                encoding="ascii"
            ).strip()
            if not token:
                raise AtlasCoreConnectionError(
                    "Operational dispatch authentication is unavailable."
                )
            response = await self._get_client().post(
                url,
                content=payload.model_dump_json(),
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
            return CoreOperationalDispatchResult.model_validate(response.json())
        except (OSError, UnicodeError) as error:
            raise AtlasCoreConnectionError(
                "Operational dispatch authentication is unavailable."
            ) from error
        except httpx.TimeoutException as error:
            raise AtlasCoreTimeoutError(
                "Operational dispatch request timed out."
            ) from error
        except httpx.HTTPStatusError as error:
            raise AtlasCoreResponseError(
                f"Operational dispatch was rejected with HTTP {error.response.status_code}."
            ) from error
        except httpx.RequestError as error:
            raise AtlasCoreConnectionError(
                "Operational dispatch boundary is unavailable."
            ) from error
        except (json.JSONDecodeError, ValidationError) as error:
            raise AtlasCorePayloadError(
                "Operational dispatch returned an invalid response."
            ) from error

    async def get_operational_action_status(
        self, request_id: str
    ) -> CoreOperationalLifecycleStatus:
        """Read one durable operational lifecycle status without provider input."""

        if (
            not request_id
            or request_id != request_id.strip()
            or any(character in request_id for character in "/?#")
        ):
            raise AtlasCorePayloadError("Operational request ID is invalid.")
        url = (
            f"{self._base_url}/api/v1/internal/operational-actions/{request_id}"
        )
        try:
            token = self.settings.operational_dispatch_auth_file.read_text(
                encoding="ascii"
            ).strip()
            if not token:
                raise AtlasCoreConnectionError(
                    "Operational dispatch authentication is unavailable."
                )
            response = await self._get_client().get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=self._timeout,
            )
            response.raise_for_status()
            return CoreOperationalLifecycleStatus.model_validate(response.json())
        except (OSError, UnicodeError) as error:
            raise AtlasCoreConnectionError(
                "Operational dispatch authentication is unavailable."
            ) from error
        except httpx.TimeoutException as error:
            raise AtlasCoreTimeoutError(
                "Operational status request timed out."
            ) from error
        except httpx.HTTPStatusError as error:
            raise AtlasCoreResponseError(
                f"Operational status was rejected with HTTP {error.response.status_code}."
            ) from error
        except httpx.RequestError as error:
            raise AtlasCoreConnectionError(
                "Operational status boundary is unavailable."
            ) from error
        except (json.JSONDecodeError, ValidationError) as error:
            raise AtlasCorePayloadError(
                "Operational status returned an invalid response."
            ) from error

    async def get_operational_lifecycle_read(
        self, request_id: str
    ) -> CoreOperationalLifecycleRead | None:
        """Read sanitized durable lifecycle facts without provider reconciliation."""

        if (
            not request_id
            or request_id != request_id.strip()
            or any(character in request_id for character in "/?#")
        ):
            raise AtlasCorePayloadError("Operational request ID is invalid.")
        url = f"{self._base_url}/api/v1/internal/operational-actions/lifecycle/{request_id}"
        try:
            token = self.settings.operational_dispatch_auth_file.read_text(
                encoding="ascii"
            ).strip()
            if not token:
                raise AtlasCoreConnectionError(
                    "Operational dispatch authentication is unavailable."
                )
            response = await self._get_client().get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=self._timeout,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return CoreOperationalLifecycleRead.model_validate(response.json())
        except (OSError, UnicodeError) as error:
            raise AtlasCoreConnectionError(
                "Operational dispatch authentication is unavailable."
            ) from error
        except httpx.TimeoutException as error:
            raise AtlasCoreTimeoutError("Operational lifecycle read timed out.") from error
        except httpx.HTTPStatusError as error:
            raise AtlasCoreResponseError(
                f"Operational lifecycle read was rejected with HTTP {error.response.status_code}."
            ) from error
        except httpx.RequestError as error:
            raise AtlasCoreConnectionError(
                "Operational lifecycle read boundary is unavailable."
            ) from error
        except (json.JSONDecodeError, ValidationError) as error:
            raise AtlasCorePayloadError(
                "Operational lifecycle read returned an invalid response."
            ) from error

    async def close(self) -> None:
        if not self._owns_client or self._client is None:
            return

        client = self._client
        owner_loop = self._client_loop
        current_loop = asyncio.get_running_loop()
        try:
            if owner_loop is None or owner_loop is current_loop:
                await client.aclose()
            elif owner_loop.is_running() and not owner_loop.is_closed():
                close_future = asyncio.run_coroutine_threadsafe(
                    client.aclose(),
                    owner_loop,
                )
                await asyncio.wrap_future(close_future)
            # A closed or inactive owner loop cannot safely drive the client's
            # connection pool. Its resources belong to that loop and are
            # discarded rather than being closed from the wrong loop.
        finally:
            self._client = None
            self._client_loop = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()

    def _get_client(self) -> httpx.AsyncClient:
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None
        if self._client is None:
            self._client = httpx.AsyncClient()
            self._client_loop = current_loop
        elif self._client_loop is None and current_loop is not None:
            self._client_loop = current_loop
        elif (
            current_loop is not None
            and self._client_loop is not None
            and self._client_loop is not current_loop
        ):
            if not self._owns_client:
                raise RuntimeError(
                    "Injected Atlas Core AsyncClient cannot be used across event loops"
                )

            previous_client = self._client
            previous_loop = self._client_loop
            if previous_loop.is_running() and not previous_loop.is_closed():
                close_future = asyncio.run_coroutine_threadsafe(
                    previous_client.aclose(),
                    previous_loop,
                )
                close_future.add_done_callback(lambda future: future.exception())
            self._client = httpx.AsyncClient()
            self._client_loop = current_loop
        return self._client
