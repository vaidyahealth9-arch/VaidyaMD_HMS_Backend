"""
VaidyaMD HMS — Counseling Service
Business logic for managing patient counseling sessions
"""

from uuid import UUID
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from fastapi import HTTPException, status

from app.modules.counseling.models import CounselingNote
from app.modules.counseling.schemas import CounselingNoteCreate, CounselingNoteUpdate, CounselingNoteResponse
from app.core.models import Patient, User


class CounselingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _build_response(self, note: CounselingNote) -> CounselingNoteResponse:
        patient = note.patient or await self.db.get(Patient, note.patient_id)
        partner = None
        if patient and patient.partner_id:
            partner = await self.db.get(Patient, patient.partner_id)

        counselor = note.counselor or await self.db.get(User, note.counselor_id)

        return CounselingNoteResponse(
            id=note.id,
            patient_id=note.patient_id,
            patient_name=patient.name if patient else "Unknown Patient",
            patient_vid=patient.vid if patient else None,
            patient_age=patient.age if patient else None,
            patient_gender=patient.gender.value if patient and hasattr(patient.gender, 'value') else (str(patient.gender) if patient else None),
            partner_name=partner.name if partner else None,
            partner_vid=partner.vid if partner else None,
            counselor_id=note.counselor_id,
            counselor_name=counselor.name if counselor else "Counselor",
            tenant_id=note.tenant_id,
            branch_id=note.branch_id,
            source=note.source,
            comments=note.comments,
            procedure=note.procedure,
            egg_pick_up=note.egg_pick_up,
            discussion=note.discussion,
            laparoscopy_hysteroscopy=note.laparoscopy_hysteroscopy,
            egg_transfer=note.egg_transfer,
            remarks=note.remarks,
            signature=note.signature,
            created_at=note.created_at,
            updated_at=note.updated_at,
        )

    async def create_note(self, payload: CounselingNoteCreate, current_user: User) -> CounselingNoteResponse:
        patient = await self.db.get(Patient, payload.patient_id)
        if not patient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

        sig = payload.signature
        if not sig or not sig.strip():
            desig = current_user.specialization or "Lead Fertility Counselor"
            sig = f"{current_user.name} ({desig})"

        note = CounselingNote(
            patient_id=payload.patient_id,
            tenant_id=current_user.tenant_id,
            branch_id=getattr(current_user, 'branch_id', None) or getattr(patient, 'branch_id', None),
            counselor_id=current_user.id,
            source=payload.source,
            comments=payload.comments,
            procedure=payload.procedure,
            egg_pick_up=payload.egg_pick_up,
            discussion=payload.discussion,
            laparoscopy_hysteroscopy=payload.laparoscopy_hysteroscopy,
            egg_transfer=payload.egg_transfer,
            remarks=payload.remarks,
            signature=sig,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        self.db.add(note)
        await self.db.flush()
        await self.db.refresh(note)

        return await self._build_response(note)

    async def list_notes(
        self,
        tenant_id: UUID,
        patient_id: Optional[UUID] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[CounselingNoteResponse]:
        query = select(CounselingNote).where(CounselingNote.tenant_id == tenant_id)

        if patient_id:
            query = query.where(CounselingNote.patient_id == patient_id)

        if search and search.strip():
            s = f"%{search.strip().lower()}%"
            # Join with patient to search by name/vid
            query = query.join(Patient, CounselingNote.patient_id == Patient.id, isouter=True).where(
                or_(
                    func.lower(CounselingNote.source).like(s),
                    func.lower(CounselingNote.comments).like(s),
                    func.lower(CounselingNote.procedure).like(s),
                    func.lower(CounselingNote.discussion).like(s),
                    func.lower(CounselingNote.remarks).like(s),
                    func.lower(CounselingNote.signature).like(s),
                    func.lower(Patient.name).like(s),
                    func.lower(Patient.vid).like(s),
                )
            )

        query = query.order_by(CounselingNote.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(query)
        notes = result.scalars().all()

        return [await self._build_response(n) for n in notes]

    async def get_note(self, note_id: UUID) -> CounselingNoteResponse:
        note = await self.db.get(CounselingNote, note_id)
        if not note:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Counseling note not found")
        return await self._build_response(note)

    async def update_note(self, note_id: UUID, payload: CounselingNoteUpdate, current_user: User) -> CounselingNoteResponse:
        note = await self.db.get(CounselingNote, note_id)
        if not note:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Counseling note not found")

        update_dict = payload.model_dump(exclude_unset=True)
        for k, v in update_dict.items():
            setattr(note, k, v)

        note.updated_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(note)
        return await self._build_response(note)

    async def delete_note(self, note_id: UUID):
        note = await self.db.get(CounselingNote, note_id)
        if not note:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Counseling note not found")
        await self.db.delete(note)
        await self.db.flush()
        return {"message": "Counseling note deleted successfully"}

    async def get_stats(self, tenant_id: UUID) -> Dict[str, Any]:
        all_notes_q = select(CounselingNote).where(CounselingNote.tenant_id == tenant_id)
        res = await self.db.execute(all_notes_q)
        notes = res.scalars().all()

        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_count = sum(1 for n in notes if n.created_at >= today_start)

        procedures_breakdown: Dict[str, int] = {}
        for n in notes:
            proc = n.procedure or "General ART Counseling"
            procedures_breakdown[proc] = procedures_breakdown.get(proc, 0) + 1

        return {
            "total_notes": len(notes),
            "today_notes": today_count,
            "procedures_breakdown": procedures_breakdown,
        }
