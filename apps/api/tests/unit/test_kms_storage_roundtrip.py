"""Unit tests del adapter KMS y storage (skill 4b).

No requieren DB. Validan que:
- El cifrado mock es determinístico y simétrico (encrypt/decrypt
  con la misma key recupera el plaintext).
- Cambiar el `key_arn` invalida el descifrado (igual que KMS real).
- El storage mock soporta put/get/delete y devuelve error si la
  clave no existe.
"""

from __future__ import annotations

import pytest

from src.domain.security.kms import MockKmsAdapter, make_kms_adapter
from src.domain.security.storage import (
    MockCertStorage,
    make_cert_storage,
)
from src.lib.errors import CertificateError

_KEY_A = "arn:aws:kms:sa-east-1:000000000000:key/key-a"
_KEY_B = "arn:aws:kms:sa-east-1:000000000000:key/key-b"


@pytest.mark.asyncio
async def test_kms_mock_roundtrip_recovers_plaintext() -> None:
    kms = MockKmsAdapter()
    plaintext = b"PFX bytes faux"
    ciphertext = await kms.encrypt(key_arn=_KEY_A, plaintext=plaintext)
    assert ciphertext != plaintext
    recovered = await kms.decrypt(key_arn=_KEY_A, ciphertext=ciphertext)
    assert recovered == plaintext


@pytest.mark.asyncio
async def test_kms_mock_decrypt_with_wrong_key_breaks() -> None:
    kms = MockKmsAdapter()
    ciphertext = await kms.encrypt(
        key_arn=_KEY_A, plaintext=b"secret"
    )
    recovered = await kms.decrypt(
        key_arn=_KEY_B, ciphertext=ciphertext
    )
    assert recovered != b"secret"


@pytest.mark.asyncio
async def test_kms_empty_arn_raises() -> None:
    kms = MockKmsAdapter()
    with pytest.raises(CertificateError):
        await kms.encrypt(key_arn="", plaintext=b"x")
    with pytest.raises(CertificateError):
        await kms.decrypt(key_arn="", ciphertext=b"x")


def test_kms_factory_default_mock() -> None:
    assert make_kms_adapter().name == "mock"


def test_kms_factory_unknown_provider_raises() -> None:
    with pytest.raises(CertificateError):
        make_kms_adapter(provider="invalid")


@pytest.mark.asyncio
async def test_storage_mock_put_get_delete() -> None:
    storage = MockCertStorage()
    await storage.put(key="foo", blob=b"abc")
    assert await storage.get(key="foo") == b"abc"
    await storage.delete(key="foo")
    with pytest.raises(CertificateError):
        await storage.get(key="foo")


def test_storage_factory_default_mock() -> None:
    assert make_cert_storage().name == "mock"


def test_storage_factory_unknown_provider_raises() -> None:
    with pytest.raises(CertificateError):
        make_cert_storage(provider="invalid")
