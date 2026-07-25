from __future__ import annotations

import asyncio
from typing import Any

from app.application.ai_service import ai_service
from app.models.dashboard import (
    AISummary,
    AlertSummary,
    AtlasSummary,
    Dashboard,
    HealthSummary,
    ServiceSummary,
)
from app.models.health import HealthState
from app.services.intelligence_service import get_intelligence_summary
from app.services.summary_service import get_ops_summary


_STATUS_PRIORITY = {
    HealthState.UNKNOWN: 0,
    HealthState.HEALTHY: 1,
    HealthState.WARNING: 2,
    HealthState.DEGRADED: 3,
    HealthState.CRITICAL: 4,
    HealthState.OFFLINE: 5,
}


def _health_state(value: Any) -> HealthState:
    if isinstance(value, HealthState):
        return value

    normalized = str(value or "").strip().lower()

    aliases = {
        "ok": HealthState.HEALTHY,
        "online": HealthState.HEALTHY,
        "running": HealthState.HEALTHY,
        "healthy": HealthState.HEALTHY,
        "info": HealthState.HEALTHY,
        "warning": HealthState.WARNING,
        "warn": HealthState.WARNING,
        "degraded": HealthState.DEGRADED,
        "critical": HealthState.CRITICAL,
        "error": HealthState.CRITICAL,
        "failed": HealthState.CRITICAL,
        "offline": HealthState.OFFLINE,
        "unavailable": HealthState.OFFLINE,
        "unknown": HealthState.UNKNOWN,
    }

    return aliases.get(normalized, HealthState.UNKNOWN)


def _finding_state(finding: dict[str, Any]) -> HealthState:
    severity = str(finding.get("severity", "")).lower()

    if severity == "critical":
        return HealthState.CRITICAL

    if severity in {"warning", "warn"}:
        return HealthState.WARNING

    if severity == "info":
        return HealthState.HEALTHY

    return HealthState.UNKNOWN


def _merge_state(
    current: HealthState,
    candidate: HealthState,
) -> HealthState:
    if _STATUS_PRIORITY[candidate] > _STATUS_PRIORITY[current]:
        return candidate

    return current


def _build_atlas(ops: dict[str, Any]) -> AtlasSummary:
    return AtlasSummary(
        release=ops.get("release"),
        status=ops.get("atlas"),
        assistant=ops.get("assistant"),
        timestamp=ops.get("timestamp"),
    )


def _build_health(
    intelligence: dict[str, Any],
) -> HealthSummary:
    findings = intelligence.get("findings", [])

    warnings = sum(
        1
        for finding in findings
        if finding.get("severity") == "warning"
    )

    critical = sum(
        1
        for finding in findings
        if finding.get("severity") == "critical"
    )

    return HealthSummary(
        score=intelligence.get("score") or 0,
        state=_health_state(intelligence.get("status")),
        warnings=warnings,
        critical=critical,
    )


def _build_ai(ai: dict[str, Any]) -> AISummary:
    provider = ai.get("provider", {})
    health = ai.get("health", {})
    models = ai.get("models", {})

    return AISummary(
        provider=provider.get("name"),
        online=bool(provider.get("online", False)),
        health=health.get("status"),
        latency_ms=health.get("latency_ms"),
        installed_models=models.get("installed_count", 0),
        running_models=models.get("running_count", 0),
    )


def _build_services(
    intelligence: dict[str, Any],
) -> dict[str, ServiceSummary]:
    service_states: dict[str, HealthState] = {}

    for finding in intelligence.get("findings", []):
        source = finding.get("source")

        if not source:
            continue

        current = service_states.get(
            source,
            HealthState.UNKNOWN,
        )

        candidate = _finding_state(finding)

        service_states[source] = _merge_state(
            current,
            candidate,
        )

    return {
        service: ServiceSummary(status=state)
        for service, state in service_states.items()
    }


def _build_alerts(
    intelligence: dict[str, Any],
) -> list[AlertSummary]:
    alerts: list[AlertSummary] = []

    for finding in intelligence.get("findings", []):
        severity = str(
            finding.get("severity", "")
        ).lower()

        if severity not in {"warning", "critical"}:
            continue

        alerts.append(
            AlertSummary(
                severity=severity,
                title=finding.get(
                    "message",
                    finding.get(
                        "title",
                        "Atlas alert",
                    ),
                ),
            )
        )

    return alerts


async def get_dashboard() -> Dashboard:
    ai_task = asyncio.create_task(ai_service.status())

    ops = get_ops_summary()

    try:
        intelligence = get_intelligence_summary()
    except Exception as error:
        intelligence = {
            "score": 0,
            "status": "unknown",
            "findings": [],
            "recommendations": [],
            "error": str(error),
        }

    try:
        ai = await ai_task
    except Exception as error:
        ai = {
            "provider": {
                "name": None,
                "online": False,
            },
            "health": {
                "status": "unavailable",
            },
            "models": {},
            "error": str(error),
        }

    return Dashboard(
        atlas=_build_atlas(ops),
        health=_build_health(intelligence),
        ai=_build_ai(ai),
        services=_build_services(intelligence),
        alerts=_build_alerts(intelligence),
    )
