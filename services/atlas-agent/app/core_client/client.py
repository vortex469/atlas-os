import asyncio
import json
from types import TracebackType
from typing import Self, TypeAlias

import httpx
from pydantic import ValidationError

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
)

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
