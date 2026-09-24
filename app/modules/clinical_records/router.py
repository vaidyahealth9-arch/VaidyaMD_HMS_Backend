from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from uuid import UUID
from typing import Optional

from app.core.database import get_db
from app.core.models import ClinicalRecord, Patient, User
from app.core.dependencies import get_current_user
from app.modules.clinical_records.schemas import ClinicalRecordCreate, ClinicalRecordResponse

router = APIRouter(prefix="/clinical-records", tags=["Clinical Records (Core EMR)"], dependencies=[Depends(get_current_user)])

@router.post("", response_model=ClinicalRecordResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=ClinicalRecordResponse, status_code=status.HTTP_201_CREATED)
async def create_clinical_record(
    data: ClinicalRecordCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Save a clinical record universally."""
    patient = await db.get(Patient, data.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    if patient.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Cross-tenant clinical record creation denied")

    record = ClinicalRecord(
        patient_id=data.patient_id,
        tenant_id=patient.tenant_id,
        branch_id=patient.branch_id or current_user.branch_id,
        plugin_id=data.plugin_id or "opd",
        record_type=data.record_type,
        schema_version="1.0",
        data=data.data,
        created_by=data.created_by or current_user.id,
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return record


@router.get("/{patient_id}", response_model=list[ClinicalRecordResponse])
async def get_patient_records(
    patient_id: UUID,
    plugin_id: Optional[str] = None,
    record_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get all clinical records for a patient universally."""
    query = select(ClinicalRecord).where(ClinicalRecord.patient_id == patient_id)
    if plugin_id:
        query = query.where(ClinicalRecord.plugin_id == plugin_id)
    if record_type:
        query = query.where(ClinicalRecord.record_type == record_type)

    result = await db.execute(query.order_by(ClinicalRecord.created_at.desc()))
    return result.scalars().all()


@router.put("/{record_id}", response_model=ClinicalRecordResponse)
@router.patch("/{record_id}", response_model=ClinicalRecordResponse)
async def update_clinical_record(
    record_id: UUID, 
    data: dict, 
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update an existing clinical record's JSONB data."""
    record = await db.get(ClinicalRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    incoming_data = data.get("data") if ("data" in data and isinstance(data["data"], dict)) else data
    record.data = {**(record.data or {}), **incoming_data}
    flag_modified(record, "data")
    
    # If the payload explicitly specifies a new record_type, allow updating it (e.g. opd_triage -> opd_consultation)
    if "record_type" in data:
        record.record_type = data["record_type"]

    record.updated_by = current_user.id
    record.updated_at = datetime.utcnow()

    await db.flush()
    await db.refresh(record)
    return record
