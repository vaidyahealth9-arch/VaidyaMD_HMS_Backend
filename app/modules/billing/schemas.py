from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime
from decimal import Decimal

class InvoiceItem(BaseModel):
    description: str
    quantity: int = 1
    unit_price: Decimal
    total: Decimal

class InvoiceCreate(BaseModel):
    patient_id: UUID
    appointment_source: Optional[str] = "OP"
    reason_for_attendance: Optional[str] = None
    selected_embryologist_id: Optional[UUID] = None
    items: list[InvoiceItem]
    discount: Decimal = Decimal("0")
    tax: Decimal = Decimal("0")
    paid_amount: Decimal = Decimal("0")
    wallet_amount_used: Decimal = Decimal("0")
    payment_method: Optional[str] = "cash"
    upi_pay_mode: Optional[str] = None
    notes: Optional[str] = None
    created_by: Optional[UUID] = None

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
    created_at: datetime

    class Config:
        from_attributes = True

class PaymentRequest(BaseModel):
    amount: Decimal
    payment_method: str = "cash"
    upi_pay_mode: Optional[str] = None
    notes: Optional[str] = None

class TreatmentPackageSchema(BaseModel):
    id: Optional[UUID] = None
    name: str
    description: Optional[str] = None
    plugin_id: Optional[str] = None
    items: list[dict]
    base_price: Decimal
    is_active: bool = True

    class Config:
        from_attributes = True
