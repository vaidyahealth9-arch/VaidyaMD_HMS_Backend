import random
from typing import Optional
from uuid import UUID
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_

from app.core.models import Hospital, Appointment, ClinicalRecord, Document, TreatmentCycle, Invoice
from app.modules.patients.model import Patient, RegistrationType, Gender
from app.modules.patients.schemas import PatientCreate, PatientUpdate, PatientResponse, PatientListResponse, AlertNotesUpdate, ClinicalNotesUpdate, ConsentCreate
from app.modules.patients.exceptions import PatientNotFoundError, PartnerLinkError
from app.core.security import encrypt_pii, mask_pii

class PatientService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_vid(self, hospital_code: str) -> str:
        """Generate a collision-resistant unique VaidyaMD Patient ID"""
        result = await self.db.execute(select(func.count(Patient.id)))
        count = result.scalar() or 0
        base_num = count + 1
        for attempt in range(100):
            candidate = f"VH-{hospital_code}-{(base_num + attempt):05d}"
            existing = await self.db.execute(select(Patient.id).where(Patient.vid == candidate))
            if not existing.scalar_one_or_none():
                return candidate
        return f"VH-{hospital_code}-{base_num:05d}-{random.randint(100, 999)}"

    def build_patient_response(self, patient: Patient, partner: Optional[Patient] = None) -> PatientResponse:
        return PatientResponse(
            id=patient.id,
            vid=patient.vid,
            registration_type=patient.registration_type.value if hasattr(patient.registration_type, "value") else str(patient.registration_type),
            title=patient.title,
            name=patient.name,
            surname=patient.surname,
            age=patient.age,
            dob=patient.dob,
            gender=patient.gender.value if hasattr(patient.gender, "value") else str(patient.gender),
            marital_status=patient.marital_status,
            phone=patient.phone,
            alternate_phone=patient.alternate_phone,
            email=patient.email,
            address=patient.address,
            husband_alternate_phone=patient.husband_alternate_phone,
            education_qualification=patient.education_qualification,
            occupation=patient.occupation,
            nationality=patient.nationality,
            mother_tongue=patient.mother_tongue,
            blood_group=patient.blood_group,
            photo_url=patient.photo_url,
            identity_type=patient.identity_type,
            aadhaar_masked=mask_pii(patient.aadhaar_encrypted),
            abha_number=patient.abha_number,
            referred_by_type=patient.referred_by_type,
            referred_by_name=patient.referred_by_name,
            referring_doctor=patient.referring_doctor or patient.referred_by_name,
            marketing_person_name=patient.marketing_person_name,
            area=patient.area,
            financial_type=patient.financial_type,
            is_surrogate=patient.is_surrogate,
            partner_id=patient.partner_id,
            partner_name=partner.name if partner else None,
            partner_vid=partner.vid if partner else None,
            partner_age=partner.age if partner else None,
            partner_phone=partner.phone if partner else None,
            partner_blood_group=partner.blood_group if partner else None,
            tags=patient.tags or [],
            alert_notes=patient.alert_notes or [],
            clinical_notes=patient.clinical_notes or [],
            tenant_id=patient.tenant_id,
            branch_id=patient.branch_id,
            created_at=patient.created_at,
            updated_at=patient.updated_at,
        )

    async def create_patient(self, patient_data: PatientCreate, tenant_id: UUID) -> PatientResponse:
        result = await self.db.execute(select(Hospital).limit(1))
        hospital = result.scalar_one_or_none()
        h_code = hospital.code if hospital else "VMD"
        vid = await self.generate_vid(h_code)

        reg_type = RegistrationType.PATIENT
        if patient_data.registration_type == "donor_bank":
            reg_type = RegistrationType.DONOR_BANK
        elif patient_data.registration_type == "donor_hospital":
            reg_type = RegistrationType.DONOR_HOSPITAL

        patient = Patient(
            vid=vid,
            registration_type=reg_type,
            title=patient_data.title,
            name=patient_data.name,
            surname=patient_data.surname,
            surname_at_birth=patient_data.surname_at_birth,
            age=patient_data.age,
            dob=patient_data.dob,
            gender=Gender(patient_data.gender),
            marital_status=patient_data.marital_status,
            phone=patient_data.phone,
            alternate_phone=patient_data.alternate_phone,
            email=patient_data.email,
            alternate_email=patient_data.alternate_email,
            address=patient_data.address,
            husband_alternate_phone=patient_data.husband_alternate_phone,
            husband_alternate_address=patient_data.husband_alternate_address,
            education_qualification=patient_data.education_qualification,
            occupation=patient_data.occupation,
            nationality=patient_data.nationality or "Indian",
            mother_tongue=patient_data.mother_tongue,
            country_of_birth=patient_data.country_of_birth or "India",
            blood_group=patient_data.blood_group,
            photo_url=patient_data.photo_url,
            identity_type=patient_data.identity_type,
            aadhaar_encrypted=encrypt_pii(patient_data.aadhaar_number),
            identity_issued_country=patient_data.identity_issued_country or "India",
            abha_number=patient_data.abha_number,
            referred_by_type=patient_data.referred_by_type,
            referred_by_name=patient_data.referred_by_name or patient_data.referring_doctor,
            referring_doctor=patient_data.referring_doctor or patient_data.referred_by_name,
            marketing_person_name=patient_data.marketing_person_name,
            area=patient_data.area,
            treating_doctor_id=patient_data.treating_doctor_id,
            marketing_person_id=patient_data.marketing_person_id,
            financial_type=patient_data.financial_type or "self_pay",
            is_surrogate=patient_data.is_surrogate or False,
            partner_id=patient_data.partner_id,
            branch_id=patient_data.branch_id,
            tags=patient_data.tags or [],
            alert_notes=patient_data.alert_notes or [],
            clinical_notes=patient_data.clinical_notes or [],
            tenant_id=tenant_id,
        )

        self.db.add(patient)
        await self.db.flush()

        if patient_data.partner_id:
            partner = await self.db.get(Patient, patient_data.partner_id)
            if partner and partner.partner_id != patient.id:
                partner.partner_id = patient.id

        await self.db.flush()
        await self.db.refresh(patient)

        partner = await self.db.get(Patient, patient.partner_id) if patient.partner_id else None
        return self.build_patient_response(patient, partner)

    async def get_patient(self, patient_id: UUID) -> PatientResponse:
        patient = await self.db.get(Patient, patient_id)
        if not patient:
            raise PatientNotFoundError(f"Patient with ID {patient_id} not found")
        partner = await self.db.get(Patient, patient.partner_id) if patient.partner_id else None
        return self.build_patient_response(patient, partner)

    async def list_patients(self, tenant_id: UUID, branch_id: Optional[UUID] = None, page: int = 1, per_page: int = 50, search: Optional[str] = None) -> PatientListResponse:
        query = select(Patient).where(Patient.tenant_id == tenant_id)
        if branch_id:
            query = query.where(Patient.branch_id == branch_id)
        
        if search and search.strip():
            s = f"%{search.strip()}%"
            query = query.where(
                or_(
                    Patient.name.ilike(s),
                    Patient.surname.ilike(s),
                    Patient.vid.ilike(s),
                    Patient.phone.ilike(s),
                    Patient.email.ilike(s),
                )
            )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query) or 0
        
        # Get paginated data
        query = query.order_by(desc(Patient.created_at)).offset((page - 1) * per_page).limit(per_page)
        result = await self.db.execute(query)
        patients = result.scalars().all()
        
        # Pre-fetch partners for optimization
        partner_ids = [p.partner_id for p in patients if p.partner_id]
        partners_map = {}
        if partner_ids:
            p_res = await self.db.execute(select(Patient).where(Patient.id.in_(partner_ids)))
            partners_map = {p.id: p for p in p_res.scalars().all()}
            
        return PatientListResponse(
            patients=[self.build_patient_response(p, partners_map.get(p.partner_id)) for p in patients],
            total=total,
            page=page,
            per_page=per_page
        )

    async def get_timeline(self, patient_id: UUID) -> dict:
        patient = await self.db.get(Patient, patient_id)
        if not patient:
            raise PatientNotFoundError(f"Patient with ID {patient_id} not found")

        events = []

        # 1. Registration Event
        if patient.created_at:
            events.append({
                "type": "registration",
                "title": "Patient Registered",
                "description": f"Patient registration completed under {patient.vid} ({patient.registration_type or 'General'}).",
                "created_at": patient.created_at.isoformat() if hasattr(patient.created_at, 'isoformat') else str(patient.created_at),
                "metadata": {
                    "vid": patient.vid,
                    "gender": patient.gender,
                    "phone": patient.phone,
                }
            })

        # 2. Appointments
        apt_res = await self.db.execute(
            select(Appointment).where(Appointment.patient_id == patient_id).order_by(desc(Appointment.created_at))
        )
        for apt in apt_res.scalars().all():
            events.append({
                "type": "appointment",
                "title": f"Appointment — {apt.department or 'OPD'} ({apt.visit_type or 'Consultation'})",
                "description": f"Status: {str(apt.status).capitalize()} · {apt.notes or 'Routine attendance'}".strip(),
                "created_at": apt.created_at.isoformat() if hasattr(apt.created_at, 'isoformat') else str(apt.created_at),
                "metadata": {
                    "status": str(apt.status),
                    "department": apt.department,
                    "triage": getattr(apt, 'triage_notes', None),
                }
            })

        # 3. Clinical Records / Consultations
        cr_res = await self.db.execute(
            select(ClinicalRecord).where(ClinicalRecord.patient_id == patient_id).order_by(desc(ClinicalRecord.created_at))
        )
        for cr in cr_res.scalars().all():
            rec_d = cr.data or {}
            events.append({
                "type": "clinical_record",
                "title": f"Consultation ({str(cr.record_type).replace('_', ' ').title()})",
                "description": f"Dx: {rec_d.get('provisional_diagnosis') or rec_d.get('chief_complaints') or 'Clinical Review'}",
                "created_at": cr.created_at.isoformat() if hasattr(cr.created_at, 'isoformat') else str(cr.created_at),
                "metadata": {
                    "record_type": cr.record_type,
                    "plugin_id": cr.plugin_id,
                    "plan": rec_d.get('plan'),
                }
            })

        # 4. Invoices / Billing
        inv_res = await self.db.execute(
            select(Invoice).where(Invoice.patient_id == patient_id).order_by(desc(Invoice.created_at))
        )
        for inv in inv_res.scalars().all():
            events.append({
                "type": "invoice",
                "title": f"Invoice #{inv.invoice_number}",
                "description": f"Billed: ₹{float(inv.total_amount or 0):,.2f} · Status: {str(inv.status).upper()}",
                "created_at": inv.created_at.isoformat() if hasattr(inv.created_at, 'isoformat') else str(inv.created_at),
                "metadata": {
                    "total_amount": float(inv.total_amount or 0),
                    "status": str(inv.status),
                }
            })

        # 5. Treatment Cycles
        try:
            tc_res = await self.db.execute(
                select(TreatmentCycle).where(
                    or_(TreatmentCycle.patient_id == patient_id, TreatmentCycle.partner_id == patient_id)
                ).order_by(desc(TreatmentCycle.created_at))
            )
            for tc in tc_res.scalars().all():
                events.append({
                    "type": "treatment_cycle",
                    "title": f"Fertility Cycle ({tc.treatment_type or 'IVF'}) - {tc.cycle_id}",
                    "description": f"Attempt #{tc.attempt_number} · Status: {tc.status.value if hasattr(tc.status, 'value') else tc.status}",
                    "created_at": tc.created_at.isoformat() if hasattr(tc.created_at, 'isoformat') else str(tc.created_at),
                    "metadata": {
                        "cycle_id": tc.cycle_id,
                        "treatment_type": tc.treatment_type,
                        "status": str(tc.status),
                    }
                })
        except Exception:
            pass

        # 6. Cosmetic Gynecology Plans
        try:
            from app.core.models.cosgyn import CosgynPatientPlan
            cg_res = await self.db.execute(
                select(CosgynPatientPlan).where(CosgynPatientPlan.patient_id == str(patient_id)).order_by(desc(CosgynPatientPlan.created_at))
            )
            for cg in cg_res.scalars().all():
                events.append({
                    "type": "treatment_cycle",
                    "title": "Cosmetic Gynecology Package Scheduled",
                    "description": f"Total Package: ₹{float(cg.total_amount or 0):,.2f} · Frequency: {cg.frequency}",
                    "created_at": cg.created_at.isoformat() if hasattr(cg.created_at, 'isoformat') else str(cg.created_at),
                    "metadata": {
                        "total_amount": float(cg.total_amount or 0),
                    }
                })
        except Exception:
            pass

        # 7. Counseling Notes
        try:
            from app.modules.counseling.models import CounselingNote
            cn_res = await self.db.execute(
                select(CounselingNote).where(CounselingNote.patient_id == patient_id).order_by(desc(CounselingNote.created_at))
            )
            for cn in cn_res.scalars().all():
                events.append({
                    "type": "counseling",
                    "title": f"Pre-ART Counseling: {cn.procedure or 'General Counseling'}",
                    "description": f"Source: {cn.source or 'OP'} · Signed: {cn.signature or 'Counselor'} · Remarks: {cn.remarks or cn.discussion or 'Completed'}",
                    "created_at": cn.created_at.isoformat() if hasattr(cn.created_at, 'isoformat') else str(cn.created_at),
                    "metadata": {
                        "id": str(cn.id),
                        "source": cn.source,
                        "procedure": cn.procedure,
                        "discussion": cn.discussion,
                        "signature": cn.signature,
                    }
                })
        except Exception:
            pass

        events.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        return {
            "patient_id": str(patient_id),
            "patient_name": patient.name,
            "total_events": len(events),
            "timeline": events,
            "events": events,
        }
        
    async def get_couple_profile(self, patient_id: UUID):
        patient = await self.db.get(Patient, patient_id)
        if not patient:
            raise PatientNotFoundError()
        partner = await self.db.get(Patient, patient.partner_id) if patient.partner_id else None
        return {
            "primary_patient": self.build_patient_response(patient, partner),
            "partner": self.build_patient_response(partner, patient) if partner else None,
            "is_linked_couple": partner is not None,
        }

    async def link_partner(self, patient_id: UUID, partner_id: UUID) -> PatientResponse:
        patient = await self.db.get(Patient, patient_id)
        partner = await self.db.get(Patient, partner_id)
        if not patient or not partner:
            raise PatientNotFoundError()
        if patient.id == partner.id:
            raise PartnerLinkError("Cannot link a patient to themselves")
        patient.partner_id = partner.id
        partner.partner_id = patient.id
        await self.db.flush()
        await self.db.refresh(patient)
        return self.build_patient_response(patient, partner)

    async def unlink_partner(self, patient_id: UUID):
        patient = await self.db.get(Patient, patient_id)
        if not patient:
            raise PatientNotFoundError()
        if patient.partner_id:
            partner = await self.db.get(Patient, patient.partner_id)
            if partner and partner.partner_id == patient.id:
                partner.partner_id = None
            patient.partner_id = None
            await self.db.flush()
        return True

    async def update_patient(self, patient_id: UUID, patient_data: PatientUpdate) -> PatientResponse:
        patient = await self.db.get(Patient, patient_id)
        if not patient:
            raise PatientNotFoundError()

        update_dict = patient_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(patient, field, value)

        await self.db.flush()
        await self.db.refresh(patient)
        partner = await self.db.get(Patient, patient.partner_id) if patient.partner_id else None
        return self.build_patient_response(patient, partner)

    async def save_consent(self, patient_id: UUID, consent_data: Any, current_user: User) -> dict:
        patient = await self.db.get(Patient, patient_id)
        if not patient:
            raise PatientNotFoundError(f"Patient with ID {patient_id} not found")
        if patient.tenant_id != current_user.tenant_id:
            raise PermissionError("Cross-tenant consent recording denied")

        record = ClinicalRecord(
            patient_id=patient_id,
            plugin_id="fertility",
            record_type="art_statutory_consent",
            schema_version="1.0",
            data={
                "title": consent_data.title,
                "signature": consent_data.signature,
                "signed_at": datetime.utcnow().isoformat(),
                "patient_name": patient.name,
                "patient_vid": patient.vid,
            },
            created_by=current_user.id,
        )
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        return {
            "id": str(record.id),
            "patient_id": str(patient_id),
            "title": consent_data.title,
            "created_at": record.created_at.isoformat(),
            "status": "signed",
            "message": "Statutory consent recorded successfully.",
        }


