"""FastAPI application entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.lib.logging import configure_logging, get_logger
from src.routers import calculations as calculations_router
from src.routers import comparador as comparador_router
from src.routers import me as me_router
from src.routers import scenario as scenario_router
from src.routers import workspaces as workspaces_router

configure_logging()
logger = get_logger(__name__)

app = FastAPI(
    title="Renteo API",
    version=settings.app_version,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

if settings.cors_allowed_origins_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )


@app.get("/healthz", tags=["health"])
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz", tags=["health"])
async def readyz() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(me_router.router)
app.include_router(workspaces_router.router)
app.include_router(calculations_router.router)
app.include_router(comparador_router.router)
app.include_router(scenario_router.router)
