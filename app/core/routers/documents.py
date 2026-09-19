"""
VaidyaMD HMS — Document / Report Upload Router
Allows staff to register document metadata (file_name, file_path/URL, category) against a patient.
"""

import uuid
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel

from app.core.database import get_db
from app.core.models import Document, Patient, User
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/documents", tags=["Documents & Reports"])


class DocumentCreate(BaseModel):
    patient_id: UUID
    file_name: str
    file_path: str  # Could be a cloud URL or relative path
    mime_type: Optional[str] = "application/pdf"
    file_size: Optional[int] = None
    category: Optional[str] = "report"  # report, scan, consent, prescription, labtest
    tags: Optional[List[str]] = []
    metadata: Optional[dict] = {}


@router.post("", status_code=201)
async def create_document(
    data: DocumentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register a document/report against a patient (link or base64 data)."""
    patient = await db.get(Patient, data.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    doc = Document(
        patient_id=data.patient_id,
        file_name=data.file_name,
        file_path=data.file_path,
        mime_type=data.mime_type,
        file_size=data.file_size,
        category=data.category,
        tags=data.tags or [],
        metadata_=data.metadata or {},
        uploaded_by=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)
    return {
        "id": str(doc.id),
        "patient_id": str(doc.patient_id),
        "file_name": doc.file_name,
        "file_path": doc.file_path,
        "category": doc.category,
        "created_at": doc.created_at.isoformat(),
        "message": "Document registered successfully",
    }


@router.get("")
async def list_documents(
    patient_id: UUID = Query(...),
    category: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all documents for a patient, optionally filtered by category."""
    query = select(Document).where(Document.patient_id == patient_id)
    if category:
        query = query.where(Document.category == category)
    query = query.order_by(desc(Document.created_at))

    result = await db.execute(query)
    docs = result.scalars().all()

    return [
        {
            "id": str(d.id),
            "file_name": d.file_name,
            "file_path": d.file_path,
            "mime_type": d.mime_type,
            "file_size": d.file_size,
            "category": d.category,
            "tags": d.tags,
            "created_at": d.created_at.isoformat(),
        }
        for d in docs
    ]


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a document record (does not delete the actual file from storage)."""
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    await db.delete(doc)
    await db.flush()
    return None
