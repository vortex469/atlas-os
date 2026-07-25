from __future__ import annotations

import os
from time import perf_counter
from typing import Any, Callable
from urllib.parse import urljoin

import httpx

from app.config.policies import get_qdrant_policy
from app.config.policy_models import PolicySeverity, QdrantPolicy
from app.intelligence.findings import Finding, Severity
from app.providers import (
    Provider,
    ProviderCapability,
    ProviderHealth,
    ProviderMetadata,
    ProviderPriority,
    ProviderWorkspace,
)


class QdrantProvider(Provider):
    """Read-only collection inventory provider for Qdrant."""

    def __init__(
        self,
        service: dict[str, Any],
        *,
        api_key: str | None = None,
        timeout_seconds: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
        policy_getter: Callable[[], QdrantPolicy] = (
            get_qdrant_policy
        ),
    ) -> None:
        self._service = service
        self._api_key = (
            api_key
            if api_key is not None
            else os.getenv("QDRANT_API_KEY")
        )
        self._timeout_seconds = timeout_seconds
        self._transport = transport
        self._policy_getter = policy_getter

        protocol = service.get("protocol", "http")
        host = service["host"]
        port = service.get("port", 6333)
        self._base_url = f"{protocol}://{host}:{port}/"

        self._metadata = ProviderMetadata(
            id="qdrant",
            name=service.get("name", "Qdrant"),
            version="1.0.0",
            description=(
                "Vector database health and collection inventory "
                "provider."
            ),
            workspace=ProviderWorkspace.KNOWLEDGE,
            icon="database-zap",
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
            headers["api-key"] = self._api_key
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
                    self._url("/collections"),
                    headers=self._headers(),
                )
                response.raise_for_status()
                payload = response.json()

            collections = self._collection_names(payload)
            policy = self._policy_getter()
            expected_collections = set(
                policy.expected_collections
            )
            missing = sorted(
                expected_collections - set(collections)
            )
            return ProviderHealth(
                status="online",
                latency_ms=self._elapsed_ms(started_at),
                http_status=response.status_code,
                message="Qdrant collection API is available.",
                details={
                    "url": self._base_url.rstrip("/"),
                    "authenticated": bool(self._api_key),
                    "collection_count": len(collections),
                    "collections": collections,
                    "expected_collection_count": len(
                        expected_collections
                    ),
                    "missing_expected_collections": missing,
                },
            )
        except httpx.HTTPStatusError as error:
            status_code = error.response.status_code
            return ProviderHealth(
                status="degraded",
                latency_ms=self._elapsed_ms(started_at),
                http_status=status_code,
                message=(
                    "Qdrant API authentication failed."
                    if status_code in {401, 403}
                    else "Qdrant returned an unexpected status."
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
                message="Qdrant collection API is unavailable.",
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
                    id=f"qdrant-api-{health.status}",
                    severity=(
                        Severity.CRITICAL
                        if critical
                        else Severity.WARNING
                    ),
                    category="knowledge",
                    source="qdrant",
                    component=self.metadata.name,
                    title=f"Qdrant API {health.status}",
                    message=(
                        health.message
                        or "Qdrant collection API is not healthy."
                    ),
                    recommendation=(
                        "Review Qdrant connectivity, API credentials, "
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
        missing = health.details.get(
            "missing_expected_collections",
            [],
        )
        if isinstance(missing, list) and missing:
            severity = self._severity(
                policy.missing_collection_severity
            )
            findings.append(
                Finding(
                    id="qdrant-expected-collections-missing",
                    severity=severity,
                    category="knowledge",
                    source="qdrant",
                    component=self.metadata.name,
                    title="Qdrant collections missing",
                    message=(
                        f"{len(missing)} expected Qdrant "
                        "collection(s) are missing."
                    ),
                    recommendation=(
                        "Review collection provisioning, restoration, "
                        "and the expected_collections inventory."
                    ),
                    affects_health=severity != Severity.INFO,
                    score_penalty=self._score_penalty(severity),
                    metric={
                        "missing_collections": len(missing),
                        "expected_collections": int(
                            health.details.get(
                                "expected_collection_count",
                                0,
                            ),
                        ),
                    },
                    details={"collections": missing},
                ),
            )

        if health.details.get("collection_count") == 0:
            severity = self._severity(
                policy.empty_instance_severity
            )
            findings.append(
                Finding(
                    id="qdrant-no-collections",
                    severity=severity,
                    category="knowledge",
                    source="qdrant",
                    component=self.metadata.name,
                    title="Qdrant has no collections",
                    message=(
                        "Qdrant is online but reports no vector "
                        "collections."
                    ),
                    recommendation=(
                        "Confirm whether this Qdrant instance should "
                        "contain indexed knowledge."
                    ),
                    affects_health=severity != Severity.INFO,
                    score_penalty=self._score_penalty(severity),
                ),
            )

        return findings

    @staticmethod
    def _collection_names(payload: object) -> list[str]:
        if not isinstance(payload, dict):
            raise ValueError(
                "Qdrant returned an invalid collections response."
            )
        result = payload.get("result")
        if not isinstance(result, dict):
            raise ValueError(
                "Qdrant returned an invalid collections result."
            )
        collections = result.get("collections")
        if not isinstance(collections, list):
            raise ValueError(
                "Qdrant returned an invalid collections list."
            )

        names: list[str] = []
        for collection in collections:
            if (
                not isinstance(collection, dict)
                or not isinstance(collection.get("name"), str)
                or not collection["name"]
            ):
                raise ValueError(
                    "Qdrant returned an invalid collection entry."
                )
            names.append(collection["name"])
        return sorted(set(names))

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
