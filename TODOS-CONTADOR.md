# TODO(contador) y TODO(estudio_juridico)

Items que requieren validación profesional antes de mergear código que
los toque. Si un PR avanza sin resolver un bloqueante, el motor queda con
`TODO(contador)` y no se publica al usuario final.

Roles:

- **CONTADOR_SOCIO**: lista blanca, casos golden, rangos razonables,
  interpretación SII, escalamiento, DPO inicial (Ley 21.719).
- **ESTUDIO_JURIDICO**: textos legales finales, DPAs, mandato digital
  cliente B.

Última actualización: 2026-04-28 (cierre de fase 0).

---

## 🔴 Bloqueantes para arrancar fase 1 (núcleo tributario)

Sin estos, el motor no puede emitir el primer cálculo aún en preview
interno. Cargar como migraciones SQL versionadas con doble firma.

| # | Item | Skill | Responsable |
|---|---|---|---|
| 1 | Tabla de tasas IDPC AT 2024-2028 firmada (14 A, 14 D N°3 con flag transitoria 12,5%, 14 D N°8, retención BHE rampa 13% → 14,5% → 15,25% → 16% → 17%) con cita ley/circular por fila. | 3 | CONTADOR_SOCIO |
| 2 | Tabla IGC AT 2024-2028 firmada (8 tramos en UTA con `desde_uta`, `hasta_uta`, `tasa`, `rebajar_uta`) + crédito 5% último tramo (art. 56 LIR). | 3 | CONTADOR_SOCIO |
| 3 | UTA / UTM / UF dic año comercial AT 2024-2027 firmados con fuente (Diario Oficial, URL SII). | 3 | CONTADOR_SOCIO |
| 4 | Factor de crédito SAC para AT 2024-2026 (necesario para imputación de retiros 14 D N°3). | 3 | CONTADOR_SOCIO |
| 5 | Composición autoritativa de "agregados art. 33 N°1" para AT 2026 post Ley 21.713. | 3 | CONTADOR_SOCIO |
| 6 | Reglas de aprovechamiento de pérdidas tributarias post Ley 21.713 (art. 31 N°3). | 3 | CONTADOR_SOCIO |
| 7 | Confirmación de columnas de `tax_calc.registros_tributarios` (SAC, RAI, REX, DDAN) post Ley 21.713 antes de cerrar el modelo. | 6 | CONTADOR_SOCIO |
| 8 | Formato de `imputacion` en `tax_calc.retiros_y_distribuciones` (orden REX → RAI con crédito → RAI sin crédito y subcategorías). | 6 | CONTADOR_SOCIO |
| 9 | Mínimo 3 casos golden por función crítica de fase 1: IDPC por régimen × AT 2024/2025/2026 (≥9 casos), IGC AT 2026 con dueño retiro 5.000 UF con crédito, postergación IVA PYME 80.000 UF sin morosidad, PPM PYME 14 D N°3 transitorio bajo y alto, función PPUA con `tax_year >= 2025` retorna 0 con warning. | 3 | CONTADOR_SOCIO |
| 31 | **Cita legal obsoleta en reglas seedeadas:** la Circular SII N°65 de 2015 fue **dejada sin efecto** por la **Circular SII N°31 de 2025** (NGA post Leyes 21.713/21.716). Migrar `fuente_legal` de `65/2015` → `31/2025` en `20260506120000_track_1_2_legal_seeds.sql:136`, `20260514120000_track_palancas_p7_p12.sql:168` y `06_whitelist_palancas_v2.sql:137,160` + skill `tax-compliance-guardrails`. Requiere **nueva versión de regla con doble firma** (no es un edit de código). Ver `docs/optimizadores/01-gasto-del-giro.md` §8. | 1, 11 | CONTADOR_SOCIO |

---

## 🟡 Encolar para fase 3 (diagnóstico) y fase 4 (simulador)

No bloquean fase 1, pero sin ellos no se puede entregar diagnóstico ni
simulador al usuario final.

| # | Item | Skill | Responsable | Fase |
|---|---|---|---|---|
| 10 | Validación interpretativa "ningún año individual > 85.000 UF en últimos 3" para 14 D (interpretación oficial SII actualizada). | 7 | CONTADOR_SOCIO | 3 |
| 11 | Tope concreto de "actividad relevante" para descalificación por participación cruzada (% capital o dividendos). | 7 | CONTADOR_SOCIO | 3 |
| 12 | Criterios de `confianza_baja` para empresas con <3 años de historia y umbral mínimo para emitir recomendación. | 7 | CONTADOR_SOCIO | 3 |
| 13 | Política para recomendar consulta art. 26 bis CT al SII en caso de ambigüedad. | 1, 7 | CONTADOR_SOCIO | 3 |
| 14 | Tope cuantitativo y cualitativo de "sueldo empresarial razonable" por industria y función (input crítico para palanca P5). | 1, 8 | CONTADOR_SOCIO | 4 |
| 15 | Tope de donaciones globales combinado con otros beneficios. | 8 | CONTADOR_SOCIO | 4 |
| 16 | Validar interacciones P1 (depreciación instantánea) × P3 (rebaja 14 E): no doble beneficio sobre la misma base. | 8 | CONTADOR_SOCIO | 4 |
| 17 | Política de aplicación del escenario "tasa revertida 25%" cuando se rompe condicionalidad Ley 21.735 (cotización empleador). | 3, 7, 11 | CONTADOR_SOCIO | 3 |
| 18 | Lista blanca firmada con mínimo 3 oficios/jurisprudencia por item (12 items en `tax-compliance-guardrails.md`). | 1 | CONTADOR_SOCIO | go-live |
| 19 | Lista actualizada del Catálogo de Esquemas Tributarios SII + procedimiento de actualización mensual. | 1 | CONTADOR_SOCIO | go-live |
| 20 | Definir matriz de severidad para banderas rojas. | 1 | CONTADOR_SOCIO | 4 |
| 32 | Firmar topes numéricos del art. 31 LIR para `tax_params.beneficios_topes` (optimizador gasto del giro): donaciones art. 31 N°7 en **cascada** con el LGA del art. 10 Ley 19.885 (2% RLI / 1,6‰ capital propio → LGA 5% RLI; en pérdida, 4,8‰ CPT o 1,6‰ capital efectivo) — cruza con #15 —; art. 31 N°12 (tope 4% de ingresos por pagos al exterior; exención si tasa país ≥30%); art. 100 bis CT (100 UTA asesor / tope 250 UTA), **vigencia desde 2024-11-01, no por año tributario completo**. Detalle en `docs/optimizadores/01-gasto-del-giro.md` §3.3. | 3, 8, 11 | CONTADOR_SOCIO | 4 |
| 33 | Firmar el **nivel de riesgo por fila** del catálogo `gasto_giro_catalogo` por rubro. Es criterio experto, **no hay fuente SII**: el SII no publica catálogos por giro, resuelve caso a caso (verificado). El catálogo es un *prior* interno de retrieval, nunca se presenta como lista SII. Ver §5. | 1, 8 | CONTADOR_SOCIO | 4 |
| 34 | Perímetro exacto del "**devengado, cuando corresponde**" en la base caja del 14 D N°3 (Circular SII N°62/2020): ¿las operaciones con **relacionados** siguen regla de devengo? Bloquea la sub-palanca de *timing de pago*; hasta cerrarlo, base caja solo con terceros no relacionados. Ver §1.7. | 3, 8 | CONTADOR_SOCIO | 4 |
| 35 | Definición operativa de "**automóvil, station wagon y similares**" (art. 31 inc. 1°) frente a vehículo comercial (camioneta, furgón). Decide si el rubro Transporte deduce o se bloquea. Recordar: la prohibición **incluye el leasing**. Es la pregunta abierta de mayor impacto práctico del optimizador. Ver §1.6.1. | 1, 8 | CONTADOR_SOCIO | 4 |
| 36 | **Exposición propia de Renteo bajo el art. 100 bis CT** como "diseñador/planificador": multa de **100 a 250 UTA**, y la exención del art. 14 letra D **ampara al contribuyente, no al asesor**. Además, la ley incentiva al contribuyente a identificar a su asesor (si no lo hace, la multa recae sobre él). Evaluar reflejo en términos de servicio y en el encuadre del producto (reconocer/documentar vs. diseñar estructuras). Ver §1.4. | 1, 2 | ESTUDIO_JURIDICO | 4 |

---

## 🟢 Pre-go-live no tributarios

Cumplimiento Ley 21.719 + seguridad. No bloquean fase 1; sí bloquean
go-live público (fase 8).

| # | Item | Skill | Responsable | Fase |
|---|---|---|---|---|
| 21 | Designación formal de DPO (Delegado de Protección de Datos). | 5 | CONTADOR_SOCIO (rol inicial) | 7 |
| 22 | DPAs firmados con encargados: Supabase, AWS, SimpleAPI/BaseAPI, Resend, Sentry. | 2, 5 | ESTUDIO_JURIDICO | 7 |
| 23 | DPIA documentada para perfilamiento tributario automatizado (alto riesgo). | 5 | CONTADOR_SOCIO + ESTUDIO_JURIDICO | 7 |
| 24 | RAT (Registro de Actividades de Tratamiento) interno por finalidad. | 5 | CONTADOR_SOCIO | 7 |
| 25 | Procedimiento de notificación de brechas con runbook (72 h). | 5 | CONTADOR_SOCIO | 7 |
| 26 | Política de retención automatizada (purga nocturna respetando art. 17 CT, mínimo 6 años). | 5, 6 | CONTADOR_SOCIO | 7 |
| 27 | Razón social, RUT, dirección legal del responsable, contacto del DPO y canal único ARCOP — completar placeholders en política de privacidad y términos. | 2, 5 | ESTUDIO_JURIDICO | 7 |
| 28 | Revisión y firma final de `politica-privacidad-v1` y `terminos-servicio-v1` para emitir versión v2 firmada. | 2 | ESTUDIO_JURIDICO | 7 |
| 29 | Cláusulas DPA específicas para mandato digital con contadores (cliente B). | 2 | ESTUDIO_JURIDICO | 6 |
| 30 | Pentest externo OWASP Top 10. Cero vulnerabilidades críticas. | 5 | (proveedor externo) | 8 |

---

## Workflow de resolución

1. El item tiene un PR asociado con la migración SQL o el texto legal
   en cuestión.
2. CONTADOR_SOCIO o ESTUDIO_JURIDICO revisa, comenta, aprueba.
3. Para reglas tributarias: doble firma materializada por
   `published_by_contador` (commit firmado del contador) y
   `published_by_admin` (merge por admin técnico). El CHECK constraint
   en `tax_rules.rule_sets` exige firmantes distintos.
4. Para textos legales: incremento de versión en `CHANGELOG-LEGAL.md`.
5. Item se mueve a estado "resuelto" en este archivo (con fecha y PR).

## Cómo agregar un nuevo item

- Numerar al final.
- Indicar skill, responsable, fase objetivo.
- Si bloquea una fase, mover a la sección 🔴.
- Una línea por item; el detalle vive en el ticket o PR asociado.
