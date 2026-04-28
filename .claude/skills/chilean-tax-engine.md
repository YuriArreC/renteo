# Motor Tributario Chileno

## Propósito
Definir todas las reglas y parámetros tributarios aplicables al motor
de cálculo. Toda regla incluye fundamento legal, vigencia y caso
golden.

## Reglas no negociables del módulo
1. Toda tasa, tope, tramo o factor está PARAMETRIZADO POR AÑO
   TRIBUTARIO en una tabla. NUNCA hardcodeado.
2. Toda función de cálculo tiene test golden (caso de prueba)
   validado por contador socio.
3. Toda función incluye en su docstring el artículo LIR / Circular
   SII / Oficio que la fundamenta.
4. Si una función no tiene fundamento explícito, MARK TODO(contador)
   y no se mergea.

## Tabla de parámetros por año tributario
Schema sugerido:
- tax_year_params(year, idpc_rate_14a, idpc_rate_14d3, idpc_rate_14d8,
  iva_rate, ppm_min_14d3, ppm_max_14d3, retencion_honorarios,
  uta_pesos_dic, utm_pesos_dic, uf_pesos_dic, vigencia_inicio,
  vigencia_fin, fuente_legal, observaciones)

### Valores conocidos (verificar antes de uso)
| Año Tributario | IDPC 14 A | IDPC 14 D N°3 | IDPC 14 D N°8 | Retención BHE | Fuente |
|---|---|---|---|---|---|
| AT 2024 | 27% | 10% (transitoria post-pandemia) | 0% | 13% | Ley 21.578 |
| AT 2025 | 27% | 25% | 0% | 14,5% | Régimen permanente |
| AT 2026 | 27% | **12,5%** | 0% | **15,25%** | Ley 21.755, Circular SII 53/2025 |
| AT 2027 | 27% | 12,5% | 0% | 16% | Ley 21.755, calendario Ley 21.133 |
| AT 2028 | 27% | 12,5% | 0% | 17% | Ley 21.755 |
| AT 2029 | 27% | 15% | 0% | 17% | Ley 21.755 |

⚠️ **Condicionalidad rebaja transitoria 12,5%:** depende del cumplimiento
progresivo de la cotización empleador del art. 4° transitorio Ley 21.735
(1% en 2025, 3,5% en 2026, 4,25% en 2027, 5% en 2028). Si la
condicionalidad se incumple, las tasas pueden revertirse. Implementar
flag de monitoreo.

### IGC AT 2026 (8 tramos en UTA, UTA dic-2025 ≈ $834.504)
| Tramo | Desde UTA | Hasta UTA | Tasa | Cantidad a rebajar |
|---|---|---|---|---|
| 1 | 0 | 13,5 | Exento | 0 |
| 2 | 13,5 | 30 | 4% | 0,54 UTA |
| 3 | 30 | 50 | 8% | 1,74 UTA |
| 4 | 50 | 70 | 13,5% | 4,49 UTA |
| 5 | 70 | 90 | 23% | 11,14 UTA |
| 6 | 90 | 120 | 30,4% | 17,80 UTA |
| 7 | 120 | 310 | 35% | 23,32 UTA |
| 8 | > 310 | — | 40% | 38,82 UTA |
Crédito 5% sobre fracción afecta al 40% (art. 56 LIR).
Carga máxima efectiva: ~44,45%.

### IVA
- Tasa general: 19% (Ley sobre IVA, DL 825).
- Postergación 2 meses: ingresos promedio ≤100.000 UF, sin morosidad,
  notificación correo (Ley 21.210).

### PPM
- Régimen 14 D N°3 transitorio (Circ. 53/2025): **0,125%** si ingresos
  giro año anterior ≤50.000 UF; **0,25%** si > 50.000 UF. Aplica entre
  agosto 2025 y diciembre 2027.

## Cálculo RLI (Renta Líquida Imponible)
RLI = Ingresos brutos del giro
− Costo directo (art. 30)
− Gastos necesarios para producir la renta (art. 31)
+ Agregados (art. 33 N°1: gastos rechazados que no benefician
a propietarios)
− Rebajas autorizadas
− Pérdidas tributarias de ejercicios anteriores (art. 31 N°3,
sujeto a normas Ley 21.713)
🔒 CONTADOR_SOCIO valida: composición exacta de "agregados" para AT
2026, en especial post Ley 21.713 sobre uso de pérdidas.

## Gastos aceptados — art. 31 LIR (post Ley 21.210)
Concepto ampliado: basta APTITUD de generar renta y vinculación con
interés, desarrollo o mantención del giro. No se requiere que efectivamente
genere renta. Fuente: Circular SII N°53/2020.

Categorías codificadas en el motor (no exhaustivo):
- Remuneraciones (art. 31 N°6).
- Sueldo empresarial (art. 31 N°6 inc. 3°).
- Depreciación normal/acelerada/instantánea (art. 31 N°5 y 5 bis).
- Intereses (art. 31 N°1).
- Impuestos no IDPC (art. 31 N°2).
- Pérdidas (art. 31 N°3).
- Créditos incobrables (art. 31 N°4).
- Donaciones (art. 31 N°7 y leyes especiales).
- I+D (Ley 20.241, deducción 65%).
- Gastos de organización y puesta en marcha (art. 31 N°9).
- Gastos por transacciones y cláusulas penales con no relacionados
  (art. 31 N°14, post Ley 21.210).

## Gastos rechazados — art. 21 y art. 33 N°1 LIR
- Art. 21: si benefician propietarios → impuesto único 40%, sin crédito
  por IDPC.
- Si no benefician propietarios → se agregan a la RLI vía art. 33 N°1.

## Registros tributarios régimen 14 A y 14 D N°3
- **SAC** (Saldo Acumulado de Créditos): créditos por IDPC disponibles
  para imputar a IGC/IA en distribuciones futuras.
- **RAI** (Rentas Afectas a Impuestos): rentas que tributarán al
  retirarse/distribuirse.
- **REX** (Rentas Exentas / Ingresos no constitutivos de renta):
  pueden retirarse sin tributación adicional.
- **DDAN** (Diferencia entre Depreciación Acelerada y Normal): control.

🔒 CONTADOR_SOCIO valida: orden de imputación de retiros (REX → RAI con
crédito → RAI sin crédito), cálculo del crédito disponible (factor),
y reglas de transición Ley 21.713.

## PPUA — DEROGADO desde AT 2025
Pago Provisional por Utilidades Absorbidas: **NO aplica desde AT 2025**.
La función de cálculo retorna 0 y registra warning si se invoca con
year >= 2025. Fuente: Ley 21.210 con derogación gradual culminada AT 2025.

## Créditos contra IDPC (orden de imputación)
1. Crédito IPE (art. 41 A y 41 C LIR).
2. Crédito SENCE (Ley 19.518).
3. Crédito I+D (Ley 20.241).
4. Crédito por donaciones (varias leyes).

## Casos golden (mínimo 5 por función crítica)
Cada función debe tener test golden con:
- Inputs explícitos.
- Output esperado calculado a mano por contador socio.
- Año tributario de aplicación.
- Fuente legal del output (artículo + circular).

Ejemplos:
- `test_idpc_14d3_at2026_caso_pyme_50000UF.py`
- `test_igc_at2026_dueno_retiro_5000UF_con_credito.py`
- `test_postergacion_iva_pyme_80000UF_sin_morosidad.py`
- `test_depreciacion_instantanea_activo_usado_2025.py`
- `test_sueldo_empresarial_socio_efectivo_dentro_tope.py`

## TODO(contador)
- Validar tabla de tasas AT 2026-2029 con publicación oficial SII.
- Confirmar UTA/UTM/UF a la fecha de cálculo.
- Validar rampa de retención BHE (15,25% → 16% → 17%).
- Definir factor del crédito SAC para AT 2026.
- Definir reglas de aprovechamiento de pérdidas tributarias post
  Ley 21.713.
