# Changelog legal

Registro de versiones de textos legales que aparecen en la UI o en
comunicaciones del producto. Skill 2 (`disclaimers-and-legal`) y skill 5
(`chilean-data-privacy`) son la fuente de verdad. Este archivo documenta
qué versión está activa y cuándo cambió.

Cualquier cambio de copy legal incrementa la versión del bloque y queda
asentado aquí en la misma PR. Toda versión final debe ir firmada por
estudio jurídico antes del go-live público.

Formato:
- Una entrada por versión publicada de un bloque.
- Identificadores estables: `disclaimer-recomendacion`, `disclaimer-simulacion`,
  `consentimiento-tratamiento-datos`, `consentimiento-certificado-digital`,
  `consentimiento-mandato-digital`, `terminos-servicio`,
  `politica-privacidad`, `ribbon-decisiones-automatizadas`.

---

## 2026-04-28 — v1 (preliminar, no firmada)

### Added

- **`politica-privacidad-v1`** (es-CL, preliminar): texto placeholder en
  `apps/web/src/app/legal/privacidad/page.tsx` con las secciones del
  skill 2 + skill 5 (responsable, bases de licitud, datos, finalidades,
  destinatarios, transferencias internacionales, retención, ARCOP,
  decisiones automatizadas, brechas, contacto DPO). Páginas marcadas
  `robots: noindex` y con banner "versión preliminar".
- **`terminos-servicio-v1`** (es-CL, preliminar): texto placeholder en
  `apps/web/src/app/legal/terminos/page.tsx` con secciones del skill 2
  (responsable, alcance, limitación de responsabilidad, cumplimiento
  tributario, datos, propiedad intelectual, terminación, conflictos).
- **`disclaimer-recomendacion-v1`** y **`disclaimer-simulacion-v1`** y
  consentimientos versionados: texto definido en
  `.claude/skills/disclaimers-and-legal.md`. Aún no consumidos por la UI
  (entran cuando el motor entrega recomendaciones, fase 3+).

### Pendientes para v2 (versión firmada de go-live)

- Razón social, RUT y dirección legal del responsable.
- Contacto del DPO designado.
- Canal único para ejercer derechos ARCOP.
- Revisión completa por estudio jurídico de los textos placeholder.
- DPAs firmados con encargados (Supabase, AWS, SimpleAPI/BaseAPI,
  Resend o equivalente, Sentry).

Responsable de la próxima revisión: **ESTUDIO_JURIDICO**.
Plazo objetivo: antes del go-live público (fase 8).
