from __future__ import annotations

import os
from collections.abc import Callable
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
                response = await client.post(
                    self._url("/api/core/firmware/status"),
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                payload = response.json()

            if not isinstance(payload, dict):
                raise TypeError(
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
                    "all_packages": payload.get("all_packages"),
                    "all_sets": payload.get("all_sets"),
                    "status_reboot": payload.get("status_reboot"),
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
        except (httpx.HTTPError, TypeError, ValueError) as error:
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
        update_count = self._pending_update_count(health.details)

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

        if self._reboot_required(health.details):
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

    @classmethod
    def _pending_update_count(cls, details: dict[str, Any]) -> int:
        firmware_status = str(details.get("firmware_status") or "").lower()
        has_authoritative_fields = any(
            key in details and details[key] is not None
            for key in ("all_packages", "all_sets", "status_reboot")
        )

        if firmware_status == "none":
            return 0

        if has_authoritative_fields:
            if firmware_status not in {"update", "upgrade"}:
                return 0

            return cls._collection_count(
                details.get("all_packages"),
            ) + cls._collection_count(details.get("all_sets"))

        updates_value = details.get("updates")
        try:
            return int(updates_value or 0)
        except (TypeError, ValueError):
            return 0

    @classmethod
    def _reboot_required(cls, details: dict[str, Any]) -> bool:
        firmware_status = str(details.get("firmware_status") or "").lower()
        has_authoritative_fields = any(
            key in details and details[key] is not None
            for key in ("all_packages", "all_sets", "status_reboot")
        )

        if firmware_status == "none":
            return False

        if has_authoritative_fields:
            if firmware_status not in {"update", "upgrade"}:
                return False
            return cls._truthy(details.get("status_reboot"))

        return cls._truthy(details.get("upgrade_needs_reboot"))

    @staticmethod
    def _collection_count(value: Any) -> int:
        if isinstance(value, dict | list | tuple | set):
            return len(value)
        return 0

    @staticmethod
    def _truthy(value: Any) -> bool:
        return str(value or "").lower() in {"1", "true", "yes"}

    @staticmethod
    def _finding_settings(
        severity: PolicySeverity,
    ) -> tuple[Severity, bool, int]:
        if severity == "critical":
            return Severity.CRITICAL, True, 15
        if severity == "warning":
            return Severity.WARNING, True, 5

        return Severity.INFO, False, 0
