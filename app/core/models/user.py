"""
VaidyaMD HMS — User Model with Configurable Permission Profile & Branch
"""

import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    DOCTOR = "doctor"
    NURSE = "nurse"
    RECEPTIONIST = "receptionist"
    EMBRYOLOGIST = "embryologist"
    ANDROLOGIST = "andrologist"
    PHARMA = "pharma"
    MANAGER = "manager"
    ACCOUNTS = "accounts"
    SCANNING = "scanning"
    COUNSELLOR = "counsellor"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False, comment="Bcrypt hash — mock for Phase 1")
    role = Column(Enum(UserRole), nullable=False, comment="Primary system display role")
    is_doctor = Column(Boolean, default=False, comment="Whether user is selectable as a Treating Doctor")

    departments = Column(JSONB, default=list, comment="List of department IDs user belongs to")
    specialization = Column(String(255), comment="E.g. 'Reproductive Medicine', 'Clinical Embryology'")
    avatar_url = Column(String(500))
    phone = Column(String(20))
    is_active = Column(Boolean, default=True)

    # Dynamic Permission Profile Link
    permission_profile_id = Column(UUID(as_uuid=True), ForeignKey("permission_profiles.id"), nullable=True)

    # Tenant & Branch FK
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=False)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    hospital = relationship("Hospital", back_populates="users", lazy="selectin")
    branch = relationship("Branch", back_populates="users", lazy="selectin")
    permission_profile = relationship("PermissionProfile", back_populates="users", lazy="selectin")
    notifications = relationship(
        "Notification",
        back_populates="recipient",
        foreign_keys="Notification.recipient_id",
        lazy="selectin",
    )
