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

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, status
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


def resolve_upload_subpath(
    category: Optional[str],
    document_type: Optional[str],
    patient_id: Optional[str],
    tenant_id: str,
) -> str:
    """
    Classifies uploaded files into purpose-based folder hierarchies for both
    local filesystem (/app/uploads/...) and Google Cloud Storage (gs://.../...).
    """
    cat = (category or "").lower().strip()
    doc_t = (document_type or "").lower().strip()
    t_id = str(tenant_id).strip()

    # 1. Hospital Branding, Logos, Letterheads & Digital Stamps
    if doc_t in ("hospital_logo", "logo", "letterhead", "branding", "stamp") or cat == "branding":
        return f"branding/{t_id}"

    # 2. Pharmacy Invoices & GRN for Smart OCR (Partitioned by YYYY-MM)
    if doc_t in ("pharmacy_invoice", "vendor_invoice", "grn", "ocr_invoice") or cat == "pharmacy":
        now_ym = datetime.utcnow().strftime("%Y-%m")
        return f"pharmacy/invoices/{t_id}/{now_ym}"

    # 3. CSV Bulk Imports & Data Migrations
    if doc_t in ("csv_import", "bulk_import") or cat == "imports":
        return f"imports/csv/{t_id}"

    # 4. Patient-Specific Records
    p_id = str(patient_id).strip() if patient_id else "unassigned"

    # Patient facial profile photos
    if doc_t in ("patient_photo", "profile_photo") or cat == "profile":
        return f"patients/{p_id}/profile"

    # Patient government identity proofs (Aadhaar, PAN, Passport, Marriage Cert)
    if cat == "identity_proof" or doc_t in ("identity_proof", "aadhaar_card", "pan_card", "passport", "voter_id", "marriage_cert"):
        return f"patients/{p_id}/identity"

    # Ultrasound & Radiographic Imaging (TVS USG, Follicular sheets, 3D/4D scans)
    if cat == "scan" or "scan" in doc_t or doc_t in ("tvs_usg_scan", "follicular_chart", "pelvic_usg_3d", "hsg_sis_report", "obstetric_usg"):
        return f"patients/{p_id}/scans"

    # Pathology, Diagnostics & Embryology Records (CASA Semen, AMH, Serology, Karyotyping, Microscopy)
    if (
        cat in ("report", "labtest", "lab_report", "andrology", "embryology")
        or "report" in doc_t
        or "analysis" in doc_t
        or doc_t in ("semen_analysis", "amh_hormone", "viral_markers", "cbc_blood_group", "karyotype_genetic", "microscopy_photo")
    ):
        return f"patients/{p_id}/lab_reports"

    # Statutory Consents & ART Act Legal Agreements (Form 8, 11, 13, 15, Cryo consent)
    if cat == "consent" or "consent" in doc_t or doc_t.startswith("art_form_"):
        return f"patients/{p_id}/consents"

    # Prescriptions & Treatment Medication Charts (OPD Rx, External Doctor Rx, Discharge Rx)
    if cat == "prescription" or "prescription" in doc_t or "rx" in doc_t:
        return f"patients/{p_id}/prescriptions"

    # General patient attachment
    if patient_id:
        return f"patients/{p_id}/general"

    # Fallback uncategorized
    return "general"


@router.post("/upload")
async def upload_document_file(
    file: UploadFile = File(...),
    category: Optional[str] = Form(None),
    document_type: Optional[str] = Form(None),
    patient_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
):
    """
    Multipart file upload endpoint with purpose-based folder grouping.
    Saves file to Google Cloud Storage (if configured) or local /uploads directory
    under a purpose-grouped subpath (e.g. branding/{tenant_id}, patients/{patient_id}/{category}),
    returning a clean URL and folder hierarchy for storage in Document.file_path.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Empty filename provided")

    # Resolve purpose-based directory subpath
    tenant_id_str = str(current_user.tenant_id) if current_user.tenant_id else "default"
    subpath = resolve_upload_subpath(
        category=category,
        document_type=document_type,
        patient_id=patient_id,
        tenant_id=tenant_id_str,
    )

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
            blob_path = f"{subpath}/{stored_filename}"
            blob = bucket.blob(blob_path)
            content = await file.read()
            blob.upload_from_string(content, content_type=file.content_type)
            gcs_url = f"https://storage.googleapis.com/{settings.GCS_BUCKET_NAME}/{blob_path}"
            return {
                "url": gcs_url,
                "folder": subpath,
                "file_name": file.filename,
                "file_size": len(content),
                "mime_type": file.content_type or "application/octet-stream",
            }
        except Exception as e:
            # Fall back to local disk storage
            print(f"⚠️ GCS upload notice ({e}), storing to local disk...")
            await file.seek(0)

    # Local Disk Fallback
    base_upload_dir = Path(settings.UPLOAD_DIR).resolve()
    target_dir = base_upload_dir / subpath
    target_dir.mkdir(parents=True, exist_ok=True)
    destination = target_dir / stored_filename

    content = await file.read()
    with open(destination, "wb") as f:
        f.write(content)

    return {
        "url": f"/uploads/{subpath}/{stored_filename}",
        "folder": subpath,
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
