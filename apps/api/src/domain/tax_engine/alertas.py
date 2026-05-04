"""Engine de alertas pre-cierre (skill 8 / 9).

Evaluador puro que recibe el estado declarado de una empresa para un
`tax_year` y produce una lista de candidatas a alerta. El router las
persiste en `core.alertas` con dedup por `(empresa_id, tipo,
tax_year)` mientras la alerta esté en estado abierto (nueva | vista).

Mantengo el set inicial chico:

- `rebaja_14e_disponible` (warning, ahorro estimado): empresa 14 D N°3
  con RLI > 0 que aún no aplicó la rebaja (la registra el simulador
  como palanca rebaja_14e). Sugiere reinvertir bajo art. 14 E LIR
  con los topes vigentes en `tax_params.beneficios_topes`
  (skill 8 P3, track 11b).
- `dep_instantanea_disponible` (info): 14 D N°3 / 14 D N°8 con RLI
  > 0 y sin escenarios que apliquen P1.
- `apv_disponible` (info): retiros declarados > 0 y APV no aplicado
  → sugerir P9 antes del cierre del ejercicio del dueño.

El catálogo crece en track 5c (worker Celery semanal) y track 4
(SII inputs reales). Por ahora el evaluador es on-demand desde el
front.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

Regimen = Literal["14_a", "14_d_3", "14_d_8"]
Severidad = Literal["info", "warning", "critical"]


@dataclass(frozen=True)
class AlertaInputs:
    regimen: Regimen
    tax_year: int
    rli_proyectada_pesos: Decimal
    retiros_declarados_pesos: Decimal
    palancas_aplicadas: frozenset[str] = frozenset()


@dataclass(frozen=True)
class AlertaCandidate:
    tipo: str
    severidad: Severidad
    titulo: str
    descripcion: str
    accion_recomendada: str
    fecha_limite: date


def _cierre_ejercicio(tax_year: int) -> date:
    """31 de diciembre del año tributario."""
    return date(tax_year, 12, 31)


def evaluate_pre_cierre(inputs: AlertaInputs) -> list[AlertaCandidate]:
    """Evalúa el estado y devuelve las candidatas pendientes."""
    candidates: list[AlertaCandidate] = []
    cierre = _cierre_ejercicio(inputs.tax_year)

    # Rebaja 14 E — solo aplica a régimen 14 D N°3.
    if (
        inputs.regimen == "14_d_3"
        and inputs.rli_proyectada_pesos > 0
        and "rebaja_14e" not in inputs.palancas_aplicadas
    ):
        candidates.append(
            AlertaCandidate(
                tipo="rebaja_14e_disponible",
                severidad="warning",
                titulo="Rebaja por reinversión 14 E disponible",
                descripcion=(
                    "Tu empresa está en régimen 14 D N°3 y la RLI "
                    "proyectada permite aplicar la rebaja por "
                    "reinversión del art. 14 E LIR. Aún no la "
                    "aplicaste."
                ),
                accion_recomendada=(
                    "Simula el escenario con la palanca rebaja_14e "
                    "antes del 31-dic y conserva evidencia de la "
                    "reinversión por al menos 12 meses."
                ),
                fecha_limite=cierre,
            )
        )

    # Depreciación instantánea — 14 D N°3 / 14 D N°8.
    if (
        inputs.regimen in ("14_d_3", "14_d_8")
        and inputs.rli_proyectada_pesos > 0
        and "dep_instantanea" not in inputs.palancas_aplicadas
    ):
        candidates.append(
            AlertaCandidate(
                tipo="dep_instantanea_disponible",
                severidad="info",
                titulo="Depreciación instantánea sin usar",
                descripcion=(
                    "Régimen 14 D habilita depreciar 100 % activos "
                    "fijos nuevos o usados (Oficio SII 715/2025). "
                    "Aún no registraste activos elegibles en el "
                    "simulador."
                ),
                accion_recomendada=(
                    "Si planeas adquirir activos fijos, hazlo y "
                    "ponlos en uso antes del cierre del ejercicio."
                ),
                fecha_limite=cierre,
            )
        )

    # APV del dueño — sugerir si hay retiros y aún no se modeló.
    if (
        inputs.retiros_declarados_pesos > 0
        and "apv" not in inputs.palancas_aplicadas
    ):
        candidates.append(
            AlertaCandidate(
                tipo="apv_disponible",
                severidad="info",
                titulo="APV régimen A o B disponible para el dueño",
                descripcion=(
                    "El dueño tiene retiros declarados pero no se "
                    "registró aporte APV. Reduce la base del IGC del "
                    "dueño dentro del tope anual (art. 42 bis LIR)."
                ),
                accion_recomendada=(
                    "Coordina con la AFP / AGF el aporte APV antes "
                    "del cierre del ejercicio del dueño y guarda "
                    "comprobante."
                ),
                fecha_limite=cierre,
            )
        )

    return candidates
