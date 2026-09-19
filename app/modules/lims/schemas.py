from pydantic import BaseModel
from typing import Optional, Any
from uuid import UUID



class ManualLabReportCreate(BaseModel):
    patient_id: UUID
    test_name: str
    sample_id: Optional[str] = None
    category: str = "Hematology"
    observations: dict[str, Any] = {}
    pathologist_notes: Optional[str] = None
    status: str = "Pending Authorization"
    branch_id: Optional[UUID] = None

class ReportAuthorizeRequest(BaseModel):
    pathologist_id: Optional[UUID] = None
    comments: Optional[str] = None
    verified_values: Optional[dict[str, Any]] = None
