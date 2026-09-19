"""
VaidyaMD HMS — Treatment Cycle Type Lookup Model
Supports 42 fertility treatment categories sourced from clinic master data.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class TreatmentCycleType(Base):
    __tablename__ = "treatment_cycle_types"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(150), nullable=False, unique=True, comment="E.g. ICSI + PGT-A, IUI*, Surrogate Commissioning Couple")
    display_order = Column(Integer, default=0, comment="Sort order for UI display")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
