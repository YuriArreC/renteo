"""Endpoint de papel de trabajo cliente B (skill 9 — closure).

GET /api/empresas/{id}/papel-trabajo.xlsx
    Genera y descarga un XLSX con el resumen, diagnóstico, escenarios
    recientes y trazabilidad SII / alertas. Bajo RLS — sólo empresas
    accesibles para el contador autenticado.

Audit log entry por descarga (acceso a datos tributarios cliente).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.jwt import verify_jwt
from src.auth.tenancy import Tenancy, current_tenancy
from src.db import get_db_session
from src.domain.papeles.builder import build_working_paper
from src.domain.papeles.xlsx import render_working_paper_xlsx
from src.lib.audit import log_audit, mask_rut

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/empresas", tags=["papeles"])


def _safe_filename(razon_social: str, rut: str) -> str:
    """Nombre de archivo seguro para Content-Disposition."""
    base = razon_social.lower()
    base = "".join(ch if ch.isalnum() else "-" for ch in base)
    base = base.strip("-") or "empresa"
    rut_compact = rut.replace(".", "").replace("-", "")
    return f"papel-trabajo-{base[:40]}-{rut_compact}.xlsx"


@router.get("/{empresa_id}/papel-trabajo.xlsx")
async def descargar_papel_trabajo(
    empresa_id: UUID,
    tenancy: Tenancy = Depends(current_tenancy),
    session: AsyncSession = Depends(get_db_session),
    claims: dict = Depends(verify_jwt),  # type: ignore[type-arg]
) -> StreamingResponse:
    workspace_row = await session.execute(
        text(
            "select name from core.workspaces where id = :id"
        ),
        {"id": str(tenancy.workspace_id)},
    )
    ws = workspace_row.mappings().first()
    workspace_name = (
        str(ws["name"]) if ws is not None else "(workspace)"
    )

    email = str(claims.get("email") or "")
    data = await build_working_paper(
        session,
        empresa_id=empresa_id,
        workspace_name=workspace_name,
        generated_at=datetime.now(UTC),
        generated_by_email=email,
    )
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="empresa no encontrada o sin acceso",
        )

    payload = render_working_paper_xlsx(data)

    await log_audit(
        session,
        workspace_id=tenancy.workspace_id,
        user_id=tenancy.user_id,
        action="download",
        resource_type="papel_trabajo",
        resource_id=empresa_id,
        empresa_id=empresa_id,
        metadata={
            "rut_masked": mask_rut(data.empresa.rut),
            "razon_social": data.empresa.razon_social,
            "size_bytes": len(payload),
            "rec_hash": (
                data.recomendacion.rules_snapshot_hash
                if data.recomendacion is not None
                else None
            ),
        },
    )
    logger.info(
        "papel_trabajo_descargado",
        empresa_id=str(empresa_id),
        rut=mask_rut(data.empresa.rut),
        size_bytes=len(payload),
    )

    filename = _safe_filename(data.empresa.razon_social, data.empresa.rut)
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
    }
    return StreamingResponse(
        iter([payload]),
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        headers=headers,
    )
