import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Text, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base

class ClinicalTemplate(Base):
    __tablename__ = "clinical_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plugin_id = Column(String(50), nullable=False)
    record_type = Column(String(100), nullable=False, unique=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    schema_json = Column(JSONB, nullable=False)
    is_active = Column(Boolean, default=True)

    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    creator = relationship("User", foreign_keys=[created_by])

class ProtocolTemplate(Base):
    __tablename__ = "protocol_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(String(50), default="stimulation")
    is_active = Column(Boolean, default=True)

    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    hospital = relationship("Hospital")
    creator = relationship("User", foreign_keys=[created_by])
    rules = relationship("ProtocolDrugRule", back_populates="protocol_template", cascade="all, delete-orphan", order_by="ProtocolDrugRule.sort_order")
    treatment_cycles = relationship("TreatmentCycle", back_populates="protocol_template")

class ProtocolDrugRule(Base):
    __tablename__ = "protocol_drug_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    protocol_template_id = Column(UUID(as_uuid=True), ForeignKey("protocol_templates.id"), nullable=False)
    drug_name = Column(String(255), nullable=False)
    dose = Column(String(100), nullable=False)
    route = Column(String(50), default="SC")
    frequency = Column(String(50), default="OD")

    sentinel_anchor = Column(String(50), default="stim_start")
    day_start_offset = Column(Integer, default=1)
    day_end_offset = Column(Integer, default=10)
    instructions = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0)

    protocol_template = relationship("ProtocolTemplate", back_populates="rules")
