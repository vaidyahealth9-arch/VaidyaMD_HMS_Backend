import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from uuid import UUID

from app.core.timezone import get_now_ist, get_now_ist_naive, get_today_ist, to_ist_iso
from app.core.models import Patient, User
from app.modules.ipd.model import (
    Ward, Bed, IPDAdmission, NursingTask,
    IPDRoundNote, IPDOrder, IPDFluidBalance,
    IPDBillItem, IPDPayment
)
from app.modules.ipd.schemas import (
    WardCreate, WardUpdate, BedCreate, BedUpdate, BedStatusUpdate,
    AdmissionCreate, AdmissionUpdate, DischargeRequest, TransferBedRequest,
    DischargeSummarySave, NursingTaskCreate, NursingTaskComplete,
    RoundNoteCreate, OrderCreate, OrderStatusUpdate, OrderAdministerPayload,
    FluidBalanceCreate, BillItemCreate, PaymentCreate, SettleBillItemsRequest
)

class IPDService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # -------------------------------------------------------------------------
    # WARDS
    # -------------------------------------------------------------------------
    async def list_wards(self, tenant_id: Optional[UUID] = None):
        query = select(Ward).where(Ward.is_active == True)
        if tenant_id:
            query = query.where(Ward.tenant_id == tenant_id)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def create_ward(self, payload: WardCreate, tenant_id: Optional[UUID] = None):
        ward = Ward(
            name=payload.name,
            code=payload.code,
            department=payload.department,
            base_charge_per_day=payload.base_charge_per_day,
            total_beds=payload.total_beds,
            branch_id=payload.branch_id,
            tenant_id=tenant_id,
        )
        self.db.add(ward)
        await self.db.flush()
        for i in range(1, payload.total_beds + 1):
            bed = Bed(
                tenant_id=ward.tenant_id,
                branch_id=ward.branch_id,
                ward_id=ward.id,
                bed_number=f"{payload.code}-{i:02d}",
                daily_rate=payload.base_charge_per_day,
                status="Vacant",
            )
            self.db.add(bed)
        await self.db.flush()
        await self.db.refresh(ward)
        return ward

    async def update_ward(self, ward_id: UUID, payload: WardUpdate):
        ward = await self.db.get(Ward, ward_id)
        if not ward:
            raise ValueError("Ward not found")
        if payload.name is not None:
            ward.name = payload.name
        if payload.department is not None:
            ward.department = payload.department
        if payload.base_charge_per_day is not None:
            ward.base_charge_per_day = payload.base_charge_per_day
        if payload.is_active is not None:
            ward.is_active = payload.is_active
        await self.db.flush()
        await self.db.refresh(ward)
        return ward

    async def delete_ward(self, ward_id: UUID):
        ward = await self.db.get(Ward, ward_id)
        if not ward:
            raise ValueError("Ward not found")
        occupied_res = await self.db.execute(select(Bed).where(Bed.ward_id == ward_id, Bed.status == "Occupied"))
        if occupied_res.scalars().first():
            raise ValueError("Cannot deactivate ward with occupied beds. Discharge or transfer patients first.")
        ward.is_active = False
        await self.db.flush()
        return {"message": "Ward deactivated successfully"}

    # -------------------------------------------------------------------------
    # BEDS
    # -------------------------------------------------------------------------
    async def list_beds(self, ward_id: UUID = None, status: str = None, tenant_id: Optional[UUID] = None):
        query = select(Bed).join(Ward, Bed.ward_id == Ward.id).order_by(Bed.bed_number)
        if tenant_id:
            query = query.where(Ward.tenant_id == tenant_id)
        if ward_id:
            query = query.where(Bed.ward_id == ward_id)
        if status:
            query = query.where(Bed.status == status)

        result = await self.db.execute(query)
        beds = result.scalars().all()

        enriched = []
        for b in beds:
            adm_info = None
            if b.current_admission_id:
                adm = await self.db.get(IPDAdmission, b.current_admission_id)
                if adm:
                    pat = await self.db.get(Patient, adm.patient_id)
                    doc = await self.db.get(User, adm.admitting_doctor_id) if adm.admitting_doctor_id else None
                    adm_info = {
                        "admission_id": str(adm.id),
                        "admission_number": adm.admission_number,
                        "patient_id": str(adm.patient_id),
                        "patient_name": pat.name if pat else "Unknown",
                        "patient_mrn": getattr(pat, "mrn", getattr(pat, "vid", "—")),
                        "admitting_doctor": doc.name if doc else "Attending Physician",
                        "diagnosis": adm.diagnosis,
                        "admission_date": adm.admission_date.isoformat() if adm.admission_date else "",
                        "package_name": adm.package_name,
                        "total_accrued_amount": adm.total_accrued_amount,
                        "allergies": adm.allergies or [],
                        "risk_factors": adm.risk_factors or {},
                    }

            enriched.append({
                "id": str(b.id),
                "ward_id": str(b.ward_id),
                "bed_number": b.bed_number,
                "bed_type": b.bed_type,
                "status": b.status,
                "daily_rate": b.daily_rate,
                "current_admission": adm_info,
            })
        return enriched

    async def create_bed(self, payload: BedCreate, tenant_id: Optional[UUID] = None):
        ward = await self.db.get(Ward, payload.ward_id)
        if not ward:
            raise ValueError("Ward not found")
        if tenant_id and ward.tenant_id != tenant_id:
            raise ValueError("Ward does not belong to this hospital tenant")

        rate = payload.daily_rate if payload.daily_rate is not None else ward.base_charge_per_day
        bed = Bed(
            tenant_id=ward.tenant_id,
            branch_id=ward.branch_id,
            ward_id=ward.id,
            bed_number=payload.bed_number,
            bed_type=payload.bed_type or "Standard",
            daily_rate=rate,
            status=payload.status or "Vacant",
        )
        self.db.add(bed)
        ward.total_beds = (ward.total_beds or 0) + 1
        await self.db.flush()
        await self.db.refresh(bed)
        return {
            "id": str(bed.id),
            "ward_id": str(bed.ward_id),
            "bed_number": bed.bed_number,
            "bed_type": bed.bed_type,
            "daily_rate": bed.daily_rate,
            "status": bed.status,
        }

    async def update_bed(self, bed_id: UUID, payload: BedUpdate):
        bed = await self.db.get(Bed, bed_id)
        if not bed:
            raise ValueError("Bed not found")
        if payload.bed_number is not None:
            bed.bed_number = payload.bed_number
        if payload.bed_type is not None:
            bed.bed_type = payload.bed_type
        if payload.daily_rate is not None:
            bed.daily_rate = payload.daily_rate
        if payload.status is not None:
            bed.status = payload.status
        await self.db.flush()
        await self.db.refresh(bed)
        return {
            "id": str(bed.id),
            "ward_id": str(bed.ward_id),
            "bed_number": bed.bed_number,
            "bed_type": bed.bed_type,
            "daily_rate": bed.daily_rate,
            "status": bed.status,
        }

    async def delete_bed(self, bed_id: UUID):
        bed = await self.db.get(Bed, bed_id)
        if not bed:
            raise ValueError("Bed not found")
        if bed.status == "Occupied" or bed.current_admission_id:
            raise ValueError("Cannot delete bed while occupied or attached to an active admission.")
        ward = await self.db.get(Ward, bed.ward_id)
        if ward and ward.total_beds and ward.total_beds > 0:
            ward.total_beds -= 1
        await self.db.delete(bed)
        await self.db.flush()
        return {"message": "Bed deleted successfully"}

    async def update_bed_status(self, bed_id: UUID, payload: BedStatusUpdate):
        bed = await self.db.get(Bed, bed_id)
        if not bed:
            raise ValueError("Bed not found")
        bed.status = payload.status
        if payload.status == "Vacant":
            bed.current_admission_id = None
        await self.db.flush()
        return {"message": f"Bed status updated to {payload.status}", "bed_id": str(bed.id)}

    # -------------------------------------------------------------------------
    # ADMISSIONS & CLINICAL INPATIENT FILE
    # -------------------------------------------------------------------------
    async def admit_patient(self, payload: AdmissionCreate, tenant_id: Optional[UUID] = None, branch_id: Optional[UUID] = None):
        bed = await self.db.get(Bed, payload.bed_id)
        if not bed:
            raise ValueError("Bed not found")
        if bed.status == "Occupied":
            raise ValueError("Selected bed is already occupied.")

        patient = await self.db.get(Patient, payload.patient_id)
        if not patient:
            raise ValueError("Patient not found")

        resolved_tenant_id = tenant_id or getattr(bed, "tenant_id", None) or getattr(patient, "tenant_id", None)
        resolved_branch_id = branch_id or getattr(bed, "branch_id", None) or getattr(patient, "branch_id", None)

        adm_num = f"IPD-{get_today_ist().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"

        admission = IPDAdmission(
            admission_number=adm_num,
            tenant_id=resolved_tenant_id,
            branch_id=resolved_branch_id,
            patient_id=payload.patient_id,
            bed_id=payload.bed_id,
            admitting_doctor_id=payload.admitting_doctor_id,
            diagnosis=payload.diagnosis,
            package_name=payload.package_name,
            status="Active",
            total_accrued_amount=bed.daily_rate,
            last_accrual_date=get_now_ist_naive(),
            notes=payload.notes,
            allergies=payload.allergies or [],
            risk_factors=payload.risk_factors or {"fall_risk": False, "npo": False, "dvt_risk": False},
            advance_amount=payload.advance_amount or 0.0,
        )
        self.db.add(admission)
        await self.db.flush()

        bed.status = "Occupied"
        bed.current_admission_id = admission.id

        task1 = NursingTask(
            tenant_id=resolved_tenant_id,
            branch_id=resolved_branch_id,
            admission_id=admission.id,
            bed_id=bed.id,
            task_type="Vitals",
            description="Baseline Vitals & SpO2 Monitoring",
            frequency="Q4H",
            status="Pending",
        )
        task2 = NursingTask(
            tenant_id=resolved_tenant_id,
            branch_id=resolved_branch_id,
            admission_id=admission.id,
            bed_id=bed.id,
            task_type="Nursing Note",
            description="Inpatient Admission Assessment & Allergy Check",
            frequency="Stat",
            status="Pending",
        )
        self.db.add(task1)
        self.db.add(task2)

        await self.db.flush()
        await self.db.refresh(admission)
        return {
            "message": "Patient successfully admitted to IPD",
            "admission_id": str(admission.id),
            "admission_number": adm_num
        }

    async def get_admission_details(self, admission_id: UUID):
        admission = await self.db.get(IPDAdmission, admission_id)
        if not admission:
            raise ValueError("Admission not found")

        patient = await self.db.get(Patient, admission.patient_id)
        partner = await self.db.get(Patient, patient.partner_id) if patient and getattr(patient, 'partner_id', None) else None
        bed = await self.db.get(Bed, admission.bed_id) if admission.bed_id else None
        ward = await self.db.get(Ward, bed.ward_id) if bed and bed.ward_id else None
        doctor = await self.db.get(User, admission.admitting_doctor_id) if admission.admitting_doctor_id else None

        adm_date = admission.admission_date or datetime.utcnow()
        end_date = admission.discharge_date or datetime.utcnow()
        duration_days = max(1, (end_date.date() - adm_date.date()).days + 1)

        # Round Notes
        r_query = select(IPDRoundNote).where(IPDRoundNote.admission_id == admission_id).order_by(IPDRoundNote.created_at.desc())
        r_res = await self.db.execute(r_query)
        round_notes = []
        for r in r_res.scalars().all():
            doc_user = await self.db.get(User, r.doctor_id) if r.doctor_id else None
            round_notes.append({
                "id": str(r.id),
                "doctor_id": str(r.doctor_id) if r.doctor_id else None,
                "doctor_name": doc_user.name if doc_user else "Doctor",
                "round_time": r.round_time.isoformat() if r.round_time else "",
                "subjective": r.subjective,
                "objective": r.objective,
                "assessment": r.assessment,
                "plan": r.plan,
                "notes": r.notes,
                "created_at": to_ist_iso(r.created_at) if r.created_at else "",
            })

        # Bedside Orders
        o_query = select(IPDOrder).where(IPDOrder.admission_id == admission_id).order_by(IPDOrder.created_at.desc())
        o_res = await self.db.execute(o_query)
        orders = []
        for o in o_res.scalars().all():
            ord_user = await self.db.get(User, o.ordered_by_id) if o.ordered_by_id else None
            orders.append({
                "id": str(o.id),
                "order_type": o.order_type,
                "item_name": o.item_name,
                "dosage": o.dosage,
                "route": o.route,
                "frequency": o.frequency,
                "duration": o.duration,
                "instructions": o.instructions,
                "status": o.status,
                "administered_logs": o.administered_logs or [],
                "ordered_by_name": ord_user.name if ord_user else None,
                "created_at": to_ist_iso(o.created_at) if o.created_at else "",
            })

        # Fluid Balance
        fb_query = select(IPDFluidBalance).where(IPDFluidBalance.admission_id == admission_id).order_by(IPDFluidBalance.record_date.desc())
        fb_res = await self.db.execute(fb_query)
        fluid_balances = []
        for fb in fb_res.scalars().all():
            rec_user = await self.db.get(User, fb.recorded_by_id) if fb.recorded_by_id else None
            total_in = (fb.intake_oral or 0) + (fb.intake_iv or 0) + (fb.intake_other or 0)
            total_out = (fb.output_urine or 0) + (fb.output_drain or 0) + (fb.output_vomitus or 0) + (fb.output_other or 0)
            fluid_balances.append({
                "id": str(fb.id),
                "record_date": to_ist_iso(fb.record_date) if fb.record_date else "",
                "shift": fb.shift,
                "intake_oral": fb.intake_oral,
                "intake_iv": fb.intake_iv,
                "intake_other": fb.intake_other,
                "total_intake": total_in,
                "output_urine": fb.output_urine,
                "output_drain": fb.output_drain,
                "output_vomitus": fb.output_vomitus,
                "output_other": fb.output_other,
                "total_output": total_out,
                "net_balance": round(total_in - total_out, 2),
                "notes": fb.notes,
                "recorded_by_name": rec_user.name if rec_user else "Staff Nurse",
            })

        # Nursing Tasks / Vitals
        nt_query = select(NursingTask).where(NursingTask.admission_id == admission_id).order_by(NursingTask.scheduled_time.desc())
        nt_res = await self.db.execute(nt_query)
        nursing_tasks = []
        for t in nt_res.scalars().all():
            comp_user = await self.db.get(User, t.completed_by_id) if t.completed_by_id else None
            nursing_tasks.append({
                "id": str(t.id),
                "task_type": t.task_type,
                "description": t.description,
                "frequency": t.frequency,
                "scheduled_time": to_ist_iso(t.scheduled_time) if t.scheduled_time else "",
                "status": t.status,
                "completed_at": to_ist_iso(t.completed_at),
                "completed_by_name": comp_user.name if comp_user else None,
                "vitals_payload": t.vitals_payload or {},
                "notes": t.notes,
            })

        return {
            "id": str(admission.id),
            "admission_number": admission.admission_number,
            "status": admission.status,
            "patient": {
                "id": str(patient.id) if patient else None,
                "name": patient.name if patient else "Inpatient",
                "vid": getattr(patient, "vid", getattr(patient, "mrn", "—")),
                "gender": getattr(patient, "gender", ""),
                "age": getattr(patient, "age", None),
                "phone": getattr(patient, "phone", ""),
                "alternate_phone": getattr(patient, "alternate_phone", None),
                "blood_group": getattr(patient, "blood_group", None),
                "photo_url": getattr(patient, "photo_url", None),
                "partner": {
                    "id": str(partner.id),
                    "name": partner.name,
                    "phone": partner.phone,
                    "vid": getattr(partner, "vid", "—"),
                } if partner else None,
            },
            "bed": {
                "id": str(bed.id) if bed else None,
                "bed_number": bed.bed_number if bed else "—",
                "bed_type": bed.bed_type if bed else "Standard",
                "daily_rate": bed.daily_rate if bed else 2000.0,
                "ward_id": str(ward.id) if ward else None,
                "ward_name": ward.name if ward else "Ward",
            },
            "admitting_doctor": {
                "id": str(doctor.id) if doctor else None,
                "name": doctor.name if doctor else "Attending Physician",
                "specialization": getattr(doctor, "specialization", None),
            },
            "credit_limit": getattr(admission, "credit_limit", 20000.0) or 20000.0,
            "attending_doctor_charge_per_day": getattr(admission, "attending_doctor_charge_per_day", 500.0) or 500.0,
            "admission_date": to_ist_iso(adm_date),
            "duration_days": duration_days,
            "diagnosis": admission.diagnosis,
            "package_name": admission.package_name,
            "notes": admission.notes,
            "allergies": admission.allergies or [],
            "risk_factors": admission.risk_factors or {"fall_risk": False, "npo": False, "dvt_risk": False},
            "advance_amount": admission.advance_amount or 0.0,
            "total_accrued_amount": admission.total_accrued_amount or 0.0,
            "discharge_summary": admission.discharge_summary or {},
            "round_notes": round_notes,
            "orders": orders,
            "fluid_balances": fluid_balances,
            "nursing_tasks": nursing_tasks,
        }

    async def update_admission(self, admission_id: UUID, payload: AdmissionUpdate):
        admission = await self.db.get(IPDAdmission, admission_id)
        if not admission:
            raise ValueError("Admission not found")
        if payload.diagnosis is not None:
            admission.diagnosis = payload.diagnosis
        if payload.package_name is not None:
            admission.package_name = payload.package_name
        if payload.notes is not None:
            admission.notes = payload.notes
        if payload.admitting_doctor_id is not None:
            admission.admitting_doctor_id = payload.admitting_doctor_id
        if payload.allergies is not None:
            admission.allergies = payload.allergies
        if payload.risk_factors is not None:
            admission.risk_factors = payload.risk_factors
        if payload.advance_amount is not None:
            admission.advance_amount = payload.advance_amount

        await self.db.flush()
        return {"message": "Admission record updated successfully", "admission_id": str(admission.id)}

    async def list_admissions(self, status: Optional[str] = None, tenant_id: Optional[UUID] = None):
        query = select(IPDAdmission).order_by(IPDAdmission.admission_date.desc())
        if tenant_id:
            query = query.where(IPDAdmission.tenant_id == tenant_id)
        if status:
            if status.lower() in ["active", "admitted"]:
                query = query.where(IPDAdmission.status.in_(["Active", "Admitted"]))
            else:
                query = query.where(IPDAdmission.status.ilike(f"%{status}%"))

        result = await self.db.execute(query)
        admissions = result.scalars().all()

        enriched = []
        for adm in admissions:
            pat = await self.db.get(Patient, adm.patient_id)
            doc = await self.db.get(User, adm.admitting_doctor_id) if adm.admitting_doctor_id else None
            bed = await self.db.get(Bed, adm.bed_id) if adm.bed_id else None
            ward = await self.db.get(Ward, bed.ward_id) if bed and bed.ward_id else None

            inv = None
            if adm.invoice_id:
                from app.modules.billing.model import Invoice
                inv = await self.db.get(Invoice, adm.invoice_id)

            stay_days = 1
            if adm.admission_date:
                end_dt = adm.discharge_date or datetime.utcnow()
                stay_days = max(1, (end_dt.date() - adm.admission_date.date()).days + 1)

            enriched.append({
                "id": str(adm.id),
                "admission_number": adm.admission_number,
                "patient_id": str(adm.patient_id),
                "patient_name": pat.name if pat else "Unknown",
                "patient_mrn": getattr(pat, "mrn", getattr(pat, "vid", "—")),
                "patient_phone": getattr(pat, "phone", None) if pat else None,
                "patient_age": getattr(pat, "age", None) if pat else None,
                "patient_gender": getattr(pat, "gender", None) if pat else None,
                "bed_id": str(adm.bed_id) if adm.bed_id else None,
                "bed_number": bed.bed_number if bed else "—",
                "ward_name": ward.name if ward else "Ward",
                "admitting_doctor_id": str(adm.admitting_doctor_id) if adm.admitting_doctor_id else None,
                "admitting_doctor": doc.name if doc else "Attending Physician",
                "diagnosis": adm.diagnosis,
                "package_name": adm.package_name,
                "admission_date": adm.admission_date.isoformat() if adm.admission_date else "",
                "discharge_date": adm.discharge_date.isoformat() if adm.discharge_date else None,
                "status": adm.status,
                "stay_days": stay_days,
                "total_accrued_amount": adm.total_accrued_amount or 0.0,
                "advance_amount": adm.advance_amount or 0.0,
                "allergies": adm.allergies or [],
                "risk_factors": adm.risk_factors or {},
                "notes": adm.notes,
                "invoice_id": str(adm.invoice_id) if adm.invoice_id else None,
                "invoice_number": inv.invoice_number if inv else None,
                "invoice_status": inv.status if inv else None,
                "invoice_total": float(inv.total_amount) if inv and inv.total_amount is not None else float(adm.total_accrued_amount or 0.0),
                "discharge_summary": adm.discharge_summary or {},
            })
        return enriched

    async def transfer_bed(self, admission_id: UUID, payload: TransferBedRequest):
        admission = await self.db.get(IPDAdmission, admission_id)
        if not admission:
            raise ValueError("Admission not found")
        old_bed = await self.db.get(Bed, admission.bed_id)
        new_bed = await self.db.get(Bed, payload.target_bed_id)
        if not new_bed:
            raise ValueError("Target bed not found")
        if new_bed.status == "Occupied":
            raise ValueError("Target bed is already occupied")

        old_bed_num = old_bed.bed_number if old_bed else "Previous Bed"
        if old_bed:
            old_bed.status = "Cleaning"
            old_bed.current_admission_id = None

        new_bed.status = "Occupied"
        new_bed.current_admission_id = admission.id
        admission.bed_id = new_bed.id

        transfer_log = f"\n[Bed Transfer on {get_now_ist_naive().strftime('%Y-%m-%d %H:%M')}] Shifting from Bed {old_bed_num} to Bed {new_bed.bed_number}. Reason: {payload.notes or 'Clinical / Administrative request'}"
        admission.notes = f"{admission.notes or ''}{transfer_log}"

        await self.db.flush()
        return {"message": f"Patient successfully transferred to bed {new_bed.bed_number}", "bed_id": str(new_bed.id)}

    # -------------------------------------------------------------------------
    # DOCTOR ROUND NOTES (SOAP)
    # -------------------------------------------------------------------------
    async def add_round_note(self, admission_id: UUID, payload: RoundNoteCreate, user: User):
        admission = await self.db.get(IPDAdmission, admission_id)
        if not admission:
            raise ValueError("Admission not found")

        doc_id = payload.doctor_id or user.id
        note = IPDRoundNote(
            tenant_id=admission.tenant_id,
            branch_id=admission.branch_id,
            admission_id=admission.id,
            doctor_id=doc_id,
            round_time=get_now_ist_naive(),
            subjective=payload.subjective,
            objective=payload.objective,
            assessment=payload.assessment,
            plan=payload.plan,
            notes=payload.notes,
        )
        self.db.add(note)
        await self.db.flush()
        await self.db.refresh(note)
        return {
            "id": str(note.id),
            "message": "Doctor round note documented successfully",
            "created_at": to_ist_iso(note.created_at),
        }

    async def list_round_notes(self, admission_id: UUID):
        query = select(IPDRoundNote).where(IPDRoundNote.admission_id == admission_id).order_by(IPDRoundNote.created_at.desc())
        res = await self.db.execute(query)
        notes = []
        for r in res.scalars().all():
            doc = await self.db.get(User, r.doctor_id) if r.doctor_id else None
            notes.append({
                "id": str(r.id),
                "doctor_name": doc.name if doc else "Doctor",
                "round_time": r.round_time.isoformat() if r.round_time else "",
                "subjective": r.subjective,
                "objective": r.objective,
                "assessment": r.assessment,
                "plan": r.plan,
                "notes": r.notes,
                "created_at": to_ist_iso(r.created_at) if r.created_at else "",
            })
        return notes

    # -------------------------------------------------------------------------
    # BEDSIDE ORDERS & eMAR
    # -------------------------------------------------------------------------
    async def create_order(self, admission_id: UUID, payload: OrderCreate, user: User):
        admission = await self.db.get(IPDAdmission, admission_id)
        if not admission:
            raise ValueError("Admission not found")

        order = IPDOrder(
            tenant_id=admission.tenant_id,
            branch_id=admission.branch_id,
            admission_id=admission.id,
            ordered_by_id=user.id,
            order_type=payload.order_type,
            item_name=payload.item_name,
            dosage=payload.dosage,
            route=payload.route,
            frequency=payload.frequency,
            duration=payload.duration,
            instructions=payload.instructions,
            status="Active",
            administered_logs=[],
        )
        self.db.add(order)
        await self.db.flush()

        # If it's a Medication or Nursing instruction, create a pending bedside nursing task
        if payload.order_type in ["Medication", "Nursing Care"]:
            task = NursingTask(
                tenant_id=admission.tenant_id,
                branch_id=admission.branch_id,
                admission_id=admission.id,
                bed_id=admission.bed_id,
                task_type="Medication" if payload.order_type == "Medication" else "Nursing Note",
                description=f"{payload.item_name} {payload.dosage or ''} ({payload.route or 'Oral'}) - {payload.frequency}",
                frequency=payload.frequency or "OD",
                status="Pending",
            )
            self.db.add(task)
            await self.db.flush()

        await self.db.refresh(order)
        return {
            "id": str(order.id),
            "message": f"Inpatient order for '{order.item_name}' created successfully",
            "order_type": order.order_type,
            "status": order.status,
        }

    async def update_order_status(self, order_id: UUID, payload: OrderStatusUpdate):
        order = await self.db.get(IPDOrder, order_id)
        if not order:
            raise ValueError("Order not found")
        order.status = payload.status
        if payload.notes:
            order.instructions = f"{order.instructions or ''}\nStatus update: {payload.notes}".strip()
        await self.db.flush()
        return {"message": f"Order status updated to {payload.status}", "order_id": str(order.id)}

    async def administer_order(self, order_id: UUID, payload: OrderAdministerPayload, user: User):
        order = await self.db.get(IPDOrder, order_id)
        if not order:
            raise ValueError("Order not found")

        logs = list(order.administered_logs or [])
        logs.append({
            "id": uuid.uuid4().hex[:8],
            "timestamp": to_ist_iso(get_now_ist()),
            "status": payload.status,
            "nurse_name": payload.administered_by_name or user.name,
            "nurse_id": str(user.id),
            "notes": payload.notes,
        })
        order.administered_logs = logs
        await self.db.flush()
        return {"message": f"Medication dose marked as '{payload.status}'", "logs": logs}

    async def list_orders(self, admission_id: UUID):
        query = select(IPDOrder).where(IPDOrder.admission_id == admission_id).order_by(IPDOrder.created_at.desc())
        res = await self.db.execute(query)
        orders = []
        for o in res.scalars().all():
            ord_user = await self.db.get(User, o.ordered_by_id) if o.ordered_by_id else None
            orders.append({
                "id": str(o.id),
                "order_type": o.order_type,
                "item_name": o.item_name,
                "dosage": o.dosage,
                "route": o.route,
                "frequency": o.frequency,
                "duration": o.duration,
                "instructions": o.instructions,
                "status": o.status,
                "administered_logs": o.administered_logs or [],
                "ordered_by_name": ord_user.name if ord_user else None,
                "created_at": to_ist_iso(o.created_at) if o.created_at else "",
            })
        return orders

    # -------------------------------------------------------------------------
    # FLUID INTAKE / OUTPUT (I/O) BALANCE
    # -------------------------------------------------------------------------
    async def add_fluid_balance(self, admission_id: UUID, payload: FluidBalanceCreate, user: User):
        admission = await self.db.get(IPDAdmission, admission_id)
        if not admission:
            raise ValueError("Admission not found")

        fb = IPDFluidBalance(
            tenant_id=admission.tenant_id,
            branch_id=admission.branch_id,
            admission_id=admission.id,
            recorded_by_id=user.id,
            record_date=payload.record_date or get_now_ist_naive(),
            shift=payload.shift,
            intake_oral=payload.intake_oral,
            intake_iv=payload.intake_iv,
            intake_other=payload.intake_other,
            output_urine=payload.output_urine,
            output_drain=payload.output_drain,
            output_vomitus=payload.output_vomitus,
            output_other=payload.output_other,
            notes=payload.notes,
        )
        self.db.add(fb)
        await self.db.flush()
        await self.db.refresh(fb)
        return {"id": str(fb.id), "message": "Fluid intake/output record saved successfully"}

    async def list_fluid_balances(self, admission_id: UUID):
        query = select(IPDFluidBalance).where(IPDFluidBalance.admission_id == admission_id).order_by(IPDFluidBalance.record_date.desc())
        res = await self.db.execute(query)
        items = []
        for fb in res.scalars().all():
            user = await self.db.get(User, fb.recorded_by_id) if fb.recorded_by_id else None
            tot_in = (fb.intake_oral or 0) + (fb.intake_iv or 0) + (fb.intake_other or 0)
            tot_out = (fb.output_urine or 0) + (fb.output_drain or 0) + (fb.output_vomitus or 0) + (fb.output_other or 0)
            items.append({
                "id": str(fb.id),
                "record_date": to_ist_iso(fb.record_date) if fb.record_date else "",
                "shift": fb.shift,
                "intake_oral": fb.intake_oral,
                "intake_iv": fb.intake_iv,
                "intake_other": fb.intake_other,
                "total_intake": tot_in,
                "output_urine": fb.output_urine,
                "output_drain": fb.output_drain,
                "output_vomitus": fb.output_vomitus,
                "output_other": fb.output_other,
                "total_output": tot_out,
                "net_balance": round(tot_in - tot_out, 2),
                "notes": fb.notes,
                "recorded_by_name": user.name if user else "Staff Nurse",
            })
        return items

    # -------------------------------------------------------------------------
    # NURSING TASKS & VITALS
    # -------------------------------------------------------------------------
    async def list_nursing_tasks(
        self,
        admission_id: Optional[UUID] = None,
        bed_id: Optional[UUID] = None,
        status: Optional[str] = None,
        tenant_id: Optional[UUID] = None,
    ):
        query = select(NursingTask).order_by(NursingTask.scheduled_time.asc())
        if tenant_id:
            query = query.where(NursingTask.tenant_id == tenant_id)
        if admission_id:
            query = query.where(NursingTask.admission_id == admission_id)
        if bed_id:
            query = query.where(NursingTask.bed_id == bed_id)
        if status:
            query = query.where(NursingTask.status.ilike(f"%{status}%"))

        result = await self.db.execute(query)
        tasks = result.scalars().all()

        enriched = []
        for t in tasks:
            bed = await self.db.get(Bed, t.bed_id) if t.bed_id else None
            adm = await self.db.get(IPDAdmission, t.admission_id) if t.admission_id else None
            pat = await self.db.get(Patient, adm.patient_id) if adm and adm.patient_id else None
            user = await self.db.get(User, t.completed_by_id) if t.completed_by_id else None

            enriched.append({
                "id": str(t.id),
                "admission_id": str(t.admission_id),
                "bed_id": str(t.bed_id),
                "bed_number": bed.bed_number if bed else "—",
                "patient_name": pat.name if pat else "Inpatient",
                "task_type": t.task_type,
                "description": t.description,
                "frequency": t.frequency,
                "scheduled_time": to_ist_iso(t.scheduled_time) if t.scheduled_time else "",
                "status": t.status,
                "completed_by_id": str(t.completed_by_id) if t.completed_by_id else None,
                "completed_by_name": user.name if user else None,
                "completed_at": to_ist_iso(t.completed_at),
                "vitals_payload": t.vitals_payload or {},
                "notes": t.notes,
            })
        return enriched

    async def create_nursing_task(
        self,
        payload: NursingTaskCreate,
        tenant_id: Optional[UUID] = None,
        branch_id: Optional[UUID] = None,
    ):
        task = NursingTask(
            tenant_id=tenant_id,
            branch_id=branch_id,
            admission_id=payload.admission_id,
            bed_id=payload.bed_id,
            task_type=payload.task_type,
            description=payload.description,
            frequency=payload.frequency,
            scheduled_time=payload.scheduled_time or get_now_ist_naive(),
            status="Pending",
        )
        self.db.add(task)
        await self.db.flush()
        await self.db.refresh(task)
        return {
            "id": str(task.id),
            "message": "Nursing task created successfully",
            "task_type": task.task_type,
            "description": task.description,
        }

    async def complete_nursing_task(
        self,
        task_id: UUID,
        payload: NursingTaskComplete,
        user_id: Optional[UUID] = None,
    ):
        task = await self.db.get(NursingTask, task_id)
        if not task:
            raise ValueError("Nursing task not found")
        task.status = "Completed"
        task.completed_at = get_now_ist_naive()
        task.completed_by_id = payload.completed_by_id or user_id
        if payload.vitals_payload:
            task.vitals_payload = payload.vitals_payload
        if payload.notes:
            task.notes = f"{task.notes or ''}\n{payload.notes}".strip()
        await self.db.flush()
        return {
            "message": "Nursing task marked as completed",
            "task_id": str(task.id),
            "status": "Completed",
        }

    # -------------------------------------------------------------------------
    # DISCHARGE & BILLING CONSOLIDATION
    # -------------------------------------------------------------------------
    async def save_discharge_summary(self, admission_id: UUID, payload: DischargeSummarySave):
        admission = await self.db.get(IPDAdmission, admission_id)
        if not admission:
            raise ValueError("Admission not found")
        admission.discharge_summary = payload.model_dump()
        await self.db.flush()
        return {"message": "Clinical discharge summary saved successfully", "admission_id": str(admission.id)}

    # -------------------------------------------------------------------------
    # ROLLING BILL & DEPOSITS
    # -------------------------------------------------------------------------
    async def post_bill_item(
        self,
        admission_id: UUID,
        payload: BillItemCreate,
        current_user: Optional[User] = None,
    ):
        admission = await self.db.get(IPDAdmission, admission_id)
        if not admission:
            raise ValueError("Admission not found")

        qty = float(payload.quantity) if payload.quantity is not None else 1.0
        unit_price = float(payload.unit_price) if payload.unit_price is not None else 0.0
        total_price = round(qty * unit_price, 2)
        billing_date = payload.billing_date or get_now_ist_naive()

        item = IPDBillItem(
            tenant_id=admission.tenant_id,
            branch_id=admission.branch_id,
            admission_id=admission.id,
            item_type=payload.item_type,
            category=payload.category,
            service_code=payload.service_code,
            item_name=payload.item_name,
            quantity=qty,
            unit_price=unit_price,
            total_price=total_price,
            is_automated=False,
            billing_date=billing_date,
            source_module=payload.source_module or "ipd",
            source_reference_id=payload.source_reference_id,
            created_by_id=current_user.id if current_user else None,
            notes=payload.notes,
        )
        self.db.add(item)
        admission.total_accrued_amount = round((admission.total_accrued_amount or 0.0) + total_price, 2)
        await self.db.flush()
        await self.db.refresh(item)
        return {
            "id": str(item.id),
            "admission_id": str(item.admission_id),
            "item_type": item.item_type,
            "category": item.category,
            "service_code": item.service_code,
            "item_name": item.item_name,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "total_price": item.total_price,
            "is_automated": item.is_automated,
            "billing_date": item.billing_date.isoformat() if item.billing_date else None,
            "created_by_name": current_user.name if current_user else "Staff",
            "notes": item.notes,
        }

    async def list_bill_items(
        self,
        admission_id: UUID,
        item_type: Optional[str] = None,
        category: Optional[str] = None,
    ):
        query = (
            select(IPDBillItem, User.name.label("creator_name"))
            .outerjoin(User, IPDBillItem.created_by_id == User.id)
            .where(IPDBillItem.admission_id == admission_id)
            .order_by(IPDBillItem.billing_date.desc(), IPDBillItem.created_at.desc())
        )
        if item_type:
            query = query.where(IPDBillItem.item_type == item_type)
        if category:
            query = query.where(IPDBillItem.category == category)

        result = await self.db.execute(query)
        rows = result.all()
        return [
            {
                "id": str(row[0].id),
                "admission_id": str(row[0].admission_id),
                "item_type": row[0].item_type,
                "category": row[0].category,
                "service_code": row[0].service_code,
                "item_name": row[0].item_name,
                "quantity": row[0].quantity,
                "unit_price": row[0].unit_price,
                "total_price": row[0].total_price,
                "is_automated": row[0].is_automated,
                "billing_date": row[0].billing_date.isoformat() if row[0].billing_date else None,
                "source_module": row[0].source_module,
                "created_by_name": row[1] or ("Automated System" if row[0].is_automated else "Staff"),
                "notes": row[0].notes,
                "created_at": row[0].created_at.isoformat() if row[0].created_at else None,
            }
            for row in rows
        ]

    async def delete_bill_item(self, item_id: UUID, current_user: Optional[User] = None):
        item = await self.db.get(IPDBillItem, item_id)
        if not item:
            raise ValueError("Bill item not found")
        admission = await self.db.get(IPDAdmission, item.admission_id)
        if admission:
            admission.total_accrued_amount = max(0.0, round((admission.total_accrued_amount or 0.0) - item.total_price, 2))
        await self.db.delete(item)
        await self.db.flush()
        return {"message": "Bill item removed successfully", "item_id": str(item_id)}

    async def post_advance_payment(
        self,
        admission_id: UUID,
        payload: PaymentCreate,
        current_user: Optional[User] = None,
    ):
        admission = await self.db.get(IPDAdmission, admission_id)
        if not admission:
            raise ValueError("Admission not found")

        receipt_number = f"IPD-REC-{get_today_ist().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        payment = IPDPayment(
            tenant_id=admission.tenant_id,
            branch_id=admission.branch_id,
            admission_id=admission.id,
            receipt_number=receipt_number,
            amount=round(float(payload.amount), 2),
            payment_method=payload.payment_method,
            transaction_reference=payload.transaction_reference,
            payment_date=get_now_ist_naive(),
            payment_type=payload.payment_type,
            notes=payload.notes,
            collected_by_id=current_user.id if current_user else None,
        )
        self.db.add(payment)

        if payload.payment_type in ["advance", "interim"]:
            admission.advance_amount = round((admission.advance_amount or 0.0) + payload.amount, 2)
        elif payload.payment_type == "refund":
            admission.advance_amount = max(0.0, round((admission.advance_amount or 0.0) - payload.amount, 2))

        # Dual Ledger Sync: sync deposit to patient's central wallet for unified billing
        try:
            from app.modules.wallet.model import PatientWallet, WalletTransaction, WalletTxType
            from decimal import Decimal
            w_res = await self.db.execute(select(PatientWallet).where(PatientWallet.patient_id == admission.patient_id))
            wallet = w_res.scalar_one_or_none()
            if not wallet:
                wallet = PatientWallet(
                    patient_id=admission.patient_id,
                    balance=Decimal("0.00"),
                    tenant_id=admission.tenant_id,
                    branch_id=admission.branch_id,
                )
                self.db.add(wallet)
                await self.db.flush()

            amount_dec = Decimal(str(payload.amount))
            if payload.payment_type in ["advance", "interim"]:
                wallet.balance = (wallet.balance or Decimal("0.00")) + amount_dec
                tx = WalletTransaction(
                    wallet_id=wallet.id,
                    amount=amount_dec,
                    transaction_type=WalletTxType.DEPOSIT,
                    description=f"IPD Advance Deposit - Adm #{admission.admission_number} ({receipt_number})",
                    reference=receipt_number,
                    tenant_id=admission.tenant_id,
                    branch_id=admission.branch_id,
                )
                self.db.add(tx)
            elif payload.payment_type == "refund":
                wallet.balance = max(Decimal("0.00"), (wallet.balance or Decimal("0.00")) - amount_dec)
                tx = WalletTransaction(
                    wallet_id=wallet.id,
                    amount=amount_dec,
                    transaction_type=WalletTxType.REFUND,
                    description=f"IPD Advance Refund - Adm #{admission.admission_number} ({receipt_number})",
                    reference=receipt_number,
                    tenant_id=admission.tenant_id,
                    branch_id=admission.branch_id,
                )
                self.db.add(tx)
        except Exception:
            pass

        await self.db.flush()
        await self.db.refresh(payment)
        return {
            "id": str(payment.id),
            "receipt_number": payment.receipt_number,
            "amount": payment.amount,
            "payment_method": payment.payment_method,
            "transaction_reference": payment.transaction_reference,
            "payment_date": payment.payment_date.isoformat(),
            "payment_type": payment.payment_type,
            "collected_by_name": current_user.name if current_user else "Cashier",
            "notes": payment.notes,
        }

    async def list_payments(self, admission_id: UUID):
        query = (
            select(IPDPayment, User.name.label("collector_name"))
            .outerjoin(User, IPDPayment.collected_by_id == User.id)
            .where(IPDPayment.admission_id == admission_id)
            .order_by(IPDPayment.payment_date.desc())
        )
        result = await self.db.execute(query)
        rows = result.all()
        return [
            {
                "id": str(row[0].id),
                "receipt_number": row[0].receipt_number,
                "amount": row[0].amount,
                "payment_method": row[0].payment_method,
                "transaction_reference": row[0].transaction_reference,
                "payment_date": row[0].payment_date.isoformat() if row[0].payment_date else None,
                "payment_type": row[0].payment_type,
                "collected_by_name": row[1] or "Cashier",
                "notes": row[0].notes,
            }
            for row in rows
        ]

    async def get_rolling_bill_summary(self, admission_id: UUID):
        admission = await self.db.get(IPDAdmission, admission_id)
        if not admission:
            raise ValueError("Admission not found")
        patient = await self.db.get(Patient, admission.patient_id)
        bed = await self.db.get(Bed, admission.bed_id) if admission.bed_id else None
        ward = await self.db.get(Ward, bed.ward_id) if bed and bed.ward_id else None
        doctor = await self.db.get(User, admission.admitting_doctor_id) if admission.admitting_doctor_id else None

        items_res = await self.db.execute(
            select(IPDBillItem, User.name.label("creator_name"))
            .outerjoin(User, IPDBillItem.created_by_id == User.id)
            .where(IPDBillItem.admission_id == admission_id)
            .order_by(IPDBillItem.billing_date.desc(), IPDBillItem.created_at.desc())
        )
        items_rows = items_res.all()

        payments_res = await self.db.execute(
            select(IPDPayment, User.name.label("collector_name"))
            .outerjoin(User, IPDPayment.collected_by_id == User.id)
            .where(IPDPayment.admission_id == admission_id)
            .order_by(IPDPayment.payment_date.desc())
        )
        payments_rows = payments_res.all()

        items = []
        category_breakdown: Dict[str, float] = {}
        total_gross = 0.0

        unbilled_total = 0.0
        billed_total = 0.0

        for it, creator in items_rows:
            tot = float(it.total_price or 0.0)
            total_gross += tot
            if it.is_billed:
                billed_total += tot
            else:
                unbilled_total += tot

            cat = it.category or "General"
            category_breakdown[cat] = round(category_breakdown.get(cat, 0.0) + tot, 2)
            items.append({
                "id": str(it.id),
                "item_type": it.item_type,
                "category": it.category,
                "service_code": it.service_code,
                "item_name": it.item_name,
                "quantity": it.quantity,
                "unit_price": it.unit_price,
                "total_price": it.total_price,
                "is_automated": it.is_automated,
                "is_billed": bool(it.is_billed),
                "status": it.status or ("billed" if it.is_billed else "unbilled"),
                "invoice_id": str(it.invoice_id) if it.invoice_id else None,
                "billed_at": it.billed_at.isoformat() if it.billed_at else None,
                "billing_date": it.billing_date.isoformat() if it.billing_date else None,
                "created_by_name": creator or ("Automated System" if it.is_automated else "Staff"),
                "notes": it.notes,
            })

        total_gross = round(total_gross, 2)
        unbilled_total = round(unbilled_total, 2)
        billed_total = round(billed_total, 2)

        payments = []
        total_advance = 0.0
        for p, collector in payments_rows:
            amt = float(p.amount or 0.0)
            if p.payment_type in ["advance", "interim", "final"]:
                total_advance += amt
            elif p.payment_type == "refund":
                total_advance -= amt
            payments.append({
                "id": str(p.id),
                "receipt_number": p.receipt_number,
                "amount": p.amount,
                "payment_method": p.payment_method,
                "transaction_reference": p.transaction_reference,
                "payment_date": p.payment_date.isoformat() if p.payment_date else None,
                "payment_type": p.payment_type,
                "invoice_id": str(p.invoice_id) if p.invoice_id else None,
                "collected_by_name": collector or "Cashier",
                "notes": p.notes,
            })

        total_advance = round(total_advance, 2)
        net_due = round(max(0.0, unbilled_total), 2)
        credit_limit = float(admission.credit_limit or 20000.0)
        is_credit_exceeded = net_due > credit_limit

        return {
            "admission_id": str(admission.id),
            "admission_number": admission.admission_number,
            "patient_id": str(admission.patient_id),
            "patient_name": patient.name if patient else "Unknown",
            "patient_mrn": getattr(patient, "mrn", getattr(patient, "vid", "—")),
            "bed_number": bed.bed_number if bed else "—",
            "ward_name": ward.name if ward else "—",
            "admitting_doctor": doctor.name if doctor else "Attending Physician",
            "admission_date": admission.admission_date.isoformat() if admission.admission_date else None,
            "total_gross": total_gross,
            "unbilled_total": unbilled_total,
            "billed_total": billed_total,
            "total_advance": total_advance,
            "net_due": net_due,
            "credit_limit": credit_limit,
            "is_credit_exceeded": is_credit_exceeded,
            "category_breakdown": category_breakdown,
            "items": items,
            "payments": payments,
        }

    async def calculate_discharge_summary(self, admission_id: UUID):
        admission = await self.db.get(IPDAdmission, admission_id)
        if not admission:
            raise ValueError("Admission not found")
        patient = await self.db.get(Patient, admission.patient_id)
        bed = await self.db.get(Bed, admission.bed_id) if admission.bed_id else None
        ward = await self.db.get(Ward, bed.ward_id) if bed and bed.ward_id else None
        doctor = await self.db.get(User, admission.admitting_doctor_id) if admission.admitting_doctor_id else None

        adm_date = admission.admission_date or datetime.utcnow()
        end_date = admission.discharge_date or datetime.utcnow()
        duration_days = max(1, (end_date.date() - adm_date.date()).days + 1)

        # Check existing UNBILLED bill items
        items_res = await self.db.execute(
            select(IPDBillItem).where(
                IPDBillItem.admission_id == admission_id,
                IPDBillItem.is_billed == False
            ).order_by(IPDBillItem.billing_date.asc())
        )
        existing_unbilled = items_res.scalars().all()

        all_items_count_res = await self.db.execute(
            select(func.count(IPDBillItem.id)).where(IPDBillItem.admission_id == admission_id)
        )
        total_items_ever = all_items_count_res.scalar() or 0

        suggested_items = []
        if existing_unbilled:
            for it in existing_unbilled:
                suggested_items.append({
                    "id": str(it.id),
                    "bill_item_id": str(it.id),
                    "description": it.item_name,
                    "quantity": it.quantity,
                    "unit_price": it.unit_price,
                    "total": it.total_price,
                    "service_code": it.service_code or "IPD-MISC",
                    "category": it.category or "General",
                    "item_type": it.item_type,
                })
        elif total_items_ever > 0:
            # All items were already billed in interim bills - no duplicate stay charges
            suggested_items = []
        else:
            daily_rate = float(bed.daily_rate) if bed and bed.daily_rate else 2000.0
            room_charge = round(daily_rate * duration_days, 2)
            suggested_items.append({
                "description": f"IPD Room Charges: {ward.name if ward else 'Ward'} - Bed {bed.bed_number if bed else 'Standard'} ({duration_days} day{'s' if duration_days > 1 else ''})",
                "quantity": duration_days,
                "unit_price": daily_rate,
                "total": room_charge,
                "service_code": "IPD-ROOM",
                "category": "Room & Bed",
                "item_type": "room_rent",
            })
            if doctor:
                doctor_visit_charge = round((admission.attending_doctor_charge_per_day or 500.0) * duration_days, 2)
                suggested_items.append({
                    "description": f"Doctor Rounding & Inpatient Care - Dr. {doctor.name} ({duration_days} visits)",
                    "quantity": duration_days,
                    "unit_price": admission.attending_doctor_charge_per_day or 500.0,
                    "total": doctor_visit_charge,
                    "service_code": "IPD-DOC-VISIT",
                    "category": "Doctor Consultation",
                    "item_type": "doctor_consultation",
                })

        subtotal = round(sum(it["total"] for it in suggested_items), 2)

        # Calculate actual advance payments
        pay_res = await self.db.execute(
            select(IPDPayment).where(IPDPayment.admission_id == admission_id)
        )
        all_payments = pay_res.scalars().all()
        if all_payments:
            advance_deduction = round(sum(
                p.amount if p.payment_type in ["advance", "interim"] else -p.amount
                for p in all_payments
            ), 2)
        else:
            advance_deduction = float(admission.advance_amount or 0.0)

        net_payable = max(0.0, round(subtotal - advance_deduction, 2))

        return {
            "admission_id": str(admission.id),
            "patient_id": str(admission.patient_id),
            "patient_name": patient.name if patient else "Patient",
            "patient_vid": getattr(patient, "vid", getattr(patient, "mrn", "")),
            "admission_date": to_ist_iso(adm_date),
            "duration_days": duration_days,
            "stay_days": duration_days,
            "bed_number": bed.bed_number if bed else "—",
            "ward_name": ward.name if ward else "—",
            "items": suggested_items,
            "suggested_items": suggested_items,
            "subtotal": subtotal,
            "advance_amount": advance_deduction,
            "net_payable": net_payable,
            "discharge_summary": admission.discharge_summary or {},
        }


    async def settle_bill_items(
        self,
        admission_id: UUID,
        payload: SettleBillItemsRequest,
        current_user: Optional[User] = None,
    ):
        admission = await self.db.get(IPDAdmission, admission_id)
        if not admission:
            raise ValueError("Admission not found")

        from app.modules.billing.model import Invoice
        invoice = await self.db.get(Invoice, payload.invoice_id)
        invoice_number = invoice.invoice_number if invoice else "INV"

        # Find items to settle
        if payload.item_ids and len(payload.item_ids) > 0:
            query = select(IPDBillItem).where(
                IPDBillItem.admission_id == admission_id,
                IPDBillItem.id.in_(payload.item_ids)
            )
        else:
            query = select(IPDBillItem).where(
                IPDBillItem.admission_id == admission_id,
                IPDBillItem.is_billed == False
            )
        res = await self.db.execute(query)
        items_to_settle = res.scalars().all()

        now = datetime.utcnow()
        item_status = "paid" if (payload.amount_paid and payload.amount_paid > 0) or (invoice and invoice.status == "paid") else "billed"

        for it in items_to_settle:
            it.is_billed = True
            it.status = item_status
            it.invoice_id = payload.invoice_id
            it.billed_at = now

        # Record payment receipt in ipd_payments
        payment_record = None
        if payload.amount_paid and float(payload.amount_paid) > 0:
            rec_num = f"IPD-REC-{now.strftime('%y%m%d%H%M')}-{str(uuid.uuid4())[:4].upper()}"
            pay_type = "final" if payload.is_discharge else "interim"
            payment_record = IPDPayment(
                tenant_id=admission.tenant_id,
                branch_id=admission.branch_id,
                admission_id=admission.id,
                receipt_number=rec_num,
                amount=round(float(payload.amount_paid), 2),
                payment_method=payload.payment_method or (invoice.payment_method if invoice else "cash"),
                transaction_reference=payload.transaction_reference or (invoice.invoice_number if invoice else None),
                payment_date=now,
                payment_type=pay_type,
                invoice_id=payload.invoice_id,
                notes=payload.notes or f"Settlement payment against Invoice #{invoice_number}",
                collected_by_id=current_user.id if current_user else None,
            )
            self.db.add(payment_record)

            if pay_type == "interim":
                admission.advance_amount = round(float(admission.advance_amount or 0.0) + float(payload.amount_paid), 2)

        if payload.is_discharge:
            admission.status = "Discharged"
            admission.discharge_date = now
            admission.invoice_id = payload.invoice_id
            if payload.discharge_summary:
                admission.discharge_summary = payload.discharge_summary
            if payload.notes:
                admission.notes = f"{admission.notes or ''}\nDischarge note: {payload.notes}".strip()

            if admission.bed_id:
                bed = await self.db.get(Bed, admission.bed_id)
                if bed:
                    bed.status = "Cleaning"

        # Update remaining unbilled total_accrued_amount
        unbilled_res = await self.db.execute(
            select(func.coalesce(func.sum(IPDBillItem.total_price), 0.0))
            .where(
                IPDBillItem.admission_id == admission_id,
                IPDBillItem.is_billed == False
            )
        )
        remaining_unbilled = float(unbilled_res.scalar() or 0.0)
        admission.total_accrued_amount = round(remaining_unbilled, 2)

        await self.db.flush()

        return {
            "message": "Bill items settled and payment recorded successfully",
            "invoice_id": str(payload.invoice_id),
            "invoice_number": invoice_number,
            "items_settled_count": len(items_to_settle),
            "amount_paid": float(payload.amount_paid or 0.0),
            "receipt_number": payment_record.receipt_number if payment_record else None,
            "remaining_unbilled_total": remaining_unbilled,
            "is_discharge": payload.is_discharge,
        }

    async def discharge_patient(self, admission_id: UUID, payload: DischargeRequest):
        admission = await self.db.get(IPDAdmission, admission_id)
        if not admission:
            raise ValueError("Admission not found")

        admission.status = "Discharged"
        admission.discharge_date = get_now_ist_naive()
        if getattr(payload, "invoice_id", None):
            admission.invoice_id = payload.invoice_id
        if payload.notes:
            admission.notes = f"{admission.notes or ''}\nDischarge note: {payload.notes}".strip()
        if payload.discharge_summary:
            admission.discharge_summary = payload.discharge_summary

        bed = await self.db.get(Bed, admission.bed_id)
        if bed:
            bed.status = "Cleaning"
            bed.current_admission_id = None

        await self.db.flush()
        return {"message": "Patient discharged successfully. Bed set to Cleaning mode."}

    async def accrue_daily_charges(self, tenant_id: Optional[UUID] = None):
        today = get_today_ist()
        query = select(IPDAdmission).where(IPDAdmission.status.in_(["Active", "Admitted"]))
        if tenant_id:
            query = query.where(IPDAdmission.tenant_id == tenant_id)
        result = await self.db.execute(query)
        admissions = result.scalars().all()

        accrued_count = 0
        items_created = 0

        for adm in admissions:
            bed = await self.db.get(Bed, adm.bed_id)
            if not bed:
                continue
            ward = await self.db.get(Ward, bed.ward_id) if bed.ward_id else None
            doctor = await self.db.get(User, adm.admitting_doctor_id) if adm.admitting_doctor_id else None

            # Check if automated daily charges already created today for this admission
            check_q = select(IPDBillItem).where(
                IPDBillItem.admission_id == adm.id,
                IPDBillItem.is_automated == True,
                IPDBillItem.item_type == "room_rent",
                func.date(IPDBillItem.billing_date) == today
            )
            already_done = (await self.db.execute(check_q)).scalars().first()
            if already_done:
                continue

            day_total = 0.0

            # 1. Room rent
            room_rate = float(bed.daily_rate) if bed.daily_rate else (float(ward.base_charge_per_day) if ward else 2000.0)
            item_room = IPDBillItem(
                tenant_id=adm.tenant_id,
                branch_id=adm.branch_id,
                admission_id=adm.id,
                item_type="room_rent",
                category="Room & Bed",
                service_code="IPD-ROOM",
                item_name=f"Daily Bed Charges: Ward {ward.name if ward else 'General'} - Bed {bed.bed_number}",
                quantity=1.0,
                unit_price=room_rate,
                total_price=room_rate,
                is_automated=True,
                billing_date=get_now_ist_naive(),
                source_module="ipd_scheduler",
                notes=f"Automated daily bed accrual for {today.strftime('%d %b %Y')}",
            )
            self.db.add(item_room)
            day_total += room_rate
            items_created += 1

            # 2. Nursing care
            nursing_rate = float(getattr(ward, 'nursing_charge_per_day', 500.0) or 500.0) if ward else 500.0
            item_nursing = IPDBillItem(
                tenant_id=adm.tenant_id,
                branch_id=adm.branch_id,
                admission_id=adm.id,
                item_type="nursing_care",
                category="Nursing Care",
                service_code="IPD-NURSING",
                item_name=f"Daily Inpatient Nursing Care & Monitoring ({ward.name if ward else 'Ward'})",
                quantity=1.0,
                unit_price=nursing_rate,
                total_price=nursing_rate,
                is_automated=True,
                billing_date=get_now_ist_naive(),
                source_module="ipd_scheduler",
                notes=f"Automated daily nursing charge for {today.strftime('%d %b %Y')}",
            )
            self.db.add(item_nursing)
            day_total += nursing_rate
            items_created += 1

            # 3. Doctor Rounding
            doc_rate = float(getattr(adm, 'attending_doctor_charge_per_day', 500.0) or 500.0)
            doc_name = doctor.name if doctor else "Attending Physician"
            clean_doc_title = doc_name if doc_name.lower().startswith('dr') else f"Dr. {doc_name}"
            item_doc = IPDBillItem(
                tenant_id=adm.tenant_id,
                branch_id=adm.branch_id,
                admission_id=adm.id,
                item_type="doctor_consultation",
                category="Doctor Consultation",
                service_code="IPD-DOC-VISIT",
                item_name=f"Inpatient Daily Physician Rounding - {clean_doc_title}",
                quantity=1.0,
                unit_price=doc_rate,
                total_price=doc_rate,
                is_automated=True,
                billing_date=get_now_ist_naive(),
                source_module="ipd_scheduler",
                notes=f"Automated physician rounding fee for {today.strftime('%d %b %Y')}",
            )
            self.db.add(item_doc)
            day_total += doc_rate
            items_created += 1

            # 4. Daily Diet if enabled
            if getattr(adm, 'daily_diet_enabled', False):
                diet_rate = float(getattr(ward, 'diet_charge_per_day', 300.0) or 300.0) if ward else 300.0
                item_diet = IPDBillItem(
                    tenant_id=adm.tenant_id,
                    branch_id=adm.branch_id,
                    admission_id=adm.id,
                    item_type="diet",
                    category="Diet & Nutrition",
                    service_code="IPD-DIET",
                    item_name="Inpatient Daily Diet & Nutrition Plan",
                    quantity=1.0,
                    unit_price=diet_rate,
                    total_price=diet_rate,
                    is_automated=True,
                    billing_date=get_now_ist_naive(),
                    source_module="ipd_scheduler",
                    notes=f"Automated daily meal plan for {today.strftime('%d %b %Y')}",
                )
                self.db.add(item_diet)
                day_total += diet_rate
                items_created += 1

            adm.total_accrued_amount = round((adm.total_accrued_amount or 0.0) + day_total, 2)
            adm.last_accrual_date = get_now_ist_naive()
            accrued_count += 1

        await self.db.flush()
        return {
            "success": True,
            "message": f"Accrued {items_created} daily charge line items across {accrued_count} active inpatient admissions.",
            "admissions_accrued": accrued_count,
            "items_created": items_created,
        }
