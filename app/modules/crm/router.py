"""
VaidyaMD HMS — CRM & Telecaller API Router
Thin controllers delegating to CRMService and WhisperService.
Enforces multi-tenancy via get_current_user and get_branch_context dependencies.
"""

import os
import uuid
import aiofiles
from datetime import datetime, date, time, timedelta
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
    city: Optional[str] = Query(None),
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
        city=city,
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
    initiated_from: str = Form("mobile"),
    target_telecaller_id: Optional[UUID] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    branch_id: Optional[str] = Depends(get_branch_context)
):
    service = CRMService(db)
    b_id = parse_branch_uuid(branch_id)
    caller_id = target_telecaller_id or current_user.id
    call_log = await service.log_call_start(
        lead_id=lead_id,
        phone_dialed=phone,
        tenant_id=current_user.hospital_id,
        branch_id=b_id,
        telecaller_id=caller_id
    )

    # Push auto-dial command to telecaller's mobile phone via WebSocket bridge
    try:
        from app.core.websocket import ws_manager
        from app.modules.crm.model import TelecallerSession
        from sqlalchemy import select

        target_ids = {str(current_user.id)}
        if target_telecaller_id:
            target_ids.add(str(target_telecaller_id))

        # Query all active online phone sessions for this tenant
        active_sess = (await db.execute(
            select(TelecallerSession.user_id).where(
                TelecallerSession.tenant_id == current_user.hospital_id,
                TelecallerSession.is_online == True,
                TelecallerSession.is_revoked == False
            )
        )).scalars().all()
        for s_uid in active_sess:
            target_ids.add(str(s_uid))

        dial_msg = {
            "type": "CRM_DIAL_TRIGGER",
            "action": "DIAL",
            "call_id": str(call_log.id),
            "phone": phone,
            "lead_id": str(lead_id),
            "initiated_from": initiated_from
        }
        for uid in target_ids:
            await ws_manager.send_to_user(uid, dial_msg)
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


@router.get("/calls", response_model=List[CallLogResponse])
async def list_call_logs(
    lead_id: Optional[UUID] = Query(None),
    telecaller_id: Optional[UUID] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = CRMService(db)
    from app.core.models.user import UserRole
    # Admins, doctors, counsellors see all hospital calls; telecallers see their own
    filter_telecaller = telecaller_id if (current_user.role in [UserRole.ADMIN, UserRole.DOCTOR, UserRole.COUNSELLOR, UserRole.RECEPTIONIST] and telecaller_id) else (None if current_user.role in [UserRole.ADMIN, UserRole.DOCTOR, UserRole.COUNSELLOR] else current_user.id)
    return await service.list_call_logs(
        tenant_id=current_user.hospital_id,
        telecaller_id=filter_telecaller,
        lead_id=lead_id,
        limit=limit,
        offset=offset
    )


@router.post("/calls/{call_id}/end", response_model=CallLogResponse)
async def log_call_end(
    call_id: UUID,
    duration_seconds: int = Form(0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = CRMService(db)
    call_log = await service.log_call_end(
        call_id=call_id,
        tenant_id=current_user.hospital_id,
        duration_seconds=duration_seconds
    )

    # Broadcast real-time call ended event to WebSocket so web desk transitions automatically
    try:
        from app.core.websocket import ws_manager
        end_msg = {
            "type": "CRM_CALL_ENDED",
            "call_id": str(call_id),
            "duration_seconds": duration_seconds,
            "lead_id": str(call_log.lead_id)
        }
        await ws_manager.send_to_user(str(call_log.telecaller_id), end_msg)
        await ws_manager.send_to_user(str(current_user.id), end_msg)
    except Exception:
        pass

    return call_log


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


@router.get("/calls/{call_id}/recording")
async def get_call_recording_stream(
    call_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Streams the recorded call audio file for in-browser HTML5 playback or download.
    """
    from sqlalchemy import select
    from fastapi.responses import FileResponse
    from app.modules.crm.model import CallLog

    result = await db.execute(select(CallLog).where(CallLog.id == call_id))
    call_log = result.scalar_one_or_none()
    if not call_log or not call_log.recording_file_path:
        raise HTTPException(status_code=404, detail="Recording not found")

    if not os.path.exists(call_log.recording_file_path):
        raise HTTPException(status_code=404, detail="Audio recording file not found on disk")

    ext = os.path.splitext(call_log.recording_file_path)[1].lower()
    media_type = "audio/aac" if ext == ".aac" else ("audio/mp4" if ext in [".m4a", ".mp4"] else "audio/mpeg")
    return FileResponse(
        path=call_log.recording_file_path,
        media_type=media_type,
        filename=os.path.basename(call_log.recording_file_path)
    )


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
    direct_apk_url = os.environ.get("TELECALLER_APK_URL")
    gcs_bucket = os.environ.get("GCS_BUCKET") or os.environ.get("GCS_BUCKET_NAME")
    download_url = (
        direct_apk_url
        or (f"https://storage.googleapis.com/{gcs_bucket}/apps/vaidyamd-telecaller.apk" if gcs_bucket else "/api/crm/app/download")
    )

    return {
        "version_code": int(os.environ.get("TELECALLER_VERSION_CODE", "5")),
        "version_name": os.environ.get("TELECALLER_VERSION_NAME", "1.3.0"),
        "download_url": download_url,
        "mandatory": False,
        "changelog": "VaidyaMD Telecaller Companion v1.3.0 — In-app QR camera pairing scanner, universal camera deep linking, post-call outcome logging dialog on mobile, in-app audio playback, and WhatsApp integration."
    }


@router.get("/app/download")
async def download_telecaller_apk():
    """
    Streams or redirects to the latest companion Android APK.
    1. Checks direct Cloud Storage Bucket URL (TELECALLER_APK_URL / GCS_BUCKET) and redirects directly (zero server load).
    2. Falls back to local container disk (uploads/apps/vaidyamd-telecaller.apk).
    """
    from fastapi.responses import RedirectResponse

    direct_apk_url = os.environ.get("TELECALLER_APK_URL")
    if direct_apk_url:
        return RedirectResponse(url=direct_apk_url, status_code=307)

    gcs_bucket = os.environ.get("GCS_BUCKET") or os.environ.get("GCS_BUCKET_NAME")
    if gcs_bucket:
        return RedirectResponse(
            url=f"https://storage.googleapis.com/{gcs_bucket}/apps/vaidyamd-telecaller.apk",
            status_code=307
        )

    apk_dir = os.path.join("uploads", "apps")
    os.makedirs(apk_dir, exist_ok=True)
    apk_file = os.path.join(apk_dir, "vaidyamd-telecaller.apk")

    if os.path.isfile(apk_file):
        return FileResponse(
            path=apk_file,
            filename="vaidyamd-telecaller.apk",
            media_type="application/vnd.android.package-archive"
        )

    # If file is not yet uploaded to server volume, return guidance
    raise HTTPException(
        status_code=404,
        detail="Companion APK is currently being deployed. Please check Cloud Storage bucket or contact admin."
    )


@router.post("/app/pair-token")
async def generate_pairing_token(
    current_user: User = Depends(get_current_user),
    branch_id: Optional[str] = Depends(get_branch_context)
):
    """
    Generates a cryptographically valid mobile companion JWT for the logged-in telecaller.
    The QR code embeds this payload so the Android phone configures itself instantly with
    full authentication for WebSocket auto-dial triggers and audio sync.
    """
    from app.core.security import create_access_token
    from datetime import timedelta

    user_name = getattr(current_user, "full_name", None) or getattr(current_user, "name", None) or current_user.email
    tenant_id = getattr(current_user, "hospital_id", None) or getattr(current_user, "tenant_id", None)
    user_role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)

    # Issue a signed companion JWT token valid for 180 days
    companion_token = create_access_token(
        data={
            "sub": str(current_user.id),
            "tenant_id": str(tenant_id),
            "role": user_role_str,
            "device_role": "telecaller_companion"
        },
        expires_delta=timedelta(days=180)
    )

    return {
        "pair_token": companion_token,
        "user_id": str(current_user.id),
        "user_name": user_name,
        "hospital_id": str(tenant_id),
        "branch_id": str(branch_id) if branch_id else None,
        "expires_in_seconds": 180 * 86400
    }


@router.get("/pair")
async def qr_pair_redirect(token: str, server: Optional[str] = None):
    """
    Handles camera scans of the pairing QR code from the standard phone camera.
    Deep-links to vaidyamd://pair?token=...&server=...
    """
    from fastapi.responses import HTMLResponse
    deep_link = f"vaidyamd://pair?token={token}&server={server or ''}"
    download_link = "/api/crm/app/download"
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Connecting VaidyaMD Telecaller</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #F8FAFC; color: #0F172A; text-align: center; padding: 48px 16px; margin: 0; }}
        .card {{ background: white; max-width: 380px; margin: 0 auto; padding: 32px 24px; border-radius: 20px; box-shadow: 0 4px 16px rgba(0,0,0,0.06); }}
        h2 {{ color: #0B4F6C; margin: 0 0 8px 0; font-size: 20px; }}
        p {{ color: #64748B; font-size: 13px; line-height: 1.5; margin: 0 0 20px 0; }}
        .btn {{ display: block; background: #0B4F6C; color: white; text-decoration: none; padding: 14px 20px; border-radius: 12px; font-weight: bold; font-size: 14px; margin-bottom: 10px; }}
        .btn-sec {{ background: #F1F5F9; color: #334155; }}
    </style>
</head>
<body>
    <div class="card">
        <h2>Pairing Mobile Dialer</h2>
        <p>Connecting your mobile phone to VaidyaMD CRM for one-click calling...</p>
        <a href="{deep_link}" class="btn">Open VaidyaMD App to Pair</a>
        <a href="{download_link}" class="btn btn-sec">Download App (If Not Installed)</a>
    </div>
    <script>
        window.location.href = "{deep_link}";
    </script>
</body>
</html>"""
    return HTMLResponse(content=html)


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
        "user_id": str(current_user.id),
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
    user_role_str = str(getattr(current_user, "role", "")).lower()
    if not any(r in user_role_str for r in ["admin", "manager", "doctor"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrative staff can revoke telecaller devices."
        )
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
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    preset: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    branch_id: Optional[str] = Depends(get_branch_context)
):
    """
    Admin Telecaller Scorecard: Aggregated call volume, talk time, average handle time,
    conversion rate %, overdue follow-up counts, and detailed outcomes (converted, callbacks,
    not interested, dnd, wrong number, skipped) per telecaller with date presets/ranges.
    """
    now = datetime.utcnow()
    filter_from = date_from
    filter_to = date_to

    if preset == "today":
        filter_from = datetime.combine(now.date(), time.min)
        filter_to = datetime.combine(now.date(), time.max)
    elif preset == "yesterday":
        yest = now.date() - timedelta(days=1)
        filter_from = datetime.combine(yest, time.min)
        filter_to = datetime.combine(yest, time.max)
    elif preset == "this_week":
        start_week = now.date() - timedelta(days=now.weekday())
        filter_from = datetime.combine(start_week, time.min)
        filter_to = datetime.combine(now.date(), time.max)
    elif preset == "this_month":
        start_month = now.date().replace(day=1)
        filter_from = datetime.combine(start_month, time.min)
        filter_to = datetime.combine(now.date(), time.max)

    service = CRMService(db)
    b_id = parse_branch_uuid(branch_id)
    return await service.get_telecaller_kpis(
        tenant_id=current_user.hospital_id,
        branch_id=b_id,
        date_from=filter_from,
        date_to=filter_to
    )
