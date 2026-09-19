"""
VaidyaMD HMS — Branches Router (Multi-Clinic & IP Allowlist)
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from pydantic import BaseModel
from typing import Optional, List

from app.core.database import get_db
from app.core.models import Branch, Hospital

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


@router.get("/")
async def list_branches(db: AsyncSession = Depends(get_db)):
    """List all clinic branches."""
    result = await db.execute(select(Branch).order_by(Branch.is_main_branch.desc(), Branch.name))
    return result.scalars().all()


@router.post("/", status_code=201)
async def create_branch(payload: BranchCreate, db: AsyncSession = Depends(get_db)):
    """Register a new clinic branch."""
    result = await db.execute(select(Hospital).limit(1))
    hospital = result.scalar_one_or_none()
    if not hospital:
        raise HTTPException(status_code=500, detail="No hospital configured")

    branch = Branch(
        hospital_id=hospital.id,
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


@router.put("/{branch_id}")
async def update_branch(branch_id: UUID, payload: BranchUpdate, db: AsyncSession = Depends(get_db)):
    """Update branch details and IP whitelist."""
    branch = await db.get(Branch, branch_id)
    if not branch:
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
