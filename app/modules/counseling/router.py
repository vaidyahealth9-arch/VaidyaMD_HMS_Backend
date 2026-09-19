"""
VaidyaMD HMS — Counseling Router
REST endpoints for Counselor Desk and Doctor Portal viewing
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional, List

from app.core.database import get_db
from app.core.models import User
from app.core.dependencies import get_current_user
from app.modules.counseling.schemas import (
    CounselingNoteCreate,
    CounselingNoteUpdate,
    CounselingNoteResponse,
    CounselingStatsResponse,
)
from app.modules.counseling.service import CounselingService

router = APIRouter(prefix="/counseling", tags=["Counselor Desk (ART Counseling)"], dependencies=[Depends(get_current_user)])


def get_service(db: AsyncSession = Depends(get_db)) -> CounselingService:
    return CounselingService(db)


@router.post("/notes", response_model=CounselingNoteResponse, status_code=status.HTTP_201_CREATED)
async def create_counseling_note(
    payload: CounselingNoteCreate,
    current_user: User = Depends(get_current_user),
    service: CounselingService = Depends(get_service),
):
    """Create a structured patient counseling session note."""
    return await service.create_note(payload, current_user)


@router.get("/notes", response_model=List[CounselingNoteResponse])
async def list_counseling_notes(
    patient_id: Optional[UUID] = Query(None, description="Filter by Patient ID"),
    search: Optional[str] = Query(None, description="Search by patient name, VID, procedure, or keyword"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    service: CounselingService = Depends(get_service),
):
    """List all counseling notes for a patient or clinic-wide."""
    return await service.list_notes(
        tenant_id=current_user.tenant_id,
        patient_id=patient_id,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.get("/stats", response_model=CounselingStatsResponse)
async def get_counseling_stats(
    current_user: User = Depends(get_current_user),
    service: CounselingService = Depends(get_service),
):
    """Get counselor desk statistics and procedure breakdown."""
    stats = await service.get_stats(tenant_id=current_user.tenant_id)
    return CounselingStatsResponse(**stats)


@router.get("/notes/{note_id}", response_model=CounselingNoteResponse)
async def get_counseling_note(
    note_id: UUID,
    current_user: User = Depends(get_current_user),
    service: CounselingService = Depends(get_service),
):
    """Get a single counseling note by ID."""
    return await service.get_note(note_id)


@router.put("/notes/{note_id}", response_model=CounselingNoteResponse)
async def update_counseling_note(
    note_id: UUID,
    payload: CounselingNoteUpdate,
    current_user: User = Depends(get_current_user),
    service: CounselingService = Depends(get_service),
):
    """Update an existing counseling note."""
    return await service.update_note(note_id, payload, current_user)


@router.delete("/notes/{note_id}")
async def delete_counseling_note(
    note_id: UUID,
    current_user: User = Depends(get_current_user),
    service: CounselingService = Depends(get_service),
):
    """Delete a counseling note."""
    return await service.delete_note(note_id)
