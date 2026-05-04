"""Unit tests para MockSiiClient (track skill 4).

El mock debe ser determinístico: dos llamadas con el mismo (rut,
period) producen el mismo set de líneas. Esto permite que tests
integration y golden cases sean estables sin depender de un
proveedor real.
"""

from __future__ import annotations

import pytest

from src.domain.sii.factory import make_sii_client
from src.domain.sii.mock_client import MockSiiClient
from src.lib.errors import SiiUnavailable


@pytest.mark.asyncio
async def test_mock_rcv_is_deterministic() -> None:
    client = MockSiiClient()
    a = await client.fetch_rcv(rut="11111111-1", period="2026-03")
    b = await client.fetch_rcv(rut="11111111-1", period="2026-03")
    assert len(a) == len(b)
    assert all(
        la.folio == lb.folio for la, lb in zip(a, b, strict=True)
    )


@pytest.mark.asyncio
async def test_mock_rcv_changes_with_period() -> None:
    client = MockSiiClient()
    a = await client.fetch_rcv(rut="11111111-1", period="2026-03")
    b = await client.fetch_rcv(rut="11111111-1", period="2026-04")
    assert {line.folio for line in a} != {line.folio for line in b}


@pytest.mark.asyncio
async def test_mock_f22_returns_one_of_known_regimes() -> None:
    client = MockSiiClient()
    f22 = await client.fetch_f22(rut="11111111-1", tax_year=2026)
    assert f22 is not None
    assert f22.regimen_declarado in ("14_a", "14_d_3", "14_d_8")


def test_factory_unknown_provider_raises() -> None:
    with pytest.raises(SiiUnavailable):
        make_sii_client("nonexistent")


def test_factory_baseapi_unimplemented_raises() -> None:
    with pytest.raises(SiiUnavailable):
        make_sii_client("baseapi")


def test_factory_mock_returns_mock_client() -> None:
    client = make_sii_client("mock")
    assert client.name == "mock"
    assert isinstance(client, MockSiiClient)
