"""
VaidyaMD HMS — Referral Commission & Doctor Profile Models
"""

import uuid
from datetime import datetime, date
from sqlalchemy import Column, String, DateTime, Date, Float, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.core.database import Base


class ReferralCommissionConfig(Base):
    __tablename__ = "referral_commission_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    opd_pct = Column(Float, default=10.0)
    pharmacy_pct = Column(Float, default=5.0)
    iui_pct = Column(Float, default=10.0)
    embryology_pct = Column(Float, default=15.0)
    lims_pct = Column(Float, default=10.0)
    ipd_pct = Column(Float, default=10.0)
    other_pct = Column(Float, default=5.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ReferringDoctor(Base):
    __tablename__ = "referring_doctors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    clinic_name = Column(String(255), nullable=True)
    specialty = Column(String(100), nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    bank_name = Column(String(150), nullable=True)
    account_number = Column(String(100), nullable=True)
    ifsc_code = Column(String(50), nullable=True)
    upi_id = Column(String(100), nullable=True)
    pan_number = Column(String(50), nullable=True)
    custom_commission_pct = Column(Float, nullable=True, comment="Custom agreed overall commission override %")
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ReferralSettlement(Base):
    __tablename__ = "referral_settlements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    settlement_number = Column(String(50), unique=True, nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    doctor_name = Column(String(255), nullable=False, index=True)
    doctor_id = Column(UUID(as_uuid=True), ForeignKey("referring_doctors.id", ondelete="SET NULL"), nullable=True)
    amount_paid = Column(Float, nullable=False)
    payment_method = Column(String(50), default="neft")  # neft, upi, cheque, cash
    reference_number = Column(String(100), nullable=True, comment="UTR, Cheque #, or UPI Ref")
    settlement_date = Column(Date, default=date.today)
    notes = Column(Text, nullable=True)
    invoice_ids = Column(JSONB, default=list, nullable=False, comment="List of settled invoice UUID strings")
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
