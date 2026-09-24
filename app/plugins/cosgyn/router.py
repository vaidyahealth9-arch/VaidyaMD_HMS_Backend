import datetime
from decimal import Decimal
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
from app.modules.billing.schemas import InvoiceCreate, InvoiceItem
from app.modules.billing.service import BillingService
from app.modules.billing.model import InvoiceStatus
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

class CustomSessionItem(BaseModel):
    equipment: str
    session_number: int
    scheduled_datetime: datetime.datetime
    duration_mins: int = 30
    notes: Optional[str] = None

class CreatePlanRequest(BaseModel):
    patient_id: str
    treatment_id: Optional[str] = None
    equipment: Optional[str] = None
    start_date: Optional[datetime.date] = None
    frequency: Optional[FrequencyType] = FrequencyType.WEEKLY
    custom_sessions: Optional[List[CustomSessionItem]] = None
    total_amount: Optional[float] = None
    should_bill_now: Optional[bool] = False
    payment_method: Optional[str] = "cash"
    paid_amount: Optional[float] = None
    discount: Optional[float] = 0.0
    tax: Optional[float] = 0.0
    billing_notes: Optional[str] = None

class BillPlanItem(BaseModel):
    description: str
    quantity: int = 1
    unit_price: float
    total: float
    service_code: Optional[str] = None

class BillPlanRequest(BaseModel):
    billing_type: Optional[str] = "package"  # "package" or "individual_services"
    custom_amount: Optional[float] = None
    discount: Optional[float] = 0.0
    tax: Optional[float] = 0.0
    paid_amount: Optional[float] = None
    payment_method: Optional[str] = "cash"
    upi_pay_mode: Optional[str] = None
    notes: Optional[str] = None
    items: Optional[List[BillPlanItem]] = None

class UpdateSessionRequest(BaseModel):
    scheduled_datetime: Optional[datetime.datetime] = None
    duration_mins: Optional[int] = None
    status: Optional[SessionStatus] = None

class UpdatePlanScheduleItem(BaseModel):
    id: uuid.UUID
    scheduled_datetime: datetime.datetime
    duration_mins: Optional[int] = 30
    status: Optional[SessionStatus] = None

class UpdatePlanScheduleRequest(BaseModel):
    sessions: List[UpdatePlanScheduleItem]

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

    effective_start_date = req.start_date or (
        req.custom_sessions[0].scheduled_datetime.date() if (req.custom_sessions and len(req.custom_sessions) > 0) else datetime.date.today()
    )
    effective_frequency = req.frequency or FrequencyType.CUSTOM

    effective_total_amount = float(req.total_amount) if req.total_amount is not None else float(treatment.price or 0.0)

    plan = CosgynPatientPlan(
        tenant_id=tenant_id,
        branch_id=branch_id,
        patient_id=req.patient_id,
        treatment_id=treatment.id,
        start_date=effective_start_date,
        frequency=effective_frequency,
        total_amount=effective_total_amount
    )
    db.add(plan)
    await db.flush()  # to obtain plan.id

    if req.custom_sessions and len(req.custom_sessions) > 0:
        # Explicit custom sessions with independent start dates, times, and durations
        for item in req.custom_sessions:
            session = CosgynSession(
                tenant_id=tenant_id,
                branch_id=branch_id,
                plan_id=plan.id,
                session_number=item.session_number,
                equipment=item.equipment,
                scheduled_datetime=item.scheduled_datetime,
                duration_mins=item.duration_mins or 30,
                status=SessionStatus.SCHEDULED,
            )
            db.add(session)
            await db.flush()

            if patient_obj:
                apt = Appointment(
                    patient_id=patient_obj.id,
                    doctor_id=doctor_id,
                    department="Cosmetic Gynecology",
                    scheduled_at=item.scheduled_datetime,
                    visit_type="procedure",
                    status=AppointmentStatus.SCHEDULED,
                    notes=f"CosGyn {item.equipment}: {treatment.name} (Session #{item.session_number})",
                    tenant_id=tenant_id,
                    branch_id=branch_id,
                    metadata_={
                        "equipment": item.equipment,
                        "cosgyn_plan_id": str(plan.id),
                        "session_id": str(session.id),
                        "duration_mins": item.duration_mins or 30
                    }
                )
                db.add(apt)
                await db.flush()
                session.appointment_id = apt.id
    else:
        # Legacy auto-generation
        current_date = datetime.datetime.combine(effective_start_date, datetime.time(9, 0)) # default 9 AM
        
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

    # If requested to bill immediately upon booking
    invoice_number = None
    if req.should_bill_now and patient_obj:
        try:
            billing_service = BillingService(db)
            discount_dec = Decimal(str(req.discount or 0.0))
            tax_dec = Decimal(str(req.tax or 0.0))
            subtotal_dec = Decimal(str(effective_total_amount))
            final_total_dec = max(Decimal("0.0"), subtotal_dec - discount_dec + tax_dec)
            paid_dec = Decimal(str(req.paid_amount)) if req.paid_amount is not None else final_total_dec

            inv_item = InvoiceItem(
                description=f"CosGyn Treatment Package: {treatment.name}",
                quantity=1,
                unit_price=subtotal_dec,
                total=subtotal_dec,
                service_code="COSGYN-PKG"
            )
            inv_create = InvoiceCreate(
                patient_id=patient_obj.id,
                appointment_source="Cosmetic Gynecology",
                reason_for_attendance=f"CosGyn Package: {treatment.name}",
                items=[inv_item],
                discount=discount_dec,
                tax=tax_dec,
                paid_amount=paid_dec,
                payment_method=req.payment_method or "cash",
                notes=req.billing_notes or f"CosGyn Plan ID: {plan.id}",
                created_by=current_user.id,
                branch_id=branch_id
            )
            inv_res = await billing_service.create_invoice(inv_create, tenant_id)
            plan.billed = inv_res.invoice_number
            invoice_number = inv_res.invoice_number
        except Exception:
            plan.billed = "false"

    await db.commit()
    return {
        "message": "Plan and sessions created successfully",
        "plan_id": str(plan.id),
        "treatment_name": treatment.name,
        "total_amount": plan.total_amount,
        "billed": plan.billed,
        "invoice_number": invoice_number,
        "sessions_count": len(req.custom_sessions) if req.custom_sessions else session_num - 1
    }

@router.get("/plans")
async def get_all_plans(
    patient_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    query = (
        select(CosgynPatientPlan)
        .options(
            selectinload(CosgynPatientPlan.treatment),
            selectinload(CosgynPatientPlan.sessions)
        )
        .order_by(CosgynPatientPlan.created_at.desc())
    )
    if patient_id:
        query = query.filter(CosgynPatientPlan.patient_id == patient_id)
    
    result = await db.execute(query)
    plans = result.scalars().all()

    # Pre-fetch patients for names/details
    patients_map = {}
    for p in plans:
        if p.patient_id and p.patient_id not in patients_map:
            try:
                pat = await db.get(Patient, uuid.UUID(p.patient_id))
                if pat:
                    patients_map[p.patient_id] = pat
            except Exception:
                pass

    response = []
    for p in plans:
        pat = patients_map.get(p.patient_id)
        sorted_sessions = sorted(
            p.sessions, 
            key=lambda s: s.scheduled_datetime.timestamp() if s.scheduled_datetime else 0
        )
        completed_count = sum(1 for s in sorted_sessions if str(getattr(s.status, 'value', s.status)).lower() == 'completed')

        response.append({
            "id": str(p.id),
            "patient_id": p.patient_id,
            "patient_name": (getattr(pat, 'name', None) or "Patient") if pat else "Patient",
            "patient_mrn": (getattr(pat, 'vid', None) or getattr(pat, 'mrn', None)) if pat else None,
            "patient_phone": getattr(pat, 'phone', None) if pat else None,
            "patient_gender": (pat.gender.value if hasattr(pat.gender, 'value') else str(pat.gender)) if (pat and getattr(pat, 'gender', None)) else None,
            "treatment_id": str(p.treatment_id) if p.treatment_id else None,
            "treatment_name": p.treatment.name if p.treatment else "CosGyn Treatment",
            "start_date": p.start_date.isoformat() if p.start_date else None,
            "frequency": p.frequency.value if hasattr(p.frequency, 'value') else str(p.frequency) if p.frequency else None,
            "total_amount": p.total_amount,
            "billed": p.billed,
            "total_sessions": len(sorted_sessions),
            "completed_sessions": completed_count,
            "created_at": p.created_at.isoformat() if hasattr(p, 'created_at') and p.created_at else None,
            "sessions": [
                {
                    "id": str(s.id),
                    "session_number": s.session_number,
                    "equipment": s.equipment,
                    "scheduled_datetime": s.scheduled_datetime.isoformat() if s.scheduled_datetime else None,
                    "duration_mins": s.duration_mins,
                    "status": s.status.value if hasattr(s.status, 'value') else str(s.status),
                    "appointment_id": str(s.appointment_id) if s.appointment_id else None
                } for s in sorted_sessions
            ]
        })
    return response

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
                    "session_number": s.session_number,
                    "equipment": s.equipment,
                    "scheduled_datetime": s.scheduled_datetime.isoformat() if s.scheduled_datetime else None,
                    "duration_mins": s.duration_mins,
                    "status": s.status.value if hasattr(s.status, 'value') else str(s.status)
                } for s in sorted_sessions
            ]
        })
    return response

@router.put("/plans/{plan_id}/schedule")
async def update_plan_schedule(
    plan_id: str,
    req: UpdatePlanScheduleRequest,
    db: AsyncSession = Depends(get_db)
):
    plan_res = await db.execute(
        select(CosgynPatientPlan)
        .options(selectinload(CosgynPatientPlan.sessions))
        .filter_by(id=uuid.UUID(plan_id))
    )
    plan = plan_res.scalars().first()
    if not plan:
        raise HTTPException(status_code=404, detail="Treatment plan not found")

    sessions_by_id = {s.id: s for s in plan.sessions}
    updated_count = 0

    for item in req.sessions:
        s = sessions_by_id.get(item.id)
        if not s:
            s_res = await db.execute(select(CosgynSession).filter_by(id=item.id, plan_id=plan.id))
            s = s_res.scalars().first()
        if not s:
            continue

        s.scheduled_datetime = item.scheduled_datetime
        if item.duration_mins is not None:
            s.duration_mins = item.duration_mins
        if item.status is not None:
            s.status = item.status

        # Synchronize linked Appointment
        if s.appointment_id:
            try:
                apt = await db.get(Appointment, s.appointment_id)
                if apt:
                    apt.scheduled_at = item.scheduled_datetime
                    meta = apt.metadata_ or {}
                    meta["duration_mins"] = s.duration_mins
                    apt.metadata_ = meta
                    if item.status:
                        st_str = item.status.value if hasattr(item.status, 'value') else str(item.status)
                        if st_str.lower() == 'completed':
                            apt.status = AppointmentStatus.COMPLETED
                        elif st_str.lower() == 'cancelled':
                            apt.status = AppointmentStatus.CANCELLED
                        elif st_str.lower() == 'scheduled':
                            apt.status = AppointmentStatus.SCHEDULED
            except Exception:
                pass

        updated_count += 1

    await db.commit()
    return {"message": "Plan schedule updated successfully", "updated_count": updated_count}

@router.put("/sessions/{session_id}")
async def update_session(session_id: str, req: UpdateSessionRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CosgynSession).filter_by(id=uuid.UUID(session_id)))
    session = result.scalars().first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if req.scheduled_datetime is not None:
        session.scheduled_datetime = req.scheduled_datetime
    if req.duration_mins is not None:
        session.duration_mins = req.duration_mins
    if req.status is not None:
        session.status = req.status

    if session.appointment_id:
        try:
            apt = await db.get(Appointment, session.appointment_id)
            if apt:
                if req.scheduled_datetime is not None:
                    apt.scheduled_at = req.scheduled_datetime
                if req.duration_mins is not None:
                    meta = apt.metadata_ or {}
                    meta["duration_mins"] = req.duration_mins
                    apt.metadata_ = meta
                if req.status is not None:
                    st_str = req.status.value if hasattr(req.status, 'value') else str(req.status)
                    if st_str.lower() == 'completed':
                        apt.status = AppointmentStatus.COMPLETED
                    elif st_str.lower() == 'cancelled':
                        apt.status = AppointmentStatus.CANCELLED
                    elif st_str.lower() == 'scheduled':
                        apt.status = AppointmentStatus.SCHEDULED
        except Exception:
            pass

    await db.commit()
    return {"message": "Session updated"}

@router.post("/plans/{plan_id}/bill")
async def bill_plan(
    plan_id: str,
    req: Optional[BillPlanRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(CosgynPatientPlan)
        .options(
            selectinload(CosgynPatientPlan.treatment),
            selectinload(CosgynPatientPlan.sessions)
        )
        .filter_by(id=uuid.UUID(plan_id))
    )
    plan = result.scalars().first()
    if not plan:
        raise HTTPException(status_code=404, detail="Treatment plan not found")

    patient = None
    try:
        patient = await db.get(Patient, uuid.UUID(plan.patient_id))
    except Exception:
        pass
    if not patient:
        raise HTTPException(status_code=404, detail="Patient record not found")

    tenant_id = (patient.tenant_id if patient else None) or current_user.tenant_id
    branch_id = (patient.branch_id if patient else None) or current_user.branch_id

    # Determine line items
    invoice_items = []
    if req and req.items and len(req.items) > 0:
        for it in req.items:
            invoice_items.append(
                InvoiceItem(
                    description=it.description,
                    quantity=it.quantity,
                    unit_price=Decimal(str(it.unit_price)),
                    total=Decimal(str(it.total)),
                    service_code=it.service_code or "COSGYN"
                )
            )
    elif req and req.billing_type == "individual_services" and plan.sessions:
        for s in plan.sessions:
            item_desc = f"CosGyn {s.equipment or 'Procedure'} Session #{s.session_number}"
            unit_price = round(float(plan.total_amount or 0.0) / max(len(plan.sessions), 1), 2)
            invoice_items.append(
                InvoiceItem(
                    description=item_desc,
                    quantity=1,
                    unit_price=Decimal(str(unit_price)),
                    total=Decimal(str(unit_price)),
                    service_code=f"COSGYN-{s.equipment[:4].upper()}" if s.equipment else "COSGYN"
                )
            )
    else:
        pkg_price = Decimal(str(req.custom_amount if (req and req.custom_amount is not None) else (plan.total_amount or 0.0)))
        invoice_items.append(
            InvoiceItem(
                description=f"CosGyn Treatment Package: {plan.treatment.name if plan.treatment else 'Cosmetic Gynecology'}",
                quantity=1,
                unit_price=pkg_price,
                total=pkg_price,
                service_code="COSGYN-PKG"
            )
        )

    subtotal = sum(it.total for it in invoice_items)
    discount = Decimal(str(req.discount if (req and req.discount) else 0.0))
    tax = Decimal(str(req.tax if (req and req.tax) else 0.0))
    total_amount = max(Decimal("0.0"), subtotal - discount + tax)

    paid_amount = Decimal(str(req.paid_amount)) if (req and req.paid_amount is not None) else total_amount
    payment_method = (req.payment_method if req else "cash") or "cash"

    invoice_data = InvoiceCreate(
        patient_id=patient.id,
        appointment_source="Cosmetic Gynecology",
        reason_for_attendance=f"CosGyn: {plan.treatment.name if plan.treatment else 'Procedure'}",
        items=invoice_items,
        discount=discount,
        tax=tax,
        paid_amount=paid_amount,
        payment_method=payment_method,
        upi_pay_mode=req.upi_pay_mode if req else None,
        notes=req.notes if (req and req.notes) else f"CosGyn Plan ID: {plan.id}",
        created_by=current_user.id,
        branch_id=branch_id
    )

    billing_service = BillingService(db)
    invoice_resp = await billing_service.create_invoice(invoice_data, tenant_id)

    plan.billed = invoice_resp.invoice_number
    if req and req.custom_amount is not None:
        plan.total_amount = float(req.custom_amount)

    await db.commit()

    return {
        "message": "Invoice created and package billed successfully",
        "invoice_id": str(invoice_resp.id),
        "invoice_number": invoice_resp.invoice_number,
        "total_amount": float(invoice_resp.total_amount),
        "paid_amount": float(invoice_resp.paid_amount),
        "status": invoice_resp.status,
        "payment_method": invoice_resp.payment_method
    }
