import uuid
from datetime import datetime, date
from sqlalchemy import Column, String, DateTime, Date, Integer, Float, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base

class PharmacyIndent(Base):
    __tablename__ = "pharmacy_indents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    indent_number = Column(String(50), nullable=False, unique=True)
    requesting_department = Column(String(100), default="OPD")
    requested_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    urgency = Column(String(20), default="Normal")
    status = Column(String(50), default="Submitted")
    items = Column(JSONB, default=list)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    requested_by = relationship("User", foreign_keys=[requested_by_id])


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    po_number = Column(String(50), nullable=False, unique=True)
    vendor_name = Column(String(150), nullable=False)
    vendor_gst = Column(String(50), nullable=True)
    vendor_contact = Column(String(100), nullable=True)
    status = Column(String(50), default="Issued")
    total_amount = Column(Float, default=0.0)
    expected_delivery_date = Column(Date, nullable=True)
    items = Column(JSONB, default=list)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class GoodsReceivedNote(Base):
    __tablename__ = "goods_received_notes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    grn_number = Column(String(50), nullable=False, unique=True)
    po_id = Column(UUID(as_uuid=True), ForeignKey("purchase_orders.id"), nullable=True)
    invoice_number = Column(String(100), nullable=False)
    invoice_date = Column(Date, default=date.today)
    vendor_name = Column(String(150), nullable=False)
    total_amount = Column(Float, default=0.0)
    status = Column(String(50), default="Verified")
    items = Column(JSONB, default=list)
    ocr_raw_data = Column(JSONB, nullable=True)
    verified_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    purchase_order = relationship("PurchaseOrder")
    verified_by = relationship("User", foreign_keys=[verified_by_id])


class InventoryBatch(Base):
    __tablename__ = "inventory_batches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    item_code = Column(String(50), nullable=False)
    item_name = Column(String(150), nullable=False)
    generic_name = Column(String(150), nullable=True)
    category = Column(String(100), default="Fertility / Injectables")
    batch_number = Column(String(50), nullable=False)
    expiry_date = Column(Date, nullable=False)
    quantity_received = Column(Integer, default=0)
    quantity_available = Column(Integer, default=0)
    purchase_rate = Column(Float, default=0.0)
    mrp = Column(Float, default=0.0)
    selling_price = Column(Float, default=0.0)
    rack_location = Column(String(50), default="Cold Chain Fridge 1")
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
