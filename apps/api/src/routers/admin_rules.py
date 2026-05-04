"""Panel admin de reglas tributarias — skill 11 fase 6.

Endpoints (requieren `internal_admin`):
- GET  /api/admin/rules                 lista por (status, domain).
- GET  /api/admin/rules/{id}            detalle con cuerpo completo.
- POST /api/admin/rules                 crea draft (nueva versión).
- POST /api/admin/rules/{id}/sign-contador  primera firma → pending.
- POST /api/admin/rules/{id}/publish    segunda firma + publica.
- POST /api/admin/rules/{id}/deprecate  marca deprecated.

El INSERT y el UPDATE corren con `service_session` (sin RLS) — las
reglas son globales y la policy original solo permite SELECT a
`authenticated`. La auditoría queda en `tax_rules.rule_set_changelog`
si la migración la pobló (track 11 oficial); en este MVP la entrada
se hace solo en `audit_log` workspace-less (workspace_id es NOT
NULL en la tabla; uso el workspace_id del usuario que firma).

Doble firma: el constraint de `rule_sets` exige published_by_contador
≠ published_by_admin y published_at no nulo al pasar a published.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from src.auth.internal_admin import require_internal_admin
from src.db import service_session

router = APIRouter(prefix="/api/admin/rules", tags=["admin"])


class RuleSetSummary(BaseModel):
    id: UUID
    domain: str
    key: str
    version: int
    status: str
    vigencia_desde: str
    vigencia_hasta: str | None
    published_by_contador: UUID | None
    published_by_admin: UUID | None
    published_at: str | None
    created_at: str


class RuleSetDetail(RuleSetSummary):
    rules: dict[str, Any]
    fuente_legal: list[dict[str, Any]]


class RuleSetListResponse(BaseModel):
    rule_sets: list[RuleSetSummary]


class CreateDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: str = Field(min_length=1)
    key: str = Field(min_length=1)
    vigencia_desde: date
    vigencia_hasta: date | None = None
    rules: dict[str, Any]
    fuente_legal: list[dict[str, Any]] = Field(min_length=1)


def _row_to_summary(row: dict[str, Any]) -> RuleSetSummary:
    return RuleSetSummary.model_validate(
        {
            "id": UUID(str(row["id"])),
            "domain": str(row["domain"]),
            "key": str(row["key"]),
            "version": int(row["version"]),
            "status": str(row["status"]),
            "vigencia_desde": row["vigencia_desde"].isoformat(),
            "vigencia_hasta": (
                row["vigencia_hasta"].isoformat()
                if row["vigencia_hasta"] is not None
                else None
            ),
            "published_by_contador": (
                UUID(str(row["published_by_contador"]))
                if row["published_by_contador"] is not None
                else None
            ),
            "published_by_admin": (
                UUID(str(row["published_by_admin"]))
                if row["published_by_admin"] is not None
                else None
            ),
            "published_at": (
                row["published_at"].isoformat()
                if row["published_at"] is not None
                else None
            ),
            "created_at": row["created_at"].isoformat(),
        }
    )


@router.get("", response_model=RuleSetListResponse)
async def list_rules(
    status_filter: str | None = None,
    domain: str | None = None,
    _admin: UUID = Depends(require_internal_admin),
) -> RuleSetListResponse:
    async with service_session() as session:
        result = await session.execute(
            text(
                """
                select id, domain, key, version, status,
                       vigencia_desde, vigencia_hasta,
                       published_by_contador, published_by_admin,
                       published_at, created_at
                  from tax_rules.rule_sets
                 where status = coalesce(:s, status)
                   and domain = coalesce(:d, domain)
                 order by domain, key, version desc
                """
            ),
            {"s": status_filter, "d": domain},
        )
        return RuleSetListResponse(
            rule_sets=[
                _row_to_summary(dict(r)) for r in result.mappings().all()
            ]
        )


@router.get("/{rule_id}", response_model=RuleSetDetail)
async def get_rule(
    rule_id: UUID,
    _admin: UUID = Depends(require_internal_admin),
) -> RuleSetDetail:
    async with service_session() as session:
        result = await session.execute(
            text(
                """
                select id, domain, key, version, status,
                       vigencia_desde, vigencia_hasta,
                       published_by_contador, published_by_admin,
                       published_at, created_at,
                       rules, fuente_legal
                  from tax_rules.rule_sets
                 where id = :id
                """
            ),
            {"id": str(rule_id)},
        )
        row = result.mappings().one_or_none()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"rule_set {rule_id} no encontrado.",
            )
        summary = _row_to_summary(dict(row))
        return RuleSetDetail.model_validate(
            {
                **summary.model_dump(mode="json"),
                "rules": row["rules"],
                "fuente_legal": row["fuente_legal"],
            }
        )


@router.post(
    "",
    response_model=RuleSetDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_draft(
    payload: CreateDraftRequest,
    _admin: UUID = Depends(require_internal_admin),
) -> RuleSetDetail:
    """Crea una nueva versión de regla en estado draft.

    `version` se autoincrementa: max(version) + 1 para (domain, key)
    o 1 si no existía.
    """
    async with service_session() as session:
        next_version = await session.execute(
            text(
                """
                select coalesce(max(version), 0) + 1
                  from tax_rules.rule_sets
                 where domain = :d and key = :k
                """
            ),
            {"d": payload.domain, "k": payload.key},
        )
        version = int(next_version.scalar_one())

        result = await session.execute(
            text(
                """
                insert into tax_rules.rule_sets
                    (domain, key, version, vigencia_desde, vigencia_hasta,
                     rules, fuente_legal, status)
                values
                    (:d, :k, :v, :vd, :vh,
                     cast(:rules as jsonb), cast(:fuente as jsonb), 'draft')
                returning id, domain, key, version, status,
                          vigencia_desde, vigencia_hasta,
                          published_by_contador, published_by_admin,
                          published_at, created_at, rules, fuente_legal
                """
            ),
            {
                "d": payload.domain,
                "k": payload.key,
                "v": version,
                "vd": payload.vigencia_desde,
                "vh": payload.vigencia_hasta,
                "rules": json.dumps(payload.rules, default=str),
                "fuente": json.dumps(payload.fuente_legal, default=str),
            },
        )
        row = result.mappings().one()
    summary = _row_to_summary(dict(row))
    return RuleSetDetail.model_validate(
        {
            **summary.model_dump(mode="json"),
            "rules": row["rules"],
            "fuente_legal": row["fuente_legal"],
        }
    )


@router.post(
    "/{rule_id}/sign-contador", response_model=RuleSetSummary
)
async def sign_contador(
    rule_id: UUID,
    admin_user_id: UUID = Depends(require_internal_admin),
) -> RuleSetSummary:
    """Primera firma → pending_approval. published_by_contador queda
    seteado y el segundo firmante (admin técnico, distinto) ejecuta
    /publish para activar la regla.
    """
    async with service_session() as session:
        result = await session.execute(
            text(
                """
                update tax_rules.rule_sets
                   set status = 'pending_approval',
                       published_by_contador = :uid
                 where id = :id and status = 'draft'
                returning id, domain, key, version, status,
                          vigencia_desde, vigencia_hasta,
                          published_by_contador, published_by_admin,
                          published_at, created_at
                """
            ),
            {"id": str(rule_id), "uid": str(admin_user_id)},
        )
        row = result.mappings().one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "La regla no existe o no está en estado draft. Solo "
                "draft puede pasar a pending_approval."
            ),
        )
    return _row_to_summary(dict(row))


@router.post("/{rule_id}/publish", response_model=RuleSetSummary)
async def publish_rule(
    rule_id: UUID,
    admin_user_id: UUID = Depends(require_internal_admin),
) -> RuleSetSummary:
    """Segunda firma → published.

    El constraint de la tabla exige published_by_contador !=
    published_by_admin; si el mismo usuario firmó ambos, Postgres
    rechaza con check_violation y devolvemos 409.
    """
    async with service_session() as session:
        try:
            result = await session.execute(
                text(
                    """
                    update tax_rules.rule_sets
                       set status = 'published',
                           published_by_admin = :uid,
                           published_at = now()
                     where id = :id and status = 'pending_approval'
                    returning id, domain, key, version, status,
                              vigencia_desde, vigencia_hasta,
                              published_by_contador, published_by_admin,
                              published_at, created_at
                    """
                ),
                {"id": str(rule_id), "uid": str(admin_user_id)},
            )
        except Exception as exc:
            if "check" in str(exc).lower():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Doble firma requerida: el admin técnico debe "
                        "ser distinto del contador socio."
                    ),
                ) from exc
            raise
        row = result.mappings().one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "La regla no está en pending_approval. Solo reglas con "
                "primera firma pueden publicarse."
            ),
        )
    return _row_to_summary(dict(row))


@router.post("/{rule_id}/deprecate", response_model=RuleSetSummary)
async def deprecate_rule(
    rule_id: UUID,
    _admin: UUID = Depends(require_internal_admin),
) -> RuleSetSummary:
    async with service_session() as session:
        result = await session.execute(
            text(
                """
                update tax_rules.rule_sets
                   set status = 'deprecated'
                 where id = :id
                returning id, domain, key, version, status,
                          vigencia_desde, vigencia_hasta,
                          published_by_contador, published_by_admin,
                          published_at, created_at
                """
            ),
            {"id": str(rule_id)},
        )
        row = result.mappings().one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"rule_set {rule_id} no encontrado.",
        )
    return _row_to_summary(dict(row))
