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
    AtlasCoreHealth,
    AtlasCoreIntelligenceSummary,
    AtlasCoreStatus,
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

    async def validate_connection(self) -> None:
        await self.get_health()

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

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
        if self._client is None:
            self._client = httpx.AsyncClient()
        return self._client
