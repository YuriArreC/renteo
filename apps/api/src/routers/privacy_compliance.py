"""Cumplimiento Ley 21.719 — RAT y DPIA (skill 5).

Endpoints:
  RAT (Registro de Actividades de Tratamiento, art. 15-16):
    GET    /api/privacy/rat            list (ocultando archivados)
    POST   /api/privacy/rat            create
    PATCH  /api/privacy/rat/{id}       update
    DELETE /api/privacy/rat/{id}       archivar (soft delete)
  DPIA (Evaluación de Impacto, art. 35):
    GET    /api/privacy/dpia           list
    POST   /api/privacy/dpia           create
    PATCH  /api/privacy/dpia/{id}      update / aprobar
  Export:
    GET    /api/privacy/rat.xlsx       descarga registro completo
    GET    /api/privacy/dpia.xlsx      descarga evaluaciones

Auth: tenancy completa. Roles permitidos para mutar:
owner / accountant_lead (DPO designado o equivalente). Lectura
abierta a roles con tenancy del workspace. Audit log por mutación.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.tenancy import Tenancy, current_tenancy
from src.db import get_db_session
from src.lib.audit import log_audit

router = APIRouter(prefix="/api/privacy", tags=["privacy-compliance"])


_ALLOWED_DPO_ROLES = frozenset({"owner", "accountant_lead"})


BaseLegal = Literal[
    "consentimiento",
    "contrato",
    "interes_legitimo",
    "obligacion_legal",
    "interes_vital",
    "interes_publico",
]
RiesgoNivel = Literal["bajo", "medio", "alto"]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class RatCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre_actividad: str = Field(min_length=2, max_length=160)
    finalidad: str = Field(min_length=2, max_length=2000)
    base_legal: BaseLegal
    categorias_titulares: list[str] = Field(default_factory=list)
    categorias_datos: list[str] = Field(default_factory=list)
    datos_sensibles: bool = False
    encargados_referenciados: list[str] = Field(default_factory=list)
    transferencias_internacionales: list[dict[str, Any]] = Field(
        default_factory=list
    )
    plazo_conservacion: str = Field(min_length=2, max_length=400)
    medidas_seguridad: list[str] = Field(default_factory=list)
    responsable_email: str = Field(min_length=3, max_length=320)


class RatUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre_actividad: str | None = Field(default=None, max_length=160)
    finalidad: str | None = Field(default=None, max_length=2000)
    base_legal: BaseLegal | None = None
    categorias_titulares: list[str] | None = None
    categorias_datos: list[str] | None = None
    datos_sensibles: bool | None = None
    encargados_referenciados: list[str] | None = None
    transferencias_internacionales: list[dict[str, Any]] | None = None
    plazo_conservacion: str | None = Field(default=None, max_length=400)
    medidas_seguridad: list[str] | None = None
    responsable_email: str | None = Field(default=None, max_length=320)


class RatResponse(BaseModel):
    id: UUID
    nombre_actividad: str
    finalidad: str
    base_legal: BaseLegal
    categorias_titulares: list[str]
    categorias_datos: list[str]
    datos_sensibles: bool
    encargados_referenciados: list[str]
    transferencias_internacionales: list[dict[str, Any]]
    plazo_conservacion: str
    medidas_seguridad: list[str]
    responsable_email: str
    created_at: str
    updated_at: str
    archived_at: str | None


class RatListResponse(BaseModel):
    records: list[RatResponse]


class DpiaCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rat_id: UUID | None = None
    nombre_evaluacion: str = Field(min_length=2, max_length=160)
    descripcion_tratamiento: str = Field(min_length=2, max_length=4000)
    necesidad_proporcionalidad: str = Field(min_length=2, max_length=4000)
    riesgos_identificados: list[dict[str, Any]] = Field(default_factory=list)
    medidas_mitigacion: list[str] = Field(default_factory=list)
    riesgo_residual: RiesgoNivel


class DpiaUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rat_id: UUID | None = None
    nombre_evaluacion: str | None = Field(default=None, max_length=160)
    descripcion_tratamiento: str | None = Field(default=None, max_length=4000)
    necesidad_proporcionalidad: str | None = Field(default=None, max_length=4000)
    riesgos_identificados: list[dict[str, Any]] | None = None
    medidas_mitigacion: list[str] | None = None
    riesgo_residual: RiesgoNivel | None = None
    aprobar: bool = False


class DpiaResponse(BaseModel):
    id: UUID
    rat_id: UUID | None
    nombre_evaluacion: str
    descripcion_tratamiento: str
    necesidad_proporcionalidad: str
    riesgos_identificados: list[dict[str, Any]]
    medidas_mitigacion: list[str]
    riesgo_residual: RiesgoNivel
    aprobado_por_dpo_email: str | None
    aprobado_at: str | None
    version: int
    created_at: str
    updated_at: str


class DpiaListResponse(BaseModel):
    records: list[DpiaResponse]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_dpo(tenancy: Tenancy) -> None:
    if tenancy.role not in _ALLOWED_DPO_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Solo el DPO designado (owner / accountant_lead) puede "
                "modificar el RAT o las DPIA del workspace."
            ),
        )


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value)


def _row_to_rat(row: dict[str, Any]) -> RatResponse:
    return RatResponse(
        id=UUID(str(row["id"])),
        nombre_actividad=str(row["nombre_actividad"]),
        finalidad=str(row["finalidad"]),
        base_legal=row["base_legal"],
        categorias_titulares=list(row["categorias_titulares"] or []),
        categorias_datos=list(row["categorias_datos"] or []),
        datos_sensibles=bool(row["datos_sensibles"]),
        encargados_referenciados=list(
            row["encargados_referenciados"] or []
        ),
        transferencias_internacionales=list(
            row["transferencias_internacionales"] or []
        ),
        plazo_conservacion=str(row["plazo_conservacion"]),
        medidas_seguridad=list(row["medidas_seguridad"] or []),
        responsable_email=str(row["responsable_email"]),
        created_at=_iso(row["created_at"]) or "",
        updated_at=_iso(row["updated_at"]) or "",
        archived_at=_iso(row["archived_at"]),
    )


def _row_to_dpia(row: dict[str, Any]) -> DpiaResponse:
    return DpiaResponse(
        id=UUID(str(row["id"])),
        rat_id=UUID(str(row["rat_id"])) if row["rat_id"] else None,
        nombre_evaluacion=str(row["nombre_evaluacion"]),
        descripcion_tratamiento=str(row["descripcion_tratamiento"]),
        necesidad_proporcionalidad=str(row["necesidad_proporcionalidad"]),
        riesgos_identificados=list(row["riesgos_identificados"] or []),
        medidas_mitigacion=list(row["medidas_mitigacion"] or []),
        riesgo_residual=row["riesgo_residual"],
        aprobado_por_dpo_email=(
            str(row["aprobado_por_dpo_email"])
            if row["aprobado_por_dpo_email"] is not None
            else None
        ),
        aprobado_at=_iso(row["aprobado_at"]),
        version=int(row["version"]),
        created_at=_iso(row["created_at"]) or "",
        updated_at=_iso(row["updated_at"]) or "",
    )


# ---------------------------------------------------------------------------
# RAT endpoints
# ---------------------------------------------------------------------------


@router.get("/rat", response_model=RatListResponse)
async def list_rat(
    include_archived: bool = False,
    _tenancy: Tenancy = Depends(current_tenancy),
    session: AsyncSession = Depends(get_db_session),
) -> RatListResponse:
    base_query = """
        select id, nombre_actividad, finalidad, base_legal,
               categorias_titulares, categorias_datos,
               datos_sensibles, encargados_referenciados,
               transferencias_internacionales, plazo_conservacion,
               medidas_seguridad, responsable_email,
               created_at, updated_at, archived_at
          from privacy.rat_records
    """
    if include_archived:
        sql = base_query + " order by created_at desc"
    else:
        sql = (
            base_query
            + " where archived_at is null order by created_at desc"
        )
    result = await session.execute(text(sql))
    return RatListResponse(
        records=[_row_to_rat(dict(r)) for r in result.mappings().all()]
    )


@router.post(
    "/rat",
    response_model=RatResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_rat(
    payload: RatCreateRequest,
    tenancy: Tenancy = Depends(current_tenancy),
    session: AsyncSession = Depends(get_db_session),
) -> RatResponse:
    _require_dpo(tenancy)
    result = await session.execute(
        text(
            """
            insert into privacy.rat_records
                (workspace_id, nombre_actividad, finalidad, base_legal,
                 categorias_titulares, categorias_datos, datos_sensibles,
                 encargados_referenciados, transferencias_internacionales,
                 plazo_conservacion, medidas_seguridad, responsable_email)
            values
                (:ws, :nombre, :finalidad, :base,
                 cast(:cat_tit as jsonb), cast(:cat_dat as jsonb), :sens,
                 cast(:enc as jsonb), cast(:tr as jsonb),
                 :plazo, cast(:med as jsonb), :email)
            returning id, nombre_actividad, finalidad, base_legal,
                      categorias_titulares, categorias_datos,
                      datos_sensibles, encargados_referenciados,
                      transferencias_internacionales, plazo_conservacion,
                      medidas_seguridad, responsable_email,
                      created_at, updated_at, archived_at
            """
        ),
        {
            "ws": str(tenancy.workspace_id),
            "nombre": payload.nombre_actividad,
            "finalidad": payload.finalidad,
            "base": payload.base_legal,
            "cat_tit": json.dumps(payload.categorias_titulares),
            "cat_dat": json.dumps(payload.categorias_datos),
            "sens": payload.datos_sensibles,
            "enc": json.dumps(payload.encargados_referenciados),
            "tr": json.dumps(payload.transferencias_internacionales),
            "plazo": payload.plazo_conservacion,
            "med": json.dumps(payload.medidas_seguridad),
            "email": payload.responsable_email,
        },
    )
    row = result.mappings().one()
    rat = _row_to_rat(dict(row))
    await log_audit(
        session,
        workspace_id=tenancy.workspace_id,
        user_id=tenancy.user_id,
        action="create",
        resource_type="rat",
        resource_id=rat.id,
        metadata={
            "nombre_actividad": rat.nombre_actividad,
            "datos_sensibles": rat.datos_sensibles,
        },
    )
    return rat


@router.patch("/rat/{rat_id}", response_model=RatResponse)
async def update_rat(
    rat_id: UUID,
    payload: RatUpdateRequest,
    tenancy: Tenancy = Depends(current_tenancy),
    session: AsyncSession = Depends(get_db_session),
) -> RatResponse:
    _require_dpo(tenancy)
    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Sin campos a actualizar.",
        )
    set_parts: list[str] = []
    params: dict[str, Any] = {"id": str(rat_id)}
    for key, value in fields.items():
        if key in (
            "categorias_titulares",
            "categorias_datos",
            "encargados_referenciados",
            "transferencias_internacionales",
            "medidas_seguridad",
        ):
            set_parts.append(f"{key} = cast(:{key} as jsonb)")
            params[key] = json.dumps(value)
        else:
            set_parts.append(f"{key} = :{key}")
            params[key] = value

    # set_parts se construye desde un whitelist Pydantic estático
    # (los nombres de campos vienen de RatUpdateRequest, no del cliente);
    # los valores van como bind parameters, jamás como literales.
    set_clause = ", ".join(set_parts)
    sql = (
        "update privacy.rat_records set "  # noqa: S608
        + set_clause
        + " where id = :id returning id, nombre_actividad, finalidad, "
          "base_legal, categorias_titulares, categorias_datos, "
          "datos_sensibles, encargados_referenciados, "
          "transferencias_internacionales, plazo_conservacion, "
          "medidas_seguridad, responsable_email, "
          "created_at, updated_at, archived_at"
    )
    result = await session.execute(text(sql), params)
    row = result.mappings().first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="RAT no encontrado.",
        )
    await log_audit(
        session,
        workspace_id=tenancy.workspace_id,
        user_id=tenancy.user_id,
        action="update",
        resource_type="rat",
        resource_id=rat_id,
        metadata={"fields": sorted(fields.keys())},
    )
    return _row_to_rat(dict(row))


@router.delete("/rat/{rat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_rat(
    rat_id: UUID,
    tenancy: Tenancy = Depends(current_tenancy),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    _require_dpo(tenancy)
    result = await session.execute(
        text(
            """
            update privacy.rat_records
               set archived_at = now()
             where id = :id
               and archived_at is null
            returning id
            """
        ),
        {"id": str(rat_id)},
    )
    if result.first() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="RAT no encontrado o ya archivado.",
        )
    await log_audit(
        session,
        workspace_id=tenancy.workspace_id,
        user_id=tenancy.user_id,
        action="archive",
        resource_type="rat",
        resource_id=rat_id,
        metadata={},
    )


# ---------------------------------------------------------------------------
# DPIA endpoints
# ---------------------------------------------------------------------------


@router.get("/dpia", response_model=DpiaListResponse)
async def list_dpia(
    _tenancy: Tenancy = Depends(current_tenancy),
    session: AsyncSession = Depends(get_db_session),
) -> DpiaListResponse:
    result = await session.execute(
        text(
            """
            select id, rat_id, nombre_evaluacion, descripcion_tratamiento,
                   necesidad_proporcionalidad, riesgos_identificados,
                   medidas_mitigacion, riesgo_residual,
                   aprobado_por_dpo_email, aprobado_at, version,
                   created_at, updated_at
              from privacy.dpia_records
             order by created_at desc
            """
        )
    )
    return DpiaListResponse(
        records=[_row_to_dpia(dict(r)) for r in result.mappings().all()]
    )


@router.post(
    "/dpia",
    response_model=DpiaResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_dpia(
    payload: DpiaCreateRequest,
    tenancy: Tenancy = Depends(current_tenancy),
    session: AsyncSession = Depends(get_db_session),
) -> DpiaResponse:
    _require_dpo(tenancy)
    result = await session.execute(
        text(
            """
            insert into privacy.dpia_records
                (workspace_id, rat_id, nombre_evaluacion,
                 descripcion_tratamiento, necesidad_proporcionalidad,
                 riesgos_identificados, medidas_mitigacion,
                 riesgo_residual)
            values
                (:ws, :rat, :nombre, :desc, :nec,
                 cast(:riesgos as jsonb), cast(:medidas as jsonb),
                 :riesgo)
            returning id, rat_id, nombre_evaluacion, descripcion_tratamiento,
                      necesidad_proporcionalidad, riesgos_identificados,
                      medidas_mitigacion, riesgo_residual,
                      aprobado_por_dpo_email, aprobado_at, version,
                      created_at, updated_at
            """
        ),
        {
            "ws": str(tenancy.workspace_id),
            "rat": str(payload.rat_id) if payload.rat_id else None,
            "nombre": payload.nombre_evaluacion,
            "desc": payload.descripcion_tratamiento,
            "nec": payload.necesidad_proporcionalidad,
            "riesgos": json.dumps(payload.riesgos_identificados),
            "medidas": json.dumps(payload.medidas_mitigacion),
            "riesgo": payload.riesgo_residual,
        },
    )
    row = result.mappings().one()
    dpia = _row_to_dpia(dict(row))
    await log_audit(
        session,
        workspace_id=tenancy.workspace_id,
        user_id=tenancy.user_id,
        action="create",
        resource_type="dpia",
        resource_id=dpia.id,
        metadata={
            "nombre_evaluacion": dpia.nombre_evaluacion,
            "riesgo_residual": dpia.riesgo_residual,
        },
    )
    return dpia


@router.patch("/dpia/{dpia_id}", response_model=DpiaResponse)
async def update_dpia(
    dpia_id: UUID,
    payload: DpiaUpdateRequest,
    tenancy: Tenancy = Depends(current_tenancy),
    session: AsyncSession = Depends(get_db_session),
) -> DpiaResponse:
    _require_dpo(tenancy)
    fields = payload.model_dump(exclude_unset=True)
    aprobar = bool(fields.pop("aprobar", False))
    if not fields and not aprobar:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Sin campos a actualizar.",
        )
    set_parts: list[str] = []
    params: dict[str, Any] = {"id": str(dpia_id)}
    jsonb_fields = {
        "riesgos_identificados",
        "medidas_mitigacion",
    }
    for key, value in fields.items():
        if key == "rat_id":
            set_parts.append("rat_id = :rat_id")
            params["rat_id"] = (
                str(value) if value is not None else None
            )
        elif key in jsonb_fields:
            set_parts.append(f"{key} = cast(:{key} as jsonb)")
            params[key] = json.dumps(value)
        else:
            set_parts.append(f"{key} = :{key}")
            params[key] = value
    if aprobar:
        # Approval requires a known email of the actor; we read from
        # tenancy and persist the aprobado_at.
        set_parts.append("aprobado_at = now()")
        # Email del DPO no viaja en Tenancy; lo pedimos al front (en
        # update payload) via update; aquí dejamos placeholder y el
        # caller debió haber invocado update con responsable_email
        # distinto si quiere personalizar. Para MVP usamos sub.
        set_parts.append("aprobado_por_dpo_email = :email")
        params["email"] = f"user-{tenancy.user_id}"
        set_parts.append("version = version + 1")

    # set_parts viene de DpiaUpdateRequest (whitelist Pydantic estático);
    # los valores van como bind parameters.
    set_clause = ", ".join(set_parts)
    sql = (
        "update privacy.dpia_records set "  # noqa: S608
        + set_clause
        + " where id = :id returning id, rat_id, nombre_evaluacion, "
          "descripcion_tratamiento, necesidad_proporcionalidad, "
          "riesgos_identificados, medidas_mitigacion, riesgo_residual, "
          "aprobado_por_dpo_email, aprobado_at, version, "
          "created_at, updated_at"
    )
    result = await session.execute(text(sql), params)
    row = result.mappings().first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DPIA no encontrada.",
        )
    await log_audit(
        session,
        workspace_id=tenancy.workspace_id,
        user_id=tenancy.user_id,
        action="approve" if aprobar else "update",
        resource_type="dpia",
        resource_id=dpia_id,
        metadata={
            "fields": sorted(fields.keys()),
            "aprobar": aprobar,
        },
    )
    return _row_to_dpia(dict(row))


# ---------------------------------------------------------------------------
# Export XLSX
# ---------------------------------------------------------------------------


def _xlsx_response(
    payload: bytes, filename: str
) -> StreamingResponse:
    return StreamingResponse(
        iter([payload]),
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )


@router.get("/rat.xlsx")
async def download_rat_xlsx(
    tenancy: Tenancy = Depends(current_tenancy),
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    from src.domain.privacy.compliance_xlsx import render_rat_xlsx

    rats = await list_rat(_tenancy=tenancy, session=session)
    workspace = await session.execute(
        text("select name from core.workspaces where id = :id"),
        {"id": str(tenancy.workspace_id)},
    )
    ws_row = workspace.mappings().first()
    workspace_name = (
        str(ws_row["name"]) if ws_row is not None else "(workspace)"
    )
    payload = render_rat_xlsx(
        records=[r.model_dump() for r in rats.records],
        workspace_name=workspace_name,
        generated_at=datetime.now(),
    )
    await log_audit(
        session,
        workspace_id=tenancy.workspace_id,
        user_id=tenancy.user_id,
        action="download",
        resource_type="rat_xlsx",
        metadata={"records": len(rats.records)},
    )
    return _xlsx_response(payload, "rat-actividades-tratamiento.xlsx")


@router.get("/dpia.xlsx")
async def download_dpia_xlsx(
    tenancy: Tenancy = Depends(current_tenancy),
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    from src.domain.privacy.compliance_xlsx import render_dpia_xlsx

    dpias = await list_dpia(_tenancy=tenancy, session=session)
    workspace = await session.execute(
        text("select name from core.workspaces where id = :id"),
        {"id": str(tenancy.workspace_id)},
    )
    ws_row = workspace.mappings().first()
    workspace_name = (
        str(ws_row["name"]) if ws_row is not None else "(workspace)"
    )
    payload = render_dpia_xlsx(
        records=[r.model_dump() for r in dpias.records],
        workspace_name=workspace_name,
        generated_at=datetime.now(),
    )
    await log_audit(
        session,
        workspace_id=tenancy.workspace_id,
        user_id=tenancy.user_id,
        action="download",
        resource_type="dpia_xlsx",
        metadata={"records": len(dpias.records)},
    )
    return _xlsx_response(payload, "dpia-evaluaciones-impacto.xlsx")
