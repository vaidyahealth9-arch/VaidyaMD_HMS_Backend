from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID
from datetime import date

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.models import User
from app.modules.patients.schemas import PatientCreate, PatientUpdate, PatientResponse, PatientListResponse, LinkPartnerRequest
from app.modules.patients.service import PatientService
from app.modules.patients.exceptions import PatientNotFoundError, PartnerLinkError

router = APIRouter(prefix="/patients", tags=["Patients (Clean Architecture)"])

def get_patient_service(db: AsyncSession = Depends(get_db)) -> PatientService:
    return PatientService(db)

@router.post("", response_model=PatientResponse, status_code=201)
@router.post("/", response_model=PatientResponse, status_code=201)
async def create_patient(
    patient_data: PatientCreate,
    current_user: User = Depends(get_current_user),
    service: PatientService = Depends(get_patient_service),
):
    tenant_id = current_user.tenant_id
    if not tenant_id:
        # Fallback for dev environment without tenant selection
        from app.core.models import Hospital
        from sqlalchemy import select
        result = await service.db.execute(select(Hospital).limit(1))
        hospital = result.scalar_one_or_none()
        if not hospital:
            raise HTTPException(status_code=500, detail="No hospital tenant found")
        tenant_id = hospital.id
        
    return await service.create_patient(patient_data, tenant_id)

@router.get("", response_model=PatientListResponse)
@router.get("/", response_model=PatientListResponse)
async def list_patients(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=1000),
    search: Optional[str] = Query(None),
    branch_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_user),
    service: PatientService = Depends(get_patient_service),
):
    tenant_id = current_user.tenant_id
    if not tenant_id:
        from app.core.models import Hospital
        from sqlalchemy import select
        result = await service.db.execute(select(Hospital).limit(1))
        hospital = result.scalar_one_or_none()
        if not hospital:
            raise HTTPException(status_code=500, detail="No hospital tenant found")
        tenant_id = hospital.id
        
    return await service.list_patients(tenant_id=tenant_id, branch_id=branch_id, page=page, per_page=per_page, search=search)


@router.get("/{patient_id}/timeline")
async def get_patient_timeline(
    patient_id: UUID,
    current_user: User = Depends(get_current_user),
    service: PatientService = Depends(get_patient_service),
):
    """Retrieve full chronological patient journey timeline."""
    return await service.get_timeline(patient_id)

@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(
    patient_id: UUID,
    current_user: User = Depends(get_current_user),
    service: PatientService = Depends(get_patient_service),
):
    try:
        return await service.get_patient(patient_id)
    except PatientNotFoundError:
        raise HTTPException(status_code=404, detail="Patient not found")

@router.get("/{patient_id}/couple")
async def get_couple_profile(
    patient_id: UUID,
    current_user: User = Depends(get_current_user),
    service: PatientService = Depends(get_patient_service),
):
    try:
        return await service.get_couple_profile(patient_id)
    except PatientNotFoundError:
        raise HTTPException(status_code=404, detail="Patient not found")

@router.post("/{patient_id}/link-partner", response_model=PatientResponse)
async def link_partner(
    patient_id: UUID,
    req: LinkPartnerRequest,
    current_user: User = Depends(get_current_user),
    service: PatientService = Depends(get_patient_service),
):
    try:
        return await service.link_partner(patient_id, req.partner_id)
    except PatientNotFoundError:
        raise HTTPException(status_code=404, detail="Patient or Partner not found")
    except PartnerLinkError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{patient_id}/unlink-partner")
async def unlink_partner(
    patient_id: UUID,
    current_user: User = Depends(get_current_user),
    service: PatientService = Depends(get_patient_service),
):
    try:
        await service.unlink_partner(patient_id)
        return {"message": "Partner unlinked successfully", "patient_id": str(patient_id)}
    except PatientNotFoundError:
        raise HTTPException(status_code=404, detail="Patient not found")

@router.put("/{patient_id}", response_model=PatientResponse)
@router.patch("/{patient_id}", response_model=PatientResponse)
async def update_patient(
    patient_id: UUID,
    patient_data: PatientUpdate,
    current_user: User = Depends(get_current_user),
    service: PatientService = Depends(get_patient_service),
):
    try:
        return await service.update_patient(patient_id, patient_data)
    except PatientNotFoundError:
        raise HTTPException(status_code=404, detail="Patient not found")

