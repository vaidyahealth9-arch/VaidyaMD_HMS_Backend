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
