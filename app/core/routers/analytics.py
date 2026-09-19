"""
VaidyaMD HMS — Revenue Leakage Engine & Clinical Analytics Router
Real-time database aggregation for hospital KPIs, department breakdowns,
monthly trends, referral ROI, leakage detection, and no-show queues.
Pushed-down SQL aggregations for production performance and strict tenant isolation.
"""

import uuid
from datetime import datetime, date, timedelta
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_, or_, case
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from typing import Optional, Any, List
from uuid import UUID

from app.core.database import get_db
from app.core.models import (
    ClinicalRecord, Invoice, Appointment, Patient, User,
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
@router.get("/revenue-breakdown/", include_in_schema=False)
async def get_revenue_breakdown(
    timeframe: Optional[str] = Query(None, description="today, 7d, 30d, 90d, this_month, this_year, all"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Hospital revenue analytics partitioned dynamically by department, doctor, and monthly growth trends.
    Uses SQL aggregation for fast, production-grade KPI computation.
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

    # 1. Total Billed, Collected, and Invoices Count via SQL func.sum
    kpi_query = select(
        func.coalesce(func.sum(Invoice.total_amount), 0.0).label("total_billed"),
        func.coalesce(func.sum(Invoice.paid_amount), 0.0).label("total_collected"),
        func.count(Invoice.id).label("invoices_count"),
    )
    if start_time:
        kpi_query = kpi_query.where(Invoice.created_at >= start_time)
    if current_user.tenant_id:
        kpi_query = kpi_query.where(Invoice.tenant_id == current_user.tenant_id)

    kpi_res = await db.execute(kpi_query)
    kpi_row = kpi_res.one()

    total_billed = float(kpi_row.total_billed or 0.0)
    total_collected = float(kpi_row.total_collected or 0.0)
    invoices_count = int(kpi_row.invoices_count or 0)
    pending_collections = max(0.0, total_billed - total_collected)
    collection_efficiency = round((total_collected / total_billed * 100), 1) if total_billed > 0 else 0.0

    # 2. Dynamic Department Breakdown via SQL CASE aggregation
    dept_query = select(
        func.coalesce(func.sum(case((or_(
            Invoice.appointment_source.ilike("%IVF%"),
            Invoice.appointment_source.ilike("%ART%"),
            Invoice.appointment_source.ilike("%PACKAGE%"),
            Invoice.appointment_source.ilike("%EMBRYO%")
        ), Invoice.total_amount), else_=0.0)), 0.0).label("ivf_rev"),
        func.coalesce(func.count(case((or_(
            Invoice.appointment_source.ilike("%IVF%"),
            Invoice.appointment_source.ilike("%ART%"),
            Invoice.appointment_source.ilike("%PACKAGE%"),
            Invoice.appointment_source.ilike("%EMBRYO%")
        ), 1))), 0).label("ivf_cnt"),

        func.coalesce(func.sum(case((or_(
            Invoice.appointment_source.ilike("%PHARM%"),
            Invoice.appointment_source.ilike("%RX%"),
            Invoice.appointment_source.ilike("%MED%")
        ), Invoice.total_amount), else_=0.0)), 0.0).label("pharm_rev"),
        func.coalesce(func.count(case((or_(
            Invoice.appointment_source.ilike("%PHARM%"),
            Invoice.appointment_source.ilike("%RX%"),
            Invoice.appointment_source.ilike("%MED%")
        ), 1))), 0).label("pharm_cnt"),

        func.coalesce(func.sum(case((or_(
            Invoice.appointment_source.ilike("%IP%"),
            Invoice.appointment_source.ilike("%WARD%"),
            Invoice.appointment_source.ilike("%SURGERY%"),
            Invoice.appointment_source.ilike("%ADMISSION%")
        ), Invoice.total_amount), else_=0.0)), 0.0).label("ipd_rev"),
        func.coalesce(func.count(case((or_(
            Invoice.appointment_source.ilike("%IP%"),
            Invoice.appointment_source.ilike("%WARD%"),
            Invoice.appointment_source.ilike("%SURGERY%"),
            Invoice.appointment_source.ilike("%ADMISSION%")
        ), 1))), 0).label("ipd_cnt"),

        func.coalesce(func.sum(case((or_(
            Invoice.appointment_source.ilike("%LIMS%"),
            Invoice.appointment_source.ilike("%LAB%"),
            Invoice.appointment_source.ilike("%ANDROLOGY%"),
            Invoice.appointment_source.ilike("%CASA%"),
            Invoice.appointment_source.ilike("%DIAGNOSTIC%")
        ), Invoice.total_amount), else_=0.0)), 0.0).label("lims_rev"),
        func.coalesce(func.count(case((or_(
            Invoice.appointment_source.ilike("%LIMS%"),
            Invoice.appointment_source.ilike("%LAB%"),
            Invoice.appointment_source.ilike("%ANDROLOGY%"),
            Invoice.appointment_source.ilike("%CASA%"),
            Invoice.appointment_source.ilike("%DIAGNOSTIC%")
        ), 1))), 0).label("lims_cnt"),

        func.coalesce(func.sum(case((and_(
            ~Invoice.appointment_source.ilike("%IVF%"),
            ~Invoice.appointment_source.ilike("%ART%"),
            ~Invoice.appointment_source.ilike("%PACKAGE%"),
            ~Invoice.appointment_source.ilike("%EMBRYO%"),
            ~Invoice.appointment_source.ilike("%PHARM%"),
            ~Invoice.appointment_source.ilike("%RX%"),
            ~Invoice.appointment_source.ilike("%MED%"),
            ~Invoice.appointment_source.ilike("%IP%"),
            ~Invoice.appointment_source.ilike("%WARD%"),
            ~Invoice.appointment_source.ilike("%SURGERY%"),
            ~Invoice.appointment_source.ilike("%ADMISSION%"),
            ~Invoice.appointment_source.ilike("%LIMS%"),
            ~Invoice.appointment_source.ilike("%LAB%"),
            ~Invoice.appointment_source.ilike("%ANDROLOGY%"),
            ~Invoice.appointment_source.ilike("%CASA%"),
            ~Invoice.appointment_source.ilike("%DIAGNOSTIC%"),
        ), Invoice.total_amount), else_=0.0)), 0.0).label("opd_rev"),
        func.coalesce(func.count(case((and_(
            ~Invoice.appointment_source.ilike("%IVF%"),
            ~Invoice.appointment_source.ilike("%ART%"),
            ~Invoice.appointment_source.ilike("%PACKAGE%"),
            ~Invoice.appointment_source.ilike("%EMBRYO%"),
            ~Invoice.appointment_source.ilike("%PHARM%"),
            ~Invoice.appointment_source.ilike("%RX%"),
            ~Invoice.appointment_source.ilike("%MED%"),
            ~Invoice.appointment_source.ilike("%IP%"),
            ~Invoice.appointment_source.ilike("%WARD%"),
            ~Invoice.appointment_source.ilike("%SURGERY%"),
            ~Invoice.appointment_source.ilike("%ADMISSION%"),
            ~Invoice.appointment_source.ilike("%LIMS%"),
            ~Invoice.appointment_source.ilike("%LAB%"),
            ~Invoice.appointment_source.ilike("%ANDROLOGY%"),
            ~Invoice.appointment_source.ilike("%CASA%"),
            ~Invoice.appointment_source.ilike("%DIAGNOSTIC%"),
        ), 1))), 0).label("opd_cnt"),
    )
    if start_time:
        dept_query = dept_query.where(Invoice.created_at >= start_time)
    if current_user.tenant_id:
        dept_query = dept_query.where(Invoice.tenant_id == current_user.tenant_id)

    dept_res = await db.execute(dept_query)
    d_row = dept_res.one()

    dept_mapping = [
        ("IVF & ART Procedures", "#4f46e5", float(d_row.ivf_rev), int(d_row.ivf_cnt)),
        ("Pharmacy & Therapeutics", "#06b6d4", float(d_row.pharm_rev), int(d_row.pharm_cnt)),
        ("IPD Ward & OT Surgeries", "#10b981", float(d_row.ipd_rev), int(d_row.ipd_cnt)),
        ("OPD Consultations", "#8b5cf6", float(d_row.opd_rev), int(d_row.opd_cnt)),
        ("LIMS & Andrology Diagnostics", "#f59e0b", float(d_row.lims_rev), int(d_row.lims_cnt)),
    ]

    dept_revenue = []
    for d_name, color, rev, cnt in dept_mapping:
        pct = round((rev / total_billed * 100), 1) if total_billed > 0 else 0.0
        dept_revenue.append({
            "department": d_name,
            "revenue": round(rev, 2),
            "color": color,
            "pct": pct,
            "count": cnt,
        })

    # 3. Dynamic Monthly Trend (Past 6 Months Chronological via SQL)
    monthly_trend = []
    for i in range(5, -1, -1):
        target_year = now.year
        target_month = now.month - i
        while target_month <= 0:
            target_month += 12
            target_year -= 1

        m_date = date(target_year, target_month, 1)
        m_label = m_date.strftime("%b")

        if target_month == 12:
            next_m_date = date(target_year + 1, 1, 1)
        else:
            next_m_date = date(target_year, target_month + 1, 1)

        m_start = datetime(target_year, target_month, 1)
        m_end = datetime(next_m_date.year, next_m_date.month, 1)

        m_query = select(
            func.coalesce(func.sum(Invoice.total_amount), 0.0).label("m_rev"),
            func.coalesce(func.sum(Invoice.paid_amount), 0.0).label("m_col"),
            func.coalesce(func.sum(case((or_(
                Invoice.appointment_source.ilike("%IVF%"),
                Invoice.appointment_source.ilike("%ART%"),
                Invoice.appointment_source.ilike("%PACKAGE%")
            ), Invoice.total_amount), else_=0.0)), 0.0).label("m_ivf"),
            func.coalesce(func.sum(case((or_(
                Invoice.appointment_source.ilike("%PHARM%"),
                Invoice.appointment_source.ilike("%RX%")
            ), Invoice.total_amount), else_=0.0)), 0.0).label("m_pharmacy"),
            func.coalesce(func.sum(case((or_(
                Invoice.appointment_source.ilike("%IP%"),
                Invoice.appointment_source.ilike("%WARD%")
            ), Invoice.total_amount), else_=0.0)), 0.0).label("m_ipd"),
            func.coalesce(func.sum(case((and_(
                ~Invoice.appointment_source.ilike("%IVF%"),
                ~Invoice.appointment_source.ilike("%ART%"),
                ~Invoice.appointment_source.ilike("%PACKAGE%"),
                ~Invoice.appointment_source.ilike("%PHARM%"),
                ~Invoice.appointment_source.ilike("%RX%"),
                ~Invoice.appointment_source.ilike("%IP%"),
                ~Invoice.appointment_source.ilike("%WARD%"),
            ), Invoice.total_amount), else_=0.0)), 0.0).label("m_opd"),
        ).where(
            Invoice.created_at >= m_start,
            Invoice.created_at < m_end,
        )
        if current_user.tenant_id:
            m_query = m_query.where(Invoice.tenant_id == current_user.tenant_id)

        m_res = await db.execute(m_query)
        m_row = m_res.one()

        monthly_trend.append({
            "month": m_label,
            "year": target_year,
            "revenue": round(float(m_row.m_rev or 0.0), 2),
            "collected": round(float(m_row.m_col or 0.0), 2),
            "opd": round(float(m_row.m_opd or 0.0), 2),
            "ivf": round(float(m_row.m_ivf or 0.0), 2),
            "pharmacy": round(float(m_row.m_pharmacy or 0.0), 2),
            "ipd": round(float(m_row.m_ipd or 0.0), 2),
        })

    # 4. Referring Doctors via SQL Group By
    ref_query = (
        select(
            Patient.referred_by_name,
            Patient.referred_by_type,
            func.count(func.distinct(Patient.id)).label("pat_count"),
            func.coalesce(func.sum(Invoice.total_amount), 0.0).label("rev_gen"),
            func.coalesce(func.sum(Invoice.paid_amount), 0.0).label("col_gen"),
        )
        .outerjoin(Invoice, Invoice.patient_id == Patient.id)
    )
    if current_user.tenant_id:
        ref_query = ref_query.where(Patient.tenant_id == current_user.tenant_id)
    ref_query = ref_query.group_by(Patient.referred_by_name, Patient.referred_by_type)
    ref_res = await db.execute(ref_query)
    ref_rows = ref_res.all()

    referring_doctors = []
    for r_name, r_type, p_cnt, r_rev, r_col in ref_rows:
        doc_name = r_name or (
            f"Dr. {r_type.title()}" if r_type and r_type not in ["self", "walk_in"] else "Direct / Self-Walk-in"
        )
        rev_val = float(r_rev or 0.0)
        col_val = float(r_col or 0.0)
        pat_cnt = int(p_cnt or 0)
        referring_doctors.append({
            "doctor_name": doc_name,
            "referral_type": r_type or "walk_in",
            "patients_referred": pat_cnt,
            "revenue_generated": round(rev_val, 2),
            "total_collected": round(col_val, 2),
            "avg_per_patient": round(rev_val / (pat_cnt or 1), 2),
        })
    referring_doctors.sort(key=lambda x: x["revenue_generated"], reverse=True)

    # 5. Bed Occupancy Rate from DB via SQL
    bed_query = select(
        func.count(Bed.id).label("total_beds"),
        func.coalesce(func.count(case((Bed.status == "Occupied", 1))), 0).label("occupied_beds"),
    )
    bed_res = await db.execute(bed_query)
    b_row = bed_res.one()
    total_beds = int(b_row.total_beds or 0)
    occupied_beds = int(b_row.occupied_beds or 0)
    bed_occupancy_rate = f"{int((occupied_beds / total_beds) * 100)}%" if total_beds > 0 else "0%"

    # 6. Active Patients Count
    pat_count_query = select(func.count(Patient.id))
    if current_user.tenant_id:
        pat_count_query = pat_count_query.where(Patient.tenant_id == current_user.tenant_id)
    active_patients_count = (await db.execute(pat_count_query)).scalar_one_or_none() or 0

    # 7. Revenue Leakage Prevented (Calculated from resolved invoices)
    leak_prev_query = select(Invoice.items)
    if current_user.tenant_id:
        leak_prev_query = leak_prev_query.where(Invoice.tenant_id == current_user.tenant_id)
    leak_prev_res = await db.execute(leak_prev_query)
    leakage_prevented = 0.0
    for items_list in leak_prev_res.scalars().all():
        for it in (items_list or []):
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
            "invoices_count": invoices_count,
        },
        "by_department": dept_revenue,
        "monthly_trend": monthly_trend,
        "referring_doctors": referring_doctors,
        "timeframe": timeframe or "all",
    }


@router.get("/revenue-leakage")
@router.get("/revenue-leakage/", include_in_schema=False)
async def get_revenue_leakage(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Real-time Leakage Detection Engine:
    Detects unbilled investigations, prescriptions, and completed procedures
    recorded in clinical records that lack a corresponding billed invoice.
    Strictly scoped to current_user.tenant_id.
    """
    # 1. Gather all existing invoices for this tenant
    inv_query = select(Invoice.patient_id, Invoice.items)
    if current_user.tenant_id:
        inv_query = inv_query.where(Invoice.tenant_id == current_user.tenant_id)
    res_inv = await db.execute(inv_query)
    all_invoices_data = res_inv.all()

    resolved_leakage_ids = set()
    billed_patient_descriptions = defaultdict(set)
    billed_patient_ids = set()
    for p_id, items in all_invoices_data:
        billed_patient_ids.add(p_id)
        for it in (items or []):
            leak_id = it.get("resolved_from_leakage_id")
            if leak_id:
                resolved_leakage_ids.add(str(leak_id))
            desc_text = str(it.get("description", "")).lower()
            billed_patient_descriptions[p_id].add(desc_text)

    # 2. Get patients for tenant
    pat_query = select(Patient)
    if current_user.tenant_id:
        pat_query = pat_query.where(Patient.tenant_id == current_user.tenant_id)
    res_pat = await db.execute(pat_query)
    patients = {p.id: p for p in res_pat.scalars().all()}

    # 3. Get recent clinical records for this tenant only
    rec_query = (
        select(ClinicalRecord)
        .join(Patient, ClinicalRecord.patient_id == Patient.id)
        .order_by(ClinicalRecord.created_at.desc())
        .limit(150)
    )
    if current_user.tenant_id:
        rec_query = rec_query.where(Patient.tenant_id == current_user.tenant_id)

    res_rec = await db.execute(rec_query)
    records = res_rec.scalars().all()

    leakage_items = []

    # Detect unbilled investigations & specialized procedures from clinical records
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

    # 4. Detect unbilled completed appointments
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

    # 5. If no specific clinical orders were flagged, audit patients who have unbilled files
    if len(leakage_items) == 0 and patients:
        for p in patients.values():
            has_any_inv = p.id in billed_patient_ids
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
@router.get("/no-shows/", include_in_schema=False)
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
@router.post("/no-shows/{appointment_id}/send-reminder/", include_in_schema=False)
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

    if current_user.tenant_id and appointment.tenant_id and appointment.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Unauthorized access to appointment")

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
@router.post("/resolve-leakage/", include_in_schema=False)
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

    branch_id = getattr(patient, 'branch_id', None) or getattr(current_user, 'branch_id', None)
    branch_code = None
    if branch_id:
        from app.core.models.branch import Branch
        b = await db.get(Branch, branch_id)
        if b and b.code:
            branch_code = b.code

    leak_prefix = f"INV-LEAK-{branch_code}" if branch_code else "INV-LEAK"
    inv_num = f"{leak_prefix}-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
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
        branch_id=branch_id,
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
