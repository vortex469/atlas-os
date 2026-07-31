"""Context engine for Atlas Agent."""

import logging

from app.context.exceptions import ContextConflictError
from app.context.models import (
    INTELLIGENCE_FAILURE_MESSAGES,
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
from app.core_client.models import AtlasCoreIntelligenceSummary

logger = logging.getLogger("atlas-agent")

_INTELLIGENCE_FAILURES = {
    AtlasCoreConnectionError: "connection_error",
    AtlasCoreTimeoutError: "timeout",
    AtlasCoreResponseError: "response_error",
    AtlasCorePayloadError: "payload_error",
}


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
        if health.atlas != status.atlas:
            raise ContextConflictError(f"Atlas mismatch: health reported {health.atlas}, status reported {status.atlas}")

        intelligence = await self._get_intelligence()

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
