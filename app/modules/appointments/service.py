from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from uuid import UUID
from datetime import datetime, timedelta, date

from app.core.models import Hospital, User, Notification, NotificationType
from app.modules.patients.model import Patient
from app.modules.appointments.model import Appointment, AppointmentStatus
from app.modules.appointments.schemas import AppointmentCreate, AppointmentUpdate, AppointmentResponse, TriageUpdate
from app.modules.appointments.exceptions import AppointmentNotFoundError, InvalidAppointmentDateError, ActiveAppointmentExistsError
from app.core.websocket import ws_manager

class AppointmentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _build_response(self, apt: Appointment, patient: Patient, doctor: User) -> AppointmentResponse:
        p_gender = patient.gender.value if (patient and hasattr(patient.gender, "value")) else (patient.gender if patient else None)
        return AppointmentResponse(
            id=apt.id,
            patient_id=apt.patient_id,
            patient_name=patient.name if patient else None,
            patient_vid=patient.vid if patient else None,
            patient_gender=p_gender,
            patient_phone=patient.phone if patient else None,
            doctor_id=apt.doctor_id,
            doctor_name=doctor.name if doctor else None,
            department=apt.department,
            scheduled_at=apt.scheduled_at,
            status=apt.status.value if hasattr(apt.status, "value") else str(apt.status),
            visit_type=apt.visit_type,
            notes=apt.notes,
            metadata_=apt.metadata_,
            tenant_id=apt.tenant_id,
            created_at=apt.created_at,
        )

    async def create_appointment(self, data: AppointmentCreate, tenant_id: UUID) -> AppointmentResponse:
        patient = await self.db.get(Patient, data.patient_id)
        if not patient:
            raise ValueError("Patient not found")

        doctor = await self.db.get(User, data.doctor_id)
        if not doctor:
            raise ValueError("Doctor not found")

        sched_clean = data.scheduled_at.replace(tzinfo=None) if data.scheduled_at.tzinfo else data.scheduled_at
        if sched_clean < datetime.utcnow() - timedelta(minutes=5):
            raise InvalidAppointmentDateError("Appointment cannot be scheduled in the past.")

        dept = data.department
        if not dept:
            if doctor.departments and len(doctor.departments) > 0:
                dept = doctor.departments[0]
            elif doctor.specialization:
                dept = doctor.specialization
            else:
                dept = "Fertility / IVF"

        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        existing_q = await self.db.execute(
            select(Appointment).where(
                and_(
                    Appointment.patient_id == data.patient_id,
                    Appointment.scheduled_at >= today_start,
                    Appointment.status.in_(["waiting", "in_progress"])
                )
            ).limit(1)
        )
        if existing_q.scalar_one_or_none():
            raise ActiveAppointmentExistsError("Patient already has an active appointment in the queue today.")

        meta = {}
        if data.consultation_fee is not None:
            meta["consultation_fee"] = float(data.consultation_fee)
        if data.metadata:
            meta.update(data.metadata)

        appointment = Appointment(
            patient_id=data.patient_id,
            doctor_id=data.doctor_id,
            department=dept,
            scheduled_at=sched_clean,
            visit_type=data.visit_type,
            notes=data.notes,
            metadata_=meta,
            tenant_id=tenant_id,
        )
        if data.status:
            appointment.status = data.status
            
        self.db.add(appointment)

        # Auto-create pending consultation invoice if fee is charged
        if data.consultation_fee and float(data.consultation_fee) > 0:
            from app.modules.billing.model import Invoice, InvoiceStatus
            import uuid
            fee = float(data.consultation_fee)
            inv_num = f"INV-OPD-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
            invoice = Invoice(
                invoice_number=inv_num,
                patient_id=data.patient_id,
                appointment_source="OP",
                reason_for_attendance=f"OPD Consultation - {doctor.name}",
                items=[{
                    "item_code": "CONS-OPD",
                    "item_name": f"Consultation Fee - {doctor.name}",
                    "quantity": 1,
                    "unit_price": fee,
                    "total_price": fee
                }],
                subtotal=fee,
                total_amount=fee,
                status=InvoiceStatus.PENDING,
                tenant_id=tenant_id,
                branch_id=getattr(patient, 'branch_id', None),
                created_by=data.doctor_id,
                notes=f"Generated upon OPD Queue check-in for {patient.name}"
            )
            self.db.add(invoice)

        await self.db.flush()
        await self.db.refresh(appointment)
        return self._build_response(appointment, patient, doctor)

    async def get_appointment(self, appointment_id: UUID) -> AppointmentResponse:
        query = (
            select(Appointment)
            .options(selectinload(Appointment.patient), selectinload(Appointment.doctor))
            .where(Appointment.id == appointment_id)
        )
        result = await self.db.execute(query)
        apt = result.scalar_one_or_none()
        if not apt:
            raise AppointmentNotFoundError("Appointment not found")
        return self._build_response(apt, apt.patient, apt.doctor)

    async def list_appointments(self, filters: dict, tenant_id: UUID = None):
        query = select(Appointment).options(selectinload(Appointment.patient), selectinload(Appointment.doctor))
        
        if tenant_id:
            query = query.where(Appointment.tenant_id == tenant_id)
            
        if filters.get("patient_id"):
            query = query.where(Appointment.patient_id == filters["patient_id"])
        if filters.get("date_filter"):
            query = query.where(func.date(Appointment.scheduled_at) == filters["date_filter"])
        if filters.get("status"):
            query = query.where(Appointment.status == filters["status"])
        if filters.get("department"):
            query = query.where(Appointment.department == filters["department"])
        
        if filters.get("branch_id") or filters.get("gender"):
            query = query.join(Patient, Appointment.patient_id == Patient.id)
            if filters.get("branch_id"):
                query = query.where(Patient.branch_id == filters["branch_id"])
            if filters.get("gender"):
                query = query.where(Patient.gender == filters["gender"])

        query = query.order_by(Appointment.scheduled_at.asc())
        result = await self.db.execute(query)
        appointments = result.scalars().all()
        
        responses = [self._build_response(apt, apt.patient, apt.doctor) for apt in appointments]
        return {"appointments": responses, "total": len(responses)}

    async def update_triage(self, appointment_id: UUID, data: TriageUpdate, user_id: UUID):
        appointment = await self.db.get(Appointment, appointment_id)
        if not appointment:
            raise AppointmentNotFoundError("Appointment not found")

        meta = dict(appointment.metadata_ or {})
        meta["triage"] = {
            "vitals": data.vitals,
            "chief_complaint": data.chief_complaint,
            "nurse_notes": data.nurse_notes,
            "triaged_by": str(user_id),
            "triaged_at": datetime.utcnow().isoformat(),
        }
        appointment.metadata_ = meta
        await self.db.flush()
        return {"message": "Triage saved", "metadata": meta}

    async def update_appointment(self, appointment_id: UUID, data: AppointmentUpdate):
        appointment = await self.db.get(Appointment, appointment_id)
        if not appointment:
            raise AppointmentNotFoundError("Appointment not found")

        old_status = appointment.status

        if data.status:
            appointment.status = data.status
        if data.scheduled_at:
            sched_clean = data.scheduled_at.replace(tzinfo=None) if data.scheduled_at.tzinfo else data.scheduled_at
            if sched_clean < datetime.utcnow() - timedelta(minutes=5):
                raise InvalidAppointmentDateError("Rescheduled appointment cannot be set to a past date and time.")
            appointment.scheduled_at = sched_clean
        if data.notes:
            appointment.notes = data.notes

        await self.db.flush()
        await self.db.refresh(appointment)

        if data.status and data.status == AppointmentStatus.WAITING.value and old_status != AppointmentStatus.WAITING:
            patient = await self.db.get(Patient, appointment.patient_id)
            notification = Notification(
                recipient_id=appointment.doctor_id,
                type=NotificationType.PATIENT_STATUS,
                title="Patient Waiting",
                message=f"{patient.name} ({patient.vid}) is now waiting for consultation.",
                metadata_={"patient_id": str(appointment.patient_id), "appointment_id": str(appointment.id)},
            )
            self.db.add(notification)
            await ws_manager.send_to_user(
                str(appointment.doctor_id),
                {
                    "type": "patient_status",
                    "title": "Patient Waiting",
                    "message": f"{patient.name} ({patient.vid}) is now waiting.",
                    "patient_id": str(appointment.patient_id),
                },
            )

        patient = await self.db.get(Patient, appointment.patient_id)
        doctor = await self.db.get(User, appointment.doctor_id)
        return self._build_response(appointment, patient, doctor)
