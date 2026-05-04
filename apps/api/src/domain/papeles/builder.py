"""Builder del papel de trabajo cliente B (skill 9 — closure).

Agrega para una empresa: identidad, último diagnóstico de régimen,
hasta 5 escenarios simulados recientes, alertas abiertas y la
última sincronización SII. Toda la consulta corre bajo RLS
(`tenant_session`), de modo que el contador solo ve empresas a las
que tiene acceso.

El DTO `WorkingPaperData` es 100% serializable y se lo consume
tanto el renderer XLSX como, en el futuro, un PDF/HTML preview.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class EmpresaInfo:
    id: UUID
    rut: str
    razon_social: str
    giro: str | None
    regimen_actual: str
    fecha_inicio_actividades: str | None


@dataclass(frozen=True)
class RecomendacionInfo:
    id: UUID
    tax_year: int
    tipo: str
    descripcion: str
    regimen_actual: str | None
    regimen_recomendado: str | None
    ahorro_estimado_clp: Decimal | None
    disclaimer_version: str
    engine_version: str
    rules_snapshot_hash: str
    fundamento_legal: list[dict[str, Any]]
    created_at: datetime


@dataclass(frozen=True)
class EscenarioInfo:
    id: UUID
    nombre: str
    tax_year: int
    regimen: str
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    es_recomendado: bool
    engine_version: str
    rules_snapshot_hash: str
    created_at: datetime


@dataclass(frozen=True)
class AlertaInfo:
    tipo: str
    severidad: str
    titulo: str
    descripcion: str
    accion_recomendada: str | None
    estado: str
    fecha_limite: str | None


@dataclass(frozen=True)
class SiiSyncInfo:
    provider: str
    kind: str
    status: str
    period_from: str | None
    period_to: str | None
    rows_inserted: int
    started_at: datetime
    finished_at: datetime | None


@dataclass(frozen=True)
class WorkingPaperData:
    workspace_name: str
    generated_at: datetime
    generated_by_email: str
    empresa: EmpresaInfo
    recomendacion: RecomendacionInfo | None
    escenarios: list[EscenarioInfo] = field(default_factory=list)
    alertas: list[AlertaInfo] = field(default_factory=list)
    sii_last_sync: SiiSyncInfo | None = None


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


async def _fetch_empresa(
    session: AsyncSession, empresa_id: UUID
) -> EmpresaInfo | None:
    result = await session.execute(
        text(
            """
            select id, rut, razon_social, giro, regimen_actual,
                   fecha_inicio_actividades
              from core.empresas
             where id = :id
               and deleted_at is null
            """
        ),
        {"id": str(empresa_id)},
    )
    row = result.mappings().first()
    if row is None:
        return None
    fecha = row["fecha_inicio_actividades"]
    return EmpresaInfo(
        id=UUID(str(row["id"])),
        rut=str(row["rut"]),
        razon_social=str(row["razon_social"]),
        giro=str(row["giro"]) if row["giro"] is not None else None,
        regimen_actual=str(row["regimen_actual"]),
        fecha_inicio_actividades=(
            fecha.isoformat() if hasattr(fecha, "isoformat") else None
        ),
    )


async def _fetch_recomendacion(
    session: AsyncSession, empresa_id: UUID
) -> RecomendacionInfo | None:
    result = await session.execute(
        text(
            """
            select id, tax_year, tipo, descripcion,
                   ahorro_estimado_clp, disclaimer_version,
                   engine_version, rules_snapshot_hash,
                   fundamento_legal, inputs_snapshot, outputs,
                   created_at
              from core.recomendaciones
             where empresa_id = :emp
             order by created_at desc
             limit 1
            """
        ),
        {"emp": str(empresa_id)},
    )
    row = result.mappings().first()
    if row is None:
        return None
    inputs = row["inputs_snapshot"] or {}
    outputs = row["outputs"] or {}
    veredicto = outputs.get("veredicto") or {}
    return RecomendacionInfo(
        id=UUID(str(row["id"])),
        tax_year=int(row["tax_year"]),
        tipo=str(row["tipo"]),
        descripcion=str(row["descripcion"]),
        regimen_actual=(
            str(veredicto["regimen_actual"])
            if veredicto.get("regimen_actual") is not None
            else inputs.get("regimen_actual")
        ),
        regimen_recomendado=(
            str(veredicto["regimen_recomendado"])
            if veredicto.get("regimen_recomendado") is not None
            else None
        ),
        ahorro_estimado_clp=_decimal_or_none(row["ahorro_estimado_clp"]),
        disclaimer_version=str(row["disclaimer_version"]),
        engine_version=str(row["engine_version"]),
        rules_snapshot_hash=str(row["rules_snapshot_hash"]),
        fundamento_legal=list(row["fundamento_legal"] or []),
        created_at=row["created_at"],
    )


async def _fetch_escenarios(
    session: AsyncSession, empresa_id: UUID, *, limit: int = 5
) -> list[EscenarioInfo]:
    result = await session.execute(
        text(
            """
            select id, nombre, tax_year, regimen, inputs, outputs,
                   es_recomendado, engine_version,
                   rules_snapshot_hash, created_at
              from core.escenarios_simulacion
             where empresa_id = :emp
             order by created_at desc
             limit :limit
            """
        ),
        {"emp": str(empresa_id), "limit": limit},
    )
    items: list[EscenarioInfo] = []
    for row in result.mappings().all():
        items.append(
            EscenarioInfo(
                id=UUID(str(row["id"])),
                nombre=str(row["nombre"]),
                tax_year=int(row["tax_year"]),
                regimen=str(row["regimen"]) if row["regimen"] else "",
                inputs=dict(row["inputs"] or {}),
                outputs=dict(row["outputs"] or {}),
                es_recomendado=bool(row["es_recomendado"]),
                engine_version=str(row["engine_version"]),
                rules_snapshot_hash=str(row["rules_snapshot_hash"]),
                created_at=row["created_at"],
            )
        )
    return items


async def _fetch_alertas_abiertas(
    session: AsyncSession, empresa_id: UUID
) -> list[AlertaInfo]:
    result = await session.execute(
        text(
            """
            select tipo, severidad, titulo, descripcion,
                   accion_recomendada, estado, fecha_limite
              from core.alertas
             where empresa_id = :emp
               and estado in ('nueva', 'vista')
             order by severidad desc, created_at desc
            """
        ),
        {"emp": str(empresa_id)},
    )
    items: list[AlertaInfo] = []
    for row in result.mappings().all():
        fecha = row["fecha_limite"]
        items.append(
            AlertaInfo(
                tipo=str(row["tipo"]),
                severidad=str(row["severidad"]),
                titulo=str(row["titulo"]),
                descripcion=str(row["descripcion"]),
                accion_recomendada=(
                    str(row["accion_recomendada"])
                    if row["accion_recomendada"] is not None
                    else None
                ),
                estado=str(row["estado"]),
                fecha_limite=(
                    fecha.isoformat() if hasattr(fecha, "isoformat") else None
                ),
            )
        )
    return items


async def _fetch_last_sii_sync(
    session: AsyncSession, empresa_id: UUID
) -> SiiSyncInfo | None:
    result = await session.execute(
        text(
            """
            select provider, kind, status, period_from, period_to,
                   rows_inserted, started_at, finished_at
              from tax_data.sii_sync_log
             where empresa_id = :emp
             order by started_at desc
             limit 1
            """
        ),
        {"emp": str(empresa_id)},
    )
    row = result.mappings().first()
    if row is None:
        return None
    return SiiSyncInfo(
        provider=str(row["provider"]),
        kind=str(row["kind"]),
        status=str(row["status"]),
        period_from=(
            str(row["period_from"]) if row["period_from"] else None
        ),
        period_to=str(row["period_to"]) if row["period_to"] else None,
        rows_inserted=int(row["rows_inserted"]),
        started_at=row["started_at"],
        finished_at=row["finished_at"],
    )


async def build_working_paper(
    session: AsyncSession,
    *,
    empresa_id: UUID,
    workspace_name: str,
    generated_at: datetime,
    generated_by_email: str,
) -> WorkingPaperData | None:
    """Construye el paquete de datos del papel de trabajo bajo RLS.
    Devuelve None si la empresa no existe o no es accesible."""
    empresa = await _fetch_empresa(session, empresa_id)
    if empresa is None:
        return None
    return WorkingPaperData(
        workspace_name=workspace_name,
        generated_at=generated_at,
        generated_by_email=generated_by_email,
        empresa=empresa,
        recomendacion=await _fetch_recomendacion(session, empresa_id),
        escenarios=await _fetch_escenarios(session, empresa_id),
        alertas=await _fetch_alertas_abiertas(session, empresa_id),
        sii_last_sync=await _fetch_last_sii_sync(session, empresa_id),
    )
