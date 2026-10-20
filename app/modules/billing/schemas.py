from pydantic import BaseModel, model_validator
from typing import Optional, List, Any
from uuid import UUID
from datetime import datetime
from decimal import Decimal

class InvoiceItem(BaseModel):
    description: str
    quantity: int = 1
    unit_price: Decimal
    total: Optional[Decimal] = None
    service_code: Optional[str] = None
    category: Optional[str] = None
    patient_package_id: Optional[UUID] = None
    package_item_id: Optional[str] = None
    tax_rate: Optional[Decimal] = Decimal("0")
    notes: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_item(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "total" not in data or data["total"] is None:
                if "total_price" in data and data["total_price"] is not None:
                    data["total"] = data["total_price"]
                elif "unit_price" in data and "quantity" in data:
                    try:
                        data["total"] = Decimal(str(data["unit_price"])) * int(data.get("quantity", 1))
                    except Exception:
                        data["total"] = Decimal("0")
        return data

class SplitPaymentItem(BaseModel):
    payment_method: str = "cash"  # 'cash', 'upi', 'card', 'wallet', 'bank_transfer', 'cheque'
    upi_pay_mode: Optional[str] = None  # 'GPay', 'PhonePe', 'Paytm', etc.
    amount: Decimal
    reference: Optional[str] = None
    notes: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_split(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "payment_method" not in data and "method" in data:
                data["payment_method"] = data["method"]
        return data

class InvoiceCreate(BaseModel):
    patient_id: UUID
    appointment_source: Optional[str] = "OP"
    source_module: Optional[str] = None
    source_reference_id: Optional[UUID] = None
    reason_for_attendance: Optional[str] = None
    selected_embryologist_id: Optional[UUID] = None
    items: list[InvoiceItem]
    discount: Decimal = Decimal("0")
    discount_value: Optional[Decimal] = None
    discount_type: Optional[str] = None
    discount_reason: Optional[str] = None
    tax: Decimal = Decimal("0")
    paid_amount: Optional[Decimal] = None
    wallet_amount_used: Optional[Decimal] = None
    wallet_deduction: Optional[Decimal] = None
    payment_method: Optional[str] = "cash"
    payment_mode: Optional[str] = None
    payment_status: Optional[str] = None
    upi_pay_mode: Optional[str] = None
    split_payments: Optional[list[SplitPaymentItem]] = None
    notes: Optional[str] = None
    created_by: Optional[UUID] = None
    branch_id: Optional[UUID] = None
    package_id: Optional[UUID] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_invoice_create(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Source normalization
            if "source" in data and not data.get("source_module"):
                data["source_module"] = str(data["source"]).lower()
            if "source_module" in data and not data.get("appointment_source"):
                data["appointment_source"] = str(data["source_module"]).upper()
            elif "appointment_source" in data and not data.get("source_module"):
                data["source_module"] = str(data["appointment_source"]).lower()
            
            # Payment mode alias
            if not data.get("payment_method") and data.get("payment_mode"):
                data["payment_method"] = data["payment_mode"]
        return data

class InvoiceResponse(BaseModel):
    id: UUID
    invoice_number: str
    patient_id: UUID
    patient_name: Optional[str] = None
    patient_vid: Optional[str] = None
    patient_mrn: Optional[str] = None
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None
    patient_address: Optional[str] = None
    patient_phone: Optional[str] = None
    appointment_source: Optional[str] = "OP"
    source_module: Optional[str] = "opd"
    source_reference_id: Optional[UUID] = None
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
    payment_transactions: Optional[list[dict]] = None
    tenant_id: UUID
    branch_id: Optional[UUID] = None
    created_at: datetime

    class Config:
        from_attributes = True

class PaymentRequest(BaseModel):
    amount: Decimal
    payment_method: str = "cash"
    upi_pay_mode: Optional[str] = None
    split_payments: Optional[list[SplitPaymentItem]] = None
    notes: Optional[str] = None
    discount: Optional[Decimal] = Decimal("0")

class InvoiceCancelRequest(BaseModel):
    reason: str
    cancelled_by: Optional[UUID] = None

class InvoiceRefundRequest(BaseModel):
    amount: Decimal
    reason: str
    refund_to_wallet: bool = True
    payment_method: Optional[str] = "wallet"
    notes: Optional[str] = None

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
