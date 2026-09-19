import uuid
from datetime import datetime
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
                        "patient_mrn": pat.mrn if pat else "—",
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

    async def update_bed_status(self, bed_id: UUID, payload: BedStatusUpdate):
        bed = await self.db.get(Bed, bed_id)
        if not bed:
            raise ValueError("Bed not found")
        bed.status = payload.status
        if payload.status == "Vacant":
            bed.current_admission_id = None
        await self.db.flush()
        return {"message": f"Bed status updated to {payload.status}", "bed_id": str(bed.id)}

    async def admit_patient(self, payload: AdmissionCreate):
        bed = await self.db.get(Bed, payload.bed_id)
        if not bed:
            raise ValueError("Bed not found")
        if bed.status == "Occupied":
            raise ValueError("Selected bed is already occupied.")

        patient = await self.db.get(Patient, payload.patient_id)
        if not patient:
            raise ValueError("Patient not found")

        adm_num = f"IPD-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"

        admission = IPDAdmission(
            admission_number=adm_num,
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
            admission_id=admission.id,
            bed_id=bed.id,
            task_type="Vitals",
            description="Baseline Vitals & SpO2 Monitoring",
            frequency="Q4H",
            status="Pending",
        )
        task2 = NursingTask(
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
