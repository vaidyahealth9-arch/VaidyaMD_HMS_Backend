import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Enum, ForeignKey, Numeric, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base

class InvoiceStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING = "pending"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"

class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_number = Column(String(50), unique=True, nullable=False, comment="Auto-generated: VMD-INV-XXXXX")
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    appointment_source = Column(String(100), default="OP")
    reason_for_attendance = Column(Text, nullable=True)
    selected_embryologist_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    items = Column(JSONB, nullable=False)
    subtotal = Column(Numeric(12, 2), nullable=False)
    discount = Column(Numeric(12, 2), default=0)
    tax = Column(Numeric(12, 2), default=0)
    total_amount = Column(Numeric(12, 2), nullable=False)
    paid_amount = Column(Numeric(12, 2), default=0)
    wallet_amount_used = Column(Numeric(12, 2), default=0)
    status = Column(Enum(InvoiceStatus), default=InvoiceStatus.DRAFT)

    payment_method = Column(String(50), default="cash")
    upi_pay_mode = Column(String(50), nullable=True)
    notes = Column(Text)

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=False)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id"), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    patient = relationship("Patient", back_populates="invoices")
    creator = relationship("User", foreign_keys=[created_by])
    embryologist = relationship("User", foreign_keys=[selected_embryologist_id])
    branch = relationship("Branch", lazy="selectin")


class TreatmentPackage(Base):
    __tablename__ = "treatment_packages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    plugin_id = Column(String(50))
    items = Column(JSONB, nullable=False)
    base_price = Column(Numeric(12, 2), nullable=False)
    is_active = Column(Boolean, default=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ServiceItem(Base):
    __tablename__ = "service_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    code = Column(String(50), nullable=False, index=True, comment="e.g. OPD-001, USG-002, LAB-003")
    name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=False, default="OP", comment="Consultation, Scan, Lab, Procedure, Nursing, Daycare")
    base_price = Column(Numeric(12, 2), nullable=False, default=0.00)
    hsn_sac = Column(String(50), nullable=True, comment="HSN or SAC statutory tax code")
    gst_rate = Column(Numeric(5, 2), default=0.00, comment="Tax rate percentage e.g. 0.00, 5.00, 18.00")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PatientPackage(Base):
    __tablename__ = "patient_packages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    package_id = Column(UUID(as_uuid=True), ForeignKey("treatment_packages.id", ondelete="SET NULL"), nullable=True)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True)
    package_name = Column(String(255), nullable=False)
    total_price = Column(Numeric(12, 2), nullable=False, default=0.00)
    status = Column(String(50), nullable=False, default="active")  # 'active', 'completed', 'cancelled'
    items = Column(JSONB, nullable=False, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    patient = relationship("Patient", lazy="selectin")
    package = relationship("TreatmentPackage", lazy="selectin")
    invoice = relationship("Invoice", lazy="selectin")

