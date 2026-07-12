# Paquete de revisión — Contador Socio de Renteo

Documento de entrega para el contador tributario que asuma el rol
de **CONTADOR_SOCIO**. Es autocontenido: explica qué es Renteo, qué
estado tiene el motor, qué se te pide validar exactamente, en qué
orden, cuánto tiempo estimamos y qué pasa después de tu firma.

Fecha de preparación: 2026-07-12.

---

## 1 · Qué es Renteo y qué rol se te propone

Renteo es una aplicación de **optimización tributaria para Chile**
que atiende PYMEs (cliente A) y contadores/estudios (cliente B) con
un motor tributario único. El motor calcula IDPC, IGC y PPM,
recomienda régimen (14 A / 14 D N°3 / 14 D N°8 / renta presunta) y
simula escenarios de cierre con 12 palancas lícitas (P1-P12).

Principios no negociables del producto (están en el `CLAUDE.md` del
repositorio y en la skill `tax-compliance-guardrails`):

- Solo se recomienda lo que está en una **lista blanca firmada**.
  Economía de opción ✅; elusión y evasión ❌ bloqueadas por diseño
  (marco NGA arts. 4 bis/ter/quáter CT y art. 100 bis).
- Toda tasa, tramo o tope vive **parametrizado en tabla** por año
  tributario. El hardcoding está prohibido y un test de CI lo
  bloquea.
- Cada cálculo cita **artículo LIR + circular SII** y persiste un
  snapshot inmutable para auditoría.

El rol CONTADOR_SOCIO valida la lista blanca, los casos golden, los
rangos razonables y la interpretación SII; además firma (junto a un
admin técnico) cada publicación de reglas tributarias, y asume el
rol inicial de DPO (Ley 21.719). Este paquete cubre **solo la
primera tarea**: la firma inicial de parámetros y lista blanca.

## 2 · Estado actual: sandbox pre-firma

Desde 2026-05-11 el motor corre **end-to-end con cifras
placeholder** (basadas en Ley 21.755 y Circular SII 53/2025, con
UTM/UTA/UF aproximadas). Ninguna salida se emite como asesoría:

- Los tests golden están en `xfail` (no certifican).
- El gate de CI `RENTEO_GOLDENS_FIRMADOS` está apagado.
- El frontend muestra banner "preliminar" en todo output.
- El adaptador SII está en modo MOCK (no toca producción).

Tu firma es lo que convierte esos placeholders en cifras
respaldadas y saca el producto del sandbox. La ingeniería está
completa; **el único bloqueo es esta revisión profesional**.

Para ver el motor funcionando antes de firmar nada, el repositorio
incluye un caso de estudio reproducible:
[`docs/casos-estudio/01-ferreteria-pyme-mvp.md`](../casos-estudio/01-ferreteria-pyme-mvp.md)
(ferretería SpA, $400M de ingresos, migración 14 A → 14 D N°3 con
palancas; cada monto cita el placeholder usado y se reproduce con
`scripts/case_study_ferreteria.py` contra el motor real).

## 3 · Qué recibes en este paquete

| Documento | Qué es |
| --------- | ------ |
| [`../REVISION_CONTADOR_SOCIO.md`](../REVISION_CONTADOR_SOCIO.md) | Checklist firmable §1-§10: cada cifra placeholder con casillero `[ ]` para marcar o corregir. |
| `01_tax_year_params.sql` … `05_beneficios_topes.sql` | Borradores SQL con los placeholders precargados; se editan en sitio. |
| `06_whitelist_palancas_v2.sql` | Publicación de la lista blanca v3 (12 palancas + 3 items) con doble firma. |
| [`07_gate_flip.md`](./07_gate_flip.md) | Procedimiento para activar el gate de goldens en CI tras la firma. |
| [`README.md`](./README.md) | Procedimiento técnico paso a paso (lo ejecuta ingeniería contigo). |
| [`../../TODOS-CONTADOR.md`](../../TODOS-CONTADOR.md) | Backlog completo de validaciones profesionales por fase. |
| [`../casos-estudio/`](../casos-estudio/) | Caso de estudio para inspeccionar el comportamiento del motor. |

No necesitas saber programar ni tocar git: los SQL se leen como
tablas (una fila por cifra, con comentario `✍️ CONTADOR_SOCIO:` en
cada punto de decisión) y la mecánica de migraciones, tests y PR la
ejecuta ingeniería en la misma sesión.

## 4 · Qué se te pide validar, en orden

La revisión se divide en tres bloques según el tipo de trabajo.
Estimación total: **una sesión de 3-4 horas** junto a ingeniería.

### Bloque A — Parámetros objetivos (verificación contra fuente) · ~1 h 05

Cifras que se cotejan contra DOF, SII o texto legal. Trabajo
mecánico de confirmar o corregir:

| Paso | Qué | Checklist | SQL | Tiempo |
| ---- | --- | --------- | --- | ------ |
| A1 | UTM / UTA / UF dic por AT 2024-2026 (2027-2028 quedan como proyección no firmada) | §3 | `01_tax_year_params.sql` | 20 min |
| A2 | Tasas IDPC por régimen y AT — incluida la transitoria 12,5% de 14 D N°3 (Ley 21.755 / Circular 53-2025) y la reversión a 25% si se rompe la condicionalidad Ley 21.735 | §1 | `02_idpc_rates.sql` | 15 min |
| A3 | Tramos IGC (8 tramos en UTA, art. 52 LIR) y si la tabla cambia entre AT 2024-2026; tratamiento del crédito 5% último tramo (art. 56 LIR) | §2 | `03_igc_brackets.sql` | 20 min |
| A4 | Tasas PPM PyME (umbral 50.000 UF, tasas baja/alta por régimen) | §4 | `04_ppm_pyme_rates.sql` | 10 min |

### Bloque B — Juicio profesional (interpretación y riesgo) · ~1 h 30

Aquí está el corazón de tu rol. Firmar un item significa: *"esto es
economía de opción lícita y Renteo puede recomendarlo"*.

| Paso | Qué | Checklist | SQL | Tiempo |
| ---- | --- | --------- | --- | ------ |
| B1 | Topes paramétricos de beneficios (rebaja 14 E, crédito I+D, SENCE, APV, art. 33 bis, etc. — 14 topes con fuente legal cada uno) | §6 | `05_beneficios_topes.sql` | 30 min |
| B2 | **Lista blanca de palancas P1-P12** + 3 items complementarios (donaciones, crédito IPE, timing de facturación). Cada una con fundamento legal propuesto que debes confirmar o corregir | §5 | `06_whitelist_palancas_v2.sql` | 45 min |
| B3 | Banderas rojas implementadas (elegibilidad por régimen, topes excedidos, capacidad real de retiros): confirmar que la interpretación es correcta y suficiente | §7 | — (revisión de tabla) | 15 min |

### Bloque C — Casos golden · ~45 min

Los tests golden fijan el resultado esperado de cada función
crítica (`tests/golden/test_idpc_golden.py`, `test_igc_golden.py`,
`test_ppm_golden.py`). Se te presentan los casos con sus montos
esperados; validas que el resultado sea el que un contador
calcularía a mano. Tras tu firma pasan a **modo estricto**: si un
cambio de código altera un resultado firmado, el merge se bloquea
automáticamente. Este es el mecanismo que protege tu firma en el
tiempo.

## 5 · Qué NO se te pide en esta etapa

Para acotar la sesión, quedan explícitamente **fuera de alcance**
(siguen abiertos en `TODOS-CONTADOR.md` y se abordan después, cada
uno como nueva versión de regla):

- **Items 5-8** — agregados art. 33 N°1, pérdidas tributarias,
  columnas SAC/RAI/REX/DDAN y formato de imputación de retiros
  post Ley 21.713. Esperan doctrina SII aún no publicada; un
  watchdog legislativo monitorea DOF y SII y abrirá ticket cuando
  salga.
- **Item 14** — tope de "sueldo empresarial razonable" por
  industria. El placeholder (60 UF/mes) queda marcado como no
  firmado.
- **Items 10-13, 15-20** — interpretaciones de fase 3/4
  (diagnóstico y simulador avanzado).
- **Items 21-30** — DPO formal, DPAs, textos legales, pentest: son
  del sprint paralelo con el estudio jurídico.
- **UTM/UTA/UF AT 2027-2028** — se firman cuando el DOF publique;
  mientras tanto quedan como proyección visible pero no firmada.

## 6 · Mecánica de la firma (doble firma)

1. Recorres el checklist y los SQL con ingeniería; cada cifra queda
   confirmada (`[x]`) o corregida con su `fuente_legal` real.
2. Ingeniería convierte los SQL en migraciones versionadas, corre
   los goldens y activa el gate `RENTEO_GOLDENS_FIRMADOS=1`.
3. El PR final requiere **dos revisores distintos**: tu cuenta
   (`contador-socio@renteo.cl`, primera firma) y el admin técnico
   (`admin-tecnico@renteo.cl`, segunda firma). Un constraint de
   base de datos (`rule_sets_double_sig_check`) exige que ambos
   firmantes sean personas distintas — nadie puede publicar reglas
   solo.
4. La publicación queda versionada con vigencia temporal y hash de
   auditoría: toda corrección futura es una **nueva versión de
   regla**, nunca una edición silenciosa, y el rollback es atómico.

## 7 · Qué se desbloquea con tu firma

- El banner "preliminar" sale del frontend: los cálculos pasan a
  ser asesoría respaldada (siempre con el disclaimer legal
  versionado).
- Los goldens pasan a modo estricto: tu firma queda protegida por
  CI.
- Se carga el primer cliente beta interno con datos reales.
- Se habilita el track comercial (pricing).

Y hacia adelante, el rol implica una cadencia liviana: revisar los
tickets que abra el watchdog legislativo (cambios de tasas, nuevas
circulares), resolver los `TODO(contador)` que escale ingeniería, y
firmar cada nueva versión de reglas. El diseño del sistema hace que
ningún cambio tributario requiera redeploy de código: siempre es
una migración de parámetros con tu firma.

---

> 🟡 Recordatorio de estado: mientras esta revisión no ocurra,
> Renteo permanece en modo sandbox y ningún output del motor se
> entrega como asesoría.
