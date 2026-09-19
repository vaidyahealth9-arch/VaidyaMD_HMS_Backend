from pydantic import BaseModel
from typing import Optional, Any
from uuid import UUID
from datetime import datetime

class WardCreate(BaseModel):
    name: str
    code: str
    department: str = "General IPD"
    base_charge_per_day: float = 2000.0
    total_beds: int = 10
    branch_id: Optional[UUID] = None

class WardUpdate(BaseModel):
    name: Optional[str] = None
    department: Optional[str] = None
    base_charge_per_day: Optional[float] = None
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
    diagnosis: Optional[str] = None
    package_name: Optional[str] = None
    notes: Optional[str] = None

class DischargeRequest(BaseModel):
    notes: Optional[str] = None

class TransferBedRequest(BaseModel):
    target_bed_id: UUID

class NursingTaskCreate(BaseModel):
    admission_id: UUID
    bed_id: UUID
    task_type: str = "Vitals"
    description: str
    frequency: str = "Q4H"
    scheduled_time: Optional[datetime] = None

class NursingTaskComplete(BaseModel):
    completed_by_id: UUID
    vitals_payload: Optional[dict[str, Any]] = None
    notes: Optional[str] = None
