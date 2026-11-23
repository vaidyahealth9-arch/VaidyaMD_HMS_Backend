"""
Operation Theatre (OT) Service — IPD Module
Handles surgical scheduling, wheel in/out tracking, clinical notes, and rolling bill ledger posting.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.timezone import IST, get_now_ist_naive, to_ist_iso
from app.core.models import User
from app.modules.ipd.model import IPDAdmission, IPDOperationTheatreRecord, IPDBillItem
from app.modules.ipd.schemas import OTRecordCreate, OTRecordUpdate, OTBillReviewPayload


def _to_naive_ist(dt: Optional[datetime]) -> Optional[datetime]:
    if not dt:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(IST).replace(tzinfo=None)
    return dt


def _clean_doc_name(name: Optional[str]) -> str:
    if not name:
        return ""
    clean = name.strip()
    return clean[4:].strip() if clean.lower().startswith("dr. ") else (clean[3:].strip() if clean.lower().startswith("dr.") else clean)


class OTService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_ot_records(self, admission_id: UUID, tenant_id: Optional[UUID] = None) -> List[Dict[str, Any]]:
        query = select(IPDOperationTheatreRecord).where(IPDOperationTheatreRecord.admission_id == admission_id)
        if tenant_id:
            query = query.where(IPDOperationTheatreRecord.tenant_id == tenant_id)
        res = await self.db.execute(query.order_by(IPDOperationTheatreRecord.created_at.desc()))
        records = []
        for r in res.scalars().all():
            primary_surgeon = await self.db.get(User, r.primary_surgeon_id) if r.primary_surgeon_id else None
            asst_surgeon = await self.db.get(User, r.assistant_surgeon_id) if r.assistant_surgeon_id else None
            anesthetist = await self.db.get(User, r.anesthetist_id) if r.anesthetist_id else None
            scrub_nurse = await self.db.get(User, r.scrub_nurse_id) if r.scrub_nurse_id else None
            circ_nurse = await self.db.get(User, r.circulating_nurse_id) if r.circulating_nurse_id else None

            asst_name = asst_surgeon.name if asst_surgeon else r.assistant_surgeon_name
            anes_name = anesthetist.name if anesthetist else r.anesthetist_name

            records.append({
                "id": str(r.id),
                "admission_id": str(r.admission_id),
                "patient_id": str(r.patient_id),
                "procedure_name": r.procedure_name,
                "surgery_category": r.surgery_category,
                "status": r.status,
                "wheel_in_time": to_ist_iso(r.wheel_in_time) if r.wheel_in_time else None,
                "wheel_out_time": to_ist_iso(r.wheel_out_time) if r.wheel_out_time else None,
                "total_ot_hours": r.total_ot_hours or 0.0,
                "primary_surgeon": {"id": str(primary_surgeon.id), "name": _clean_doc_name(primary_surgeon.name)} if primary_surgeon else None,
                "assistant_surgeon": {"id": str(asst_surgeon.id) if asst_surgeon else "", "name": _clean_doc_name(asst_name)} if asst_name else None,
                "assistant_surgeon_name": r.assistant_surgeon_name,
                "anesthetist": {"id": str(anesthetist.id) if anesthetist else "", "name": _clean_doc_name(anes_name)} if anes_name else None,
                "anesthetist_name": r.anesthetist_name,
                "scrub_nurse": {"id": str(scrub_nurse.id), "name": scrub_nurse.name} if scrub_nurse else None,
                "circulating_nurse": {"id": str(circ_nurse.id), "name": circ_nurse.name} if circ_nurse else None,
                "guest_surgeons": r.guest_surgeons or [],
                "anesthesia_type": r.anesthesia_type,
                "anesthesia_notes": r.anesthesia_notes,
                "pre_op_diagnosis": r.pre_op_diagnosis,
                "post_op_diagnosis": r.post_op_diagnosis,
                "operative_notes": r.operative_notes,
                "post_op_orders": r.post_op_orders,
                "ot_hourly_rate": r.ot_hourly_rate or 1500.0,
                "ot_room_charge": r.ot_room_charge or 0.0,
                "procedure_fee": r.procedure_fee or 0.0,
                "surgeon_fee": r.surgeon_fee or 0.0,
                "anesthesia_fee": r.anesthesia_fee or 0.0,
                "guest_surgeons_fee": r.guest_surgeons_fee or 0.0,
                "total_ot_charge": r.total_ot_charge or 0.0,
                "is_billed": r.is_billed or False,
                "created_at": to_ist_iso(r.created_at) if r.created_at else "",
            })
        return records

    async def create_ot_record(self, admission_id: UUID, payload: OTRecordCreate, current_user: User) -> Dict[str, Any]:
        admission = await self.db.get(IPDAdmission, admission_id)
        if not admission:
            raise ValueError("Admission not found")

        w_in = _to_naive_ist(payload.wheel_in_time)
        w_out = _to_naive_ist(payload.wheel_out_time)
        total_hours = payload.total_ot_hours or 0.0
        if w_in and w_out:
            diff = (w_out - w_in).total_seconds()
            if diff > 0:
                total_hours = round(diff / 3600.0, 2)

        hourly_rate = payload.ot_hourly_rate or 1500.0
        room_charge = round(total_hours * hourly_rate, 2)
        guest_fee = sum(float(g.get("fee", 0.0)) for g in (payload.guest_surgeons or [])) if payload.guest_surgeons else (payload.guest_surgeons_fee or 0.0)
        total_charge = room_charge + (payload.procedure_fee or 0.0) + (payload.surgeon_fee or 0.0) + (payload.anesthesia_fee or 0.0) + guest_fee

        record = IPDOperationTheatreRecord(
            tenant_id=admission.tenant_id,
            branch_id=admission.branch_id,
            admission_id=admission.id,
            patient_id=admission.patient_id,
            procedure_name=payload.procedure_name,
            surgery_category=payload.surgery_category or "Major",
            status=payload.status or "Scheduled",
            wheel_in_time=w_in,
            wheel_out_time=w_out,
            total_ot_hours=total_hours,
            primary_surgeon_id=payload.primary_surgeon_id,
            assistant_surgeon_id=payload.assistant_surgeon_id,
            assistant_surgeon_name=payload.assistant_surgeon_name,
            anesthetist_id=payload.anesthetist_id,
            anesthetist_name=payload.anesthetist_name,
            scrub_nurse_id=payload.scrub_nurse_id,
            circulating_nurse_id=payload.circulating_nurse_id,
            guest_surgeons=payload.guest_surgeons or [],
            anesthesia_type=payload.anesthesia_type or "General",
            anesthesia_notes=payload.anesthesia_notes,
            pre_op_diagnosis=payload.pre_op_diagnosis,
            post_op_diagnosis=payload.post_op_diagnosis,
            operative_notes=payload.operative_notes,
            post_op_orders=payload.post_op_orders,
            ot_hourly_rate=hourly_rate,
            ot_room_charge=room_charge,
            procedure_fee=payload.procedure_fee or 0.0,
            surgeon_fee=payload.surgeon_fee or 0.0,
            anesthesia_fee=payload.anesthesia_fee or 0.0,
            guest_surgeons_fee=guest_fee,
            total_ot_charge=total_charge,
            is_billed=False,
        )

        self.db.add(record)
        await self.db.flush()
        return {"id": str(record.id), "message": f"OT Record for '{record.procedure_name}' created."}

    async def update_ot_record(self, ot_record_id: UUID, payload: OTRecordUpdate, tenant_id: Optional[UUID] = None) -> Dict[str, Any]:
        query = select(IPDOperationTheatreRecord).where(IPDOperationTheatreRecord.id == ot_record_id)
        if tenant_id:
            query = query.where(IPDOperationTheatreRecord.tenant_id == tenant_id)
        res = await self.db.execute(query)
        record = res.scalars().first()
        if not record:
            raise ValueError("OT record not found")

        data = payload.model_dump(exclude_unset=True)
        if "wheel_in_time" in data:
            data["wheel_in_time"] = _to_naive_ist(data["wheel_in_time"])
        if "wheel_out_time" in data:
            data["wheel_out_time"] = _to_naive_ist(data["wheel_out_time"])

        for k, v in data.items():
            setattr(record, k, v)

        if record.wheel_in_time and record.wheel_out_time:
            diff = (record.wheel_out_time - record.wheel_in_time).total_seconds()
            record.total_ot_hours = round(diff / 3600.0, 2) if diff > 0 else 0.0

        hourly_rate = record.ot_hourly_rate or 1500.0
        record.ot_room_charge = round((record.total_ot_hours or 0.0) * hourly_rate, 2)
        if record.guest_surgeons:
            record.guest_surgeons_fee = sum(float(g.get("fee", 0.0)) for g in record.guest_surgeons)
        record.total_ot_charge = (
            record.ot_room_charge + (record.procedure_fee or 0.0) + (record.surgeon_fee or 0.0) +
            (record.anesthesia_fee or 0.0) + (record.guest_surgeons_fee or 0.0)
        )
        record.updated_at = get_now_ist_naive()
        await self.db.flush()
        return {"id": str(record.id), "message": "OT Record updated successfully."}

    def _add_bill_item(self, admission: IPDAdmission, record: IPDOperationTheatreRecord, user: User, item_type: str, category: str, code: str, name: str, qty: float, price: float, notes: Optional[str]):
        item = IPDBillItem(
            tenant_id=admission.tenant_id,
            branch_id=admission.branch_id,
            admission_id=admission.id,
            item_type=item_type,
            category=category,
            service_code=code,
            item_name=name,
            quantity=qty,
            unit_price=price,
            total_price=round(qty * price, 2),
            is_automated=False,
            billing_date=get_now_ist_naive(),
            source_module="ipd_ot",
            source_reference_id=record.id,
            created_by_id=user.id,
            notes=notes,
        )
        self.db.add(item)

    async def post_ot_billing(self, ot_record_id: UUID, payload: OTBillReviewPayload, current_user: User) -> Dict[str, Any]:
        query = select(IPDOperationTheatreRecord).where(IPDOperationTheatreRecord.id == ot_record_id)
        if current_user.tenant_id:
            query = query.where(IPDOperationTheatreRecord.tenant_id == current_user.tenant_id)
        res = await self.db.execute(query)
        record = res.scalars().first()
        if not record:
            raise ValueError("OT record not found")

        admission = await self.db.get(IPDAdmission, record.admission_id)
        if not admission:
            raise ValueError("Admission not found")

        items_created = []
        total_posted = 0.0

        if payload.ot_room_charge > 0:
            hrs = record.total_ot_hours or 1.0
            rate = record.ot_hourly_rate or 1500.0
            self._add_bill_item(admission, record, current_user, "procedure_ot", "Operation Theatre", "IPD-OT-TABLE", f"OT Table Charge ({hrs} hrs @ Rs.{rate:g}/hr) - {record.procedure_name}", 1.0, payload.ot_room_charge, payload.notes)
            items_created.append("OT Table Charge")
            total_posted += payload.ot_room_charge

        if payload.procedure_fee > 0:
            self._add_bill_item(admission, record, current_user, "procedure_ot", "Operation Theatre", "IPD-SURG-BASE", f"Surgical Procedure Fee: {record.procedure_name} ({record.surgery_category})", 1.0, payload.procedure_fee, payload.notes)
            items_created.append("Procedure Fee")
            total_posted += payload.procedure_fee

        if payload.surgeon_fee > 0:
            s_name = "Primary Surgeon"
            if record.primary_surgeon_id:
                s_user = await self.db.get(User, record.primary_surgeon_id)
                if s_user:
                    s_name = f"Dr. {_clean_doc_name(s_user.name)}"
            self._add_bill_item(admission, record, current_user, "doctor_consultation", "Surgeon Professional Fee", "IPD-SURG-FEE", f"Surgeon Operating Fee - {s_name} ({record.procedure_name})", 1.0, payload.surgeon_fee, payload.notes)
            items_created.append("Surgeon Fee")
            total_posted += payload.surgeon_fee

        if payload.anesthesia_fee > 0:
            a_name = "Anesthesiologist"
            if record.anesthetist_id:
                a_user = await self.db.get(User, record.anesthetist_id)
                if a_user:
                    a_name = f"Dr. {_clean_doc_name(a_user.name)}"
            elif record.anesthetist_name:
                a_name = f"Dr. {_clean_doc_name(record.anesthetist_name)}"
            self._add_bill_item(admission, record, current_user, "doctor_consultation", "Anesthesia Professional Fee", "IPD-ANES-FEE", f"Anesthesia Charges ({record.anesthesia_type}) - {a_name}", 1.0, payload.anesthesia_fee, payload.notes)
            items_created.append("Anesthesia Fee")
            total_posted += payload.anesthesia_fee

        # Guest / Visiting Surgeons posting
        guest_list = payload.guest_surgeons or record.guest_surgeons or []
        for g in guest_list:
            g_fee = float(g.get("fee", 0.0))
            if g_fee > 0:
                g_name = f"Dr. {_clean_doc_name(g.get('name', 'Visiting Specialist'))}"
                g_role = g.get("role", "Visiting Surgeon")
                self._add_bill_item(admission, record, current_user, "doctor_consultation", "Visiting Surgeon Fee", "IPD-VISIT-SURG", f"Visiting Surgeon Fee - {g_name} ({g_role})", 1.0, g_fee, payload.notes)
                items_created.append(f"Guest Surgeon ({g_name})")
                total_posted += g_fee

        record.ot_room_charge = payload.ot_room_charge
        record.procedure_fee = payload.procedure_fee
        record.surgeon_fee = payload.surgeon_fee
        record.anesthesia_fee = payload.anesthesia_fee
        record.guest_surgeons_fee = sum(float(g.get("fee", 0.0)) for g in guest_list)
        record.total_ot_charge = total_posted
        record.is_billed = True
        record.status = "Completed"

        admission.total_accrued_amount = round((admission.total_accrued_amount or 0.0) + total_posted, 2)
        await self.db.flush()

        return {
            "success": True,
            "message": f"Successfully posted {len(items_created)} OT charges to patient's Rolling Bill.",
            "total_posted": total_posted,
            "items_posted": items_created,
        }
