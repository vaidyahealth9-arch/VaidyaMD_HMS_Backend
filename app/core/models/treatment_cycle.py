"""
VaidyaMD HMS — Treatment Cycle Model
"""

import uuid
import enum
from datetime import datetime, date
from sqlalchemy import Column, String, DateTime, Date, Integer, Enum, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


class TreatmentCycleStatus(str, enum.Enum):
    PLANNED = "planned"
    RUNNING = "running"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"


class TreatmentCycle(Base):
    __tablename__ = "treatment_cycles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cycle_id = Column(String(50), unique=True, nullable=False, comment="E.g. TC-2026-0001")
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, comment="Female/Primary patient")
    partner_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=True, comment="Male/Partner patient")
    treating_doctor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    treatment_type = Column(String(50), nullable=False, comment="ICSI, IVF, IUI_H, IUI_D, FET, ICSI_FET, OI, EGG_FREEZING, SURROGACY")
    status = Column(Enum(TreatmentCycleStatus), default=TreatmentCycleStatus.RUNNING, nullable=False)
    attempt_number = Column(Integer, default=1)
    start_date = Column(Date, default=date.today)
    end_date = Column(Date, nullable=True)

    cancellation_reason = Column(Text, nullable=True)
    cancelled_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    female_factors = Column(JSONB, default=list, comment="E.g. ['PCOS', 'Tubal Factor', 'Endometriosis', 'DOR']")
    male_factors = Column(JSONB, default=list, comment="E.g. ['Oligozoospermia', 'Asthenozoospermia', 'Azoospermia']")
    treatment_at_other_centre = Column(Boolean, default=False)

    protocol_template_id = Column(UUID(as_uuid=True), ForeignKey("protocol_templates.id"), nullable=True)
    sentinel_dates = Column(
        JSONB,
        default=dict,
        comment="{'lmp_day1': '...', 'baseline_scan': '...', 'stim_start': '...', 'trigger': '...', 'opu': '...', 'et': '...'}"
    )
    gametes_source = Column(
        JSONB,
        default=dict,
        comment="{'oocyte': 'self'|'donor', 'donor_oocyte_id': '...', 'sperm': 'partner'|'donor'|'surgical', 'donor_sperm_id': '...'}"
    )
    pgs_pgd_data = Column(
        JSONB,
        default=dict,
        comment="{'indicated': bool, 'type': 'PGT-A', 'lab_name': '...', 'biopsy_day': 'D5'}"
    )
    endometrial_monitoring = Column(
        JSONB,
        default=list,
        comment="Array of [{date, day_of_cycle, thickness_mm, pattern, vascularity}]"
    )
    medication_calendar = Column(
        JSONB,
        default=list,
        comment="Structured day-by-day stimulation grid [{day_number, date, medications: [], right_follicles: [], left_follicles: [], endometrium_mm, e2_pgml, p4_ngml, lh_miu, notes}]"
    )
    et_discharge_summary = Column(
        JSONB,
        default=dict,
        comment="Embryo Transfer discharge protocol, catheter loading, retained embryo check & luteal support"
    )
    remarks = Column(Text)

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    patient = relationship("Patient", foreign_keys=[patient_id], back_populates="treatment_cycles")
    partner = relationship("Patient", foreign_keys=[partner_id])
    doctor = relationship("User", foreign_keys=[treating_doctor_id])
    canceller = relationship("User", foreign_keys=[cancelled_by])
    protocol_template = relationship("ProtocolTemplate", back_populates="treatment_cycles")
    oocytes = relationship("OocyteRecord", back_populates="treatment_cycle", cascade="all, delete-orphan")
    witnesses = relationship("EmbryologyWitness", back_populates="treatment_cycle", cascade="all, delete-orphan")
    cryo_samples = relationship("CryoSample", back_populates="treatment_cycle")
