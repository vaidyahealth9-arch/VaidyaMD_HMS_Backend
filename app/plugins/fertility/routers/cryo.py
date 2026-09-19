"""
VaidyaMD HMS — Cryobank & Straw Inventory Router
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from uuid import UUID
from datetime import date, datetime, timedelta
from pydantic import BaseModel
from typing import Optional, Any, List

from app.core.database import get_db
from app.core.models import CryoSample, CryoSampleStatus, Patient, User

router = APIRouter(prefix="/cryo", tags=["Fertility — Cryobank & Storage"])


class CryoSampleCreate(BaseModel):
    patient_id: UUID
    partner_id: Optional[UUID] = None
    treatment_cycle_id: Optional[UUID] = None
    sample_type: str = "embryo"  # embryo, sperm, oocyte
    straw_number: str
    tank_number: str = "Tank-1 (Liquid LN2)"
    canister_number: str = "Canister-1"
    canister_colour: str = "Red"
    goblet_colour: str = "Yellow"
    cryo_device_colour: str = "Green"
    cryo_device_type: str = "Cryotop"
    no_of_embryos: int = 1
    day_of_freezing: int = 5
    embryo_details: Optional[list[dict[str, Any]]] = []
    media_lot_number: Optional[str] = None
    embryologist_id: UUID
    witness_id: Optional[UUID] = None
    expiry_date: Optional[date] = None
    consent_form_reference: Optional[str] = None
    is_donor: bool = False
    remarks: Optional[str] = None


class ThawEventRequest(BaseModel):
    thaw_date: Optional[date] = None
    embryos_warmed: int
    embryos_survived: int
    survival_rate_pct: float
    disposition: str = "Transferred"  # Transferred, Re-vitrified, Discarded
    witness_id: Optional[UUID] = None
    notes: Optional[str] = None


@router.post("/samples", status_code=201)
async def create_cryo_sample(payload: CryoSampleCreate, db: AsyncSession = Depends(get_db)):
    """Add a new straw/sample to physical cryotank coordinates."""
    patient = await db.get(Patient, payload.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    # Default expiry to 5 years if not specified
    exp_date = payload.expiry_date or (date.today() + timedelta(days=365 * 5))

    sample = CryoSample(
        patient_id=payload.patient_id,
        partner_id=payload.partner_id or patient.partner_id,
        treatment_cycle_id=payload.treatment_cycle_id,
        sample_type=payload.sample_type,
        freezing_datetime=datetime.utcnow(),
        day_of_freezing=payload.day_of_freezing,
        straw_number=payload.straw_number,
        tank_number=payload.tank_number,
        canister_number=payload.canister_number,
        canister_colour=payload.canister_colour,
        goblet_colour=payload.goblet_colour,
        cryo_device_colour=payload.cryo_device_colour,
        cryo_device_type=payload.cryo_device_type,
        no_of_embryos=payload.no_of_embryos,
        embryo_details=payload.embryo_details or [],
        media_lot_number=payload.media_lot_number,
        embryologist_id=payload.embryologist_id,
        witness_id=payload.witness_id,
        status=CryoSampleStatus.AVAILABLE,
        expiry_date=exp_date,
        consent_form_reference=payload.consent_form_reference,
        is_donor=payload.is_donor,
        remarks=payload.remarks,
        tenant_id=patient.tenant_id,
    )
    db.add(sample)
    await db.flush()
    await db.refresh(sample)
    return sample


@router.get("/samples")
async def list_cryo_samples(
    patient_id: Optional[UUID] = None,
    sample_type: Optional[str] = None,
    status: Optional[CryoSampleStatus] = None,
    is_donor: Optional[bool] = None,
    tank_number: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List and filter physical tank inventory."""
    query = select(CryoSample).order_by(desc(CryoSample.freezing_datetime))
    if patient_id:
        query = query.where((CryoSample.patient_id == patient_id) | (CryoSample.partner_id == patient_id))
    if sample_type:
        query = query.where(CryoSample.sample_type == sample_type)
    if status:
        query = query.where(CryoSample.status == status)
    if is_donor is not None:
        query = query.where(CryoSample.is_donor == is_donor)
    if tank_number:
        query = query.where(CryoSample.tank_number == tank_number)
    if search:
        query = query.where(CryoSample.straw_number.ilike(f"%{search}%"))

    result = await db.execute(query)
    samples = result.scalars().all()

    # Enhance with patient & partner display info
    enhanced = []
    for s in samples:
        pt = await db.get(Patient, s.patient_id)
        prt = await db.get(Patient, s.partner_id) if s.partner_id else None
        enhanced.append({
            "id": s.id,
            "patient_id": s.patient_id,
            "patient_name": pt.name if pt else "Unknown",
            "patient_vid": pt.vid if pt else "—",
            "patient_phone": pt.phone if pt else "—",
            "partner_name": prt.name if prt else "—",
            "partner_vid": prt.vid if prt else "—",
            "sample_type": s.sample_type,
            "straw_number": s.straw_number,
            "tank_number": s.tank_number,
            "canister_number": s.canister_number,
            "canister_colour": s.canister_colour,
            "goblet_colour": s.goblet_colour,
            "cryo_device_colour": s.cryo_device_colour,
            "cryo_device_type": s.cryo_device_type,
            "no_of_embryos": s.no_of_embryos,
            "day_of_freezing": s.day_of_freezing,
            "embryo_details": s.embryo_details,
            "freezing_datetime": s.freezing_datetime,
            "status": s.status.value,
            "expiry_date": s.expiry_date,
            "is_donor": s.is_donor,
            "consent_form_reference": s.consent_form_reference,
            "remarks": s.remarks,
            "thaw_event": s.thaw_event,
        })
    return enhanced


@router.patch("/samples/{sample_id}/thaw")
async def record_sample_thaw(
    sample_id: UUID,
    payload: ThawEventRequest,
    db: AsyncSession = Depends(get_db),
):
    """Record a warming/thaw event for FET or use."""
    sample = await db.get(CryoSample, sample_id)
    if not sample:
        raise HTTPException(status_code=404, detail="Cryo sample not found")

    sample.status = CryoSampleStatus.WARMED
    sample.thaw_event = {
        "thaw_date": (payload.thaw_date or date.today()).isoformat(),
        "embryos_warmed": payload.embryos_warmed,
        "embryos_survived": payload.embryos_survived,
        "survival_rate_pct": payload.survival_rate_pct,
        "disposition": payload.disposition,
        "witness_id": str(payload.witness_id) if payload.witness_id else None,
        "notes": payload.notes,
    }

    await db.flush()
    await db.refresh(sample)
    return sample


@router.get("/samples/expiring-soon")
async def get_expiring_samples(days: int = Query(30), db: AsyncSession = Depends(get_db)):
    """Alert feed for cryo samples nearing statutory consent expiry."""
    threshold = date.today() + timedelta(days=days)
    query = (
        select(CryoSample)
        .where(
            CryoSample.status == CryoSampleStatus.AVAILABLE,
            CryoSample.expiry_date <= threshold,
        )
        .order_by(CryoSample.expiry_date)
    )
    result = await db.execute(query)
    samples = result.scalars().all()

    alert_list = []
    for s in samples:
        pt = await db.get(Patient, s.patient_id)
        alert_list.append({
            "id": s.id,
            "patient_name": pt.name if pt else "Unknown",
            "straw_number": s.straw_number,
            "tank_number": s.tank_number,
            "sample_type": s.sample_type,
            "expiry_date": s.expiry_date,
            "days_left": (s.expiry_date - date.today()).days if s.expiry_date else 0,
        })
    return alert_list
