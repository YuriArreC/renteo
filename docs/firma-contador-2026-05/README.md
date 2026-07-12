# Sprint firma contador socio — 2026-05

**Objetivo del sprint**: salir del estado "todo placeholder" en el
motor tributario. Al merge de este branch, el motor pasa de
ingeniería verde a asesoría firmada.

**Branch**: `firma-contador-socio-2026-05`
**Paquete de entrega al contador**: [`00_PAQUETE_REVISION.md`](./00_PAQUETE_REVISION.md)
(documento autocontenido para el candidato; este README es el
procedimiento técnico que ejecuta ingeniería).
**Checklist firmable**: [`docs/REVISION_CONTADOR_SOCIO.md`](../REVISION_CONTADOR_SOCIO.md)
**Tickets que cierra**: items 1, 2, 3, 4, 9 de
[`TODOS-CONTADOR.md`](../../TODOS-CONTADOR.md). Items 5-8 quedan
abiertos esperando doctrina SII post Ley 21.713.

---

## Qué hay en esta carpeta

Cada archivo `.sql` es un **borrador** con las cifras placeholder
actuales precargadas. El contador socio recorre el archivo de
arriba a abajo:

1. **Si la cifra placeholder coincide con la oficial**: borra el
   comentario `✍️ CONTADOR_SOCIO:` y deja la fila como está.
2. **Si difiere**: cambia el valor + completa `fuente_legal` con
   `'Ley X / Circular SII Y'` real (no `'PLACEHOLDER — ...'`).
3. **Si la cifra todavía no existe** (típicamente AT 2027-2028 sin
   DOF): **deja la fila** tal cual (queda como proyección no
   firmada). El recomendador la necesita para la proyección a 3
   años; borrarla haría que `compute_idpc/igc` levante
   `MissingTaxYearParams`. Se refirma cuando salga el DOF.

Cuando el archivo está completo, se **renombra** al timestamp
correspondiente y se mueve a `supabase/migrations/`:

```bash
mv docs/firma-contador-2026-05/01_tax_year_params.sql \
   supabase/migrations/20260518120000_tax_year_params_firmado.sql
```

Los 5 SQL de parámetros son **UPSERT** (`INSERT … ON CONFLICT DO
UPDATE`) dentro de una `BEGIN/COMMIT`: firman en sitio los años
2024-2026 sin borrar filas. Se usa UPSERT y **no** DELETE+INSERT
porque `tax_year_params` es tabla padre con FK `ON DELETE RESTRICT`
(un DELETE aborta por violación de FK) y porque borrar arrastraría
las filas AT 2027-2028 y las constantes `uf_valor_clp` /
`utm_valor_clp` / `sueldo_empresarial_tope_mensual_uf` que el
simulador y el recomendador cargan en cada request. El 06 depreca
las versiones previas de la whitelist y publica la firmada.

| # | Archivo                              | Tabla / acción                          | Checklist §  |
| - | ------------------------------------ | --------------------------------------- | ------------ |
| 1 | `01_tax_year_params.sql`             | UPSERT `tax_params.tax_year_params`     | §3           |
| 2 | `02_idpc_rates.sql`                  | UPSERT `tax_params.idpc_rates`          | §1           |
| 3 | `03_igc_brackets.sql`                | UPSERT `tax_params.igc_brackets`        | §2           |
| 4 | `04_ppm_pyme_rates.sql`              | UPSERT `tax_params.ppm_pyme_rates`      | §4           |
| 5 | `05_beneficios_topes.sql`            | UPSERT `tax_params.beneficios_topes`    | §6           |
| 6 | `06_whitelist_palancas_v2.sql`       | Depreca v1/v2 + publica **v3** `tax_rules.rule_sets` (`key='global'`, doble firma) | §5  |
| 7 | `07_gate_flip.md`                  | Patch `.github/workflows/ci.yml`        | §9 paso 5    |

---

## Orden recomendado de trabajo (sesión 1 — ~3-4 h con contador)

### Paso 1 — Revisar §1-§6 del checklist en `REVISION_CONTADOR_SOCIO.md`

Antes de tocar SQL: leer cada tabla del checklist y marcar `[x]`
o anotar la cifra correcta en la columna ✍️. Esto da la lista
completa de cambios antes de programar.

### Paso 2 — Editar los 6 SQL de la carpeta

Uno por archivo. **No** convertirlos en migración todavía
(siguen en `docs/firma-contador-2026-05/`).

Tiempo estimado por archivo:
- `01_tax_year_params.sql` — 20 min (UTM/UTA/UF AT 2024-2026; AT
  2027-2028 se dejan como proyección, no se borran).
- `02_idpc_rates.sql` — 15 min (5 filas × 3 regímenes; verificar
  rampa transitoria 12,5% vs 25% reversión).
- `03_igc_brackets.sql` — 20 min (8 tramos × 3 AT; confirmar si
  cambia entre AT 2024-2026).
- `04_ppm_pyme_rates.sql` — 10 min (2 regímenes × 3 AT).
- `05_beneficios_topes.sql` — 30 min (15+ topes; `sueldo_empresarial_tope_mensual_uf`
  (ítem #14), `uf_valor_clp` y `utm_valor_clp` **no** se firman acá:
  se conservan intactas para no tumbar el simulador).
- `06_whitelist_palancas_v2.sql` — 45 min (12 palancas + 3 items
  complementarios; se depreca v1/v2 y se publica **v3** bajo
  `key='global'` con shape `{"items": […]}`, `fuente_legal` JSON y
  doble firma).

### Paso 3 — Renombrar a migraciones y aplicar local

```bash
ts=$(date -u +%Y%m%d%H%M%S)
for f in docs/firma-contador-2026-05/0*.sql; do
  base=$(basename "$f" .sql)
  mv "$f" "supabase/migrations/${ts}_${base}_firmado.sql"
  ts=$((ts + 1))
done
supabase stop --workdir .
supabase start --workdir .   # aplica las 6 migraciones nuevas
```

### Paso 4 — Correr golden + integration local

```bash
cd apps/api
pytest tests/golden -v
pytest tests/integration -v -k "rules"
```

Los goldens deben pasar (todavía con `strict=False`). Si alguno
**falla**, hay drift entre cifras firmadas y el `expected_pesos`
hardcoded en el test — actualizar el test con el nuevo expected y
agregar comentario `# Firmado por <nombre> el YYYY-MM-DD`.

### Paso 5 — Aplicar el gate flip

Seguir las instrucciones de [`07_gate_flip.md`](./07_gate_flip.md):
agregar `RENTEO_GOLDENS_FIRMADOS: "1"` al `env:` del job
`test-api-integration` en `.github/workflows/ci.yml` (1 línea).

Los `@pytest.mark.xfail(strict=GOLDENS_STRICT)` pasan a strict=True;
desde acá un golden que falle = merge bloqueado.

### Paso 6 — Marcar checklist y commit final

1. En `docs/REVISION_CONTADOR_SOCIO.md` marcar `[x]` cada fila
   firmada. Las que quedaron sin firmar (típicamente §8 items 5-8
   por Ley 21.713) se mantienen en `[ ]` para tracking.
2. Agregar entrada en `CHANGELOG.md`:
   ```
   ## [0.2.0] — 2026-05-XX

   ### Changed
   - Tax params AT 2024-2026 firmados por <nombre contador socio>.
   - Whitelist v3 de palancas P1-P12 publicada con doble firma
     (key=global); v1/v2 depreciadas.
   - Gate `RENTEO_GOLDENS_FIRMADOS=1` activo: goldens en strict mode.
   ```
3. Tag en git: `v0.2.0-firma-contador`.

### Paso 7 — PR a main

Dos reviewers requeridos:
- `contador-socio@renteo.cl` (1ra firma, debe ser igual a los
  UUIDs `published_by_contador` usados en `06_whitelist_palancas_v2.sql`).
- `admin-tecnico@renteo.cl` (2da firma, debe ser distinto, igual a
  `published_by_admin`).

CI debe pasar verde con `RENTEO_GOLDENS_FIRMADOS=1` activo. Si no
pasa, hay un test golden que no encaja con las cifras firmadas —
arreglar el test, no quitar el gate.

---

## Qué NO está en este sprint

Por diseño, este sprint **no** intenta cerrar:

- **Items 5-8 de TODOS-CONTADOR** (agregados art. 33 N°1, pérdidas
  tributarias, columnas SAC/RAI/REX/DDAN, formato `imputacion` de
  retiros). Dependen de doctrina SII post Ley 21.713 que aún no
  está publicada. El watchdog legislativo abrirá tickets cuando
  salgan; cada uno = nueva versión de regla.
- **Items 21-30** (DPO formal, DPAs encargados, política privacidad
  v2, pentest OWASP). Sprint paralelo del abogado tributario,
  branch separado.
- **AT 2027-2028 UTM/UTA/UF** si DOF no publicó al cierre del año
  comercial respectivo. Se publican como nueva versión cuando
  salgan, no se inventan acá.

---

## UUIDs para doble firma

Para que el constraint `rule_sets_double_sig_check` valide en
`06_whitelist_palancas_v2.sql`, hay que tener creados ambos
usuarios en `auth.users` antes de aplicar la migración:

```sql
-- en local (supabase studio) o via auth-admin API en prod:
-- 1. contador-socio@renteo.cl (rol CONTADOR_SOCIO)
-- 2. admin-tecnico@renteo.cl  (rol INTERNAL_ADMIN)
-- ambos emails en la env var INTERNAL_ADMIN_EMAILS (mapea al campo
-- settings.internal_admin_emails), no un literal en config.py.
-- Ver 07_gate_flip.md §"Después del flip" paso 2.
```

Una vez creados, anotar sus UUIDs y reemplazar
`<UUID_CONTADOR_SOCIO>` y `<UUID_ADMIN_TECNICO>` en
`06_whitelist_palancas_v2.sql`.
