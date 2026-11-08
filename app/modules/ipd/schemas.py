from pydantic import BaseModel
from typing import Optional, Any, List, Dict
from uuid import UUID
from datetime import datetime

class WardCreate(BaseModel):
    name: str
    code: str
    department: str = "General IPD"
    base_charge_per_day: float = 2000.0
    nursing_charge_per_day: float = 500.0
    diet_charge_per_day: float = 300.0
    total_beds: int = 10
    branch_id: Optional[UUID] = None

class WardUpdate(BaseModel):
    name: Optional[str] = None
    department: Optional[str] = None
    base_charge_per_day: Optional[float] = None
    nursing_charge_per_day: Optional[float] = None
    diet_charge_per_day: Optional[float] = None
    is_active: Optional[bool] = None

class BedCreate(BaseModel):
    ward_id: UUID
    bed_number: str
    bed_type: str = "Standard"
    daily_rate: Optional[float] = None
    status: str = "Vacant"

class BedUpdate(BaseModel):
    bed_number: Optional[str] = None
    bed_type: Optional[str] = None
    daily_rate: Optional[float] = None
    status: Optional[str] = None

class BedStatusUpdate(BaseModel):
    status: str

class AdmissionCreate(BaseModel):
    patient_id: UUID
    bed_id: UUID
    admitting_doctor_id: Optional[UUID] = None
    attending_doctor_charge_per_day: Optional[float] = 500.0
    daily_diet_enabled: Optional[bool] = True
    credit_limit: Optional[float] = 20000.0
    diagnosis: Optional[str] = None
    package_name: Optional[str] = None
    notes: Optional[str] = None
    allergies: Optional[List[str]] = None
    risk_factors: Optional[Dict[str, Any]] = None
    advance_amount: Optional[float] = 0.0

class AdmissionUpdate(BaseModel):
    admitting_doctor_id: Optional[UUID] = None
    attending_doctor_charge_per_day: Optional[float] = None
    daily_diet_enabled: Optional[bool] = None
    credit_limit: Optional[float] = None
    diagnosis: Optional[str] = None
    package_name: Optional[str] = None
    notes: Optional[str] = None
    allergies: Optional[List[str]] = None
    risk_factors: Optional[Dict[str, Any]] = None
    advance_amount: Optional[float] = None

class DischargeSummarySave(BaseModel):
    discharge_type: Optional[str] = "Normal"  # Normal, LAMA, Referred, Deceased
    condition_at_discharge: Optional[str] = "Stable"
    hospital_course: Optional[str] = None
    discharge_diagnosis: Optional[str] = None
    investigations_summary: Optional[str] = None
    discharge_medications: Optional[List[Dict[str, Any]]] = None
    dietary_advice: Optional[str] = None
    follow_up_instructions: Optional[str] = None
    follow_up_date: Optional[str] = None

class DischargeRequest(BaseModel):
    notes: Optional[str] = None
    invoice_id: Optional[UUID] = None
    discharge_summary: Optional[Dict[str, Any]] = None

class TransferBedRequest(BaseModel):
    target_bed_id: UUID
    notes: Optional[str] = None

class NursingTaskCreate(BaseModel):
    admission_id: UUID
    bed_id: UUID
    task_type: str = "Vitals"
    description: str
    frequency: str = "Q4H"
    scheduled_time: Optional[datetime] = None

class NursingTaskComplete(BaseModel):
    completed_by_id: Optional[UUID] = None
    vitals_payload: Optional[dict[str, Any]] = None
    notes: Optional[str] = None

class RoundNoteCreate(BaseModel):
    doctor_id: Optional[UUID] = None
    subjective: Optional[str] = None
    objective: Optional[str] = None
    assessment: Optional[str] = None
    plan: Optional[str] = None
    notes: Optional[str] = None

class OrderCreate(BaseModel):
    order_type: str = "Medication"  # Medication, Investigation, Diet, Nursing Care
    item_name: str
    dosage: Optional[str] = None
    route: Optional[str] = None
    frequency: Optional[str] = "OD"
    duration: Optional[str] = None
    instructions: Optional[str] = None

class OrderStatusUpdate(BaseModel):
    status: str  # Active, Completed, Discontinued
    notes: Optional[str] = None

class OrderAdministerPayload(BaseModel):
    status: str = "Given"  # Given, Withheld, Refused, Omitted
    notes: Optional[str] = None
    administered_by_name: Optional[str] = None

class FluidBalanceCreate(BaseModel):
    shift: str = "Morning"
    record_date: Optional[datetime] = None
    intake_oral: float = 0.0
    intake_iv: float = 0.0
    intake_other: float = 0.0
    output_urine: float = 0.0
    output_drain: float = 0.0
    output_vomitus: float = 0.0
    output_other: float = 0.0
    notes: Optional[str] = None

# Rolling Bill Schemas
class BillItemCreate(BaseModel):
    item_type: str = "miscellaneous"  # room_rent, nursing_care, doctor_consultation, pharmacy_medication, pharmacy_surgical, lab_investigation, radiology, equipment, diet, procedure_ot, miscellaneous
    category: str = "General"
    service_code: Optional[str] = None
    item_name: str
    quantity: float = 1.0
    unit_price: float = 0.0
    notes: Optional[str] = None
    billing_date: Optional[datetime] = None
    source_module: Optional[str] = "ipd"
    source_reference_id: Optional[UUID] = None

class PaymentCreate(BaseModel):
    amount: float
    payment_method: str = "cash"  # cash, card, upi, neft, cheque
    transaction_reference: Optional[str] = None
    payment_type: str = "advance"  # advance, interim, refund
    notes: Optional[str] = None

class SettleBillItemsRequest(BaseModel):
    invoice_id: UUID
    item_ids: Optional[List[UUID]] = None
    amount_paid: float = 0.0
    payment_method: str = "cash"
    transaction_reference: Optional[str] = None
    notes: Optional[str] = None
    is_discharge: bool = False
    discharge_summary: Optional[Dict[str, Any]] = None

