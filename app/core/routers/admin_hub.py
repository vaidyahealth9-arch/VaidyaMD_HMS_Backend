"""
VaidyaMD HMS — Master Admin Control Hub Router
Provides centralized administration APIs:
- Hospital & Multi-Branch legal entity / receipt header management
- Dynamic CSV Template download (blank RFC 4180 headers)
- Live Tenant Data Export (CSV)
- In-App CSV Import Hub with conflict policy (Overwrite vs Skip)
- Super-Admin RBAC enforcement
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Form, UploadFile, File, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from app.core.database import get_db
from app.core.models import Hospital, Branch, User
from app.core.dependencies import get_current_user
from app.core.onboarding.engine import (
    DOMAIN_SPECS,
    get_blank_template_csv,
    export_domain_csv,
    import_domain_csv,
)

router = APIRouter(prefix="/admin", tags=["Master Admin Hub"])


def require_super_admin(current_user: User = Depends(get_current_user)) -> User:
    """Enforce strict Super-Admin access for master configuration changes."""
    role_str = (current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)).lower()
    if role_str != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: Master Administrative settings require Super-Admin privileges.",
        )
    return current_user


# --- Schemas ---

class BranchReceiptHeaderUpdate(BaseModel):
    branch_id: UUID
    name: Optional[str] = None
    code: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    gstin: Optional[str] = None
    receipt_header: Optional[Dict[str, Any]] = None


class HospitalProfileUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    logo_url: Optional[str] = None
    branches: Optional[List[BranchReceiptHeaderUpdate]] = None


# --- Endpoints ---

@router.get("/domains")
async def list_supported_domains(
    current_user: User = Depends(require_super_admin),
):
    """List all 13 canonical onboarding/master domains with header specifications."""
    return [
        {
            "key": key,
            "filename": spec["filename"],
            "title": spec["title"],
            "description": spec["description"],
            "headers": spec["headers"],
        }
        for key, spec in DOMAIN_SPECS.items()
    ]


@router.get("/hospital-profile")
async def get_hospital_profile(
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve hospital legal identity along with all branch receipt header configurations."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="Current user has no associated tenant")

    hospital = await db.get(Hospital, current_user.tenant_id)
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital tenant not found")

    branch_res = await db.execute(
        select(Branch).where(Branch.hospital_id == hospital.id).order_by(Branch.is_main_branch.desc(), Branch.name)
    )
    branches = branch_res.scalars().all()

    return {
        "hospital": {
            "id": str(hospital.id),
            "name": hospital.name,
            "code": hospital.code,
            "address": hospital.address,
            "phone": hospital.phone,
            "email": hospital.email,
            "logo_url": hospital.logo_url,
            "active_plugins": hospital.active_plugins or [],
            "is_active": hospital.is_active,
        },
        "branches": [
            {
                "id": str(b.id),
                "name": b.name,
                "code": b.code,
                "address": b.address,
                "phone": b.phone,
                "email": b.email,
                "is_main_branch": b.is_main_branch,
                "gstin": b.gstin,
                "ip_whitelist": b.ip_whitelist or [],
                "enabled_plugins": b.enabled_plugins or [],
                "receipt_header": b.receipt_header or {},
                "is_active": b.is_active,
            }
            for b in branches
        ],
    }


@router.put("/hospital-profile")
async def update_hospital_profile(
    payload: HospitalProfileUpdate,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update hospital legal identity and individual branch receipt printing headers."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="Current user has no associated tenant")

    hospital = await db.get(Hospital, current_user.tenant_id)
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital tenant not found")

    if payload.name is not None:
        hospital.name = payload.name
    if payload.address is not None:
        hospital.address = payload.address
    if payload.phone is not None:
        hospital.phone = payload.phone
    if payload.email is not None:
        hospital.email = payload.email
    if payload.logo_url is not None:
        hospital.logo_url = payload.logo_url

    # Update nested branches if provided
    if payload.branches:
        for b_up in payload.branches:
            branch = await db.get(Branch, b_up.branch_id)
            if branch and branch.hospital_id == hospital.id:
                if b_up.name is not None:
                    branch.name = b_up.name
                if b_up.code is not None:
                    branch.code = b_up.code
                if b_up.address is not None:
                    branch.address = b_up.address
                if b_up.phone is not None:
                    branch.phone = b_up.phone
                if b_up.email is not None:
                    branch.email = b_up.email
                if b_up.gstin is not None:
                    branch.gstin = b_up.gstin
                if b_up.receipt_header is not None:
                    branch.receipt_header = b_up.receipt_header

    await db.commit()
    return {"status": "success", "message": "Hospital profile and branch configurations updated successfully"}


def resolve_domain_spec(domain_name: str) -> tuple[str, dict] | tuple[None, None]:
    if domain_name in DOMAIN_SPECS:
        return domain_name, DOMAIN_SPECS[domain_name]
    clean_name = domain_name.lower().replace(".csv", "").strip()
    for k, spec in DOMAIN_SPECS.items():
        if spec.get("slug") == clean_name or spec.get("filename") == domain_name or spec.get("filename", "").replace(".csv", "") == clean_name:
            return k, spec
    return None, None


@router.get("/csv-templates/{domain}")
async def download_csv_template_or_export(
    domain: str,
    mode: str = Query("blank", pattern="^(blank|export)$"),
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Download CSV for a domain:
    - mode=blank: Downloads empty RFC 4180 header template for manual filling.
    - mode=export: Exports live database records for current tenant into CSV format.
    """
    resolved_key, spec = resolve_domain_spec(domain)
    if not resolved_key or not spec:
        raise HTTPException(status_code=404, detail=f"Unknown domain '{domain}'")

    if mode == "blank":
        csv_data = get_blank_template_csv(resolved_key)
        filename = f"template_{resolved_key}_{spec['filename']}"
    else:
        if not current_user.tenant_id:
            raise HTTPException(status_code=400, detail="Tenant context required for export")
        try:
            csv_data = await export_domain_csv(db, current_user.tenant_id, resolved_key)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Export failed for domain '{domain}': {str(e)}")
        filename = f"export_{resolved_key}_{spec['filename']}"

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.post("/import-csv/{domain}")
async def import_csv_domain(
    domain: str,
    file: UploadFile = File(...),
    conflict_mode: str = Form("overwrite"),
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    In-App bulk ingestion for any of the 13 canonical domains.
    Supports conflict_mode: 'overwrite' (upsert) or 'skip' (preserve existing).
    """
    resolved_key, spec = resolve_domain_spec(domain)
    if not resolved_key or not spec:
        raise HTTPException(status_code=404, detail=f"Unknown domain '{domain}'")

    if conflict_mode not in ["overwrite", "skip"]:
        raise HTTPException(status_code=400, detail="conflict_mode must be either 'overwrite' or 'skip'")

    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="Tenant context required for import")

    try:
        raw_bytes = await file.read()
        # Decode utf-8 with bom tolerance
        csv_content = raw_bytes.decode("utf-8-sig")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Unable to read uploaded CSV file: {str(e)}")

    try:
        stats = await import_domain_csv(
            session=db,
            hospital_id=current_user.tenant_id,
            domain=resolved_key,
            csv_content=csv_content,
            conflict_mode=conflict_mode,
        )
        await db.commit()
        return {
            "status": "success",
            "domain": domain,
            "filename": file.filename,
            "conflict_mode": conflict_mode,
            "stats": stats,
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=422,
            detail=f"Import failed for domain '{domain}': {str(e)}",
        )
