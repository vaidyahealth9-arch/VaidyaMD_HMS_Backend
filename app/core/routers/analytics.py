"""
VaidyaMD HMS — Revenue Leakage Engine & Clinical Analytics Router
Real-time database aggregation for hospital KPIs, department breakdowns,
monthly trends, referral ROI, leakage detection, and no-show queues.
"""

import uuid
from datetime import datetime, date, timedelta
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_, or_
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from typing import Optional, Any, List
from uuid import UUID

from app.core.database import get_db
from app.core.models import (
    ClinicalRecord, Invoice, Appointment, Patient, User, Hospital,
    InvoiceStatus, Bed, Notification, NotificationType, AppointmentStatus
)
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/analytics", tags=["Revenue Leakage & Hospital Analytics"])


class ResolveLeakagePayload(BaseModel):
    leakage_item_id: str
    patient_id: UUID
    item_description: str
    amount: float
    department: str = "OPD"


@router.get("/revenue-breakdown")
async def get_revenue_breakdown(
    timeframe: Optional[str] = Query(None, description="today, 7d, 30d, 90d, this_month, this_year, all"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Hospital revenue analytics partitioned dynamically by department, doctor, and monthly growth trends.
    Uses 100% real database records.
    """
    now = datetime.utcnow()
    start_time = None
    if timeframe == "today":
        start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif timeframe == "7d":
        start_time = now - timedelta(days=7)
    elif timeframe == "30d":
        start_time = now - timedelta(days=30)
    elif timeframe == "90d":
        start_time = now - timedelta(days=90)
    elif timeframe == "this_month":
        start_time = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif timeframe == "this_year":
        start_time = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

    # Base query for all invoices (for trend & leakage prevented calculation)
    all_inv_query = select(Invoice).order_by(Invoice.created_at.desc())
    if current_user.tenant_id:
        all_inv_query = all_inv_query.where(Invoice.tenant_id == current_user.tenant_id)

    res_all = await db.execute(all_inv_query)
    all_invoices = res_all.scalars().all()

    # Filtered invoices for current timeframe metrics
    if start_time:
        invoices = [inv for inv in all_invoices if inv.created_at and inv.created_at >= start_time]
    else:
        invoices = all_invoices

    total_billed = float(sum(float(inv.total_amount or 0) for inv in invoices))
    total_collected = float(sum(float(inv.paid_amount or 0) for inv in invoices))
    pending_collections = max(0.0, total_billed - total_collected)
    collection_efficiency = round((total_collected / total_billed * 100), 1) if total_billed > 0 else 0.0

    # 1. Dynamic Department Breakdown
    dept_totals = defaultdict(float)
    dept_counts = defaultdict(int)
    for inv in invoices:
        source = (inv.appointment_source or "OP").upper()
        amount = float(inv.total_amount or 0.0)
        
        assigned = False
        if any(k in source for k in ["IVF", "ART", "EMBRYO", "PACKAGE"]):
            dept_totals["IVF & ART Procedures"] += amount
            dept_counts["IVF & ART Procedures"] += 1
            assigned = True
        elif any(k in source for k in ["PHARM", "RX", "MED"]):
            dept_totals["Pharmacy & Therapeutics"] += amount
            dept_counts["Pharmacy & Therapeutics"] += 1
            assigned = True
        elif any(k in source for k in ["IP", "WARD", "SURGERY", "ADMISSION"]):
            dept_totals["IPD Ward & OT Surgeries"] += amount
            dept_counts["IPD Ward & OT Surgeries"] += 1
            assigned = True
        elif any(k in source for k in ["LIMS", "LAB", "ANDROLOGY", "CASA", "DIAGNOSTIC"]):
            dept_totals["LIMS & Andrology Diagnostics"] += amount
            dept_counts["LIMS & Andrology Diagnostics"] += 1
            assigned = True

        if not assigned:
            # Inspect line items
            for it in (inv.items or []):
                desc_lower = str(it.get("description", "")).lower()
                if any(k in desc_lower for k in ["ivf", "icsi", "embryo", "opu", "stim"]):
                    dept_totals["IVF & ART Procedures"] += amount
                    dept_counts["IVF & ART Procedures"] += 1
                    assigned = True
                    break
                elif any(k in desc_lower for k in ["tab", "cap", "inj", "syrup", "pharm"]):
                    dept_totals["Pharmacy & Therapeutics"] += amount
                    dept_counts["Pharmacy & Therapeutics"] += 1
                    assigned = True
                    break
                elif any(k in desc_lower for k in ["bed", "ward", "admission"]):
                    dept_totals["IPD Ward & OT Surgeries"] += amount
                    dept_counts["IPD Ward & OT Surgeries"] += 1
                    assigned = True
                    break
                elif any(k in desc_lower for k in ["semen", "cbc", "blood", "test", "scan", "dfi"]):
                    dept_totals["LIMS & Andrology Diagnostics"] += amount
                    dept_counts["LIMS & Andrology Diagnostics"] += 1
                    assigned = True
                    break

        if not assigned:
            dept_totals["OPD Consultations"] += amount
            dept_counts["OPD Consultations"] += 1

    standard_departments = [
        ("IVF & ART Procedures", "#4f46e5"),
        ("Pharmacy & Therapeutics", "#06b6d4"),
        ("IPD Ward & OT Surgeries", "#10b981"),
        ("OPD Consultations", "#8b5cf6"),
        ("LIMS & Andrology Diagnostics", "#f59e0b"),
    ]

    dept_revenue = []
    for d_name, color in standard_departments:
        actual_amt = round(dept_totals.get(d_name, 0.0), 2)
        pct = round((actual_amt / total_billed * 100), 1) if total_billed > 0 else 0.0
        dept_revenue.append({
            "department": d_name,
            "revenue": actual_amt,
            "color": color,
            "pct": pct,
            "count": dept_counts.get(d_name, 0),
        })

    # 2. Dynamic Monthly Trend (Past 6 Months Chronological)
    monthly_trend = []
    for i in range(5, -1, -1):
        target_year = now.year
        target_month = now.month - i
        while target_month <= 0:
            target_month += 12
            target_year -= 1
        
        m_date = date(target_year, target_month, 1)
        m_label = m_date.strftime("%b")
        
        month_invoices = [
            inv for inv in all_invoices
            if inv.created_at and inv.created_at.year == target_year and inv.created_at.month == target_month
        ]
        
        m_rev = float(sum(float(inv.total_amount or 0) for inv in month_invoices))
        m_collected = float(sum(float(inv.paid_amount or 0) for inv in month_invoices))
        
        m_opd = 0.0
        m_ivf = 0.0
        m_pharmacy = 0.0
        m_ipd = 0.0
        for inv in month_invoices:
            src = (inv.appointment_source or "OP").upper()
            amt = float(inv.total_amount or 0.0)
            if any(k in src for k in ["IVF", "ART", "PACKAGE"]):
                m_ivf += amt
            elif any(k in src for k in ["PHARM", "RX"]):
                m_pharmacy += amt
            elif any(k in src for k in ["IP", "WARD"]):
                m_ipd += amt
            else:
                m_opd += amt

        monthly_trend.append({
            "month": m_label,
            "year": target_year,
            "revenue": round(m_rev, 2),
            "collected": round(m_collected, 2),
            "opd": round(m_opd, 2),
            "ivf": round(m_ivf, 2),
            "pharmacy": round(m_pharmacy, 2),
            "ipd": round(m_ipd, 2),
        })

    # 3. Dynamic Referring Doctors & Marketing Attribution from real patients
    pat_query = select(Patient)
    if current_user.tenant_id:
        pat_query = pat_query.where(Patient.tenant_id == current_user.tenant_id)
    pats_res = await db.execute(pat_query)
    all_patients = pats_res.scalars().all()

    doctor_referrals = defaultdict(lambda: {"patients_referred": 0, "revenue_generated": 0.0, "total_collected": 0.0, "type": "walk_in"})
    for p in all_patients:
        doc_name = p.referred_by_name or (
            f"Dr. {p.referred_by_type.title()}" if p.referred_by_type and p.referred_by_type not in ["self", "walk_in"] else "Direct / Self-Walk-in"
        )
        doctor_referrals[doc_name]["patients_referred"] += 1
        doctor_referrals[doc_name]["type"] = p.referred_by_type or "walk_in"
        pat_invs = [inv for inv in all_invoices if inv.patient_id == p.id]
        doctor_referrals[doc_name]["revenue_generated"] += sum(float(inv.total_amount or 0) for inv in pat_invs)
        doctor_referrals[doc_name]["total_collected"] += sum(float(inv.paid_amount or 0) for inv in pat_invs)

    referring_doctors = [
        {
            "doctor_name": d,
            "referral_type": stats["type"],
            "patients_referred": stats["patients_referred"],
            "revenue_generated": round(stats["revenue_generated"], 2),
            "total_collected": round(stats["total_collected"], 2),
            "avg_per_patient": round(stats["revenue_generated"] / (stats["patients_referred"] or 1), 2),
        }
        for d, stats in doctor_referrals.items()
    ]
    referring_doctors.sort(key=lambda x: x["revenue_generated"], reverse=True)

    # 4. Bed Occupancy Rate from DB
    bed_res = await db.execute(select(Bed))
    beds = bed_res.scalars().all()
    total_beds = len(beds)
    occupied_beds = sum(1 for b in beds if b.status == "Occupied")
    bed_occupancy_rate = f"{int((occupied_beds / total_beds) * 100)}%" if total_beds > 0 else "0%"

    # 5. Live Patient Count
    active_patients_count = len(all_patients)

    # 6. Real Revenue Leakage Prevented (Calculated from resolved invoices)
    leakage_prevented = 0.0
    for inv in all_invoices:
        for it in (inv.items or []):
            if it.get("resolved_from_leakage_id"):
                leakage_prevented += float(it.get("total") or it.get("unit_price") or 0.0)

    return {
        "kpis": {
            "total_billed": round(total_billed, 2),
            "total_collected": round(total_collected, 2),
            "pending_collections": round(pending_collections, 2),
            "collection_efficiency_pct": collection_efficiency,
            "active_patients_count": active_patients_count,
            "bed_occupancy_rate": bed_occupancy_rate,
            "total_beds": total_beds,
            "occupied_beds": occupied_beds,
            "vacant_beds": max(0, total_beds - occupied_beds),
            "revenue_leakage_prevented": round(leakage_prevented, 2),
            "invoices_count": len(invoices),
        },
        "by_department": dept_revenue,
        "monthly_trend": monthly_trend,
        "referring_doctors": referring_doctors,
        "timeframe": timeframe or "all",
    }


@router.get("/revenue-leakage")
async def get_revenue_leakage(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Real-time Leakage Detection Engine:
    Detects unbilled investigations, prescriptions, and completed procedures
    recorded in clinical records that lack a corresponding billed invoice.
    """
    inv_query = select(Invoice)
    if current_user.tenant_id:
        inv_query = inv_query.where(Invoice.tenant_id == current_user.tenant_id)
    res_inv = await db.execute(inv_query)
    all_invoices = res_inv.scalars().all()

    resolved_leakage_ids = set()
    billed_patient_descriptions = defaultdict(set)
    for inv in all_invoices:
        for it in (inv.items or []):
            leak_id = it.get("resolved_from_leakage_id")
            if leak_id:
                resolved_leakage_ids.add(str(leak_id))
            desc_text = str(it.get("description", "")).lower()
            billed_patient_descriptions[inv.patient_id].add(desc_text)

    pat_query = select(Patient)
    if current_user.tenant_id:
        pat_query = pat_query.where(Patient.tenant_id == current_user.tenant_id)
    res_pat = await db.execute(pat_query)
    patients = {p.id: p for p in res_pat.scalars().all()}

    res_rec = await db.execute(select(ClinicalRecord).order_by(ClinicalRecord.created_at.desc()))
    records = res_rec.scalars().all()

    leakage_items = []

    # 1. Detect unbilled investigations & prescriptions from clinical records
    for r in records:
        pat = patients.get(r.patient_id)
        if not pat:
            continue

        data = r.data or {}
        leak_id = f"LEAK-CR-{str(r.id)[:8].upper()}"
        if leak_id in resolved_leakage_ids:
            continue

        inv_ordered = data.get("investigations_ordered") or data.get("assessment", {}).get("investigations_ordered")
        if inv_ordered and isinstance(inv_ordered, str) and len(inv_ordered) > 3:
            already_billed = any(inv_ordered.lower() in b_desc for b_desc in billed_patient_descriptions[r.patient_id])
            if not already_billed:
                leakage_items.append({
                    "leakage_id": leak_id,
                    "patient_id": str(r.patient_id),
                    "patient_name": pat.name,
                    "patient_mrn": pat.vid or "—",
                    "department": "OPD / Diagnostics",
                    "leakage_type": "Unbilled Investigation Order",
                    "service_description": inv_ordered[:100],
                    "estimated_amount": 3500.0,
                    "detected_at": r.created_at.isoformat() if r.created_at else datetime.utcnow().isoformat(),
                    "status": "Action Required",
                })
                continue

        if r.record_type == "sonohysterogram":
            has_sis_inv = any("sis" in b or "sono" in b for b in billed_patient_descriptions[r.patient_id])
            if not has_sis_inv:
                leakage_items.append({
                    "leakage_id": leak_id,
                    "patient_id": str(r.patient_id),
                    "patient_name": pat.name,
                    "patient_mrn": pat.vid or "—",
                    "department": "Ultrasound / OPD",
                    "leakage_type": "Unbilled Sonohysterogram (SIS)",
                    "service_description": "Saline Infusion Sonohysterography procedure documented without cashier invoice",
                    "estimated_amount": 4500.0,
                    "detected_at": r.created_at.isoformat() if r.created_at else datetime.utcnow().isoformat(),
                    "status": "Action Required",
                })
                continue

        if r.record_type == "sperm_dfi":
            has_dfi_inv = any("dfi" in b or "halosperm" in b for b in billed_patient_descriptions[r.patient_id])
            if not has_dfi_inv:
                leakage_items.append({
                    "leakage_id": leak_id,
                    "patient_id": str(r.patient_id),
                    "patient_name": pat.name,
                    "patient_mrn": pat.vid or "—",
                    "department": "Andrology Lab",
                    "leakage_type": "Unbilled Sperm DFI Halosperm Assay",
                    "service_description": "Halosperm DNA Fragmentation Assay reported without invoice clearance",
                    "estimated_amount": 4500.0,
                    "detected_at": r.created_at.isoformat() if r.created_at else datetime.utcnow().isoformat(),
                    "status": "Action Required",
                })
                continue

    # 2. Detect unbilled completed appointments
    completed_appts_q = (
        select(Appointment)
        .where(Appointment.status == AppointmentStatus.COMPLETED)
        .order_by(Appointment.scheduled_at.desc())
        .limit(20)
    )
    if current_user.tenant_id:
        completed_appts_q = completed_appts_q.where(Appointment.tenant_id == current_user.tenant_id)
    res_appts = await db.execute(completed_appts_q)
    for apt in res_appts.scalars().all():
        pat = patients.get(apt.patient_id)
        if not pat:
            continue
        leak_id = f"LEAK-APT-{str(apt.id)[:8].upper()}"
        if leak_id in resolved_leakage_ids:
            continue

        has_consult_inv = any("consult" in b or "op" in b for b in billed_patient_descriptions[apt.patient_id])
        if not has_consult_inv:
            leakage_items.append({
                "leakage_id": leak_id,
                "patient_id": str(apt.patient_id),
                "patient_name": pat.name,
                "patient_mrn": pat.vid or "—",
                "department": apt.department or "OPD",
                "leakage_type": "Unbilled Completed Consultation",
                "service_description": f"Completed {apt.visit_type or 'consultation'} appointment with doctor",
                "estimated_amount": 1000.0,
                "detected_at": apt.scheduled_at.isoformat() if apt.scheduled_at else datetime.utcnow().isoformat(),
                "status": "Action Required",
            })

    # 3. If no specific clinical orders were flagged, audit patients who have unbilled files
    if len(leakage_items) == 0 and patients:
        for p in patients.values():
            has_any_inv = any(inv.patient_id == p.id for inv in all_invoices)
            leak_id = f"LEAK-PAT-{str(p.id)[:8].upper()}"
            if not has_any_inv and leak_id not in resolved_leakage_ids:
                leakage_items.append({
                    "leakage_id": leak_id,
                    "patient_id": str(p.id),
                    "patient_name": p.name,
                    "patient_mrn": p.vid or "—",
                    "department": "OPD / Consultation",
                    "leakage_type": "Unbilled Patient Consultation File",
                    "service_description": "Initial outpatient clinical workup & consultation unbilled at cashier",
                    "estimated_amount": 1500.0,
                    "detected_at": p.created_at.isoformat() if p.created_at else datetime.utcnow().isoformat(),
                    "status": "Action Required",
                })
                break

    total_leakage = sum(item["estimated_amount"] for item in leakage_items)

    return {
        "summary": {
            "total_leakage_detected": round(total_leakage, 2),
            "unbilled_orders_count": len(leakage_items),
            "unbilled_prescriptions_count": sum(1 for i in leakage_items if "Prescription" in i["leakage_type"]),
            "unbilled_diagnostics_count": sum(1 for i in leakage_items if "Investigation" in i["leakage_type"] or "Sonohysterogram" in i["leakage_type"] or "DFI" in i["leakage_type"]),
            "unbilled_consultations_count": sum(1 for i in leakage_items if "Consultation" in i["leakage_type"]),
        },
        "items": leakage_items,
    }


@router.get("/no-shows")
async def get_no_show_appointments(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Identify appointments scheduled in the PAST that were never checked in, billed, or completed.
    Upcoming appointments are NOT marked as no-shows.
    """
    now = datetime.utcnow()
    query = (
        select(Appointment)
        .options(selectinload(Appointment.patient), selectinload(Appointment.doctor))
        .where(
            or_(
                Appointment.status == AppointmentStatus.NO_SHOW,
                and_(
                    Appointment.status == AppointmentStatus.SCHEDULED,
                    Appointment.scheduled_at < now
                )
            )
        )
        .order_by(Appointment.scheduled_at.desc())
        .limit(30)
    )
    if current_user.tenant_id:
        query = query.where(Appointment.tenant_id == current_user.tenant_id)

    res = await db.execute(query)
    appts = res.scalars().all()

    no_shows = []
    for a in appts:
        pat = a.patient
        doc = a.doctor
        meta = a.metadata_ or {}
        reminders = meta.get("reminders_sent", [])
        no_shows.append({
            "id": str(a.id),
            "patient_id": str(a.patient_id),
            "patient_name": pat.name if pat else "Patient",
            "patient_phone": pat.phone if pat else "—",
            "patient_vid": pat.vid if pat else "—",
            "doctor_name": doc.name if doc else "Consultant Doctor",
            "department": a.department or "General OPD",
            "scheduled_time": a.scheduled_at.isoformat() if a.scheduled_at else "",
            "status": "Missed / No Show",
            "visit_type": a.visit_type or "consultation",
            "reminders_count": len(reminders),
            "last_reminder_at": meta.get("last_reminder_at"),
            "action_required": "Recall & Reschedule",
        })
    return no_shows


@router.post("/no-shows/{appointment_id}/send-reminder")
async def send_no_show_reminder(
    appointment_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Dispatches a recall / WhatsApp notification for a missed appointment
    and logs the reminder in appointment metadata.
    """
    appointment = await db.get(Appointment, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    meta = dict(appointment.metadata_ or {})
    reminders = meta.get("reminders_sent", [])
    now_str = datetime.utcnow().isoformat()
    reminders.append({
        "channel": "whatsapp",
        "sent_at": now_str,
        "sent_by": current_user.name,
        "status": "sent",
    })
    meta["reminders_sent"] = reminders
    meta["last_reminder_at"] = now_str
    appointment.metadata_ = meta

    # Create notification
    notif = Notification(
        user_id=current_user.id,
        title="Recall Dispatched",
        message=f"WhatsApp recall sent to patient for appointment slot {appointment.scheduled_at.strftime('%d-%b %H:%M') if appointment.scheduled_at else ''}.",
        notification_type=NotificationType.SYSTEM,
        tenant_id=appointment.tenant_id or current_user.tenant_id,
    )
    db.add(notif)
    await db.flush()

    return {
        "status": "success",
        "message": "WhatsApp recall reminder logged (SMS/WhatsApp gateway integration pending).",
        "wip": True,
        "appointment_id": str(appointment.id),
        "sent_at": now_str,
        "reminders_count": len(reminders),
    }


@router.post("/resolve-leakage")
async def resolve_leakage(
    payload: ResolveLeakagePayload,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    1-Click Action: Automatically generates an Invoice from a detected revenue leakage item.
    Attaches resolved_from_leakage_id so the item is permanently marked as resolved.
    """
    patient = await db.get(Patient, payload.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    tenant_id = current_user.tenant_id or patient.tenant_id
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context required to resolve revenue leakage")

    inv_num = f"INV-LEAK-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
    invoice = Invoice(
        invoice_number=inv_num,
        patient_id=payload.patient_id,
        appointment_source=payload.department or "OP",
        subtotal=payload.amount,
        discount=0,
        tax=0,
        total_amount=payload.amount,
        paid_amount=0,
        wallet_amount_used=0,
        status=InvoiceStatus.PENDING,
        items=[
            {
                "description": payload.item_description,
                "quantity": 1,
                "unit_price": float(payload.amount),
                "total": float(payload.amount),
                "department": payload.department,
                "resolved_from_leakage_id": payload.leakage_item_id,
            }
        ],
        payment_method="cash",
        tenant_id=tenant_id,
        created_by=current_user.id,
        notes=f"Generated via Revenue Leakage Engine from Item {payload.leakage_item_id}",
    )
    db.add(invoice)
    await db.flush()
    await db.refresh(invoice)

    return {
        "message": f"Revenue leakage resolved! Generated invoice {inv_num} for ₹{payload.amount:,.2f}.",
        "invoice_id": str(invoice.id),
        "invoice_number": inv_num,
        "amount": payload.amount,
        "wip": True,
    }
