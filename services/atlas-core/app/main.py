from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config.validation import validate_configuration
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestLoggingMiddleware
from app.providers.loader import load_provider_registry
from app.routes.ace import router as ace_router
from app.routes.analysis import router as analysis_router
from app.routes.docker import router as docker_router
from app.routes.health import router as health_router
from app.routes.homeassistant import router as home_router
from app.routes.intelligence import router as intelligence_router
from app.routes.ops import router as ops_router
from app.routes.proxmox import router as proxmox_router
from app.routes.providers import router as providers_router
from app.routes.ai import router as ai_router

configure_logging()
logger = get_logger("atlas")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Atlas Core starting")

    validate_configuration()
    logger.info("Atlas configuration validated")

    load_provider_registry()
    logger.info("Provider registry initialized")

    logger.info("Atlas Cognitive Engine ready")
    logger.info("Atlas Core ready")

    yield

    logger.info("Atlas Core shutting down")


app = FastAPI(
    title="Atlas Core",
    version="0.3.0-alpha1",
    lifespan=lifespan,
)

app.add_middleware(RequestLoggingMiddleware)


@app.get("/")
def root():
    return {
        "atlas": "online",
        "assistant": "Orion",
        "reasoning_engine": "Hermes",
        "cognitive_engine": "ACE",
        "release": "0.3-intelligence",
    }


app.include_router(analysis_router)
app.include_router(health_router)
app.include_router(providers_router)
app.include_router(ops_router)
app.include_router(docker_router)
app.include_router(proxmox_router)
app.include_router(home_router)
app.include_router(intelligence_router)
app.include_router(ace_router)
app.include_router(analysis_router)
app.include_router(health_router)
app.include_router(providers_router)
app.include_router(ai_router)
app.include_router(ops_router)