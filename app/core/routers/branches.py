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
    gstin: Optional[str] = None
    enabled_plugins: Optional[List[str]] = []
    receipt_header: Optional[dict] = {}


class BranchUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_main_branch: Optional[bool] = None
    ip_whitelist: Optional[List[str]] = None
    is_active: Optional[bool] = None
    gstin: Optional[str] = None
    enabled_plugins: Optional[List[str]] = None
    receipt_header: Optional[dict] = None


@router.get("/user-access")
async def get_branch_user_access(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve branches accessible to the current user along with network roaming privileges."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No active hospital tenant for user")

    user_role = (current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)).lower()
    can_roam = user_role in ["admin", "doctor"]

    result = await db.execute(
        select(Branch)
        .where(Branch.hospital_id == current_user.tenant_id, Branch.is_active == True)
        .order_by(Branch.is_main_branch.desc(), Branch.name)
    )
    all_branches = result.scalars().all()

    if can_roam:
        accessible = all_branches
    else:
        allowed_ids = [str(b) for b in (current_user.allowed_branch_ids or [])]
        accessible = [
            b for b in all_branches 
            if str(b.id) == str(current_user.branch_id) or str(b.id) in allowed_ids
        ]

    return {
        "all_branches_allowed": can_roam,
        "primary_branch_id": str(current_user.branch_id) if current_user.branch_id else None,
        "accessible_branches": [
            {
                "id": str(b.id),
                "name": b.name,
                "code": b.code,
                "is_main_branch": b.is_main_branch,
                "gstin": b.gstin,
                "enabled_plugins": b.enabled_plugins or [],
            }
            for b in accessible
        ],
    }


@router.get("")
@router.get("/")
async def list_branches(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List clinic branches accessible to the user within their hospital tenant."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No active hospital tenant for user")

    user_role = (current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)).lower()
    can_roam = user_role in ["admin", "doctor"]

    result = await db.execute(
        select(Branch)
        .where(Branch.hospital_id == current_user.tenant_id)
        .order_by(Branch.is_main_branch.desc(), Branch.name)
    )
    branches = result.scalars().all()

    if can_roam:
        return branches

    allowed_ids = [str(b) for b in (current_user.allowed_branch_ids or [])]
    return [
        b for b in branches 
        if str(b.id) == str(current_user.branch_id) or str(b.id) in allowed_ids
    ]


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
        gstin=payload.gstin,
        enabled_plugins=payload.enabled_plugins or [],
        receipt_header=payload.receipt_header or {},
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
    """Update branch details, GSTIN, plugins, and IP whitelist."""
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
    if payload.gstin is not None:
        branch.gstin = payload.gstin
    if payload.enabled_plugins is not None:
        branch.enabled_plugins = payload.enabled_plugins
    if payload.receipt_header is not None:
        branch.receipt_header = payload.receipt_header

    await db.flush()
    await db.refresh(branch)
    return branch
