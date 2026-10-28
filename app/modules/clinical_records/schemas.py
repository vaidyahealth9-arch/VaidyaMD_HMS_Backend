from pydantic import BaseModel, field_serializer
from uuid import UUID
from typing import Optional, Any
from datetime import datetime, timezone

class ClinicalRecordCreate(BaseModel):
    patient_id: UUID
    record_type: str = "opd_consultation"
    data: dict[str, Any]
    plugin_id: str = "opd"
    created_by: Optional[UUID] = None

    class Config:
        extra = "allow"

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

    @field_serializer("created_at", "updated_at", when_used="json")
    def serialize_datetime(self, v: Optional[datetime]) -> Optional[str]:
        if v is None:
            return None
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc).isoformat()
        return v.isoformat()

    class Config:
        from_attributes = True
