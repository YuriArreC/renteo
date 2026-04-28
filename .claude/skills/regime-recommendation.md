# Recomendación de Régimen Tributario — Renteo

## Propósito
Definir el árbol de decisión, validaciones de elegibilidad y
proyección financiera multi-año para recomendar al usuario el
régimen tributario óptimo entre 14 A, 14 D N°3, 14 D N°8 y renta
presunta.

## Marco legal
- LIR arts. 14 A, 14 D N°3, 14 D N°8, 34 (renta presunta).
- Ley 21.210 (estructura de regímenes).
- Ley 21.713 (modificaciones recientes).
- Ley 21.755 + Circular SII 53/2025 (rebaja transitoria 12,5% IDPC
  14 D N°3 para AT 2026-2028).
- `tax-compliance-guardrails.md` Lista blanca, ítem 1.

## Reglas no negociables
1. La recomendación nace solo si el contribuyente cumple TODOS los
   requisitos objetivos del régimen sugerido.
2. Si el caso requiere reorganización societaria para calzar en un
   régimen, se RECHAZA. Mostrar mensaje educativo, no la
   recomendación.
3. La proyección financiera es a **3 años** mínimo.
4. Cada output cita artículo LIR + Circular SII vigente.
5. Cada output incluye el `disclaimer-recomendacion-v1` de
   `disclaimers-and-legal.md`.
6. Si la rebaja transitoria 12,5% IDPC 14 D N°3 está en juego, la
   proyección debe **mostrar también el escenario en que se reverta**
   por incumplimiento de la condicionalidad de Ley 21.735 (cotización
   empleador). No esconder ese riesgo.

---

## Inputs requeridos del wizard

Wizard de 12-15 preguntas. Si falta un dato crítico, no avanzar.

**Identificación**
1. RUT empresa.
2. Régimen actual (auto-detectado de `empresas.regimen_actual` si
   ya está sincronizado vía SII; si no, preguntar).
3. Fecha de inicio de actividades.

**Situación económica**
4. Capital efectivo inicial (UF).
5. Ingresos del giro últimos 3 años (promedio anual UF). Si la
   empresa tiene <3 años, se pide proyección y se marca
   `confianza_baja`.
6. Estructura de ingresos: % pasivos vs. operacionales.
7. Sector / giro principal (afecta renta presunta).

**Estructura societaria**
8. Tipo jurídico (SpA, SRL, Ltda, EIRL, persona natural con giro,
   sociedad anónima cerrada, sociedad anónima abierta).
9. Composición de dueños:
   - ¿Todos los dueños son personas naturales con domicilio o
     residencia en Chile, o personas jurídicas sin domicilio en Chile?
     (relevante para 14 D N°8).
   - Cantidad de socios.
   - % participación.

**Plan futuro**
10. Expectativa de ingresos próximos 3 años.
11. Plan de retiros vs. reinversión por el dueño principal
    (porcentaje aproximado anual).
12. ¿Tiene o piensa tener filiales / coligadas? (afecta concepto de
    grupo empresarial).

**Otros**
13. ¿Tiene rentas de fuente extranjera? (relevante crédito IPE).
14. ¿Realiza I+D certificable? (Ley 20.241).
15. ¿Tiene actividad en sector con renta presunta? (agrícola,
    transporte, minería).

---

## Motor de elegibilidad

Cada régimen tiene una función `is_eligible_for_<regimen>(inputs)`
que retorna `(bool, list[razones])`.

### 14 A — Régimen General Semi Integrado
- Sin requisitos cuantitativos. Es el régimen supletorio.
- Siempre elegible si no aplica otro.

### 14 D N°3 — Pro Pyme General
Elegibilidad (todas las condiciones):
- Promedio ingresos giro últimos 3 años ≤ 75.000 UF (al cierre del
  año comercial).
- Ningún año individual de los últimos 3 puede superar 85.000 UF.
- Capital efectivo inicial ≤ 85.000 UF (si recién inicia actividades).
- Ingresos pasivos no superan 35% del total.
- No participar en otra empresa por más del 10% del capital o
  dividendos en empresas no acogidas a 14 D.

Si falla alguna, listar la razón. Recomendación NO se entrega.

### 14 D N°8 — Pro Pyme Transparente
Elegibilidad (todas las del 14 D N°3) PLUS:
- Todos los dueños son personas naturales con domicilio/residencia
  en Chile, O contribuyentes sin domicilio en Chile (Adicional).
- Ningún dueño es persona jurídica con domicilio en Chile.

### Renta presunta (art. 34 LIR)
Elegibilidad (todas):
- Actividad agrícola: ventas anuales ≤ 9.000 UF.
- Transporte terrestre de carga: ventas anuales ≤ 5.000 UF.
- Minería: ventas anuales ≤ 17.000 UF.
- Cumplimiento de capital propio inicial.
- No tener participación en sociedades anónimas / SpA con cierto %
  capital.

Si la empresa no opera en estos rubros, descartar.

---

## Scoring por carga tributaria proyectada

Para cada régimen elegible, calcular carga tributaria total
(empresa + dueños) a 3 años:
carga_total_regimen = sum(
idpc(regimen, año, rli) +
igc_dueños(regimen, año, retiros, sac, rai, rex)
) for año in [año_actual, año_actual+1, año_actual+2]

Variables de entrada al cálculo:
- RLI proyectada (input 10 del wizard).
- Plan de retiros (input 11).
- Tasas IDPC desde `idpc_rates` (incluyendo 12,5% transitoria
  14 D N°3 condicionada).
- Crédito SAC: 100% en 14 D N°3, 65% en 14 A semi integrado.
- Tabla IGC desde `igc_brackets`.
- Topes y beneficios desde `tax_params.*`.

El motor produce 4 escenarios:
- Régimen actual (baseline).
- Mejor régimen elegible alternativo.
- Cada otro régimen elegible (si lo es).

Y una **proyección dual** para 14 D N°3:
- Con rebaja 12,5% (escenario base).
- Con tasa 25% (escenario revertido por Ley 21.735).

---

## Output al usuario

Estructura del informe:

**1. Veredicto**
- "Régimen actual: 14 A"
- "Régimen recomendado: 14 D N°3"
- Ahorro estimado a 3 años: $X (en CLP) / Y UF.

**2. Sustento legal**
- Cita de art. 14 D N°3 LIR.
- Cita de Circular SII 53/2025 sobre tasa transitoria.
- Si aplica: cita de Ley 21.755.

**3. Requisitos cumplidos**
Tabla con cada requisito y su estado (✓ / ✗).

**4. Proyección financiera 3 años**
- Tabla por régimen × año con: RLI, IDPC, retiros, IGC, total.
- Gráfico comparativo (frontend).
- Escenario dual para 14 D N°3.

**5. Riesgos e implicancias del cambio**
- Costos de cambio: nuevo plan de cuentas, ajustes contables,
  registros SAC/RAI/REX si aplica.
- Implicancias en IVA (no cambia).
- Plazo y forma de cambio: aviso al SII en abril del año siguiente.
- Reversibilidad y restricciones para volver al régimen anterior.

**6. Disclaimer obligatorio**
`disclaimer-recomendacion-v1`.

**7. Acciones siguientes**
- "Generar PDF para tu contador."
- "Agendar revisión humana antes de decidir." (link revisión humana
  por Ley 21.719).

---

## Persistencia

Cada recomendación se guarda en `recomendaciones` con:
- `tipo = "cambio_regimen"`.
- `inputs_snapshot` = JSON del wizard.
- `outputs` = JSON con escenarios y veredicto.
- `engine_version` = hash + tag.
- `fundamento_legal` = artículos y circulares citadas.

---

## Casos de exclusión (rechazo automático)

- Empresa con menos de 1 año de operación → marcar
  `confianza_baja`, mostrar recomendación con disclaimer reforzado y
  obligar revisión humana antes de actuar.
- Empresa en proceso de fusión, división o disolución → no recomendar.
- Empresa con observaciones, bloqueos o anotaciones SII → no recomendar
  hasta resolver.
- Empresa con rentas de fuente extranjera complejas (filiales en
  paraísos, holdings internacionales) → escalar a contador socio,
  recomendación TODO(contador).
- Empresa parte de grupo empresarial con sociedad dominante en
  régimen 14 A → revisar consistencia antes de recomendar 14 D.

---

## Casos golden (mínimo 5)

1. PYME comercio, ingresos promedio 30.000 UF, dueño persona natural
   chileno → 14 D N°3 (transitoria 12,5%) vs 14 D N°8.
2. PYME servicios, ingresos 60.000 UF, dueños mixtos (persona
   natural + persona jurídica chilena) → 14 D N°3, no califica
   14 D N°8.
3. Empresa servicios financieros, ingresos pasivos 50% → no califica
   14 D, queda en 14 A.
4. Empresa agrícola, ventas 6.000 UF anuales, capital inicial bajo →
   renta presunta vs 14 D N°3.
5. PYME en crecimiento que pasó de 70.000 a 90.000 UF en últimos 3
   años → cae fuera de 14 D, debe migrar a 14 A.

Cada caso golden con valores numéricos exactos y output esperado
validado por contador socio.

---

## TODO(contador)
- Validar requisito "ningún año puede superar 85.000 UF" en últimos
  3 años para 14 D (interpretación oficial SII actualizada).
- Definir tope concreto de "actividad relevante" para descalificación
  por participación en otras empresas.
- Definir cuándo recomendar consulta art. 26 bis CT en caso de
  ambigüedad de elegibilidad.
- Validar criterios de "confianza_baja" para empresas con <3 años de
  historia y umbral mínimo para emitir recomendación.
