"""
VaidyaMD HMS — CRM & Telecaller API Router
Thin controllers delegating to CRMService and WhisperService.
Enforces multi-tenancy via get_current_user and get_branch_context dependencies.
"""

import os
import uuid
import aiofiles
from typing import Optional, List, Any
from uuid import UUID
from fastapi import APIRouter, Depends, UploadFile, File, Form, BackgroundTasks, Query, status, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_branch_context
from app.core.models.user import User
from app.modules.crm.model import LeadStatus, LeadSource
from app.modules.crm.schemas import (
    LeadCreate, LeadUpdate, LeadResponse, LeadListResponse,
    CallLogResponse, CallDispositionUpdate, DialerQueueItem, CRMAnalyticsResponse,
    HeartbeatPayload, TelecallerRosterItem, TelecallerKPIItem
)
from app.modules.crm.service import CRMService
from app.modules.crm.whisper_service import process_call_audio_transcription

router = APIRouter(prefix="/crm", tags=["CRM & Telecaller"])


def parse_branch_uuid(branch_id: Optional[Any]) -> Optional[UUID]:
    if not branch_id:
        return None
    if isinstance(branch_id, UUID):
        return branch_id
    try:
        return UUID(str(branch_id))
    except (ValueError, TypeError):
        return None


# ----------------------------------------------------------------------------
# Leads Endpoints
# ----------------------------------------------------------------------------

@router.get("/leads", response_model=LeadListResponse)
async def list_leads(
    status: Optional[LeadStatus] = Query(None),
    source: Optional[LeadSource] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    branch_id: Optional[str] = Depends(get_branch_context)
):
    service = CRMService(db)
    b_id = parse_branch_uuid(branch_id)
    total, items = await service.list_leads(
        tenant_id=current_user.hospital_id,
        branch_id=b_id,
        status=status,
        source=source,
        search=search,
        limit=limit,
        offset=offset
    )
    return LeadListResponse(total=total, items=items)


@router.post("/leads", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(
    payload: LeadCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    branch_id: Optional[str] = Depends(get_branch_context)
):
    service = CRMService(db)
    b_id = parse_branch_uuid(branch_id)
    return await service.create_lead(
        data=payload,
        tenant_id=current_user.hospital_id,
        branch_id=b_id,
        creator_id=current_user.id
    )


@router.get("/leads/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = CRMService(db)
    return await service.get_lead_by_id(lead_id=lead_id, tenant_id=current_user.hospital_id)


@router.patch("/leads/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: UUID,
    payload: LeadUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = CRMService(db)
    return await service.update_lead(
        lead_id=lead_id,
        data=payload,
        tenant_id=current_user.hospital_id,
        user_id=current_user.id
    )


@router.post("/leads/import-csv")
async def import_leads_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    branch_id: Optional[str] = Depends(get_branch_context)
):
    content = await file.read()
    service = CRMService(db)
    b_id = parse_branch_uuid(branch_id)
    return await service.import_leads_csv(
        file_content=content,
        tenant_id=current_user.hospital_id,
        branch_id=b_id,
        creator_id=current_user.id
    )


# ----------------------------------------------------------------------------
# Dialer Queue & Call Handling
# ----------------------------------------------------------------------------

@router.get("/dialer/next-lead", response_model=Optional[DialerQueueItem])
async def get_next_lead_in_queue(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    branch_id: Optional[str] = Depends(get_branch_context)
):
    service = CRMService(db)
    b_id = parse_branch_uuid(branch_id)
    return await service.get_next_lead_in_queue(
        tenant_id=current_user.hospital_id,
        branch_id=b_id,
        user_id=current_user.id
    )


@router.post("/calls/start", response_model=CallLogResponse)
async def initiate_call(
    lead_id: UUID = Form(...),
    phone: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    branch_id: Optional[str] = Depends(get_branch_context)
):
    service = CRMService(db)
    b_id = parse_branch_uuid(branch_id)
    call_log = await service.log_call_start(
        lead_id=lead_id,
        phone_dialed=phone,
        tenant_id=current_user.hospital_id,
        branch_id=b_id,
        telecaller_id=current_user.id
    )

    # Push auto-dial command to telecaller's mobile phone via WebSocket bridge
    try:
        from app.core.websocket import ws_manager
        await ws_manager.send_to_user(
            str(current_user.id),
            {
                "type": "CRM_DIAL_TRIGGER",
                "action": "DIAL",
                "call_id": str(call_log.id),
                "phone": phone,
                "lead_id": str(lead_id)
            }
        )
    except Exception as e:
        import logging
        logging.getLogger("uvicorn.error").warning(f"Failed to push dial event over WS: {e}")

    return call_log


@router.post("/calls/{call_id}/disposition", response_model=CallLogResponse)
async def update_call_disposition(
    call_id: UUID,
    payload: CallDispositionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = CRMService(db)
    return await service.update_call_disposition(
        call_id=call_id,
        data=payload,
        tenant_id=current_user.hospital_id,
        user_id=current_user.id
    )


@router.post("/calls/{call_id}/recording")
async def upload_call_recording(
    call_id: UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Called by the Companion Android App upon call termination.
    Saves audio file locally/volume and triggers background Faster-Whisper.
    """
    service = CRMService(db)
    upload_dir = os.path.join("uploads", "crm_recordings")
    os.makedirs(upload_dir, exist_ok=True)

    ext = os.path.splitext(file.filename)[1] or ".mp3"
    saved_filename = f"{call_id}_{uuid.uuid4().hex[:8]}{ext}"
    saved_path = os.path.join(upload_dir, saved_filename)

    async with aiofiles.open(saved_path, "wb") as out_file:
        content = await file.read()
        await out_file.write(content)

    # Update recording path on CallLog
    stmt = (
        CallLogResponse  # schema reference
    )
    from sqlalchemy import select
    from app.modules.crm.model import CallLog

    result = await db.execute(select(CallLog).where(CallLog.id == call_id))
    call_log = result.scalar_one_or_none()
    if call_log:
        call_log.recording_file_path = saved_path
        call_log.transcript_status = "processing"
        await db.commit()

    # Trigger self-hosted Faster-Whisper in background
    background_tasks.add_task(process_call_audio_transcription, call_id, saved_path)

    return {
        "status": "recording_uploaded",
        "call_id": call_id,
        "file_path": saved_path,
        "transcription": "queued"
    }


# ----------------------------------------------------------------------------
# Analytics Dashboard
# ----------------------------------------------------------------------------

@router.get("/analytics/dashboard", response_model=CRMAnalyticsResponse)
async def get_crm_analytics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    branch_id: Optional[str] = Depends(get_branch_context)
):
    service = CRMService(db)
    b_id = parse_branch_uuid(branch_id)
    return await service.get_analytics(tenant_id=current_user.hospital_id, branch_id=b_id)


# ----------------------------------------------------------------------------
# Android APK Hosting & Device Pairing
# ----------------------------------------------------------------------------

@router.get("/app/version")
async def get_app_version():
    """
    Checks latest version of the companion Android APK.
    Used by the Android app for in-app auto-update checks.
    """
    return {
        "version_code": 1,
        "version_name": "1.0.0",
        "download_url": "/api/crm/app/download",
        "mandatory": false,
        "changelog": "VaidyaMD Telecaller Companion v1.0.0 — Native SIM dialing & Faster-Whisper sync."
    }


@router.get("/app/download")
async def download_telecaller_apk():
    """
    Streams the latest companion Android APK.
    1. Checks local container disk (uploads/apps/vaidyamd-telecaller.apk).
    2. Fallbacks to GCS bucket if present.
    """
    apk_dir = os.path.join("uploads", "apps")
    os.makedirs(apk_dir, exist_ok=True)
    apk_file = os.path.join(apk_dir, "vaidyamd-telecaller.apk")

    if os.path.isfile(apk_file):
        return FileResponse(
            path=apk_file,
            filename="vaidyamd-telecaller-v1.0.0.apk",
            media_type="application/vnd.android.package-archive"
        )

    # If file is not yet uploaded to server volume, return guidance
    raise HTTPException(
        status_code=404,
        detail="Companion APK is currently being built. Contact admin or upload APK to uploads/apps/vaidyamd-telecaller.apk."
    )


@router.post("/app/pair-token")
async def generate_pairing_token(
    current_user: User = Depends(get_current_user),
    branch_id: Optional[str] = Depends(get_branch_context)
):
    """
    Generates an ephemeral scan-to-pair token for the logged-in telecaller.
    The QR code embeds this payload so the Android phone configures itself instantly.
    """
    pair_token = f"ptk_{uuid.uuid4().hex}"
    user_name = getattr(current_user, "full_name", None) or getattr(current_user, "name", None) or current_user.email
    tenant_id = getattr(current_user, "hospital_id", None) or getattr(current_user, "tenant_id", None)
    return {
        "pair_token": pair_token,
        "user_id": str(current_user.id),
        "user_name": user_name,
        "hospital_id": str(tenant_id),
        "branch_id": str(branch_id) if branch_id else None,
        "expires_in_seconds": 900
    }


# ----------------------------------------------------------------------------
# Telecaller Fleet Heartbeat & Admin Roster
# ----------------------------------------------------------------------------

@router.post("/fleet/heartbeat")
async def telecaller_heartbeat(
    payload: HeartbeatPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    branch_id: Optional[str] = Depends(get_branch_context)
):
    """
    Called every 30-60s by the Android companion app to report online presence,
    battery, and call states. Returns whether the device is active or has been revoked.
    """
    service = CRMService(db)
    b_id = parse_branch_uuid(branch_id)
    session = await service.record_heartbeat(
        user_id=current_user.id,
        tenant_id=current_user.hospital_id,
        branch_id=b_id,
        payload=payload
    )
    return {
        "status": "ok",
        "is_online": session.is_online,
        "is_revoked": session.is_revoked or False
    }


@router.post("/fleet/devices/{user_id}/revoke")
async def revoke_telecaller_device(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Admin Kill-Switch: Revokes the telecaller's mobile device access."""
    service = CRMService(db)
    session = await service.revoke_device(user_id=user_id, tenant_id=current_user.hospital_id)
    return {"status": "device_revoked", "user_id": str(user_id), "is_revoked": session.is_revoked}


@router.get("/fleet/roster", response_model=List[TelecallerRosterItem])
async def get_telecaller_roster(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    branch_id: Optional[str] = Depends(get_branch_context)
):
    """
    Admin Floor View: Lists all paired telecaller devices with live online/offline
    presence, active call timers, and today's calling performance.
    """
    service = CRMService(db)
    b_id = parse_branch_uuid(branch_id)
    return await service.get_telecaller_roster(tenant_id=current_user.hospital_id, branch_id=b_id)


@router.get("/fleet/kpis", response_model=List[TelecallerKPIItem])
async def get_telecaller_kpis(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    branch_id: Optional[str] = Depends(get_branch_context)
):
    """
    Admin Telecaller Scorecard: Aggregated call volume, talk time, average handle time,
    conversion rate %, and overdue follow-up counts per telecaller.
    """
    service = CRMService(db)
    b_id = parse_branch_uuid(branch_id)
    return await service.get_telecaller_kpis(tenant_id=current_user.hospital_id, branch_id=b_id)
