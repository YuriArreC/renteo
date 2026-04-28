# Tax Compliance Guardrails — Reglas innegociables

## Propósito
Esta skill define los límites legales y éticos de las recomendaciones que
la aplicación puede entregar a usuarios (PYMEs, medianas, contadores).
Toda feature, prompt, motor de reglas o copy de UI debe pasar por estos
guardrails. Si una recomendación no encaja claramente en la lista
permitida, se RECHAZA. Si hay duda, se marca TODO(contador) y se
escala.

## Marco legal de referencia (vigente AT 2026)
- Código Tributario, arts. 4 bis, 4 ter, 4 quáter (Norma General
  Antielusiva, "NGA").
- Código Tributario, art. 4 quinquies (procedimiento para declarar abuso
  o simulación).
- Código Tributario, art. 26 bis (consultas previas vinculantes al SII).
- Código Tributario, art. 35 (reserva tributaria, quórum calificado).
- Código Tributario, art. 97 (delitos tributarios).
- Código Tributario, art. 100 (responsabilidad del contador).
- Código Tributario, art. 100 bis (responsabilidad del asesor que diseñe
  o planifique abuso/simulación: multa 100-250 UTA).
- Ley sobre Impuesto a la Renta (LIR), arts. 14 A, 14 D N°3, 14 D N°8,
  14 E, 21, 31, 33, 41 A, 41 C, 56, 84.
- Ley 21.210 (Modernización Tributaria, 2020).
- Ley 21.713 (Cumplimiento Tributario, 24-oct-2024).
- Ley 21.716 ("ley corta" de corrección, nov-2024).
- Ley 21.755 (extensión beneficios PyME y rebaja transitoria IDPC, 2025).
- Circular SII N° 65/2015 (NGA y buena fe tributaria).
- Circular SII N° 35/2022 (reserva tributaria).
- Circular SII N° 53/2025 (rebaja transitoria tasa IDPC Pro Pyme).
- Catálogo de Esquemas Tributarios SII (versión vigente al momento de
  la consulta — verificar mensualmente).

## Marco conceptual: tres niveles

### Nivel 1 — Economía de opción (PERMITIDO ✅)
Elegir entre alternativas EXPLÍCITAMENTE previstas por la ley para
optimizar carga tributaria, sin alterar la realidad económica de la
operación. La buena fe tributaria (Circular 65/2015) protege esta
elección. **La app opera 100% en este nivel.**

### Nivel 2 — Elusión (PROHIBIDO ❌)
Evitar el hecho gravado mediante:
- **Abuso de las formas jurídicas** (art. 4 ter): operaciones que no
  producen efectos económicos relevantes distintos de los meramente
  tributarios.
- **Simulación** (art. 4 quáter): ocultar la verdadera naturaleza,
  partes o cuantía de los actos.
Sancionado por la NGA en sede TTA. El asesor diseñador responde por
art. 100 bis (multa 100-250 UTA).

### Nivel 3 — Evasión (PROHIBIDO ❌, además es delito)
Violación directa y dolosa de la norma tributaria (art. 97 CT). Delito.

---

## ✅ LISTA BLANCA — Recomendaciones que la app SÍ puede hacer

Cada elemento incluye fundamento legal y condiciones objetivas. Si no
se cumplen las condiciones, la recomendación NO se entrega.

### 1. Cambio de régimen tributario
- ✅ Sugerir cambio entre 14 A, 14 D N°3, 14 D N°8 o renta presunta
  cuando el contribuyente cumple TODOS los requisitos objetivos del
  régimen destino (ingresos promedio ≤75.000 UF para 14 D, capital
  inicial, % ingresos pasivos, etc.).
- ✅ Mostrar simulación financiera comparativa a 3 años con tasas
  vigentes (incluida la rebaja transitoria 12,5% AT 2026-2028 del
  régimen 14 D N°3).
- ❌ NO sugerir reorganizaciones (divisiones, fusiones, conversiones)
  con el solo fin de calzar artificialmente en un régimen distinto.
- Fundamento: arts. 14 A, 14 D LIR; Circular SII N°53/2025.

### 2. Depreciación instantánea (art. 31 N°5 bis LIR)
- ✅ Sugerir depreciación instantánea del 100% para activos fijos
  nuevos o usados (Oficio SII N°715 del 10-abr-2025) en empresas
  régimen 14 D, cuando el activo está adquirido y en uso durante el
  ejercicio.
- ❌ NO sugerir simular adquisiciones; NO sugerir compras a partes
  relacionadas sin razón económica.
- Fundamento: art. 31 N°5 bis LIR; Oficio SII N°715/2025.

### 3. Franquicia SENCE (Ley 19.518)
- ✅ Sugerir uso de hasta 1% de la planilla de remuneraciones imponibles
  o tope alternativo en UTM, en cursos efectivamente realizados con
  OTEC acreditada.
- ❌ NO sugerir cursos ficticios o sin asistencia real.
- Fundamento: Ley 19.518; reglamento SENCE.

### 4. Rebaja RLI por reinversión, art. 14 E LIR
- ✅ Sugerir rebajar hasta 50% de la RLI (con tope 5.000 UF) por
  reinversión en empresa, para PyMEs régimen 14 D N°3, cuando la
  reinversión es real (no retiros disfrazados).
- ❌ NO sugerir retiros que vuelvan al patrimonio del dueño en el corto
  plazo.
- Fundamento: art. 14 E LIR; Circular SII vigente.

### 5. Postergación IVA (Pro PyME)
- ✅ Sugerir postergación hasta 2 meses sin intereses cuando ingresos
  promedio ≤100.000 UF, sin morosidad reiterada.
- Fundamento: Ley 21.210; portal SII postergación IVA.

### 6. Crédito I+D (Ley 20.241)
- ✅ Sugerir solicitud de certificación CORFO para 35% del desembolso
  como crédito IDPC (tope 15.000 UTM) y 65% como gasto.
- ❌ NO sugerir reclasificar gastos operacionales como I+D sin
  certificación.
- Fundamento: Ley 20.241; extensión por Ley 21.755 hasta 31-dic-2035.

### 7. Donaciones con beneficio tributario
- ✅ Sugerir donaciones bajo Leyes Valdés, 19.885, 20.444 (cultural,
  social, reconstrucción), respetando topes globales y específicos.
- ❌ NO sugerir donaciones a entidades relacionadas con el donante.
- Fundamento: Ley Valdés y leyes complementarias.

### 8. Crédito IPE (Impuesto Pagado Extranjero, arts. 41 A y C)
- ✅ Sugerir uso de crédito por impuestos pagados en el extranjero
  cuando hay rentas de fuente extranjera y prueba documental del pago.
- Fundamento: arts. 41 A y 41 C LIR.

### 9. Sueldo empresarial (art. 31 N°6 inciso 3° LIR)
- ✅ Sugerir asignar sueldo empresarial al socio que trabaja
  efectiva y permanentemente en la empresa, con contrato y cotizaciones,
  dentro de límite razonable (test: relación con función y mercado).
- ❌ NO sugerir sueldos a socios que no trabajan ni cumplen requisitos
  de presencia efectiva.
- Fundamento: art. 31 N°6 LIR; jurisprudencia administrativa SII.

### 10. Retiros vs reinversión (timing dentro del ejercicio)
- ✅ Mostrar impacto en IGC del dueño de retirar X o reinvertir X,
  utilizando tablas IGC vigentes y reglas SAC/RAI/REX para 14 D N°3.
- ❌ NO sugerir patrones de retiros que oculten distribuciones.
- Fundamento: arts. 14 A, 14 D LIR; Circular SII N°73/2020 y posteriores.

### 11. Timing de facturación dentro del período
- ✅ Sugerir adelantar/diferir facturación al mes siguiente cuando es
  legítimo (servicios prestados, condiciones de pago acordadas).
- ❌ NO sugerir facturar después de prestado el servicio para evitar
  hecho gravado del período.
- Fundamento: Ley IVA arts. 9 y 55.

### 12. APV (Ahorro Previsional Voluntario, art. 42 bis LIR)
- ✅ Sugerir APV régimen A o B según perfil de ingresos del dueño,
  dentro de topes anuales.
- Fundamento: art. 42 bis LIR; DL 3.500.

---

## ❌ LISTA NEGRA — Recomendaciones que la app NO puede hacer NUNCA

Estas son rechazos automáticos. El motor de reglas debe filtrar
cualquier output que coincida con estos patrones.

### Estructurales
- ❌ Reorganizaciones societarias (divisiones, fusiones, conversiones,
  transformaciones) cuyo único o principal motivo sea tributario.
- ❌ Constitución de holdings, sociedades de inversión, sociedades
  plataforma con el solo fin de diferir o disminuir tributación.
- ❌ Sugerir cualquier estructura mencionada en el Catálogo de Esquemas
  Tributarios del SII (verificación mensual obligatoria de la lista
  vigente).
- ❌ Operaciones con paraísos fiscales o jurisdicciones de baja o nula
  imposición (regímenes preferenciales, art. 41 H LIR) sin sustrato
  económico real.

### Operacionales
- ❌ Facturas por servicios no prestados, sobrefacturación, doble
  facturación, facturas a partes relacionadas sin sustrato económico.
- ❌ Gastos sin documentación de respaldo o sin relación con el giro.
- ❌ Reclasificación de gastos personales del dueño como gastos de
  empresa.
- ❌ Sueldos a socios o relacionados que no trabajan efectivamente.
- ❌ Préstamos a socios disfrazados (forma de retiro no declarado).
- ❌ Contratos de arriendo entre relacionadas sin valor de mercado.

### Estructurales relacionados
- ❌ Precios de transferencia entre relacionadas que no respeten arm's
  length (art. 41 E LIR).
- ❌ "Roll-up" de ingresos pasivos a vehículos diseñados para evitar
  Global Complementario.
- ❌ Uso de pérdidas tributarias compradas (arts. 31 N°3 y 100 LIR
  modificado por Ley 21.713).
- ❌ Esquemas con instrumentos derivados, capital propio tributario o
  reorganización internacional.
- ❌ Sugerencias que requieran cambio de domicilio tributario sólo
  para optimizar.

### Banderas rojas que disparan rechazo automático
Si el motor detecta cualquiera de estos patrones en una sugerencia
generada, debe descartarla y registrar el evento:
- Operaciones entre partes relacionadas sin sustrato económico.
- Cambio en estructura jurídica próximo al cierre del ejercicio.
- Aumento de gastos en el último mes del ejercicio sin actividad
  comparable previa.
- Operaciones internacionales con jurisdicciones del Decreto 628/2003
  o sus modificaciones.

---

## 🔒 CONTADOR_SOCIO debe completar y validar:

1. **Lista actualizada del Catálogo de Esquemas Tributarios SII**
   (negative-prompt list) en el momento del go-live, y procedimiento
   de actualización mensual.
2. **Tope cuantitativo y cualitativo de "sueldo empresarial razonable"**
   por industria y función, basado en jurisprudencia administrativa.
3. **Definición operacional de "legítima razón de negocios"** (concepto
   reforzado por Ley 21.713) aplicable a cada tipo de recomendación.
4. **Flujo de escalamiento** para casos límite donde el motor marque
   TODO(contador): plazo de respuesta, criterio de decisión, registro.
5. **Política de consulta al SII (art. 26 bis)** cuando el caso del
   usuario sea ambiguo respecto de una potencial NGA: criterio para
   recomendar al usuario hacer consulta previa vinculante.
6. **Casos golden** para cada item de la lista blanca, con número y
   fundamento (mínimo 3 por item).
7. **Validación de la rebaja transitoria 12,5% IDPC 14 D N°3** y su
   condicionalidad con cumplimiento progresivo del art. 4° transitorio
   de Ley 21.735 (cotización empleador).

---

## Disclaimer obligatorio en cada recomendación generada
Toda recomendación que llegue a la UI debe ir acompañada del bloque
"disclaimer-recomendacion-v1" definido en `disclaimers-and-legal.md`.

## Auditoría
Cada recomendación generada se persiste con:
- Versión del motor de reglas.
- Inputs exactos del usuario al momento de generar.
- Output con fundamento legal (artículo + circular/oficio).
- Hash de la regla aplicada para reproducibilidad.
- Quién accedió y cuándo.

## Revisión periódica
Esta skill se revisa cada vez que:
- Se publica una nueva ley tributaria.
- SII emite Circular u Oficio relevante.
- Se actualiza el Catálogo de Esquemas Tributarios SII.
- Hay jurisprudencia TTA o Corte Suprema sobre NGA.
Mínimo: revisión trimestral por contador socio.

## TODO(contador)
- Validar y firmar (literal) cada item de la lista blanca antes del
  go-live.
- Adjuntar oficios SII y jurisprudencia que respalden cada item.
- Definir matriz de severidad para banderas rojas.
