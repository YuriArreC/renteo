"""Storage adapter para el blob cifrado del certificado (skill 4b).

Después de cifrar el PFX con KMS, el ciphertext queda en un object
storage (S3 en producción). Este adapter abstrae la diferencia entre
mock (in-memory dict para CI / dev) y S3 real.

Reglas:
- Solo el `s3_object_key` queda en DB; el blob no.
- En `MockCertStorage` los bytes viven en memoria del proceso —
  para tests; un restart pierde el contenido.
- En `S3CertStorage` el bucket viaja por env (`SII_CERT_BUCKET`).
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import structlog

from src.lib.errors import CertificateError

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any

logger = structlog.get_logger(__name__)


class CertStorageAdapter(ABC):
    name: str

    @abstractmethod
    async def put(self, *, key: str, blob: bytes) -> None: ...

    @abstractmethod
    async def get(self, *, key: str) -> bytes: ...

    @abstractmethod
    async def delete(self, *, key: str) -> None: ...


class MockCertStorage(CertStorageAdapter):
    """Almacena los blobs en un dict de proceso. Solo tests / dev."""

    name = "mock"

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    async def put(self, *, key: str, blob: bytes) -> None:
        self._store[key] = blob

    async def get(self, *, key: str) -> bytes:
        if key not in self._store:
            raise CertificateError(
                f"object {key!r} no existe en el storage mock"
            )
        return self._store[key]

    async def delete(self, *, key: str) -> None:
        self._store.pop(key, None)


class S3CertStorage(CertStorageAdapter):
    """boto3 S3 real. Activa con `CERT_STORAGE_PROVIDER=s3` y
    `SII_CERT_BUCKET` en el entorno. Sin DPA / encryption-at-rest
    server-side configurado, NO encender."""

    name = "s3"

    def __init__(
        self,
        *,
        bucket: str | None = None,
        region: str | None = None,
    ) -> None:
        env_bucket = os.getenv("SII_CERT_BUCKET")
        env_region = os.getenv("AWS_REGION", "sa-east-1")
        chosen_bucket = bucket or env_bucket
        if not chosen_bucket:
            raise CertificateError(
                "SII_CERT_BUCKET no configurado para S3CertStorage."
            )
        self._bucket: str = chosen_bucket
        self._region: str = region or env_region
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                import boto3
            except ImportError as exc:  # pragma: no cover
                raise CertificateError(
                    "boto3 no disponible; instala renteo-api con "
                    "extras [aws]."
                ) from exc
            self._client = boto3.client(
                "s3", region_name=self._region
            )
        return self._client

    async def put(self, *, key: str, blob: bytes) -> None:
        try:
            self._get_client().put_object(
                Bucket=self._bucket,
                Key=key,
                Body=blob,
                # Encryption at-rest server-side (defensa en
                # profundidad sobre el cifrado KMS-envelope ya
                # aplicado al blob).
                ServerSideEncryption="aws:kms",
            )
        except Exception as exc:  # pragma: no cover
            logger.error("s3_put_failed", error=str(exc), key=key)
            raise CertificateError(f"S3 put falló: {exc}") from exc

    async def get(self, *, key: str) -> bytes:
        try:
            response = self._get_client().get_object(
                Bucket=self._bucket, Key=key
            )
            return bytes(response["Body"].read())
        except Exception as exc:  # pragma: no cover
            logger.error("s3_get_failed", error=str(exc), key=key)
            raise CertificateError(f"S3 get falló: {exc}") from exc

    async def delete(self, *, key: str) -> None:
        try:
            self._get_client().delete_object(
                Bucket=self._bucket, Key=key
            )
        except Exception as exc:  # pragma: no cover
            logger.error("s3_delete_failed", error=str(exc), key=key)
            raise CertificateError(f"S3 delete falló: {exc}") from exc


_DEFAULT_PROVIDER = "mock"
_SHARED_MOCK = MockCertStorage()


def make_cert_storage(
    provider: str | None = None,
) -> CertStorageAdapter:
    """Factory: por defecto mock compartido; S3 sólo si
    `CERT_STORAGE_PROVIDER=s3`. El mock es un singleton de proceso
    para que el `put` desde un endpoint y el `get` desde SimpleAPI
    coincidan dentro del mismo CI run."""
    raw = (
        provider
        or os.getenv("CERT_STORAGE_PROVIDER")
        or _DEFAULT_PROVIDER
    )
    chosen = raw.lower()
    if chosen == "mock":
        return _SHARED_MOCK
    if chosen == "s3":
        return S3CertStorage()
    raise CertificateError(
        f"CertStorage provider desconocido: {chosen!r}"
    )
