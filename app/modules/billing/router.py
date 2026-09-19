from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID

from app.core.database import get_db
from app.core.models import User
from app.core.dependencies import get_current_user
from app.modules.billing.schemas import InvoiceCreate, InvoiceResponse, PaymentRequest, TreatmentPackageSchema
from app.modules.billing.service import BillingService
from app.modules.billing.exceptions import InvoiceNotFoundError, InsufficientWalletBalanceError

router = APIRouter(prefix="/billing", tags=["Billing (Clean Architecture)"])

def get_billing_service(db: AsyncSession = Depends(get_db)) -> BillingService:
    return BillingService(db)

@router.get("/service-catalog")
async def get_service_catalog(
    service_type: str = None,
    q: str = None,
    current_user: User = Depends(get_current_user),
    service: BillingService = Depends(get_billing_service),
):
    return service.get_service_catalog(service_type, q)

@router.post("/invoices", response_model=InvoiceResponse, status_code=201)
async def create_invoice(
    data: InvoiceCreate,
    current_user: User = Depends(get_current_user),
    service: BillingService = Depends(get_billing_service),
):
    try:
        tenant_id = current_user.tenant_id
        if not tenant_id:
            from app.core.models import Hospital
            from sqlalchemy import select
            result = await service.db.execute(select(Hospital).limit(1))
            hospital = result.scalar_one_or_none()
            tenant_id = hospital.id if hospital else None
        
        # Override created_by with current user if not provided
        if not data.created_by:
            data.created_by = current_user.id
            
        return await service.create_invoice(data, tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InsufficientWalletBalanceError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/invoices", response_model=list[InvoiceResponse])
async def list_invoices(
    status: Optional[str] = Query(None),
    patient_id: Optional[UUID] = Query(None),
    appointment_source: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    service: BillingService = Depends(get_billing_service),
):
    filters = {
        "status": status,
        "patient_id": patient_id,
        "appointment_source": appointment_source
    }
    return await service.list_invoices(filters, current_user.tenant_id)

@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: UUID,
    current_user: User = Depends(get_current_user),
    service: BillingService = Depends(get_billing_service),
):
    try:
        return await service.get_invoice(invoice_id)
    except InvoiceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/invoices/{invoice_id}/pay", response_model=InvoiceResponse)
@router.post("/invoices/{invoice_id}/payment", response_model=InvoiceResponse)
async def add_invoice_payment(
    invoice_id: UUID,
    payload: PaymentRequest,
    current_user: User = Depends(get_current_user),
    service: BillingService = Depends(get_billing_service),
):
    try:
        return await service.record_payment(invoice_id, payload)
    except InvoiceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/packages", response_model=list[TreatmentPackageSchema])
async def list_packages(
    plugin_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    service: BillingService = Depends(get_billing_service),
):
    return await service.list_packages(plugin_id)

@router.post("/packages", response_model=TreatmentPackageSchema, status_code=201)
async def create_package(
    data: TreatmentPackageSchema,
    current_user: User = Depends(get_current_user),
    service: BillingService = Depends(get_billing_service),
):
    tenant_id = current_user.tenant_id
    if not tenant_id:
        from app.core.models import Hospital
        from sqlalchemy import select
        result = await service.db.execute(select(Hospital).limit(1))
        hospital = result.scalar_one_or_none()
        tenant_id = hospital.id if hospital else None
    return await service.create_package(data, tenant_id)
