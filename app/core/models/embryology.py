"""
VaidyaMD HMS — Embryology & Dual-Witnessing Audit Models
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


class OocyteRecord(Base):
    __tablename__ = "oocyte_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    treatment_cycle_id = Column(UUID(as_uuid=True), ForeignKey("treatment_cycles.id"), nullable=False)
    oocyte_number = Column(Integer, nullable=False, comment="1..N")

    # Day 0 — OPU & Insemination
    procedure_type = Column(String(50), default="ICSI", comment="ICSI, IVF, IVM, Discard")
    maturity_day0 = Column(String(50), default="MII", comment="MII, MI, GV, Degenerated, Atretic")
    quality_day0 = Column(String(50), default="Good", comment="Good, Fair, Poor, Mixed")
    oocyte_comments = Column(String(255), nullable=True)
    sperm_comments = Column(String(255), nullable=True)
    injection_datetime = Column(DateTime, nullable=True)
    injection_comments = Column(String(255), nullable=True)

    # Day 1 — Fertilization Check
    fert_check_day1 = Column(String(50), nullable=True, comment="2PN, 1PN, 3PN+, 0PN, Degenerated")
    day1_data = Column(JSONB, default=dict, comment="{'pn_details': '2PN & 2PB', 'nucleoli': 'aligned', 'halo': 'present'}")

    # Day 2–7 — Cleavage & Blastocyst Development
    day2_data = Column(JSONB, default=dict, comment="{'cells': 4, 'fragmentation_pct': 5, 'symmetry': 'even', 'grade': 'Grade 1'}")
    day3_data = Column(JSONB, default=dict, comment="{'cells': 8, 'fragmentation_pct': 5, 'symmetry': 'even', 'grade': 'Grade 1'}")
    day4_data = Column(JSONB, default=dict, comment="{'stage': 'Morula', 'compaction': 'Full'}")
    day5_data = Column(JSONB, default=dict, comment="{'stage': 'Blastocyst', 'expansion': 4, 'icm': 'A', 'te': 'A', 'gardner': '4AA', 'sart': 'Good'}")
    day6_data = Column(JSONB, default=dict, comment="{'stage': 'Blastocyst', 'expansion': 5, 'icm': 'A', 'te': 'A', 'gardner': '5AA', 'sart': 'Good'}")
    day7_data = Column(JSONB, default=dict)

    # Final Embryo Disposition
    disposition = Column(
        JSONB,
        default=dict,
        comment="{'status': 'Transferred'|'Frozen'|'PGT_Biopsied'|'Arrested'|'Discarded'|'Donated', 'straw_no': '...', 'date': '...'}"
    )

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    treatment_cycle = relationship("TreatmentCycle", back_populates="oocytes")


class EmbryologyWitness(Base):
    __tablename__ = "embryology_witnesses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    treatment_cycle_id = Column(UUID(as_uuid=True), ForeignKey("treatment_cycles.id"), nullable=False)
    day_number = Column(Integer, nullable=False, comment="Day 0 to 7")

    checked_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, comment="Primary Embryologist")
    witnessed_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, comment="Secondary Dual-Witness")

    checked_at = Column(DateTime, default=datetime.utcnow)
    witnessed_at = Column(DateTime, default=datetime.utcnow)
    is_verified = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)

    # Relationships
    treatment_cycle = relationship("TreatmentCycle", back_populates="witnesses")
    checked_by = relationship("User", foreign_keys=[checked_by_id])
    witnessed_by = relationship("User", foreign_keys=[witnessed_by_id])
