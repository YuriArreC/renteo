# Supabase

Postgres 15 + Auth + RLS + Storage gestionados por Supabase.

## Workflow de migraciones

- Carpeta canónica: `supabase/migrations/`.
- Naming: `YYYYMMDDHHMMSS_<descripcion>.sql`.
- Idempotentes cuando es posible (`if not exists`).
- Sin SQL ad-hoc en producción. Toda mutación de schema pasa por migración
  versionada y deploy preview.
- Reglas tributarias se cargan vía migraciones en `supabase/migrations/`
  (Opción B confirmada en CLAUDE.md). Plantilla en
  `migrations/_template_tax_rule.sql.example` (creada en bloque 0D).

## Comandos típicos

```bash
supabase start              # arranca Postgres + Studio + Auth locales
supabase db reset           # reaplicar todas las migraciones
supabase db diff -f <name>  # generar migración a partir de cambios locales
supabase db push            # aplicar migraciones al proyecto remoto
```

## Seeds

`supabase/seeds/` queda reservado para datos de referencia (parámetros
tributarios AT 2024-2028, catálogos de regímenes, alertas iniciales).
Datos de prueba jamás van a seeds productivos.

## Schemas

| schema | propósito |
|---|---|
| `core` | workspaces, miembros, empresas, asignaciones cliente B, escenarios y outputs |
| `tax_params` | parámetros tributarios por año (tasas, tramos, topes) |
| `tax_data` | datos sincronizados desde SII (DTEs, RCV, F29, F22, BHE) |
| `tax_calc` | cálculos del motor (RLI, registros tributarios, retiros) |
| `security` | certificados digitales, mandatos, audit log inmutable |
| `privacy` | derechos ARCOP, consentimientos, incidentes (Ley 21.719) |
| `tax_rules` | reglas declarativas versionadas con vigencia (skill 11) |
