from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional

from app.core.database import get_db
from app.core.models import User
from app.core.dependencies import get_current_user, get_branch_context
from app.modules.pharmacy.service import PharmacyService
from app.modules.pharmacy.schemas import (
    IndentCreate, IndentStatusUpdate, PurchaseOrderCreate, GRNCreate, DispenseRequest
)

router = APIRouter(prefix="/pharmacy", tags=["Pharmacy & Inventory (Clean Architecture)"], dependencies=[Depends(get_current_user)])

def get_pharmacy_service(db: AsyncSession = Depends(get_db)) -> PharmacyService:
    return PharmacyService(db)

@router.post("/ocr/invoice")
@router.post("/ocr/invoice/", include_in_schema=False)
async def parse_vendor_invoice_ocr(
    request: Request,
    service: PharmacyService = Depends(get_pharmacy_service)
):
    payload = {}
    file_name = ""

    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            payload = await request.json()
            if not isinstance(payload, dict):
                payload = {}
        else:
            form = await request.form()
            payload = dict(form)
            if "file" in form:
                f = form["file"]
                file_name = getattr(f, "filename", "")
    except Exception:
        pass

    return await service.parse_vendor_invoice_ocr(payload, file_name)

@router.post("/dispense")
@router.post("/dispense/", include_in_schema=False)
async def dispense_fefo(
    payload: DispenseRequest,
    current_user: User = Depends(get_current_user),
    service: PharmacyService = Depends(get_pharmacy_service)
):
    try:
        return await service.dispense_fefo(payload, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/batches")
@router.get("/batches/", include_in_schema=False)
async def list_inventory_batches(
    category: Optional[str] = None,
    search: Optional[str] = None,
    branch_id: Optional[UUID] = Depends(get_branch_context),
    current_user: User = Depends(get_current_user),
    service: PharmacyService = Depends(get_pharmacy_service)
):
    return await service.list_inventory_batches(category, search, tenant_id=current_user.tenant_id, branch_id=branch_id)

@router.get("/indents")
@router.get("/indents/", include_in_schema=False)
async def list_indents(
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    service: PharmacyService = Depends(get_pharmacy_service)
):
    return await service.list_indents(status, tenant_id=current_user.tenant_id)

@router.post("/indents", status_code=201)
@router.post("/indents/", status_code=201, include_in_schema=False)
async def create_indent(
    payload: IndentCreate,
    branch_id: Optional[UUID] = Depends(get_branch_context),
    current_user: User = Depends(get_current_user),
    service: PharmacyService = Depends(get_pharmacy_service)
):
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context required to create pharmacy indents")
    if not payload.requested_by_id:
        payload.requested_by_id = current_user.id
    if not payload.branch_id and branch_id:
        payload.branch_id = branch_id
    return await service.create_indent(payload, tenant_id=current_user.tenant_id)

@router.post("/indents/{indent_id}/transfer-fulfill")
@router.post("/indents/{indent_id}/transfer-fulfill/", include_in_schema=False)
async def fulfill_inter_branch_indent(
    indent_id: UUID,
    current_user: User = Depends(get_current_user),
    service: PharmacyService = Depends(get_pharmacy_service)
):
    try:
        return await service.fulfill_inter_branch_indent(indent_id, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/indents/{indent_id}/status")
@router.patch("/indents/{indent_id}/status/", include_in_schema=False)
async def update_indent_status(
    indent_id: UUID,
    payload: IndentStatusUpdate,
    service: PharmacyService = Depends(get_pharmacy_service)
):
    try:
        return await service.update_indent_status(indent_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/purchase-orders")
@router.get("/purchase-orders/", include_in_schema=False)
async def list_purchase_orders(
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    service: PharmacyService = Depends(get_pharmacy_service)
):
    return await service.list_purchase_orders(status, tenant_id=current_user.tenant_id)

@router.post("/purchase-orders", status_code=201)
@router.post("/purchase-orders/", status_code=201, include_in_schema=False)
async def create_purchase_order(
    payload: PurchaseOrderCreate,
    current_user: User = Depends(get_current_user),
    service: PharmacyService = Depends(get_pharmacy_service)
):
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context required to create purchase orders")
    return await service.create_purchase_order(payload, tenant_id=current_user.tenant_id)

@router.get("/grns")
@router.get("/grns/", include_in_schema=False)
async def list_grns(
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    service: PharmacyService = Depends(get_pharmacy_service)
):
    return await service.list_grns(status, tenant_id=current_user.tenant_id)

@router.post("/grns", status_code=201)
@router.post("/grns/", status_code=201, include_in_schema=False)
async def create_grn(
    payload: GRNCreate,
    current_user: User = Depends(get_current_user),
    service: PharmacyService = Depends(get_pharmacy_service)
):
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context required to create GRN")
    if not payload.verified_by_id:
        payload.verified_by_id = current_user.id
    return await service.create_grn(payload, tenant_id=current_user.tenant_id)

@router.post("/grns/{grn_id}/stock")
@router.post("/grns/{grn_id}/stock/", include_in_schema=False)
async def commit_grn_to_stock(
    grn_id: UUID,
    service: PharmacyService = Depends(get_pharmacy_service)
):
    try:
        return await service.commit_grn_to_stock(grn_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
