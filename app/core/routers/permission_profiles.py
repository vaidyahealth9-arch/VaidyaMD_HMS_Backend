"""
VaidyaMD HMS — Permission Profiles Router (Dynamic Configurable RBAC)
"""

from fastapi import APIRouter, Depends, HTTPException
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


@router.get("/")
async def list_permission_profiles(db: AsyncSession = Depends(get_db)):
    """List all configured permission profiles for the hospital."""
    result = await db.execute(select(PermissionProfile).order_by(PermissionProfile.name))
    return result.scalars().all()


@router.post("/", status_code=201)
async def create_permission_profile(
    payload: ProfileCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new dynamic permission profile."""
    result = await db.execute(select(Hospital).limit(1))
    hospital = result.scalar_one_or_none()
    if not hospital:
        raise HTTPException(status_code=500, detail="No hospital configured")

    profile = PermissionProfile(
        hospital_id=hospital.id,
        name=payload.name,
        description=payload.description,
        menu_permissions=payload.menu_permissions,
        is_active=True,
    )
    db.add(profile)
    await db.flush()
    await db.refresh(profile)
    return profile


@router.put("/{profile_id}")
async def update_permission_profile(
    profile_id: UUID,
    payload: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update profile permissions or metadata."""
    profile = await db.get(PermissionProfile, profile_id)
    if not profile:
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
