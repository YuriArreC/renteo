# UX y Patrones de Diseño Dual — Renteo

## Propósito
Renteo atiende dos clientes paralelos con motores tributarios
compartidos pero UX distintas:

- **Cliente A — PYME / mediana empresa:** dueño, CFO o contralor.
  Maneja 1 empresa (o pocas en grupo). Perfil financiero, no
  contable profesional.
- **Cliente B — Contador / estudio:** profesional contable que
  atiende cartera (10-80 empresas). Perfil técnico avanzado.

Esta skill define cuándo cada feature se muestra simplificada
(cliente A) o densa (cliente B), y cómo el motor único alimenta
ambas.

## Reglas no negociables
1. **El motor tributario es UNO solo.** Las dos UX consumen los
   mismos cálculos, registros y reglas.
2. **Cada pantalla declara explícitamente su `client_mode`** (`A`,
   `B`, o `shared`). Los componentes compartidos llevan suffix
   `Shared`. Los específicos llevan suffix `_A` o `_B`.
3. **No mezclar densidad.** Si una pantalla es densidad B, no se
   muestra a A nunca, y viceversa. Los componentes compartidos sí
   pueden adaptar densidad por prop.
4. **Defaults sensatos por cliente:** A ve simulaciones; B ve
   cartera. Lo opuesto requiere navegación explícita.
5. **Auditoría cross-empresa cliente B:** todo acceso a empresa de
   cartera queda en `audit_log` con `user_id` del staff y razón.

---

## Detección y enrutamiento

Al login, el JWT incluye `app_metadata.workspace_type` (`pyme` o
`accounting_firm`). El frontend rutea:

- `pyme` → `/dashboard/empresa/<empresa_id>` (cliente A).
- `accounting_firm` → `/cartera` (cliente B).

Si un usuario tiene workspaces de ambos tipos (raro pero posible),
se le ofrece selector al login.

---

## Cliente A — Dashboard de empresa

### Página principal: `/dashboard`
Vista única de SU empresa. Hero con:
- Estado actual del año tributario (RLI estimada, IDPC proyectado).
- 3 alertas más relevantes (severidad alta).
- 1 CTA principal: "Simular cierre".

### Densidad
- Tipografía generosa, espaciado amplio.
- Vocabulario traducido: "carga tributaria total" en vez de "IDPC +
  IGC", "ahorro estimado" en vez de "delta de carga".
- Tooltips obligatorios sobre todo término técnico (RLI, SAC, RAI,
  REX, PPM, RCV, F22, F29, IDPC, IGC).
- Storytelling tributario al lado de cada número: "Si reinviertes
  $X, te ahorras $Y porque el régimen 14 D N°3 te permite rebajar
  hasta 50% de la RLI por reinversión (art. 14 E LIR)".

### Features principales
- **Diagnóstico de régimen** (skill 7). Wizard guiado con
  ilustraciones, preguntas de a una, recomendación clara con
  veredicto + ahorro 3 años.
- **Simulador de cierre** (skill 8). Sliders, gráficos en vivo,
  máximo 4 escenarios comparables.
- **Alertas pre-cierre.** Inbox tipo email con prioridades visuales.
  Cada alerta tiene plan de acción concreto.
- **Reporte ejecutivo PDF.** Exportable, narrativo, citas legales,
  para enviar a contador externo o socios.

### Lo que A NO ve
- Vista cartera.
- Comparador cross-empresa.
- Papeles de trabajo Excel formato declaración SII.
- Métricas de productividad de cartera.

---

## Cliente B — Vista cartera y herramientas profesionales

### Página principal: `/cartera`
Grilla densa con todas las empresas de la cartera, columnas:
- RUT, razón social, régimen, año tributario en curso.
- Estado SII (al día / pendientes / observaciones).
- RLI estimada, IDPC proyectado.
- **Score de oportunidad de ahorro** (0-100, calculado por motor
  comparando palancas no usadas vs disponibles).
- N° de alertas críticas.
- Última simulación (fecha + ahorro).
- Asignación (qué staff atiende).

Filtros: por régimen, por staff asignado, por score, por estado SII,
por urgencia.

Ordenable por todas las columnas; ordenamiento por defecto: score
de oportunidad descendente (priorizar las que más ahorro pueden
generar).

### Densidad
- Tablas densas tipo Bloomberg, mucho dato por pantalla.
- Atajos de teclado.
- Bulk actions: seleccionar N empresas y ejecutar diagnóstico /
  simulación batch.
- Vocabulario técnico estándar contable.
- Sin tooltips redundantes para términos obvios al gremio.

### Features exclusivas B

**Vista cartera priorizada**
Score de oportunidad por empresa, ordenado para que el contador
ataque primero las de mayor ahorro potencial.

**Batch diagnóstico de régimen**
Ejecutar diagnóstico (skill 7) sobre N empresas en paralelo. Reporte
consolidado con qué empresas tienen oportunidad de cambio y ahorro
agregado.

**Comparador cross-empresa**
Para empresas de un mismo grupo o industria, comparar palancas
usadas, score de eficiencia tributaria, etc.

**Papeles de trabajo Excel**
Exportación a XLSX compatible con formato SII (RLI, ajustes, F22
preparado, declaraciones juradas relacionadas). Una pestaña por
módulo.

**Mandato digital por cartera**
Gestión centralizada de mandatos digitales SII por empresa de la
cartera, con alertas de vencimiento.

**Centro de delegación**
Asignación de empresas a staff con permisos diferenciados.
Auditoría de quién accedió a qué.

**Productividad de cartera**
KPIs internos: % empresas atendidas, ahorro tributario agregado del
mes, alertas accionadas. Útil para reportar a clientes finales del
estudio.

### Lo que B NO ve por defecto
- Tutorial / onboarding educativo (sí disponible en help, no como
  intersticial).
- Storytelling de cada número (mostrar dato puro).

---

## Componentes compartidos (`*_Shared`)

Estos componentes se usan en ambos clientes pero con prop `density`:

- **`SimuladorCierre_Shared`**: el simulador principal, idéntico
  cálculo. En A: 4 sliders visibles a la vez con explicación; en B:
  los 12 sliders en grilla compacta con números.
- **`DiagnosticoRegimen_Shared`**: motor idéntico. A: wizard de a
  una pregunta. B: formulario plano con todos los campos.
- **`AlertasInbox_Shared`**: A: lista con cards visuales. B: tabla
  con filtros.
- **`InformeRecomendacion_Shared`**: A: PDF ejecutivo narrativo. B:
  PDF técnico con anexos legales.
- **`SyncStatusBadge_Shared`**: estado SII de la empresa. Idéntico.

---

## Roles y permisos por cliente

### Cliente A
- `owner`: todo dentro de su empresa(s).
- `cfo`: lectura y simulaciones, no puede borrar empresa ni mover
  certificado digital.
- `viewer`: solo lectura.

### Cliente B
- `accountant_lead`: todo dentro del workspace, todas las empresas.
- `accountant_staff`: solo empresas asignadas en
  `accountant_assignments`, con `permission_level` definido por
  empresa.
- `viewer`: lectura de empresas asignadas.

Reglas:
- `accountant_staff` no puede ver empresas no asignadas (RLS lo
  bloquea).
- `accountant_lead` puede asignar / desasignar.
- Cambios de asignación quedan en `audit_log`.

---

## Onboarding diferenciado

### Cliente A — onboarding de 1 empresa
1. Email + verificación.
2. Datos de empresa: RUT, giro, régimen actual auto-detectado.
3. Subida de certificado digital (con consentimiento explícito de
   `consentimiento-certificado-digital-v1`).
4. Sincronización inicial con SII (RCV últimos 24 meses, F29,
   F22 año anterior).
5. Tour de 3 pantallas: dashboard, simulador, alertas.

### Cliente B — onboarding de cartera
1. Email + verificación.
2. Datos del estudio: razón social, RUT, dirección, DPO designado.
3. Importación de cartera vía Excel (RUT + datos básicos por
   empresa) o ingreso manual.
4. Plan de mandato digital: para cada empresa, indicar si ya hay
   mandato vigente, o iniciar flujo SII.
5. Asignación inicial de staff a empresas.
6. Tour de 4 pantallas: cartera, batch diagnóstico, simulador,
   papeles de trabajo.

---

## Disclaimers diferenciados

### Cliente A
Se muestra `disclaimer-recomendacion-v1` en cada recomendación.
Se muestra `disclaimer-simulacion-v1` en cada pantalla del simulador.

### Cliente B
Se muestra `consentimiento-mandato-digital-v1` al usar un mandato.
Términos de servicio reconocen su rol profesional y responsabilidad
frente al contribuyente final.

---

## Tono y voz

### Cliente A
- Claro, accesible, narrativo.
- Sin sarcasmo ni jerga interna del gremio.
- Mostrar siempre el "qué significa esto para tu negocio".
- Empático pero firme con disclaimers de no asesoría.

### Cliente B
- Profesional, conciso, eficiente.
- Vocabulario contable estándar.
- Sin "explicar lo obvio".
- Mostrar siempre el "atajo más rápido para tu trabajo del día".

---

## Anti-patrones (evitar)

- ❌ Mostrar a A la vista cartera B (los abruma).
- ❌ Mostrar a B tutoriales y wizards lentos (los frustra).
- ❌ Tooltips contables triviales en B (rompe ritmo).
- ❌ Densidad B sin atajos de teclado.
- ❌ Sliders del simulador sin validación ex-ante (bandera roja
  debe activarse en el slider, no después).
- ❌ Reportes A con jerga ("RAI", "DDAN", "PPUA") sin traducción.

---

## TODO
- Definir wireframes específicos por pantalla diferenciados A/B.
- Decidir si existe "modo experto" para A (toggle a densidad B).
- Definir copy maestro de cada disclaimer y tooltip en español
  Chile.
- Validar con 5 PYMEs y 5 contadores los flujos de onboarding antes
  del go-live.
