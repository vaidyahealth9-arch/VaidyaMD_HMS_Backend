import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Enum, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base

class WalletTxType(str, enum.Enum):
    DEPOSIT = "deposit"
    INVOICE_DEBIT = "invoice_debit"
    REFUND = "refund"

class PatientWallet(Base):
    __tablename__ = "patient_wallets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), unique=True, nullable=False)
    balance = Column(Numeric(12, 2), default=0.00, nullable=False)

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    patient = relationship("Patient", back_populates="wallet")
    transactions = relationship("WalletTransaction", back_populates="wallet", order_by="WalletTransaction.created_at.desc()")

class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wallet_id = Column(UUID(as_uuid=True), ForeignKey("patient_wallets.id"), nullable=False)
    transaction_type = Column(Enum(WalletTxType), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    payment_mode = Column(String(50), default="cash")
    reference_invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=True)

    notes = Column(Text, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    wallet = relationship("PatientWallet", back_populates="transactions")
    invoice = relationship("Invoice")
    creator = relationship("User", foreign_keys=[created_by])
    branch = relationship("Branch", lazy="selectin")
