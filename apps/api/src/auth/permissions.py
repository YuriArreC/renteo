"""Role-based access control built on top of `current_tenancy`.

Mirrors `app.has_empresa_access(uuid)` in SQL (B2): only `accountant_staff`
must have the empresa explicitly listed in `empresa_ids[]`; other roles
are gated by the workspace_id RLS policy.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from fastapi import Depends, HTTPException, status

from src.auth.tenancy import Role, Tenancy, current_tenancy


def require_role(*roles: Role) -> Callable[[Tenancy], Tenancy]:
    allowed = frozenset(roles)

    def dep(t: Tenancy = Depends(current_tenancy)) -> Tenancy:
        if t.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="forbidden",
            )
        return t

    return dep


def require_empresa_access(empresa_id: UUID) -> Callable[[Tenancy], Tenancy]:
    def dep(t: Tenancy = Depends(current_tenancy)) -> Tenancy:
        if t.role == "accountant_staff" and empresa_id not in t.empresa_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="no access to empresa",
            )
        return t

    return dep
