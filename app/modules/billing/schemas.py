from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from decimal import Decimal

class InvoiceItem(BaseModel):
    description: str
    quantity: int = 1
    unit_price: Decimal
    total: Decimal
    service_code: Optional[str] = None
    patient_package_id: Optional[UUID] = None
    package_item_id: Optional[str] = None

class InvoiceCreate(BaseModel):
    patient_id: UUID
    appointment_source: Optional[str] = "OP"
    reason_for_attendance: Optional[str] = None
    selected_embryologist_id: Optional[UUID] = None
    items: list[InvoiceItem]
    discount: Decimal = Decimal("0")
    discount_value: Optional[Decimal] = None
    discount_type: Optional[str] = None
    tax: Decimal = Decimal("0")
    paid_amount: Decimal = Decimal("0")
    wallet_amount_used: Decimal = Decimal("0")
    wallet_deduction: Optional[Decimal] = None
    payment_method: Optional[str] = "cash"
    upi_pay_mode: Optional[str] = None
    notes: Optional[str] = None
    created_by: Optional[UUID] = None
    branch_id: Optional[UUID] = None
    package_id: Optional[UUID] = None

class InvoiceResponse(BaseModel):
    id: UUID
    invoice_number: str
    patient_id: UUID
    patient_name: Optional[str] = None
    patient_vid: Optional[str] = None
    appointment_source: Optional[str] = "OP"
    reason_for_attendance: Optional[str] = None
    items: list[dict]
    subtotal: Decimal
    discount: Decimal
    tax: Decimal
    total_amount: Decimal
    paid_amount: Decimal
    wallet_amount_used: Decimal = Decimal("0")
    pending_due: Decimal = Decimal("0")
    status: str
    payment_method: Optional[str] = None
    upi_pay_mode: Optional[str] = None
    notes: Optional[str] = None
    tenant_id: UUID
    branch_id: Optional[UUID] = None
    created_at: datetime

    class Config:
        from_attributes = True

class PaymentRequest(BaseModel):
    amount: Decimal
    payment_method: str = "cash"
    upi_pay_mode: Optional[str] = None
    notes: Optional[str] = None
    discount: Optional[Decimal] = Decimal("0")

class TreatmentPackageSchema(BaseModel):
    id: Optional[UUID] = None
    name: str
    description: Optional[str] = None
    plugin_id: Optional[str] = None
    items: list[dict] = []
    base_price: Decimal
    is_active: bool = True

    class Config:
        from_attributes = True

class TreatmentPackageUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    plugin_id: Optional[str] = None
    items: Optional[list[dict]] = None
    base_price: Optional[Decimal] = None
    is_active: Optional[bool] = None

class ServiceItemSchema(BaseModel):
    id: Optional[UUID] = None
    code: str
    name: str
    category: str = "OP"
    base_price: Decimal
    hsn_sac: Optional[str] = None
    gst_rate: Decimal = Decimal("0.00")
    is_active: bool = True
    branch_id: Optional[UUID] = None

    class Config:
        from_attributes = True

class ServiceItemCreate(BaseModel):
    code: str
    name: str
    category: str = "OP"
    base_price: Decimal
    hsn_sac: Optional[str] = None
    gst_rate: Decimal = Decimal("0.00")
    branch_id: Optional[UUID] = None

class ServiceItemUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    category: Optional[str] = None
    base_price: Optional[Decimal] = None
    hsn_sac: Optional[str] = None
    gst_rate: Optional[Decimal] = None
    is_active: Optional[bool] = None
    branch_id: Optional[UUID] = None


class PatientPackageAssignRequest(BaseModel):
    patient_id: UUID
    package_id: UUID
    invoice_id: Optional[UUID] = None
    custom_items: Optional[list[dict]] = None


class PatientPackageConsumeRequest(BaseModel):
    item_id: str
    quantity: int = 1
    doctor_id: Optional[UUID] = None
    notes: Optional[str] = None


class PatientPackageResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    patient_id: UUID
    patient_name: Optional[str] = None
    package_id: Optional[UUID] = None
    invoice_id: Optional[UUID] = None
    package_name: str
    total_price: Decimal
    status: str
    items: list[dict] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
