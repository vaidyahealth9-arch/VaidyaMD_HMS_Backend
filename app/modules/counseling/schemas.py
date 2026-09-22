"""
VaidyaMD HMS — Counseling Schemas
Pydantic models for Counseling Notes with 8 clinical columns
"""

from pydantic import BaseModel, Field
from uuid import UUID
from typing import Optional, Dict, Any, List
from datetime import datetime


class CounselingNoteCreate(BaseModel):
    patient_id: UUID
    source: Optional[str] = Field(None, description="e.g. OP, Referral, Direct Consultation")
    comments: Optional[str] = Field(None, description="Comments beside source / additional counselor observations")
    procedure: Optional[str] = Field(None, description="e.g. IVF-ICSI, IUI, FET, Egg Freezing")
    egg_pick_up: Optional[str] = Field(None, description="Egg pick up notes / plans")
    discussion: Optional[str] = Field(None, description="Counseling discussion details")
    laparoscopy_hysteroscopy: Optional[str] = Field(None, description="Laparoscopy/hysteroscopy/etc notes")
    egg_transfer: Optional[str] = Field(None, description="Egg transfer notes")
    remarks: Optional[str] = Field(None, description="Remarks and follow-up plans")
    signature: Optional[str] = Field(None, description="Counselor signature / sign-off")


class CounselingNoteUpdate(BaseModel):
    source: Optional[str] = None
    comments: Optional[str] = None
    procedure: Optional[str] = None
    egg_pick_up: Optional[str] = None
    discussion: Optional[str] = None
    laparoscopy_hysteroscopy: Optional[str] = None
    egg_transfer: Optional[str] = None
    remarks: Optional[str] = None
    signature: Optional[str] = None


class CounselingNoteResponse(BaseModel):
    id: UUID
    patient_id: UUID
    patient_name: Optional[str] = None
    patient_vid: Optional[str] = None
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None
    partner_name: Optional[str] = None
    partner_vid: Optional[str] = None
    counselor_id: UUID
    counselor_name: Optional[str] = None
    tenant_id: UUID
    branch_id: Optional[UUID] = None
    source: Optional[str] = None
    comments: Optional[str] = None
    procedure: Optional[str] = None
    egg_pick_up: Optional[str] = None
    discussion: Optional[str] = None
    laparoscopy_hysteroscopy: Optional[str] = None
    egg_transfer: Optional[str] = None
    remarks: Optional[str] = None
    signature: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CounselingStatsResponse(BaseModel):
    total_notes: int
    today_notes: int
    procedures_breakdown: Dict[str, int]
