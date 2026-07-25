from __future__ import annotations

import os
from time import perf_counter
from typing import Any
from urllib.parse import urljoin

import httpx

from app.providers import (
    Provider,
    ProviderCapability,
    ProviderHealth,
    ProviderMetadata,
    ProviderPriority,
    ProviderWorkspace,
)


class OPNsenseProvider(Provider):
    """Read-only health and diagnostics integration for OPNsense."""

    def __init__(
        self,
        service: dict[str, Any],
        *,
        api_key: str | None = None,
        api_secret: str | None = None,
        timeout_seconds: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._service = service
        self._api_key = (
            api_key
            if api_key is not None
            else os.getenv("OPNSENSE_API_KEY")
        )
        self._api_secret = (
            api_secret
            if api_secret is not None
            else os.getenv("OPNSENSE_API_SECRET")
        )
        self._timeout_seconds = timeout_seconds
        self._transport = transport

        protocol = service.get("protocol", "https")
        host = service["host"]
        port = service.get("port", 443)
        self._base_url = f"{protocol}://{host}:{port}/"

        self._metadata = ProviderMetadata(
            id="opnsense",
            name=service.get("name", "OPNsense"),
            version="1.0.0",
            description=(
                "Firewall health and firmware status provider."
            ),
            workspace=ProviderWorkspace.OPERATIONS,
            icon="shield",
            priority=(
                ProviderPriority.CRITICAL
                if service.get("critical", True)
                else ProviderPriority.HIGH
            ),
            capabilities=frozenset(
                {
                    ProviderCapability.HEALTH,
                    ProviderCapability.ACTIONS,
                    ProviderCapability.CONFIGURATION,
                },
            ),
        )

    @property
    def metadata(self) -> ProviderMetadata:
        return self._metadata

    def _url(self, path: str) -> str:
        return urljoin(self._base_url, path.lstrip("/"))

    def _tls_verification(self) -> bool | str:
        ca_bundle = self._service.get("ca_bundle")

        if ca_bundle:
            return str(ca_bundle)

        return bool(self._service.get("verify_tls", True))

    async def get_health(self) -> ProviderHealth:
        if not self._api_key or not self._api_secret:
            return ProviderHealth(
                status="degraded",
                message="OPNsense API credentials are not configured.",
                details={
                    "url": self._base_url.rstrip("/"),
                    "credentials_configured": False,
                    "tls_verification": bool(
                        self._tls_verification(),
                    ),
                },
            )

        started_at = perf_counter()

        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds,
                verify=self._tls_verification(),
                transport=self._transport,
                auth=(self._api_key, self._api_secret),
            ) as client:
                response = await client.get(
                    self._url("/api/core/firmware/status"),
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                payload = response.json()

            if not isinstance(payload, dict):
                raise ValueError(
                    "OPNsense returned an invalid status response.",
                )

            return ProviderHealth(
                status="online",
                latency_ms=round(
                    (perf_counter() - started_at) * 1000,
                    2,
                ),
                http_status=response.status_code,
                message="OPNsense API is available.",
                details={
                    "url": self._base_url.rstrip("/"),
                    "credentials_configured": True,
                    "firmware_status": payload.get("status"),
                    "firmware_message": payload.get(
                        "status_msg",
                    ),
                    "product_name": payload.get(
                        "product_name",
                    ),
                    "product_version": payload.get(
                        "product_version",
                    ),
                    "updates": payload.get("updates"),
                    "upgrade_needs_reboot": payload.get(
                        "upgrade_needs_reboot",
                    ),
                },
            )
        except httpx.HTTPStatusError as error:
            status_code = error.response.status_code
            authentication_failed = status_code in {401, 403}

            return ProviderHealth(
                status="degraded",
                latency_ms=round(
                    (perf_counter() - started_at) * 1000,
                    2,
                ),
                http_status=status_code,
                message=(
                    "OPNsense API authentication failed."
                    if authentication_failed
                    else "OPNsense returned an unexpected status."
                ),
                details={
                    "url": self._base_url.rstrip("/"),
                    "credentials_configured": True,
                },
            )
        except (httpx.HTTPError, ValueError) as error:
            return ProviderHealth(
                status="offline",
                latency_ms=round(
                    (perf_counter() - started_at) * 1000,
                    2,
                ),
                message="OPNsense API is unavailable.",
                details={
                    "url": self._base_url.rstrip("/"),
                    "credentials_configured": True,
                    "error": str(error),
                },
            )
