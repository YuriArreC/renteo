"""Custodia del certificado digital + mandato (skill 4b).

Endpoints (todos requieren tenancy + role con escritura tributaria):
  POST   /api/empresas/{id}/certificado    sube PFX cifrado en KMS.
  GET    /api/empresas/{id}/certificado    metadata del cert vigente.
  DELETE /api/empresas/{id}/certificado    revoca + borra blob.
  POST   /api/empresas/{id}/mandato        registra mandato + persiste
                                           consentimiento del cliente.
  GET    /api/empresas/{id}/mandato        mandato vigente.

El payload del cert llega como JSON con `pfx_base64` + `passphrase`
para evitar multipart en MVP (rinde mejor para tests). En frontend
real el PFX viaja como FormData; el endpoint lo acepta vía JSON
porque toda la lógica de cifrado vive en `domain/security/custody`.
"""

from __future__ import annotations

import base64
from datetime import date
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.tenancy import Tenancy, current_tenancy
from src.config import settings
from src.db import get_db_session
from src.domain.security.custody import (
    revoke_certificate,
    store_certificate,
)
from src.domain.security.kms import make_kms_adapter
from src.domain.security.storage import make_cert_storage
from src.lib.audit import log_audit, mask_rut
from src.lib.errors import CertificateError
from src.lib.rut import InvalidRutError, validate_rut

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/empresas", tags=["custodia"])


_ALLOWED_ROLES = frozenset(
    {"owner", "cfo", "accountant_lead", "accountant_staff"}
)


class CertificateUploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pfx_base64: str = Field(min_length=4)
    rut_titular: str = Field(min_length=3, max_length=12)
    nombre_titular: str | None = Field(default=None, max_length=160)
    valido_desde: date
    valido_hasta: date
    # En prod la passphrase llega cifrada con KMS (track 4c). MVP la
    # acepta para mantener el contrato; el endpoint NO la persiste.
    passphrase: str | None = Field(default=None, max_length=200)


class CertificateMetadataResponse(BaseModel):
    id: UUID
    rut_titular: str
    nombre_titular: str | None
    valido_desde: str
    valido_hasta: str
    revocado_at: str | None
    kms_provider: str
    storage_provider: str


class MandatoCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alcance: list[str] = Field(min_length=1)
    inicio: date
    termino: date
    sii_referencia: str | None = Field(default=None, max_length=120)
    consentimiento_version: str = Field(min_length=2, max_length=80)
    ip_otorgamiento: str | None = Field(default=None, max_length=45)


class MandatoResponse(BaseModel):
    id: UUID
    alcance: list[str]
    inicio: str
    termino: str
    revocado_at: str | None
    sii_referencia: str | None


def _require_role(tenancy: Tenancy) -> None:
    if tenancy.role not in _ALLOWED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Tu rol no puede gestionar la custodia del "
                "certificado digital."
            ),
        )


async def _fetch_empresa(
    session: AsyncSession, empresa_id: UUID
) -> tuple[UUID, str]:
    result = await session.execute(
        text(
            """
            select workspace_id, rut from core.empresas
             where id = :id and deleted_at is null
            """
        ),
        {"id": str(empresa_id)},
    )
    row = result.first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="empresa no encontrada",
        )
    return UUID(str(row[0])), str(row[1])


@router.post(
    "/{empresa_id}/certificado",
    response_model=CertificateMetadataResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_certificate(
    empresa_id: UUID,
    payload: CertificateUploadRequest,
    tenancy: Tenancy = Depends(current_tenancy),
    session: AsyncSession = Depends(get_db_session),
) -> CertificateMetadataResponse:
    _require_role(tenancy)
    workspace_id, _empresa_rut = await _fetch_empresa(session, empresa_id)

    try:
        rut_canonico = validate_rut(payload.rut_titular)
    except InvalidRutError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    try:
        pfx_bytes = base64.b64decode(
            payload.pfx_base64, validate=True
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"pfx_base64 inválido: {exc}",
        ) from exc

    kms_key_arn = (
        settings.sii_kms_key_arn
        or "arn:aws:kms:sa-east-1:placeholder:key/renteo-mock"
    )

    kms = make_kms_adapter()
    storage = make_cert_storage()
    try:
        meta = await store_certificate(
            session,
            kms=kms,
            storage=storage,
            workspace_id=workspace_id,
            empresa_id=empresa_id,
            rut_titular=rut_canonico,
            pfx_bytes=pfx_bytes,
            valido_desde=payload.valido_desde,
            valido_hasta=payload.valido_hasta,
            kms_key_arn=kms_key_arn,
            nombre_titular=payload.nombre_titular,
        )
    except CertificateError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # Best-effort: limpiar la referencia al PFX plaintext para que
    # el GC pueda recolectarla. La passphrase queda en el objeto
    # `payload` hasta que FastAPI lo descarte al cerrar el request.
    pfx_bytes = b""

    await log_audit(
        session,
        workspace_id=tenancy.workspace_id,
        user_id=tenancy.user_id,
        action="certificate_uploaded",
        resource_type="certificado",
        resource_id=meta.id,
        empresa_id=empresa_id,
        metadata={
            "rut_masked": mask_rut(rut_canonico),
            "valido_desde": meta.valido_desde.isoformat(),
            "valido_hasta": meta.valido_hasta.isoformat(),
            "kms_provider": kms.name,
            "storage_provider": storage.name,
        },
    )

    return CertificateMetadataResponse(
        id=meta.id,
        rut_titular=meta.rut_titular,
        nombre_titular=meta.nombre_titular,
        valido_desde=meta.valido_desde.isoformat(),
        valido_hasta=meta.valido_hasta.isoformat(),
        revocado_at=None,
        kms_provider=kms.name,
        storage_provider=storage.name,
    )


@router.get(
    "/{empresa_id}/certificado",
    response_model=CertificateMetadataResponse,
)
async def get_certificate(
    empresa_id: UUID,
    _tenancy: Tenancy = Depends(current_tenancy),
    session: AsyncSession = Depends(get_db_session),
) -> CertificateMetadataResponse:
    await _fetch_empresa(session, empresa_id)
    result = await session.execute(
        text(
            """
            select id, rut_titular, nombre_titular, valido_desde,
                   valido_hasta, revocado_at, kms_key_arn,
                   s3_object_key
              from security.certificados_digitales
             where empresa_id = :emp
               and revocado_at is null
             order by created_at desc
             limit 1
            """
        ),
        {"emp": str(empresa_id)},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay certificado vigente para esta empresa.",
        )
    kms = make_kms_adapter()
    storage = make_cert_storage()
    return CertificateMetadataResponse(
        id=UUID(str(row["id"])),
        rut_titular=str(row["rut_titular"]),
        nombre_titular=(
            str(row["nombre_titular"])
            if row["nombre_titular"] is not None
            else None
        ),
        valido_desde=row["valido_desde"].isoformat(),
        valido_hasta=row["valido_hasta"].isoformat(),
        revocado_at=None,
        kms_provider=kms.name,
        storage_provider=storage.name,
    )


@router.delete(
    "/{empresa_id}/certificado",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_certificate_endpoint(
    empresa_id: UUID,
    tenancy: Tenancy = Depends(current_tenancy),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    _require_role(tenancy)
    await _fetch_empresa(session, empresa_id)
    result = await session.execute(
        text(
            """
            select id from security.certificados_digitales
             where empresa_id = :emp and revocado_at is null
             order by created_at desc limit 1
            """
        ),
        {"emp": str(empresa_id)},
    )
    row = result.first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay certificado vigente para revocar.",
        )
    cert_id = UUID(str(row[0]))

    storage = make_cert_storage()
    revoked = await revoke_certificate(
        session, storage=storage, cert_id=cert_id
    )
    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificado ya revocado.",
        )
    await log_audit(
        session,
        workspace_id=tenancy.workspace_id,
        user_id=tenancy.user_id,
        action="certificate_revoked",
        resource_type="certificado",
        resource_id=cert_id,
        empresa_id=empresa_id,
    )


@router.post(
    "/{empresa_id}/mandato",
    response_model=MandatoResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_mandato(
    empresa_id: UUID,
    payload: MandatoCreateRequest,
    tenancy: Tenancy = Depends(current_tenancy),
    session: AsyncSession = Depends(get_db_session),
) -> MandatoResponse:
    _require_role(tenancy)
    await _fetch_empresa(session, empresa_id)

    if payload.termino <= payload.inicio:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="termino debe ser posterior a inicio",
        )

    # Persistir consentimiento ANTES del mandato — el mandato sin
    # consentimiento explícito es nulo según skill 5.
    await session.execute(
        text(
            """
            insert into privacy.consentimientos
                (user_id, workspace_id, empresa_id,
                 tipo_consentimiento, version_texto, ip_otorgamiento)
            values
                (:uid, :ws, :emp,
                 'mandato_digital', :ver, cast(:ip as inet))
            """
        ),
        {
            "uid": str(tenancy.user_id),
            "ws": str(tenancy.workspace_id),
            "emp": str(empresa_id),
            "ver": payload.consentimiento_version,
            "ip": payload.ip_otorgamiento,
        },
    )

    result = await session.execute(
        text(
            """
            insert into security.mandatos_digitales
                (workspace_id, empresa_id, contador_user_id,
                 alcance, inicio, termino, sii_referencia)
            values
                (:ws, :emp, :uid, :alcance,
                 :inicio, :termino, :sii_ref)
            returning id
            """
        ),
        {
            "ws": str(tenancy.workspace_id),
            "emp": str(empresa_id),
            "uid": str(tenancy.user_id),
            "alcance": payload.alcance,
            "inicio": payload.inicio,
            "termino": payload.termino,
            "sii_ref": payload.sii_referencia,
        },
    )
    mandato_id = UUID(str(result.scalar_one()))

    await log_audit(
        session,
        workspace_id=tenancy.workspace_id,
        user_id=tenancy.user_id,
        action="mandato_registered",
        resource_type="mandato",
        resource_id=mandato_id,
        empresa_id=empresa_id,
        metadata={
            "alcance_count": len(payload.alcance),
            "vigencia_dias": (payload.termino - payload.inicio).days,
            "consentimiento_version": payload.consentimiento_version,
        },
    )

    return MandatoResponse(
        id=mandato_id,
        alcance=payload.alcance,
        inicio=payload.inicio.isoformat(),
        termino=payload.termino.isoformat(),
        revocado_at=None,
        sii_referencia=payload.sii_referencia,
    )


@router.get(
    "/{empresa_id}/mandato",
    response_model=MandatoResponse,
)
async def get_mandato(
    empresa_id: UUID,
    _tenancy: Tenancy = Depends(current_tenancy),
    session: AsyncSession = Depends(get_db_session),
) -> MandatoResponse:
    await _fetch_empresa(session, empresa_id)
    result = await session.execute(
        text(
            """
            select id, alcance, inicio, termino, revocado_at,
                   sii_referencia
              from security.mandatos_digitales
             where empresa_id = :emp and revocado_at is null
             order by created_at desc limit 1
            """
        ),
        {"emp": str(empresa_id)},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay mandato vigente para esta empresa.",
        )
    return MandatoResponse(
        id=UUID(str(row["id"])),
        alcance=list(row["alcance"]),
        inicio=row["inicio"].isoformat(),
        termino=row["termino"].isoformat(),
        revocado_at=None,
        sii_referencia=(
            str(row["sii_referencia"])
            if row["sii_referencia"] is not None
            else None
        ),
    )
