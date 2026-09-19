import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.core.models import ClinicalRecord, Patient, User
from app.core.hl7_server import parse_hl7_message, save_hl7_clinical_record
from app.modules.lims.schemas import ManualLabReportCreate, ReportAuthorizeRequest

class LIMSService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_manual_lab_report(self, payload: ManualLabReportCreate, current_user: User):
        patient = await self.db.get(Patient, payload.patient_id)
        if not patient:
            raise ValueError("Patient not found")

        sample_id = payload.sample_id or f"LAB-{datetime.utcnow().strftime('%y%m')}-{uuid.uuid4().hex[:4].upper()}"

        record_data = {
            "sample_id": sample_id,
            "patient_name": patient.name,
            "patient_mrn": patient.vid,
            "test_name": payload.test_name,
            "category": payload.category,
            "analyzer_id": "MANUAL-BENCH",
            "status": payload.status,
            "observations": payload.observations,
            "pathologist_notes": payload.pathologist_notes,
            "entered_by": current_user.name,
            "entered_at": datetime.utcnow().isoformat(),
        }

        record = ClinicalRecord(
            patient_id=payload.patient_id,
            plugin_id="lims",
            record_type="diagnostic_lab_report",
            schema_version="1.0",
            data=record_data,
            created_by=current_user.id,
        )
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)

        return {
            "status": "success",
            "record_id": str(record.id),
            "sample_id": sample_id,
            "test_name": payload.test_name,
            "message": f"Manual lab report for '{payload.test_name}' queued into LIMS worklist.",
        }

    async def get_lims_worklist(self, status: str = None, tenant_id: UUID = None):
        query = (
            select(ClinicalRecord, Patient)
            .join(Patient, ClinicalRecord.patient_id == Patient.id)
            .where(
                ClinicalRecord.record_type.in_(["casa_semen_analysis", "diagnostic_lab_report", "hematology_cbc"])
            )
            .order_by(ClinicalRecord.created_at.desc())
        )
        if tenant_id:
            query = query.where(Patient.tenant_id == tenant_id)

        res = await self.db.execute(query)
        rows = res.all()

        worklist = []
        for r, pat in rows:
            current_status = r.data.get("status", "Pending Authorization")
            if status and current_status != status:
                continue

            worklist.append({
                "id": str(r.id),
                "patient_id": str(r.patient_id),
                "patient_name": pat.name if pat else r.data.get("patient_name", "Unknown Patient"),
                "patient_mrn": pat.vid if pat else r.data.get("patient_mrn", "—"),
                "gender": pat.gender if pat else "—",
                "age": pat.age if pat else "—",
                "test_name": r.data.get("test_name", "Laboratory Test"),
                "sample_id": r.data.get("sample_id", f"SMP-{str(r.id)[:6].upper()}"),
                "analyzer_id": r.data.get("analyzer_id", "MINDRAY-BC5000"),
                "status": current_status,
                "observations_count": len(r.data.get("observations", {})),
                "observations": r.data.get("observations", {}),
                "pathologist_notes": r.data.get("pathologist_notes"),
                "authorized_by": r.data.get("authorized_by"),
                "authorized_at": r.data.get("authorized_at"),
                "created_at": r.created_at.isoformat(),
            })
        return worklist

    async def get_lims_record_detail(self, record_id: UUID, tenant_id: UUID = None):
        record = await self.db.get(ClinicalRecord, record_id)
        if not record:
            raise ValueError("Lab record not found")

        pat = await self.db.get(Patient, record.patient_id)
        if tenant_id and pat and pat.tenant_id != tenant_id:
            raise PermissionError("Unauthorized access to lab record")

        return {
            "id": str(record.id),
            "patient": {
                "id": str(pat.id) if pat else None,
                "name": pat.name if pat else "Unknown",
                "mrn": pat.vid if pat else "—",
                "gender": pat.gender if pat else "—",
                "age": pat.age if pat else "—",
                "blood_group": pat.blood_group if pat else "—",
            },
            "data": record.data,
            "created_at": record.created_at.isoformat(),
        }

    async def authorize_lab_report(self, record_id: UUID, payload: ReportAuthorizeRequest, current_user: User):
        record = await self.db.get(ClinicalRecord, record_id)
        if not record:
            raise ValueError("Lab record not found")

        pat = await self.db.get(Patient, record.patient_id)
        if current_user.tenant_id and pat and pat.tenant_id != current_user.tenant_id:
            raise PermissionError("Cannot authorize record outside of current tenant")

        pathologist_id = payload.pathologist_id or current_user.id
        doctor = await self.db.get(User, pathologist_id)
        doc_name = doctor.name if doctor else "Pathologist In-Charge"

        updated_data = dict(record.data or {})
        updated_data["status"] = "Authorized"
        updated_data["authorized_by"] = doc_name
        updated_data["authorized_by_id"] = str(pathologist_id)
        updated_data["authorized_at"] = datetime.utcnow().isoformat()
        if payload.comments:
            updated_data["pathologist_notes"] = payload.comments
        if payload.verified_values:
            updated_data["observations"] = {**updated_data.get("observations", {}), **payload.verified_values}

        record.data = updated_data
        await self.db.flush()
        await self.db.refresh(record)

        return {
            "message": "Lab report authorized and published to Patient EMR successfully.",
            "record_id": str(record.id),
            "status": "Authorized",
            "authorized_by": doc_name,
        }
