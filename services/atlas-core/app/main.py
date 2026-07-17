from fastapi import FastAPI

from app.routes.status import router as status_router
from app.routes.health import router as health_router
from app.routes.ops import router as ops_router

app = FastAPI(
    title="Atlas Core",
    version="0.1.0-foundry",
    description="Atlas Personal Infrastructure Operating System",
)

app.include_router(status_router)
app.include_router(health_router)
app.include_router(ops_router)
