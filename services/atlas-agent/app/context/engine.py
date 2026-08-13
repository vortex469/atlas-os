"""Context engine for Atlas Agent."""

import logging

from app.context.exceptions import ContextConflictError
from app.context.models import (
    ACTION_HISTORY_FAILURE_MESSAGES,
    INTELLIGENCE_FAILURE_MESSAGES,
    ActionHistoryContext,
    ActionHistoryEntry,
    ActionHistoryFailure,
    AgentContext,
    IntelligenceAssessment,
    IntelligenceContext,
    IntelligenceFailure,
    IntelligenceFinding,
    IntelligenceRecommendation,
    ServiceHealth,
)
from app.core_client.client import AtlasCoreClient
from app.core_client.exceptions import (
    AtlasCoreClientError,
    AtlasCoreConnectionError,
    AtlasCorePayloadError,
    AtlasCoreResponseError,
    AtlasCoreTimeoutError,
)
from app.core_client.models import (
    AtlasCoreActionHistoryEntry,
    AtlasCoreIntelligenceSummary,
)

logger = logging.getLogger("atlas-agent")

_INTELLIGENCE_FAILURES = {
    AtlasCoreConnectionError: "connection_error",
    AtlasCoreTimeoutError: "timeout",
    AtlasCoreResponseError: "response_error",
    AtlasCorePayloadError: "payload_error",
}
_ACTION_HISTORY_LIMIT = 25
_ACTION_HISTORY_MESSAGE_LIMIT = 240
_AVAILABLE_HEALTH_STATES = frozenset({"healthy"})
_AVAILABLE_STATUS_STATES = frozenset({"online"})
_UNAVAILABLE_HEALTH_STATES = frozenset(
    {"critical", "degraded", "offline", "unknown"}
)
_UNAVAILABLE_STATUS_STATES = frozenset(
    {"critical", "degraded", "offline", "unknown"}
)


class ContextEngine:
    """Engine for fetching and normalizing context from Atlas Core."""

    def __init__(self, core_client: AtlasCoreClient) -> None:
        self.core_client = core_client

    async def get_context(self) -> AgentContext:
        """Fetch and normalize context from Atlas Core."""
        # Fetch health and status from Atlas Core
        health = await self.core_client.get_health()
        status = await self.core_client.get_status()

        # Check for atlas mismatch
        if not _atlas_states_compatible(health.atlas, status.atlas):
            raise ContextConflictError(
                "Atlas mismatch: "
                f"health reported {health.atlas}, status reported {status.atlas}"
            )

        intelligence = await self._get_intelligence()
        action_history = await self._get_action_history()

        # Normalize services data
        normalized_services = {}
        for service_name, service_health in health.services.items():
            normalized_services[service_name] = ServiceHealth(
                provider_id=service_health.provider_id,
                status=service_health.status,
                latency_ms=service_health.latency_ms,
                http_status=service_health.http_status,
                message=service_health.message,
                details=service_health.details
            )

        # Create AgentContext
        return AgentContext(
            atlas=status.atlas,
            assistant=status.assistant,
            engine=status.engine,
            release=status.release,
            services=normalized_services,
            intelligence=intelligence,
            action_history=action_history,
        )

    async def _get_intelligence(self) -> IntelligenceContext:
        try:
            summary = await self.core_client.get_intelligence_summary()
        except AtlasCoreClientError as error:
            logger.warning(
                "Atlas intelligence enrichment failed",
                exc_info=error,
            )
            code = _INTELLIGENCE_FAILURES[type(error)]
            return IntelligenceContext(
                failure=IntelligenceFailure(
                    code=code,
                    message=INTELLIGENCE_FAILURE_MESSAGES[code],
                )
            )

        return self._normalize_intelligence(summary)

    async def _get_action_history(self) -> ActionHistoryContext:
        try:
            entries = await self.core_client.get_action_history(
                limit=_ACTION_HISTORY_LIMIT,
            )
        except AtlasCoreClientError as error:
            logger.warning(
                "Atlas action history enrichment failed",
                exc_info=error,
            )
            code = _INTELLIGENCE_FAILURES[type(error)]
            return ActionHistoryContext(
                failure=ActionHistoryFailure(
                    code=code,
                    message=ACTION_HISTORY_FAILURE_MESSAGES[code],
                )
            )

        return self._normalize_action_history(entries)

    @staticmethod
    def _normalize_intelligence(
        summary: AtlasCoreIntelligenceSummary,
    ) -> IntelligenceContext:
        return IntelligenceContext(
            findings=tuple(
                IntelligenceFinding(
                    identifier=finding.id,
                    severity=finding.severity,
                    category=finding.category,
                    source=finding.source,
                    title=finding.title,
                    message=finding.message,
                    recommendation=finding.recommendation,
                    component=finding.component,
                    affects_health=finding.affects_health,
                )
                for finding in summary.findings
            ),
            assessments=tuple(
                IntelligenceAssessment(
                    title=assessment.title,
                    priority=assessment.priority,
                    component=assessment.component,
                )
                for assessment in summary.assessments
            ),
            recommendations=tuple(
                IntelligenceRecommendation(
                    title=recommendation.title,
                    reason=recommendation.reason,
                    priority=recommendation.priority,
                    confidence=recommendation.confidence,
                    estimated_effort=recommendation.estimated_effort,
                    component=recommendation.component,
                )
                for recommendation in summary.recommendations
            ),
        )

    @staticmethod
    def _normalize_action_history(
        entries: tuple[AtlasCoreActionHistoryEntry, ...],
    ) -> ActionHistoryContext:
        return ActionHistoryContext(
            entries=tuple(
                ActionHistoryEntry(
                    identifier=entry.id,
                    provider_id=entry.provider_id,
                    provider_name=entry.provider_name,
                    action_id=entry.action_id,
                    action_label=entry.action_label,
                    status=entry.status,
                    success=entry.success,
                    message=_bounded_message(entry.message),
                    confirmed=entry.confirmed,
                    destructive=entry.destructive,
                    parameter_names=tuple(entry.parameter_names),
                    request_id=entry.request_id,
                    started_at=entry.started_at,
                    completed_at=entry.completed_at,
                    duration_ms=entry.duration_ms,
                )
                for entry in entries
            )
        )


def _bounded_message(message: str) -> str:
    normalized = " ".join(message.split())
    if len(normalized) <= _ACTION_HISTORY_MESSAGE_LIMIT:
        return normalized
    return normalized[: _ACTION_HISTORY_MESSAGE_LIMIT - 1].rstrip() + "…"


def _atlas_states_compatible(health_state: str, status_state: str) -> bool:
    health = _normalize_atlas_state(health_state)
    status = _normalize_atlas_state(status_state)

    if health == status:
        return True
    if health in _AVAILABLE_HEALTH_STATES:
        return status in _AVAILABLE_STATUS_STATES
    if health in _UNAVAILABLE_HEALTH_STATES:
        return status in _UNAVAILABLE_STATUS_STATES
    return False


def _normalize_atlas_state(state: str) -> str:
    return state.strip().lower()
