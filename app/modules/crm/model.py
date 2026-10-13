"""
VaidyaMD HMS — CRM & Telecaller Models
Clean Architecture module for Lead Tracking, Progressive Dialing, and Call Logging.
"""

import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Enum, ForeignKey, Text, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


class LeadStatus(str, enum.Enum):
    NEW = "new"
    CONTACTED = "contacted"
    INTERESTED = "interested"
    FOLLOW_UP = "follow_up"
    CONVERTED = "converted"
    LOST = "lost"
    DO_NOT_CALL = "do_not_call"


class LeadSource(str, enum.Enum):
    GOOGLE_ADS = "google_ads"
    META_ADS = "meta_ads"
    WEBSITE = "website"
    DOCTOR_REFERRAL = "doctor_referral"
    WALK_IN = "walk_in"
    WHATSAPP = "whatsapp"
    EXCEL_IMPORT = "excel_import"
    OTHER = "other"


class CallDisposition(str, enum.Enum):
    INTERESTED = "interested"
    CALLBACK_REQUESTED = "callback_requested"
    WRONG_NUMBER = "wrong_number"
    NOT_REACHABLE = "not_reachable"
    NOT_INTERESTED = "not_interested"
    CONVERTED_APPOINTMENT = "converted_appointment"
    DND = "dnd"


class Lead(Base):
    __tablename__ = "crm_leads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id"), nullable=True, index=True)

    # Lead Contact Information
    name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=False, index=True)
    alternate_phone = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)

    # Lead Meta & Pipeline Status
    source = Column(Enum(LeadSource), default=LeadSource.EXCEL_IMPORT, nullable=False)
    source_campaign = Column(String(255), nullable=True, comment="E.g. Summer IVF Camp 2026")
    status = Column(Enum(LeadStatus), default=LeadStatus.NEW, nullable=False, index=True)
    priority = Column(Integer, default=1, comment="1: Standard, 2: High, 3: Urgent")
    
    # Ownership & Assignment
    assigned_to_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    last_contacted_at = Column(DateTime, nullable=True)
    next_follow_up_date = Column(DateTime, nullable=True, index=True)
    
    # Tagging and Extra Attributes
    tags = Column(JSONB, default=list, comment="Custom tags: IVF Inpatient, PCOS inquiry, etc.")
    notes_summary = Column(Text, nullable=True)
    is_converted = Column(Boolean, default=False)
    converted_patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
    converted_patient = relationship("Patient", foreign_keys=[converted_patient_id])
    call_logs = relationship("CallLog", back_populates="lead", cascade="all, delete-orphan", order_by="desc(CallLog.created_at)")
    status_history = relationship("LeadStatusHistory", back_populates="lead", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_crm_leads_tenant_status", "tenant_id", "status"),
        Index("ix_crm_leads_follow_up", "tenant_id", "next_follow_up_date"),
    )


class CallLog(Base):
    __tablename__ = "crm_call_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id"), nullable=True)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("crm_leads.id"), nullable=False, index=True)
    telecaller_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # Call Technical Metrics
    phone_dialed = Column(String(20), nullable=False)
    call_started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    call_ended_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, default=0)
    
    # Audio Recording & Transcription
    recording_file_path = Column(String(500), nullable=True, comment="Local path or Cloud Storage URL")
    transcript_text = Column(Text, nullable=True, comment="Whisper Speech-to-Text output")
    transcript_status = Column(String(50), default="pending", comment="pending, processing, completed, failed, skipped")
    whisper_model_used = Column(String(50), nullable=True)

    # Post-Call Capture
    disposition = Column(Enum(CallDisposition), nullable=True)
    notes = Column(Text, nullable=True)
    follow_up_scheduled_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    lead = relationship("Lead", back_populates="call_logs")
    telecaller = relationship("User", foreign_keys=[telecaller_id])


class LeadStatusHistory(Base):
    __tablename__ = "crm_lead_status_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("crm_leads.id"), nullable=False, index=True)
    old_status = Column(String(50), nullable=True)
    new_status = Column(String(50), nullable=False)
    changed_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    lead = relationship("Lead", back_populates="status_history")
    changed_by = relationship("User", foreign_keys=[changed_by_id])


class TelecallerSession(Base):
    __tablename__ = "crm_telecaller_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=False, index=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id"), nullable=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True, index=True)

    device_id = Column(String(100), nullable=True, index=True, comment="Hardware Android ID")
    is_revoked = Column(Boolean, default=False, index=True, comment="Admin remote kill switch")

    # Device & App Telemetry
    device_model = Column(String(100), nullable=True, comment="e.g. Samsung Galaxy M34")
    app_version = Column(String(20), nullable=True, comment="e.g. 1.0.0")
    sim_operator = Column(String(50), nullable=True, comment="e.g. Jio 5G, Airtel")
    battery_level = Column(Integer, nullable=True)

    # Real-Time Operational State
    is_online = Column(Boolean, default=False, index=True)
    current_state = Column(String(50), default="idle", comment="idle, ringing, on_call, wrap_up, offline")
    current_lead_id = Column(UUID(as_uuid=True), ForeignKey("crm_leads.id"), nullable=True)
    current_call_started_at = Column(DateTime, nullable=True)

    last_heartbeat_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    paired_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    current_lead = relationship("Lead", foreign_keys=[current_lead_id])
