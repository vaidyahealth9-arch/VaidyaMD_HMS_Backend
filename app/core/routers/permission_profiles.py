"""
VaidyaMD HMS — Permission Profiles Router (Dynamic Configurable RBAC)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from pydantic import BaseModel
from typing import Optional, Any

from app.core.database import get_db
from app.core.models import PermissionProfile, Hospital, User
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/permission-profiles", tags=["Permission Profiles"])


class ProfileCreate(BaseModel):
    name: str
    description: Optional[str] = None
    menu_permissions: dict[str, bool]


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    menu_permissions: Optional[dict[str, bool]] = None
    is_active: Optional[bool] = None


@router.get("")
@router.get("/")
async def list_permission_profiles(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all configured permission profiles for the user's hospital tenant."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No active hospital tenant for user")

    result = await db.execute(
        select(PermissionProfile)
        .where(PermissionProfile.hospital_id == current_user.tenant_id)
        .order_by(PermissionProfile.name)
    )
    return result.scalars().all()


@router.post("", status_code=status.HTTP_201_CREATED)
@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_permission_profile(
    payload: ProfileCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new dynamic permission profile under user's hospital tenant."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No active hospital tenant for user")

    profile = PermissionProfile(
        hospital_id=current_user.tenant_id,
        name=payload.name,
        description=payload.description,
        menu_permissions=payload.menu_permissions,
        is_active=True,
    )
    db.add(profile)
    await db.flush()
    await db.refresh(profile)
    return profile


@router.get("/{profile_id}")
async def get_permission_profile(
    profile_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a permission profile by ID."""
    profile = await db.get(PermissionProfile, profile_id)
    if not profile or profile.hospital_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Permission profile not found")
    return profile


@router.put("/{profile_id}")
@router.patch("/{profile_id}")
async def update_permission_profile(
    profile_id: UUID,
    payload: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update profile permissions or metadata."""
    profile = await db.get(PermissionProfile, profile_id)
    if not profile or profile.hospital_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Permission profile not found")

    if payload.name is not None:
        profile.name = payload.name
    if payload.description is not None:
        profile.description = payload.description
    if payload.menu_permissions is not None:
        profile.menu_permissions = payload.menu_permissions
    if payload.is_active is not None:
        profile.is_active = payload.is_active

    await db.flush()
    await db.refresh(profile)
    return profile
