"""Context engine for Atlas Agent."""


from app.context.exceptions import ContextConflictError
from app.context.models import AgentContext, ServiceHealth
from app.core_client.client import AtlasCoreClient


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
            services=normalized_services
        )
