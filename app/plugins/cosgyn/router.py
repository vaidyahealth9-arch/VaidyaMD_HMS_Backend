import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
import uuid

from app.core.database import get_db
from app.core.models.cosgyn import (
    CosgynTreatment, CosgynPatientPlan, CosgynSession,
    FrequencyType, SessionStatus
)
from app.core.models import Patient
from app.modules.appointments.model import Appointment, AppointmentStatus
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/cosgyn", tags=["cosgyn"])

# Pydantic Schemas

class TreatmentResponse(BaseModel):
    id: uuid.UUID
    name: str
    package_combo: Optional[str] = None
    jet_plasma_sessions: int
    jet_plasma_duration_mins: int
    tesla_chair_sessions: int
    tesla_chair_duration_mins: int
    prp_sessions: int
    price: float

    model_config = ConfigDict(from_attributes=True)

class CreateTreatmentRequest(BaseModel):
    name: str
    package_combo: Optional[str] = None
    jet_plasma_sessions: int = 0
    jet_plasma_duration_mins: int = 30
    tesla_chair_sessions: int = 0
    tesla_chair_duration_mins: int = 30
    prp_sessions: int = 0
    price: float

class CreatePlanRequest(BaseModel):
    patient_id: str
    treatment_id: str
    start_date: datetime.date
    frequency: FrequencyType

class UpdateSessionRequest(BaseModel):
    scheduled_datetime: Optional[datetime.datetime] = None
    status: Optional[SessionStatus] = None

# Endpoints

@router.get("/treatments", response_model=List[TreatmentResponse])
async def get_treatments(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CosgynTreatment).order_by(CosgynTreatment.name))
    return result.scalars().all()

@router.post("/treatments", response_model=TreatmentResponse)
async def create_treatment(req: CreateTreatmentRequest, db: AsyncSession = Depends(get_db)):
    treatment = CosgynTreatment(
        name=req.name,
        package_combo=req.package_combo,
        jet_plasma_sessions=req.jet_plasma_sessions,
        jet_plasma_duration_mins=req.jet_plasma_duration_mins,
        tesla_chair_sessions=req.tesla_chair_sessions,
        tesla_chair_duration_mins=req.tesla_chair_duration_mins,
        prp_sessions=req.prp_sessions,
        price=req.price
    )
    db.add(treatment)
    await db.commit()
    await db.refresh(treatment)
    return treatment

@router.get("/sessions")
async def get_all_sessions(
    start_date: Optional[datetime.date] = None,
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(CosgynSession)
        .join(CosgynSession.plan)
        .options(
            selectinload(CosgynSession.plan).selectinload(CosgynPatientPlan.treatment)
        )
        .order_by(CosgynSession.scheduled_datetime.asc())
    )
    if start_date:
        query = query.where(CosgynSession.scheduled_datetime >= datetime.datetime.combine(start_date, datetime.time.min))
    res = await db.execute(query)
    sessions = res.scalars().all()

    result = []
    for s in sessions:
        pat_name = "Patient"
        pat_id = s.plan.patient_id if s.plan else None
        if pat_id:
            try:
                p = await db.get(Patient, uuid.UUID(pat_id))
                if p:
                    pat_name = f"{p.name} ({p.vid or p.mrn or ''})"
            except Exception:
                pass
        result.append({
            "id": str(s.id),
            "plan_id": str(s.plan_id),
            "patient_id": pat_id,
            "patient_name": pat_name,
            "treatment_name": s.plan.treatment.name if (s.plan and s.plan.treatment) else "CosGyn Treatment",
            "equipment": s.equipment,
            "scheduled_datetime": s.scheduled_datetime.isoformat(),
            "duration_mins": s.duration_mins,
            "status": s.status.value if hasattr(s.status, 'value') else str(s.status),
        })
    return result

@router.post("/plans")
async def create_plan(req: CreatePlanRequest, db: AsyncSession = Depends(get_db)):
    treatment_result = await db.execute(select(CosgynTreatment).filter_by(id=uuid.UUID(req.treatment_id)))
    treatment = treatment_result.scalars().first()
    if not treatment:
        raise HTTPException(status_code=404, detail="Treatment not found")

    plan = CosgynPatientPlan(
        patient_id=req.patient_id,
        treatment_id=treatment.id,
        start_date=req.start_date,
        frequency=req.frequency,
        total_amount=treatment.price
    )
    db.add(plan)
    await db.flush()  # to get plan.id

    patient_obj = None
    try:
        patient_res = await db.execute(select(Patient).filter_by(id=uuid.UUID(req.patient_id)))
        patient_obj = patient_res.scalars().first()
    except Exception:
        pass

    # Generate Sessions
    current_date = datetime.datetime.combine(req.start_date, datetime.time(9, 0)) # default 9 AM
    
    def get_next_date(dt, freq):
        if freq == FrequencyType.DAILY:
            return dt + datetime.timedelta(days=1)
        elif freq == FrequencyType.TWICE_WEEKLY:
            return dt + datetime.timedelta(days=3)
        elif freq == FrequencyType.WEEKLY:
            return dt + datetime.timedelta(days=7)
        elif freq == FrequencyType.FORTNIGHTLY:
            return dt + datetime.timedelta(days=14)
        elif freq == FrequencyType.MONTHLY:
            return dt + datetime.timedelta(days=30)
        return dt + datetime.timedelta(days=7)

    # Jet Plasma Sessions
    jp_date = current_date
    for i in range(treatment.jet_plasma_sessions):
        session = CosgynSession(
            plan_id=plan.id,
            equipment="Jet Plasma",
            scheduled_datetime=jp_date,
            duration_mins=treatment.jet_plasma_duration_mins
        )
        db.add(session)
        if patient_obj:
            apt = Appointment(
                patient_id=patient_obj.id,
                doctor_id=patient_obj.treating_doctor_id,
                department="Cosmetic Gynecology",
                scheduled_at=jp_date,
                visit_type="procedure",
                status=AppointmentStatus.SCHEDULED,
                notes=f"CosGyn Jet Plasma: {treatment.name}",
                tenant_id=patient_obj.tenant_id,
                metadata_={"equipment": "Jet Plasma", "cosgyn_plan_id": str(plan.id)}
            )
            db.add(apt)
        jp_date = get_next_date(jp_date, req.frequency)

    # Tesla Chair Sessions
    tc_date = current_date
    for i in range(treatment.tesla_chair_sessions):
        if i < treatment.jet_plasma_sessions:
            tc_date_session = tc_date + datetime.timedelta(minutes=treatment.jet_plasma_duration_mins + 10)
        else:
            tc_date_session = tc_date
            
        session = CosgynSession(
            plan_id=plan.id,
            equipment="Tesla Chair",
            scheduled_datetime=tc_date_session,
            duration_mins=treatment.tesla_chair_duration_mins
        )
        db.add(session)
        if patient_obj:
            apt = Appointment(
                patient_id=patient_obj.id,
                doctor_id=patient_obj.treating_doctor_id,
                department="Cosmetic Gynecology",
                scheduled_at=tc_date_session,
                visit_type="procedure",
                status=AppointmentStatus.SCHEDULED,
                notes=f"CosGyn Tesla Chair: {treatment.name}",
                tenant_id=patient_obj.tenant_id,
                metadata_={"equipment": "Tesla Chair", "cosgyn_plan_id": str(plan.id)}
            )
            db.add(apt)
        tc_date = get_next_date(tc_date, req.frequency)

    await db.commit()
    return {"message": "Plan and sessions created successfully", "plan_id": str(plan.id)}

@router.get("/plans/{patient_id}")
async def get_patient_plans(patient_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CosgynPatientPlan)
        .options(selectinload(CosgynPatientPlan.treatment), selectinload(CosgynPatientPlan.sessions))
        .filter_by(patient_id=patient_id)
        .order_by(CosgynPatientPlan.created_at.desc())
    )
    plans = result.scalars().all()
    response = []
    for p in plans:
        # sort sessions by date
        sorted_sessions = sorted(p.sessions, key=lambda s: s.scheduled_datetime)
        
        response.append({
            "id": str(p.id),
            "treatment_name": p.treatment.name,
            "start_date": p.start_date,
            "frequency": p.frequency,
            "total_amount": p.total_amount,
            "billed": p.billed,
            "sessions": [
                {
                    "id": str(s.id),
                    "equipment": s.equipment,
                    "scheduled_datetime": s.scheduled_datetime,
                    "duration_mins": s.duration_mins,
                    "status": s.status
                } for s in sorted_sessions
            ]
        })
    return response

@router.put("/sessions/{session_id}")
async def update_session(session_id: str, req: UpdateSessionRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CosgynSession).filter_by(id=uuid.UUID(session_id)))
    session = result.scalars().first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if req.scheduled_datetime is not None:
        session.scheduled_datetime = req.scheduled_datetime
    if req.status is not None:
        session.status = req.status
    await db.commit()
    return {"message": "Session updated"}

@router.post("/plans/{plan_id}/bill")
async def bill_plan(plan_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CosgynPatientPlan).filter_by(id=uuid.UUID(plan_id)))
    plan = result.scalars().first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    plan.billed = "true"
    await db.commit()
    return {"message": "Plan billed successfully"}
