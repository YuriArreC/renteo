# 07 — Gate flip: activar `RENTEO_GOLDENS_FIRMADOS=1`

**Cuándo aplicar**: después de mergear las 6 migraciones firmadas
(pasos 01-06) y confirmar que `pytest tests/golden` corre verde local.

**Qué hace**: prende el gate definido en
`apps/api/tests/golden/__init__.py`:

```python
GOLDENS_STRICT: bool = os.getenv("RENTEO_GOLDENS_FIRMADOS") == "1"
```

Todos los `@pytest.mark.xfail(strict=GOLDENS_STRICT)` pasan a
`strict=True`. Desde acá:

- Un golden que **falla** → CI rojo, merge bloqueado.
- Un golden que **pasa inesperadamente** (XPASS) → CI rojo, merge bloqueado.

O sea: el motor queda blindado contra drift de cifras tributarias.

---

## Cambio exacto

**Archivo**: `.github/workflows/ci.yml`
**Job**: `test-api-integration` → step `Run integration + RLS + golden`

Agregar `RENTEO_GOLDENS_FIRMADOS: "1"` debajo de `DATABASE_URL` en el
bloque `env:`. Queda así:

```yaml
      - name: Run integration + RLS + golden + unit tests (cobertura combinada)
        working-directory: apps/api
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:postgres@127.0.0.1:54322/postgres
          # 🔒 Gate firma contador socio: cuando =1, los goldens
          # marcados @pytest.mark.xfail(strict=GOLDENS_STRICT) pasan a
          # strict=True. Un golden que falle o que pase inesperado
          # bloquea el merge.
          RENTEO_GOLDENS_FIRMADOS: "1"
        run: |
          pytest tests/unit tests/integration tests/golden -v \
            --cov=src/domain/tax_engine \
            --cov-report=term \
            --cov-fail-under=85
```

---

## Validación post-flip (correr local antes de pushear)

```bash
cd apps/api
RENTEO_GOLDENS_FIRMADOS=1 pytest tests/golden -v
```

Posibles resultados:

| Resultado pytest                                  | Significa                                                  | Qué hacer                                              |
| ------------------------------------------------- | ---------------------------------------------------------- | ------------------------------------------------------ |
| Todos passed                                       | Cifras firmadas coinciden con `expected_pesos` del test    | Commitear y abrir PR.                                  |
| `XPASS` (= pasa pero estaba marcado xfail strict) | El test ya pasaba con placeholders; tras firma sigue OK    | Quitar `@pytest.mark.xfail` del test. Es lo deseado.   |
| `FAILED` con assertion en expected_pesos          | La cifra firmada cambió el resultado vs el test            | Actualizar `expected_pesos` con cifra firmada + comment `# Firmado por <nombre> <fecha>`. |
| `FAILED` con `MissingTaxYearParams` o similar     | Falta una fila en `tax_params.*` que el test necesita      | Volver al paso 01-04, revisar que la migración la incluya. |

---

## Después del flip

Una vez que el PR esté en `main` con CI verde:

1. **Banner "Versión preliminar" del frontend** — NO se toca en este
   sprint.
   - No existe `apps/web/src/components/legal/PlaceholderBanner_Shared.tsx`.
     El copy es la clave `legal.placeholderBanner` en
     `apps/web/messages/es-CL.json`, renderizada inline en un `<div>`
     dentro de `apps/web/src/app/legal/terminos/page.tsx` y
     `apps/web/src/app/legal/privacidad/page.tsx`.
   - Ese texto dice "pendiente de revisión y firma por **estudio
     jurídico**": está atado a la firma del ESTUDIO_JURIDICO (sprint
     legal aparte, ver "Qué NO está en este sprint" del README), no a
     la firma tributaria del contador socio. Se quita cuando el
     abogado firme los textos legales, **no en este gate-flip**.
   - (No hay un banner separado de "datos tributarios sandbox" en la
     web que corresponda remover acá.)

2. **Emails de admin interno reales** — setear la **variable de
   entorno** `INTERNAL_ADMIN_EMAILS` en el entorno de deploy
   (preview/staging/prod). **No** agregar un literal en `config.py`.
   - El motor lee el campo Pydantic `settings.internal_admin_emails`
     (lista separada por comas) vía la propiedad
     `internal_admin_emails_set` (`apps/api/src/config.py`), que
     consume `require_internal_admin`
     (`apps/api/src/auth/internal_admin.py:48`). Un
     `INTERNAL_ADMIN_EMAILS = [...]` a nivel de módulo en `config.py`
     **no tiene efecto**: el código nunca lo lee.
   - Valor a setear (reemplaza el default placeholder
     `contador-socio@renteo.local,admin-tecnico@renteo.local`; si no
     se reemplaza, esos usuarios `.local` conservan acceso admin):
     ```
     INTERNAL_ADMIN_EMAILS=contador-socio@renteo.cl,admin-tecnico@renteo.cl
     ```
   - Requisito: esos emails deben existir como usuarios en
     `auth.users` (el check compara el email del JWT contra la lista).

3. **Tag de release**:
   ```bash
   git tag -a v0.2.0-firma-contador -m "Firma contador socio AT 2024-2026"
   git push origin v0.2.0-firma-contador
   ```
