"""
VaidyaMD HMS — CRM & Telecaller Pydantic v2 Schemas
Strict data validation models adhering to Clean Architecture standards.
"""

from typing import Optional, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.modules.crm.model import LeadStatus, LeadSource, CallDisposition


# ============================================================================
# Lead Schemas
# ============================================================================

class LeadBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    phone: str = Field(..., min_length=7, max_length=20)
    alternate_phone: Optional[str] = None
    email: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    source: LeadSource = LeadSource.EXCEL_IMPORT
    source_campaign: Optional[str] = None
    priority: int = Field(default=1, ge=1, le=3)
    tags: List[str] = Field(default_factory=list)
    notes_summary: Optional[str] = None


class LeadCreate(LeadBase):
    assigned_to_id: Optional[UUID] = None
    next_follow_up_date: Optional[datetime] = None


class LeadUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    alternate_phone: Optional[str] = None
    email: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    source: Optional[LeadSource] = None
    source_campaign: Optional[str] = None
    status: Optional[LeadStatus] = None
    priority: Optional[int] = None
    assigned_to_id: Optional[UUID] = None
    next_follow_up_date: Optional[datetime] = None
    tags: Optional[List[str]] = None
    notes_summary: Optional[str] = None
    is_converted: Optional[bool] = None


class LeadResponse(LeadBase):
    id: UUID
    tenant_id: UUID
    branch_id: Optional[UUID] = None
    status: LeadStatus
    assigned_to_id: Optional[UUID] = None
    last_contacted_at: Optional[datetime] = None
    next_follow_up_date: Optional[datetime] = None
    is_converted: bool
    converted_patient_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LeadListResponse(BaseModel):
    total: int
    items: List[LeadResponse]


# ============================================================================
# Call Log & Dialer Schemas
# ============================================================================

class CallLogCreate(BaseModel):
    lead_id: UUID
    phone_dialed: str
    duration_seconds: int = 0
    disposition: Optional[CallDisposition] = None
    notes: Optional[str] = None
    follow_up_scheduled_at: Optional[datetime] = None


class CallDispositionUpdate(BaseModel):
    disposition: CallDisposition
    notes: Optional[str] = None
    follow_up_scheduled_at: Optional[datetime] = None
    lead_status: Optional[LeadStatus] = None


class CallLogResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    branch_id: Optional[UUID] = None
    lead_id: UUID
    telecaller_id: UUID
    phone_dialed: str
    call_started_at: datetime
    call_ended_at: Optional[datetime] = None
    duration_seconds: int
    recording_file_path: Optional[str] = None
    transcript_text: Optional[str] = None
    transcript_status: str
    whisper_model_used: Optional[str] = None
    disposition: Optional[CallDisposition] = None
    notes: Optional[str] = None
    follow_up_scheduled_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Dialer Queue & Analytics Schemas
# ============================================================================

class DialerQueueItem(BaseModel):
    lead: LeadResponse
    previous_call_count: int
    last_disposition: Optional[str] = None
    last_notes: Optional[str] = None


class CRMAnalyticsResponse(BaseModel):
    total_leads: int
    new_leads: int
    calls_made_today: int
    conversions_total: int
    pending_follow_ups_today: int
    overdue_follow_ups: int
    status_breakdown: dict[str, int]
    source_breakdown: dict[str, int]


# ============================================================================
# Fleet Monitoring & Telecaller KPI Schemas
# ============================================================================

class HeartbeatPayload(BaseModel):
    device_model: Optional[str] = None
    app_version: Optional[str] = None
    sim_operator: Optional[str] = None
    battery_level: Optional[int] = None
    current_state: str = "idle"  # idle, ringing, on_call, wrap_up, offline
    current_lead_id: Optional[UUID] = None


class TelecallerRosterItem(BaseModel):
    user_id: UUID
    user_name: str
    email: str
    device_model: Optional[str] = None
    app_version: Optional[str] = None
    sim_operator: Optional[str] = None
    battery_level: Optional[int] = None
    is_online: bool
    current_state: str
    current_lead_name: Optional[str] = None
    current_lead_phone: Optional[str] = None
    call_duration_seconds: int = 0
    last_heartbeat_at: datetime
    calls_today: int = 0
    conversions_today: int = 0
    total_talk_time_seconds: int = 0


class TelecallerKPIItem(BaseModel):
    user_id: UUID
    user_name: str
    total_calls: int
    answered_calls: int
    total_duration_seconds: int
    avg_duration_seconds: int
    conversions: int
    conversion_rate_percentage: float
    overdue_follow_ups: int
