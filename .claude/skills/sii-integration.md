# Integración con SII

## Propósito
Estandarizar cómo el producto se conecta con datos del SII, garantizando
seguridad, legalidad y resiliencia.

## Principios no negociables
1. **NUNCA pedir Clave Tributaria del usuario en texto plano.**
2. Certificados digitales solo viven en KMS, jamás en DB en claro.
3. Toda llamada externa pasa por feature flag de proveedor para poder
   conmutar entre SimpleAPI ↔ BaseAPI ↔ ApiGateway sin downtime.
4. Toda llamada se loguea sin PII (RUT enmascarado, sin claves).
5. Rate limiting por proveedor; retries exponenciales con jitter.
6. Idempotencia en sincronizaciones (key = empresa_id + período +
   tipo_dato).

## Proveedores

### Primario: SimpleAPI (chilesystems.com)
- Endpoints: RCV, F29, DTE emitidos/recibidos, BHE, BTE, contribuyentes,
  folios CAF.
- Modelo: REST + JSON, plan gratis 500 consultas/mes.
- Auth interna del proveedor: certificado centralizado del proveedor.
- Doc: simpleapi.cl/Productos/SimpleAPI

### Backup: BaseAPI (baseapi.cl)
- Endpoints: RCV, F29, DTE, BHE.
- Modelo: REST + JSON, sandbox disponible.
- Auth interna del proveedor: usa credenciales del contribuyente sin
  almacenarlas (cliente provee certificado por sesión efímera).
- Doc: baseapi.cl/docs

### Alternativo: ApiGateway (apigateway.cl)
- Endpoints amplios incluyendo conector LibreDTE.
- Para casos donde SimpleAPI/BaseAPI fallen.

### Para emisión DTE (FASE 2, no MVP): OpenFactura/Haulmer
- Solo si el producto agrega emisión.
- Doc: docsapi-openfactura.haulmer.com

## Flujo de certificado digital del usuario
1. Usuario sube archivo .pfx + clave en TLS 1.3 a endpoint dedicado.
2. Backend valida estructura PFX + extrae metadatos (RUT, vigencia).
3. Backend cifra el binario con AWS KMS (key arn por tenant) y
   almacena en S3 cifrado.
4. En DB queda solo el ARN de la versión cifrada + metadata.
5. Para cada llamada SII: backend descifra en memoria, abre sesión
   efímera, descarta certificado de RAM al terminar.
6. Auditoría: cada uso queda registrado en `cert_usage_log` con
   user_id, propósito, timestamp, resultado.
7. Revocación: usuario puede borrar certificado; KMS purga key.

## Mandato Digital SII (cliente B contadores, fase 2)
- El contador-usuario solicita al contribuyente autorización vía
  portal SII como Mandatario Digital.
- Una vez autorizado, el contador opera con SU PROPIA Clave Tributaria
  o Clave Única, sin pedir credenciales del cliente.
- Ventaja: cumplimiento legal pleno, sin riesgo de delegación de clave.
- Implementación: registrar en `mandato_digital` con plazo, alcance
  (consultar F29, declarar F22, etc.) y fecha de revocación.

## Resiliencia y errores
Clasificar errores en categorías:
- `AUTH_FAILED`: certificado vencido, revocado o clave incorrecta.
  → mostrar UX clara al usuario, NO reintentar.
- `SII_DOWN`: portal SII caído (caídas reportadas en Op. Renta 2024
  y 2025). → exponential backoff, mostrar status banner en UI.
- `RATE_LIMITED`: límite del proveedor. → cambiar a proveedor backup
  vía feature flag.
- `DATA_NOT_FOUND`: período sin datos. → no es error, es estado.
- `MALFORMED_RESPONSE`: cambio no avisado en respuesta SII. → alertar
  al equipo, fallback a último snapshot.

## Sincronización periódica
- F29 mensual: día 15 de cada mes (post vencimiento día 12).
- RCV: diario, incremental por fecha.
- DTE emitidos/recibidos: real-time o cada 6 horas.
- F22: una vez al año en mayo.

## NO HACER
- ❌ Pedir Clave Tributaria del usuario.
- ❌ Almacenar PFX en DB en claro o en variables de entorno.
- ❌ Loguear el contenido del certificado o RUTs completos en
  texto plano.
- ❌ Compartir certificado entre usuarios o tenants.
- ❌ Hacer scraping directo del portal SII desde nuestra
  infraestructura (mejor usar APIs de terceros, que ya gestionan
  rate limits y bloqueos).

## TODO
- Negociar SLA con SimpleAPI/BaseAPI para tiempos de respuesta y
  uptime durante Operación Renta.
- Definir umbral de fallback proveedor primario → backup.
- Implementar dashboard interno de salud de integración SII.
