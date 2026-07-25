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


class N8nProvider(Provider):
    """Read-only workflow inventory provider for n8n."""

    def __init__(
        self,
        service: dict[str, Any],
        *,
        api_key: str | None = None,
        timeout_seconds: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._service = service
        self._api_key = (
            api_key
            if api_key is not None
            else os.getenv("N8N_API_KEY")
        )
        self._timeout_seconds = timeout_seconds
        self._transport = transport
        self._max_workflows = self._positive_int(
            service.get("max_workflows", 250),
            "max_workflows",
        )
        expected = service.get("expected_active_workflows", [])
        if not isinstance(expected, list) or not all(
            isinstance(name, str) and name
            for name in expected
        ):
            raise ValueError(
                "expected_active_workflows must be a list of names."
            )
        if len(set(expected)) != len(expected):
            raise ValueError(
                "expected_active_workflows must not contain duplicates."
            )
        self._expected_active_workflows = frozenset(expected)

        protocol = service.get("protocol", "http")
        host = service["host"]
        port = service.get("port", 5678)
        self._base_url = f"{protocol}://{host}:{port}/"

        self._metadata = ProviderMetadata(
            id="n8n",
            name=service.get("name", "n8n"),
            version="1.0.0",
            description=(
                "Workflow automation health and inventory provider."
            ),
            workspace=ProviderWorkspace.AUTOMATION,
            icon="workflow",
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
        if self._api_key:
            headers["X-N8N-API-KEY"] = self._api_key
        return headers

    async def get_health(self) -> ProviderHealth:
        started_at = perf_counter()

        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds,
                verify=self._tls_verification(),
                transport=self._transport,
            ) as client:
                workflows, truncated, status_code = (
                    await self._collect_workflows(client)
                )

            active_names = sorted(
                workflow["name"]
                for workflow in workflows
                if workflow["active"]
            )
            inactive_names = sorted(
                workflow["name"]
                for workflow in workflows
                if not workflow["active"]
            )
            known_names = set(active_names) | set(inactive_names)
            missing = sorted(
                self._expected_active_workflows - known_names
            )
            inactive_expected = sorted(
                self._expected_active_workflows
                & set(inactive_names)
            )

            return ProviderHealth(
                status="online",
                latency_ms=self._elapsed_ms(started_at),
                http_status=status_code,
                message="n8n workflow API is available.",
                details={
                    "url": self._base_url.rstrip("/"),
                    "authenticated": bool(self._api_key),
                    "workflow_count": len(workflows),
                    "active_workflow_count": len(active_names),
                    "inactive_workflow_count": len(inactive_names),
                    "active_workflows": active_names,
                    "inactive_workflows": inactive_names,
                    "missing_expected_workflows": missing,
                    "inactive_expected_workflows": (
                        inactive_expected
                    ),
                    "scan_truncated": truncated,
                    "max_workflows": self._max_workflows,
                },
            )
        except httpx.HTTPStatusError as error:
            status_code = error.response.status_code
            return ProviderHealth(
                status="degraded",
                latency_ms=self._elapsed_ms(started_at),
                http_status=status_code,
                message=(
                    "n8n API authentication failed."
                    if status_code in {401, 403}
                    else "n8n returned an unexpected status."
                ),
                details={
                    "url": self._base_url.rstrip("/"),
                    "authenticated": bool(self._api_key),
                },
            )
        except (httpx.HTTPError, ValueError) as error:
            return ProviderHealth(
                status="offline",
                latency_ms=self._elapsed_ms(started_at),
                message="n8n workflow API is unavailable.",
                details={
                    "url": self._base_url.rstrip("/"),
                    "authenticated": bool(self._api_key),
                    "error": str(error),
                },
            )

    async def get_findings(self) -> list[Finding]:
        health = await self.get_health()

        if health.status != "online":
            critical = (
                health.status == "offline"
                and self.metadata.priority
                == ProviderPriority.CRITICAL
            )
            return [
                Finding(
                    id=f"n8n-api-{health.status}",
                    severity=(
                        Severity.CRITICAL
                        if critical
                        else Severity.WARNING
                    ),
                    category="automation",
                    source="n8n",
                    component=self.metadata.name,
                    title=f"n8n API {health.status}",
                    message=(
                        health.message
                        or "n8n workflow API is not healthy."
                    ),
                    recommendation=(
                        "Review n8n connectivity, API credentials, "
                        "TLS trust, and service logs."
                    ),
                    score_penalty=20 if critical else 10,
                    details={
                        "http_status": health.http_status,
                    },
                ),
            ]

        findings: list[Finding] = []
        missing = self._detail_list(
            health,
            "missing_expected_workflows",
        )
        inactive = self._detail_list(
            health,
            "inactive_expected_workflows",
        )
        if missing or inactive:
            findings.append(
                Finding(
                    id="n8n-expected-workflows-inactive",
                    severity=Severity.WARNING,
                    category="automation",
                    source="n8n",
                    component=self.metadata.name,
                    title="Expected n8n workflows are not active",
                    message=(
                        f"{len(missing)} expected workflow(s) are "
                        f"missing and {len(inactive)} are inactive."
                    ),
                    recommendation=(
                        "Review workflow provisioning, activation, and "
                        "the expected_active_workflows inventory."
                    ),
                    score_penalty=10,
                    metric={
                        "missing_workflows": len(missing),
                        "inactive_workflows": len(inactive),
                    },
                    details={
                        "missing": missing,
                        "inactive": inactive,
                    },
                ),
            )

        if health.details.get("scan_truncated"):
            findings.append(
                Finding(
                    id="n8n-workflow-scan-truncated",
                    severity=Severity.WARNING,
                    category="automation",
                    source="n8n",
                    component=self.metadata.name,
                    title="n8n workflow scan truncated",
                    message=(
                        "The workflow inventory exceeded the "
                        "configured scan limit."
                    ),
                    recommendation=(
                        "Increase max_workflows so Atlas can evaluate "
                        "the complete n8n inventory."
                    ),
                    score_penalty=5,
                    details={
                        "max_workflows": self._max_workflows,
                    },
                ),
            )

        if health.details.get("workflow_count") == 0:
            findings.append(
                Finding(
                    id="n8n-no-workflows",
                    severity=Severity.INFO,
                    category="automation",
                    source="n8n",
                    component=self.metadata.name,
                    title="n8n has no workflows",
                    message=(
                        "n8n is online but reports no workflows."
                    ),
                    recommendation=(
                        "Confirm whether this n8n instance should "
                        "contain automation workflows."
                    ),
                    affects_health=False,
                    score_penalty=0,
                ),
            )

        return findings

    async def _collect_workflows(
        self,
        client: httpx.AsyncClient,
    ) -> tuple[list[dict[str, object]], bool, int]:
        workflows: list[dict[str, object]] = []
        cursor: str | None = None
        status_code = 200

        while len(workflows) < self._max_workflows:
            remaining = self._max_workflows - len(workflows)
            params: dict[str, str | int] = {
                "limit": min(100, remaining),
            }
            if cursor is not None:
                params["cursor"] = cursor

            response = await client.get(
                self._url("/api/v1/workflows"),
                headers=self._headers(),
                params=params,
            )
            response.raise_for_status()
            status_code = response.status_code
            page, cursor = self._workflow_page(response.json())
            workflows.extend(page[:remaining])

            if cursor is None:
                return workflows, False, status_code
            if not page:
                raise ValueError(
                    "n8n returned an empty page with a next cursor."
                )

        return workflows, cursor is not None, status_code

    @staticmethod
    def _workflow_page(
        payload: object,
    ) -> tuple[list[dict[str, object]], str | None]:
        if not isinstance(payload, dict):
            raise ValueError(
                "n8n returned an invalid workflows response."
            )
        data = payload.get("data")
        cursor = payload.get("nextCursor")
        if not isinstance(data, list):
            raise ValueError(
                "n8n returned an invalid workflows list."
            )
        if cursor is not None and not isinstance(cursor, str):
            raise ValueError(
                "n8n returned an invalid workflow cursor."
            )

        workflows: list[dict[str, object]] = []
        for workflow in data:
            if (
                not isinstance(workflow, dict)
                or not isinstance(workflow.get("name"), str)
                or not workflow["name"]
                or not isinstance(workflow.get("active"), bool)
            ):
                raise ValueError(
                    "n8n returned an invalid workflow entry."
                )
            workflows.append(
                {
                    "name": workflow["name"],
                    "active": workflow["active"],
                },
            )
        return workflows, cursor

    @staticmethod
    def _detail_list(
        health: ProviderHealth,
        key: str,
    ) -> list[str]:
        value = health.details.get(key)
        if not isinstance(value, list):
            return []
        return [
            item
            for item in value
            if isinstance(item, str)
        ]

    @staticmethod
    def _positive_int(value: object, field: str) -> int:
        if isinstance(value, bool):
            raise ValueError(f"{field} must be a positive integer.")
        try:
            parsed = int(value)
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"{field} must be a positive integer."
            ) from error
        if parsed < 1:
            raise ValueError(f"{field} must be a positive integer.")
        return parsed

    @staticmethod
    def _elapsed_ms(started_at: float) -> float:
        return round((perf_counter() - started_at) * 1000, 2)
