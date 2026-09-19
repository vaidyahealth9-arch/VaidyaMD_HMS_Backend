from pydantic import BaseModel
from uuid import UUID
from typing import Optional, Any
from datetime import datetime

class ClinicalRecordCreate(BaseModel):
    patient_id: UUID
    record_type: str = "opd_consultation"
    data: dict[str, Any]
    plugin_id: str = "opd"
    created_by: Optional[UUID] = None

class ClinicalRecordResponse(BaseModel):
    id: UUID
    patient_id: UUID
    plugin_id: str
    record_type: str
    schema_version: str
    data: dict[str, Any]
    created_by: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
