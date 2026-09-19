from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID
from datetime import date

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_branch_context
from app.core.models import User
from app.modules.patients.schemas import (
    PatientCreate,
    PatientUpdate,
    PatientResponse,
    PatientListResponse,
    LinkPartnerRequest,
    ConsentCreate,
)
from app.modules.patients.service import PatientService
from app.modules.patients.exceptions import PatientNotFoundError, PartnerLinkError

router = APIRouter(prefix="/patients", tags=["Patients (Clean Architecture)"])


def get_patient_service(db: AsyncSession = Depends(get_db)) -> PatientService:
    return PatientService(db)


@router.post("", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
async def create_patient(
    patient_data: PatientCreate,
    current_user: User = Depends(get_current_user),
    service: PatientService = Depends(get_patient_service),
):
    if not current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not associated with an active hospital tenant")
    return await service.create_patient(patient_data, current_user.tenant_id)


@router.get("", response_model=PatientListResponse)
@router.get("/", response_model=PatientListResponse)
async def list_patients(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=1000),
    search: Optional[str] = Query(None),
    branch_id: Optional[UUID] = Depends(get_branch_context),
    current_user: User = Depends(get_current_user),
    service: PatientService = Depends(get_patient_service),
):
    if not current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not associated with an active hospital tenant")
    return await service.list_patients(
        tenant_id=current_user.tenant_id,
        branch_id=branch_id,
        page=page,
        per_page=per_page,
        search=search,
    )


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


@router.post("/{patient_id}/consents", status_code=status.HTTP_201_CREATED)
@router.post("/{patient_id}/consents/", status_code=status.HTTP_201_CREATED)
async def save_patient_consent(
    patient_id: UUID,
    consent_data: ConsentCreate,
    current_user: User = Depends(get_current_user),
    service: PatientService = Depends(get_patient_service),
):
    """Sign and record statutory ART / Clinical consent form."""
    try:
        return await service.save_consent(patient_id, consent_data, current_user)
    except PatientNotFoundError:
        raise HTTPException(status_code=404, detail="Patient not found")
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
