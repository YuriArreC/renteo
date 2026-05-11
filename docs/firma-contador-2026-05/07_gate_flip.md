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

1. **Quitar banner "preliminar"** del frontend.
   - Archivo: `apps/web/src/components/legal/PlaceholderBanner_Shared.tsx`
   - Setearlo para que retorne `null` o eliminarlo de los layouts.
   - Verificar en `apps/web/messages/es-CL.json` que no queden copy
     residuales "versión preliminar".

2. **Sumar `INTERNAL_ADMIN_EMAILS` reales** en
   `apps/api/src/config.py`:
   ```python
   INTERNAL_ADMIN_EMAILS = [
       "contador-socio@renteo.cl",
       "admin-tecnico@renteo.cl",
   ]
   ```

3. **Tag de release**:
   ```bash
   git tag -a v0.2.0-firma-contador -m "Firma contador socio AT 2024-2026"
   git push origin v0.2.0-firma-contador
   ```
