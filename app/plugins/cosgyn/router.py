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
from app.core.models import Patient, User
from app.modules.appointments.model import Appointment, AppointmentStatus
from app.core.dependencies import get_current_user, require_active_plugin

router = APIRouter(
    prefix="/cosgyn",
    tags=["cosgyn"],
    dependencies=[Depends(get_current_user), Depends(require_active_plugin("cosgyn"))],
)

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

class UpdateTreatmentRequest(BaseModel):
    name: Optional[str] = None
    package_combo: Optional[str] = None
    jet_plasma_sessions: Optional[int] = None
    jet_plasma_duration_mins: Optional[int] = None
    tesla_chair_sessions: Optional[int] = None
    tesla_chair_duration_mins: Optional[int] = None
    prp_sessions: Optional[int] = None
    price: Optional[float] = None

class CreatePlanRequest(BaseModel):
    patient_id: str
    treatment_id: Optional[str] = None
    equipment: Optional[str] = None
    start_date: datetime.date
    frequency: FrequencyType = FrequencyType.WEEKLY

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

@router.put("/treatments/{treatment_id}", response_model=TreatmentResponse)
async def update_treatment(treatment_id: uuid.UUID, req: UpdateTreatmentRequest, db: AsyncSession = Depends(get_db)):
    treatment = await db.get(CosgynTreatment, treatment_id)
    if not treatment:
        raise HTTPException(status_code=404, detail="Treatment package not found")
    if req.name is not None:
        treatment.name = req.name
    if req.package_combo is not None:
        treatment.package_combo = req.package_combo
    if req.jet_plasma_sessions is not None:
        treatment.jet_plasma_sessions = req.jet_plasma_sessions
    if req.jet_plasma_duration_mins is not None:
        treatment.jet_plasma_duration_mins = req.jet_plasma_duration_mins
    if req.tesla_chair_sessions is not None:
        treatment.tesla_chair_sessions = req.tesla_chair_sessions
    if req.tesla_chair_duration_mins is not None:
        treatment.tesla_chair_duration_mins = req.tesla_chair_duration_mins
    if req.prp_sessions is not None:
        treatment.prp_sessions = req.prp_sessions
    if req.price is not None:
        treatment.price = req.price
    await db.commit()
    await db.refresh(treatment)
    return treatment

@router.delete("/treatments/{treatment_id}")
async def delete_treatment(treatment_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    treatment = await db.get(CosgynTreatment, treatment_id)
    if not treatment:
        raise HTTPException(status_code=404, detail="Treatment package not found")
    await db.delete(treatment)
    await db.commit()
    return {"message": "Treatment package deleted successfully"}

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
            "scheduled_datetime": s.scheduled_datetime.isoformat() if s.scheduled_datetime else None,
            "duration_mins": s.duration_mins,
            "status": s.status.value if hasattr(s.status, 'value') else str(s.status),
        })
    return result

@router.post("/plans")
async def create_plan(
    req: CreatePlanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    treatment = None
    if req.treatment_id and req.treatment_id != "manual":
        try:
            treatment_result = await db.execute(select(CosgynTreatment).filter_by(id=uuid.UUID(req.treatment_id)))
            treatment = treatment_result.scalars().first()
        except Exception:
            pass

    # Fallback if manual equipment was selected or treatment ID not matched
    if not treatment:
        if req.equipment:
            treatment_result = await db.execute(
                select(CosgynTreatment).filter(CosgynTreatment.name.ilike(f"%{req.equipment}%"))
            )
            treatment = treatment_result.scalars().first()
        if not treatment:
            res = await db.execute(select(CosgynTreatment).order_by(CosgynTreatment.name.asc()))
            treatment = res.scalars().first()

    if not treatment:
        raise HTTPException(status_code=404, detail="CosGyn treatment protocol not found")

    patient_obj = None
    try:
        patient_res = await db.execute(select(Patient).filter_by(id=uuid.UUID(req.patient_id)))
        patient_obj = patient_res.scalars().first()
    except Exception:
        pass

    tenant_id = (patient_obj.tenant_id if patient_obj else None) or current_user.tenant_id
    branch_id = (patient_obj.branch_id if patient_obj else None) or current_user.branch_id

    # Resolve doctor for scheduled appointments (Appointment.doctor_id cannot be null)
    doctor_id = getattr(patient_obj, 'treating_doctor_id', None)
    if not doctor_id:
        user_role_str = (current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)).lower()
        if current_user.is_doctor or "doctor" in user_role_str:
            doctor_id = current_user.id
        else:
            # Pick first available doctor in hospital
            doc_res = await db.execute(
                select(User).where(User.tenant_id == tenant_id, User.is_active == True)
            )
            all_users = doc_res.scalars().all()
            doc_user = next((u for u in all_users if u.is_doctor or "doctor" in str(u.role).lower()), None)
            doctor_id = doc_user.id if doc_user else current_user.id

    plan = CosgynPatientPlan(
        tenant_id=tenant_id,
        branch_id=branch_id,
        patient_id=req.patient_id,
        treatment_id=treatment.id,
        start_date=req.start_date,
        frequency=req.frequency,
        total_amount=treatment.price
    )
    db.add(plan)
    await db.flush()  # to obtain plan.id

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

    session_num = 1

    # Jet Plasma Sessions
    jp_date = current_date
    num_jp = treatment.jet_plasma_sessions if treatment.jet_plasma_sessions > 0 else (1 if req.equipment == "Jet Plasma" else 0)
    for i in range(num_jp):
        session = CosgynSession(
            tenant_id=tenant_id,
            branch_id=branch_id,
            plan_id=plan.id,
            session_number=session_num,
            equipment="Jet Plasma",
            scheduled_datetime=jp_date,
            duration_mins=treatment.jet_plasma_duration_mins or 30,
            status=SessionStatus.SCHEDULED,
        )
        db.add(session)
        await db.flush()
        session_num += 1

        if patient_obj:
            apt = Appointment(
                patient_id=patient_obj.id,
                doctor_id=doctor_id,
                department="Cosmetic Gynecology",
                scheduled_at=jp_date,
                visit_type="procedure",
                status=AppointmentStatus.SCHEDULED,
                notes=f"CosGyn Jet Plasma: {treatment.name} (Session #{session.session_number})",
                tenant_id=tenant_id,
                branch_id=branch_id,
                metadata_={"equipment": "Jet Plasma", "cosgyn_plan_id": str(plan.id), "session_id": str(session.id)}
            )
            db.add(apt)
            await db.flush()
            session.appointment_id = apt.id

        jp_date = get_next_date(jp_date, req.frequency)

    # Tesla Chair Sessions
    tc_date = current_date
    num_tc = treatment.tesla_chair_sessions if treatment.tesla_chair_sessions > 0 else (1 if req.equipment == "Tesla Chair" else 0)
    for i in range(num_tc):
        if i < num_jp:
            tc_date_session = tc_date + datetime.timedelta(minutes=(treatment.jet_plasma_duration_mins or 30) + 10)
        else:
            tc_date_session = tc_date
            
        session = CosgynSession(
            tenant_id=tenant_id,
            branch_id=branch_id,
            plan_id=plan.id,
            session_number=session_num,
            equipment="Tesla Chair",
            scheduled_datetime=tc_date_session,
            duration_mins=treatment.tesla_chair_duration_mins or 30,
            status=SessionStatus.SCHEDULED,
        )
        db.add(session)
        await db.flush()
        session_num += 1

        if patient_obj:
            apt = Appointment(
                patient_id=patient_obj.id,
                doctor_id=doctor_id,
                department="Cosmetic Gynecology",
                scheduled_at=tc_date_session,
                visit_type="procedure",
                status=AppointmentStatus.SCHEDULED,
                notes=f"CosGyn Tesla Chair: {treatment.name} (Session #{session.session_number})",
                tenant_id=tenant_id,
                branch_id=branch_id,
                metadata_={"equipment": "Tesla Chair", "cosgyn_plan_id": str(plan.id), "session_id": str(session.id)}
            )
            db.add(apt)
            await db.flush()
            session.appointment_id = apt.id

        tc_date = get_next_date(tc_date, req.frequency)

    # If neither Jet Plasma nor Tesla Chair was configured (e.g. PRP, Labiaplasty), create at least 1 procedure session:
    if num_jp == 0 and num_tc == 0:
        session = CosgynSession(
            tenant_id=tenant_id,
            branch_id=branch_id,
            plan_id=plan.id,
            session_number=session_num,
            equipment=treatment.package_combo or "CosGyn Procedure",
            scheduled_datetime=current_date,
            duration_mins=45,
            status=SessionStatus.SCHEDULED,
        )
        db.add(session)
        await db.flush()

        if patient_obj:
            apt = Appointment(
                patient_id=patient_obj.id,
                doctor_id=doctor_id,
                department="Cosmetic Gynecology",
                scheduled_at=current_date,
                visit_type="procedure",
                status=AppointmentStatus.SCHEDULED,
                notes=f"CosGyn Procedure: {treatment.name}",
                tenant_id=tenant_id,
                branch_id=branch_id,
                metadata_={"equipment": treatment.package_combo or "CosGyn Procedure", "cosgyn_plan_id": str(plan.id), "session_id": str(session.id)}
            )
            db.add(apt)
            await db.flush()
            session.appointment_id = apt.id

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
        # sort sessions safely by date
        sorted_sessions = sorted(
            p.sessions, 
            key=lambda s: s.scheduled_datetime.timestamp() if s.scheduled_datetime else 0
        )
        
        response.append({
            "id": str(p.id),
            "treatment_name": p.treatment.name if p.treatment else "CosGyn Treatment",
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
