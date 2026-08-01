from __future__ import annotations

from collections.abc import Callable
from time import perf_counter
from typing import Any
from urllib.parse import urljoin

import httpx

from app.config.policies import get_n8n_policy
from app.config.policy_models import N8nPolicy, PolicySeverity
from app.context import AtlasContext
from app.intelligence.findings import Finding, Severity
from app.providers import (
    Provider,
    ProviderCapability,
    ProviderHealth,
    ProviderMetadata,
    ProviderPriority,
    ProviderWorkspace,
)
from app.providers.context_helpers import (
    base_url_from_context,
    context_from_legacy_service,
    legacy_service,
    metadata_from_context,
    secret_value,
    timeout_from_context,
    tls_verification_from_context,
)


class N8nProvider(Provider):
    """Read-only workflow inventory provider for n8n."""

    def __init__(
        self,
        service: AtlasContext | dict[str, Any],
        *,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        policy_getter: Callable[[], N8nPolicy] = get_n8n_policy,
    ) -> None:
        # Temporary compatibility seam for direct legacy constructors.
        self.atlas_context = (
            service
            if isinstance(service, AtlasContext)
            else context_from_legacy_service("n8n", service)
        )
        service_config = legacy_service(self.atlas_context)
        self._api_key = api_key or secret_value(self.atlas_context, "api_key")
        self._timeout_seconds = timeout_seconds or timeout_from_context(
            self.atlas_context,
        )
        self._transport = transport
        self._policy_getter = policy_getter
        self._max_workflows = self._positive_int(
            service_config.get("max_workflows", 250),
            "max_workflows",
        )
        self._base_url = base_url_from_context(
            self.atlas_context,
            default_port=5678,
        )
        self._metadata = metadata_from_context(
            self.atlas_context,
            default_description="Workflow automation health and inventory provider.",
            default_workspace=ProviderWorkspace.AUTOMATION,
            default_icon="workflow",
            default_priority=ProviderPriority.HIGH,
            default_capabilities=frozenset(
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
        return tls_verification_from_context(self.atlas_context)

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
            policy = self._policy_getter()
            expected_active_workflows = set(
                policy.expected_active_workflows
            )
            missing = sorted(
                expected_active_workflows - known_names
            )
            inactive_expected = sorted(
                expected_active_workflows & set(inactive_names)
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
                    "expected_active_workflow_count": len(
                        expected_active_workflows
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
        policy = self._policy_getter()
        missing = self._detail_list(
            health,
            "missing_expected_workflows",
        )
        inactive = self._detail_list(
            health,
            "inactive_expected_workflows",
        )
        if missing or inactive:
            severity = self._severity(
                policy.inactive_workflow_severity
            )
            findings.append(
                Finding(
                    id="n8n-expected-workflows-inactive",
                    severity=severity,
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
                    affects_health=severity != Severity.INFO,
                    score_penalty=self._score_penalty(severity),
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
            severity = self._severity(
                policy.scan_truncated_severity
            )
            findings.append(
                Finding(
                    id="n8n-workflow-scan-truncated",
                    severity=severity,
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
                    affects_health=severity != Severity.INFO,
                    score_penalty=self._score_penalty(severity),
                    details={
                        "max_workflows": self._max_workflows,
                    },
                ),
            )

        if health.details.get("workflow_count") == 0:
            severity = self._severity(
                policy.empty_instance_severity
            )
            findings.append(
                Finding(
                    id="n8n-no-workflows",
                    severity=severity,
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
                    affects_health=severity != Severity.INFO,
                    score_penalty=self._score_penalty(severity),
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
            raise ValueError(  # noqa: TRY004
                "n8n returned an invalid workflows response."
            )
        data = payload.get("data")
        cursor = payload.get("nextCursor")
        if not isinstance(data, list):
            raise ValueError(  # noqa: TRY004
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
            raise ValueError(f"{field} must be a positive integer.")  # noqa: TRY004
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

    @staticmethod
    def _severity(value: PolicySeverity) -> Severity:
        return {
            "info": Severity.INFO,
            "warning": Severity.WARNING,
            "critical": Severity.CRITICAL,
        }[value]

    @staticmethod
    def _score_penalty(severity: Severity) -> int:
        return {
            Severity.INFO: 0,
            Severity.WARNING: 10,
            Severity.CRITICAL: 20,
        }[severity]
