"""
VaidyaMD HMS — Dependency Injection & Security Guards
"""

from uuid import UUID
from typing import Optional
from fastapi import Depends, HTTPException, status, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from jose import JWTError

from app.core.database import get_db
from app.core.models import User, Hospital
from app.core.security import decode_access_token
from app.config import settings

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Authenticate request via Bearer JWT token.
    Validates token signature, expiration, and user active status.
    In development environments, gracefully falls back to an active clinic staff member.
    """
    is_dev = getattr(settings, "DEBUG", False) or getattr(settings, "ENVIRONMENT", "") != "production"

    if credentials and credentials.credentials:
        token = credentials.credentials
        try:
            payload = decode_access_token(token)
            user_id_str: Optional[str] = payload.get("sub")
            if user_id_str:
                user_id = UUID(user_id_str)
                result = await db.execute(
                    select(User).options(selectinload(User.hospital)).where(User.id == user_id, User.is_active == True)
                )
                user = result.scalar_one_or_none()
                if user:
                    return user
        except Exception as e:
            if not is_dev:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Could not validate credentials: {str(e)}",
                    headers={"WWW-Authenticate": "Bearer"},
                )

    if is_dev:
        # Fallback in local development to active clinical staff
        result = await db.execute(
            select(User).options(selectinload(User.hospital)).where(User.is_active == True).order_by(User.created_at.asc())
        )
        dev_users = result.scalars().all()
        doc = next((u for u in dev_users if u.is_doctor or str(u.role).lower() in ["doctor", "admin"]), None)
        dev_user = doc or (dev_users[0] if dev_users else None)
        if dev_user:
            return dev_user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication credentials were not provided or session has expired",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    Optional authentication: returns User if valid token is provided, else None.
    Allows backward-compatible verification calls while providing full user context when present.
    """
    if not credentials or not credentials.credentials:
        return None
    try:
        payload = decode_access_token(credentials.credentials)
        user_id_str: Optional[str] = payload.get("sub")
        if not user_id_str:
            return None
        user_id = UUID(user_id_str)
        result = await db.execute(
            select(User).options(selectinload(User.hospital)).where(User.id == user_id, User.is_active == True)
        )
        return result.scalar_one_or_none()
    except Exception:
        return None


def require_roles(*allowed_roles: str):
    """Factory dependency for role-based authorization."""
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
        if "admin" == user_role.lower():
            return current_user
        if user_role.lower() not in [r.lower() for r in allowed_roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted for role '{user_role}'. Required roles: {allowed_roles}",
            )
        return current_user
    return role_checker


require_admin = require_roles("admin")
require_clinical_staff = require_roles("doctor", "nurse", "embryologist", "pathologist", "admin")


async def get_branch_context(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Optional[UUID]:
    """
    Resolves active branch context from HTTP headers ('X-Branch-ID') or query parameters ('branch_id').
    
    Hybrid Roaming Rules:
    - If header/param is 'all' or empty for Admins/Doctors: returns None (indicating hospital-wide network view).
    - If 'all' is requested by non-Admin/Doctor facility staff: raises 403 Forbidden.
    - If a specific branch UUID is provided:
      - Validates that the branch belongs to current_user.tenant_id.
      - If user is Admin or Doctor: access granted immediately.
      - If user is facility staff: verifies that the branch ID matches user's primary branch_id or is listed in user.allowed_branch_ids.
    - Fallback: returns current_user.branch_id if set, else None for Admins/Doctors.
    """
    raw_branch = request.headers.get("X-Branch-ID") or request.query_params.get("branch_id")
    user_role = (current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)).lower()
    is_roaming_role = user_role in ["admin", "doctor"]

    if raw_branch:
        val = raw_branch.strip()
        if val.lower() in ("all", "network", "*", ""):
            if not is_roaming_role:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Network-wide 'All Branches' view is restricted to Doctors and Administrators.",
                )
            return None

        try:
            target_branch_id = UUID(val)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid branch ID format: '{val}'. Must be a valid UUID or 'all'.",
            )

        # Verify branch exists and belongs to user's hospital tenant
        from app.core.models.branch import Branch
        branch = await db.get(Branch, target_branch_id)
        if not branch or branch.hospital_id != current_user.tenant_id or not branch.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Branch not found or inactive in this hospital network.",
            )

        if not is_roaming_role:
            allowed_ids = [str(b) for b in (current_user.allowed_branch_ids or [])]
            if str(target_branch_id) != str(current_user.branch_id) and str(target_branch_id) not in allowed_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not authorized to access this branch facility.",
                )

        return target_branch_id

    # No branch specified in request: fallback
    return current_user.branch_id


def require_active_plugin(plugin_name: str):
    """
    Factory dependency checking if a plugin is active at hospital level,
    and not disabled at active branch facility level.
    """
    async def plugin_checker(
        branch_id: Optional[UUID] = Depends(get_branch_context),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> bool:
        hospital = current_user.hospital
        if not hospital:
            from app.core.models import Hospital
            hospital = await db.get(Hospital, current_user.tenant_id)

        active_plugins = [p.lower() for p in (hospital.active_plugins or [])] if hospital else []
        if active_plugins and plugin_name.lower() not in active_plugins:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Module '{plugin_name}' is not licensed or activated for this hospital.",
            )

        if branch_id:
            from app.core.models.branch import Branch
            branch = await db.get(Branch, branch_id)
            if branch and branch.enabled_plugins:
                branch_plugins = [p.lower() for p in branch.enabled_plugins]
                if plugin_name.lower() not in branch_plugins:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Module '{plugin_name}' is disabled at facility branch '{branch.name}'.",
                    )
        return True
    return plugin_checker

