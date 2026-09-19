from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import date

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.models import User
from app.modules.appointments.schemas import AppointmentCreate, AppointmentUpdate, AppointmentResponse, AppointmentListResponse, TriageUpdate
from app.modules.appointments.service import AppointmentService
from app.modules.appointments.exceptions import AppointmentNotFoundError, InvalidAppointmentDateError, ActiveAppointmentExistsError

router = APIRouter(prefix="/appointments", tags=["Appointments (Clean Architecture)"])

def get_appointment_service(db: AsyncSession = Depends(get_db)) -> AppointmentService:
    return AppointmentService(db)

@router.post("", response_model=AppointmentResponse, status_code=201)
@router.post("/", response_model=AppointmentResponse, status_code=201)
async def create_appointment(
    data: AppointmentCreate,
    current_user: User = Depends(get_current_user),
    service: AppointmentService = Depends(get_appointment_service),
):
    try:
        tenant_id = current_user.tenant_id
        if not tenant_id:
            from app.core.models import Hospital
            from sqlalchemy import select
            result = await service.db.execute(select(Hospital).limit(1))
            hospital = result.scalar_one_or_none()
            tenant_id = hospital.id if hospital else None
            
        return await service.create_appointment(data, tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (InvalidAppointmentDateError, ActiveAppointmentExistsError) as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("", response_model=AppointmentListResponse)
@router.get("/", response_model=AppointmentListResponse)
async def list_appointments(
    date_filter: date = Query(None),
    status: str = Query(None),
    gender: str = Query(None),
    department: str = Query(None),
    branch_id: UUID = Query(None),
    patient_id: UUID = Query(None),
    current_user: User = Depends(get_current_user),
    service: AppointmentService = Depends(get_appointment_service),
):
    filters = {
        "date_filter": date_filter,
        "status": status,
        "gender": gender,
        "department": department,
        "branch_id": branch_id,
        "patient_id": patient_id
    }
    return await service.list_appointments(filters, current_user.tenant_id)

@router.get("/{appointment_id}", response_model=AppointmentResponse)
async def get_appointment(
    appointment_id: UUID,
    current_user: User = Depends(get_current_user),
    service: AppointmentService = Depends(get_appointment_service),
):
    try:
        return await service.get_appointment(appointment_id)
    except AppointmentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.patch("/{appointment_id}/triage")
async def update_triage(
    appointment_id: UUID,
    data: TriageUpdate,
    current_user: User = Depends(get_current_user),
    service: AppointmentService = Depends(get_appointment_service),
):
    try:
        return await service.update_triage(appointment_id, data, current_user.id)
    except AppointmentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.patch("/{appointment_id}", response_model=AppointmentResponse)
async def update_appointment(
    appointment_id: UUID,
    data: AppointmentUpdate,
    current_user: User = Depends(get_current_user),
    service: AppointmentService = Depends(get_appointment_service),
):
    try:
        return await service.update_appointment(appointment_id, data)
    except AppointmentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidAppointmentDateError as e:
        raise HTTPException(status_code=400, detail=str(e))
