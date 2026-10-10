from pydantic import BaseModel, field_serializer
from typing import Optional
from uuid import UUID
from datetime import datetime

class AppointmentCreate(BaseModel):
    patient_id: UUID
    doctor_id: UUID
    department: Optional[str] = None
    scheduled_at: datetime
    visit_type: str = "consultation"
    status: Optional[str] = None
    notes: Optional[str] = None
    consultation_fee: Optional[float] = None
    paid_amount: Optional[float] = None
    payment_method: Optional[str] = None
    upi_pay_mode: Optional[str] = None
    discount: Optional[float] = None
    metadata: Optional[dict] = None
    branch_id: Optional[UUID] = None

class AppointmentUpdate(BaseModel):
    status: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    notes: Optional[str] = None

class TriageUpdate(BaseModel):
    vitals: dict
    chief_complaint: Optional[str] = None
    nurse_notes: Optional[str] = None

class AppointmentResponse(BaseModel):
    id: UUID
    patient_id: UUID
    patient_name: Optional[str] = None
    patient_vid: Optional[str] = None
    patient_gender: Optional[str] = None
    patient_phone: Optional[str] = None
    doctor_id: UUID
    doctor_name: Optional[str] = None
    department: str
    scheduled_at: datetime
    status: str
    visit_type: str
    notes: Optional[str] = None
    invoice_id: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_status: Optional[str] = None
    invoice_total: Optional[float] = None
    invoice_paid: Optional[float] = None
    invoice_pending_due: Optional[float] = None
    metadata_: dict = {}
    tenant_id: UUID
    branch_id: Optional[UUID] = None
    created_at: datetime

    @field_serializer("scheduled_at", "created_at", when_used="json")
    def serialize_datetime(self, v: datetime) -> str:
        if v.tzinfo is None:
            return v.isoformat() + "Z"
        return v.isoformat()

    class Config:
        from_attributes = True

class AppointmentListResponse(BaseModel):
    appointments: list[AppointmentResponse]
    total: int
