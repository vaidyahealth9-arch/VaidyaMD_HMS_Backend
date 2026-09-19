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
    name = Column(String, nullable=False, unique=True)
    package_combo = Column(String, nullable=True) # e.g. "Jet Plasma + Tesla Chair"
    
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
    patient_id = Column(String, index=True, nullable=False)
    treatment_id = Column(UUID(as_uuid=True), ForeignKey('cosgyn_treatments.id'), nullable=False)
    
    start_date = Column(Date, nullable=False)
    frequency = Column(Enum(FrequencyType), default=FrequencyType.WEEKLY)
    
    total_amount = Column(Float, default=0.0)
    billed = Column(String, default="false") # 'false', 'true', 'invoice_id'

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    treatment = relationship("CosgynTreatment")
    sessions = relationship("CosgynSession", back_populates="plan", cascade="all, delete-orphan")

class CosgynSession(Base):
    __tablename__ = "cosgyn_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    plan_id = Column(UUID(as_uuid=True), ForeignKey('cosgyn_patient_plans.id'), nullable=False)
    
    equipment = Column(String, nullable=False) # "Jet Plasma", "Tesla Chair", "PRP"
    scheduled_datetime = Column(DateTime, nullable=False)
    duration_mins = Column(Integer, default=30)
    
    status = Column(Enum(SessionStatus), default=SessionStatus.SCHEDULED)
    notes = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    plan = relationship("CosgynPatientPlan", back_populates="sessions")
