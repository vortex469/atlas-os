from __future__ import annotations

import os
from time import perf_counter
from typing import Any
from urllib.parse import urljoin

import httpx

from app.intelligence.findings import Finding, Severity
from app.providers import (
    Provider,
    ProviderCapability,
    ProviderHealth,
    ProviderMetadata,
    ProviderPriority,
    ProviderWorkspace,
)


class FrigateProvider(Provider):
    """Read-only health and camera telemetry provider for Frigate."""

    def __init__(
        self,
        service: dict[str, Any],
        *,
        api_token: str | None = None,
        timeout_seconds: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._service = service
        self._api_token = (
            api_token
            if api_token is not None
            else os.getenv("FRIGATE_API_TOKEN")
        )
        self._timeout_seconds = timeout_seconds
        self._transport = transport

        protocol = service.get("protocol", "https")
        host = service["host"]
        port = service.get("port", 8971)
        self._base_url = f"{protocol}://{host}:{port}/"

        self._metadata = ProviderMetadata(
            id="frigate",
            name=service.get("name", "Frigate"),
            version="1.0.0",
            description=(
                "NVR health, camera telemetry, and version provider."
            ),
            workspace=ProviderWorkspace.AUTOMATION,
            icon="video",
            priority=(
                ProviderPriority.CRITICAL
                if service.get("critical", False)
                else ProviderPriority.HIGH
            ),
            capabilities=frozenset(
                {
                    ProviderCapability.HEALTH,
                    ProviderCapability.FINDINGS,
                    ProviderCapability.ACTIONS,
                    ProviderCapability.METRICS,
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

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}

        if self._api_token:
            headers["Authorization"] = (
                f"Bearer {self._api_token}"
            )

        return headers

    async def get_health(self) -> ProviderHealth:
        started_at = perf_counter()

        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds,
                verify=self._tls_verification(),
                transport=self._transport,
            ) as client:
                response = await client.get(
                    self._url("/api/stats"),
                    headers=self._headers(),
                )
                response.raise_for_status()
                payload = response.json()

            if not isinstance(payload, dict):
                raise ValueError(
                    "Frigate returned an invalid stats response.",
                )

            cameras = payload.get("cameras", {})
            service_stats = payload.get("service", {})

            if not isinstance(cameras, dict):
                cameras = {}
            if not isinstance(service_stats, dict):
                service_stats = {}

            return ProviderHealth(
                status="online",
                latency_ms=round(
                    (perf_counter() - started_at) * 1000,
                    2,
                ),
                http_status=response.status_code,
                message="Frigate API is available.",
                details={
                    "url": self._base_url.rstrip("/"),
                    "authenticated": bool(self._api_token),
                    "camera_count": len(cameras),
                    "cameras": {
                        name: {
                            "camera_fps": stats.get(
                                "camera_fps",
                            ),
                            "process_fps": stats.get(
                                "process_fps",
                            ),
                            "skipped_fps": stats.get(
                                "skipped_fps",
                            ),
                            "detection_fps": stats.get(
                                "detection_fps",
                            ),
                        }
                        for name, stats in cameras.items()
                        if isinstance(stats, dict)
                    },
                    "detection_fps": payload.get(
                        "detection_fps",
                    ),
                    "uptime": service_stats.get("uptime"),
                    "version": service_stats.get("version"),
                    "latest_version": service_stats.get(
                        "latest_version",
                    ),
                },
            )
        except httpx.HTTPStatusError as error:
            status_code = error.response.status_code

            return ProviderHealth(
                status="degraded",
                latency_ms=round(
                    (perf_counter() - started_at) * 1000,
                    2,
                ),
                http_status=status_code,
                message=(
                    "Frigate API authentication failed."
                    if status_code in {401, 403}
                    else "Frigate returned an unexpected status."
                ),
                details={
                    "url": self._base_url.rstrip("/"),
                    "authenticated": bool(self._api_token),
                },
            )
        except (httpx.HTTPError, ValueError) as error:
            return ProviderHealth(
                status="offline",
                latency_ms=round(
                    (perf_counter() - started_at) * 1000,
                    2,
                ),
                message="Frigate API is unavailable.",
                details={
                    "url": self._base_url.rstrip("/"),
                    "authenticated": bool(self._api_token),
                    "error": str(error),
                },
            )

    async def get_findings(self) -> list[Finding]:
        health = await self.get_health()

        if health.status != "online":
            severity = (
                Severity.CRITICAL
                if health.status == "offline"
                and self.metadata.priority
                == ProviderPriority.CRITICAL
                else Severity.WARNING
            )
            return [
                Finding(
                    id=f"frigate-api-{health.status}",
                    severity=severity,
                    category="video",
                    source="frigate",
                    component="Frigate",
                    title=f"Frigate API {health.status}",
                    message=(
                        health.message
                        or "Frigate API is not healthy."
                    ),
                    recommendation=(
                        "Review Frigate connectivity, authentication, "
                        "TLS trust, and service logs."
                    ),
                    score_penalty=(
                        20
                        if severity == Severity.CRITICAL
                        else 10
                    ),
                    details={
                        "http_status": health.http_status,
                    },
                ),
            ]

        findings: list[Finding] = []
        cameras = health.details.get("cameras", {})
        stalled_cameras = [
            name
            for name, stats in cameras.items()
            if isinstance(stats, dict)
            and (
                self._numeric_fps(stats.get("camera_fps")) <= 0
                or self._numeric_fps(stats.get("process_fps")) <= 0
            )
        ] if isinstance(cameras, dict) else []

        if stalled_cameras:
            findings.append(
                Finding(
                    id="frigate-cameras-stalled",
                    severity=Severity.WARNING,
                    category="video",
                    source="frigate",
                    component="Frigate",
                    title="Frigate cameras stalled",
                    message=(
                        f"{len(stalled_cameras)} Frigate camera(s) "
                        "are not producing or processing frames."
                    ),
                    recommendation=(
                        "Review camera connectivity and Frigate ffmpeg "
                        "logs."
                    ),
                    score_penalty=10,
                    metric={
                        "stalled_cameras": len(stalled_cameras),
                        "configured_cameras": len(cameras),
                    },
                    details={"cameras": stalled_cameras},
                ),
            )

        version = health.details.get("version")
        latest_version = health.details.get("latest_version")
        if version and latest_version and version != latest_version:
            findings.append(
                Finding(
                    id="frigate-update-available",
                    severity=Severity.INFO,
                    category="updates",
                    source="frigate",
                    component="Frigate",
                    title="Frigate update available",
                    message=(
                        f"Frigate {version} is running; "
                        f"{latest_version} is available."
                    ),
                    recommendation=(
                        "Review Frigate release notes before upgrading."
                    ),
                    affects_health=False,
                    score_penalty=0,
                    details={
                        "current_version": version,
                        "latest_version": latest_version,
                    },
                ),
            )

        return findings

    @staticmethod
    def _numeric_fps(value: object) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0
