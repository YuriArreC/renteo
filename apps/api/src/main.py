"""FastAPI application entrypoint.

Health endpoints only at this stage. Routers are wired in subsequent phases.
"""

from fastapi import FastAPI

from src.config import settings
from src.lib.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

app = FastAPI(
    title="Renteo API",
    version=settings.app_version,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)


@app.get("/healthz", tags=["health"])
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz", tags=["health"])
async def readyz() -> dict[str, str]:
    return {"status": "ok"}
