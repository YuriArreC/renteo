"""Tests golden — validación profesional del motor tributario.

CLAUDE.md exige que cada función de cálculo tenga test golden firmado
por el contador socio. Hasta que la firma exista, los goldens viven
como `@pytest.mark.xfail(strict=GOLDENS_STRICT)` para que un cambio
de placeholder no rompa CI.

Cuando el contador firme (ver `docs/REVISION_CONTADOR_SOCIO.md`):
1. Setear `RENTEO_GOLDENS_FIRMADOS=1` en CI.
2. `GOLDENS_STRICT` pasa a True → cualquier xfail que pase termina en
   `XPASSED` y rompe el run; cualquiera que falle, idem. Los goldens
   se vuelven assertions reales.
"""

from __future__ import annotations

import os

GOLDENS_STRICT: bool = os.getenv("RENTEO_GOLDENS_FIRMADOS") == "1"
