# Optimizador — Gasto asociado al giro (art. 31 LIR)

> **Estado:** RESEARCH + DISEÑO (sandbox pre-firma). NO es asesoría
> tributaria ni está activo en el motor. Antes de exponerse como
> recomendación requiere: (a) alta en `recomendacion_whitelist`, (b)
> parámetros firmados en `tax_params`/`tax_rules`, y (c) validación del
> **CONTADOR_SOCIO** (skills 1, 3, 11). Las secciones marcadas
> `TODO(contador)` no tienen fundamento verificado y no se mergean como
> lógica del motor hasta cerrarse.
>
> **Research:** 1a ronda 2026-07-13 · **2a ronda (cierre de gaps)
> 2026-07-13**, verificada contra texto consolidado de BCN/Ley Chile y
> circulares SII. Marco vigente a jul-2026.

---

## 0. TL;DR

El art. 31 LIR (reformado por la **Ley 21.210**, sistematizado en la
**Circular SII N°53 de 2020**) amplió el concepto de "gasto necesario":
ya no exige que el gasto sea *inevitable u obligatorio*, sino que tenga
**aptitud de generar renta** (en el mismo o futuros ejercicios) y esté
**asociado al interés, desarrollo o mantención del giro**. Muchas PYMEs
**sub-deducen** gastos legítimos de su giro (no los registran o no los
documentan) y pagan IDPC de más.

El optimizador de Renteo ataca esa brecha **por el lado lícito**: ayuda al
contribuyente a *reconocer y documentar* gastos reales de su giro a los que
tiene derecho. La línea roja —que define todo el diseño del agente— es no
cruzar a **inflar/inventar gastos, gasto sin nexo con el giro, o gasto
irracional solo para pagar menos**, que caen en gasto rechazado (art. 21
LIR) o elusión/evasión (NGA, arts. 4 bis/ter/quáter CT).

**Lo que cerró la 2a ronda de research** (detalle en §1.4–§1.8):

| Gap | Resultado |
| --- | --- |
| Base caja 14 D N°3 | ✅ **Verificado** (Circular SII N°62/2020). Habilita la palanca de *timing*. |
| Límites especiales art. 31 | ✅ **Verificados** contra texto consolidado BCN. Ver §1.6. |
| Umbral 5 UTA supermercados | ❌ **DEROGADO** por la Ley 21.210. Era la hipótesis de la 1a ronda: es **derecho derogado**. |
| Catálogo SII por rubro | ❌ **No existe.** El SII resuelve **caso a caso**. §5 se reencuadra. |
| Art. 100 bis CT | ⚠️ **Corregido.** Sustituido por Ley 21.713 **y** Ley 21.755. La multa al asesor ya no es un %, son **100–250 UTA**. |
| Ley 21.713 y art. 31 | ✅ **No lo modificó.** AT 2025-2026 se rigen por el texto de la Ley 21.210. |

---

## 1. Fundamento legal (verificado con fuentes primarias)

### 1.1 El nuevo concepto de gasto necesario (post Ley 21.210)

El art. 31 inc. 1° LIR define hoy los gastos necesarios como **"aquellos
que tengan aptitud de generar renta, en el mismo o futuros ejercicios y se
encuentren asociados al interés, desarrollo o mantención del giro del
negocio"**. Es un criterio de **aptitud/propósito, no de resultado**: son
deducibles desembolsos "aptos o con la potencialidad de generar rentas…
aunque en definitiva no se generen" — incluidos gastos **voluntarios**, de
riesgo propio del negocio, de fidelización de clientes, profundización de
mercado y **exploración de proyectos aunque fracasen**. La Circular SII
N°53 declara que el requisito de *inevitabilidad u obligatoriedad* que el
SII exigía antes "debiera quedar sin efecto".

*Fundamento:* art. 31 inc. 1° LIR; **Circular SII N°53 de 2020**
(10-ago-2020). Vigente en 2026 (la Ley 21.713/2024 no lo revirtió — §1.8).

### 1.2 Requisitos copulativos de aceptación

Para ser deducible, el gasto debe cumplir **todos**:
1. **Aptitud + nexo con el giro** (§1.1).
2. **No ser costo** ya rebajado por art. 30 (sin doble deducción).
3. **Pagado o adeudado** en el ejercicio comercial correspondiente — **no
   se aceptan provisiones ni estimaciones**. (En 14 D N°3 la regla es más
   estricta: solo **pagado**. Ver §1.7.)
4. **Acreditación fehaciente** ante el SII (recoge el art. 21 del Código
   Tributario: la **carga de la prueba es del contribuyente**), con reglas
   especiales para gastos en el extranjero (§1.6.3).

*Fundamento:* art. 31 inc. 1° LIR; Circular SII N°53 §§1.3–1.4; art. 21 CT.

### 1.3 Gasto rechazado y el impuesto único de 40% (matiz clave)

Un gasto rechazado **NO siempre** paga el IU de 40% del art. 21 inc. 1°
LIR. Ese IU aplica **solo** cuando la partida beneficia **directa o
indirectamente a relacionados o propietarios**, o cuando el contribuyente
**no acredita** la naturaleza y efectividad del desembolso. En los demás
casos el gasto rechazado **solo se agrega a la RLI** (letra g del N°1 art.
33) y tributa con IDPC a tasa general. Si el beneficio es atribuible a un
propietario contribuyente de impuesto final, aplica el art. 21 inc. 3°
(IGC/IA + 10% de recargo a nivel del dueño) en lugar del IU de empresa.

> Implicancia de producto: el agente no debe asustar con "40%" en todos los
> casos, pero **sí** debe marcar el riesgo alto cuando el gasto huele a
> beneficio a relacionados/propietario o a falta de respaldo.

*Fundamento:* art. 21 inc. 1° lit. i) y inc. 3° LIR; Circular SII N°53
(línea 568); Instructivo SII Línea 62 AT2023 (tasa IU 40%).

### 1.4 La frontera lícita: economía de opción, NGA y art. 100 bis ✅ *(corregido en 2a ronda)*

El **art. 4 ter CT** declara **expresamente legítima** "la razonable
opción de conductas y alternativas contempladas en la legislación
tributaria": obtener el mismo resultado por un acto de menor carga **no es
abuso por sí solo** si los efectos derivan de la ley tributaria. Solo hay
elusión ante **abuso de las formas jurídicas** o **simulación**. Para
deducciones, el **primer filtro es el art. 31** (¿es gasto del giro,
acreditado?); la NGA es un backstop general.

> ⚠️ **Corrección de fuente (importante y transversal al repo).** La
> **Circular SII N°65 de 2015** —que este doc y varias seeds del motor
> citan como fundamento de la NGA— fue **dejada sin efecto** por la
> **Circular SII N°31 de 2025** (17-abr-2025), que instruye la NGA post
> Leyes 21.713 y 21.716. Toda cita a la 65/2015 debe migrar a la 31/2025.
> Ver §8.

**Art. 100 bis CT — formulación VIGENTE.** La versión que la 1a ronda
manejaba ("multa de hasta el 100% de los impuestos eludidos, tope 100 UTA")
es **texto derogado**: rigió hasta el 31-oct-2024. El artículo fue
**sustituido íntegramente** por la **Ley 21.713** (art. 1 N°38) y sus
incisos 5° y 6° **sustituidos de nuevo** por la **Ley 21.755**
(D.O. 11-jul-2025). El texto vigente sanciona así:

| Sujeto | Multa | Tope |
| --- | --- | --- |
| **Asesor** que diseñó o planificó (regla general) | **100 UTA fijas** (no es un %) | 100 UTA |
| Asesor, con **reiteración** del mismo diseño | 250 UTA | 250 UTA |
| Asesor, si **honorarios pactados > 100 UTA** | hasta el total de los honorarios | **250 UTA** |
| **Contribuyente** (solo si no hay tercero diseñador, o si no lo identifica en la fiscalización) | 100% de las diferencias de impuesto | **250 UTA** |
| Contribuyente acogido al **art. 14 letra D** | **exento** | — |

Además: **responsabilidad solidaria** de directores, representantes y
administradores (estándar Ley 20.393) si infringieron sus deberes de
dirección y supervisión. La multa la impone el **Tribunal Tributario y
Aduanero** en el procedimiento del **art. 160 bis** —no el SII por vía
administrativa—, y debe pedirse junto con el requerimiento de declaración
de abuso o simulación. La acción de cobro de Tesorería prescribe en **3
años** desde sentencia firme; la ventana para requerir es de **6 años**
(art. 4 bis inc. final CT).

> 🔴 **Implicancia crítica para Renteo (escalar a ESTUDIO_JURIDICO).** La
> exención del 14 letra D **protege al contribuyente, no al asesor**.
> Renteo, al sugerir estructuras de gasto, actúa funcionalmente como
> **diseñador/planificador**: su exposición es de **100 a 250 UTA** y **no
> se atenúa** porque el cliente sea una PYME 14 D. Peor: la ley crea un
> **incentivo legal a que el contribuyente identifique a su asesor**
> (si no lo hace, la multa recae sobre él). Esto es, por sí solo,
> justificación suficiente de los guardrails de §3.4 — no son burocracia
> interna, son la mitigación del riesgo sancionatorio propio.
>
> Matiz que juega a favor: la Circular 31/2025 §6.3 precisa que lo
> sancionado es **la actividad intelectual del diseño**, y que "la mera
> implementación de lo diseñado o planificado no cumple con los
> presupuestos de hecho" de la norma. Un motor que solo **reconoce y
> documenta gastos que el contribuyente ya incurre** (§2) está lejos del
> tipo; uno que **propone estructuras** se acerca. El diseño de este
> optimizador debe mantenerse deliberadamente del primer lado.

**No confundir:** la fórmula **"100% al 300% del impuesto defraudado"**
pertenece al **art. 97 N°4 CT** (delito de defraudación, con pena de
presidio; la Ley 21.713 subió el mínimo de 50% a 100%). Es un **delito**,
no la sanción del 100 bis, que es infraccional y sin pena corporal.

*Fundamento:* arts. 4 bis/ter/quáter y **100 bis** CT (texto consolidado
BCN, versión 11-jul-2025); Ley 21.713 art. 1 N°38; Ley 21.755 art. 2 N°2;
**Circular SII N°31 de 2025**; art. 97 N°4 CT.

*Vigencia:* incisos 1° a 4° del 100 bis rigen desde el **1-nov-2024** y
solo respecto de **actos o negocios celebrados después de esa fecha**
(Circular 31/2025 cap. III); incisos 5° y 6°, desde el 11-jul-2025.

### 1.5 Respaldo documental e IVA (condición transversal)

La aceptación del gasto en renta y el **crédito fiscal IVA** (art. 23 DL
825) comparten raíz: el crédito procede por operaciones **relacionadas con
el giro** y respaldadas en **facturas fidedignas**; facturas no fidedignas
o falsas **no dan crédito** (art. 23 N°5), con *safe-harbors* de pago
bancarizado (cheque nominativo / transferencia con RUT). Es decir: **sin
documento fehaciente + nexo con el giro, ni gasto en renta ni crédito
IVA.**

*Fundamento:* art. 23 N°1 y N°5 DL 825; FAQ SII crédito fiscal.

### 1.6 Límites y reglas especiales del art. 31 ✅ *(verificado en 2a ronda)*

Verificado contra el **texto consolidado del DL 824 en BCN/Ley Chile**
(idNorma 6368). Dato estructural: el bloque del art. 31 lleva
`fechaVersion="2020-02-24"` y **ningún** sub-bloque posterior → su última
modificación es la Ley 21.210 (ver §1.8).

#### 1.6.1 Automóviles, station wagons y similares — regla **cualitativa**, sin tope numérico

**No se deducen** la adquisición ni el arrendamiento de automóviles,
station wagons y similares, **"cuando no sea éste el giro habitual"**, ni
combustible, lubricantes, reparaciones, seguros y "en general, todos los
gastos para su mantención y funcionamiento".

Dos vías de excepción, y solo dos:
- **(a)** que el **giro habitual** del contribuyente sea la adquisición y/o
  arrendamiento de automóviles; o
- **(b)** que el **Director del SII**, **"mediante resolución fundada"**, lo
  establezca por cumplirse los requisitos del inciso primero.

> 🪤 **Trampa que el motor debe bloquear:** la Circular 53/2020 aclara que la
> prohibición **incluye expresamente los vehículos adquiridos o recibidos
> mediante contrato de leasing** (financiero y operativo). "Ponerlo en
> leasing" **no** convierte el auto en gasto deducible. Es el error más
> probable que un usuario PYME intentará.
>
> Nota de fórmula: la excepción vigente es **"mediante resolución
> fundada"**. La versión antigua ("el Director los califique previamente de
> necesarios, **a su juicio exclusivo**") fue reemplazada por la Ley 21.210
> — si una fuente la usa, está desactualizada.

*Fundamento:* art. 31 inc. 1° LIR; Circular SII N°53/2020.

#### 1.6.2 Supermercados y comercios similares — ❌ el umbral de 5 UTA está **DEROGADO**

La regla especial que permitía deducir gastos en supermercados hasta **5
UTA anuales por ejercicio**, e informar al SII (monto + nombre y RUT de
proveedores) por sobre ese monto, fue introducida por la **Ley 20.780** y
**eliminada por la Ley 21.210**. Hoy:

- El texto vigente del art. 31 **no contiene** la palabra "supermercado":
  el inciso primero pasa de los bienes no destinados al giro directo a los
  automóviles, sin párrafo intermedio.
- Las compras en supermercados quedan sujetas **solo a los requisitos
  generales del inciso primero** → se analiza **caso a caso** si son gasto
  del giro.
- La **obligación de informar al SII** (Res. Ex. SII N°123 de 2015) **dejó
  de aplicar** respecto de operaciones realizadas **desde el 1-ene-2020**.

> 🔴 **Consecuencia de diseño.** La hipótesis de la 1a ronda ("¿5 UTA/mes?
> ¿15 UTA/año?") era **derecho derogado**. Un optimizador que sugiriera
> "mantente bajo 5 UTA para no tener que informar al SII" estaría dando una
> recomendación **basada en una norma que ya no existe** — y además
> enseñando a fraccionar, que es exactamente la conducta que los guardrails
> deben impedir. **No se parametriza ningún umbral de supermercados.**
> Verificado: ese umbral **no está seedeado** en el motor hoy.
>
> Por qué la 1a ronda se equivocó: la Circular 53/2020 §2.4 describe el
> régimen antiguo **en pretérito** (nota al pie 8: "La Ley N° 20.780 *había
> incorporado*… prescribiendo que *podían* deducirse…") **para declararlo
> eliminado**. Leída fuera de contexto, esa nota parece la regla vigente.
> Medio internet la sigue replicando así.

*Fundamento:* art. 31 LIR (texto consolidado, sin regla de supermercados);
**Circular SII N°53/2020 §2.4** y sus notas al pie 8 y 9.

#### 1.6.3 Gastos incurridos en el extranjero — acreditación especial

Se acreditan con los **documentos emitidos en el exterior** conforme a la
ley del país respectivo, y en ellos debe constar **al menos**: (i)
individualización y domicilio del prestador/vendedor, (ii) naturaleza u
objeto de la operación, (iii) monto, y (iv) fecha.

- El SII puede exigir **traducción al castellano**. La Circular 53/2020
  (nota 6) precisa que **basta una traducción libre**: no se requiere
  traductor oficial. *(Dato operativo: el motor no debe exigirlo.)*
- **Sin documento de respaldo el gasto NO se pierde automáticamente**: la
  Dirección Regional **puede aceptarlo** si, a su juicio, es "razonable y
  necesario para la operación", comparando con contribuyentes de la misma
  actividad. Es una válvula discrecional, no un derecho → el motor la
  marca 🟡, nunca la promete.

*Fundamento:* art. 31 inc. 2° LIR; Circular SII N°53/2020.

#### 1.6.4 Partes relacionadas — **cuatro** reglas restrictivas dentro del art. 31

Contra lo que asumía la 1a ronda, el art. 31 **sí** tiene reglas propias de
relacionados, y todas **limitan** la deducción:

1. **Inc. 3° — cantidades del art. 59 pagadas a relacionadas** (en los
   términos del art. 41 E): se deducen **solo en el año de su pago, abono
   en cuenta o puesta a disposición** (criterio de caja, no devengo), y
   **se exige haber declarado y pagado el Impuesto Adicional**, salvo
   exención legal o convenio de doble tributación.
2. **Inciso final — transacciones y cláusulas penales:** "constituyen gasto
   los desembolsos acordados **entre partes no relacionadas** que tengan
   como causa el cumplimiento de una transacción, judicial o extrajudicial,
   o el cumplimiento de una cláusula penal". *A contrario sensu*: entre
   **relacionados, NO son gasto**. 🪤 Regla silenciosa y fácil de pisar.
3. **N°4 — créditos incobrables:** la regla del párrafo segundo **no aplica**
   a créditos entre empresas relacionadas (art. 8 N°17 CT), salvo sociedades
   de apoyo al giro.
4. **N°12 — pagos al exterior del art. 59 inc. 1°:** deducibles **hasta un
   máximo del 4% de los ingresos por ventas o servicios del giro** del
   ejercicio. Ese tope **no aplica** si no hay relación (requiere
   **declaración jurada** dentro de los 2 meses siguientes al cierre; la DJ
   falsa maliciosa se sanciona por art. 97 N°4 CT), ni si en el país del
   beneficiario la renta se grava con tasa **≥ 30%**.

El resto del tratamiento vive fuera del art. 31: gastos rechazados y
retiros presuntos en **art. 21**; precios de transferencia en **art. 41 E**
(sustituido por Ley 21.713 → Circular SII N°10 de 2025); rentas pasivas y
regímenes preferenciales en **arts. 41 G / 41 H** (Circular SII N°11 de
2025).

*Fundamento:* art. 31 incs. 3° y final, y N°4 y N°12 LIR; Circular SII
N°53/2020 (nota 7: aplica la norma de relación del art. 21 inc. final).

#### 1.6.5 Donaciones (art. 31 N°7) — **dos límites en cascada**

Las donaciones con fin de instrucción (básica, media, técnica, profesional
o universitaria) son deducibles **"sólo en cuanto no excedan del 2% de la
renta líquida imponible de la empresa o del 1,6‰ del capital propio de la
empresa al término del correspondiente ejercicio"**. No requieren
insinuación y están exentas de todo impuesto.

Precisiones que el motor **no puede colapsar en una sola regla**:
- El tope del N°7 es **alternativo** (2% RLI **o** 1,6‰ capital propio), no
  acumulativo.
- La ley dice **"capital propio"**, *no* "capital propio tributario" — no
  sobre-especificar.
- **1,6 por mil (‰)**, no 1,6 por ciento.
- **Encima corre el Límite Global Absoluto (LGA)** del **art. 10 de la Ley
  19.885**: el conjunto de donaciones con beneficio tributario —y la norma
  **nombra expresamente al N°7 del art. 31**— tiene como tope el **5% de la
  RLI**. En **pérdida tributaria**, el LGA muta a **4,8‰ del capital propio
  tributario** o **1,6‰ del capital efectivo**.

→ Son **tres cifras en dos cuerpos legales distintos** (2%, 1,6‰, 5%).
Modelarlas como un solo tope sería un error. Conecta con
**TODO-CONTADOR #15** ("tope de donaciones globales combinado con otros
beneficios"), que queda con fundamento pero sigue requiriendo firma.

*Fundamento:* art. 31 N°7 LIR; **art. 10 Ley 19.885** (texto consolidado
BCN, versión 24-ago-2024).

### 1.7 Régimen 14 D N°3 Pro PyME — base caja ✅ *(verificado en 2a ronda)*

**Cerrado contra la Circular SII N°62 de 2020** ("Régimen Tributario
Propyme", D.O. 30-sep-2020), fuente primaria.

La base imponible del IDPC es **"la diferencia positiva entre la suma de
los ingresos percibidos (y devengados, cuando corresponde) menos la suma de
los gastos o egresos efectivamente pagados"**, ambos **sin reajuste**
(valor nominal). Consecuencias directas para el optimizador:

- **El gasto se reconoce cuando se PAGA**, no cuando se devenga. En 14 A
  (régimen general) sigue rigiendo *pagado o adeudado*.
- **Existencias e insumos**: los adquiridos y no enajenados/utilizados en el
  año se reconocen como gasto, **pero solo si están pagados** — "por cuanto,
  en el régimen Pro Pyme la determinación de la base imponible se basa en
  flujos de caja".
- **Activo fijo: depreciación instantánea e íntegra** en el mismo ejercicio
  de adquisición o fabricación, **condicionada a que esté efectivamente
  pagado**.

> 🎯 **Esto habilita la palanca de *timing* del optimizador**, y es lícita:
> en Pro PyME, **adelantar el pago de un gasto real del giro antes del
> 31-dic** lo traslada al ejercicio en curso. No se inventa gasto ni se
> altera su naturaleza: solo se ejerce la opción de flujo que la propia ley
> estructura como base caja. Es economía de opción (art. 4 ter CT) en
> sentido estricto.
>
> ⚠️ **Límite del guardrail:** la palanca solo es lícita si el gasto **es
> real, del giro y ya está decidido**. "Pagar por adelantado algo que no
> necesitas" o "prepagar a un relacionado" sale de la lista blanca. Y el
> pago debe ser **efectivo** (no una provisión ni un documento
> post-fechado): un pago simulado para adelantar la deducción es
> derechamente evasión.

`TODO(contador)`: confirmar el perímetro exacto de los **"devengados, cuando
corresponde"** (la Circular 62 los admite en ciertos casos, y hay indicios
—no verificados— de que las operaciones con **relacionados** siguen regla de
devengo). Hasta cerrarlo, el motor aplica base caja **solo** a gastos con
terceros no relacionados.

*Fundamento:* art. 14 D N°3 LIR; **Circular SII N°62 de 2020**; SII, "Tipos
de regímenes tributarios" (Modernización Tributaria).

### 1.8 Ley 21.713 (2024): **no modificó el art. 31** ✅ *(verificado — cierra el gap de AT 2025-2026)*

Ningún umbral, tope ni monto de deducción de gastos del art. 31 cambió por
la Ley 21.713. Tres pruebas independientes y convergentes:

1. **Texto de la Ley 21.713:** el articulado que modifica la LIR **no
   menciona el art. 31** ni una vez. Los artículos de la LIR efectivamente
   intervenidos son **10, 32, 41 E, 41 G y 41 H**.
2. **Versionado de BCN:** en el DL 824 consolidado, el bloque del art. 31
   conserva `fechaVersion="2020-02-24"` (fecha de la Ley 21.210). Si la Ley
   21.713 (D.O. 24-oct-2024) lo hubiera tocado, la fecha sería posterior.
3. **Circulares SII de la Ley 21.713 en materia de renta:** la **N°10 de
   2025** (art. 41 E) y la **N°11 de 2025** (arts. 10, 41 G, 41 H). **No
   existe circular de la Ley 21.713 sobre el art. 31.**

→ Para **AT 2025 y AT 2026**, la norma de gastos aplicable sigue siendo el
**art. 31 en su redacción de la Ley 21.210**, instruido por la **Circular
SII N°53 de 2020**. Esto se refleja en `tax_rules` como vigencia abierta
desde 2020, sin nueva versión por Ley 21.713.

> ⚠️ **Colisión de nombres a evitar en las citas:** "Circular 53" es
> ambigua. **Circular 53 de 2020** = gastos del art. 31 (esta). **Circular
> 53 de 2025** (03-sep-2025) = disminución transitoria de la tasa IDPC y de
> PPM para 14 D N°3 — otro tema (conecta con el escenario dual de tasa
> transitoria de la skill 7, y **no está verificada**). Citar **siempre con
> año**.

### Fuentes primarias

| Fuente | URL | Versión / nota |
| --- | --- | --- |
| **LIR (DL 824) consolidado** — art. 31 | `bcn.cl/leychile/navegar?idNorma=6368` | Norma v. 2026-03-27; **bloque art. 31 v. 2020-02-24** |
| **Circular SII N°53 de 2020** (gastos art. 31) | `sii.cl/normativa_legislacion/circulares/2020/circu53.pdf` | 10-ago-2020 |
| **Circular SII N°62 de 2020** (Pro PyME 14 D) | `sii.cl/normativa_legislacion/circulares/2020/circu62.pdf` | D.O. 30-sep-2020 |
| **Código Tributario (DL 830) consolidado** — art. 100 bis | `bcn.cl/leychile/navegar?idNorma=6374&idParte=9510279` | **v. 2025-07-11** |
| **Circular SII N°31 de 2025** (NGA; deja sin efecto la 65/2015) | `sii.cl/normativa_legislacion/circulares/2025/circu31.pdf` | 17-abr-2025 |
| **Ley 21.713** (art. 1 N°38 sustituye 100 bis) | `bcn.cl/leychile/navegar?idNorma=1207746` | D.O. 24-oct-2024 |
| **Ley 21.755** (art. 2 N°2 sustituye incs. 5°-6°) | `bcn.cl/leychile/navegar?idNorma=1214890` | D.O. 11-jul-2025 |
| **Ley 19.885** art. 10 (LGA donaciones) | `bcn.cl/leychile/navegar?idNorma=213294` | v. 2024-08-24 |
| Oficio SII (gasto necesario, caso a caso) | `sii.cl/normativa_legislacion/jurisprudencia_administrativa/ley_impuesto_renta/2017/ja2357.htm` | 2017 (pre-reforma; ver §5) |
| FAQ crédito fiscal IVA | `sii.cl/preguntas_frecuentes/impuestos_mensuales/001_130_0622.htm` | — |

> 🚩 **Dos PDF del propio SII están DESACTUALIZADOS y son trampas de
> fuente** (ambos rotulados "actualizado a la Ley 21.210", feb-2020):
> - `sii.cl/normativa_legislacion/codigo_tributario.pdf` → contiene el
>   **art. 100 bis derogado** ("hasta el 100%… tope 100 UTA"). **Es el
>   origen del error de la 1a ronda.**
> - `sii.cl/normativa_legislacion/leyimpuestoalarenta.pdf` → inocuo para el
>   art. 31 (no cambió), pero **no sirve** para arts. 14, 41 E, 41 G, 41 H.
>
> **Regla para el watchdog legislativo (skill 11): la fuente canónica es el
> XML consolidado de BCN**, que expone `fechaVersion` **por artículo** —
> eso da versionado temporal gratis y encaja directo con `tax_rules`. Los
> PDF del SII sirven para *interpretación* (circulares), no como texto legal
> vigente.

---

## 2. La tesis del optimizador

**El ángulo lícito (economía de opción ✅):** la PYME típica no lleva
contabilidad fina; incurre en gastos reales del giro (insumos, arriendo,
servicios, capacitación, publicidad, mantención) que **no factura a nombre
de la empresa, no documenta o no registra**. Renteo detecta esa
**sub-deducción** y guía a: (1) identificar categorías de gasto propias de
su giro que probablemente ya incurre, (2) exigir el documento correcto
(factura/boleta electrónica a RUT de la empresa, medio de pago
bancarizado), (3) reconocerlas en la RLI. Baja RLI → baja IDPC, usando la
ley como está pensada.

En Pro PyME (14 D N°3) se agrega una segunda palanca, también lícita: el
**timing de pago** de gastos reales ya decididos (§1.7).

**La línea roja (❌ y por qué el agente debe blindarse):**
- Sugerir **incurrir en un gasto nuevo solo para pagar menos** sin
  propósito de negocio real (gasto irracional).
- Gasto **sin nexo con el giro** o **personal disfrazado** de empresa.
- **Inflar montos** o documentar operaciones inexistentes → factura falsa
  (delito, art. 97 N°4 CT) + rechazo IVA + IU 40%.
- Gasto que beneficia a **relacionados/propietarios** sin sustancia.
- **Fraccionar** gastos para caer bajo un umbral (además, el umbral de
  supermercados que motivaba esta táctica **ya no existe** — §1.6.2).

El valor está en el primer grupo; el diseño existe para **impedir
estructuralmente** el segundo. Y, como establece §1.4, ese blindaje protege
**también a Renteo**: el art. 100 bis sanciona al diseñador con 100–250
UTA, sin la exención que ampara al cliente 14 D.

---

## 3. Cómo encaja en el flujo de Renteo

### 3.1 Como palanca nueva del simulador
Encaja como palanca del `scenario-simulator` (skill 8), en la familia de
las que **bajan RLI** (junto a P1 depreciación, P3 rebaja 14 E, P6 gasto
I+D). Propuesta de id: **`optimizacion_gastos_giro`** ("P13"). A diferencia
de las otras, no aplica un tope numérico único: aplica un **delta de RLI**
= suma de gastos deducibles adicionales que el usuario confirma que incurre
y documentará, cada uno con su categoría y su bandera de riesgo.

Sub-palanca opcional (solo 14 D N°3): **timing de pago** (§1.7) — mover al
ejercicio en curso el pago de un gasto real ya decidido. Requiere que el
motor conozca el régimen; en 14 A no se ofrece.

### 3.2 Alta en `recomendacion_whitelist` (skill 1) — spec
Nuevo item para la whitelist v-siguiente (mismo shape `{"items":[...]}`,
`key='global'`):
```json
{
  "id": "optimizacion_gastos_giro",
  "label": "Optimización de gastos necesarios del giro",
  "fundamento": "art. 31 LIR; Circular SII N°53 de 2020"
}
```
Publicar como **nueva versión** de la regla con doble firma
(CONTADOR_SOCIO + ADMIN_TECNICO), igual que el resto (ver
`docs/firma-contador-2026-05/06_whitelist_palancas_v2.sql`).

### 3.3 Modelo de datos (sin hardcode — skill 11)
Todo parámetro va a tablas, no a código:

- `tax_rules.rule_sets` dominio nuevo **`gasto_giro_catalogo`**: el catálogo
  por rubro (§5) como regla declarativa versionada, resuelto por
  `resolve_rule` según año. Cada entrada: `{giro_code, categoria,
  fundamento, riesgo, requiere_doc}`. **No es doctrina SII** (§5): es un
  *prior* interno firmado por el contador.
- `tax_rules.rule_sets` dominio **`gasto_giro_reglas_especiales`**: las
  reglas **cualitativas** de §1.6 como predicados declarativos (autos +
  leasing, relacionados, extranjero). No son números: son condiciones que
  disparan 🔴/🟡. Vigencia `[2020-01-01, )`.
- `tax_params.beneficios_topes` — los **topes numéricos reales** que el
  research sí encontró, por `tax_year` (`key, tax_year, valor, unidad,
  fuente_legal, descripcion`). Candidatos, **todos `TODO(contador)` para
  firma**:

  | key | valor | unidad | fuente_legal |
  | --- | --- | --- | --- |
  | `donaciones_art31n7_tope_rli_pct` | 2 | `pct` | art. 31 N°7 LIR |
  | `donaciones_art31n7_tope_capital_propio_permil` | 1,6 | `permil` | art. 31 N°7 LIR |
  | `donaciones_lga_tope_rli_pct` | 5 | `pct` | art. 10 Ley 19.885 |
  | `donaciones_lga_perdida_cpt_permil` | 4,8 | `permil` | art. 10 Ley 19.885 |
  | `donaciones_lga_perdida_capital_efectivo_permil` | 1,6 | `permil` | art. 10 Ley 19.885 |
  | `pagos_exterior_art31n12_tope_ingresos_pct` | 4 | `pct` | art. 31 N°12 LIR |
  | `pagos_exterior_art31n12_tasa_pais_exime_pct` | 30 | `pct` | art. 31 N°12 LIR |
  | `art100bis_multa_asesor_uta` | 100 | `uta` | art. 100 bis CT (v. 11-jul-2025) |
  | `art100bis_multa_asesor_tope_uta` | 250 | `uta` | art. 100 bis CT (v. 11-jul-2025) |
  | `art100bis_multa_contribuyente_tope_uta` | 250 | `uta` | art. 100 bis CT (v. 11-jul-2025) |

  ⚠️ Los tres últimos rigen desde **2024-11-01** (no desde el inicio del AT):
  el versionado temporal de `tax_rules` debe reflejar esa fecha, no el año
  tributario completo.

  ❌ **NO se parametriza ningún umbral de supermercados**: está derogado
  (§1.6.2). Si aparece en un seed, es un bug.

- `tax_data`: los gastos que el usuario declara/confirma (per-tenant, RLS),
  con su categoría, monto, estado de documentación y flag de riesgo.

### 3.4 Guardrails (skill 1) — banderas que el motor debe emitir

🔴 **block** (no se aplica; se explica el fundamento):
- Gasto marcado **personal** / **sin nexo con el giro**.
- **Automóvil / station wagon** y sus gastos de mantención y funcionamiento,
  cuando **no es el giro habitual** — **incluido el leasing** (§1.6.1). Solo
  se levanta con **resolución fundada del Director** acreditada por el
  usuario.
- **Transacción o cláusula penal con parte relacionada** (§1.6.4 regla 2):
  no es gasto, punto.
- Gasto a **relacionado sin sustancia**, o cualquier sugerencia de
  reorganización con motivo principal tributario.
- **Fraccionar** un gasto para caer bajo un umbral.

🟡 **warning** (se aplica condicionado, con derivación al contador):
- Gasto **sin documento tributario** aún → se aplica condicionado a
  documentación.
- **Gasto en el extranjero** (§1.6.3): exige los 4 datos mínimos del
  documento; la aceptación sin respaldo es **discrecional** de la Dirección
  Regional → nunca se promete.
- **Pagos al exterior del art. 59 inc. 1°** → tope 4% de ingresos si hay
  relación (§1.6.4 regla 4); exige DJ de no relación.
- **Donaciones** → doble límite en cascada (§1.6.5).
- **Compras en supermercado**: **no hay umbral**, pero la probabilidad de
  gasto personal es alta → se pide nexo explícito con el giro, **caso a
  caso**.
- **Timing de pago en 14 D N°3** (§1.7): solo si el gasto es real, del giro
  y ya decidido; el pago debe ser efectivo.
- Categoría de **riesgo alto** según el catálogo del rubro.

**Regla dura de copy:** el motor **nunca** dice "gasta X para pagar menos";
dice "si ya incurres en X para tu giro y lo documentas, es deducible".

---

## 4. El agente AI: cómo sugiere "el gasto adecuado" por giro

### 4.1 Entradas
- **Giro / código de actividad económica SII** de la empresa (define el
  rubro).
- **Régimen** (14 A vs 14 D N°3) — determina si aplica la sub-palanca de
  timing (§1.7) y el devengado vs caja.
- Señales opcionales: histórico de F29/F22, gastos ya registrados,
  tamaño/planilla — para estimar **qué categorías del rubro faltan**.
- **Catálogo por rubro** (§5) recuperado desde `gasto_giro_catalogo`.

### 4.2 Arquitectura (retrieval + Claude + tool-use, con guardrails)
1. **Retrieval determinista, no libre:** el agente **no inventa** gastos;
   parte del catálogo versionado del rubro (RAG sobre `gasto_giro_catalogo`,
   no del conocimiento paramétrico del modelo). Esto ancla las sugerencias a
   categorías pre-validadas por el contador.
2. **Razonamiento del modelo (Claude):** dado el giro + señales, prioriza
   qué categorías del catálogo probablemente el negocio incurre y **no está
   deduciendo**, y explica el nexo con el giro.
3. **Tool-use hacia el motor:** para cuantificar impacto llama al
   simulador real (`_apply_palancas`/`_carga`), nunca calcula impuestos por
   su cuenta.
4. **Guardrail post-generación:** cada sugerencia pasa por
   `is_recomendacion_whitelisted` + las banderas §3.4 antes de mostrarse.

### 4.3 Qué SÍ sugiere / qué NUNCA
- ✅ "Para una ferretería, el arriendo de bodega, los seguros de mercadería
  y la mantención de montacargas son gastos del giro; si los pagas y los
  facturas a la empresa, son deducibles (art. 31)."
- ✅ "Detectamos que pagas publicidad digital pero no la registras como
  gasto — pídela con factura a RUT de la empresa."
- ✅ (solo 14 D N°3) "Esta mantención que ya tienes comprometida para enero:
  si la pagas antes del 31-dic, se reconoce en este ejercicio."
- ❌ Nunca: montos objetivo, "gasta más para bajar impuestos", categorías
  sin nexo con el giro, mecanismos con relacionados, ni el auto de la
  empresa "vía leasing".

### 4.4 System prompt (borrador)
```
Eres el asistente de gastos del giro de Renteo (Chile). Tu objetivo es
ayudar a la PYME a RECONOCER y DOCUMENTAR gastos reales de su giro que
podría estar sub-deduciendo, dentro del art. 31 LIR (Circular SII 53/2020).

REGLAS DURAS (no negociables):
- Solo sugieres categorías presentes en el catálogo del rubro que se te
  entrega. No inventas categorías nuevas.
- Nunca sugieres incurrir en un gasto con el único fin de pagar menos
  impuestos, ni montos objetivo. El propósito debe ser del negocio.
- Todo gasto exige (a) nexo con el giro, (b) documento tributario a nombre
  de la empresa, (c) pago acreditable. Si falta alguno, lo marcas como
  pendiente, no como deducible.
- Automóviles y station wagons: sus gastos NO son deducibles si ese no es
  el giro habitual, y eso INCLUYE el leasing. No ofrezcas rodeos. La única
  excepción es una resolución fundada del Director del SII.
- No existe un umbral de gastos en supermercados: se evalúan caso a caso
  bajo la regla general. Nunca sugieras fraccionar un gasto ni "mantenerse
  bajo un tope".
- Marcas riesgo alto y derivas al contador cuando el gasto toque
  relacionados/propietarios, automóviles, gastos en el extranjero,
  donaciones o pagos al exterior.
- Solo si el régimen es 14 D N°3 puedes mencionar el timing de pago (base
  caja), y únicamente sobre gastos reales del giro YA decididos.
- Cada sugerencia cita art. 31 LIR + la fuente SII del catálogo, e incluye
  el disclaimer de simulación (skill 2). No es asesoría.
- Si el usuario pide inflar, inventar o "gastos truchos", te niegas y
  explicas el art. 21 LIR (gasto rechazado / IU 40%) y art. 97 N°4 CT.
```

### 4.5 Salida
Cada sugerencia = `{categoria, por_qué_del_giro, fundamento (art.+Circular),
documento_requerido, riesgo (bajo/medio/alto), impacto_estimado_RLI (vía
motor), disclaimer}`. El impacto agregado entra al comparador del simulador
como la palanca `optimizacion_gastos_giro`.

---

## 5. Catálogo de gastos por rubro — ✅ *pregunta resuelta*: **el SII NO publica catálogos por giro**

> **Resultado de la 2a ronda.** El SII **no** aplica catálogos de gastos
> deducibles por sector económico o rubro. La calificación del gasto se hace
> **caso a caso**: *"la necesidad del gasto implica determinar, **en cada
> caso concreto**, considerando las circunstancias particulares de la
> actividad"* (Oficio SII, jurisprudencia administrativa 2017). No existe
> una lista oficial por giro que Renteo pueda importar. **La pregunta queda
> cerrada: es caso a caso.**
>
> ⚠️ Matiz honesto: ese oficio es de **2017**, anterior a la Ley 21.210, y
> por tanto razona sobre el concepto **antiguo** de gasto necesario
> (inevitabilidad). Lo que sobrevive a la reforma es el **método**
> (evaluación caso a caso, requisitos copulativos); el **estándar** se
> flexibilizó a *aptitud de generar renta* (§1.1). La ausencia de catálogo
> SII es, además, un hecho negativo verificado: no se encontró ninguno.

**Consecuencia de diseño (importante).** El catálogo `gasto_giro_catalogo`
**se mantiene**, pero cambia de naturaleza:

- ❌ **No es** —ni se presenta al usuario como— una lista del SII. Nunca se
  cita como si tuviera respaldo normativo por rubro.
- ✅ **Es** un ***prior* interno de Renteo**: una heurística de *retrieval*
  que acota lo que el agente puede proponer (§4.2), firmada por el
  CONTADOR_SOCIO. Su función es **restrictiva** (impedir que el modelo
  invente categorías), no probatoria.
- El **fundamento** que se cita al usuario es siempre el **art. 31 inc. 1° +
  Circular 53/2020** (la regla general), más las reglas especiales de §1.6
  cuando apliquen. El rubro solo explica **por qué ese gasto tiene nexo con
  su giro** — que es exactamente el análisis caso a caso que la ley exige.
- Cada fila necesita el **nivel de riesgo firmado por el contador**. El
  "riesgo" es heurística de probabilidad de objeción del SII y carga de
  acreditación, **no doctrina SII**.

**Tabla ilustrativa (sigue `TODO(contador)` — riesgo sin firmar):**

| Rubro | Gastos típicos del giro (candidatos) | Riesgo* |
| --- | --- | --- |
| **Ferretería / retail** | Arriendo local/bodega, mercadería (costo), seguros de inventario, mantención de estanterías/montacargas, sistema POS, publicidad local, transporte de mercadería | Bajo |
| **Servicios profesionales** | Arriendo oficina, software/licencias, honorarios de subcontratistas (con BHE), capacitación técnica, membresías de colegios profesionales, equipos y su depreciación | Bajo–medio |
| **Gastronómico** | Insumos (costo), arriendo, gas/electricidad, uniformes, sanitización, mantención de cocina, delivery apps, música/ambientación | Medio (mermas y consumo propio: riesgo) |
| **E-commerce / logística** | Plataforma/hosting, comisiones de marketplace y pasarela de pago, packaging, courier, publicidad digital, almacenaje | Medio (publicidad digital extranjera → §1.6.3 y posible art. 31 N°12) |
| **Construcción** | Materiales (costo), arriendo de maquinaria, subcontratos, EPP, seguros de obra, combustible de faena, fletes | Medio (subcontratos y relacionados: acreditación) |
| **Transporte** | Combustible, mantención y repuestos, peajes, seguros, permisos de circulación, depreciación de vehículos comerciales | **Medio–alto** (§1.6.1: si el vehículo es "automóvil o station wagon" y no es el giro, se bloquea aunque sea leasing) |

\* Riesgo = probabilidad de objeción del SII / carga de acreditación.
**Heurística de diseño, no doctrina SII.**

---

## 6. Checklist de compliance antes de activar (gates)

- [ ] `optimizacion_gastos_giro` agregado a `recomendacion_whitelist` con
      doble firma.
- [ ] Catálogo `gasto_giro_catalogo` cargado en `tax_rules`, cada fila con
      su riesgo **firmado**, y **etiquetado como *prior* interno, no como
      lista SII** (§5).
- [ ] Reglas especiales `gasto_giro_reglas_especiales` (§1.6) implementadas
      como predicados declarativos versionados: autos **+ leasing**,
      relacionados (4 reglas), extranjero.
- [ ] Topes numéricos de §3.3 en `tax_params.beneficios_topes` por año,
      firmados — con la **vigencia 2024-11-01** correcta para los del art.
      100 bis.
- [ ] **Verificado que NO existe ningún umbral de supermercados** en seeds
      ni en código (está derogado — §1.6.2).
- [ ] Guardrails §3.4 implementados y con test (skill 1) + golden del
      contador.
- [ ] Disclaimer de simulación (skill 2) en cada output del agente.
- [ ] Banderas de relacionados / falta de documento / gasto personal /
      **auto en leasing** probadas.
- [ ] Copy legal revisado: la multa del art. 100 bis la impone el **TTA**
      (art. 160 bis), **no el SII** — cualquier texto que diga "multa
      aplicada por el SII" es incorrecto desde el 11-jul-2025.
- [ ] Revisión CONTADOR_SOCIO de la lógica y del prompt (PR toca motor →
      review obligatoria, CODEOWNERS).
- [ ] **ESTUDIO_JURIDICO**: evaluar la exposición propia de Renteo bajo el
      art. 100 bis como "diseñador/planificador" (§1.4) y su reflejo en los
      términos de servicio.

---

## 7. Estado de los gaps

### ✅ Cerrados en la 2a ronda (con fuente primaria)

| # | Gap | Cierre |
| --- | --- | --- |
| 1 | Límites especiales art. 31 (autos, supermercados, extranjero, relacionados, donaciones) | §1.6 — verificados contra texto consolidado BCN + Circular 53/2020. El umbral de supermercados **no existe**: está derogado. |
| 2 | Base caja 14 D N°3 | §1.7 — Circular SII N°62/2020. Habilita la palanca de timing. |
| 3 | Catálogo SII por rubro | §5 — **no existe**; el SII resuelve caso a caso. El catálogo se reencuadra como *prior* interno. |
| 4 | Art. 100 bis CT | §1.4 — texto vigente (Ley 21.713 + Ley 21.755): **100–250 UTA al asesor**, no un %. |
| 5 | Parámetros AT 2025/2026 (Ley 21.713) | §1.8 — la Ley 21.713 **no modificó** el art. 31. Nada que versionar. |

### 🔴 Abiertos (para la próxima iteración)

1. **Perímetro del "devengado, cuando corresponde" en 14 D N°3** (§1.7):
   confirmar si las operaciones con **relacionados** siguen regla de devengo.
   Hasta cerrarlo, base caja **solo** con terceros no relacionados.
2. **Riesgo por fila del catálogo** (§5): sigue siendo heurística. Requiere
   firma del contador. (No hay fuente SII que lo resuelva — es criterio
   experto, no norma.)
3. **Circular SII N°53 de 2025** (tasa transitoria IDPC/PPM 14 D N°3): **no
   verificada**. No afecta al art. 31, pero sí al cálculo de impacto de la
   palanca. Cruza con la skill 7 (escenario dual 12,5%).
4. **Circulares SII N°10 y N°11 de 2025** (arts. 41 E / 41 G / 41 H post Ley
   21.713): solo verificadas por su descripción en el índice oficial. Si el
   motor toca precios de transferencia o pagos al exterior (art. 31 N°12),
   requieren verificación propia.
5. **Definición operativa de "automóvil o station wagon y similares"**: la
   frontera con vehículos comerciales (camionetas, furgones) decide si el
   rubro Transporte deduce o no. No verificada — es la pregunta de mayor
   impacto práctico que queda abierta.

---

## 8. Hallazgo transversal al repo (fuera del alcance de este doc)

La **Circular SII N°65 de 2015** fue **dejada sin efecto** por la **Circular
SII N°31 de 2025**. Hoy se cita como `fuente_legal` en:

- `.claude/skills/tax-compliance-guardrails.md` (líneas ~28, ~39)
- `supabase/migrations/20260506120000_track_1_2_legal_seeds.sql:136`
- `supabase/migrations/20260514120000_track_palancas_p7_p12.sql:168`
- `docs/firma-contador-2026-05/06_whitelist_palancas_v2.sql:137,160`

**No se corrige en este PR**: cambiar el `fuente_legal` de una regla ya
seedeada exige **publicar una nueva versión con doble firma** (skill 11), es
decir, es una acción del CONTADOR_SOCIO, no un edit de código. Se propone
como nuevo item de `TODOS-CONTADOR.md`.

Nota a favor: la skill de guardrails ya dice *"art. 100 bis (multa 100-250
UTA)"*, que **coincide** con el texto vigente verificado (§1.4). El error de
cifra vivía solo en este documento.

---

> Recordatorio: sigue vigente el **modo sandbox pre-firma**. Nada de esto
> sale a un usuario como recomendación sin la firma del contador socio.
