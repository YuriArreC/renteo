# Revisión por contador socio — checklist firmable

**Objetivo**: convertir las cifras placeholder del motor en cifras
firmadas. Sin esta revisión, los goldens viven en `xfail` y el motor
no puede usarse para asesoría real, aunque la ingeniería esté completa.

**Resultado esperado**: un PR único que (a) corrija parámetros donde
haga falta, (b) flippe `RENTEO_GOLDENS_FIRMADOS=1` en CI, (c) cambie
`strict=False → strict=True` en los `@pytest.mark.xfail` de
`tests/golden/`. Con ese merge el repo sale del estado "todo
placeholder" y queda listo para vender.

**Convención**: cada fila tiene una columna ✍️ con un casillero
vacío `[ ]`. Marcar `[x]` cuando la cifra coincide con la
oficial, o reemplazar con la cifra firmada en el PR cuando difiera.

---

## 1 · Tabla IDPC — `tax_params.idpc_rates`

Migración: `supabase/migrations/20260502120000_tax_params_placeholder_seeds.sql`.

| ✍️  | AT   | Régimen      | Tasa placeholder | Fuente que aplica                       | Comentario                                       |
| --- | ---- | ------------ | ---------------- | --------------------------------------- | ------------------------------------------------ |
| [ ] | 2024 | 14 A         | 27%              | art. 14 A LIR; Ley 21.210               | Tasa permanente régimen general                 |
| [ ] | 2025 | 14 A         | 27%              | idem                                    |                                                  |
| [ ] | 2026 | 14 A         | 27%              | idem                                    |                                                  |
| [ ] | 2024 | 14 D N°3     | 12,5%            | Ley 21.755; Circular SII 53/2025        | Tasa transitoria condicional Ley 21.735         |
| [ ] | 2025 | 14 D N°3     | 12,5%            | idem                                    | Verificar continuidad transitoria               |
| [ ] | 2026 | 14 D N°3     | 12,5%            | idem                                    | Verificar continuidad transitoria               |
| [ ] | 2024 | 14 D N°3 rev | 25%              | art. 14 D N°3 LIR; Ley 21.735 art. 4° t | Tasa permanente si rompe condicionalidad        |
| [ ] | 2024 | 14 D N°8     | 0%               | art. 14 D N°8 LIR                       | Transparente: IDPC = 0; dueños tributan IGC      |

Test golden: `tests/golden/test_idpc_golden.py` — 4 casos firmables.

---

## 2 · Tramos IGC — `tax_params.igc_brackets`

8 tramos en UTA con `desde_uta`, `hasta_uta`, `tasa`, `rebajar_uta`.

| ✍️  | AT 2026 tramo | desde UTA | hasta UTA | tasa  | rebajar UTA | ✍️ correcto |
| --- | ------------- | --------- | --------- | ----- | ----------- | ----------- |
| [ ] | 1             | 0         | 13.5      | 0%    | 0           |             |
| [ ] | 2             | 13.5      | 30        | 4%    | 0.54        |             |
| [ ] | 3             | 30        | 50        | 8%    | 1.74        |             |
| [ ] | 4             | 50        | 70        | 13.5% | 4.49        |             |
| [ ] | 5             | 70        | 90        | 23%   | 11.14       |             |
| [ ] | 6             | 90        | 120       | 30.4% | 17.80       |             |
| [ ] | 7             | 120       | 310       | 35%   | 23.32       |             |
| [ ] | 8             | 310       | NULL      | 40%   | 38.82       |             |

**Crédito 5% último tramo (art. 56 LIR)**: aplicar como deducción
contra el IGC determinado del dueño, NO dentro de `compute_igc`.

Test golden: `tests/golden/test_igc_golden.py` — 3 casos firmables
(tramo exento, tramo 3, tramo 8).

✍️ Confirmar que la tabla aplica idéntica para AT 2024-2028 (revisar
si hay cambios entre años).

---

## 3 · UTA / UTM / UF dic — `tax_params.tax_year_params`

| ✍️  | AT   | UTM dic placeholder | UTA dic placeholder | UF dic placeholder | Fuente DOF |
| --- | ---- | ------------------- | ------------------- | ------------------ | ---------- |
| [ ] | 2024 | $67.000             | $804.000            | $38.000            |            |
| [ ] | 2025 | $68.000             | $816.000            | $38.000            |            |
| [ ] | 2026 | $69.542             | $834.504            | $38.000            |            |
| [ ] | 2027 | $71.000             | $852.000            | $38.000            |            |
| [ ] | 2028 | $73.000             | $876.000            | $38.000            |            |

Las cifras correctas se publican en DOF y SII; reemplazar con valores
firmados al cierre de cada año comercial.

---

## 4 · PPM PyME — `tax_params.ppm_pyme_rates`

| ✍️  | AT   | Régimen  | umbral UF | tasa baja (≤ umbral) | tasa alta (> umbral) | Fuente               |
| --- | ---- | -------- | --------- | -------------------- | -------------------- | -------------------- |
| [ ] | 2026 | 14 D N°3 | 50.000    | 0,125%               | 0,25%                | Ley 21.755; Circ SII |
| [ ] | 2026 | 14 D N°8 | 50.000    | 0,2%                 | 0,2%                 | art. 14 D N°8 LIR    |

Test golden: `tests/golden/test_ppm_golden.py` — 2 casos firmables.

---

## 5 · Lista blanca de palancas — `tax_rules.recomendacion_whitelist v2`

Migración: `20260514120000_track_palancas_p7_p12.sql`. Las 12 palancas
del simulador (skill 8) deben estar firmadas individualmente. Una
palanca firmada implica: el contador acepta que recomendarla está
dentro de la economía de opción (lícito) y NO constituye elusión.

| ✍️  | id                       | Palanca                                       | Fundamento                              | Régimen elegible                |
| --- | ------------------------ | --------------------------------------------- | --------------------------------------- | ------------------------------- |
| [ ] | dep_instantanea          | P1 — Depreciación instantánea                 | art. 31 N°5 bis LIR; Oficio SII 715/2025 | 14 D N°3, 14 D N°8              |
| [ ] | sence                    | P2 — Franquicia SENCE                         | Ley 19.518                              | Todos                           |
| [ ] | rebaja_14e               | P3 — Rebaja RLI por reinversión                | art. 14 E LIR                           | Solo 14 D N°3                   |
| [ ] | retiros_adicionales      | P4 — Retiros adicionales del dueño             | arts. 14 A, 14 D LIR; Circ SII 73/2020  | Todos                           |
| [ ] | sueldo_empresarial       | P5 — Sueldo empresarial al socio activo        | art. 31 N°6 inc. 3° LIR                 | Todos                           |
| [ ] | credito_id               | P6 — Crédito I+D + gasto 65%                   | Ley 20.241; Ley 21.755                  | Todos                           |
| [ ] | ppm_extraordinario       | P7 — PPM extraordinario                       | art. 84 LIR                             | Todos                           |
| [ ] | postergacion_iva         | P8 — Postergación IVA Pro PyME                 | Ley 21.210; art. 64 N°9 CT              | Solo 14 D                       |
| [ ] | apv                      | P9 — APV régimen A o B                         | art. 42 bis LIR; DL 3.500               | Todos                           |
| [ ] | credito_reinversion      | P10 — Crédito por inversión activo fijo        | art. 33 bis LIR                         | 14 A, 14 D N°3 (no 14 D N°8)    |
| [ ] | depreciacion_acelerada   | P11 — Depreciación acelerada                   | art. 31 N°5 LIR                         | Todos                           |
| [ ] | cambio_regimen           | P12 — Cambio de régimen tributario             | arts. 14 A, 14 D LIR                    | Todos                           |

**Lista blanca extra** (no son palancas pero la whitelist las
incluye para recomendaciones):

| ✍️  | id                       | Item                                       | Fundamento                                |
| --- | ------------------------ | ------------------------------------------ | ----------------------------------------- |
| [ ] | donaciones               | Donaciones con beneficio tributario         | Ley Valdés y leyes complementarias        |
| [ ] | credito_ipe              | Crédito Impuesto Pagado Extranjero          | arts. 41 A y 41 C LIR                     |
| [ ] | timing_facturacion       | Timing de facturación dentro del período    | Ley IVA arts. 9 y 55                      |

---

## 6 · Topes paramétricos — `tax_params.beneficios_topes`

Migraciones: `20260505120000_track_11b_simulator_topes.sql` +
`20260508120000_track_8b_palancas_topes.sql` +
`20260514120000_track_palancas_p7_p12.sql`.

| ✍️  | key                              | AT 2026 placeholder | Unidad     | Fuente                        |
| --- | -------------------------------- | ------------------- | ---------- | ----------------------------- |
| [ ] | rebaja_14e_porcentaje            | 50%                 | porcentaje | art. 14 E LIR                 |
| [ ] | rebaja_14e_uf                    | 5.000               | UF         | art. 14 E LIR                 |
| [ ] | sueldo_empresarial_tope_mensual_uf | 60                | UF         | TODO(contador) ítem #14       |
| [ ] | credito_id_porcentaje_credito    | 35%                 | porcentaje | Ley 20.241                    |
| [ ] | credito_id_porcentaje_gasto      | 65%                 | porcentaje | Ley 20.241                    |
| [ ] | credito_id_tope_utm              | 15.000              | UTM        | Ley 20.241                    |
| [ ] | sence_porcentaje_planilla        | 1%                  | porcentaje | Ley 19.518                    |
| [ ] | sence_tope_minimo_utm            | 9                   | UTM        | Ley 19.518                    |
| [ ] | apv_tope_anual_uf                | 600                 | UF         | art. 42 bis LIR               |
| [ ] | ppm_extraordinario_max_factor    | 2,0                 | factor     | art. 84 LIR                   |
| [ ] | iva_postergacion_dias            | 60                  | días       | art. 64 N°9 CT                |
| [ ] | credito_reinversion_porcentaje   | 6%                  | porcentaje | art. 33 bis LIR               |
| [ ] | credito_reinversion_tope_utm     | 500                 | UTM        | art. 33 bis LIR               |
| [ ] | depreciacion_acelerada_factor    | 3                   | factor     | art. 31 N°5 LIR               |

---

## 7 · Banderas rojas (red flags) — `domain/tax_engine` + `_apply_palancas`

Estas validaciones bloquean o advierten al usuario antes de aplicar
una palanca. Confirmar interpretación.

| ✍️  | Bandera                                            | Implementada en                          |
| --- | -------------------------------------------------- | ---------------------------------------- |
| [ ] | P1 dep instantánea NO en 14 A                      | `_validate_eligibility` scenario.py     |
| [ ] | P3 rebaja 14 E SOLO en 14 D N°3                    | `_validate_eligibility` scenario.py     |
| [ ] | P5 sueldo empresarial > tope mensual razonable     | `_apply_palancas` warning bandera        |
| [ ] | P6 crédito I+D excede tope 15.000 UTM              | scenario.py warning                      |
| [ ] | P7 PPM extraordinario > 2× tasa habitual           | scenario.py warning                      |
| [ ] | P8 postergación IVA en 14 A                        | `_validate_eligibility` 422              |
| [ ] | P9 APV anual excede 600 UF                         | scenario.py warning                      |
| [ ] | P10 crédito reinversión en 14 D N°8 transparente   | `_validate_eligibility` 422              |
| [ ] | P12 régimen objetivo igual al actual               | `_validate_eligibility` 422              |
| [ ] | Capacidad real: retiros + sueldo > 1,5× RLI base   | scenario.py warning global               |
| [ ] | Reorganización societaria con motivo principal trib. | TODO ítem #16 — interacciones P1×P3    |

---

## 8 · Interpretaciones SII pendientes (TODOS-CONTADOR.md)

Resumen de los items pendientes para fase 3+ que afectan al motor.
Cuando se firmen, se traducen a reglas declarativas en `tax_rules`
con doble firma.

| ✍️  | # | Item                                                                  | Skill |
| --- | - | --------------------------------------------------------------------- | ----- |
| [ ] | 5 | Composición autoritativa "agregados art. 33 N°1" post Ley 21.713      | 3     |
| [ ] | 6 | Reglas aprovechamiento pérdidas tributarias post Ley 21.713 art. 31 N°3 | 3   |
| [ ] | 7 | Columnas SAC/RAI/REX/DDAN post Ley 21.713                              | 6     |
| [ ] | 8 | Formato `imputacion` en `retiros_y_distribuciones`                    | 6     |
| [ ] | 10| "Ningún año individual > 85.000 UF" interpretación oficial 14 D       | 7     |
| [ ] | 11| Tope "actividad relevante" para descalificación participación cruzada | 7     |
| [ ] | 12| Criterios `confianza_baja` < 3 años de historia                       | 7     |
| [ ] | 13| Política consulta art. 26 bis CT en ambigüedad                        | 1, 7  |
| [ ] | 14| Tope cuantitativo "sueldo empresarial razonable" por industria        | 1, 8  |
| [ ] | 15| Tope donaciones globales combinado con otros beneficios               | 8     |
| [ ] | 16| Interacciones P1 × P3: no doble beneficio sobre la misma base         | 8     |

---

## 9 · Procedimiento de firma

1. **Crear branch** `firma-contador-socio-<fecha>`.
2. **Para cada cifra que cambie**: nueva migración Supabase
   versionada (no editar las existentes).
3. **Para cifras correctas**: marcar `[x]` en este documento. Una vez
   todas marcadas, se mergea el flip `strict=False → strict=True` en
   los `@pytest.mark.xfail` de `tests/golden/`.
4. **Firma efectiva**: el PR debe ser revisado por
   `contador-socio@renteo.cl` (whitelist `INTERNAL_ADMIN_EMAILS`) Y
   por `admin-tecnico@renteo.cl` (segunda firma técnica). El
   constraint `rule_sets_double_sig_check` exige firmantes distintos.
5. **Activar gate**: setear `RENTEO_GOLDENS_FIRMADOS=1` en CI
   (`.github/workflows/ci.yml`). Cuando esté presente, los goldens
   pasan de `strict=False` a `strict=True` y un fallo bloquea merge.
6. **Actualizar `CHANGELOG.md`** con la versión `v0.2.0 — firma
   contador socio` y la fecha.

---

## 10 · Después de la firma

Lo que se desbloquea:

- Quitar el banner "preliminar" del frontend (`legal/placeholderBanner`).
- Habilitar `INTERNAL_ADMIN_EMAILS` con los emails reales del staff.
- Cargar primer cliente beta interno con datos reales.
- Empezar el track Stripe + pricing (cobrar ya tiene sentido).

Lo que **no** se desbloquea (siguen pendientes para fase 2+):
- Skill 7 fase 3 oficial (SAC/RAI/REX completo) — items 7-8.
- Watchdog real con HTTP fetcher DOF/SII (track 11d).
- Custodia certificado con AWS real (track 4c — passphrase via
  Secrets Manager).
