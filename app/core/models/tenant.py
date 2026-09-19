"""
VaidyaMD HMS — Tenant (Hospital) Model
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


class Hospital(Base):
    __tablename__ = "hospitals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    code = Column(String(10), unique=True, nullable=False, comment="Short code for VID generation, e.g. HYD01")
    address = Column(String(500))
    phone = Column(String(20))
    email = Column(String(255))
    logo_url = Column(String(500))
    active_plugins = Column(JSONB, default=list, comment="List of active plugin IDs, e.g. ['fertility', 'opd']")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    branches = relationship("Branch", back_populates="hospital", lazy="selectin")
    permission_profiles = relationship("PermissionProfile", back_populates="hospital", lazy="selectin")
    users = relationship("User", back_populates="hospital", lazy="selectin")
    patients = relationship("Patient", back_populates="hospital", lazy="selectin")
