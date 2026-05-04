"""FastAPI application entrypoint."""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import settings
from src.lib.errors import IneligibleForRegime, MissingRuleError, RedFlagBlocked
from src.lib.legal_texts import LegalTextNotFound
from src.lib.logging import configure_logging, get_logger
from src.routers import alertas as alertas_router
from src.routers import calculations as calculations_router
from src.routers import cartera as cartera_router
from src.routers import comparador as comparador_router
from src.routers import empresas as empresas_router
from src.routers import legal as legal_router
from src.routers import me as me_router
from src.routers import privacy as privacy_router
from src.routers import regime as regime_router
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


@app.exception_handler(RedFlagBlocked)
async def _red_flag_handler(
    _request: Request, exc: RedFlagBlocked
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": str(exc), "code": "red_flag_blocked"},
    )


@app.exception_handler(IneligibleForRegime)
async def _ineligible_handler(
    _request: Request, exc: IneligibleForRegime
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": str(exc), "code": "ineligible_for_regime"},
    )


@app.exception_handler(MissingRuleError)
async def _missing_rule_handler(
    _request: Request, exc: MissingRuleError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": str(exc), "code": "missing_rule"},
    )


@app.exception_handler(LegalTextNotFound)
async def _legal_text_handler(
    _request: Request, exc: LegalTextNotFound
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": str(exc), "code": "legal_text_missing"},
    )


app.include_router(me_router.router)
app.include_router(workspaces_router.router)
app.include_router(calculations_router.router)
app.include_router(comparador_router.router)
app.include_router(scenario_router.router)
app.include_router(regime_router.router)
app.include_router(legal_router.router)
app.include_router(legal_router.public_router)
app.include_router(empresas_router.router)
app.include_router(privacy_router.router)
app.include_router(alertas_router.router)
app.include_router(cartera_router.router)
