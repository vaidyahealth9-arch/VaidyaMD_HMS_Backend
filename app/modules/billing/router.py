from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID

from app.core.database import get_db
from app.core.models import User
from app.core.dependencies import get_current_user
from app.modules.billing.schemas import (
    InvoiceCreate,
    InvoiceResponse,
    PaymentRequest,
    TreatmentPackageSchema,
    TreatmentPackageUpdate,
    ServiceItemCreate,
    ServiceItemUpdate,
    PatientPackageAssignRequest,
    PatientPackageConsumeRequest,
    PatientPackageResponse,
)
from app.modules.billing.service import BillingService
from app.modules.billing.exceptions import InvoiceNotFoundError, InsufficientWalletBalanceError

router = APIRouter(prefix="/billing", tags=["Billing (Clean Architecture)"])

def get_billing_service(db: AsyncSession = Depends(get_db)) -> BillingService:
    return BillingService(db)

def check_admin(user: User):
    role = (user.role.value if hasattr(user.role, "value") else str(user.role)).lower()
    if role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super-Admin privileges required")

@router.get("/service-catalog")
async def get_service_catalog(
    service_type: str = None,
    q: str = None,
    current_user: User = Depends(get_current_user),
    service: BillingService = Depends(get_billing_service),
):
    return await service.get_service_catalog(
        tenant_id=current_user.tenant_id,
        branch_id=current_user.branch_id,
        service_type=service_type,
        q=q,
    )

@router.post("/service-catalog", status_code=status.HTTP_201_CREATED)
async def create_service_item(
    data: ServiceItemCreate,
    current_user: User = Depends(get_current_user),
    service: BillingService = Depends(get_billing_service),
):
    check_admin(current_user)
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="Tenant context required")
    item = await service.create_service_item(data, current_user.tenant_id)
    return {
        "id": str(item.id),
        "code": item.code,
        "name": item.name,
        "category": item.category,
        "base_price": float(item.base_price),
        "hsn_sac": item.hsn_sac,
        "gst_rate": float(item.gst_rate) if item.gst_rate is not None else 0.0,
        "is_active": item.is_active,
    }

@router.put("/service-catalog/{item_id}")
async def update_service_item(
    item_id: UUID,
    data: ServiceItemUpdate,
    current_user: User = Depends(get_current_user),
    service: BillingService = Depends(get_billing_service),
):
    check_admin(current_user)
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="Tenant context required")
    try:
        item = await service.update_service_item(item_id, data, current_user.tenant_id)
        return {
            "id": str(item.id),
            "code": item.code,
            "name": item.name,
            "category": item.category,
            "base_price": float(item.base_price),
            "hsn_sac": item.hsn_sac,
            "gst_rate": float(item.gst_rate) if item.gst_rate is not None else 0.0,
            "is_active": item.is_active,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/service-catalog/{item_id}")
async def delete_service_item(
    item_id: UUID,
    current_user: User = Depends(get_current_user),
    service: BillingService = Depends(get_billing_service),
):
    check_admin(current_user)
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="Tenant context required")
    success = await service.delete_service_item(item_id, current_user.tenant_id)
    if not success:
        raise HTTPException(status_code=404, detail="Service item not found")
    return {"status": "success", "message": "Service item deactivated successfully"}

@router.post("/invoices", response_model=InvoiceResponse, status_code=201)
async def create_invoice(
    data: InvoiceCreate,
    current_user: User = Depends(get_current_user),
    service: BillingService = Depends(get_billing_service),
):
    try:
        if not current_user.tenant_id:
            raise HTTPException(status_code=403, detail="User is not associated with an active hospital tenant")
        tenant_id = current_user.tenant_id

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
    except InsufficientWalletBalanceError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/packages", response_model=list[TreatmentPackageSchema])
@router.get("/packages/", response_model=list[TreatmentPackageSchema], include_in_schema=False)
async def list_packages(
    plugin_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    service: BillingService = Depends(get_billing_service),
):
    return await service.list_packages(plugin_id, tenant_id=current_user.tenant_id)

@router.post("/packages", response_model=TreatmentPackageSchema, status_code=201)
@router.post("/packages/", response_model=TreatmentPackageSchema, status_code=201, include_in_schema=False)
async def create_package(
    data: TreatmentPackageSchema,
    current_user: User = Depends(get_current_user),
    service: BillingService = Depends(get_billing_service),
):
    check_admin(current_user)
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context required to create packages")
    return await service.create_package(data, current_user.tenant_id)

@router.put("/packages/{package_id}", response_model=TreatmentPackageSchema)
async def update_package(
    package_id: UUID,
    data: TreatmentPackageUpdate,
    current_user: User = Depends(get_current_user),
    service: BillingService = Depends(get_billing_service),
):
    check_admin(current_user)
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context required")
    try:
        return await service.update_package(package_id, data, current_user.tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/packages/{package_id}")
async def delete_package(
    package_id: UUID,
    current_user: User = Depends(get_current_user),
    service: BillingService = Depends(get_billing_service),
):
    check_admin(current_user)
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context required")
    success = await service.delete_package(package_id, current_user.tenant_id)
    if not success:
        raise HTTPException(status_code=404, detail="Treatment package not found")
    return {"status": "success", "message": "Treatment package deactivated successfully"}


# ---------------------------------------------------------
# Patient Package Allocations & Service Quota Deductions
# ---------------------------------------------------------

@router.post("/patient-packages/assign", response_model=PatientPackageResponse, status_code=201)
@router.post("/patient-packages", response_model=PatientPackageResponse, status_code=201, include_in_schema=False)
async def assign_patient_package(
    data: PatientPackageAssignRequest,
    current_user: User = Depends(get_current_user),
    service: BillingService = Depends(get_billing_service),
):
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context required")
    try:
        return await service.assign_patient_package(data, current_user.tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/patient-packages/patient/{patient_id}", response_model=list[PatientPackageResponse])
async def get_patient_packages(
    patient_id: UUID,
    current_user: User = Depends(get_current_user),
    service: BillingService = Depends(get_billing_service),
):
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context required")
    return await service.get_patient_packages(patient_id, current_user.tenant_id)


@router.post("/patient-packages/{package_id}/consume", response_model=PatientPackageResponse)
async def consume_package_service(
    package_id: UUID,
    data: PatientPackageConsumeRequest,
    current_user: User = Depends(get_current_user),
    service: BillingService = Depends(get_billing_service),
):
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context required")
    try:
        return await service.consume_package_service(package_id, data, current_user.tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

