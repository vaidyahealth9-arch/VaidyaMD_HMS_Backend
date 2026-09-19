"""
VaidyaMD HMS — Cryopreservation & Physical Tank Coordinate Models
"""

import uuid
import enum
from datetime import datetime, date
from sqlalchemy import Column, String, DateTime, Date, Integer, Enum, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


class CryoSampleStatus(str, enum.Enum):
    AVAILABLE = "available"
    WARMED = "warmed"
    DISCARDED = "discarded"
    TRANSFERRED_OUT = "transferred_out"
    EXPIRED = "expired"


class CryoSample(Base):
    __tablename__ = "cryo_samples"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, comment="Female/Primary owner")
    partner_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=True, comment="Male/Partner owner")
    treatment_cycle_id = Column(UUID(as_uuid=True), ForeignKey("treatment_cycles.id"), nullable=True)

    sample_type = Column(String(50), default="embryo", comment="embryo, sperm, oocyte, ovarian_tissue, testicular_tissue")
    freezing_datetime = Column(DateTime, default=datetime.utcnow)
    day_of_freezing = Column(Integer, default=5, comment="Day 0, 3, 5, 6 etc.")

    # Physical Tank Coordinates
    straw_number = Column(String(100), nullable=False, comment="Straw identifier, e.g. STR-001")
    tank_number = Column(String(100), nullable=False, comment="E.g. Tank-1 (Liquid LN2)")
    canister_number = Column(String(100), nullable=False, comment="E.g. Canister-2")
    canister_colour = Column(String(50), default="Red")
    goblet_colour = Column(String(50), default="Yellow")
    cryo_device_colour = Column(String(50), default="Green")
    cryo_device_type = Column(String(100), default="Cryotop", comment="Cryotop, CryoLock, CBS Straw, CryoVial")

    no_of_embryos = Column(Integer, default=1)
    embryo_details = Column(
        JSONB,
        default=list,
        comment="Array of [{embryo_no: 1, grade: '4AA', stage: 'Blastocyst', comments: '...'}]"
    )
    media_lot_number = Column(String(100), nullable=True)

    embryologist_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    witness_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    status = Column(Enum(CryoSampleStatus), default=CryoSampleStatus.AVAILABLE, nullable=False)
    expiry_date = Column(Date, nullable=True, comment="Statutory / consent validity expiry date")
    consent_form_reference = Column(String(255), nullable=True, comment="E.g. ART Act Form 15 Ref #8821")
    is_donor = Column(Boolean, default=False)
    remarks = Column(Text, nullable=True)

    # Thaw / Warming History
    thaw_event = Column(
        JSONB,
        default=dict,
        comment="{'thaw_date': '...', 'embryos_warmed': 2, 'embryos_survived': 2, 'survival_rate_pct': 100, 'disposition': 'Transferred'}"
    )

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    patient = relationship("Patient", foreign_keys=[patient_id], back_populates="cryo_samples")
    partner = relationship("Patient", foreign_keys=[partner_id])
    treatment_cycle = relationship("TreatmentCycle", back_populates="cryo_samples")
    embryologist = relationship("User", foreign_keys=[embryologist_id])
    witness = relationship("User", foreign_keys=[witness_id])
