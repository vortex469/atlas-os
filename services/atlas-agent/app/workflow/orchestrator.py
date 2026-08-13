"""Application composition for context-aware workflow execution."""

import logging

from app.context.engine import ContextEngine
from app.workflow.engine import WorkflowEngine
from app.workflow.models import WorkflowRequest, WorkflowResult

logger = logging.getLogger("atlas-agent")


class WorkflowOrchestrator:
    """Capture Atlas context before invoking the synchronous workflow."""

    def __init__(
        self,
        *,
        workflow_engine: WorkflowEngine,
        context_engine: ContextEngine,
        atlas_core_required: bool = False,
    ) -> None:
        self._workflow_engine = workflow_engine
        self._context_engine = context_engine
        self._atlas_core_required = atlas_core_required

    async def run(self, request: WorkflowRequest) -> WorkflowResult:
        """Capture one context snapshot and run the workflow."""

        try:
            context = await self._context_engine.get_context()
        except Exception:
            logger.exception("Atlas Core context acquisition failed")
            if self._atlas_core_required:
                return self._workflow_engine.block_before_planning(
                    request,
                    error_message="Atlas Core context acquisition failed",
                )
            context = None

        return self._workflow_engine.run(request, context=context)
