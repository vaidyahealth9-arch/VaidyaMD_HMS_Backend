"""
VaidyaMD HMS — Branch Model (Multi-Clinic Foundation)
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


class Branch(Base):
    __tablename__ = "branches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=False)
    name = Column(String(255), nullable=False)
    code = Column(String(20), nullable=False, comment="Branch code, e.g. MAIN, HYD-01")
    address = Column(String(500))
    phone = Column(String(20))
    email = Column(String(255))
    is_main_branch = Column(Boolean, default=False)
    ip_whitelist = Column(JSONB, default=list, comment="List of allowed IP addresses / CIDR ranges")
    gstin = Column(String(50), nullable=True, comment="Local branch GSTIN for physical invoices")
    enabled_plugins = Column(JSONB, default=list, comment="List of enabled plugins for this branch; empty means all hospital active plugins")
    receipt_header = Column(JSONB, default=dict, comment="Physical branch receipt printing header: address, state_code, phone, email")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    hospital = relationship("Hospital", back_populates="branches")
    users = relationship("User", back_populates="branch")
    patients = relationship("Patient", back_populates="branch")
