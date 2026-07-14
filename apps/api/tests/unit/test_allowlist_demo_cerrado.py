"""Allowlist del demo cerrado — `verify_jwt` es el único portón.

Mientras el motor tributario no lo valide el CONTADOR_SOCIO, Renteo corre como
demo cerrado: solo los emails de `ALLOWED_USER_EMAILS` entran. Emitir
recomendaciones a una persona real sobre reglas sin validar expone a Renteo al
art. 100 bis CT como diseñador/planificador (100-250 UTA), y la exención del
art. 14 letra D ampara al contribuyente, no al asesor.

Se testea la función de enforcement directamente (no vía HTTP) porque lo que
importa fijar es la POLÍTICA: quién pasa, quién no, y qué ocurre en los bordes
(sin email, allowlist vacía, mayúsculas, espacios).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import HTTPException

from src.auth.jwt import _enforce_allowlist
from src.config import settings


@pytest.fixture
def allowlist() -> Iterator[None]:
    """Activa la allowlist con dos emails y la restaura al salir."""
    original = settings.allowed_user_emails
    settings.allowed_user_emails = "demo@renteo.cl, Dueno@Renteo.CL"
    try:
        yield
    finally:
        settings.allowed_user_emails = original


def test_allowlist_vacia_no_bloquea_a_nadie() -> None:
    """Default abierto: local y CI corren sin fricción.

    Es deliberado, pero implica que olvidarse de setearla en producción deja la
    app abierta — por eso existe `test_produccion_exige_allowlist`.
    """
    original = settings.allowed_user_emails
    settings.allowed_user_emails = ""
    try:
        assert not settings.allowlist_enabled
        _enforce_allowlist({"email": "cualquiera@internet.cl"})  # no levanta
    finally:
        settings.allowed_user_emails = original


@pytest.mark.usefixtures("allowlist")
def test_email_en_la_lista_pasa() -> None:
    _enforce_allowlist({"email": "demo@renteo.cl"})


@pytest.mark.usefixtures("allowlist")
def test_email_fuera_de_la_lista_recibe_403() -> None:
    with pytest.raises(HTTPException) as exc:
        _enforce_allowlist({"email": "intruso@gmail.com"})
    assert exc.value.status_code == 403


@pytest.mark.usefixtures("allowlist")
@pytest.mark.parametrize(
    "email",
    ["DEMO@RENTEO.CL", "  demo@renteo.cl  ", "dueno@renteo.cl"],
)
def test_la_comparacion_ignora_mayusculas_y_espacios(email: str) -> None:
    """Un email no debe quedar fuera por venir en mayúsculas del proveedor."""
    _enforce_allowlist({"email": email})


@pytest.mark.usefixtures("allowlist")
@pytest.mark.parametrize(
    "claims", [{}, {"email": None}, {"email": ""}, {"email": "   "}]
)
def test_token_sin_email_falla_cerrado(claims: dict[str, object]) -> None:
    """Sin email no hay prueba de pertenencia → se rechaza.

    Falla CERRADA a propósito: un token sin `email` no puede tratarse como si
    estuviera en la lista.
    """
    with pytest.raises(HTTPException) as exc:
        _enforce_allowlist(claims)
    assert exc.value.status_code == 403


def test_produccion_sin_allowlist_no_arranca(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Desplegar a producción sin allowlist debe REVENTAR, no degradar.

    Si `ALLOWED_USER_EMAILS` queda sin setear en prod, cualquiera que se
    registre recibiría recomendaciones tributarias de un motor sin validar. Un
    deploy que no levanta es mejor que una app abierta emitiendo asesoría no
    firmada, así que el guard es un `RuntimeError` al importar `main`.
    """
    from src.main import _assert_demo_cerrado

    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "allowed_user_emails", "")

    with pytest.raises(RuntimeError, match="ALLOWED_USER_EMAILS"):
        _assert_demo_cerrado()


def test_produccion_con_allowlist_arranca(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.main import _assert_demo_cerrado

    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "allowed_user_emails", "demo@renteo.cl")

    _assert_demo_cerrado()  # no levanta


def test_entorno_local_no_exige_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.main import _assert_demo_cerrado

    monkeypatch.setattr(settings, "environment", "local")
    monkeypatch.setattr(settings, "allowed_user_emails", "")

    _assert_demo_cerrado()  # no levanta
