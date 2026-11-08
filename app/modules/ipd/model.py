import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Float, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base

class Ward(Base):
    __tablename__ = "wards"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    code = Column(String(20), nullable=False, unique=True)
    department = Column(String(100), default="General IPD")
    base_charge_per_day = Column(Float, default=2000.0)
    nursing_charge_per_day = Column(Float, default=500.0)
    diet_charge_per_day = Column(Float, default=300.0)
    total_beds = Column(Integer, default=10)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    beds = relationship("Bed", back_populates="ward", cascade="all, delete-orphan")

class Bed(Base):
    __tablename__ = "beds"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    ward_id = Column(UUID(as_uuid=True), ForeignKey("wards.id"), nullable=False)
    bed_number = Column(String(50), nullable=False)
    bed_type = Column(String(50), default="Standard")
    status = Column(String(50), default="Vacant")
    daily_rate = Column(Float, default=2000.0)
    current_admission_id = Column(UUID(as_uuid=True), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    ward = relationship("Ward", back_populates="beds")
    admissions = relationship("IPDAdmission", back_populates="bed", foreign_keys="IPDAdmission.bed_id")
    nursing_tasks = relationship("NursingTask", back_populates="bed", cascade="all, delete-orphan")

class IPDAdmission(Base):
    __tablename__ = "ipd_admissions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    admission_number = Column(String(50), nullable=False, unique=True)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    bed_id = Column(UUID(as_uuid=True), ForeignKey("beds.id"), nullable=False)
    admission_date = Column(DateTime, default=datetime.utcnow)
    discharge_date = Column(DateTime, nullable=True)
    admitting_doctor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    diagnosis = Column(String(255), nullable=True)
    package_name = Column(String(150), nullable=True)
    status = Column(String(50), default="Active")
    total_accrued_amount = Column(Float, default=0.0)
    advance_amount = Column(Float, default=0.0)
    credit_limit = Column(Float, default=20000.0)
    attending_doctor_charge_per_day = Column(Float, default=500.0)
    daily_diet_enabled = Column(Boolean, default=False)
    last_accrual_date = Column(DateTime, nullable=True)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=True)
    discharge_summary = Column(JSONB, default=dict)
    allergies = Column(JSONB, default=list)
    risk_factors = Column(JSONB, default=dict)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    patient = relationship("Patient")
    bed = relationship("Bed", back_populates="admissions", foreign_keys=[bed_id])
    admitting_doctor = relationship("User", foreign_keys=[admitting_doctor_id])
    nursing_tasks = relationship("NursingTask", back_populates="admission", cascade="all, delete-orphan")
    round_notes = relationship("IPDRoundNote", back_populates="admission", cascade="all, delete-orphan")
    orders = relationship("IPDOrder", back_populates="admission", cascade="all, delete-orphan")
    fluid_balances = relationship("IPDFluidBalance", back_populates="admission", cascade="all, delete-orphan")
    bill_items = relationship("IPDBillItem", back_populates="admission", cascade="all, delete-orphan")
    payments = relationship("IPDPayment", back_populates="admission", cascade="all, delete-orphan")

class NursingTask(Base):
    __tablename__ = "nursing_tasks"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    admission_id = Column(UUID(as_uuid=True), ForeignKey("ipd_admissions.id"), nullable=False)
    bed_id = Column(UUID(as_uuid=True), ForeignKey("beds.id"), nullable=False)
    task_type = Column(String(50), default="Vitals")
    description = Column(String(255), nullable=False)
    scheduled_time = Column(DateTime, default=datetime.utcnow)
    frequency = Column(String(50), default="Q4H")
    status = Column(String(50), default="Pending")
    completed_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    completed_at = Column(DateTime, nullable=True)
    vitals_payload = Column(JSONB, default=dict)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    admission = relationship("IPDAdmission", back_populates="nursing_tasks")
    bed = relationship("Bed", back_populates="nursing_tasks")
    completed_by = relationship("User", foreign_keys=[completed_by_id])

class IPDRoundNote(Base):
    __tablename__ = "ipd_round_notes"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    admission_id = Column(UUID(as_uuid=True), ForeignKey("ipd_admissions.id", ondelete="CASCADE"), nullable=False, index=True)
    doctor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    round_time = Column(DateTime, default=datetime.utcnow)
    subjective = Column(Text, nullable=True)
    objective = Column(Text, nullable=True)
    assessment = Column(Text, nullable=True)
    plan = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    admission = relationship("IPDAdmission", back_populates="round_notes")
    doctor = relationship("User", foreign_keys=[doctor_id])

class IPDOrder(Base):
    __tablename__ = "ipd_orders"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    admission_id = Column(UUID(as_uuid=True), ForeignKey("ipd_admissions.id", ondelete="CASCADE"), nullable=False, index=True)
    ordered_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    order_type = Column(String(50), default="Medication")  # Medication, Investigation, Diet, Nursing Care
    item_name = Column(String(255), nullable=False)
    dosage = Column(String(100), nullable=True)
    route = Column(String(50), nullable=True)
    frequency = Column(String(50), default="OD")
    duration = Column(String(50), nullable=True)
    instructions = Column(Text, nullable=True)
    status = Column(String(50), default="Active")  # Active, Completed, Discontinued
    administered_logs = Column(JSONB, default=list)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    admission = relationship("IPDAdmission", back_populates="orders")
    ordered_by = relationship("User", foreign_keys=[ordered_by_id])

class IPDFluidBalance(Base):
    __tablename__ = "ipd_fluid_balances"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    admission_id = Column(UUID(as_uuid=True), ForeignKey("ipd_admissions.id", ondelete="CASCADE"), nullable=False, index=True)
    recorded_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    record_date = Column(DateTime, default=datetime.utcnow)
    shift = Column(String(50), default="Morning")
    intake_oral = Column(Float, default=0.0)
    intake_iv = Column(Float, default=0.0)
    intake_other = Column(Float, default=0.0)
    output_urine = Column(Float, default=0.0)
    output_drain = Column(Float, default=0.0)
    output_vomitus = Column(Float, default=0.0)
    output_other = Column(Float, default=0.0)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    admission = relationship("IPDAdmission", back_populates="fluid_balances")
    recorded_by = relationship("User", foreign_keys=[recorded_by_id])

class IPDBillItem(Base):
    __tablename__ = "ipd_bill_items"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    admission_id = Column(UUID(as_uuid=True), ForeignKey("ipd_admissions.id", ondelete="CASCADE"), nullable=False, index=True)
    item_type = Column(String(50), nullable=False)  # room_rent, nursing_care, doctor_consultation, pharmacy_medication, pharmacy_surgical, lab_investigation, radiology, equipment, diet, procedure_ot, miscellaneous
    category = Column(String(100), default="General")
    service_code = Column(String(50), nullable=True)
    item_name = Column(String(255), nullable=False)
    quantity = Column(Float, default=1.0)
    unit_price = Column(Float, default=0.0)
    total_price = Column(Float, default=0.0)
    is_automated = Column(Boolean, default=False)
    billing_date = Column(DateTime, default=datetime.utcnow)
    source_module = Column(String(50), default="ipd")  # ipd, pharmacy, lims, etc.
    source_reference_id = Column(UUID(as_uuid=True), nullable=True)
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text, nullable=True)

    is_billed = Column(Boolean, default=False, nullable=False, index=True)
    status = Column(String(50), default="unbilled", nullable=False)  # unbilled, billed, paid
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True, index=True)
    billed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    admission = relationship("IPDAdmission", back_populates="bill_items")
    created_by = relationship("User", foreign_keys=[created_by_id])

class IPDPayment(Base):
    __tablename__ = "ipd_payments"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    admission_id = Column(UUID(as_uuid=True), ForeignKey("ipd_admissions.id", ondelete="CASCADE"), nullable=False, index=True)
    receipt_number = Column(String(50), unique=True, nullable=False)
    amount = Column(Float, nullable=False)
    payment_method = Column(String(50), default="cash")  # cash, card, upi, neft, cheque
    transaction_reference = Column(String(100), nullable=True)
    payment_date = Column(DateTime, default=datetime.utcnow)
    payment_type = Column(String(50), default="advance")  # advance, interim, final, refund
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True, index=True)
    notes = Column(Text, nullable=True)
    collected_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    admission = relationship("IPDAdmission", back_populates="payments")
    collected_by = relationship("User", foreign_keys=[collected_by_id])
