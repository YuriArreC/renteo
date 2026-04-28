# Disclaimers y textos legales

## Propósito
Centralizar todos los textos legales obligatorios que aparecen en la
UI o en comunicaciones del producto. La app no debe usar texto legal
distinto del que está aquí, salvo aprobación previa por estudio
jurídico.

## Versionado
Cada bloque tiene un identificador y versión (ej. "disclaimer-
recomendacion-v1"). Cualquier cambio incrementa la versión y se
registra en CHANGELOG-LEGAL.md.

---

## 1. disclaimer-recomendacion-v1
Aparece debajo de cada recomendación tributaria que el sistema
muestre al usuario.

> **Información general, no asesoría individualizada.** Esta
> recomendación se basa en información tributaria general vigente y
> en los datos que tú o tu empresa han ingresado o autorizado a
> consultar. No reemplaza la asesoría personalizada de un contador o
> abogado tributarista. La decisión final y la responsabilidad
> tributaria son del contribuyente. [Sistema] no sugiere estructuras
> que puedan calificar como elusivas conforme a los artículos 4 bis,
> 4 ter y 4 quáter del Código Tributario.

## 2. disclaimer-simulacion-v1
Aparece en cada pantalla de simulador de cierre.

> **Esta simulación es una proyección.** Los resultados dependen de
> los datos ingresados y de la normativa vigente al momento del
> cálculo. Cambios en la ley, oficios SII o jurisprudencia pueden
> alterar el resultado. Verifica con tu contador antes de tomar
> decisiones de cierre.

## 3. consentimiento-tratamiento-datos-v1
Aparece en el onboarding y antes de cualquier sincronización con SII.

> Autorizo a [Sistema] a tratar mis datos personales y los datos
> tributarios de mi empresa, con la finalidad de entregarme servicios
> de diagnóstico tributario, simulación de escenarios y alertas. El
> tratamiento se rige por la Ley 19.628 y, desde el 1 de diciembre
> de 2026, por la Ley 21.719. Puedo ejercer mis derechos ARCOP
> (acceso, rectificación, cancelación, oposición y portabilidad) en
> [link al portal de privacidad]. Conozco que [Sistema] no comparte
> mis datos con terceros sin mi consentimiento, salvo cuando la ley
> lo requiera.

## 4. consentimiento-certificado-digital-v1
Aparece cuando el usuario sube su certificado digital.

> Autorizo a [Sistema] a usar mi certificado digital, exclusivamente
> para consultar mi información tributaria en el SII a través de los
> proveedores autorizados (SimpleAPI/BaseAPI). El certificado se
> almacena cifrado en infraestructura segura (AWS KMS) y nunca se
> comparte con terceros. Puedo revocar este permiso en cualquier
> momento desde la configuración de mi cuenta.

## 5. consentimiento-mandato-digital-v1 (cliente B contadores)
Aparece cuando un contador-usuario opera por mandato digital de un
cliente.

> Reconozco actuar como Mandatario Digital del contribuyente
> [contribuyente], con autorización expresa registrada en el SII para
> los trámites detallados. Como contador colegiado/profesional asumo
> la responsabilidad profesional frente al contribuyente y al SII.
> [Sistema] es una herramienta de apoyo y no asume responsabilidad
> por las decisiones tributarias que yo, como profesional, tome con
> mis clientes.

## 6. terminos-servicio-v1
Estructura mínima (texto detallado lo redacta el estudio jurídico):
- Identificación del responsable (RUT, dirección, contacto).
- Descripción del servicio: información y simulación, no asesoría.
- Limitación de responsabilidad: alcance dentro del marco legal
  chileno.
- Tratamiento de datos: referencia a Política de Privacidad.
- Propiedad intelectual.
- Suspensión y terminación del servicio.
- Resolución de conflictos: mediación + tribunales chilenos.

## 7. politica-privacidad-v1
Estructura obligatoria post Ley 21.719:
- Identidad y contacto del responsable y del DPO.
- Bases de licitud para cada finalidad (consentimiento, contrato,
  obligación legal, interés legítimo).
- Categorías de datos tratados.
- Finalidades específicas.
- Destinatarios o categorías de destinatarios (encargados:
  Supabase, AWS, SimpleAPI/BaseAPI, Sentry, etc.).
- Transferencias internacionales (data residency Brasil/EE.UU. de
  AWS, evaluar adecuación o garantías).
- Plazos de conservación por categoría.
- Derechos del titular: acceso, rectificación, cancelación,
  oposición, portabilidad, derecho a no ser objeto de decisiones
  automatizadas.
- Procedimiento para ejercer derechos (canal y plazo, máximo 30
  días).
- Procedimiento de notificación de brechas.

## 8. ribbon-decisiones-automatizadas-v1
Aparece cuando el sistema entrega un score, ranking o priorización
de empresas (cliente B) o recomendación automatizada (cliente A).

> Esta recomendación incorpora elementos de tratamiento automatizado.
> Tienes derecho a solicitar revisión humana antes de tomar la
> decisión final. Solicitar revisión [link].

---

## 🔒 ESTUDIO_JURIDICO debe validar:
1. Cada uno de los textos anteriores en formato final.
2. Términos de servicio y política de privacidad completos.
3. Aviso legal específico para el régimen Ley 21.719 (entrada en
   vigencia 1-dic-2026).
4. Cláusulas DPA (Data Processing Agreement) con cada encargado:
   Supabase, AWS, SimpleAPI/BaseAPI, Resend, Sentry, etc.
5. Cláusulas específicas para mandato digital con contadores
   (cliente B).
6. Cláusula de exclusión del rol de "asesor tributario" del producto.
7. Cláusula de no responsabilidad por errores en información del
   SII o caídas de su portal.
