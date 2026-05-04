"""Custody orquesta KMS + storage + DB para el certificado digital.

Flujo de alta:
  1. El contador sube el PFX (bytes) por POST /api/empresas/{id}/certificado
     con el RUT del titular y la passphrase.
  2. `store_certificate` cifra el PFX con `kms_key_arn` (ENV) y
     sube el blob a `s3://<bucket>/<workspace>/<empresa>/<uuid>.pfx`.
  3. Persiste metadatos en `security.certificados_digitales`. Solo
     `kms_key_arn` y `s3_object_key` quedan en DB.

Flujo de uso (SimpleAPI):
  4. `load_certificate` baja el blob, lo descifra con KMS y devuelve
     los bytes plaintext + metadatos. El llamador descarta los bytes
     al terminar.

Flujo de revocación:
  5. `revoke_certificate` marca `revocado_at`, opcionalmente borra
     el blob en storage y deja la fila en DB para auditoría.

Reglas:
- La passphrase NUNCA se persiste. La descifra el cliente SimpleAPI
  en cada uso a partir de un secreto KMS-cifrado en `secret_arn`
  (track 4b siguiente fase). MVP: passphrase viaja en payload del
  request y se descarta en memoria; en prod debe llegar por
  Secrets Manager.
- Cada uso registra en `security.cert_usage_log`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID, uuid4

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.security.kms import KmsAdapter
from src.domain.security.storage import CertStorageAdapter
from src.lib.errors import CertificateError

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class CertificateMetadata:
    id: UUID
    workspace_id: UUID
    empresa_id: UUID
    rut_titular: str
    nombre_titular: str | None
    valido_desde: date
    valido_hasta: date
    revocado_at: str | None
    kms_key_arn: str
    s3_object_key: str


@dataclass(frozen=True)
class StoredCertificate:
    metadata: CertificateMetadata
    pfx_bytes: bytes


def _object_key(
    workspace_id: UUID, empresa_id: UUID, cert_id: UUID
) -> str:
    return f"{workspace_id}/{empresa_id}/{cert_id}.pfx"


async def store_certificate(
    session: AsyncSession,
    *,
    kms: KmsAdapter,
    storage: CertStorageAdapter,
    workspace_id: UUID,
    empresa_id: UUID,
    rut_titular: str,
    pfx_bytes: bytes,
    valido_desde: date,
    valido_hasta: date,
    kms_key_arn: str,
    nombre_titular: str | None = None,
) -> CertificateMetadata:
    """Cifra + sube + persiste. Idempotente sólo dentro del mismo
    request; reintentos del cliente generan nuevos `cert_id`.

    Si una empresa ya tiene un certificado vigente (sin
    `revocado_at`), lo revoca como parte de la operación: una
    empresa = un cert vigente.
    """
    if not pfx_bytes:
        raise CertificateError("PFX vacío")
    if valido_hasta <= valido_desde:
        raise CertificateError(
            "valido_hasta debe ser posterior a valido_desde"
        )

    # Revocar cert vigente previo (si existe).
    await session.execute(
        text(
            """
            update security.certificados_digitales
               set revocado_at = now()
             where empresa_id = :emp
               and revocado_at is null
            """
        ),
        {"emp": str(empresa_id)},
    )

    cert_id = uuid4()
    s3_key = _object_key(workspace_id, empresa_id, cert_id)
    ciphertext = await kms.encrypt(
        key_arn=kms_key_arn, plaintext=pfx_bytes
    )
    await storage.put(key=s3_key, blob=ciphertext)

    await session.execute(
        text(
            """
            insert into security.certificados_digitales
                (id, workspace_id, empresa_id, rut_titular,
                 kms_key_arn, s3_object_key, nombre_titular,
                 valido_desde, valido_hasta)
            values
                (:id, :ws, :emp, :rut, :arn, :s3, :nombre,
                 :desde, :hasta)
            """
        ),
        {
            "id": str(cert_id),
            "ws": str(workspace_id),
            "emp": str(empresa_id),
            "rut": rut_titular,
            "arn": kms_key_arn,
            "s3": s3_key,
            "nombre": nombre_titular,
            "desde": valido_desde,
            "hasta": valido_hasta,
        },
    )

    logger.info(
        "certificate_stored",
        cert_id=str(cert_id),
        empresa_id=str(empresa_id),
        kms_provider=kms.name,
        storage_provider=storage.name,
        s3_key=s3_key,
    )

    return CertificateMetadata(
        id=cert_id,
        workspace_id=workspace_id,
        empresa_id=empresa_id,
        rut_titular=rut_titular,
        nombre_titular=nombre_titular,
        valido_desde=valido_desde,
        valido_hasta=valido_hasta,
        revocado_at=None,
        kms_key_arn=kms_key_arn,
        s3_object_key=s3_key,
    )


async def load_active_certificate(
    session: AsyncSession,
    *,
    kms: KmsAdapter,
    storage: CertStorageAdapter,
    empresa_id: UUID,
) -> StoredCertificate | None:
    """Descarga + descifra el certificado vigente. Devuelve None si
    no hay cert activo. Los bytes plaintext deben descartarse cuanto
    antes — son secretos."""
    result = await session.execute(
        text(
            """
            select id, workspace_id, empresa_id, rut_titular,
                   nombre_titular, valido_desde, valido_hasta,
                   revocado_at, kms_key_arn, s3_object_key
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
        return None
    ciphertext = await storage.get(key=str(row["s3_object_key"]))
    plaintext = await kms.decrypt(
        key_arn=str(row["kms_key_arn"]), ciphertext=ciphertext
    )
    metadata = CertificateMetadata(
        id=UUID(str(row["id"])),
        workspace_id=UUID(str(row["workspace_id"])),
        empresa_id=UUID(str(row["empresa_id"])),
        rut_titular=str(row["rut_titular"]),
        nombre_titular=(
            str(row["nombre_titular"])
            if row["nombre_titular"] is not None
            else None
        ),
        valido_desde=row["valido_desde"],
        valido_hasta=row["valido_hasta"],
        revocado_at=None,
        kms_key_arn=str(row["kms_key_arn"]),
        s3_object_key=str(row["s3_object_key"]),
    )
    return StoredCertificate(metadata=metadata, pfx_bytes=plaintext)


async def revoke_certificate(
    session: AsyncSession,
    *,
    storage: CertStorageAdapter,
    cert_id: UUID,
    delete_blob: bool = True,
) -> bool:
    """Marca `revocado_at` y opcionalmente borra el blob. Devuelve
    True si se revocó, False si no se encontró cert vigente."""
    result = await session.execute(
        text(
            """
            update security.certificados_digitales
               set revocado_at = now()
             where id = :id
               and revocado_at is null
            returning s3_object_key
            """
        ),
        {"id": str(cert_id)},
    )
    row = result.first()
    if row is None:
        return False
    if delete_blob:
        await storage.delete(key=str(row[0]))
    logger.info(
        "certificate_revoked",
        cert_id=str(cert_id),
        deleted_blob=delete_blob,
    )
    return True
