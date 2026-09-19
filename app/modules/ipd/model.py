import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Float, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base

class Ward(Base):
    __tablename__ = "wards"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    code = Column(String(20), nullable=False, unique=True)
    department = Column(String(100), default="General IPD")
    base_charge_per_day = Column(Float, default=2000.0)
    total_beds = Column(Integer, default=10)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    beds = relationship("Bed", back_populates="ward", cascade="all, delete-orphan")

class Bed(Base):
    __tablename__ = "beds"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    ward_id = Column(UUID(as_uuid=True), ForeignKey("wards.id"), nullable=False)
    bed_number = Column(String(50), nullable=False)
    bed_type = Column(String(50), default="Standard")
    status = Column(String(50), default="Vacant")
    daily_rate = Column(Float, default=2000.0)
    current_admission_id = Column(UUID(as_uuid=True), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    ward = relationship("Ward", back_populates="beds")
    admissions = relationship("IPDAdmission", back_populates="bed", foreign_keys="IPDAdmission.bed_id")
    nursing_tasks = relationship("NursingTask", back_populates="bed", cascade="all, delete-orphan")

class IPDAdmission(Base):
    __tablename__ = "ipd_admissions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    admission_number = Column(String(50), nullable=False, unique=True)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    bed_id = Column(UUID(as_uuid=True), ForeignKey("beds.id"), nullable=False)
    admission_date = Column(DateTime, default=datetime.utcnow)
    discharge_date = Column(DateTime, nullable=True)
    admitting_doctor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    diagnosis = Column(String(255), nullable=True)
    package_name = Column(String(150), nullable=True)
    status = Column(String(50), default="Active")
    total_accrued_amount = Column(Float, default=0.0)
    last_accrual_date = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    patient = relationship("Patient")
    bed = relationship("Bed", back_populates="admissions", foreign_keys=[bed_id])
    admitting_doctor = relationship("User", foreign_keys=[admitting_doctor_id])
    nursing_tasks = relationship("NursingTask", back_populates="admission", cascade="all, delete-orphan")

class NursingTask(Base):
    __tablename__ = "nursing_tasks"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    admission_id = Column(UUID(as_uuid=True), ForeignKey("ipd_admissions.id"), nullable=False)
    bed_id = Column(UUID(as_uuid=True), ForeignKey("beds.id"), nullable=False)
    task_type = Column(String(50), default="Vitals")
    description = Column(String(255), nullable=False)
    scheduled_time = Column(DateTime, default=datetime.utcnow)
    frequency = Column(String(50), default="Q4H")
    status = Column(String(50), default="Pending")
    completed_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    completed_at = Column(DateTime, nullable=True)
    vitals_payload = Column(JSONB, default=dict)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    admission = relationship("IPDAdmission", back_populates="nursing_tasks")
    bed = relationship("Bed", back_populates="nursing_tasks")
    completed_by = relationship("User", foreign_keys=[completed_by_id])
