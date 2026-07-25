from __future__ import annotations

import asyncio

from app.application.ai_service import ai_service
from app.services.intelligence_service import get_intelligence_summary
from app.services.summary_service import get_ops_summary


async def get_dashboard() -> dict:
    ai_task = asyncio.create_task(ai_service.status())

    ops = get_ops_summary()

    try:
        intelligence = get_intelligence_summary()
    except Exception as error:
        intelligence = {
            "status": "unavailable",
            "error": str(error),
        }

    try:
        ai = await ai_task
    except Exception as error:
        ai = {
            "status": "unavailable",
            "error": str(error),
        }

    operations_alerts = ops.get("alerts", {})

    intelligence_findings = intelligence.get("findings", [])
    intelligence_recommendations = intelligence.get(
        "recommendations",
        [],
    )

    ai_models = ai.get("models", {})
    ai_health = ai.get("health", {})
    ai_provider = ai.get("provider", {})

    return {
        "atlas": {
            "release": ops.get("release"),
            "status": ops.get("atlas"),
            "assistant": ops.get("assistant"),
            "timestamp": ops.get("timestamp"),
        },
        "ai": {
            "provider": ai_provider.get("name"),
            "online": ai_provider.get("online"),
            "health": ai_health.get("status"),
            "latency_ms": ai_health.get("latency_ms"),
            "installed_models": ai_models.get(
                "installed_count",
                0,
            ),
            "running_models": ai_models.get(
                "running_count",
                0,
            ),
        },
        "operations": {
            "status": ops.get("atlas"),
            "critical_services": len(
                operations_alerts.get(
                    "critical_services",
                    [],
                )
            ),
            "warnings": len(
                operations_alerts.get(
                    "warnings",
                    [],
                )
            ),
            "failed_sections": len(
                operations_alerts.get(
                    "failed_sections",
                    [],
                )
            ),
            "unhealthy_containers": operations_alerts.get(
                "unhealthy_containers",
                0,
            ),
            "unavailable_home_entities": operations_alerts.get(
                "unavailable_home_entities",
                0,
            ),
            "pending_home_updates": operations_alerts.get(
                "pending_home_updates",
                0,
            ),
        },
        "intelligence": {
            "score": intelligence.get("score"),
            "status": intelligence.get("status"),
            "summary": intelligence.get("summary"),
            "findings": len(intelligence_findings),
            "recommendations": len(
                intelligence_recommendations
            ),
        },
    }
