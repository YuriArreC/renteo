"""KMS adapter para envelope encryption (skill 4b).

Custodia del certificado digital: el PFX viaja cifrado a S3 con
una data key que a su vez está protegida por KMS. El backend solo
descifra la data key + el blob justo antes de invocar SII y
descarta ambos al volver — nunca persiste plaintext.

Reglas no negociables:
- El PFX y la passphrase NUNCA en DB / logs / env.
- Solo el `kms_key_arn` queda en `security.certificados_digitales`.
- El blob cifrado vive en S3 (`s3_object_key`).
- En CI / dev usamos MockKmsAdapter (in-memory determinístico).
"""

from __future__ import annotations

import hashlib
import hmac
import os
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import structlog

from src.lib.errors import CertificateError

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any

logger = structlog.get_logger(__name__)


class KmsAdapter(ABC):
    """Contrato común a mock + AWS KMS."""

    name: str

    @abstractmethod
    async def encrypt(
        self, *, key_arn: str, plaintext: bytes
    ) -> bytes:
        """Cifra `plaintext` con la KMS key indicada."""

    @abstractmethod
    async def decrypt(
        self, *, key_arn: str, ciphertext: bytes
    ) -> bytes:
        """Descifra `ciphertext` con la misma KMS key."""


class MockKmsAdapter(KmsAdapter):
    """Mock determinístico — XOR con HMAC(key_arn) como "cifrado".

    No es seguro criptográficamente y NO debe usarse en producción.
    Sirve para CI / dev: el roundtrip funciona, el ciphertext es
    distinto del plaintext y depende del key_arn (cambiar el ARN
    invalida el descifrado, igual que KMS real)."""

    name = "mock"

    @staticmethod
    def _stream(key_arn: str, length: int) -> bytes:
        """HMAC-SHA256 expandido al largo necesario."""
        secret = b"renteo-mock-kms-secret"
        out = bytearray()
        counter = 0
        while len(out) < length:
            block = hmac.new(
                secret,
                f"{key_arn}|{counter}".encode(),
                hashlib.sha256,
            ).digest()
            out.extend(block)
            counter += 1
        return bytes(out[:length])

    async def encrypt(
        self, *, key_arn: str, plaintext: bytes
    ) -> bytes:
        if not key_arn:
            raise CertificateError("kms_key_arn vacío")
        stream = self._stream(key_arn, len(plaintext))
        return bytes(a ^ b for a, b in zip(plaintext, stream, strict=True))

    async def decrypt(
        self, *, key_arn: str, ciphertext: bytes
    ) -> bytes:
        if not key_arn:
            raise CertificateError("kms_key_arn vacío")
        # XOR es simétrico: encrypt = decrypt con el mismo stream.
        return await self.encrypt(
            key_arn=key_arn, plaintext=ciphertext
        )


class AwsKmsAdapter(KmsAdapter):
    """boto3 KMS real. Requiere AWS_REGION y credenciales válidas
    en el entorno (IAM role en Render, profile local en dev). NO
    activar sin DPA + key policy revisada por el equipo de seguridad.

    Se carga perezosamente para no exigir boto3 ni credenciales en
    CI / unit tests; track 4b deja el scaffolding listo para el flip
    del feature flag `kms_provider=aws`.
    """

    name = "aws"

    def __init__(self, *, region: str | None = None) -> None:
        self._region = region or os.getenv("AWS_REGION", "sa-east-1")
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
                "kms", region_name=self._region
            )
        return self._client

    async def encrypt(
        self, *, key_arn: str, plaintext: bytes
    ) -> bytes:
        # KMS encrypt es síncrono en boto3; lo dejamos sync dentro de
        # la corutina porque el llamado es corto. Si necesitamos no
        # bloquear el loop, env. envolver en run_in_executor.
        try:
            response = self._get_client().encrypt(
                KeyId=key_arn,
                Plaintext=plaintext,
            )
        except Exception as exc:  # pragma: no cover — gated en prod
            logger.error("kms_encrypt_failed", error=str(exc))
            raise CertificateError(f"KMS encrypt falló: {exc}") from exc
        return bytes(response["CiphertextBlob"])

    async def decrypt(
        self, *, key_arn: str, ciphertext: bytes
    ) -> bytes:
        try:
            response = self._get_client().decrypt(
                KeyId=key_arn,
                CiphertextBlob=ciphertext,
            )
        except Exception as exc:  # pragma: no cover
            logger.error("kms_decrypt_failed", error=str(exc))
            raise CertificateError(f"KMS decrypt falló: {exc}") from exc
        return bytes(response["Plaintext"])


_DEFAULT_PROVIDER = "mock"


def make_kms_adapter(provider: str | None = None) -> KmsAdapter:
    """Factory: por defecto mock; AWS sólo si KMS_PROVIDER=aws."""
    raw = provider or os.getenv("KMS_PROVIDER") or _DEFAULT_PROVIDER
    chosen = raw.lower()
    if chosen == "mock":
        return MockKmsAdapter()
    if chosen == "aws":
        return AwsKmsAdapter()
    raise CertificateError(f"KMS provider desconocido: {chosen!r}")
