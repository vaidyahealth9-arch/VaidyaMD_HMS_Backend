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
    AdmissionCreate, DischargeRequest, TransferBedRequest,
    NursingTaskCreate, NursingTaskComplete
)

router = APIRouter(
    prefix="/ipd",
    tags=["IPD (Clean Architecture)"],
    dependencies=[Depends(get_current_user), Depends(require_active_plugin("ipd"))],
)

def get_ipd_service(db: AsyncSession = Depends(get_db)) -> IPDService:
    return IPDService(db)

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

@router.post("/admissions", status_code=status.HTTP_201_CREATED)
@router.post("/admissions/", status_code=status.HTTP_201_CREATED)
async def admit_patient(
    payload: AdmissionCreate,
    current_user: User = Depends(get_current_user),
    service: IPDService = Depends(get_ipd_service),
):
    try:
        return await service.admit_patient(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

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
