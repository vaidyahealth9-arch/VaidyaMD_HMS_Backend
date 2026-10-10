from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload
from uuid import UUID
from datetime import datetime, timedelta, date, timezone
import zoneinfo

from app.config import settings
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
        
        # Ensure scheduled_at is serialized with UTC timezone awareness so client formats in local time accurately
        sched_val = apt.scheduled_at
        if sched_val and not sched_val.tzinfo:
            sched_val = sched_val.replace(tzinfo=timezone.utc)

        inv_id = str(apt.invoice_id) if apt.invoice_id else None
        inv_num = None
        inv_status = None
        inv_total = None
        inv_paid = None
        inv_due = None

        if getattr(apt, "invoice", None):
            inv = apt.invoice
            inv_id = str(inv.id)
            inv_num = inv.invoice_number
            inv_status = inv.status.value if hasattr(inv.status, "value") else str(inv.status)
            inv_total = float(inv.total_amount)
            inv_paid = float(inv.paid_amount)
            inv_due = max(0.0, float(inv.total_amount - inv.paid_amount))
        elif apt.metadata_ and apt.metadata_.get("invoice_id"):
            inv_id = str(apt.metadata_.get("invoice_id"))
            inv_num = apt.metadata_.get("invoice_number")
            if apt.metadata_.get("invoice_status"):
                inv_status = str(apt.metadata_.get("invoice_status"))

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
            scheduled_at=sched_val,
            status=apt.status.value if hasattr(apt.status, "value") else str(apt.status),
            visit_type=apt.visit_type,
            notes=apt.notes,
            invoice_id=inv_id,
            invoice_number=inv_num,
            invoice_status=inv_status,
            invoice_total=inv_total,
            invoice_paid=inv_paid,
            invoice_pending_due=inv_due,
            metadata_=apt.metadata_,
            tenant_id=apt.tenant_id,
            branch_id=apt.branch_id,
            created_at=apt.created_at,
        )

    async def create_appointment(self, data: AppointmentCreate, tenant_id: UUID) -> AppointmentResponse:
        patient = await self.db.get(Patient, data.patient_id)
        if not patient:
            raise ValueError("Patient not found")

        doctor = await self.db.get(User, data.doctor_id)
        if not doctor:
            raise ValueError("Doctor not found")

        # Standardize scheduled_at to UTC naive datetime for storage
        if data.scheduled_at:
            if data.scheduled_at.tzinfo:
                sched_clean = data.scheduled_at.astimezone(timezone.utc).replace(tzinfo=None)
            else:
                sched_clean = data.scheduled_at
        else:
            sched_clean = datetime.utcnow()

        if sched_clean < datetime.utcnow() - timedelta(minutes=5):
            raise InvalidAppointmentDateError("Appointment cannot be scheduled in the past.")

        dept = data.department
        if not dept:
            if doctor.departments and len(doctor.departments) > 0:
                dept = doctor.departments[0]
            else:
                dept = "General"

        try:
            tz = zoneinfo.ZoneInfo(getattr(settings, "TIMEZONE", "Asia/Kolkata"))
        except Exception:
            tz = zoneinfo.ZoneInfo("UTC")

        today_start_local = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
        today_start = today_start_local.astimezone(zoneinfo.ZoneInfo("UTC")).replace(tzinfo=None)

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

        branch_id = getattr(data, 'branch_id', None) or getattr(patient, 'branch_id', None)

        appointment = Appointment(
            patient_id=data.patient_id,
            doctor_id=data.doctor_id,
            department=dept,
            scheduled_at=sched_clean,
            visit_type=data.visit_type,
            notes=data.notes,
            metadata_=meta,
            tenant_id=tenant_id,
            branch_id=branch_id,
        )
        if data.status:
            appointment.status = data.status
            
        self.db.add(appointment)

        # Auto-create consultation invoice through BillingService SSOT if fee is charged
        if data.consultation_fee and float(data.consultation_fee) > 0:
            from app.modules.billing.service import BillingService
            from app.modules.billing.schemas import InvoiceCreate, InvoiceItem
            from decimal import Decimal

            fee = Decimal(str(data.consultation_fee))
            paid = Decimal(str(data.paid_amount or 0))
            disc = Decimal(str(data.discount or 0))

            raw_vt = (data.visit_type or "consultation").lower()
            if "tvs" in raw_vt or "scan" in raw_vt:
                visit_label = "TVS Follicular Scan"
            elif "opu" in raw_vt:
                visit_label = "OPU (Egg Retrieval)"
            elif "et" in raw_vt or "embryo" in raw_vt:
                visit_label = "Embryo Transfer"
            elif "semen" in raw_vt:
                visit_label = "Semen Analysis"
            elif "iui" in raw_vt:
                visit_label = "IUI Insemination"
            else:
                visit_label = raw_vt.replace("visit_", "").replace("_", " ").title()

            billing_service = BillingService(self.db)
            pay_method = data.payment_method or ("cash" if paid > Decimal("0") else "pending")
            invoice_create = InvoiceCreate(
                patient_id=data.patient_id,
                appointment_source="OP",
                source_module="opd",
                source_reference_id=appointment.id,
                reason_for_attendance=f"OPD: {visit_label} - {doctor.name}",
                items=[
                    InvoiceItem(
                        description=f"{visit_label} - {doctor.name}",
                        quantity=1,
                        unit_price=fee,
                        total=fee,
                        service_code="CONS-OPD"
                    )
                ],
                discount=disc,
                paid_amount=paid,
                payment_method=pay_method,
                upi_pay_mode=data.upi_pay_mode,
                created_by=data.doctor_id,
                branch_id=branch_id,
                notes=f"Generated upon appointment booking for {patient.name}"
            )
            created_inv = await billing_service.create_invoice(invoice_create, tenant_id=tenant_id)
            appointment.invoice_id = created_inv.id
            meta["invoice_id"] = str(created_inv.id)
            meta["invoice_number"] = created_inv.invoice_number
            meta["invoice_status"] = created_inv.status
            appointment.metadata_ = meta

        await self.db.flush()
        await self.db.refresh(appointment)
        return self._build_response(appointment, patient, doctor)

    async def get_appointment(self, appointment_id: UUID) -> AppointmentResponse:
        query = (
            select(Appointment)
            .options(selectinload(Appointment.patient), selectinload(Appointment.doctor), selectinload(Appointment.invoice))
            .where(Appointment.id == appointment_id)
        )
        result = await self.db.execute(query)
        apt = result.scalar_one_or_none()
        if not apt:
            raise AppointmentNotFoundError("Appointment not found")
        return self._build_response(apt, apt.patient, apt.doctor)

    async def list_appointments(self, filters: dict, tenant_id: UUID = None):
        query = select(Appointment).options(selectinload(Appointment.patient), selectinload(Appointment.doctor), selectinload(Appointment.invoice))
        
        if tenant_id:
            query = query.where(Appointment.tenant_id == tenant_id)
            
        if filters.get("patient_id"):
            query = query.where(Appointment.patient_id == filters["patient_id"])
        if filters.get("date_filter"):
            target_date = filters["date_filter"]
            try:
                tz = zoneinfo.ZoneInfo(getattr(settings, "TIMEZONE", "Asia/Kolkata"))
            except Exception:
                tz = zoneinfo.ZoneInfo("UTC")

            start_local = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=tz)
            end_local = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59, 999999, tzinfo=tz)
            start_utc = start_local.astimezone(zoneinfo.ZoneInfo("UTC")).replace(tzinfo=None)
            end_utc = end_local.astimezone(zoneinfo.ZoneInfo("UTC")).replace(tzinfo=None)

            query = query.where(Appointment.scheduled_at >= start_utc, Appointment.scheduled_at <= end_utc)
        if filters.get("status"):
            query = query.where(Appointment.status == filters["status"])
        if filters.get("department"):
            query = query.where(Appointment.department == filters["department"])
        
        if filters.get("branch_id") or filters.get("gender"):
            query = query.join(Patient, Appointment.patient_id == Patient.id)
            if filters.get("branch_id"):
                b_id = filters["branch_id"]
                query = query.where(
                    or_(
                        Appointment.branch_id == b_id,
                        and_(Appointment.branch_id.is_(None), Patient.branch_id == b_id),
                    )
                )
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

        if data.status and data.status != old_status:
            from app.core.events import event_bus, AppointmentStatusChangedEvent
            event_bus.publish_background(
                AppointmentStatusChangedEvent(
                    appointment_id=str(appointment.id),
                    patient_id=str(appointment.patient_id),
                    doctor_id=str(appointment.doctor_id) if appointment.doctor_id else None,
                    department=appointment.department,
                    old_status=str(old_status) if old_status else None,
                    new_status=str(data.status),
                    tenant_id=str(appointment.tenant_id) if appointment.tenant_id else None,
                )
            )

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
