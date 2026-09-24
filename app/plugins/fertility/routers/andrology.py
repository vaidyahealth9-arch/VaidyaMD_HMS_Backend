"""
VaidyaMD HMS — Andrology Suite Router (CASA, DFI, Prep, Freezing, Surgical & IUI)
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel
from typing import Optional, Any

from app.core.database import get_db
from app.core.models import ClinicalRecord, Patient, User

router = APIRouter(prefix="/andrology", tags=["Fertility — Andrology Suite"])


class AndrologyRecordCreate(BaseModel):
    patient_id: UUID
    record_type: Optional[str] = "casa_semen_analysis"
    data: Optional[dict[str, Any]] = None
    created_by: Optional[UUID] = None

    class Config:
        extra = "allow"


@router.post("/", status_code=201)
async def create_andrology_record(payload: AndrologyRecordCreate, db: AsyncSession = Depends(get_db)):
    """Save an Andrology test or procedure record as dynamic JSONB."""
    patient = await db.get(Patient, payload.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    record_data = payload.data or {}
    # If additional fields were passed at top-level
    extra_fields = payload.model_extra or {}
    if extra_fields:
        record_data = {**extra_fields, **record_data}

    # Resolve created_by or fallback to first available user
    creator_id = payload.created_by
    if not creator_id:
        user_res = await db.execute(select(User.id).limit(1))
        creator_id = user_res.scalar_one_or_none()

    record = ClinicalRecord(
        patient_id=payload.patient_id,
        tenant_id=patient.tenant_id,
        branch_id=patient.branch_id,
        plugin_id="fertility",
        record_type=payload.record_type or "casa_semen_analysis",
        schema_version="1.0",
        data=record_data,
        created_by=creator_id,
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return record


@router.get("/")
async def list_andrology_records(
    patient_id: Optional[UUID] = None,
    record_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List andrology records for a patient or overall."""
    query = select(ClinicalRecord).where(ClinicalRecord.plugin_id == "fertility")
    if patient_id:
        query = query.where(ClinicalRecord.patient_id == patient_id)
    if record_type:
        query = query.where(ClinicalRecord.record_type == record_type)

    result = await db.execute(query.order_by(desc(ClinicalRecord.created_at)))
    return result.scalars().all()


@router.get("/{record_id}")
async def get_andrology_record(record_id: UUID, db: AsyncSession = Depends(get_db)):
    """Fetch specific andrology test report."""
    record = await db.get(ClinicalRecord, record_id)
    if not record or record.plugin_id != "fertility":
        raise HTTPException(status_code=404, detail="Andrology record not found")
    return record
