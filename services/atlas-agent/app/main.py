"""Atlas Agent FastAPI application."""

import logging

from fastapi import FastAPI

from app.approval.engine import ApprovalEngine
from app.approval.repository import ApprovalRepository
from app.config.settings import Settings, load_settings
from app.container.application import ApplicationContainer
from app.context.engine import ContextEngine
from app.core_client.client import AtlasCoreClient
from app.execution.engine import ExecutionEngine
from app.execution.runner import SubprocessRunner
from app.model_providers.ollama import OllamaProvider
from app.model_service.service import ModelService
from app.persistence.snapshot import AgentStatePersistenceCoordinator
from app.planning.advisor import PlanningAdvisor
from app.planning.engine import PlanningEngine
from app.repository.inspector import GitInspector
from app.review.advisor import ReviewAdvisor
from app.review.engine import ReviewEngine
from app.routes.approval import router as approval_router
from app.routes.health import router as health_router
from app.routes.status import router as status_router
from app.routes.workflow import router as workflow_router
from app.verification.engine import VerificationEngine
from app.version import AGENT_VERSION
from app.workflow.engine import WorkflowEngine
from app.workflow.orchestrator import WorkflowOrchestrator
from app.workflow.state import WorkflowStateStore

logger = logging.getLogger("atlas-agent")


def configure_logging(settings: Settings) -> None:
    """Configure standard console logging."""

    log_level = getattr(
        logging,
        settings.log_level.upper(),
        logging.INFO,
    )

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def create_app() -> FastAPI:
    """Create and configure the Atlas Agent application."""

    settings = load_settings()
    configure_logging(settings)

    logger.info(
        "Starting %s version=%s environment=%s host=%s port=%s "
        "repository_root=%s",
        settings.app_name,
        AGENT_VERSION,
        settings.environment,
        settings.host,
        settings.port,
        settings.repository_root,
    )

    # Create a single core client instance
    core_client = AtlasCoreClient(
        settings=settings,
    )
    model_service = ModelService(
        provider=OllamaProvider(
            base_url=settings.ollama_base_url,
            timeout_seconds=settings.atlas_core_timeout_seconds,
        ),
        default_model=settings.ollama_default_model,
    )

    planning_advisor = PlanningAdvisor(
        model_service=model_service,
    )
    review_advisor = ReviewAdvisor(
        model_service=model_service,
    )

    workflow_state = WorkflowStateStore()
    approval_repository = ApprovalRepository()
    state_persistence = AgentStatePersistenceCoordinator(
        state_dir=settings.state_dir,
        workflow_state=workflow_state,
        approval_repository=approval_repository,
    )
    state_persistence.initialize()
    runner = SubprocessRunner()
    context_engine = ContextEngine(core_client)
    workflow_engine = WorkflowEngine(
        repository_inspector_factory=GitInspector,
        planning_engine=PlanningEngine(),
        execution_engine=ExecutionEngine(runner),
        verification_engine=VerificationEngine(runner),
        review_engine=ReviewEngine(),
        approval_engine=ApprovalEngine(),
        approval_repository=approval_repository,
        state_store=workflow_state,
        planning_mode=settings.planning_mode,
        planning_advisor=planning_advisor,
        review_mode=settings.review_mode,
        review_advisor=review_advisor,
        state_persistence=state_persistence,
    )
    workflow_orchestrator = WorkflowOrchestrator(
        workflow_engine=workflow_engine,
        context_engine=context_engine,
        atlas_core_required=settings.atlas_core_required,
    )

    container = ApplicationContainer(
        settings=settings,
        repository_inspector=GitInspector(
            repository_root=settings.repository_root,
        ),
        workflow_state=workflow_state,
        core_client=core_client,
        context_engine=context_engine,
        approval_repository=approval_repository,
        model_service=model_service,
        planning_advisor=planning_advisor,
        review_advisor=review_advisor,
        workflow_engine=workflow_engine,
        workflow_orchestrator=workflow_orchestrator,
        state_persistence=state_persistence,
    )

    application = FastAPI(
        title=settings.app_name,
        version=AGENT_VERSION,
    )
    application.state.container = container
    application.include_router(health_router)
    application.include_router(status_router)
    application.include_router(approval_router)
    application.include_router(workflow_router)

    return application


app = create_app()
