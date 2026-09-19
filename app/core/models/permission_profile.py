"""
VaidyaMD HMS — Dynamic Permission Profile Model (Configurable RBAC)
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


class PermissionProfile(Base):
    __tablename__ = "permission_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(100), nullable=False, comment="Profile name, e.g. Doctor, Nurse, Embryologist")
    description = Column(Text)
    menu_permissions = Column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Flat mapping of module/feature slugs to boolean access (e.g. {'patients': true, 'ivf_lab': true})"
    )
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    hospital = relationship("Hospital", back_populates="permission_profiles")
    users = relationship("User", back_populates="permission_profile")
