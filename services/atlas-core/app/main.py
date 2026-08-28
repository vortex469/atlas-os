from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError

from app.api.v1.router import router as api_v1_router
from app.config.settings import settings
from app.config.validation import validate_configuration
from app.core.exceptions import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestLoggingMiddleware
from app.core.restore_interlock import assert_restore_state_clean
from app.execution_candidates.operator_intents import OperatorIntentStore
from app.installation_approval_intent.service import InstallationApprovalIntentService
from app.installation_approval_intent.store import InstallationApprovalIntentStore
from app.installation_assessment.cache import EphemeralAssessmentRetryCache
from app.installation_candidate_admission.assembly import (
    InstallationCandidateAdmissionReadDependency,
)
from app.installation_candidate_lifecycle.service import (
    InstallationCandidateLifecycleService,
)
from app.installation_candidate_lifecycle.store import (
    InstallationCandidateRecordStore,
)
from app.installation_capability.assembly import (
    InstallationCapabilityAssessmentReadDependency,
)
from app.installation_dispatch_handoff.service import InstallationDispatchHandoffService
from app.installation_dispatch_handoff.store import InstallationDispatchHandoffStore
from app.installation_execution_request.service import (
    InstallationExecutionRequestService,
)
from app.installation_execution_request.store import (
    InstallationExecutionRequestStore,
)
from app.installation_targets.resolver import (
    enumerate_destinations,
    resolve_operational_target,
)
from app.installation_targets.service import (
    InstallationDestinationSelectionService,
)
from app.installation_targets.service import (
    utc_server_clock as assessment_clock,
)
from app.installation_targets.store import InstallationDestinationSelectionStore
from app.intelligence.development_fixture import (
    development_fixture_enabled_and_validated,
)
from app.operational_dispatch.auth import OperationalDispatchAuthenticator
from app.operational_dispatch.ledger import OperationalDispatchLedger
from app.operational_dispatch.lifecycle import (
    OperationalLifecycleService,
    OperationalVerifierRegistry,
)
from app.operational_dispatch.production import (
    build_production_operational_handler_registry,
)
from app.operational_dispatch.registry import OperationalHandlerRegistry
from app.operational_dispatch.service import OperationalDispatchService
from app.operator_auth.audit import OperatorSecurityAuditStore
from app.operator_auth.credentials import OperatorCredentialVerifier
from app.operator_auth.rate_limit import OperatorRateLimiter
from app.operator_auth.sessions import OperatorSessionStore
from app.provider_intents.activation import validate_provider_intent_activation
from app.provider_intents.authority import configure_monitoring_intent_authority
from app.providers.loader import load_provider_registry
from app.providers.proxmox import ProxmoxProvider
from app.providers.proxmox_operational import ProxmoxQemuVerificationService
from app.providers.registry import provider_registry
from app.routes.ace import router as ace_router
from app.routes.ai import router as ai_router
from app.routes.analysis import router as analysis_router
from app.routes.dashboard import router as dashboard_router
from app.routes.docker import router as docker_router
from app.routes.health import router as health_router
from app.routes.homeassistant import router as home_router
from app.routes.intelligence import router as intelligence_router
from app.routes.ops import router as ops_router
from app.routes.policies import router as policies_router
from app.routes.providers import router as providers_router
from app.routes.proxmox import router as proxmox_router
from app.services.discovery_dynamic_activation import DynamicDiscoveryActivation
from app.services.installation_plan import get_installation_plan_read_dependency

configure_logging()
logger = get_logger("atlas")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Atlas Core starting")
    assert_restore_state_clean(Path(settings.operational_dispatch.database).parent)
    validate_configuration()
    logger.info("Atlas configuration validated")
    provider_intent_store = validate_provider_intent_activation(
        settings.provider_intents
    )
    app.state.monitoring_intent_authority = configure_monitoring_intent_authority(
        settings.provider_intents,
        provider_intent_store,
    )
    development_fixture_enabled_and_validated()

    discovery_activation = None
    if settings.dynamic_discovery.enabled:
        discovery_activation = await DynamicDiscoveryActivation.start()
        logger.info("Dynamic Discovery initial refresh completed")

    operator_settings = settings.operator_auth
    app.state.operator_intent_store = OperatorIntentStore(
        operator_settings.intent_database
    )
    app.state.operator_auth_enabled = operator_settings.enabled
    app.state.operator_auth_trusted_origins = frozenset(
        operator_settings.trusted_origins
    )
    if operator_settings.enabled:
        app.state.operator_credential_verifier = OperatorCredentialVerifier(
            operator_settings.verifier_file
        )
        app.state.operator_session_store = OperatorSessionStore(
            operator_settings.session_database,
            operator_settings.session_lifetime_seconds,
        )
        app.state.operator_security_audit = OperatorSecurityAuditStore(
            operator_settings.audit_database
        )
        app.state.operator_login_rate_limiter = OperatorRateLimiter(
            operator_settings.login_rate_limit,
            operator_settings.rate_limit_window_seconds,
        )
        app.state.operator_mutation_rate_limiter = OperatorRateLimiter(
            operator_settings.mutation_rate_limit,
            operator_settings.rate_limit_window_seconds,
        )

    load_provider_registry()
    logger.info("Provider registry initialized")

    app.state.installation_destination_selection_store = (
        InstallationDestinationSelectionStore(
            operator_settings.installation_selection_database
        )
    )
    app.state.installation_destination_selection_service = (
        InstallationDestinationSelectionService(
            store=app.state.installation_destination_selection_store,
            resolver=resolve_operational_target,
        )
    )
    app.state.installation_destination_enumerator = enumerate_destinations
    app.state.installation_assessment_retry_cache = EphemeralAssessmentRetryCache()
    app.state.installation_assessment_clock = assessment_clock
    app.state.installation_capability_clock = assessment_clock
    app.state.installation_capability_target_resolver = resolve_operational_target
    app.state.installation_plan_read_dependency = (
        get_installation_plan_read_dependency()
    )
    app.state.installation_candidate_admission_read_dependency = (
        InstallationCandidateAdmissionReadDependency(
            plans=app.state.installation_plan_read_dependency,
            selections=app.state.installation_destination_selection_store,
            capabilities=InstallationCapabilityAssessmentReadDependency(
                target_resolver=resolve_operational_target,
                clock=assessment_clock,
            ),
            clock=assessment_clock,
        )
    )
    app.state.installation_candidate_record_store = InstallationCandidateRecordStore(
        operator_settings.installation_candidate_record_database
    )
    app.state.installation_candidate_lifecycle_service = (
        InstallationCandidateLifecycleService(
            store=app.state.installation_candidate_record_store,
            admissions=app.state.installation_candidate_admission_read_dependency,
        )
    )
    app.state.installation_approval_intent_store = InstallationApprovalIntentStore(
        operator_settings.installation_approval_intent_database,
        candidates=app.state.installation_candidate_record_store,
    )
    app.state.installation_approval_intent_service = InstallationApprovalIntentService(
        store=app.state.installation_approval_intent_store
    )
    app.state.installation_execution_request_store = InstallationExecutionRequestStore(
        operator_settings.installation_execution_request_database,
        candidates=app.state.installation_candidate_record_store,
        approvals=app.state.installation_approval_intent_store,
    )
    app.state.installation_execution_request_service = (
        InstallationExecutionRequestService(
            store=app.state.installation_execution_request_store,
            enabled=operator_settings.installation_execution_request_enabled,
        )
    )
    app.state.installation_dispatch_handoff_store = InstallationDispatchHandoffStore(
        operator_settings.installation_dispatch_handoff_database,
        execution_requests=app.state.installation_execution_request_store,
        candidates=app.state.installation_candidate_record_store,
        approvals=app.state.installation_approval_intent_store,
    )
    app.state.installation_dispatch_handoff_service = (
        InstallationDispatchHandoffService(
            store=app.state.installation_dispatch_handoff_store,
            enabled=operator_settings.installation_dispatch_handoff_enabled,
        )
    )

    operational_ledger = OperationalDispatchLedger(
        settings.operational_dispatch.database
    )
    reconciliation = operational_ledger.reconcile_startup()
    app.state.operational_dispatch_ledger = operational_ledger
    app.state.operational_dispatch_authenticator = OperationalDispatchAuthenticator(
        settings.operational_dispatch.agent_auth_file
    )
    verifier_registry = OperationalVerifierRegistry()
    proxmox_provider = provider_registry.get("proxmox")
    handler_registry = OperationalHandlerRegistry()
    if isinstance(proxmox_provider, ProxmoxProvider):
        handler_registry = build_production_operational_handler_registry(
            proxmox_provider.atlas_context
        )
        proxmox_verifier = ProxmoxQemuVerificationService(
            proxmox_provider.atlas_context
        )

        async def verify_proxmox_qemu(request, result, deadline):
            return await proxmox_verifier.verify(request, result, deadline=deadline)

        verifier_registry.register(
            execution_intent="restart-service",
            provider_id="proxmox",
            resource_type="qemu",
            verifier=verify_proxmox_qemu,
        )
    operational_dispatch_service = OperationalDispatchService(
        ledger=operational_ledger,
        registry=handler_registry,
    )
    app.state.operational_dispatch_service = operational_dispatch_service
    operational_lifecycle = OperationalLifecycleService(
        ledger=operational_ledger,
        dispatcher=operational_dispatch_service,
        verifiers=verifier_registry,
    )
    app.state.operational_lifecycle_service = operational_lifecycle
    recovery_scheduled = operational_lifecycle.schedule_startup_recovery()
    logger.info(
        "Operational dispatch ledger initialized",
        extra={
            "operational_reconciliation": reconciliation,
            "operational_recovery_scheduled": recovery_scheduled,
        },
    )

    logger.info("Atlas Cognitive Engine ready")
    logger.info("Atlas Core ready")

    yield

    if discovery_activation is not None:
        await discovery_activation.aclose()
    await operational_lifecycle.close()

    logger.info("Atlas Core shutting down")


app = FastAPI(
    title="Atlas Core",
    description="Central control-plane API for Atlas OS.",
    version="0.4.0-alpha1",
    lifespan=lifespan,
)

app.add_middleware(RequestLoggingMiddleware)

app.add_exception_handler(
    HTTPException,
    http_exception_handler,
)
app.add_exception_handler(
    RequestValidationError,
    validation_exception_handler,
)
app.add_exception_handler(
    Exception,
    unhandled_exception_handler,
)


@app.get("/", tags=["System"])
def root():
    return {
        "atlas": "online",
        "assistant": settings.atlas.assistant,
        "reasoning_engine": "Hermes",
        "cognitive_engine": "ACE",
        "release": settings.atlas.release,
        "api": {
            "current": "v1",
            "base_url": "/api/v1",
            "documentation": "/docs",
        },
    }


# Legacy endpoints retained for Dashboard v1 and existing integrations.
app.include_router(analysis_router)
app.include_router(health_router)
app.include_router(providers_router)
app.include_router(ops_router)
app.include_router(policies_router)
app.include_router(docker_router)
app.include_router(proxmox_router)
app.include_router(home_router)
app.include_router(intelligence_router)
app.include_router(ace_router)
app.include_router(ai_router)
app.include_router(dashboard_router)

# Versioned public API.
app.include_router(api_v1_router)
