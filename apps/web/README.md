# Renteo Web

Frontend Next.js 15 (App Router) + React 19 + TypeScript strict + Tailwind +
shadcn/ui + next-intl (es-CL).

## Comandos

```bash
pnpm --filter @renteo/web dev        # Next dev en :3000
pnpm --filter @renteo/web build      # producción
pnpm --filter @renteo/web lint       # eslint (next)
pnpm --filter @renteo/web typecheck  # tsc --noEmit
pnpm --filter @renteo/web test       # vitest
```

## Convenciones de componentes (skill 9)

- Suffix `_A` — específico cliente PYME / mediana.
- Suffix `_B` — específico cliente contador / estudio.
- Suffix `_Shared` — usable en ambos clientes con prop `density`.
- Sin densidad B en pantallas A ni viceversa.
