"""
VaidyaMD HMS — Referral Module Pydantic Schemas
"""

import uuid
from datetime import datetime, date
from typing import List, Optional, Any
from pydantic import BaseModel, ConfigDict


class DepartmentBreakdown(BaseModel):
    opd: float = 0.0
    pharmacy: float = 0.0
    iui: float = 0.0
    embryology: float = 0.0
    lims: float = 0.0
    ipd: float = 0.0
    other: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class ReferringDoctorBase(BaseModel):
    name: str
    clinic_name: Optional[str] = None
    specialty: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    ifsc_code: Optional[str] = None
    upi_id: Optional[str] = None
    pan_number: Optional[str] = None
    custom_commission_pct: Optional[float] = None
    notes: Optional[str] = None
    is_active: bool = True


class ReferringDoctorCreate(ReferringDoctorBase):
    pass


class ReferringDoctorResponse(ReferringDoctorBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReferralSettlementCreate(BaseModel):
    doctor_name: str
    amount_paid: float
    payment_method: str = "neft"  # neft, upi, cheque, cash
    reference_number: Optional[str] = None
    settlement_date: Optional[date] = None
    notes: Optional[str] = None
    invoice_ids: List[str] = []


class ReferralSettlementResponse(BaseModel):
    id: uuid.UUID
    settlement_number: str
    tenant_id: uuid.UUID
    doctor_name: str
    doctor_id: Optional[uuid.UUID] = None
    amount_paid: float
    payment_method: str
    reference_number: Optional[str] = None
    settlement_date: date
    notes: Optional[str] = None
    invoice_ids: List[str]
    created_by: Optional[uuid.UUID] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReferralInvoiceReportItem(BaseModel):
    patient_id: uuid.UUID
    patient_name: str
    patient_vid: Optional[str] = None
    patient_mrn: Optional[str] = None
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None
    patient_phone: Optional[str] = None
    referring_doctor: str
    marketing_person: Optional[str] = None
    treatment_protocol: str
    cycle_status: Optional[str] = None

    invoice_id: uuid.UUID
    invoice_number: str
    invoice_date: datetime
    invoice_status: str
    payment_method: Optional[str] = None

    subsections: DepartmentBreakdown
    subtotal: float
    discount: float
    round_off: float
    net_total: float
    paid_amount: float
    pending_due: float
    commission_amount: float

    # Settlement tracking
    is_settled: bool = False
    settlement_number: Optional[str] = None
    settlement_date: Optional[date] = None

    model_config = ConfigDict(from_attributes=True)


class PatientReferralCardItem(BaseModel):
    patient_id: uuid.UUID
    patient_name: str
    patient_vid: Optional[str] = None
    patient_mrn: Optional[str] = None
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None
    patient_phone: Optional[str] = None
    treatment_protocol: str
    cycle_status: Optional[str] = None
    conversion_badge: str  # "Converted to IVF", "Converted to IUI", "Procedural Care", "OPD Only"
    
    total_billed: float
    total_paid: float
    total_due: float
    total_commission: float
    settled_commission: float
    pending_commission: float
    invoices: List[ReferralInvoiceReportItem]


class DoctorDirectoryItem(BaseModel):
    doctor_name: str
    doctor_profile: Optional[ReferringDoctorResponse] = None
    patient_count: int
    invoice_count: int
    total_revenue: float
    total_paid: float
    total_due: float
    total_commission: float
    settled_commission: float
    pending_commission: float
    has_unsettled: bool
    converted_count: int = 0
    conversion_rate_pct: float = 0.0


class DoctorHierarchyDetailResponse(BaseModel):
    doctor_name: str
    doctor_profile: Optional[ReferringDoctorResponse] = None
    total_patients_count: int
    total_invoices_count: int
    total_revenue: float
    total_paid: float
    total_due: float
    total_commission: float
    settled_commission: float
    pending_commission: float
    departmental_totals: DepartmentBreakdown
    patients: List[PatientReferralCardItem]
    settlements: List[ReferralSettlementResponse]


class DoctorSummaryItem(BaseModel):
    doctor_name: str
    patient_count: int
    invoice_count: int
    total_revenue: float
    total_paid: float
    total_due: float
    total_commission: float


class ReferralSummaryResponse(BaseModel):
    total_referred_patients: int
    total_invoices_count: int
    total_revenue: float
    total_paid: float
    total_due: float
    total_commission: float
    departmental_totals: DepartmentBreakdown
    top_doctors: List[DoctorSummaryItem]


class HospitalReferralOverviewResponse(BaseModel):
    total_referral_revenue: float
    total_paid: float
    total_due: float
    total_commission: float
    settled_commission: float
    pending_commission: float
    total_patients_count: int
    total_invoices_count: int
    converted_cycles_count: int
    conversion_rate_pct: float
    active_referring_doctors_count: int
    departmental_totals: DepartmentBreakdown
    doctors_league: List[DoctorDirectoryItem]
    recent_settlements: List[ReferralSettlementResponse]


class CommissionConfigSchema(BaseModel):
    opd_pct: float = 10.0
    pharmacy_pct: float = 5.0
    iui_pct: float = 10.0
    embryology_pct: float = 15.0
    lims_pct: float = 10.0
    ipd_pct: float = 10.0
    other_pct: float = 5.0

    model_config = ConfigDict(from_attributes=True)
