import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from uuid import UUID

from app.core.models import Patient, User
from app.modules.ipd.model import Ward, Bed, IPDAdmission, NursingTask
from app.modules.ipd.schemas import (
    WardCreate, WardUpdate, BedCreate, BedUpdate, BedStatusUpdate,
    AdmissionCreate, DischargeRequest, TransferBedRequest,
    NursingTaskCreate, NursingTaskComplete
)

class IPDService:
    def __init__(self, db: AsyncSession):
        self.db = db



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
                        "admission_date": adm.admission_date.isoformat(),
                        "package_name": adm.package_name,
                        "total_accrued_amount": adm.total_accrued_amount,
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

        adm_num = f"IPD-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"

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
            last_accrual_date=datetime.utcnow(),
            notes=payload.notes,
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
        return {"message": "Patient successfully admitted to IPD", "admission_id": str(admission.id), "admission_number": adm_num}

    async def discharge_patient(self, admission_id: UUID, payload: DischargeRequest):
        admission = await self.db.get(IPDAdmission, admission_id)
        if not admission:
            raise ValueError("Admission not found")

        admission.status = "Discharged"
        admission.discharge_date = datetime.utcnow()
        if payload.notes:
            admission.notes = f"{admission.notes or ''}\nDischarge note: {payload.notes}"

        bed = await self.db.get(Bed, admission.bed_id)
        if bed:
            bed.status = "Cleaning"
            bed.current_admission_id = None

        await self.db.flush()
        return {"message": "Patient discharged successfully. Bed set to Cleaning mode."}

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
            enriched.append({
                "id": str(adm.id),
                "admission_number": adm.admission_number,
                "patient_id": str(adm.patient_id),
                "patient_name": pat.name if pat else "Unknown",
                "patient_mrn": getattr(pat, "mrn", getattr(pat, "vid", "—")),
                "bed_id": str(adm.bed_id),
                "bed_number": bed.bed_number if bed else "—",
                "admitting_doctor_id": str(adm.admitting_doctor_id) if adm.admitting_doctor_id else None,
                "admitting_doctor": doc.name if doc else "Attending Physician",
                "diagnosis": adm.diagnosis,
                "package_name": adm.package_name,
                "admission_date": adm.admission_date.isoformat() if adm.admission_date else "",
                "discharge_date": adm.discharge_date.isoformat() if adm.discharge_date else None,
                "status": adm.status,
                "total_accrued_amount": adm.total_accrued_amount or 0.0,
                "notes": adm.notes,
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

        if old_bed:
            old_bed.status = "Cleaning"
            old_bed.current_admission_id = None

        new_bed.status = "Occupied"
        new_bed.current_admission_id = admission.id
        admission.bed_id = new_bed.id
        await self.db.flush()
        return {"message": f"Patient transferred to bed {new_bed.bed_number}", "bed_id": str(new_bed.id)}

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
                "scheduled_time": t.scheduled_time.isoformat() if t.scheduled_time else "",
                "status": t.status,
                "completed_by_id": str(t.completed_by_id) if t.completed_by_id else None,
                "completed_by_name": user.name if user else None,
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
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
            scheduled_time=payload.scheduled_time or datetime.utcnow(),
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
        task.completed_at = datetime.utcnow()
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

    async def accrue_daily_charges(self, tenant_id: Optional[UUID] = None):
        query = select(IPDAdmission).where(IPDAdmission.status.in_(["Active", "Admitted"]))
        if tenant_id:
            query = query.where(IPDAdmission.tenant_id == tenant_id)
        result = await self.db.execute(query)
        admissions = result.scalars().all()
        count = 0
        for adm in admissions:
            bed = await self.db.get(Bed, adm.bed_id)
            if bed and bed.daily_rate:
                adm.total_accrued_amount = (adm.total_accrued_amount or 0.0) + bed.daily_rate
                adm.last_accrual_date = datetime.utcnow()
                count += 1
        await self.db.flush()
        return {"success": True, "message": f"Daily charges accrued for {count} active inpatient admissions"}

