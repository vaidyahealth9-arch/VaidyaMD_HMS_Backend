from pydantic import BaseModel
from typing import Optional, Any
from uuid import UUID

class ClinicalTemplateCreate(BaseModel):
    plugin_id: str
    record_type: str
    title: str
    description: Optional[str] = None
    schema_json: dict[str, Any]
    created_by: Optional[UUID] = None

class ClinicalTemplateUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    schema_json: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None

class ClinicalTemplateResponse(BaseModel):
    id: UUID
    plugin_id: str
    record_type: str
    title: str
    description: Optional[str]
    schema_json: dict[str, Any]
    is_active: bool

    class Config:
        from_attributes = True
