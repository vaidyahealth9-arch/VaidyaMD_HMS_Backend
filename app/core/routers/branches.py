"""
VaidyaMD HMS — Branches Router (Multi-Clinic & IP Allowlist)
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from pydantic import BaseModel
from typing import Optional, List

from app.core.database import get_db
from app.core.models import Branch, Hospital, User
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/branches", tags=["Branches"])


class BranchCreate(BaseModel):
    name: str
    code: str
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_main_branch: bool = False
    ip_whitelist: Optional[List[str]] = []


class BranchUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_main_branch: Optional[bool] = None
    ip_whitelist: Optional[List[str]] = None
    is_active: Optional[bool] = None


@router.get("")
@router.get("/")
async def list_branches(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all clinic branches scoped to user's hospital tenant."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No active hospital tenant for user")

    result = await db.execute(
        select(Branch)
        .where(Branch.hospital_id == current_user.tenant_id)
        .order_by(Branch.is_main_branch.desc(), Branch.name)
    )
    return result.scalars().all()


@router.post("", status_code=status.HTTP_201_CREATED)
@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_branch(
    payload: BranchCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register a new clinic branch under user's hospital tenant."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No active hospital tenant for user")

    branch = Branch(
        hospital_id=current_user.tenant_id,
        name=payload.name,
        code=payload.code.upper(),
        address=payload.address,
        phone=payload.phone,
        email=payload.email,
        is_main_branch=payload.is_main_branch,
        ip_whitelist=payload.ip_whitelist or [],
        is_active=True,
    )
    db.add(branch)
    await db.flush()
    await db.refresh(branch)
    return branch


@router.get("/{branch_id}")
async def get_branch(
    branch_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a single clinic branch by ID."""
    branch = await db.get(Branch, branch_id)
    if not branch or branch.hospital_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Branch not found")
    return branch


@router.put("/{branch_id}")
@router.patch("/{branch_id}")
async def update_branch(
    branch_id: UUID,
    payload: BranchUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update branch details and IP whitelist."""
    branch = await db.get(Branch, branch_id)
    if not branch or branch.hospital_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Branch not found")

    if payload.name is not None:
        branch.name = payload.name
    if payload.code is not None:
        branch.code = payload.code.upper()
    if payload.address is not None:
        branch.address = payload.address
    if payload.phone is not None:
        branch.phone = payload.phone
    if payload.email is not None:
        branch.email = payload.email
    if payload.is_main_branch is not None:
        branch.is_main_branch = payload.is_main_branch
    if payload.ip_whitelist is not None:
        branch.ip_whitelist = payload.ip_whitelist
    if payload.is_active is not None:
        branch.is_active = payload.is_active

    await db.flush()
    await db.refresh(branch)
    return branch
