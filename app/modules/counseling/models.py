"""
VaidyaMD HMS — Counseling Note Model
Stores structured clinical counseling sessions with 8 required clinical columns
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class CounselingNote(Base):
    __tablename__ = "counseling_notes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True)
    counselor_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # 8 Required Clinical Columns
    source = Column(String(255), nullable=True, comment="Source e.g. OP, Referral, Direct Consultation")
    comments = Column(Text, nullable=True, comment="Source comments / additional counselor notes")
    procedure = Column(String(255), nullable=True, comment="Procedure e.g. IVF-ICSI, IUI, FET, Egg Freezing")
    egg_pick_up = Column(Text, nullable=True, comment="Egg pick up notes / plans")
    discussion = Column(Text, nullable=True, comment="Counseling discussion details")
    laparoscopy_hysteroscopy = Column(Text, nullable=True, comment="Laparoscopy/hysteroscopy/etc notes")
    egg_transfer = Column(Text, nullable=True, comment="Egg transfer notes")
    remarks = Column(Text, nullable=True, comment="Remarks and follow-up plans")
    signature = Column(String(255), nullable=True, comment="Counselor signature / sign-off")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    patient = relationship("Patient", lazy="selectin")
    counselor = relationship("User", foreign_keys=[counselor_id], lazy="selectin")
