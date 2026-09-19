import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional

from app.core.database import get_db
from app.modules.ipd.service import IPDService
from app.modules.ipd.schemas import (
    WardCreate, WardUpdate, BedCreate, BedUpdate, BedStatusUpdate,
    AdmissionCreate, DischargeRequest, TransferBedRequest,
    NursingTaskCreate, NursingTaskComplete
)

router = APIRouter(prefix="/ipd", tags=["IPD (Clean Architecture)"])

def get_ipd_service(db: AsyncSession = Depends(get_db)) -> IPDService:
    return IPDService(db)

@router.get("/wards")
async def list_wards(service: IPDService = Depends(get_ipd_service)):
    return await service.list_wards()

@router.post("/wards", status_code=201)
async def create_ward(payload: WardCreate, service: IPDService = Depends(get_ipd_service)):
    return await service.create_ward(payload)

@router.put("/wards/{ward_id}")
async def update_ward(ward_id: UUID, payload: WardUpdate, service: IPDService = Depends(get_ipd_service)):
    try:
        return await service.update_ward(ward_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/wards/{ward_id}")
async def delete_ward(ward_id: UUID, service: IPDService = Depends(get_ipd_service)):
    try:
        return await service.delete_ward(ward_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/beds")
async def list_beds(
    ward_id: Optional[UUID] = None,
    status: Optional[str] = None,
    service: IPDService = Depends(get_ipd_service),
):
    return await service.list_beds(ward_id, status)

@router.patch("/beds/{bed_id}/status")
async def update_bed_status(bed_id: UUID, payload: BedStatusUpdate, service: IPDService = Depends(get_ipd_service)):
    try:
        return await service.update_bed_status(bed_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/admissions", status_code=201)
async def admit_patient(payload: AdmissionCreate, service: IPDService = Depends(get_ipd_service)):
    try:
        return await service.admit_patient(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/admissions/{admission_id}/discharge")
async def discharge_patient(admission_id: UUID, payload: DischargeRequest, service: IPDService = Depends(get_ipd_service)):
    try:
        return await service.discharge_patient(admission_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
