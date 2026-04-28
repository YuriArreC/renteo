# Privacidad y Protección de Datos — Chile

## Propósito
Garantizar cumplimiento de Ley 19.628 (vigente) y Ley 21.719 (vigencia
plena 1-dic-2026) en cada feature del producto.

## Marco legal
- Ley 19.628 (1999) sobre Protección de Datos Personales — vigente.
- Ley 21.719 (publicada 13-dic-2024, vigencia plena 1-dic-2026).
- Ley 21.663 (Marco de Ciberseguridad).
- Código Tributario art. 35 (reserva tributaria, quórum calificado).
- Ley 21.521 Fintech (no aplica al MVP, monitorear si se agregan
  features financieras).

## Principios de diseño (privacy-by-design)
1. **Minimización de datos:** solo recolectar lo necesario para la
   finalidad declarada.
2. **Consentimiento expreso, informado y específico** para cada
   finalidad.
3. **Bases de licitud explícitas** documentadas por finalidad
   (contrato, obligación legal, consentimiento).
4. **Cifrado:** AES-256 en reposo, TLS 1.3 en tránsito. Certificados
   digitales y datos sensibles en KMS/HSM.
5. **Segregación multi-tenant** vía RLS por workspace_id +
   empresa_id. Pruebas automáticas que validen aislamiento.
6. **Trazabilidad:** todo acceso a datos personales/tributarios
   queda registrado en audit_log inmutable.
7. **Retención limitada:** purga automática según política de
   retención por categoría.

## Derechos ARCOP (obligatorios desde Ley 21.719)
- **A**cceso: usuario puede descargar todos sus datos en formato
  estructurado.
- **R**ectificación: usuario puede corregir datos inexactos.
- **C**ancelación: usuario puede solicitar borrado, salvo retención
  legal obligatoria (ej. 6 años CT art. 17).
- **O**posición: usuario puede oponerse a ciertos tratamientos.
- **P**ortabilidad: usuario puede recibir sus datos en formato
  interoperable.

Implementación:
- Portal de privacidad accesible desde Settings.
- Plazo de respuesta: máximo 30 días corridos.
- Identidad del solicitante validada con MFA.

## Decisiones automatizadas
La app entrega recomendaciones tributarias automatizadas. Bajo Ley
21.719:
- Disclosure obligatorio de que existe perfilamiento.
- Derecho del usuario a solicitar **revisión humana** antes de tomar
  decisión final → para esto, el contador socio o equipo dedicado
  responde dentro de 5 días hábiles.

## DPO (Delegado de Protección de Datos)
Obligatorio para entidades que tratan datos a gran escala y datos
financieros/tributarios.
- Rol inicial: contador socio (con capacitación adicional).
- Funciones: supervisar cumplimiento, atender ARCOP, ser punto de
  contacto con la Agencia.
- Independencia funcional, reporta directamente a la dirección.

## RAT (Registro de Actividades de Tratamiento)
Documento interno con, por cada finalidad:
- Identificación del responsable y DPO.
- Finalidad y base de licitud.
- Categorías de titulares y datos.
- Categorías de destinatarios.
- Transferencias internacionales (AWS, Supabase) y garantías.
- Plazos de conservación.
- Medidas técnicas y organizativas.

Mantener actualizado y disponible ante fiscalización de la Agencia.

## DPIA (Evaluación de Impacto en Privacidad)
Obligatoria para tratamientos de alto riesgo. **El perfilamiento
tributario automatizado del MVP CALIFICA como alto riesgo.**
Documentar:
- Descripción del tratamiento.
- Necesidad y proporcionalidad.
- Riesgos para los titulares (acceso no autorizado, decisiones
  erróneas, discriminación, inferencias invasivas).
- Medidas de mitigación.
- Consulta previa a la Agencia si el riesgo residual es alto.

## Notificación de brechas
- Plazo: notificar a la Agencia "sin dilación indebida" (estándar
  GDPR-like: 72 horas) cuando la brecha pueda afectar derechos.
- Notificar a titulares afectados cuando el riesgo sea alto.
- Procedimiento documentado: detección → contención → análisis →
  notificación → remediación → post-mortem.

## Encargados de tratamiento
Cada tercero que toca datos firma DPA (Data Processing Agreement):
- Supabase (DB, Auth).
- AWS (S3, KMS, infra).
- SimpleAPI / BaseAPI / ApiGateway (acceso SII).
- Sentry / Datadog (logs sin PII).
- Resend / similar (emails transaccionales).

## Transferencias internacionales
AWS regiones disponibles: sa-east-1 (São Paulo) o us-east-1.
- Preferencia: sa-east-1 por menor latencia y eventual exigencia de
  data residency latinoamericano.
- Si hay procesamiento en EE.UU., evaluar adecuación / cláusulas
  contractuales tipo / consentimiento explícito.

## Sanciones (referencia, Ley 21.719)
- Leves: hasta 5.000 UTM.
- Graves: hasta 10.000 UTM.
- Gravísimas: hasta 20.000 UTM o 4% ingresos del ejercicio anterior.
- Régimen transitorio PyME (dic 2026 - dic 2027): solo amonestaciones.

## Reserva tributaria (art. 35 CT)
Toda información tributaria del contribuyente es reservada con
quórum calificado. La app y sus encargados quedan vinculados:
- Cláusula contractual con cada empleado, contractor y proveedor.
- Acceso a datos tributarios solo bajo principio de mínimo necesario.
- Logging exhaustivo de cada acceso.

## TODO
- Designar DPO formal pre-go-live.
- Redactar y firmar DPAs con cada encargado.
- DPIA documentada para perfilamiento tributario.
- Procedimiento de notificación de brechas con runbook.
- Pentest externo OWASP Top 10 antes de lanzar.
