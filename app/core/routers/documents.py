"""
VaidyaMD HMS — Document / Report Upload Router
Allows staff to upload binary files (PDFs, images, DICOM reports) and register document metadata
against patient profiles with enterprise tenant isolation.
"""

import os
import uuid
import shutil
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel

from app.config import settings
from app.core.database import get_db
from app.core.models import Document, Patient, User
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/documents", tags=["Documents & Reports"])


class DocumentCreate(BaseModel):
    patient_id: UUID
    file_name: str
    file_path: str  # Cloud URL, relative /uploads path, or fallback data URI
    mime_type: Optional[str] = "application/pdf"
    file_size: Optional[int] = None
    category: Optional[str] = "report"  # report, scan, consent, prescription, labtest
    tags: Optional[List[str]] = []
    metadata: Optional[dict] = {}


@router.post("/upload")
async def upload_document_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Multipart file upload endpoint.
    Saves file to Google Cloud Storage (if configured) or local /uploads directory,
    returning a clean URL for storage in Document.file_path.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Empty filename provided")

    # Generate secure, collision-free filename
    ext = Path(file.filename).suffix.lower() or ".bin"
    file_uuid = uuid.uuid4()
    stored_filename = f"{file_uuid}{ext}"

    # Check GCS Storage if configured
    if settings.GCS_BUCKET_NAME:
        try:
            from google.cloud import storage
            client = storage.Client()
            bucket = client.bucket(settings.GCS_BUCKET_NAME)
            blob_path = f"patient_documents/{stored_filename}"
            blob = bucket.blob(blob_path)
            content = await file.read()
            blob.upload_from_string(content, content_type=file.content_type)
            gcs_url = f"https://storage.googleapis.com/{settings.GCS_BUCKET_NAME}/{blob_path}"
            return {
                "url": gcs_url,
                "file_name": file.filename,
                "file_size": len(content),
                "mime_type": file.content_type or "application/octet-stream",
            }
        except Exception as e:
            # Fall back to local disk storage
            print(f"⚠️ GCS upload notice ({e}), storing to local disk...")
            await file.seek(0)

    # Local Disk Fallback
    upload_dir = Path(settings.UPLOAD_DIR).resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)
    destination = upload_dir / stored_filename

    content = await file.read()
    with open(destination, "wb") as f:
        f.write(content)

    return {
        "url": f"/uploads/{stored_filename}",
        "file_name": file.filename,
        "file_size": len(content),
        "mime_type": file.content_type or "application/octet-stream",
    }


@router.post("", status_code=201)
@router.post("/", status_code=201)
async def create_document(
    data: DocumentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register a document/report against a patient."""
    patient = await db.get(Patient, data.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    if patient.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Cross-tenant document registration denied")

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
@router.get("/")
async def list_documents(
    patient_id: UUID = Query(...),
    category: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all documents for a patient within user's tenant, optionally filtered by category."""
    query = (
        select(Document)
        .where(
            Document.patient_id == patient_id,
            Document.tenant_id == current_user.tenant_id,
        )
    )
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
    """Delete a document record scoped to user's tenant."""
    doc = await db.get(Document, document_id)
    if not doc or doc.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Document not found")
    await db.delete(doc)
    await db.flush()
    return None
