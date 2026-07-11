## Casos de estudio — beneficio Renteo MVP

🟡 **MODO SANDBOX — INSPECCIÓN INTERNA**. Los números acá no son
asesoría. El motor corre con seeds `PLACEHOLDER` (Ley 21.755 +
Circular SII 53/2025; UTM/UTA/UF aprox publicación SII). Goldens
en `xfail`, `RENTEO_GOLDENS_FIRMADOS` apagado, banner preliminar
visible en el frontend. La firma del contador socio sigue
pendiente (decisión 2026-05-11).

Estos casos sirven para que ingeniería **vea de antemano la forma
del beneficio** que Renteo entrega — orden de magnitud del ahorro,
qué palancas se activan, qué riesgos quedan marcados — antes de
ejecutar el sprint de firma profesional.

### Casos disponibles

| # | Perfil | Cliente | Régimen actual → recomendado | Archivo |
| - | ------ | ------- | ---------------------------- | ------- |
| 1 | Ferretería barrio · $400M ingresos · 8 empleados | A (PYME) | 14 A → 14 D N°3 | [01-ferreteria-pyme-mvp.md](./01-ferreteria-pyme-mvp.md) |

### Cómo se construyeron los números

1. **A mano** sobre los placeholders publicados en
   `supabase/migrations/20260502120000_tax_params_placeholder_seeds.sql`
   — IDPC por régimen, IGC en 8 tramos UTA, topes de palancas. Cada
   monto cita el placeholder usado.
2. **Reproducible end-to-end** con el script
   `scripts/case_study_ferreteria.py`, que abre sesión async contra
   Supabase local y llama al motor real del simulador —`_load_topes`,
   `_apply_palancas`, `_carga` de `src.routers.scenario` (los mismos
   que corre `POST /api/scenario/simulate`)— más `compute_idpc` /
   `compute_igc`. No reimplementa la aritmética: si el router cambia,
   cambian los números del caso.

### Correr el script

Requiere stack local del repo (ver `docs/DEVELOPMENT.md`):

```powershell
# Supabase local levantado y migraciones aplicadas
supabase start --workdir .

# Variable de entorno con DATABASE_URL local
$env:DATABASE_URL = "postgresql+asyncpg://postgres:postgres@127.0.0.1:54322/postgres"

# Ejecutar el caso de estudio (imprime el comparador en stdout)
python scripts/case_study_ferreteria.py
```

El script reproduce el comparador del caso 01 e imprime el
`rules_snapshot_hash` del set de reglas/parámetros. Si se fija ese
valor en `EXPECTED_RULES_HASH` (constante del script), cualquier
corrida en la que los placeholders o reglas cambien **aborta**
pidiendo re-revisar el caso — así el markdown y el motor no se
desincronizan en silencio.

### Por qué este formato y no flippear los gates

Tener un caso de estudio **estanco** (markdown + script
ejecutable) deja ver el beneficio sin necesidad de mover el banner
preliminar, sin tocar `RENTEO_GOLDENS_FIRMADOS`, sin habilitar
SII real, sin mergear `firma-contador-socio-2026-05`. Cuando el
contador firme, el mismo script seguirá corriendo — pero ahí los
números pasan a ser asesoría real y los goldens se vuelven
bloqueantes.

Mientras tanto: cualquier output del motor visible en estos casos
es **estimación preliminar**, no consejo profesional.
