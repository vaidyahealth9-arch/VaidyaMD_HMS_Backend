"""
VaidyaMD HMS — Clinical Record Model (JSONB-driven, plugin-agnostic)
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


class ClinicalRecord(Base):
    __tablename__ = "clinical_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=True)
    plugin_id = Column(String(50), nullable=False, comment="E.g. 'fertility', 'opd'")

    record_type = Column(String(100), nullable=False, comment="E.g. 'female_history', 'male_history', 'opd_consultation'")
    schema_version = Column(String(10), default="1.0", comment="Version of the JSON schema used")
    data = Column(JSONB, nullable=False, comment="The actual clinical data as JSONB — NOT hardcoded columns")

    # Audit
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    patient = relationship("Patient", back_populates="clinical_records")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])
