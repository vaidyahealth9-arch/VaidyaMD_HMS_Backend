from pydantic import BaseModel
from typing import Optional
from uuid import UUID

class DepositRequest(BaseModel):
    patient_id: UUID
    amount: float
    payment_mode: str = "cash"
    notes: Optional[str] = None
    created_by: Optional[UUID] = None

class DeductRequest(BaseModel):
    patient_id: UUID
    amount: float
    reference_invoice_id: Optional[UUID] = None
    discount: Optional[float] = 0.0
    notes: Optional[str] = None
    created_by: Optional[UUID] = None

class TopUpPayload(BaseModel):
    amount: float
    payment_method: str = "cash"
    notes: Optional[str] = None

class PayInvoicePayload(BaseModel):
    invoice_id: UUID
    amount: float
    discount: Optional[float] = 0.0
