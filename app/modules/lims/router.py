from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional

from app.core.database import get_db
from app.core.models import User
from app.core.dependencies import get_current_user
from app.modules.lims.service import LIMSService
from app.modules.lims.schemas import ManualLabReportCreate, ReportAuthorizeRequest

router = APIRouter(prefix="/lims", tags=["LIMS & Lab Equipment Integration (Clean Architecture)"], dependencies=[Depends(get_current_user)])

def get_lims_service(db: AsyncSession = Depends(get_db)) -> LIMSService:
    return LIMSService(db)

@router.post("/manual-report", status_code=201)
async def create_manual_lab_report(
    payload: ManualLabReportCreate,
    current_user: User = Depends(get_current_user),
    service: LIMSService = Depends(get_lims_service)
):
    try:
        return await service.create_manual_lab_report(payload, current_user)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/worklist")
async def get_lims_worklist(
    status: Optional[str] = None,
    service: LIMSService = Depends(get_lims_service)
):
    return await service.get_lims_worklist(status)

@router.get("/records/{record_id}")
async def get_lims_record_detail(
    record_id: UUID,
    service: LIMSService = Depends(get_lims_service)
):
    try:
        return await service.get_lims_record_detail(record_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))



@router.post("/records/{record_id}/authorize")
async def authorize_lab_report(
    record_id: UUID, 
    payload: ReportAuthorizeRequest,
    current_user: User = Depends(get_current_user),
    service: LIMSService = Depends(get_lims_service)
):
    try:
        return await service.authorize_lab_report(record_id, payload, current_user)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


class HL7IngestPayload(BaseModel):
    raw_message: str


@router.post("/hl7-message", status_code=201)
@router.post("/hl7-message/", status_code=201)
async def ingest_hl7_message_http(
    payload: HL7IngestPayload,
    current_user: User = Depends(get_current_user),
):
    """HTTP REST Webhook for HL7 v2.x ER7 messages from cloud bridges & analyzers."""
    from app.core.hl7_server import parse_hl7_message, save_hl7_clinical_record
    parsed = parse_hl7_message(payload.raw_message)
    rec = await save_hl7_clinical_record(parsed)
    if not rec:
        raise HTTPException(status_code=400, detail="Failed to match patient or parse HL7 observation message")
    return {
        "status": "success",
        "record_id": str(rec.id),
        "test_name": parsed.get("test_name"),
        "observations_count": len(parsed.get("observations", {})),
        "message": "HL7 message ingested successfully via HTTP REST.",
    }

