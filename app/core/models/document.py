"""
VaidyaMD HMS — Document Model (File Registry)
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    file_name = Column(String(500), nullable=False)
    file_path = Column(Text, nullable=False, comment="Local path, cloud URL, or fallback data URI")

    mime_type = Column(String(100))
    file_size = Column(Integer, comment="Size in bytes")
    category = Column(String(100), comment="E.g. 'scan', 'report', 'consent', 'prescription'")
    tags = Column(JSONB, default=list, comment="Specific tags like 'Pelvic Scan 3D NS', 'Follicular Scan'")
    metadata_ = Column("metadata", JSONB, default=dict, comment="Additional metadata like scan measurements")

    # Audit
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    patient = relationship("Patient", back_populates="documents")
    uploader = relationship("User", foreign_keys=[uploaded_by])
