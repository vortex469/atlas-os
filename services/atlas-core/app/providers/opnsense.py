from __future__ import annotations

from collections.abc import Callable
import os
from time import perf_counter
from typing import Any
from urllib.parse import urljoin

import httpx

from app.config.policies import get_opnsense_policy
from app.config.policy_models import OPNsensePolicy, PolicySeverity
from app.intelligence.findings import Finding, Severity
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
        policy_getter: Callable[
            [], OPNsensePolicy
        ] = get_opnsense_policy,
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
        self._policy_getter = policy_getter

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

    async def get_findings(self) -> list[Finding]:
        health = await self.get_health()

        if health.status == "offline":
            return [
                Finding(
                    id="opnsense-api-offline",
                    severity=Severity.CRITICAL,
                    category="network",
                    source="opnsense",
                    component="OPNsense",
                    title="OPNsense API unavailable",
                    message=(
                        health.message
                        or "OPNsense API is unavailable."
                    ),
                    recommendation=(
                        "Verify firewall reachability, TLS trust, and "
                        "OPNsense API availability."
                    ),
                    score_penalty=20,
                    details={
                        "http_status": health.http_status,
                    },
                ),
            ]

        if health.status == "degraded":
            return [
                Finding(
                    id="opnsense-api-degraded",
                    severity=Severity.WARNING,
                    category="network",
                    source="opnsense",
                    component="OPNsense",
                    title="OPNsense API degraded",
                    message=(
                        health.message
                        or "OPNsense API health is degraded."
                    ),
                    recommendation=(
                        "Review OPNsense API credentials, privileges, "
                        "and endpoint configuration."
                    ),
                    score_penalty=10,
                    details={
                        "http_status": health.http_status,
                    },
                ),
            ]

        policy = self._policy_getter()
        findings: list[Finding] = []
        updates_value = health.details.get("updates")

        try:
            update_count = int(updates_value or 0)
        except (TypeError, ValueError):
            update_count = 0

        if update_count > 0:
            update_severity: PolicySeverity = "info"
            if (
                policy.pending_update_warning_threshold
                is not None
                and update_count
                >= policy.pending_update_warning_threshold
            ):
                update_severity = "warning"
            severity, affects_health, penalty = (
                self._finding_settings(update_severity)
            )
            findings.append(
                Finding(
                    id="opnsense-firmware-updates",
                    severity=severity,
                    category="updates",
                    source="opnsense",
                    component="OPNsense",
                    title="OPNsense firmware updates available",
                    message=(
                        f"OPNsense reports {update_count} pending "
                        "firmware package update(s)."
                    ),
                    recommendation=(
                        "Review the OPNsense firmware changelog and "
                        "schedule an approved maintenance window."
                    ),
                    affects_health=affects_health,
                    score_penalty=penalty,
                    metric={"updates": update_count},
                ),
            )

        reboot_value = str(
            health.details.get("upgrade_needs_reboot") or "",
        ).lower()
        if reboot_value in {"1", "true", "yes"}:
            severity, affects_health, penalty = (
                self._finding_settings(
                    policy.reboot_required_severity,
                )
            )
            findings.append(
                Finding(
                    id="opnsense-reboot-required",
                    severity=severity,
                    category="updates",
                    source="opnsense",
                    component="OPNsense",
                    title="OPNsense reboot required",
                    message=(
                        "OPNsense requires a reboot to complete its "
                        "firmware maintenance."
                    ),
                    recommendation=(
                        "Schedule an approved firewall reboot during "
                        "a maintenance window."
                    ),
                    affects_health=affects_health,
                    score_penalty=penalty,
                ),
            )

        return findings

    @staticmethod
    def _finding_settings(
        severity: PolicySeverity,
    ) -> tuple[Severity, bool, int]:
        if severity == "critical":
            return Severity.CRITICAL, True, 15
        if severity == "warning":
            return Severity.WARNING, True, 5

        return Severity.INFO, False, 0
