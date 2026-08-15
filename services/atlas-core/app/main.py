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

configure_logging()
logger = get_logger("atlas")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Atlas Core starting")
    assert_restore_state_clean(
        Path(settings.operational_dispatch.database).parent
    )
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

    operator_settings = settings.operator_auth
    app.state.operator_intent_store = OperatorIntentStore(
        operator_settings.intent_database
    )
    app.state.operator_auth_enabled = operator_settings.enabled
    app.state.operator_auth_trusted_origins = frozenset(operator_settings.trusted_origins)
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
            return await proxmox_verifier.verify(
                request, result, deadline=deadline
            )

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
