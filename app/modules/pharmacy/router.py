from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional

from app.core.database import get_db
from app.core.models import User
from app.core.dependencies import get_current_user
from app.modules.pharmacy.service import PharmacyService
from app.modules.pharmacy.schemas import (
    IndentCreate, IndentStatusUpdate, PurchaseOrderCreate, GRNCreate, DispenseRequest
)

router = APIRouter(prefix="/pharmacy", tags=["Pharmacy & Inventory (Clean Architecture)"], dependencies=[Depends(get_current_user)])

def get_pharmacy_service(db: AsyncSession = Depends(get_db)) -> PharmacyService:
    return PharmacyService(db)

@router.post("/ocr/invoice")
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
async def list_inventory_batches(
    category: Optional[str] = None,
    search: Optional[str] = None,
    service: PharmacyService = Depends(get_pharmacy_service)
):
    return await service.list_inventory_batches(category, search)

@router.get("/indents")
async def list_indents(
    status: Optional[str] = None,
    service: PharmacyService = Depends(get_pharmacy_service)
):
    return await service.list_indents(status)

@router.post("/indents", status_code=201)
async def create_indent(
    payload: IndentCreate,
    current_user: User = Depends(get_current_user),
    service: PharmacyService = Depends(get_pharmacy_service)
):
    if not payload.requested_by_id:
        payload.requested_by_id = current_user.id
    return await service.create_indent(payload)

@router.patch("/indents/{indent_id}/status")
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
async def list_purchase_orders(
    status: Optional[str] = None,
    service: PharmacyService = Depends(get_pharmacy_service)
):
    return await service.list_purchase_orders(status)

@router.post("/purchase-orders", status_code=201)
async def create_purchase_order(
    payload: PurchaseOrderCreate,
    service: PharmacyService = Depends(get_pharmacy_service)
):
    return await service.create_purchase_order(payload)

@router.get("/grns")
async def list_grns(
    status: Optional[str] = None,
    service: PharmacyService = Depends(get_pharmacy_service)
):
    return await service.list_grns(status)

@router.post("/grns", status_code=201)
async def create_grn(
    payload: GRNCreate,
    current_user: User = Depends(get_current_user),
    service: PharmacyService = Depends(get_pharmacy_service)
):
    if not payload.verified_by_id:
        payload.verified_by_id = current_user.id
    return await service.create_grn(payload)

@router.post("/grns/{grn_id}/stock")
async def commit_grn_to_stock(
    grn_id: UUID,
    service: PharmacyService = Depends(get_pharmacy_service)
):
    try:
        return await service.commit_grn_to_stock(grn_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
