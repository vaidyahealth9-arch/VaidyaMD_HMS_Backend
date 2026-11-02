from fastapi import APIRouter, Depends, HTTPException, Request, Query, UploadFile, File, Form, Response
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional

from app.core.database import get_db
from app.core.models import User
from app.core.dependencies import get_current_user, get_branch_context
from app.modules.pharmacy.service import PharmacyService
from app.modules.pharmacy.schemas import (
    IndentCreate, IndentStatusUpdate, PurchaseOrderCreate, GRNCreate, DispenseRequest, PurchaseReturnCreate
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
    active_only: Optional[bool] = Query(None, description="Filter only active batches (True) or all (False)"),
    branch_id: Optional[UUID] = Depends(get_branch_context),
    current_user: User = Depends(get_current_user),
    service: PharmacyService = Depends(get_pharmacy_service)
):
    return await service.list_inventory_batches(
        category=category,
        search=search,
        tenant_id=current_user.tenant_id,
        branch_id=branch_id,
        active_only=bool(active_only),
    )

@router.post("/batches", status_code=201)
@router.post("/batches/", status_code=201, include_in_schema=False)
async def create_inventory_batch(
    payload: dict,
    branch_id: Optional[UUID] = Depends(get_branch_context),
    current_user: User = Depends(get_current_user),
    service: PharmacyService = Depends(get_pharmacy_service)
):
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context required to create batch")
    return await service.create_batch(payload, tenant_id=current_user.tenant_id, branch_id=branch_id)

@router.put("/batches/{batch_id}")
async def update_inventory_batch(
    batch_id: UUID,
    payload: dict,
    current_user: User = Depends(get_current_user),
    service: PharmacyService = Depends(get_pharmacy_service)
):
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context required to update batch")
    return await service.update_batch(batch_id, payload, tenant_id=current_user.tenant_id)

@router.delete("/batches/{batch_id}")
async def delete_inventory_batch(
    batch_id: UUID,
    deactivate_all: bool = Query(False, description="Also deactivate all other batches matching this item code"),
    current_user: User = Depends(get_current_user),
    service: PharmacyService = Depends(get_pharmacy_service)
):
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context required to delete batch")
    return await service.delete_batch(batch_id, tenant_id=current_user.tenant_id, deactivate_all_batches=deactivate_all)

@router.get("/indents")
@router.get("/indents/", include_in_schema=False)
async def list_indents(
    status: Optional[str] = None,
    indent_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    service: PharmacyService = Depends(get_pharmacy_service)
):
    return await service.list_indents(status, indent_type=indent_type, tenant_id=current_user.tenant_id)

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

@router.get("/vendors")
@router.get("/vendors/", include_in_schema=False)
async def list_vendors(
    current_user: User = Depends(get_current_user),
    service: PharmacyService = Depends(get_pharmacy_service)
):
    return await service.list_vendors(tenant_id=current_user.tenant_id)

@router.post("/vendors", status_code=201)
@router.post("/vendors/", status_code=201, include_in_schema=False)
async def create_vendor(
    payload: dict,
    current_user: User = Depends(get_current_user),
    service: PharmacyService = Depends(get_pharmacy_service)
):
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context required to create vendor")
    return await service.create_vendor(payload, tenant_id=current_user.tenant_id)

@router.put("/vendors/{vendor_id}")
async def update_vendor(
    vendor_id: UUID,
    payload: dict,
    current_user: User = Depends(get_current_user),
    service: PharmacyService = Depends(get_pharmacy_service)
):
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context required to update vendor")
    return await service.update_vendor(vendor_id, payload, tenant_id=current_user.tenant_id)

@router.delete("/vendors/{vendor_id}")
async def delete_vendor(
    vendor_id: UUID,
    current_user: User = Depends(get_current_user),
    service: PharmacyService = Depends(get_pharmacy_service)
):
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context required to delete vendor")
    return await service.delete_vendor(vendor_id, tenant_id=current_user.tenant_id)


# =====================================================================
# Dedicated Pharmacy CSV Batch Stock Ingestion Endpoints
# =====================================================================

@router.get("/inventory/template-csv")
@router.get("/inventory/template-csv/", include_in_schema=False)
async def download_pharmacy_stock_template():
    """Download standard RFC 4180 CSV template for bulk pharmacy formulary and batch upload."""
    from app.core.onboarding.engine import get_blank_template_csv
    csv_data = get_blank_template_csv("pharmacy_stock")
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="11b_pharmacy_stock_template.csv"',
            "Cache-Control": "no-cache",
        },
    )


@router.post("/inventory/preview-csv")
@router.post("/inventory/preview-csv/", include_in_schema=False)
async def preview_pharmacy_stock_csv(
    file: UploadFile = File(...),
    conflict_mode: str = Form("overwrite"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Preview pharmacy stock CSV rows, identifying new insertions vs batch updates."""
    from app.core.onboarding.engine import preview_domain_csv
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context required to preview stock CSV")
    try:
        raw_bytes = await file.read()
        csv_content = raw_bytes.decode("utf-8-sig")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Unable to read CSV file: {str(e)}")

    try:
        stats = await preview_domain_csv(
            session=db,
            hospital_id=current_user.tenant_id,
            domain="pharmacy_stock",
            csv_content=csv_content,
            conflict_mode=conflict_mode,
        )
        return {
            "status": "preview",
            "domain": "pharmacy_stock",
            "filename": file.filename,
            "conflict_mode": conflict_mode,
            "stats": stats,
        }
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Preview failed: {str(e)}")


@router.post("/inventory/import-csv")
@router.post("/inventory/import-csv/", include_in_schema=False)
async def import_pharmacy_stock_csv(
    file: UploadFile = File(...),
    conflict_mode: str = Form("overwrite"),
    dry_run: bool = Form(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Bulk ingest pharmacy inventory batches from CSV into live database."""
    from app.core.onboarding.engine import import_domain_csv, preview_domain_csv
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context required to import stock CSV")
    try:
        raw_bytes = await file.read()
        csv_content = raw_bytes.decode("utf-8-sig")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Unable to read CSV file: {str(e)}")

    if dry_run:
        try:
            stats = await preview_domain_csv(
                session=db,
                hospital_id=current_user.tenant_id,
                domain="pharmacy_stock",
                csv_content=csv_content,
                conflict_mode=conflict_mode,
            )
            return {"status": "preview", "stats": stats}
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Preview failed: {str(e)}")

    try:
        stats = await import_domain_csv(
            session=db,
            hospital_id=current_user.tenant_id,
            domain="pharmacy_stock",
            csv_content=csv_content,
            conflict_mode=conflict_mode,
        )
        if isinstance(stats, dict) and stats.get("success") is False:
            raise HTTPException(status_code=400, detail=stats.get("error", "CSV ingestion failed"))
        await db.commit()
        return {
            "status": "success",
            "domain": "pharmacy_stock",
            "filename": file.filename,
            "conflict_mode": conflict_mode,
            "stats": stats,
        }
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=f"Stock CSV Import failed: {str(e)}")




@router.get("/reports/agency-summary")
@router.get("/reports/agency-summary/", include_in_schema=False)
async def get_agency_summary_report(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Aggregates pharmacy distributor / agency purchase value, active inventory value,
    and returns metrics per agency.
    """
    tenant_id = current_user.hospital_id or getattr(current_user, 'tenant_id', None)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context required")

    from sqlalchemy import select, func, and_
    from app.modules.pharmacy.model import GoodsReceivedNote, InventoryBatch, PharmacyPurchaseReturn, PharmacyVendor

    # 1. Total purchases per vendor from Goods Received Notes (GRN)
    grn_stmt = select(
        GoodsReceivedNote.vendor_name,
        func.sum(GoodsReceivedNote.total_amount).label("total_purchased"),
        func.count(GoodsReceivedNote.id).label("grn_count")
    ).where(GoodsReceivedNote.tenant_id == tenant_id).group_by(GoodsReceivedNote.vendor_name)
    grn_res = await db.execute(grn_stmt)
    grn_rows = grn_res.all()

    agency_map = {}
    for r in grn_rows:
        v_name = r.vendor_name or "Unknown Distributor"
        agency_map[v_name] = {
            "agency_name": v_name,
            "total_purchases": round(float(r.total_purchased or 0.0), 2),
            "grn_count": int(r.grn_count or 0),
            "current_stock_value": 0.0,
            "total_returns": 0.0,
            "returns_count": 0,
            "batches_count": 0
        }

    # 2. Current available inventory value per vendor
    batch_stmt = select(InventoryBatch).where(
        InventoryBatch.tenant_id == tenant_id,
        InventoryBatch.quantity_available > 0
    )
    b_res = await db.execute(batch_stmt)
    batches = b_res.scalars().all()
    for b in batches:
        v_name = getattr(b, 'vendor_name', None) or "Direct Stock / Registered Vendor"
        if v_name not in agency_map:
            agency_map[v_name] = {
                "agency_name": v_name,
                "total_purchases": 0.0,
                "grn_count": 0,
                "current_stock_value": 0.0,
                "total_returns": 0.0,
                "returns_count": 0,
                "batches_count": 0
            }
        val = float(b.quantity_available or 0) * float(b.purchase_rate or 0.0)
        agency_map[v_name]["current_stock_value"] += val
        agency_map[v_name]["batches_count"] += 1

    # 3. Total returns / debit notes per vendor
    try:
        ret_stmt = select(
            PharmacyPurchaseReturn.vendor_name,
            func.sum(PharmacyPurchaseReturn.total_return_amount).label("total_returns"),
            func.count(PharmacyPurchaseReturn.id).label("ret_count")
        ).where(PharmacyPurchaseReturn.tenant_id == tenant_id).group_by(PharmacyPurchaseReturn.vendor_name)
        ret_res = await db.execute(ret_stmt)
        for r in ret_res.all():
            v_name = r.vendor_name or "Unknown Distributor"
            if v_name in agency_map:
                agency_map[v_name]["total_returns"] = round(float(r.total_returns or 0.0), 2)
                agency_map[v_name]["returns_count"] = int(r.ret_count or 0)
    except Exception:
        pass

    results = list(agency_map.values())
    for item in results:
        item["current_stock_value"] = round(item["current_stock_value"], 2)

    return {
        "status": "success",
        "count": len(results),
        "agencies": results
    }


@router.post("/returns")
@router.post("/returns/", include_in_schema=False)
async def create_purchase_return(
    payload: PurchaseReturnCreate,
    current_user: User = Depends(get_current_user),
    service: PharmacyService = Depends(get_pharmacy_service),
    db: AsyncSession = Depends(get_db)
):
    """
    Creates a Purchase Return (Debit Note) back to distributor agency
    and automatically decrements inventory stock atomically.
    """
    tenant_id = current_user.hospital_id or getattr(current_user, 'tenant_id', None)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context required")

    from app.modules.pharmacy.model import InventoryBatch, PharmacyPurchaseReturn
    from datetime import date
    import random

    return_num = f"PR-{date.today().strftime('%Y%m')}-{random.randint(1000, 9999)}"
    total_val = 0.0
    processed_items = []

    for it in payload.items:
        batch = await db.get(InventoryBatch, it.batch_id)
        if not batch or batch.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail=f"Batch {it.batch_number} ({it.item_code}) not found")

        if batch.quantity_available < it.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot return {it.quantity} units of {batch.item_name}. Only {batch.quantity_available} available in stock."
            )

        # Atomically deduct returned units from available inventory
        batch.quantity_available -= it.quantity
        rate = float(it.purchase_rate or batch.purchase_rate or 0.0)
        item_tot = round(it.quantity * rate, 2)
        total_val += item_tot

        processed_items.append({
            "batch_id": str(batch.id),
            "item_code": batch.item_code,
            "item_name": batch.item_name,
            "batch_number": batch.batch_number,
            "expiry_date": batch.expiry_date.isoformat() if batch.expiry_date else None,
            "quantity_returned": it.quantity,
            "purchase_rate": rate,
            "return_amount": item_tot,
            "reason": it.reason or payload.reason
        })

    pr = PharmacyPurchaseReturn(
        tenant_id=tenant_id,
        branch_id=payload.branch_id or getattr(current_user, 'branch_id', None),
        return_number=return_num,
        vendor_id=payload.vendor_id,
        vendor_name=payload.vendor_name,
        invoice_ref=payload.invoice_ref,
        return_date=date.today(),
        status="Approved",
        reason=payload.reason or "Near Expiry / Damaged",
        items=processed_items,
        total_return_amount=round(total_val, 2),
        notes=payload.notes,
        created_by_id=current_user.id
    )
    db.add(pr)
    await db.commit()

    return {
        "status": "success",
        "message": f"Purchase Return {return_num} approved and stock deducted.",
        "return_number": return_num,
        "total_amount": round(total_val, 2),
        "items_count": len(processed_items)
    }


@router.get("/returns")
@router.get("/returns/", include_in_schema=False)
async def list_purchase_returns(
    vendor_id: Optional[UUID] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List purchase returns / debit notes issued to agencies."""
    tenant_id = current_user.hospital_id or getattr(current_user, 'tenant_id', None)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context required")

    from sqlalchemy import select
    from app.modules.pharmacy.model import PharmacyPurchaseReturn

    stmt = select(PharmacyPurchaseReturn).where(PharmacyPurchaseReturn.tenant_id == tenant_id)
    if vendor_id:
        stmt = stmt.where(PharmacyPurchaseReturn.vendor_id == vendor_id)
    stmt = stmt.order_by(PharmacyPurchaseReturn.created_at.desc())

    res = await db.execute(stmt)
    returns = res.scalars().all()
    return returns


@router.get("/vendors/{vendor_id}/ledger")
@router.get("/vendors/{vendor_id}/ledger/", include_in_schema=False)
async def get_vendor_ledger(
    vendor_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Calculates running financial statement for a distributor vendor:
    Bills (GRNs) vs Returns (Debit Notes) vs Net Payable.
    """
    tenant_id = current_user.hospital_id or getattr(current_user, 'tenant_id', None)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context required")

    from sqlalchemy import select
    from app.modules.pharmacy.model import PharmacyVendor, GoodsReceivedNote, PharmacyPurchaseReturn

    vendor = await db.get(PharmacyVendor, vendor_id)
    if not vendor or vendor.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Vendor not found")

    grn_stmt = select(GoodsReceivedNote).where(
        GoodsReceivedNote.tenant_id == tenant_id,
        GoodsReceivedNote.vendor_name == vendor.name
    ).order_by(GoodsReceivedNote.created_at.asc())
    grn_res = await db.execute(grn_stmt)
    grns = grn_res.scalars().all()

    ret_stmt = select(PharmacyPurchaseReturn).where(
        PharmacyPurchaseReturn.tenant_id == tenant_id,
        PharmacyPurchaseReturn.vendor_name == vendor.name
    ).order_by(PharmacyPurchaseReturn.created_at.asc())
    ret_res = await db.execute(ret_stmt)
    returns = ret_res.scalars().all()

    total_bills = sum(float(g.total_amount or 0.0) for g in grns)
    total_debit_notes = sum(float(r.total_return_amount or 0.0) for r in returns)
    net_payable = round(total_bills - total_debit_notes, 2)

    return {
        "vendor_id": str(vendor.id),
        "vendor_name": vendor.name,
        "gst_number": vendor.gst_number,
        "contact_phone": vendor.contact_phone,
        "total_bills_invoiced": round(total_bills, 2),
        "total_returns_credited": round(total_debit_notes, 2),
        "net_balance_due": net_payable,
        "invoices_count": len(grns),
        "returns_count": len(returns),
        "recent_invoices": [
            {
                "grn_number": g.grn_number,
                "invoice_number": g.invoice_number,
                "invoice_date": g.invoice_date.isoformat() if g.invoice_date else None,
                "amount": float(g.total_amount or 0.0)
            } for g in grns[-10:]
        ],
        "recent_returns": [
            {
                "return_number": r.return_number,
                "return_date": r.return_date.isoformat() if r.return_date else None,
                "amount": float(r.total_return_amount or 0.0),
                "reason": r.reason
            } for r in returns[-10:]
        ]
    }
