"""
VaidyaMD HMS — Treatment Cycles & Medication Calendar Router
"""

import io
import csv
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_
from uuid import UUID
from datetime import date, datetime
from pydantic import BaseModel
from typing import Optional, Any, List, Union

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.models import TreatmentCycle, TreatmentCycleStatus, ProtocolTemplate, ProtocolDrugRule, Patient, User, Hospital, TreatmentCycleType
from app.plugins.fertility.rules_engine import generate_medication_calendar

router = APIRouter(prefix="/treatment-cycles", tags=["Fertility — Treatment Cycles"])


@router.get("/types", tags=["Fertility — Treatment Cycles"])
async def list_cycle_types(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all active treatment cycle types for dropdown population directly from database."""
    query = select(TreatmentCycleType).where(TreatmentCycleType.is_active == True)
    if current_user and current_user.tenant_id:
        query = query.where(
            or_(
                TreatmentCycleType.tenant_id == current_user.tenant_id,
                TreatmentCycleType.tenant_id.is_(None),
            )
        )
    query = query.order_by(TreatmentCycleType.display_order, TreatmentCycleType.name)
    result = await db.execute(query)
    types = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "name": t.name,
            "category": t.category,
            "display_order": t.display_order,
            "is_active": t.is_active,
        }
        for t in types
    ]


class TreatmentCycleTypeCreate(BaseModel):
    name: str
    category: Optional[str] = "Stimulation"
    display_order: Optional[int] = 0
    is_active: Optional[bool] = True


class TreatmentCycleTypeUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None


@router.post("/types", status_code=201, tags=["Fertility — Treatment Cycles"])
async def create_cycle_type(
    payload: TreatmentCycleTypeCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cycle_type = TreatmentCycleType(
        tenant_id=current_user.tenant_id,
        name=payload.name,
        category=payload.category,
        display_order=payload.display_order or 0,
        is_active=payload.is_active if payload.is_active is not None else True,
    )
    db.add(cycle_type)
    await db.commit()
    await db.refresh(cycle_type)
    return {
        "id": str(cycle_type.id),
        "name": cycle_type.name,
        "category": cycle_type.category,
        "display_order": cycle_type.display_order,
        "is_active": cycle_type.is_active,
    }


@router.put("/types/{type_id}", tags=["Fertility — Treatment Cycles"])
async def update_cycle_type(
    type_id: UUID,
    payload: TreatmentCycleTypeUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cycle_type = await db.get(TreatmentCycleType, type_id)
    if not cycle_type or (cycle_type.tenant_id and cycle_type.tenant_id != current_user.tenant_id):
        raise HTTPException(status_code=404, detail="Cycle type not found")
    if payload.name is not None:
        cycle_type.name = payload.name
    if payload.category is not None:
        cycle_type.category = payload.category
    if payload.display_order is not None:
        cycle_type.display_order = payload.display_order
    if payload.is_active is not None:
        cycle_type.is_active = payload.is_active
    await db.commit()
    await db.refresh(cycle_type)
    return {
        "id": str(cycle_type.id),
        "name": cycle_type.name,
        "category": cycle_type.category,
        "display_order": cycle_type.display_order,
        "is_active": cycle_type.is_active,
    }


@router.delete("/types/{type_id}", tags=["Fertility — Treatment Cycles"])
async def delete_cycle_type(
    type_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cycle_type = await db.get(TreatmentCycleType, type_id)
    if not cycle_type or (cycle_type.tenant_id and cycle_type.tenant_id != current_user.tenant_id):
        raise HTTPException(status_code=404, detail="Cycle type not found")
    cycle_type.is_active = False
    await db.commit()
    return {"status": "success", "message": "Cycle type deleted successfully"}




# --- Pydantic Schemas ---
class CycleCreate(BaseModel):
    patient_id: UUID
    partner_id: Optional[UUID] = None
    treating_doctor_id: UUID
    treatment_type: str = "ICSI"
    attempt_number: int = 1
    start_date: Optional[date] = None
    female_factors: Optional[list[str]] = []
    male_factors: Optional[list[str]] = []
    treatment_at_other_centre: bool = False
    protocol_template_id: Optional[Union[UUID, str]] = None
    sentinel_dates: Optional[dict[str, Any]] = {}
    gametes_source: Optional[dict[str, Any]] = {}
    pgs_pgd_data: Optional[dict[str, Any]] = {}
    endometrial_monitoring: Optional[list[dict[str, Any]]] = []
    medication_calendar: Optional[list[dict[str, Any]]] = []
    remarks: Optional[str] = None
    created_by: UUID


class CycleStatusUpdate(BaseModel):
    status: TreatmentCycleStatus
    cancellation_reason: Optional[str] = None
    cancelled_by: Optional[UUID] = None


class SentinelDatesUpdate(BaseModel):
    sentinel_dates: dict[str, Any]
    endometrial_monitoring: Optional[list[dict[str, Any]]] = None


async def generate_cycle_id(db: AsyncSession) -> str:
    year = datetime.utcnow().year
    result = await db.execute(select(func.count(TreatmentCycle.id)))
    count = (result.scalar() or 0) + 1
    return f"TC-{year}-{count:04d}"


def serialize_treatment_cycle(cycle: TreatmentCycle, patient: Optional[Patient] = None, partner: Optional[Patient] = None) -> dict:
    return {
        "id": str(cycle.id),
        "cycle_id": cycle.cycle_id,
        "patient_id": str(cycle.patient_id),
        "partner_id": str(cycle.partner_id) if cycle.partner_id else None,
        "treating_doctor_id": str(cycle.treating_doctor_id),
        "treatment_type": cycle.treatment_type,
        "status": cycle.status.value if hasattr(cycle.status, "value") else str(cycle.status),
        "attempt_number": cycle.attempt_number,
        "start_date": cycle.start_date.isoformat() if cycle.start_date else None,
        "end_date": cycle.end_date.isoformat() if cycle.end_date else None,
        "cancellation_reason": cycle.cancellation_reason,
        "cancelled_by": str(cycle.cancelled_by) if cycle.cancelled_by else None,
        "female_factors": cycle.female_factors or [],
        "male_factors": cycle.male_factors or [],
        "treatment_at_other_centre": cycle.treatment_at_other_centre,
        "protocol_template_id": str(cycle.protocol_template_id) if cycle.protocol_template_id else None,
        "sentinel_dates": cycle.sentinel_dates or {},
        "gametes_source": cycle.gametes_source or {},
        "pgs_pgd_data": cycle.pgs_pgd_data or {},
        "endometrial_monitoring": cycle.endometrial_monitoring or [],
        "medication_calendar": getattr(cycle, "medication_calendar", []) or [],
        "et_discharge_summary": getattr(cycle, "et_discharge_summary", {}) or {},
        "remarks": cycle.remarks,
        "tenant_id": str(cycle.tenant_id),
        "created_by": str(cycle.created_by),
        "created_at": cycle.created_at.isoformat() if cycle.created_at else None,
        "updated_at": cycle.updated_at.isoformat() if cycle.updated_at else None,
        # Enriched Patient & Partner fields for unified Couple EMR
        "patient_name": patient.name if patient else None,
        "patient_vid": patient.vid if patient else None,
        "patient_age": patient.age if patient else None,
        "patient_gender": patient.gender.value if patient and hasattr(patient.gender, "value") else (str(patient.gender) if patient else None),
        "patient_phone": patient.phone if patient else None,
        "patient_blood_group": patient.blood_group if patient else None,
        "patient_clinical_notes": patient.clinical_notes if patient else [],
        "partner_name": partner.name if partner else None,
        "partner_vid": partner.vid if partner else None,
        "partner_age": partner.age if partner else None,
        "partner_gender": partner.gender.value if partner and hasattr(partner.gender, "value") else (str(partner.gender) if partner else None),
        "partner_phone": partner.phone if partner else None,
        "partner_blood_group": partner.blood_group if partner else None,
        "partner_clinical_notes": partner.clinical_notes if partner else [],
    }


# --- Endpoints ---
@router.post("", status_code=201)
@router.post("/", status_code=201)
async def create_treatment_cycle(
    payload: CycleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new treatment cycle for a patient."""
    patient = await db.get(Patient, payload.patient_id)
    if not patient or patient.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Patient not found")


    cycle_num = await generate_cycle_id(db)

    # Resolve protocol_template_id safely if UUID or string name
    resolved_proto_id = None
    if payload.protocol_template_id:
        try:
            resolved_proto_id = UUID(str(payload.protocol_template_id))
        except (ValueError, TypeError):
            # Lookup by name/identifier
            proto_q = await db.execute(
                select(ProtocolTemplate)
                .where(ProtocolTemplate.name.ilike(f"%{payload.protocol_template_id}%"))
                .limit(1)
            )
            found_p = proto_q.scalar_one_or_none()
            if found_p:
                resolved_proto_id = found_p.id

    # Auto-generate timetable if medication_calendar is empty or has no medications
    med_calendar = payload.medication_calendar or []
    has_meds = any(
        isinstance(d, dict) and len(d.get("medications", [])) > 0
        for d in med_calendar
    )

    if not has_meds and (resolved_proto_id or payload.sentinel_dates):
        rules_data = []
        if resolved_proto_id:
            r_res = await db.execute(
                select(ProtocolDrugRule)
                .where(ProtocolDrugRule.protocol_template_id == resolved_proto_id)
                .order_by(ProtocolDrugRule.sort_order)
            )
            for r in r_res.scalars().all():
                rules_data.append({
                    "drug_name": r.drug_name,
                    "dose": r.dose,
                    "route": r.route,
                    "frequency": r.frequency,
                    "sentinel_anchor": r.sentinel_anchor,
                    "day_start_offset": r.day_start_offset,
                    "day_end_offset": r.day_end_offset,
                    "instructions": r.instructions,
                })
        gen_cal = generate_medication_calendar(
            rules=rules_data,
            sentinel_dates=payload.sentinel_dates or {},
            total_days=21,
        )
        if gen_cal and gen_cal.get("days"):
            med_calendar = gen_cal["days"]

    cycle = TreatmentCycle(
        cycle_id=cycle_num,
        patient_id=payload.patient_id,
        partner_id=payload.partner_id or patient.partner_id,
        treating_doctor_id=payload.treating_doctor_id,
        treatment_type=payload.treatment_type,
        status=TreatmentCycleStatus.RUNNING,
        attempt_number=payload.attempt_number,
        start_date=payload.start_date or date.today(),
        female_factors=payload.female_factors or [],
        male_factors=payload.male_factors or [],
        treatment_at_other_centre=payload.treatment_at_other_centre,
        protocol_template_id=resolved_proto_id,
        sentinel_dates=payload.sentinel_dates or {},
        gametes_source=payload.gametes_source or {},
        pgs_pgd_data=payload.pgs_pgd_data or {},
        endometrial_monitoring=payload.endometrial_monitoring or [],
        medication_calendar=med_calendar,
        remarks=payload.remarks,
        tenant_id=patient.tenant_id,
        created_by=payload.created_by,
    )
    db.add(cycle)
    await db.flush()
    await db.refresh(cycle)
    partner = await db.get(Patient, cycle.partner_id) if cycle.partner_id else None
    return serialize_treatment_cycle(cycle, patient, partner)


@router.get("")
@router.get("/")
async def list_treatment_cycles(
    patient_id: Optional[UUID] = None,
    status: Optional[TreatmentCycleStatus] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List treatment cycles optionally filtered by patient or status with enriched couple details."""
    query = (
        select(TreatmentCycle)
        .where(TreatmentCycle.tenant_id == current_user.tenant_id)
        .order_by(desc(TreatmentCycle.created_at))
    )

    if patient_id:
        query = query.where(
            (TreatmentCycle.patient_id == patient_id) | (TreatmentCycle.partner_id == patient_id)
        )
    if status:
        query = query.where(TreatmentCycle.status == status)

    result = await db.execute(query)
    cycles = result.scalars().all()

    # Batch load all related patients & partners in 1 query
    pat_ids = set()
    for c in cycles:
        if c.patient_id:
            pat_ids.add(c.patient_id)
        if c.partner_id:
            pat_ids.add(c.partner_id)

    patient_map = {}
    if pat_ids:
        p_res = await db.execute(select(Patient).where(Patient.id.in_(list(pat_ids))))
        for p in p_res.scalars().all():
            patient_map[p.id] = p

    return [
        serialize_treatment_cycle(c, patient_map.get(c.patient_id), patient_map.get(c.partner_id))
        for c in cycles
    ]


@router.get("/art-registry-export")
async def export_art_registry(
    format: str = Query("json", regex="^(json|csv)$"),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Statutory National ART Registry Export under Indian ART Regulation Act 2021 (Rules 13 & 14).
    Generates standardized statutory dataset for submission to the National ART & Surrogacy Registry Board.
    """
    query = select(TreatmentCycle)
    if current_user.tenant_id:
        query = query.where(TreatmentCycle.tenant_id == current_user.tenant_id)
    if start_date:
        query = query.where(TreatmentCycle.start_date >= start_date)
    if end_date:
        query = query.where(TreatmentCycle.start_date <= end_date)
    if status and status != "ALL":
        query = query.where(TreatmentCycle.status == status)

    result = await db.execute(query.order_by(desc(TreatmentCycle.start_date)))
    cycles = result.scalars().all()

    pat_ids = set()
    for c in cycles:
        if c.patient_id:
            pat_ids.add(c.patient_id)
        if c.partner_id:
            pat_ids.add(c.partner_id)

    patient_map = {}
    if pat_ids:
        p_res = await db.execute(select(Patient).where(Patient.id.in_(list(pat_ids))))
        for p in p_res.scalars().all():
            patient_map[p.id] = p

    records = []
    for c in cycles:
        p = patient_map.get(c.patient_id)
        pt = patient_map.get(c.partner_id)
        s_dates = c.sentinel_dates or {}
        med_cal = getattr(c, "medication_calendar", []) or []
        et_summary = getattr(c, "et_discharge_summary", {}) or {}

        # Masked identifiers (Statutory Privacy compliance)
        p_uid_masked = f"XXXX-XXXX-{str(p.id)[-4:]}" if p else "—"
        pt_uid_masked = f"XXXX-XXXX-{str(pt.id)[-4:]}" if pt else "—"

        oocytes_total = s_dates.get("oocytes_retrieved") or s_dates.get("total_oocytes") or 0
        embryos_transferred = et_summary.get("embryos_transferred_count") or (1 if s_dates.get("et") else 0)

        records.append({
            "registry_code": c.cycle_id,
            "patient_vid": p.vid if p else "—",
            "patient_name_masked": f"{p.name[:2]}***" if (p and p.name) else "—",
            "patient_age": p.age if p else None,
            "patient_masked_uid": p_uid_masked,
            "partner_vid": pt.vid if pt else "—",
            "partner_name_masked": f"{pt.name[:2]}***" if (pt and pt.name) else "—",
            "partner_age": pt.age if pt else None,
            "treatment_type": c.treatment_type,
            "attempt_number": c.attempt_number,
            "cycle_status": c.status.value if hasattr(c.status, "value") else str(c.status),
            "female_factors": ", ".join(c.female_factors or []) or "Unspecified",
            "male_factors": ", ".join(c.male_factors or []) or "Normal / Unspecified",
            "lmp_date": s_dates.get("lmp_day1") or (c.start_date.isoformat() if c.start_date else "—"),
            "stim_start_date": s_dates.get("stim_start") or "—",
            "trigger_date": s_dates.get("trigger") or "—",
            "opu_date": s_dates.get("opu") or "—",
            "et_date": s_dates.get("et") or "—",
            "total_stimulation_days": len(med_cal) if med_cal else None,
            "total_oocytes_retrieved": oocytes_total,
            "embryos_transferred_count": embryos_transferred,
            "transfer_type": et_summary.get("transfer_type") or ("FET" if "FET" in c.treatment_type else "Fresh ET"),
            "retained_embryos_cleared": et_summary.get("retained_embryo_checked", True),
            "catheter_type": et_summary.get("catheter_type") or "Cook Sydney",
            "outcome_beta_hcg": s_dates.get("beta_hcg") or et_summary.get("beta_hcg_result") or "Pending / Follow-up",
            "ohss_complication": "None" if not s_dates.get("ohss_risk") else s_dates.get("ohss_risk"),
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })

    if format == "csv":
        output = io.StringIO()
        if records:
            writer = csv.DictWriter(output, fieldnames=list(records[0].keys()))
            writer.writeheader()
            writer.writerows(records)
        else:
            writer = csv.writer(output)
            writer.writerow(["No records found for selected criteria"])

        output.seek(0)
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=national_art_registry_export_{date.today().isoformat()}.csv"}
        )

    return {
        "statutory_act": "National Assisted Reproductive Technology and Surrogacy Act 2021",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "total_records": len(records),
        "records": records,
    }


@router.get("/{cycle_id}")
async def get_treatment_cycle(cycle_id: UUID, db: AsyncSession = Depends(get_db)):
    """Fetch details of a specific treatment cycle with patient and partner summary."""
    cycle = await db.get(TreatmentCycle, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Treatment cycle not found")
    patient = await db.get(Patient, cycle.patient_id) if cycle.patient_id else None
    partner = await db.get(Patient, cycle.partner_id) if cycle.partner_id else None
    return serialize_treatment_cycle(cycle, patient, partner)


@router.patch("/{cycle_id}/status")
async def update_cycle_status(
    cycle_id: UUID,
    payload: CycleStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update cycle status. Mandatory reason on cancellation."""
    cycle = await db.get(TreatmentCycle, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Treatment cycle not found")

    if payload.status == TreatmentCycleStatus.CANCELLED and not payload.cancellation_reason:
        raise HTTPException(
            status_code=422,
            detail="Cancellation reason is mandatory when cancelling a treatment cycle."
        )

    cycle.status = payload.status
    if payload.cancellation_reason:
        cycle.cancellation_reason = payload.cancellation_reason
    if payload.cancelled_by:
        cycle.cancelled_by = payload.cancelled_by
    if payload.status in [TreatmentCycleStatus.COMPLETED, TreatmentCycleStatus.CANCELLED]:
        cycle.end_date = date.today()

    await db.flush()
    await db.refresh(cycle)
    return cycle


@router.patch("/{cycle_id}/sentinel-dates")
async def update_sentinel_dates(
    cycle_id: UUID,
    payload: SentinelDatesUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update sentinel dates & serial endometrial monitoring scans for cycle."""
    cycle = await db.get(TreatmentCycle, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Treatment cycle not found")

    cycle.sentinel_dates = {**cycle.sentinel_dates, **payload.sentinel_dates}
    if payload.endometrial_monitoring is not None:
        cycle.endometrial_monitoring = payload.endometrial_monitoring

    await db.flush()
    await db.refresh(cycle)
    return cycle


class CycleUpdate(BaseModel):
    status: Optional[TreatmentCycleStatus] = None
    sentinel_dates: Optional[dict[str, Any]] = None
    endometrial_monitoring: Optional[list[dict[str, Any]]] = None
    medication_calendar: Optional[list[dict[str, Any]]] = None
    et_discharge_summary: Optional[dict[str, Any]] = None
    remarks: Optional[str] = None
    cancellation_reason: Optional[str] = None


class ETDischargeUpdate(BaseModel):
    transfer_type: str = "FET"
    catheter_type: str = "Cook Sydney"
    embryos_transferred_count: int = 1
    embryo_stage: Optional[str] = None
    embryo_grades: Optional[list[str]] = None
    ultrasound_guidance: Optional[str] = "Transabdominal"
    blood_on_catheter: bool = False
    retained_embryo_checked: bool = True
    witness_embryologist_id: Optional[str] = None
    witness_embryologist_name: Optional[str] = None
    attending_doctor_name: Optional[str] = None
    luteal_support_medications: Optional[list[dict[str, Any]]] = None
    beta_hcg_due_date: Optional[str] = None
    discharge_notes: Optional[str] = None
    precautions: Optional[list[str]] = None


class MedicationAddRequest(BaseModel):
    day_number: int
    drug_name: str
    dose: str
    frequency: str = "OD"
    instructions: Optional[str] = None


@router.patch("/{cycle_id}")
async def update_treatment_cycle(
    cycle_id: UUID,
    payload: CycleUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update treatment cycle fields (sentinel dates, medication calendar, status, remarks)."""
    cycle = await db.get(TreatmentCycle, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Treatment cycle not found")

    if payload.status:
        cycle.status = payload.status
    if payload.sentinel_dates is not None:
        cycle.sentinel_dates = {**dict(cycle.sentinel_dates or {}), **payload.sentinel_dates}
    if payload.endometrial_monitoring is not None:
        cycle.endometrial_monitoring = payload.endometrial_monitoring
    if payload.medication_calendar is not None:
        cycle.medication_calendar = payload.medication_calendar
    if payload.et_discharge_summary is not None:
        cycle.et_discharge_summary = {**dict(cycle.et_discharge_summary or {}), **payload.et_discharge_summary}
    if payload.remarks is not None:
        cycle.remarks = payload.remarks
    if payload.cancellation_reason:
        cycle.cancellation_reason = payload.cancellation_reason

    await db.flush()
    await db.refresh(cycle)
    patient = await db.get(Patient, cycle.patient_id) if cycle.patient_id else None
    partner = await db.get(Patient, cycle.partner_id) if cycle.partner_id else None
    return serialize_treatment_cycle(cycle, patient, partner)


@router.patch("/{cycle_id}/et-discharge")
async def update_et_discharge(
    cycle_id: UUID,
    payload: ETDischargeUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Save specialized Embryo Transfer discharge protocol & luteal support schedule."""
    cycle = await db.get(TreatmentCycle, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Treatment cycle not found")

    summary = dict(getattr(cycle, "et_discharge_summary", {}) or {})
    summary.update(payload.dict())
    summary["recorded_at"] = datetime.utcnow().isoformat() + "Z"
    cycle.et_discharge_summary = summary

    s_dates = dict(cycle.sentinel_dates or {})
    if payload.beta_hcg_due_date:
        s_dates["beta_hcg_due"] = payload.beta_hcg_due_date
    cycle.sentinel_dates = s_dates

    await db.flush()
    await db.refresh(cycle)
    patient = await db.get(Patient, cycle.patient_id) if cycle.patient_id else None
    partner = await db.get(Patient, cycle.partner_id) if cycle.partner_id else None
    return {
        "message": "Embryo Transfer discharge summary saved successfully",
        "cycle": serialize_treatment_cycle(cycle, patient, partner)
    }


@router.get("/{cycle_id}/medication-calendar")
@router.get("/{cycle_id}/calendar")
async def get_cycle_medication_calendar(cycle_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Generate day-by-day medication timetable using the Protocol Rules Engine or custom calendar.
    """
    cycle = await db.get(TreatmentCycle, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Treatment cycle not found")

    # If structured medication_calendar was saved
    if getattr(cycle, "medication_calendar", None) and len(cycle.medication_calendar) > 0:
        return {
            "cycle_id": cycle.cycle_id,
            "treatment_type": cycle.treatment_type,
            "days": cycle.medication_calendar,
        }

    # If custom medications calendar was explicitly saved in sentinel_dates
    if cycle.sentinel_dates and "custom_calendar" in cycle.sentinel_dates:
        custom_days = cycle.sentinel_dates["custom_calendar"]
        if custom_days:
            return {
                "cycle_id": cycle.cycle_id,
                "treatment_type": cycle.treatment_type,
                "days": custom_days,
            }

    rules_data = []
    if cycle.protocol_template_id:
        result = await db.execute(
            select(ProtocolDrugRule)
            .where(ProtocolDrugRule.protocol_template_id == cycle.protocol_template_id)
            .order_by(ProtocolDrugRule.sort_order)
        )
        rules = result.scalars().all()
        for r in rules:
            rules_data.append({
                "drug_name": r.drug_name,
                "dose": r.dose,
                "route": r.route,
                "frequency": r.frequency,
                "sentinel_anchor": r.sentinel_anchor,
                "day_start_offset": r.day_start_offset,
                "day_end_offset": r.day_end_offset,
                "instructions": r.instructions,
            })

    calendar = generate_medication_calendar(
        rules=rules_data,
        sentinel_dates=cycle.sentinel_dates or {},
        total_days=21,
    )
    calendar["cycle_id"] = cycle.cycle_id
    calendar["treatment_type"] = cycle.treatment_type
    return calendar


@router.post("/{cycle_id}/medications")
async def add_cycle_medication(
    cycle_id: UUID,
    payload: MedicationAddRequest,
    db: AsyncSession = Depends(get_db),
):
    """Add or update medication on a specific day of the treatment cycle."""
    cycle = await db.get(TreatmentCycle, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Treatment cycle not found")

    calendar = await get_cycle_medication_calendar(cycle_id, db)
    days = calendar.get("days", [])
    found = False
    for d in days:
        if d.get("day_number") == payload.day_number:
            if "medications" not in d or not isinstance(d["medications"], list):
                d["medications"] = []
            d["medications"].append({
                "drug_name": payload.drug_name,
                "dose": payload.dose,
                "frequency": payload.frequency,
                "instructions": payload.instructions or "",
            })
            found = True
            break

    if not found and days:
        days[0]["medications"] = [{
            "drug_name": payload.drug_name,
            "dose": payload.dose,
            "frequency": payload.frequency,
            "instructions": payload.instructions or "",
        }]

    current_sentinel = dict(cycle.sentinel_dates or {})
    current_sentinel["custom_calendar"] = days
    cycle.sentinel_dates = current_sentinel

    await db.flush()
    await db.refresh(cycle)
    return {"message": "Medication added successfully", "days": days}
