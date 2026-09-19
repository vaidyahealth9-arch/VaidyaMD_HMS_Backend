from fastapi import APIRouter, Request, Depends
from typing import Optional
from pydantic import BaseModel
from app.core.dependencies import get_current_user
from app.modules.ai_scribe.service import AIScribeService

router = APIRouter(prefix="/ai-scribe", tags=["AI Scribe Engine (Core)"], dependencies=[Depends(get_current_user)])

class ScribeParsePayload(BaseModel):
    transcript_or_audio: Optional[str] = None
    patient_id: Optional[str] = None
    doctor_notes_context: Optional[str] = None

@router.post("/parse")
async def parse_ambient_scribe(request: Request):
    """
    Ambient Voice Scribe AI Endpoint with Clinical NLP Extraction.
    Extracts vitals, complaints, diagnoses, and orders from conversational transcripts or audio context.
    Supports both application/json and multipart/form-data.
    """
    transcript = ""
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            body = await request.json()
            if isinstance(body, dict):
                transcript = f"{body.get('transcript_or_audio') or ''} {body.get('doctor_notes_context') or ''}".strip()
        else:
            form = await request.form()
            transcript = str(form.get("transcript_or_audio") or form.get("doctor_notes_context") or "").strip()
            if not transcript and "file" in form:
                f = form["file"]
                transcript = getattr(f, "filename", "")
    except Exception:
        pass

    extracted_data = AIScribeService.parse_clinical_transcript(transcript)

    return {
        "status": "awaiting_integration",
        "model": "not_configured",
        "extracted_data": extracted_data,
        "message": "Ambient AI Scribe integration is pending LLM pipeline setup.",
    }
