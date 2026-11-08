import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional

from app.core.database import get_db
from app.core.models import User
from app.core.dependencies import get_current_user, require_active_plugin
from app.modules.ipd.service import IPDService
from app.modules.ipd.schemas import (
    WardCreate, WardUpdate, BedCreate, BedUpdate, BedStatusUpdate,
    AdmissionCreate, AdmissionUpdate, DischargeRequest, TransferBedRequest,
    DischargeSummarySave, NursingTaskCreate, NursingTaskComplete,
    RoundNoteCreate, OrderCreate, OrderStatusUpdate, OrderAdministerPayload,
    FluidBalanceCreate, BillItemCreate, PaymentCreate, SettleBillItemsRequest
)

router = APIRouter(
    prefix="/ipd",
    tags=["IPD (Inpatient Department)"],
    dependencies=[Depends(get_current_user), Depends(require_active_plugin("ipd"))],
)

def get_ipd_service(db: AsyncSession = Depends(get_db)) -> IPDService:
    return IPDService(db)

# -----------------------------------------------------------------------------
# WARDS
# -----------------------------------------------------------------------------
@router.get("/wards")
@router.get("/wards/")
async def list_wards(
    current_user: User = Depends(get_current_user),
    service: IPDService = Depends(get_ipd_service),
):
    return await service.list_wards(tenant_id=current_user.tenant_id)

@router.post("/wards", status_code=status.HTTP_201_CREATED)
@router.post("/wards/", status_code=status.HTTP_201_CREATED)
async def create_ward(
    payload: WardCreate,
    current_user: User = Depends(get_current_user),
    service: IPDService = Depends(get_ipd_service),
):
    return await service.create_ward(payload, tenant_id=current_user.tenant_id)

@router.put("/wards/{ward_id}")
@router.patch("/wards/{ward_id}")
async def update_ward(
    ward_id: UUID,
    payload: WardUpdate,
    current_user: User = Depends(get_current_user),
    service: IPDService = Depends(get_ipd_service),
):
    try:
        return await service.update_ward(ward_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/wards/{ward_id}")
async def delete_ward(
    ward_id: UUID,
    current_user: User = Depends(get_current_user),
    service: IPDService = Depends(get_ipd_service),
):
    try:
        return await service.delete_ward(ward_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# -----------------------------------------------------------------------------
# BEDS
# -----------------------------------------------------------------------------
@router.get("/beds")
@router.get("/beds/")
async def list_beds(
    ward_id: Optional[UUID] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    service: IPDService = Depends(get_ipd_service),
):
    return await service.list_beds(ward_id=ward_id, status=status, tenant_id=current_user.tenant_id)

@router.post("/beds", status_code=status.HTTP_201_CREATED)
@router.post("/beds/", status_code=status.HTTP_201_CREATED)
async def create_bed(
    payload: BedCreate,
    current_user: User = Depends(get_current_user),
    service: IPDService = Depends(get_ipd_service),
):
    try:
        return await service.create_bed(payload, tenant_id=current_user.tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/beds/{bed_id}")
@router.patch("/beds/{bed_id}")
async def update_bed(
    bed_id: UUID,
    payload: BedUpdate,
    current_user: User = Depends(get_current_user),
    service: IPDService = Depends(get_ipd_service),
):
    try:
        return await service.update_bed(bed_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/beds/{bed_id}")
async def delete_bed(
    bed_id: UUID,
    current_user: User = Depends(get_current_user),
    service: IPDService = Depends(get_ipd_service),
):
    try:
        return await service.delete_bed(bed_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/beds/{bed_id}/status")
async def update_bed_status(
    bed_id: UUID,
    payload: BedStatusUpdate,
    current_user: User = Depends(get_current_user),
    service: IPDService = Depends(get_ipd_service),
):
    try:
        return await service.update_bed_status(bed_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# -----------------------------------------------------------------------------
# ADMISSIONS
# -----------------------------------------------------------------------------
@router.get("/admissions")
@router.get("/admissions/")
async def list_admissions(
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    service: IPDService = Depends(get_ipd_service),
):
    return await service.list_admissions(status=status, tenant_id=current_user.tenant_id)

@router.post("/admissions", status_code=status.HTTP_201_CREATED)
@router.post("/admissions/", status_code=status.HTTP_201_CREATED)
async def admit_patient(
    payload: AdmissionCreate,
    current_user: User = Depends(get_current_user),
    service: IPDService = Depends(get_ipd_service),
):
    try:
        return await service.admit_patient(
            payload,
            tenant_id=current_user.tenant_id,
            branch_id=current_user.branch_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/admissions/{admission_id}")
@router.get("/admissions/{admission_id}/")
async def get_admission_details(
    admission_id: UUID,
    current_user: User = Depends(get_current_user),
    service: IPDService = Depends(get_ipd_service),
):
    try:
        return await service.get_admission_details(admission_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.patch("/admissions/{admission_id}")
@router.put("/admissions/{admission_id}")
async def update_admission(
    admission_id: UUID,
    payload: AdmissionUpdate,
    current_user: User = Depends(get_current_user),
    service: IPDService = Depends(get_ipd_service),
):
    try:
        return await service.update_admission(admission_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/admissions/{admission_id}/transfer-bed")
@router.post("/admissions/{admission_id}/transfer-bed/")
async def transfer_bed(
    admission_id: UUID,
    payload: TransferBedRequest,
    current_user: User = Depends(get_current_user),
    service: IPDService = Depends(get_ipd_service),
):
    try:
        return await service.transfer_bed(admission_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/admissions/{admission_id}/discharge-summary")
@router.get("/admissions/{admission_id}/discharge-summary/")
async def get_discharge_summary(
    admission_id: UUID,
    current_user: User = Depends(get_current_user),
    service: IPDService = Depends(get_ipd_service),
):
    try:
        return await service.calculate_discharge_summary(admission_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/admissions/{admission_id}/save-discharge-summary")
@router.post("/admissions/{admission_id}/save-discharge-summary/")
async def save_discharge_summary(
    admission_id: UUID,
    payload: DischargeSummarySave,
    current_user: User = Depends(get_current_user),
    service: IPDService = Depends(get_ipd_service),
):
    try:
        return await service.save_discharge_summary(admission_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/admissions/{admission_id}/discharge")
@router.post("/admissions/{admission_id}/discharge/")
async def discharge_patient(
    admission_id: UUID,
    payload: DischargeRequest,
    current_user: User = Depends(get_current_user),
    service: IPDService = Depends(get_ipd_service),
):
    try:
        return await service.discharge_patient(admission_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# -----------------------------------------------------------------------------
# DOCTOR ROUND NOTES (SOAP)
# -----------------------------------------------------------------------------
@router.get("/admissions/{admission_id}/round-notes")
async def list_round_notes(
    admission_id: UUID,
    current_user: User = Depends(get_current_user),
    service: IPDService = Depends(get_ipd_service),
):
    return await service.list_round_notes(admission_id)

@router.post("/admissions/{admission_id}/round-notes", status_code=status.HTTP_201_CREATED)
async def add_round_note(
    admission_id: UUID,
    payload: RoundNoteCreate,
    current_user: User = Depends(get_current_user),
    service: IPDService = Depends(get_ipd_service),
):
    try:
        return await service.add_round_note(admission_id, payload, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# -----------------------------------------------------------------------------
# BEDSIDE ORDERS & eMAR
# -----------------------------------------------------------------------------
@router.get("/admissions/{admission_id}/orders")
async def list_orders(
    admission_id: UUID,
    current_user: User = Depends(get_current_user),
    service: IPDService = Depends(get_ipd_service),
):
    return await service.list_orders(admission_id)

@router.post("/admissions/{admission_id}/orders", status_code=status.HTTP_201_CREATED)
async def create_order(
    admission_id: UUID,
    payload: OrderCreate,
    current_user: User = Depends(get_current_user),
    service: IPDService = Depends(get_ipd_service),
):
    try:
        return await service.create_order(admission_id, payload, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/orders/{order_id}/status")
async def update_order_status(
    order_id: UUID,
    payload: OrderStatusUpdate,
    current_user: User = Depends(get_current_user),
    service: IPDService = Depends(get_ipd_service),
):
    try:
        return await service.update_order_status(order_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/orders/{order_id}/administer")
async def administer_order(
    order_id: UUID,
    payload: OrderAdministerPayload,
    current_user: User = Depends(get_current_user),
    service: IPDService = Depends(get_ipd_service),
):
    try:
        return await service.administer_order(order_id, payload, current_user)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# -----------------------------------------------------------------------------
# FLUID BALANCE (INTAKE / OUTPUT)
# -----------------------------------------------------------------------------
@router.get("/admissions/{admission_id}/fluid-balance")
async def list_fluid_balances(
    admission_id: UUID,
    current_user: User = Depends(get_current_user),
    service: IPDService = Depends(get_ipd_service),
):
    return await service.list_fluid_balances(admission_id)

@router.post("/admissions/{admission_id}/fluid-balance", status_code=status.HTTP_201_CREATED)
async def add_fluid_balance(
    admission_id: UUID,
    payload: FluidBalanceCreate,
    current_user: User = Depends(get_current_user),
    service: IPDService = Depends(get_ipd_service),
):
    try:
        return await service.add_fluid_balance(admission_id, payload, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# -----------------------------------------------------------------------------
# NURSING TASKS & VITALS
# -----------------------------------------------------------------------------
@router.get("/nursing-tasks")
@router.get("/nursing-tasks/")
async def list_nursing_tasks(
    admission_id: Optional[UUID] = None,
    bed_id: Optional[UUID] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    service: IPDService = Depends(get_ipd_service),
):
    return await service.list_nursing_tasks(
        admission_id=admission_id,
        bed_id=bed_id,
        status=status,
        tenant_id=current_user.tenant_id,
    )

@router.post("/nursing-tasks", status_code=status.HTTP_201_CREATED)
@router.post("/nursing-tasks/", status_code=status.HTTP_201_CREATED)
async def create_nursing_task(
    payload: NursingTaskCreate,
    current_user: User = Depends(get_current_user),
    service: IPDService = Depends(get_ipd_service),
):
    try:
        return await service.create_nursing_task(
            payload,
            tenant_id=current_user.tenant_id,
            branch_id=current_user.branch_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/nursing-tasks/{task_id}/complete")
@router.post("/nursing-tasks/{task_id}/complete/")
async def complete_nursing_task(
    task_id: UUID,
    payload: NursingTaskComplete,
    current_user: User = Depends(get_current_user),
    service: IPDService = Depends(get_ipd_service),
):
    try:
        return await service.complete_nursing_task(
            task_id,
            payload,
            user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# -----------------------------------------------------------------------------
# NIGHTLY CHARGES ACCRUAL
# -----------------------------------------------------------------------------
@router.post("/accrue-daily-charges")
@router.post("/accrue-daily-charges/")
async def accrue_daily_charges(
    current_user: User = Depends(get_current_user),
    service: IPDService = Depends(get_ipd_service),
):
    return await service.accrue_daily_charges(tenant_id=current_user.tenant_id)

# -----------------------------------------------------------------------------
# ROLLING BILL & PAYMENTS
# -----------------------------------------------------------------------------
@router.get("/admissions/{admission_id}/rolling-bill")
@router.get("/admissions/{admission_id}/rolling-bill/")
async def get_rolling_bill(
    admission_id: UUID,
    current_user: User = Depends(get_current_user),
    service: IPDService = Depends(get_ipd_service),
):
    try:
        return await service.get_rolling_bill_summary(admission_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/admissions/{admission_id}/bill-items")
@router.get("/admissions/{admission_id}/bill-items/")
async def list_bill_items(
    admission_id: UUID,
    item_type: Optional[str] = None,
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    service: IPDService = Depends(get_ipd_service),
):
    return await service.list_bill_items(admission_id, item_type=item_type, category=category)

@router.post("/admissions/{admission_id}/bill-items", status_code=status.HTTP_201_CREATED)
@router.post("/admissions/{admission_id}/bill-items/", status_code=status.HTTP_201_CREATED)
async def post_bill_item(
    admission_id: UUID,
    payload: BillItemCreate,
    current_user: User = Depends(get_current_user),
    service: IPDService = Depends(get_ipd_service),
):
    try:
        return await service.post_bill_item(admission_id, payload, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/bill-items/{item_id}")
@router.delete("/bill-items/{item_id}/")
async def delete_bill_item(
    item_id: UUID,
    current_user: User = Depends(get_current_user),
    service: IPDService = Depends(get_ipd_service),
):
    try:
        return await service.delete_bill_item(item_id, current_user)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/admissions/{admission_id}/payments")
@router.get("/admissions/{admission_id}/payments/")
async def list_admission_payments(
    admission_id: UUID,
    current_user: User = Depends(get_current_user),
    service: IPDService = Depends(get_ipd_service),
):
    return await service.list_payments(admission_id)

@router.post("/admissions/{admission_id}/payments", status_code=status.HTTP_201_CREATED)
@router.post("/admissions/{admission_id}/payments/", status_code=status.HTTP_201_CREATED)
async def post_advance_payment(
    admission_id: UUID,
    payload: PaymentCreate,
    current_user: User = Depends(get_current_user),
    service: IPDService = Depends(get_ipd_service),
):
    try:
        return await service.post_advance_payment(admission_id, payload, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/admissions/{admission_id}/settle-invoice")
@router.post("/admissions/{admission_id}/settle-invoice/")
async def settle_invoice(
    admission_id: UUID,
    payload: SettleBillItemsRequest,
    current_user: User = Depends(get_current_user),
    service: IPDService = Depends(get_ipd_service),
):
    try:
        return await service.settle_bill_items(admission_id, payload, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
