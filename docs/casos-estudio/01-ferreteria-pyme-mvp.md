# Caso 01 — Ferretería de barrio (cliente A, PYME)

🟡 **INSPECCIÓN INTERNA · No es asesoría tributaria**. Cifras
calculadas sobre `tax_params` placeholder
(`20260502120000_tax_params_placeholder_seeds.sql`). La firma del
contador socio sigue pendiente. La proyección 3 años asume tasas
estables; el escenario revertido por Ley 21.735 art. 4° transitorio
queda señalizado más abajo como bandera amarilla.

## Perfil

Ferretería de barrio en la comuna de Independencia, sociedad por
acciones (SpA), 1 dueño + 1 cónyuge (ambos personas naturales
chilenas), 8 empleados de planta. Año tributario AT 2026.

| Variable | Valor | Notas |
| -------- | ----- | ----- |
| Ingresos anuales 2025 | $400.000.000 CLP | Ventas con IVA cobradas |
| Promedio ingresos 3a | $390.000.000 CLP | ≈ 9.929 UF (UF dic $39.280) |
| Capital efectivo inicial | $50.000.000 CLP | ≈ 1.273 UF |
| Ingresos pasivos | 5% | Arriendo bodega trasera |
| Planilla anual (8 empleados) | $72.000.000 CLP | Sueldo bruto promedio $750k |
| RLI proyectada AT 2026 | $80.000.000 CLP | Margen ≈ 20% |
| Retiros planeados dueño | 60% RLI = $48.000.000 | Único retirante |
| Régimen actual | **14 A** semi integrado | Supletorio: nunca optó |

Decisión a tomar: ¿qué régimen y qué palancas optimizan la carga
del dueño en AT 2026, dentro de la lista blanca de Renteo?

## Paso 1 — Elegibilidad (skill 7)

El wizard de Renteo evalúa los 4 regímenes en orden:

| Régimen | Elegible | Por qué |
| ------- | -------- | ------- |
| 14 A — General | ✓ (supletorio) | Aplica a cualquier contribuyente |
| **14 D N°3** — Pro PyME General | ✓ | Promedio 3a $390M ≈ 9.929 UF (< 75.000 UF), capital $50M < 85.000 UF, dueños PN Chile, pasivos < 35% (art. 14 D LIR) |
| 14 D N°8 — Pro PyME Transparente | ✓ | Mismos requisitos que 14 D N°3, sin tope adicional para este perfil |
| Renta presunta art. 34 | ✗ | Sector comercio no califica (limitado a agrícola/transporte/minería) |

Tres regímenes elegibles; entre ellos el motor proyecta carga a 3
años y recomienda el de menor total.

## Paso 2 — Status quo (14 A sin palancas)

Cálculo año a año con los placeholders firmados a continuación:

- Tasa IDPC 14 A AT 2026 → **27%**
  (`tax_params.idpc_rates.rate WHERE regimen='14_a' AND tax_year=2026`)
- UTA dic 2025 → **$834.504 CLP**
  (`tax_year_params.uta_pesos_dic WHERE tax_year=2026`)
- Tramos IGC AT 2026 → 8 tramos en UTA, art. 52 LIR

### Año 1 (AT 2026)

```
IDPC = 0,27 × $80.000.000               = $21.600.000
Base IGC (retiros)                       =  $48.000.000
$48.000.000 / $834.504 UTA               = 57,52 UTA
Tramo 4 (50–70 UTA): tasa 13,5% · rebajar 4,49 UTA
impuesto_uta = 57,52 × 0,135 − 4,49      = 3,27 UTA
IGC = 3,27 × $834.504                    =  $2.733.245
─────────────────────────────────────────────────────
Carga total año 1                          $24.333.245
```

### Proyección 3 años (asume RLI y retiros estables)

| Año | RLI | IDPC | Retiros | IGC | **Total** |
| --- | --- | ---- | ------- | --- | --------- |
| 2026 | $80.000.000 | $21.600.000 | $48.000.000 | $2.733.245 | **$24.333.245** |
| 2027 | $80.000.000 | $21.600.000 | $48.000.000 | $2.733.245 | **$24.333.245** |
| 2028 | $80.000.000 | $21.600.000 | $48.000.000 | $2.733.245 | **$24.333.245** |
| **Total 3 años** | | | | | **$72.999.735** |

> **Nota — Crédito IDPC contra IGC**: el motor actual calcula IDPC
> y IGC por separado y NO descuenta el crédito 65% del semi
> integrado (art. 14 A) automáticamente. El comparador queda
> conservador a favor del status quo (le da más carga al status
> quo de la real). El item está pendiente de validación
> contador socio (skill 3 §"créditos contra IDPC").

## Paso 3 — Recomendación Renteo: cambio a 14 D N°3

El motor evalúa las 3 proyecciones elegibles, elige la menor total y
verifica que `cambio_regimen` esté en la lista blanca v1.

### 14 D N°3 puro (sin palancas), año 1

```
Tasa IDPC 14 D N°3 AT 2026 → 12,5% transitoria
  (tax_params.idpc_rates · Ley 21.755 · Circular SII 53/2025)
IDPC = 0,125 × $80.000.000               = $10.000.000
Base IGC (retiros)                        = $48.000.000
IGC = $2.733.245                           (igual que 14 A)
─────────────────────────────────────────────────────
Carga total año 1                          $12.733.245
```

### Proyección 3 años (asume tasa transitoria estable)

| Año | IDPC | IGC | **Total** | Ahorro vs 14 A |
| --- | ---- | --- | --------- | --------------- |
| 2026 | $10.000.000 | $2.733.245 | $12.733.245 | $11.600.000 |
| 2027 | $10.000.000 | $2.733.245 | $12.733.245 | $11.600.000 |
| 2028 | $10.000.000 | $2.733.245 | $12.733.245 | $11.600.000 |
| **Total 3 años** | | | **$38.199.735** | **$34.800.000** |

> **🟡 Bandera amarilla — Ley 21.735 art. 4° transitorio**: la
> tasa 12,5% queda condicionada al cumplimiento de cotizaciones
> previsionales del empleador. Si la condicionalidad se rompe, la
> tasa revierte a **25%** y el ahorro se reduce a la mitad. El
> motor expone el escenario dual: ver "Escenario revertido"
> abajo.

### Escenario revertido (mismo régimen, tasa 25% por incumplimiento)

```
IDPC = 0,25 × $80.000.000                 = $20.000.000
IGC                                        =  $2.733.245
─────────────────────────────────────────────────────
Carga total año 1                          $22.733.245
Total 3 años                              ($68.199.735)
Ahorro vs 14 A en escenario revertido      $4.800.000
```

Aún en el escenario revertido el cambio mejora un poco — pero el
plan de ejecución debe garantizar la condicionalidad (DT pagados
mes a mes en formulario 1879/3252) o el ahorro se evapora.

## Paso 4 — Simulador (palancas P1, P2, P9) sobre 14 D N°3

El simulador permite aplicar palancas de la lista blanca al
escenario base recomendado. Combinación elegida para este perfil:

| ID | Palanca | Acción | Fundamento |
| -- | ------- | ------ | ---------- |
| P1 | Depreciación instantánea | Compra y pone en uso $15M en estanterías + montacargas en 2026 | art. 31 N°5 bis LIR · Oficio SII 715/2025 |
| P2 | SENCE | $720k en capacitación OTEC acreditada (= 1% planilla) | Ley 19.518 |
| P9 | APV del dueño | Aporta el tope anual 600 UF = $23.568.000 régimen A | art. 42 bis LIR · DL 3.500 |

### Año 1 (AT 2026) con palancas

```
Aplicar P1 — depreciación instantánea
  RLI ajustada = $80.000.000 − $15.000.000 = $65.000.000

Calcular IDPC bruto (14 D N°3)
  IDPC bruto = 0,125 × $65.000.000        = $8.125.000

Aplicar P2 — crédito SENCE contra IDPC
  Tope SENCE = max(1% × $72.000.000, 9 UTM × $69.542)
             = max($720.000, $625.878)
             = $720.000
  Crédito aplicado = min($720.000, $720.000) = $720.000
  IDPC neto = $8.125.000 − $720.000        = $7.405.000

Aplicar P9 — APV deduce base IGC
  Base IGC = $48.000.000 − $23.568.000      = $24.432.000
  $24.432.000 / $834.504 UTA                = 29,28 UTA
  Tramo 2 (13,5–30 UTA): tasa 4% · rebajar 0,54 UTA
  impuesto_uta = 29,28 × 0,04 − 0,54        = 0,63 UTA
  IGC = 0,63 × $834.504                      =   $526.658
─────────────────────────────────────────────────────
Carga total año 1                            $7.931.658
```

### Proyección 3 años (P1 solo año 1; P2 y P9 todos los años)

P1 es one-shot del año de la compra; P2 y P9 se sostienen
mientras la empresa mantenga la planilla y el dueño siga con
capacidad de aporte.

| Año | RLI ajustada | IDPC neto | Base IGC | IGC | **Total** |
| --- | ------------ | --------- | -------- | --- | --------- |
| 2026 | $65.000.000 (P1) | $7.405.000 | $24.432.000 | $526.658 | **$7.931.658** |
| 2027 | $80.000.000 | $9.280.000 (− SENCE) | $24.432.000 | $526.658 | **$9.806.658** |
| 2028 | $80.000.000 | $9.280.000 | $24.432.000 | $526.658 | **$9.806.658** |
| **Total 3 años** | | | | | **$27.544.974** |

## Paso 5 — Comparador final

| Escenario | Total 3 años | Δ vs status quo | Δ % |
| --------- | ------------ | --------------- | --- |
| 14 A status quo, sin palancas | $72.999.735 | — | — |
| 14 D N°3 puro (solo cambio régimen) | $38.199.735 | **−$34.800.000** | **−47,7%** |
| 14 D N°3 + P1·P2·P9 (recomendación Renteo) | $27.544.974 | **−$45.454.761** | **−62,3%** |
| 14 D N°3 revertido por Ley 21.735 | $68.199.735 | −$4.800.000 | −6,6% |

**El beneficio bruto de Renteo para esta PYME es del orden de
$45M en 3 años** — siempre que la condicionalidad de Ley 21.735
se cumpla. Esa es la mitad del ahorro que el motor está
proyectando y es donde el contador socio debe firmar la política
de monitoreo del DT pagado.

## Banderas y riesgos identificados por el motor

1. **🟡 Capacidad real**: la suma retiros + sueldo + APV sigue por
   debajo de 1,5x RLI (sin sueldo empresarial; el dueño cobra sólo
   retiros). Bandera no se dispara.
2. **🟡 Ley 21.735 art. 4° transitorio**: si en cualquier mes
   2026-2028 el DT cae fuera de plazo, la tasa 12,5% revierte a
   25% y el ahorro baja a $4,8M en 3 años. Plan de acción
   obligatorio: agenda mensual + alerta automática del watchdog.
3. **🟡 P9 APV sobre el tope**: el aporte sugerido ($23,57M) coincide
   con el tope anual. Aportes mayores no generan crédito; el dueño
   debe entender la asimetría antes de aportar de más.
4. **🟡 P1 depreciación instantánea**: requiere bien nuevo en uso
   efectivo dentro del ejercicio. Si la compra se atrasa al 2027,
   el ahorro de $1,875M se desplaza un año (no se pierde, pero el
   flujo cambia).
5. **🟢 P2 SENCE**: tope ya saturado al 1% de planilla; la palanca
   está optimizada al 100%.

## Por qué este caso muestra el motor en su mejor forma

Una PYME con perfil similar **sin** Renteo decide régimen al fundar
la SpA, normalmente 14 A por desconocimiento, y queda ahí. La
diferencia entre 14 A y 14 D N°3 transitoria es el grueso del
ahorro: **47,7% en 3 años** sólo por cambiar de régimen + avisar al
SII (Form. 3265). Las palancas suman otro 14,6%. Total ≈ 62%.

PYMEs ya optimizadas (que ya están en 14 D N°3) verán números
mucho más modestos — el techo se reduce a las palancas (5-15%).
Cliente B (contadores) verá el comparador agregado sobre toda su
cartera; ese caso queda para 02-cartera-estudio-contable.md.

## Cómo reproducir estos números

```powershell
# 1. Levantar Supabase local con las migraciones (incluye seeds placeholder)
supabase start --workdir .

# 2. Variable de entorno
$env:DATABASE_URL = "postgresql+asyncpg://postgres:postgres@127.0.0.1:54322/postgres"

# 3. Correr el script
python scripts/case_study_ferreteria.py
```

El script llama al motor real:
`compute_idpc`, `compute_igc`, `_load_topes`, `_apply_palancas`,
`_carga`. Si los placeholders cambian (nuevas migraciones), el
script detecta el hash y aborta con un mensaje pidiendo re-revisar
este caso.

## Disclaimer (versión sandbox)

Este caso usa datos ficticios y placeholders no firmados. No
constituye recomendación tributaria, asesoría financiera ni
sustituye al contador del contribuyente. Cualquier decisión real
debe basarse en cifras firmadas por el contador socio + estudio
jurídico al cierre del sprint `firma-contador-socio-2026-05`.

Disclaimer formal versionado: ver `disclaimer-recomendacion-v1`
en `privacy.legal_texts` (skill 2).
