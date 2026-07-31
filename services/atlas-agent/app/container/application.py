"""Application dependency container."""

from dataclasses import dataclass

from app.approval.repository import ApprovalRepository
from app.config.settings import Settings
from app.context.engine import ContextEngine
from app.core_client.client import AtlasCoreClient
from app.model_service.service import ModelService
from app.persistence.snapshot import AgentStatePersistenceCoordinator
from app.planning.advisor import PlanningAdvisor
from app.repository.inspector import GitInspector
from app.review.advisor import ReviewAdvisor
from app.workflow.engine import WorkflowEngine
from app.workflow.orchestrator import WorkflowOrchestrator
from app.workflow.state import WorkflowStateStore


@dataclass(frozen=True, slots=True)
class ApplicationContainer:
    """Dependencies shared by the Atlas Agent application."""

    settings: Settings
    core_client: AtlasCoreClient
    context_engine: ContextEngine
    repository_inspector: GitInspector
    workflow_state: WorkflowStateStore
    approval_repository: ApprovalRepository
    model_service: ModelService
    planning_advisor: PlanningAdvisor
    review_advisor: ReviewAdvisor
    workflow_engine: WorkflowEngine
    workflow_orchestrator: WorkflowOrchestrator
    state_persistence: AgentStatePersistenceCoordinator | None = None
