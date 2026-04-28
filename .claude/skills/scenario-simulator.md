# Simulador de Cierre de Ejercicio — Renteo

## Propósito
Definir el motor que permite al usuario PYME / mediana / contador
simular **what-if** sobre el cierre del año tributario en curso,
modificando palancas lícitas y viendo en vivo el impacto en RLI,
IDPC, distribuciones e IGC del dueño. Es la **feature core
diferencial** del producto.

## Marco legal
- LIR arts. 14 A, 14 D, 14 E, 21, 31, 33, 41 A, 41 C, 42 bis, 56.
- Ley 19.518 (SENCE).
- Ley 20.241 (I+D, extendida hasta 2035).
- Ley 21.755 + Circular SII 53/2025 (tasa transitoria 12,5%).
- `tax-compliance-guardrails.md` Lista blanca, ítems 1-12.

## Reglas no negociables
1. **Solo palancas de la lista blanca.** Si una palanca cae en lista
   negra, no aparece en la UI ni en el motor.
2. **Cada palanca se valida ex-ante** contra requisitos objetivos
   antes de aplicarla.
3. **Cada output muestra el fundamento legal** de la palanca.
4. Toda simulación queda guardada en `escenarios_simulacion` con
   inputs, outputs y `engine_version`.
5. **Comparador hasta 4 escenarios** lado a lado. El motor marca el
   "mejor escenario lícito" (`es_recomendado=true`) por menor carga
   total.
6. **Banderas rojas activas:** si el usuario configura una palanca
   en valor que dispare patrón de lista negra (ver
   `tax-compliance-guardrails.md`), la UI bloquea y educa.

---

## Inputs base (estado actual del año en curso)

Provienen de la sincronización SII y del onboarding:
- Régimen tributario vigente.
- RLI estimada del año en curso (cálculo desde RCV + ajustes).
- Activo fijo del año (compras detectadas).
- Planilla de remuneraciones del año (para tope SENCE).
- Dueños / socios y su porcentaje de participación.
- Retiros realizados en el año.
- Saldos SAC, RAI, REX iniciales.
- Año tributario objetivo (default: año en curso).

---

## Palancas (sliders / inputs)

Cada palanca tiene:
- ID interno.
- Nombre humano.
- Rango y unidad.
- Validación de elegibilidad.
- Fundamento legal.
- Cálculo de impacto.

### P1 — Depreciación instantánea de activos fijos
- ID: `dep_instantanea`.
- Input: lista de activos elegibles del año, con checkbox por activo.
- Validación: empresa en régimen 14 D + activo adquirido y en uso en
  el ejercicio. Acepta nuevos y usados (Oficio SII 715/2025).
- Impacto: deducción 100% del valor del activo en el año, baja RLI.
- Fundamento: art. 31 N°5 bis LIR + Oficio SII 715/2025.
- Bandera roja: si el activo fue adquirido a parte relacionada y
  hay indicio de no estar en uso real → bloquear.

### P2 — Franquicia SENCE
- ID: `sence`.
- Input: monto de gasto en capacitación (desde 0 hasta tope legal).
- Validación: cursos con OTEC acreditada, empleados en planilla,
  tope = max(1% planilla anual, 9 UTM si planilla pequeña).
- Impacto: crédito directo contra IDPC, no baja RLI.
- Fundamento: Ley 19.518.
- Bandera roja: cursos sin asistencia o sin OTEC → bloquear.

### P3 — Rebaja RLI por reinversión (art. 14 E)
- ID: `rebaja_14e`.
- Input: % de RLI a reinvertir, slider 0-50%, con tope absoluto
  5.000 UF.
- Validación: empresa régimen 14 D N°3, reinversión real (no retiros
  encubiertos en los siguientes 12 meses → si ya hay retiros que
  contradicen, bloquear).
- Impacto: rebaja directa de RLI por el monto reinvertido.
- Fundamento: art. 14 E LIR.

### P4 — Retiros vs. reinversión del dueño
- ID: `retiros`.
- Input: monto adicional a retirar antes del 31-dic, por dueño.
- Validación: respetar saldos SAC/RAI/REX. Mostrar imputación
  obligatoria (REX → RAI con crédito → RAI sin crédito).
- Impacto: aumenta IGC del dueño en el ejercicio, libera créditos
  SAC.
- Fundamento: arts. 14 A, 14 D LIR; Circular SII 73/2020 y
  posteriores.
- Bandera roja: retiros que excedan SAC/RAI/REX → mostrar advertencia
  de tributación sin crédito.

### P5 — Sueldo empresarial al socio activo
- ID: `sueldo_empresarial`.
- Input: monto mensual (sujeto a tope razonable según industria/función).
- Validación: socio trabaja efectiva y permanentemente, contrato y
  cotizaciones, monto razonable de mercado.
- Impacto: gasto aceptado para empresa (baja RLI), tributa como IUSC
  en el socio.
- Fundamento: art. 31 N°6 inc. 3° LIR.
- Bandera roja: socio sin presencia real, monto fuera de rango
  razonable definido por contador socio.

### P6 — Crédito I+D
- ID: `credito_id`.
- Input: monto certificado por CORFO.
- Validación: contrato I+D registrado y certificado.
- Impacto: 35% como crédito contra IDPC (tope 15.000 UTM), 65% como
  gasto.
- Fundamento: Ley 20.241; extensión Ley 21.755.

### P7 — Postergación IVA
- ID: `postergacion_iva`.
- Input: ON/OFF (no monto).
- Validación: ingresos promedio ≤100.000 UF, sin morosidad reiterada.
- Impacto: cero financiero en el año (solo timing); mostrar como
  "alivio de caja" no como ahorro.
- Fundamento: Ley 21.210; portal SII postergación IVA.

### P8 — Donaciones con beneficio tributario
- ID: `donaciones`.
- Input: monto y tipo de donación (cultural, social, reconstrucción,
  etc.).
- Validación: entidad receptora habilitada, no relacionada con
  donante, tope global y por tipo.
- Impacto: variable (50% crédito, 50% gasto en muchos casos).
- Fundamento: Ley Valdés y leyes complementarias.

### P9 — APV del dueño
- ID: `apv`.
- Input: monto anual y régimen A o B.
- Validación: dentro de tope anual.
- Impacto: rebaja de base imponible IGC del dueño.
- Fundamento: art. 42 bis LIR.

### P10 — Crédito IPE (rentas extranjeras)
- ID: `ipe`.
- Input: monto de impuesto extranjero pagado y prueba documental.
- Validación: existencia real de la renta y del impuesto pagado.
- Impacto: crédito imputable contra IDPC (con topes).
- Fundamento: arts. 41 A y 41 C LIR.

### P11 — Timing de facturación dentro del período
- ID: `timing_facturacion`.
- Input: lista de facturas que pueden adelantarse o diferirse según
  fecha de prestación efectiva.
- Validación: prestación efectiva del servicio en el período correcto;
  no facturar después del hecho gravado para evadirlo.
- Impacto: redistribución de RLI entre meses.
- Fundamento: Ley IVA arts. 9 y 55.
- Bandera roja: factura cuya prestación ya ocurrió y se difiere
  para evitar IVA → bloquear.

### P12 — Cambio de régimen (link a `regime-recommendation.md`)
- ID: `cambio_regimen`.
- Input: régimen objetivo.
- Validación: motor de elegibilidad de skill 7.
- Impacto: simulación a 3 años bajo nuevo régimen.

---

## Cálculo de impacto

Pseudo-código:

```python
def simulate_scenario(empresa, tax_year, inputs):
    # 1. Estado base
    base = compute_base_state(empresa, tax_year)

    # 2. Aplicar palancas en orden definido
    state = base.clone()
    for palanca in inputs.palancas:
        if not is_eligible(palanca, state):
            raise ScenarioInvalid(palanca, reason)
        if matches_red_flag(palanca, state):
            raise ScenarioBlocked(palanca, reason)
        state = apply(palanca, state)

    # 3. Recalcular RLI
    state.rli = compute_rli(state)

    # 4. IDPC con tasa vigente del régimen y año
    state.idpc = compute_idpc(state.regimen, tax_year, state.rli)

    # 5. SAC/RAI/REX postcierre
    state.sac, state.rai, state.rex = update_registros(state)

    # 6. IGC del dueño con retiros del escenario
    state.igc_per_socio = compute_igc(state)

    # 7. Carga total
    state.carga_total = state.idpc + sum(state.igc_per_socio.values())

    # 8. Comparación contra base
    state.ahorro = base.carga_total - state.carga_total

    return state
```

Orden de aplicación de palancas (importante porque algunas afectan
la base de otras):
1. Cambios de régimen (si aplica).
2. Gastos directos (depreciación, sueldo empresarial, donaciones,
   APV).
3. Rebajas RLI (14 E).
4. Cálculo RLI e IDPC.
5. Créditos contra IDPC (SENCE, I+D, IPE, donaciones).
6. Distribuciones / retiros.
7. IGC dueños.
8. Postergación IVA (sólo flag, no afecta carga total).
9. Timing facturación (solo redistribución mensual, ya reflejada).

---

## Comparador de escenarios

UI permite hasta 4 escenarios lado a lado, con tabla:

| Métrica | Base | Esc. 1 | Esc. 2 | Esc. 3 |
|---|---|---|---|---|
| RLI | | | | |
| IDPC | | | | |
| Retiros del año | | | | |
| IGC dueño 1 | | | | |
| IGC dueño 2 | | | | |
| Carga total | | | | |
| Ahorro vs base | — | | | |
| Es recomendado | — | ✓/✗ | ✓/✗ | ✓/✗ |

El motor marca como `es_recomendado` el escenario con menor carga
total entre los lícitos. Empate: priorizar el que tenga menos
palancas activadas (preferir simplicidad).

---

## Plan de acción exportable

Cuando el usuario selecciona un escenario, se genera checklist:

- [ ] Adquirir activo fijo X antes del 31-dic-AAAA (depreciación
      instantánea).
- [ ] Inscribir curso SENCE con OTEC Y, plazo Z.
- [ ] Reinvertir $X en empresa antes del 31-dic.
- [ ] Pagar sueldo empresarial al socio J por monto K mensual.
- [ ] Otorgar mandato a contador para presentar I+D ante CORFO.

Cada ítem con fecha límite y fundamento legal.

---

## Persistencia

Cada simulación guardada en `escenarios_simulacion` con:
- `inputs` = JSON de palancas.
- `outputs` = JSON con resultados.
- `es_recomendado` = bool.
- `engine_version` = hash + tag.
- `created_by` = user_id.

---

## Banderas rojas globales (rechazo automático del escenario)

- Suma de retiros + sueldo empresarial > capacidad real de la
  empresa → advertencia, no bloqueo.
- Reinversión 14 E con retiro equivalente en los 12 meses siguientes
  ya programado → bloquear.
- Adquisición de activo fijo elegible para depreciación instantánea
  desde parte relacionada sin razón económica documentada → bloquear.
- Sueldo empresarial fuera del rango razonable definido por contador
  socio → advertencia, requiere justificación.
- Donación a entidad relacionada con donante → bloquear.
- Crédito I+D sin certificación CORFO → bloquear.

---

## Casos golden (mínimo 6)

1. PYME 14 D N°3 con RLI base 30.000 UF, activa P1+P2+P3 → ahorro
   esperado $X validado por contador.
2. PYME 14 A con plan de retiro alto → comparar con migrar a 14 D N°3.
3. Empresa con I+D certificado: aplicar P6 → impacto en IDPC.
4. Dueño con APV régimen B (P9) + retiro alto (P4) → IGC neto.
5. Postergación IVA (P7) ON vs OFF → idéntica carga, distinto cash flow.
6. Escenario que activa bandera roja (sueldo a socio sin presencia)
   → motor bloquea, mensaje educativo correcto.

---

## TODO(contador)
- Definir rango razonable de sueldo empresarial por industria
  (input crítico para P5).
- Validar orden de aplicación de palancas (algunas son sensibles al
  orden, ej. donaciones que son crédito vs gasto).
- Definir tope de "donaciones globales" combinado con otros beneficios.
- Validar interacciones entre P1 (depreciación instantánea) y P3
  (rebaja 14 E): no doble beneficio sobre misma base.
- Confirmar política de aplicación del escenario "tasa revertida 25%"
  para 14 D N°3 cuando se rompe condicionalidad Ley 21.735.
