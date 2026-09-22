"""
VaidyaMD HMS — Cosmetic Gynecology (CosGyn) Plugin Domain Models
Encapsulates treatments, package combinations, patient plans, and procedural session tracking.
"""

import uuid
import enum
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Enum, Date
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class FrequencyType(str, enum.Enum):
    DAILY = "daily"
    TWICE_WEEKLY = "twice_weekly"
    WEEKLY = "weekly"
    FORTNIGHTLY = "fortnightly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


class SessionStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CosgynTreatment(Base):
    __tablename__ = "cosgyn_treatments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=True, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String, nullable=False, unique=True)
    package_combo = Column(String, nullable=True)  # e.g. "Jet Plasma + Tesla Chair"
    
    jet_plasma_sessions = Column(Integer, default=0)
    jet_plasma_duration_mins = Column(Integer, default=0)
    
    tesla_chair_sessions = Column(Integer, default=0)
    tesla_chair_duration_mins = Column(Integer, default=0)

    prp_sessions = Column(Integer, default=0)

    price = Column(Float, default=0.0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CosgynPatientPlan(Base):
    __tablename__ = "cosgyn_patient_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=True, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    patient_id = Column(String, index=True, nullable=False)
    treatment_id = Column(UUID(as_uuid=True), ForeignKey('cosgyn_treatments.id'), nullable=False)
    
    start_date = Column(Date, nullable=False)
    frequency = Column(Enum(FrequencyType), default=FrequencyType.WEEKLY)
    
    total_amount = Column(Float, default=0.0)
    billed = Column(String, default="false")  # 'false', 'true', 'invoice_id'

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    treatment = relationship("CosgynTreatment")
    sessions = relationship("CosgynSession", back_populates="plan", cascade="all, delete-orphan")


class CosgynSession(Base):
    __tablename__ = "cosgyn_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=True, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    plan_id = Column(UUID(as_uuid=True), ForeignKey('cosgyn_patient_plans.id'), nullable=False)
    session_number = Column(Integer, nullable=False)
    equipment = Column(String(100), nullable=True)
    duration_mins = Column(Integer, default=30)
    
    scheduled_datetime = Column(DateTime(timezone=True), nullable=True)
    status = Column(Enum(SessionStatus), default=SessionStatus.SCHEDULED)
    
    appointment_id = Column(UUID(as_uuid=True), nullable=True)

    plan = relationship("CosgynPatientPlan", back_populates="sessions")
