from pydantic import BaseModel
from typing import Optional, Any, List
from uuid import UUID
from datetime import date

class IndentCreate(BaseModel):
    requesting_department: str = "OPD"
    requested_by_id: Optional[UUID] = None
    urgency: str = "Routine"
    items: List[dict[str, Any]]
    notes: Optional[str] = None
    branch_id: Optional[UUID] = None
    target_branch_id: Optional[UUID] = None
    indent_type: Optional[str] = "INTERNAL"

class IndentStatusUpdate(BaseModel):
    status: str

class PurchaseOrderCreate(BaseModel):
    vendor_name: str
    vendor_gst: Optional[str] = None
    vendor_contact: Optional[str] = None
    total_amount: float
    expected_delivery_date: Optional[date] = None
    items: List[dict[str, Any]]
    notes: Optional[str] = None
    branch_id: Optional[UUID] = None

class GRNCreate(BaseModel):
    invoice_number: str
    vendor_name: str
    total_amount: float
    po_id: Optional[UUID] = None
    invoice_date: Optional[date] = None
    items: List[dict[str, Any]]
    ocr_raw_data: Optional[dict[str, Any]] = None
    verified_by_id: Optional[UUID] = None
    branch_id: Optional[UUID] = None

class DispenseItem(BaseModel):
    item_code: str
    quantity: int

class DispenseRequest(BaseModel):
    patient_id: UUID
    items: List[DispenseItem]
    doctor_id: Optional[Any] = None
    notes: Optional[str] = None
    branch_id: Optional[UUID] = None
    payment_method: Optional[str] = "Cash"
    payment_ref: Optional[str] = None
    discount: Optional[float] = 0.0
    amount_paid: Optional[float] = None
