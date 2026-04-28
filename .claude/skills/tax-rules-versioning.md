# Versionado de Reglas Tributarias — Renteo

## Propósito
Garantizar que cambios en la legislación tributaria chilena (leyes,
circulares, oficios SII, jurisprudencia) se reflejen en Renteo
modificando DATOS, no código. Esta skill define el contrato técnico
entre el motor de cálculo y las reglas que aplica: cómo se modelan,
versionan, publican y consumen.

Toda regla con vigencia temporal (elegibilidad de regímenes, palancas
del simulador, banderas rojas, imputación de créditos, fórmulas de
RLI, validaciones del motor) se gestiona conforme a esta skill. Si
una regla no encaja en el modelo aquí descrito, DETENER y discutir
antes de inventar un mecanismo paralelo.

## Principios no negociables
1. **El motor no conoce años específicos.** Recibe `tax_year` y
   consulta reglas. Cero `if year == 2026` en código.
2. **Cero números mágicos** en `apps/api/src/domain/tax_engine/`.
   Tasas, tramos, topes, factores viven en tablas o reglas
   declarativas con vigencia.
3. **Snapshot inmutable** de cada cálculo: jamás se sobrescribe un
   resultado al cambiar reglas. Recalcular = nuevo cálculo.
4. **Trazabilidad inversa:** dada una ley nueva, debe ser posible
   listar todas las reglas afectadas en menos de 1 minuto.
5. **Doble firma para publicar** una regla nueva: contador socio +
   admin técnico. Sin excepción en producción.
6. **CI bloquea regresiones:** tests automáticos rechazan
   hardcoding y validan que toda regla publicada tiene fuente legal
   y vigencia.

---

## Tres niveles de cambio que el sistema soporta

| Nivel | Ejemplo | Cómo se resuelve |
|---|---|---|
| 1. Parámetros | Tasa IDPC sube de 12,5% a 15% | Insertar fila en `tax_year_params` o `idpc_rates` con nueva vigencia |
| 2. Reglas | Cambia tope de 75.000 UF a 100.000 UF; cambia fórmula de RLI | Insertar nueva versión de regla en tabla declarativa con `vigencia_desde` |
| 3. Estructura | Nace régimen nuevo; deroga PPUA | Catálogo + reglas nuevas; código mínimo si el motor es declarativo |

Niveles 1 y 2 deben resolverse SIN redeploy de código. Nivel 3 puede
requerir migración + código nuevo, pero el modelo de datos debe
absorber la mayor parte.

---

## Modelo de datos

### Schema `tax_rules` — reglas declarativas versionadas

**rule_sets**
Agrupa reglas por dominio (un dominio = un conjunto coherente de
reglas que se aplican juntas).

| col | tipo | notas |
|---|---|---|
| id | uuid PK | |
| domain | text | `regime_eligibility`, `palanca_definition`, `red_flag`, `rli_formula`, `credit_imputation_order`, etc. |
| key | text | identificador estable dentro del dominio (ej. `14_d_3`, `dep_instantanea`, `sueldo_a_socio_sin_presencia`) |
| version | int | incrementa con cada cambio |
| vigencia_desde | date | |
| vigencia_hasta | date | nullable |
| rules | jsonb | el cuerpo declarativo de la regla |
| fuente_legal | jsonb | `[{tipo:"ley", id:"21.755"}, {tipo:"circular_sii", id:"53/2025"}]` |
| status | text | `draft`, `pending_approval`, `published`, `deprecated` |
| published_by_contador | uuid FK auth.users | nullable hasta publicación |
| published_by_admin | uuid FK auth.users | nullable hasta publicación |
| published_at | timestamptz | nullable |
| created_at | timestamptz | |

UNIQUE (domain, key, version).
INDEX (domain, key, vigencia_desde, vigencia_hasta).

**rule_set_changelog** (auditoría de cambios)
| col | tipo | notas |
|---|---|---|
| id | uuid PK | |
| rule_set_id | uuid FK | |
| action | text | `created`, `submitted`, `approved`, `published`, `deprecated` |
| diff | jsonb | before/after del campo `rules` |
| performed_by | uuid FK auth.users | |
| performed_at | timestamptz | |
| comment | text | |

**legal_dependencies**
Mapeo regla ↔ fuentes legales que la sustentan, mantenido por
contador socio. Permite trazabilidad inversa.

| col | tipo | notas |
|---|---|---|
| rule_set_id | uuid FK | |
| fuente_tipo | text | `ley`, `decreto`, `circular_sii`, `oficio_sii`, `resolucion_sii`, `jurisprudencia_tta`, `cs` |
| fuente_id | text | ej. "21.755", "53/2025", "715/2025" |
| articulo | text | nullable, ej. "art. 31 N°5 bis" |

PK (rule_set_id, fuente_tipo, fuente_id, articulo).

---

## Estructura JSON de una regla declarativa

El campo `rules` admite distintos shapes según el `domain`. Los
schemas se validan con JSON Schema almacenado en
`apps/api/src/domain/tax_engine/rule_schemas/`. Toda regla nueva DEBE
validar contra el schema de su dominio antes de pasar a `published`.

### Domain `regime_eligibility`
Reglas para evaluar si un contribuyente califica para un régimen.

```json
{
  "all_of": [
    {
      "field": "ingresos_promedio_uf",
      "op": "lte",
      "value": 75000,
      "message": "Promedio ingresos últimos 3 años > 75.000 UF",
      "fundamento": "art. 14 D N°3 inc. 1° LIR"
    },
    {
      "field": "ingresos_max_un_ano_uf",
      "op": "lte",
      "value": 85000,
      "message": "Algún año individual superó 85.000 UF",
      "fundamento": "art. 14 D N°3 LIR"
    },
    {
      "field": "pct_ingresos_pasivos",
      "op": "lte",
      "value": 0.35,
      "message": "Ingresos pasivos > 35%",
      "fundamento": "art. 14 D N°3 LIR"
    }
  ]
}
```

Operadores soportados:
`eq`, `neq`, `lt`, `lte`, `gt`, `gte`, `between`, `in`, `not_in`,
`exists`, `not_exists`, `matches_regex`.

Combinadores: `all_of`, `any_of`, `not`.

### Domain `palanca_definition`
Define una palanca del simulador (skill 8) con su rango,
elegibilidad y fórmula de impacto.

```json
{
  "id": "dep_instantanea",
  "nombre_humano": "Depreciación instantánea de activos fijos",
  "tipo_input": "asset_list",
  "elegibilidad": {
    "all_of": [
      {"field": "regimen", "op": "in",
       "value": ["14_d_3", "14_d_8"]},
      {"field": "activo.estado", "op": "eq",
       "value": "adquirido_y_en_uso"}
    ]
  },
  "red_flags": [
    {
      "id": "activo_a_relacionada_sin_razon",
      "condicion": {
        "all_of": [
          {"field": "activo.proveedor_relacionado", "op": "eq",
           "value": true},
          {"field": "activo.razon_economica_documentada", "op": "eq",
           "value": false}
        ]
      },
      "accion": "block",
      "mensaje_educativo": "Adquisición a parte relacionada sin razón económica documentada puede caer bajo NGA arts. 4 ter/quáter CT."
    }
  ],
  "impacto": {
    "tipo": "deduccion_rli",
    "formula": "sum(activos_seleccionados.valor)"
  },
  "fundamento": [
    {"tipo": "ley", "articulo": "art. 31 N°5 bis LIR"},
    {"tipo": "oficio_sii", "id": "715/2025"}
  ]
}
```

### Domain `red_flag`
Banderas rojas globales del motor (skill 1).

```json
{
  "id": "donacion_a_relacionada",
  "severidad": "block",
  "condicion": {
    "all_of": [
      {"field": "donacion.entidad_receptora.relacionada_con_donante",
       "op": "eq", "value": true}
    ]
  },
  "mensaje": "No se permite donación a entidad relacionada con el donante.",
  "fundamento": "Ley Valdés y leyes complementarias; lista negra tax-compliance-guardrails.md."
}
```

### Domain `rli_formula`
Composición de la RLI del ejercicio. Permite agregar/quitar partidas
con vigencia (ej. eliminación PPUA AT 2025).

```json
{
  "componentes": [
    {"id": "ingresos_brutos", "signo": "+",
     "fundamento": "art. 29 LIR"},
    {"id": "costos_directos", "signo": "-",
     "fundamento": "art. 30 LIR"},
    {"id": "gastos_aceptados", "signo": "-",
     "fundamento": "art. 31 LIR"},
    {"id": "agregados_art_33", "signo": "+",
     "fundamento": "art. 33 N°1 LIR"},
    {"id": "perdidas_anteriores", "signo": "-",
     "fundamento": "art. 31 N°3 LIR (modif. Ley 21.713)"},
    {"id": "rebaja_14e", "signo": "-",
     "fundamento": "art. 14 E LIR"}
  ]
}
```

### Domain `credit_imputation_order`
Orden de imputación de créditos contra IDPC (puede cambiar con
reformas).

```json
{
  "orden": ["credito_ipe", "credito_sence", "credito_id",
            "credito_donaciones"]
}
```

### Domain `igc_table`
Tabla del Impuesto Global Complementario (alternativa a hacerlo en
`igc_brackets`; se mantiene `igc_brackets` por simplicidad
operacional, pero el formato declarativo es válido para casos
donde la estructura del impuesto cambie sustancialmente).

---

## Selector de regla vigente

Función única que el motor usa para resolver qué versión de regla
aplica a un cálculo. Vive en
`apps/api/src/domain/tax_engine/rule_resolver.py`.

```python
async def resolve_rule(domain: str, key: str,
                       tax_year: int) -> RuleSet:
    """
    Retorna el RuleSet publicado cuya vigencia incluye
    el ejercicio del tax_year dado.
    """
    target_date = date(tax_year, 12, 31)  # ejercicio comercial
    rule = await db.fetch_one("""
        SELECT * FROM tax_rules.rule_sets
        WHERE domain = :d
          AND key = :k
          AND status = 'published'
          AND vigencia_desde <= :t
          AND (vigencia_hasta IS NULL OR vigencia_hasta >= :t)
        ORDER BY vigencia_desde DESC, version DESC
        LIMIT 1
    """, {"d": domain, "k": key, "t": target_date})
    if not rule:
        raise MissingRuleError(domain, key, tax_year)
    return RuleSet.model_validate(rule)
```

Reglas:
- Si no hay regla publicada para ese año → `MissingRuleError`.
  Bloqueo total. Nada se calcula sin regla.
- Si hay solapamiento (raro), gana la de `vigencia_desde` más
  reciente; si empatan, la de `version` mayor. Esto facilita
  transiciones legislativas que se publican antes de la vigencia.

---

## Evaluador de reglas declarativas

Vive en `apps/api/src/domain/tax_engine/rule_evaluator.py`. Recibe
un objeto de contexto y una regla; retorna resultado + razones
citando fundamento.

```python
@dataclass
class EvaluationResult:
    passed: bool
    failed_clauses: list[FailedClause]  # con field, op, value, message, fundamento

def evaluate(rule: dict, ctx: dict) -> EvaluationResult: ...
```

Operadores y combinadores soportados son los listados arriba. El
evaluador NO puede ejecutar código arbitrario (sin `eval`, sin
expresiones lambda); solo el set finito de operadores. Esto lo
hace seguro contra inyección y testeable.

---

## Snapshot inmutable de cálculos

Toda tabla con cálculo persistido (`rli_calculations`,
`escenarios_simulacion`, `recomendaciones`, registros tributarios
calculados, alertas accionables que dependen de una regla) lleva:

| col | tipo | propósito |
|---|---|---|
| engine_version | text | hash + tag del motor (ej. `v0.4.2-a1b2c3d`) |
| rule_set_snapshot | jsonb | dump de las reglas y parámetros aplicados |
| tax_year_params_snapshot | jsonb | tasas, tramos, topes usados |
| computed_at | timestamptz | |

Esto permite:
- Reproducir exactamente un cálculo ejecutado meses atrás.
- Explicar al SII (o al usuario) qué reglas usamos en una
  recomendación pasada.
- Auditar diferencias entre versiones de motor.

**Nunca se sobrescribe un cálculo existente.** Si el usuario quiere
"actualizar" un escenario antiguo a reglas vigentes hoy:
1. Sistema crea un cálculo nuevo con `engine_version` actual.
2. El cálculo viejo queda como histórico.
3. UI muestra ambos lado a lado, con badge "Cálculo histórico
   vs. cálculo con reglas vigentes a hoy".

---

## CI: protección contra hardcoding

Test automático que escanea `apps/api/src/domain/tax_engine/` y
rechaza PRs con números mágicos que deberían vivir en
`tax_year_params` o reglas. Vive en `tests/test_no_hardcoded.py` y
es bloqueante.

```python
# tests/test_no_hardcoded.py
import re
from pathlib import Path

# Patrones que NO deben aparecer en código del motor.
FORBIDDEN = [
    (r"0\.27\b", "tasa IDPC 14 A"),
    (r"0\.125\b", "tasa transitoria 14 D N°3"),
    (r"0\.25\b", "tasa 14 D N°3 permanente"),
    (r"0\.19\b", "tasa IVA"),
    (r"0\.1525\b", "retención BHE 2026"),
    (r"\b75[._]?000\b", "tope ingresos 14 D"),
    (r"\b85[._]?000\b", "tope capital / año individual 14 D"),
    (r"\b5[._]?000\b", "tope rebaja 14 E"),
    (r"\b13[._]?5\b", "primer tramo IGC en UTA"),
]

EXEMPT_FILES = {
    # archivos donde sí pueden aparecer (tests golden, seeds).
    "tests/golden/",
    "supabase/seeds/",
}

def test_no_hardcoded_tax_values():
    src = Path("apps/api/src/domain/tax_engine")
    violations = []
    for f in src.rglob("*.py"):
        if any(s in str(f) for s in EXEMPT_FILES):
            continue
        text = f.read_text(encoding="utf-8")
        for pattern, descripcion in FORBIDDEN:
            for m in re.finditer(pattern, text):
                line = text[:m.start()].count("\n") + 1
                violations.append(
                    f"{f}:{line}  {descripcion}  patrón={pattern}"
                )
    assert not violations, "\n".join(violations)
```

Si el test detecta un falso positivo legítimo (ej. constante de
unidad, no de tasa), se documenta con comentario `# noqa: tax-magic-number  motivo`
y se ajusta el regex.

---

## Validación de reglas en CI

Tests automáticos que ejecutan al subir una nueva regla:

1. **Schema válido:** `rules` valida contra el JSON Schema del
   dominio.
2. **Fuente legal presente:** `fuente_legal` no vacío.
3. **Vigencia coherente:** `vigencia_desde < vigencia_hasta` cuando
   hay hasta.
4. **Sin huecos en el continuo:** para un (`domain`, `key`) dado,
   las vigencias publicadas no dejan años sin cobertura entre la
   regla más antigua y `now()`.
5. **Casos golden pasan:** cada regla publicada tiene mínimo 3
   casos golden (tabla `rule_golden_cases`) que el motor evalúa al
   pasar a `published`. Si un golden falla, no se publica.

---

## Panel admin (`/admin/rules`)

Frontend interno (no expuesto a usuarios finales). Funciones:

1. **Listar reglas** filtradas por dominio, estado, vigencia.
2. **Editar borrador** con formulario que valida JSON Schema en vivo.
3. **Dry-run de impacto:** ejecutar la regla nueva contra una
   muestra de datos productivos y mostrar:
   - Cuántas empresas cambiarían de elegibilidad de régimen.
   - Cuántos escenarios simulados cambiarían su `es_recomendado`.
   - Cuántas alertas se gatillarían o desaparecerían.
4. **Submit for approval:** marca la regla como `pending_approval`
   y notifica al contador socio.
5. **Approval workflow:**
   - Contador socio revisa, comenta, aprueba o rechaza.
   - Una vez aprobado, admin técnico hace publish (doble firma).
6. **Diff visual** entre versiones de la misma regla.
7. **Vista de impacto histórico:** "esta regla afectó N cálculos
   desde su publicación".
8. **Toda acción registrada** en `rule_set_changelog` y
   `audit_log`.

Acceso restringido al rol `internal_tax_admin` (definido en
`auth.users.app_metadata`). RLS bloquea el resto.

---

## legal-dependencies.yaml — mantenido por contador socio

Archivo en `apps/api/legal-dependencies.yaml` actualizado por el
contador cuando crea o modifica reglas. Permite trazabilidad inversa
desde una ley o circular hacia las reglas afectadas.

```yaml
- rule_set:
    domain: regime_eligibility
    key: 14_d_3
  depends_on:
    - { tipo: ley, id: "21.210" }
    - { tipo: ley, id: "21.713" }
    - { tipo: circular_sii, id: "62/2020" }

- rule_set:
    domain: idpc_rate
    key: 14_d_3_at2026
  depends_on:
    - { tipo: ley, id: "21.755" }
    - { tipo: circular_sii, id: "53/2025" }
    - { tipo: ley, id: "21.735", articulo: "art. 4° transitorio" }
```

Job semanal cruza este archivo con un seguimiento de novedades
legales y produce un reporte: "Esta semana publicaron Circular SII
N° X. Reglas potencialmente afectadas: [...]". El contador revisa.

---

## Watchdog legislativo (fase 5+)

Job semanal monitorea fuentes oficiales y notifica al contador
socio. NO actualiza nada automáticamente.

Fuentes:
- BCN (https://www.bcn.cl) — leyes promulgadas y proyectos relevantes.
- SII normativa (https://www.sii.cl/normativa_legislacion/) —
  circulares, resoluciones, oficios.
- Diario Oficial — sección "Ley".
- Tribunales Tributarios y Aduaneros — jurisprudencia destacada.
- Senado y Cámara — proyectos en trámite con materia tributaria.

Implementación:
- Worker Celery `watchdog_legal_weekly`.
- Almacena últimos hashes de páginas vigiladas para detectar
  cambios.
- Dispara email al contador socio + entrada en `legal_alerts`.
- Tablero interno `/admin/legal-alerts` con triage (relevante /
  no relevante / requiere acción).

Importante: el watchdog NO toca reglas. Es una alerta humana, no
un automatismo.

---

## Feature flags por tax_year

Para situaciones condicionales (ej. condicionalidad rebaja IDPC
12,5% AT 2026-2028 con cumplimiento de cotización empleador Ley
21.735), usar feature flags en tabla:

| col | tipo | notas |
|---|---|---|
| flag_key | text | `idpc_14d3_at2026_transitoria` |
| value | text | `transitoria_12_5` o `permanente_25` |
| effective_from | date | |
| reason | text | razón del último cambio |
| changed_by | uuid FK auth.users | |
| changed_at | timestamptz | |

El motor consulta el flag al resolver tasa para ese año. Si la
realidad legislativa cambia, el contador edita el flag desde panel
admin con auditoría completa. Cero código nuevo.

Para el simulador, la regla práctica es **mostrar siempre los dos
escenarios** (base y revertido) cuando un flag tiene impacto
material. El usuario decide cuál cree probable.

---

## Casos típicos de cambio y cómo se manejan

### Caso 1: tasa IDPC sube de 12,5% a 15% para AT 2027
**Acción:**
1. Contador socio edita `idpc_rates` insertando fila para AT 2027
   con tasa 0,15.
2. Si la rebaja se reverta antes, también ajusta flag
   `idpc_14d3_at2027_transitoria`.
3. Doble firma + publicación.

**Código tocado:** cero.

### Caso 2: aparece nuevo crédito tributario "Crédito Verde"
**Acción:**
1. Contador socio define la regla del crédito como
   `credit_definition` (nuevo dominio si no existe; si no, agregar
   al catálogo).
2. Actualiza `credit_imputation_order` para definir dónde se imputa.
3. Si el crédito requiere campo nuevo en datos del usuario (ej.
   "tiene certificación verde"), se agrega como migración de DB.
4. Casos golden, dry-run, doble firma.

**Código tocado:** mínimo (agregar el campo al input y al snapshot).

### Caso 3: derogación de PPUA (ya ocurrió AT 2025)
**Acción:**
1. Regla `ppua_calculation` con `vigencia_hasta = '2024-12-31'`.
2. Función del motor que invocaba PPUA retorna 0 con warning para
   `tax_year >= 2025`.
3. Tests golden de años anteriores siguen pasando con regla vieja.

**Código tocado:** mínimo (solo el warning).

### Caso 4: nace un régimen tributario nuevo (hipotético)
**Acción:**
1. Catálogo de regímenes recibe nueva entrada.
2. Reglas en `regime_eligibility` para el nuevo régimen.
3. Si tiene IDPC propio, agregar a `idpc_rates`.
4. Si tiene registros propios distintos (no usa SAC/RAI/REX),
   evaluar si requiere migración de DB.
5. UI del wizard de diagnóstico (skill 7) lo lista
   automáticamente porque lee del catálogo.
6. Casos golden por contador.

**Código tocado:** menor en el motor; sí puede requerir cambios en
UI si el régimen cambia el flujo de información.

### Caso 5: cambia la fórmula de cálculo de RLI por reforma
**Acción:**
1. Nueva versión de regla en `rli_formula` con nuevos componentes.
2. `vigencia_desde` = primer ejercicio afectado.
3. Casos golden actualizados.

**Código tocado:** cero, si los componentes nuevos ya existen como
campos. Si la reforma introduce un concepto totalmente nuevo
(rarísimo), agregar el campo.

---

## Anti-patrones (NO hacer)

- ❌ Hardcodear cualquier tasa o tope en código del motor.
- ❌ `if tax_year == 2026` en lugar de selector por vigencia.
- ❌ Modificar una regla publicada in-place. Siempre nueva versión.
- ❌ Sobrescribir un cálculo histórico con resultado nuevo.
- ❌ Saltarse el doble firma en producción.
- ❌ Cargar reglas vía SQL ad-hoc sin pasar por panel admin.
- ❌ Confiar en watchdog automatizado para actualizar reglas. El
  watchdog notifica; el contador decide.
- ❌ Permitir reglas sin `fuente_legal`.
- ❌ Permitir publicación sin casos golden.

---

## Casos golden de la propia infraestructura

Sí, esta skill también requiere casos golden — pero del sistema, no
tributarios:

1. `test_resolve_rule_returns_correct_version_for_year`: dada
   `regime_eligibility/14_d_3` con dos versiones (vigencia 2024-2026
   y vigencia 2027+), pedir AT 2025 retorna v1; pedir AT 2027
   retorna v2.
2. `test_resolve_rule_raises_on_missing`: dada una key sin reglas
   publicadas, falla con `MissingRuleError`.
3. `test_evaluator_blocks_arbitrary_code`: una regla con
   operadores no soportados se rechaza al validar schema.
4. `test_no_hardcoded_passes_clean_repo`: con un repo limpio, el
   linter de hardcoding pasa.
5. `test_no_hardcoded_fails_when_planted`: plantar un `0.125` en
   código del motor → CI falla.
6. `test_snapshot_immutability`: modificar `rule_set_snapshot` de
   un cálculo persistido falla por trigger Postgres.
7. `test_double_signature_required`: publicar regla sin firma de
   contador o sin firma de admin falla.

---

## TODO(contador)

- Definir lista inicial de dominios necesarios al go-live (al
  menos: `regime_eligibility`, `palanca_definition`, `red_flag`,
  `rli_formula`, `credit_imputation_order`).
- Cargar primera versión de reglas para AT 2024-2028 con
  fundamento legal completo.
- Crear primer set de casos golden por dominio (mínimo 3 por
  regla).
- Mantener `legal-dependencies.yaml` con las dependencias iniciales.
- Definir frecuencia mínima de revisión del watchdog
  (recomendado: revisión semanal del email; triage en 48 horas).

## TODO(técnico)

- Implementar JSON Schema por dominio en
  `apps/api/src/domain/tax_engine/rule_schemas/`.
- Implementar `rule_resolver.py` y `rule_evaluator.py` con tests.
- Implementar trigger Postgres que bloquea UPDATE/DELETE en
  campos snapshot de tablas de cálculo.
- Implementar panel `/admin/rules` con dry-run y workflow de doble
  firma.
- CI con tests `test_no_hardcoded` y validación de reglas
  publicadas.
- Worker `watchdog_legal_weekly` y tablero de triage.
