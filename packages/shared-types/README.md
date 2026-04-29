# @renteo/shared-types

TypeScript types generated from Pydantic schemas in `apps/api/src/**`.

The codegen pipeline lands in phase 1 (núcleo tributario), once the first
Pydantic request/response models exist. Plan:

1. `apps/api` exposes its Pydantic models as JSON Schema via FastAPI.
2. `pnpm --filter @renteo/shared-types generate` runs `datamodel-codegen`
   against the schemas and writes TS types to `src/`.
3. `apps/web` consumes types via `import type { ... } from "@renteo/shared-types"`.

Until then this package only ships an empty `index.ts` so the workspace
resolves cleanly.
