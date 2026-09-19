"""
VaidyaMD HMS — Fertility Plugin Domain Models
Encapsulates Treatment Cycles, Embryology, Dual Witnessing, Cryobank, and Cycle Types.
"""

import uuid
import enum
from datetime import datetime, date
from sqlalchemy import Column, String, DateTime, Date, Integer, Enum, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


# ==============================================================================
# 1. Treatment Cycle & Lookups
# ==============================================================================

class TreatmentCycleStatus(str, enum.Enum):
    PLANNED = "planned"
    RUNNING = "running"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"


class TreatmentCycleType(Base):
    __tablename__ = "treatment_cycle_types"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=True, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(150), nullable=False, unique=True, comment="E.g. ICSI + PGT-A, IUI*, Surrogate Commissioning Couple")
    display_order = Column(Integer, default=0, comment="Sort order for UI display")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


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

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
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


# ==============================================================================
# 2. Embryology & Witnessing Models
# ==============================================================================

class OocyteRecord(Base):
    __tablename__ = "oocyte_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=True, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
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
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=True, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    treatment_cycle_id = Column(UUID(as_uuid=True), ForeignKey("treatment_cycles.id"), nullable=False)
    day_number = Column(Integer, nullable=False, comment="Day 0 to 7")
    witness_type = Column(String(50), nullable=False, comment="OPU, INSEMINATION, FERT_CHECK, STRIP, BIOPSY, ET, FREEZING, THAW")

    primary_operator_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    witness_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    step_description = Column(String(255), nullable=True)
    patient_id_verified = Column(Boolean, default=True)
    dish_id_verified = Column(Boolean, default=True)
    witnessed_at = Column(DateTime, default=datetime.utcnow)
    remarks = Column(Text, nullable=True)

    # Relationships
    treatment_cycle = relationship("TreatmentCycle", back_populates="witnesses")
    primary_operator = relationship("User", foreign_keys=[primary_operator_id])
    witness = relationship("User", foreign_keys=[witness_user_id])


# ==============================================================================
# 3. Cryobank & Storage Coordinates
# ==============================================================================

class CryoSampleStatus(str, enum.Enum):
    AVAILABLE = "available"
    WARMED = "warmed"
    DISCARDED = "discarded"
    TRANSFERRED_OUT = "transferred_out"
    EXPIRED = "expired"


class CryoSample(Base):
    __tablename__ = "cryo_samples"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=True, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
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
    warmed_at = Column(DateTime, nullable=True)
    warmed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    warming_witness_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    survival_rate_pct = Column(Integer, nullable=True, comment="E.g. 100")
    warming_notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    treatment_cycle = relationship("TreatmentCycle", back_populates="cryo_samples")
    patient = relationship("Patient", foreign_keys=[patient_id])
    partner = relationship("Patient", foreign_keys=[partner_id])
    embryologist = relationship("User", foreign_keys=[embryologist_id])
    witness = relationship("User", foreign_keys=[witness_id])
    warmer = relationship("User", foreign_keys=[warmed_by])
