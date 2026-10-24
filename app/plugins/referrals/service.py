"""
VaidyaMD HMS — Referral & Commission Domain Service
Includes Master Directory, 3-Level Grouping Hierarchy, and Settlement Payouts.
"""

import uuid
from datetime import datetime, date
from typing import List, Optional, Dict, Any, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, and_, desc, func
from sqlalchemy.orm import selectinload

import app.core.models
from app.modules.patients.model import Patient
from app.modules.billing.model import Invoice, InvoiceStatus
from app.plugins.fertility.models import TreatmentCycle
from app.plugins.referrals.models import (
    ReferralCommissionConfig,
    ReferringDoctor,
    ReferralSettlement,
)
from app.plugins.referrals.schemas import (
    DepartmentBreakdown,
    ReferralInvoiceReportItem,
    PatientReferralCardItem,
    DoctorDirectoryItem,
    DoctorHierarchyDetailResponse,
    ReferringDoctorCreate,
    ReferringDoctorResponse,
    ReferralSettlementCreate,
    ReferralSettlementResponse,
    DoctorSummaryItem,
    ReferralSummaryResponse,
    HospitalReferralOverviewResponse,
    CommissionConfigSchema,
)


class ReferralsService:

    @staticmethod
    async def get_commission_config(db: AsyncSession, tenant_id: uuid.UUID) -> CommissionConfigSchema:
        stmt = select(ReferralCommissionConfig).where(ReferralCommissionConfig.tenant_id == tenant_id)
        res = await db.execute(stmt)
        cfg = res.scalar_one_or_none()
        if not cfg:
            return CommissionConfigSchema()
        return CommissionConfigSchema.model_validate(cfg)

    @staticmethod
    async def save_commission_config(
        db: AsyncSession, tenant_id: uuid.UUID, data: CommissionConfigSchema
    ) -> CommissionConfigSchema:
        stmt = select(ReferralCommissionConfig).where(ReferralCommissionConfig.tenant_id == tenant_id)
        res = await db.execute(stmt)
        cfg = res.scalar_one_or_none()
        if not cfg:
            cfg = ReferralCommissionConfig(
                tenant_id=tenant_id,
                opd_pct=data.opd_pct,
                pharmacy_pct=data.pharmacy_pct,
                iui_pct=data.iui_pct,
                embryology_pct=data.embryology_pct,
                lims_pct=data.lims_pct,
                ipd_pct=data.ipd_pct,
                other_pct=data.other_pct,
            )
            db.add(cfg)
        else:
            cfg.opd_pct = data.opd_pct
            cfg.pharmacy_pct = data.pharmacy_pct
            cfg.iui_pct = data.iui_pct
            cfg.embryology_pct = data.embryology_pct
            cfg.lims_pct = data.lims_pct
            cfg.ipd_pct = data.ipd_pct
            cfg.other_pct = data.other_pct
            cfg.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(cfg)
        return CommissionConfigSchema.model_validate(cfg)

    @staticmethod
    def classify_line_item(item: Dict[str, Any], invoice_source: str) -> str:
        desc_text = (
            item.get("description")
            or item.get("item_name")
            or item.get("name")
            or ""
        ).lower()
        src = (invoice_source or "").lower()

        # 1. Embryology & IVF Lab
        embryology_keywords = [
            "icsi", "opu", "oocyte", "egg retrieval", "embryo", "blastocyst",
            "pgt", "cryo", "freez", "thaw", "hatching", "incubator",
            "fertility", "ivf lab", "sperm prep", "dual witness"
        ]
        if any(k in desc_text for k in embryology_keywords):
            return "embryology"

        # 2. IUI
        if "iui" in desc_text or "insemination" in desc_text or "semen wash" in desc_text:
            return "iui"

        # 3. Pharmacy
        pharma_keywords = [
            "tablet", "capsule", "syrup", "injection", "inj.", "vial", "mg",
            "gel", "suppository", "cream", "saline", "medication", "pharmacy"
        ]
        if src == "pharmacy" or any(k in desc_text for k in pharma_keywords):
            return "pharmacy"

        # 4. LIMS / Diagnostics / Pathology
        lims_keywords = [
            "blood", "serum", "assay", "panel", "test", "scan", "usg",
            "ultrasound", "follicular", "amh", "beta hcg", "hcg", "tsh",
            "prolactin", "estradiol", "semen analysis", "pathology", "lims", "culture"
        ]
        if src == "lims" or any(k in desc_text for k in lims_keywords):
            return "lims"

        # 5. IPD / Daycare / OT / CosGyn Procedures
        ipd_keywords = [
            "surgery", "ot ", "operation", "bed", "ward", "nursing", "room",
            "laparoscopy", "hysteroscopy", "daycare", "admission", "tesla chair",
            "jet plasma", "cosgyn", "prp"
        ]
        if src in ("ipd", "cosgyn") or any(k in desc_text for k in ipd_keywords):
            return "ipd"

        # 6. OPD Consultations
        opd_keywords = ["consult", "opd", "review", "registration", "visit", "appointment"]
        if src == "opd" or any(k in desc_text for k in opd_keywords):
            return "opd"

        # Fallback to source
        if src == "pharmacy":
            return "pharmacy"
        if src == "lims":
            return "lims"
        if src in ("ipd", "cosgyn"):
            return "ipd"
        return "other"

    @staticmethod
    def calculate_subsections(items: List[Dict[str, Any]], invoice_source: str) -> DepartmentBreakdown:
        breakdown = {
            "opd": 0.0,
            "pharmacy": 0.0,
            "iui": 0.0,
            "embryology": 0.0,
            "lims": 0.0,
            "ipd": 0.0,
            "other": 0.0,
        }

        if not items:
            src = (invoice_source or "").lower()
            if src == "pharmacy":
                breakdown["pharmacy"] = 1.0
            elif src == "lims":
                breakdown["lims"] = 1.0
            elif src in ("ipd", "cosgyn"):
                breakdown["ipd"] = 1.0
            else:
                breakdown["opd"] = 1.0
            return DepartmentBreakdown(**breakdown)

        for it in items:
            cat = ReferralsService.classify_line_item(it, invoice_source)
            qty = float(it.get("quantity") or it.get("quantity_dispensed") or 1)
            unit_p = float(it.get("unit_price") or it.get("unitPrice") or it.get("rate") or it.get("price") or 0)
            tot = float(it.get("total") or it.get("total_price") or it.get("amount") or (qty * unit_p))
            if cat in breakdown:
                breakdown[cat] += tot
            else:
                breakdown["other"] += tot

        return DepartmentBreakdown(**{k: round(v, 2) for k, v in breakdown.items()})

    @staticmethod
    def calculate_commission(
        breakdown: DepartmentBreakdown,
        cfg: CommissionConfigSchema,
        custom_pct: Optional[float] = None
    ) -> float:
        if custom_pct is not None and custom_pct > 0:
            tot = sum(
                [breakdown.opd, breakdown.pharmacy, breakdown.iui, breakdown.embryology, breakdown.lims, breakdown.ipd, breakdown.other]
            )
            return round((tot * custom_pct) / 100.0, 2)

        comm = (
            (breakdown.opd * cfg.opd_pct)
            + (breakdown.pharmacy * cfg.pharmacy_pct)
            + (breakdown.iui * cfg.iui_pct)
            + (breakdown.embryology * cfg.embryology_pct)
            + (breakdown.lims * cfg.lims_pct)
            + (breakdown.ipd * cfg.ipd_pct)
            + (breakdown.other * cfg.other_pct)
        ) / 100.0
        return round(comm, 2)

    # ─────────────────────────────────────────────────────────────
    # LEVEL 1: Referring Doctor Directory
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    async def get_doctors_directory(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        search: Optional[str] = None,
        filter_type: Optional[str] = None,  # "all", "unsettled", "settled"
        branch_id: Optional[uuid.UUID] = None,
    ) -> List[DoctorDirectoryItem]:
        cfg = await ReferralsService.get_commission_config(db, tenant_id)

        # 1. Fetch saved doctor profiles
        doc_prof_stmt = select(ReferringDoctor).where(ReferringDoctor.tenant_id == tenant_id)
        doc_prof_res = await db.execute(doc_prof_stmt)
        saved_profiles = {d.name.strip().lower(): d for d in doc_prof_res.scalars().all()}

        # 2. Fetch settlements to know which invoices are settled
        settle_stmt = select(ReferralSettlement).where(ReferralSettlement.tenant_id == tenant_id)
        settle_res = await db.execute(settle_stmt)
        all_settlements = settle_res.scalars().all()
        settled_invoice_map: Dict[str, ReferralSettlement] = {}
        for s in all_settlements:
            for inv_id in (s.invoice_ids or []):
                settled_invoice_map[str(inv_id)] = s

        # 3. Fetch all patients with referring doctors
        pat_stmt = (
            select(Patient)
            .where(
                Patient.tenant_id == tenant_id,
                or_(
                    Patient.referring_doctor.isnot(None),
                    Patient.referred_by_name.isnot(None),
                )
            )
            .options(selectinload(Patient.invoices))
        )
        if branch_id:
            pat_stmt = pat_stmt.where(Patient.branch_id == branch_id)

        pat_res = await db.execute(pat_stmt)
        patients = pat_res.scalars().all()

        # Check which patients have treatment cycles
        pat_ids = [p.id for p in patients]
        cycle_patients: Set[uuid.UUID] = set()
        if pat_ids:
            cycle_stmt = select(TreatmentCycle.patient_id).where(
                TreatmentCycle.tenant_id == tenant_id,
                TreatmentCycle.patient_id.in_(pat_ids)
            )
            c_res = await db.execute(cycle_stmt)
            cycle_patients = set(c_res.scalars().all())

        # Group stats by doctor name
        grouped: Dict[str, Dict[str, Any]] = {}

        # Pre-seed with saved profiles
        for doc_l_name, prof in saved_profiles.items():
            display_name = prof.name
            grouped[display_name] = {
                "profile": prof,
                "patients": set(),
                "converted_patients": set(),
                "invoices": 0,
                "revenue": 0.0,
                "paid": 0.0,
                "due": 0.0,
                "commission": 0.0,
                "settled_comm": 0.0,
                "pending_comm": 0.0,
            }

        for p in patients:
            doc_name = (p.referring_doctor or p.referred_by_name or "").strip()
            if not doc_name:
                continue

            # Find matching profile key
            prof = saved_profiles.get(doc_name.lower())
            key_name = prof.name if prof else doc_name

            if key_name not in grouped:
                grouped[key_name] = {
                    "profile": prof,
                    "patients": set(),
                    "converted_patients": set(),
                    "invoices": 0,
                    "revenue": 0.0,
                    "paid": 0.0,
                    "due": 0.0,
                    "commission": 0.0,
                    "settled_comm": 0.0,
                    "pending_comm": 0.0,
                }

            grouped[key_name]["patients"].add(p.id)
            if p.id in cycle_patients:
                grouped[key_name]["converted_patients"].add(p.id)

            custom_override = prof.custom_commission_pct if prof else None

            for inv in (p.invoices or []):
                if inv.status == InvoiceStatus.CANCELLED:
                    continue

                items_list = inv.items if isinstance(inv.items, list) else []
                breakdown = ReferralsService.calculate_subsections(items_list, inv.source_module or "")
                comm_amt = ReferralsService.calculate_commission(breakdown, cfg, custom_override)

                if breakdown.embryology > 0 or breakdown.iui > 0 or breakdown.ipd > 0:
                    grouped[key_name]["converted_patients"].add(p.id)

                net_t = float(inv.total_amount or 0)
                paid_t = float(inv.paid_amount or 0)
                due_t = max(0.0, net_t - paid_t)

                grouped[key_name]["invoices"] += 1
                grouped[key_name]["revenue"] += net_t
                grouped[key_name]["paid"] += paid_t
                grouped[key_name]["due"] += due_t
                grouped[key_name]["commission"] += comm_amt

                if str(inv.id) in settled_invoice_map:
                    grouped[key_name]["settled_comm"] += comm_amt
                else:
                    grouped[key_name]["pending_comm"] += comm_amt

        results: List[DoctorDirectoryItem] = []
        for d_name, d_val in grouped.items():
            if search:
                s_low = search.lower()
                clinic = (d_val["profile"].clinic_name or "") if d_val["profile"] else ""
                phone = (d_val["profile"].phone or "") if d_val["profile"] else ""
                if s_low not in d_name.lower() and s_low not in clinic.lower() and s_low not in phone.lower():
                    continue

            pending_c = round(d_val["pending_comm"], 2)
            settled_c = round(d_val["settled_comm"], 2)
            has_unsettled = pending_c > 0

            if filter_type == "unsettled" and not has_unsettled:
                continue
            if filter_type == "settled" and (has_unsettled or settled_c <= 0):
                continue

            prof_schema = (
                ReferringDoctorResponse.model_validate(d_val["profile"])
                if d_val["profile"]
                else None
            )

            p_count = len(d_val["patients"])
            c_count = len(d_val["converted_patients"])
            c_rate = round((c_count / p_count * 100.0), 1) if p_count > 0 else 0.0

            results.append(
                DoctorDirectoryItem(
                    doctor_name=d_name,
                    doctor_profile=prof_schema,
                    patient_count=p_count,
                    invoice_count=d_val["invoices"],
                    total_revenue=round(d_val["revenue"], 2),
                    total_paid=round(d_val["paid"], 2),
                    total_due=round(d_val["due"], 2),
                    total_commission=round(d_val["commission"], 2),
                    settled_commission=settled_c,
                    pending_commission=pending_c,
                    has_unsettled=has_unsettled,
                    converted_count=c_count,
                    conversion_rate_pct=c_rate,
                )
            )

        # Sort by pending commission desc, then total revenue desc
        results.sort(key=lambda d: (d.pending_commission, d.total_revenue), reverse=True)
        return results

    # ─────────────────────────────────────────────────────────────
    # EXECUTIVE OVERVIEW: Hospital-Wide Referral Metrics & Performance
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    async def get_hospital_overview(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        branch_id: Optional[uuid.UUID] = None,
    ) -> HospitalReferralOverviewResponse:
        docs = await ReferralsService.get_doctors_directory(db, tenant_id, branch_id=branch_id)

        # Departmental totals
        dept_totals = {"opd": 0.0, "pharmacy": 0.0, "iui": 0.0, "embryology": 0.0, "lims": 0.0, "ipd": 0.0, "other": 0.0}
        unique_patients: Set[uuid.UUID] = set()
        converted_patients: Set[uuid.UUID] = set()

        pat_stmt = (
            select(Patient)
            .where(
                Patient.tenant_id == tenant_id,
                or_(
                    Patient.referring_doctor.isnot(None),
                    Patient.referred_by_name.isnot(None),
                )
            )
            .options(selectinload(Patient.invoices))
        )
        if branch_id:
            pat_stmt = pat_stmt.where(Patient.branch_id == branch_id)
        pat_res = await db.execute(pat_stmt)
        patients = pat_res.scalars().all()

        pat_ids = [p.id for p in patients]
        cycle_patients: Set[uuid.UUID] = set()
        if pat_ids:
            cycle_stmt = select(TreatmentCycle.patient_id).where(
                TreatmentCycle.tenant_id == tenant_id,
                TreatmentCycle.patient_id.in_(pat_ids)
            )
            c_res = await db.execute(cycle_stmt)
            cycle_patients = set(c_res.scalars().all())

        for p in patients:
            unique_patients.add(p.id)
            if p.id in cycle_patients:
                converted_patients.add(p.id)
            for inv in (p.invoices or []):
                if inv.status == InvoiceStatus.CANCELLED:
                    continue
                items_list = inv.items if isinstance(inv.items, list) else []
                breakdown = ReferralsService.calculate_subsections(items_list, inv.source_module or "")
                dept_totals["opd"] += breakdown.opd
                dept_totals["pharmacy"] += breakdown.pharmacy
                dept_totals["iui"] += breakdown.iui
                dept_totals["embryology"] += breakdown.embryology
                dept_totals["lims"] += breakdown.lims
                dept_totals["ipd"] += breakdown.ipd
                dept_totals["other"] += breakdown.other
                if breakdown.embryology > 0 or breakdown.iui > 0 or breakdown.ipd > 0:
                    converted_patients.add(p.id)

        tot_rev = sum(d.total_revenue for d in docs)
        tot_paid = sum(d.total_paid for d in docs)
        tot_due = sum(d.total_due for d in docs)
        tot_comm = sum(d.total_commission for d in docs)
        tot_settled_comm = sum(d.settled_commission for d in docs)
        tot_pending_comm = sum(d.pending_commission for d in docs)
        tot_invoices = sum(d.invoice_count for d in docs)

        conv_pct = round((len(converted_patients) / len(unique_patients) * 100.0), 1) if unique_patients else 0.0

        settlements = await ReferralsService.get_settlements(db, tenant_id)

        return HospitalReferralOverviewResponse(
            total_referral_revenue=round(tot_rev, 2),
            total_paid=round(tot_paid, 2),
            total_due=round(tot_due, 2),
            total_commission=round(tot_comm, 2),
            settled_commission=round(tot_settled_comm, 2),
            pending_commission=round(tot_pending_comm, 2),
            total_patients_count=len(unique_patients),
            total_invoices_count=tot_invoices,
            converted_cycles_count=len(converted_patients),
            conversion_rate_pct=conv_pct,
            active_referring_doctors_count=len(docs),
            departmental_totals=DepartmentBreakdown(**{k: round(v, 2) for k, v in dept_totals.items()}),
            doctors_league=docs,
            recent_settlements=settlements[:10],
        )

    # ─────────────────────────────────────────────────────────────
    # LEVEL 2 & 3: Master-Detail Hierarchy for a Selected Doctor
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    async def get_doctor_hierarchy_detail(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        doctor_name: str,
        branch_id: Optional[uuid.UUID] = None,
    ) -> DoctorHierarchyDetailResponse:
        cfg = await ReferralsService.get_commission_config(db, tenant_id)

        # Doctor profile
        doc_prof_stmt = select(ReferringDoctor).where(
            ReferringDoctor.tenant_id == tenant_id,
            func.lower(ReferringDoctor.name) == doctor_name.strip().lower()
        )
        doc_prof_res = await db.execute(doc_prof_stmt)
        prof = doc_prof_res.scalar_one_or_none()
        custom_override = prof.custom_commission_pct if prof else None

        # Doctor settlements
        settle_stmt = select(ReferralSettlement).where(
            ReferralSettlement.tenant_id == tenant_id,
            func.lower(ReferralSettlement.doctor_name) == doctor_name.strip().lower()
        ).order_by(ReferralSettlement.settlement_date.desc())
        settle_res = await db.execute(settle_stmt)
        doctor_settlements = settle_res.scalars().all()

        settled_invoice_map: Dict[str, ReferralSettlement] = {}
        for s in doctor_settlements:
            for inv_id in (s.invoice_ids or []):
                settled_invoice_map[str(inv_id)] = s

        # Patients referred by this doctor
        pat_stmt = (
            select(Patient)
            .where(
                Patient.tenant_id == tenant_id,
                or_(
                    func.lower(Patient.referring_doctor) == doctor_name.strip().lower(),
                    func.lower(Patient.referred_by_name) == doctor_name.strip().lower(),
                )
            )
            .options(
                selectinload(Patient.invoices),
                selectinload(Patient.treatment_cycles),
            )
        )
        if branch_id:
            pat_stmt = pat_stmt.where(Patient.branch_id == branch_id)

        pat_res = await db.execute(pat_stmt)
        patients = pat_res.scalars().all()

        patient_cards: List[PatientReferralCardItem] = []

        tot_rev = 0.0
        tot_paid = 0.0
        tot_due = 0.0
        tot_comm = 0.0
        settled_comm = 0.0
        pending_comm = 0.0

        dept_totals = {
            "opd": 0.0,
            "pharmacy": 0.0,
            "iui": 0.0,
            "embryology": 0.0,
            "lims": 0.0,
            "ipd": 0.0,
            "other": 0.0,
        }

        for p in patients:
            # Determine Protocol & Status
            protocol = "General Clinical Care"
            cycle_status = None
            conversion_badge = "OPD Consultation Only"

            if p.treatment_cycles:
                sorted_cycles = sorted(
                    p.treatment_cycles,
                    key=lambda c: (c.start_date or date.min, c.created_at or datetime.min),
                    reverse=True
                )
                if sorted_cycles:
                    c = sorted_cycles[0]
                    t_type = (c.treatment_type or "Fertility Protocol").replace("_", " ").upper()
                    protocol = t_type
                    cycle_status = c.status.value.capitalize() if hasattr(c.status, "value") else str(c.status)
                    if any(ivf_word in t_type.lower() for ivf_word in ["ivf", "icsi", "opu", "fet", "donor"]):
                        conversion_badge = "Converted to IVF Protocol"
                    elif "iui" in t_type.lower():
                        conversion_badge = "Converted to IUI Cycle"

            patient_invoices: List[ReferralInvoiceReportItem] = []
            pat_billed = 0.0
            pat_paid = 0.0
            pat_due = 0.0
            pat_comm = 0.0
            pat_settled_comm = 0.0
            pat_pending_comm = 0.0

            for inv in (p.invoices or []):
                if inv.status == InvoiceStatus.CANCELLED:
                    continue

                items_list = inv.items if isinstance(inv.items, list) else []
                breakdown = ReferralsService.calculate_subsections(items_list, inv.source_module or "")
                comm_amt = ReferralsService.calculate_commission(breakdown, cfg, custom_override)

                # Check if settled
                inv_id_str = str(inv.id)
                is_settled = inv_id_str in settled_invoice_map
                settlement_obj = settled_invoice_map.get(inv_id_str)

                # Protocol refinement from attendance or first line item
                item_protocol = protocol
                if item_protocol == "General Clinical Care":
                    if inv.reason_for_attendance:
                        item_protocol = inv.reason_for_attendance
                    elif items_list and len(items_list) > 0:
                        first_desc = items_list[0].get("description") or items_list[0].get("item_name")
                        if first_desc:
                            item_protocol = first_desc

                # If patient had no cycle but bill has procedural items
                if conversion_badge == "OPD Consultation Only":
                    if breakdown.embryology > 0 or breakdown.ipd > 0:
                        conversion_badge = "Procedural Treatment"
                    elif breakdown.iui > 0:
                        conversion_badge = "IUI Services"

                subtot = float(inv.subtotal if inv.subtotal is not None else inv.total_amount)
                disc = float(inv.discount or 0)
                r_off = float(inv.round_off or 0)
                net_t = float(inv.total_amount or 0)
                paid_t = float(inv.paid_amount or 0)
                due_t = max(0.0, net_t - paid_t)

                pat_billed += net_t
                pat_paid += paid_t
                pat_due += due_t
                pat_comm += comm_amt

                if is_settled:
                    pat_settled_comm += comm_amt
                    settled_comm += comm_amt
                else:
                    pat_pending_comm += comm_amt
                    pending_comm += comm_amt

                dept_totals["opd"] += breakdown.opd
                dept_totals["pharmacy"] += breakdown.pharmacy
                dept_totals["iui"] += breakdown.iui
                dept_totals["embryology"] += breakdown.embryology
                dept_totals["lims"] += breakdown.lims
                dept_totals["ipd"] += breakdown.ipd
                dept_totals["other"] += breakdown.other

                patient_invoices.append(
                    ReferralInvoiceReportItem(
                        patient_id=p.id,
                        patient_name=p.name,
                        patient_vid=p.vid,
                        patient_mrn=getattr(p, "mrn", None),
                        patient_age=p.age,
                        patient_gender=p.gender.value if hasattr(p.gender, "value") else str(p.gender),
                        patient_phone=p.phone,
                        referring_doctor=doctor_name,
                        marketing_person=p.marketing_person_name,
                        treatment_protocol=item_protocol,
                        cycle_status=cycle_status,
                        invoice_id=inv.id,
                        invoice_number=inv.invoice_number,
                        invoice_date=inv.created_at,
                        invoice_status=inv.status.value if hasattr(inv.status, "value") else str(inv.status),
                        payment_method=inv.payment_method,
                        subsections=breakdown,
                        subtotal=round(subtot, 2),
                        discount=round(disc, 2),
                        round_off=round(r_off, 2),
                        net_total=round(net_t, 2),
                        paid_amount=round(paid_t, 2),
                        pending_due=round(due_t, 2),
                        commission_amount=comm_amt,
                        is_settled=is_settled,
                        settlement_number=settlement_obj.settlement_number if settlement_obj else None,
                        settlement_date=settlement_obj.settlement_date if settlement_obj else None,
                    )
                )

            patient_invoices.sort(key=lambda x: x.invoice_date, reverse=True)

            tot_rev += pat_billed
            tot_paid += pat_paid
            tot_due += pat_due
            tot_comm += pat_comm

            patient_cards.append(
                PatientReferralCardItem(
                    patient_id=p.id,
                    patient_name=p.name,
                    patient_vid=p.vid,
                    patient_mrn=getattr(p, "mrn", None),
                    patient_age=p.age,
                    patient_gender=p.gender.value if hasattr(p.gender, "value") else str(p.gender),
                    patient_phone=p.phone,
                    treatment_protocol=protocol,
                    cycle_status=cycle_status,
                    conversion_badge=conversion_badge,
                    total_billed=round(pat_billed, 2),
                    total_paid=round(pat_paid, 2),
                    total_due=round(pat_due, 2),
                    total_commission=round(pat_comm, 2),
                    settled_commission=round(pat_settled_comm, 2),
                    pending_commission=round(pat_pending_comm, 2),
                    invoices=patient_invoices,
                )
            )

        # Sort patients with most recent invoice first
        patient_cards.sort(
            key=lambda c: (c.invoices[0].invoice_date if c.invoices else datetime.min),
            reverse=True
        )

        return DoctorHierarchyDetailResponse(
            doctor_name=doctor_name,
            doctor_profile=ReferringDoctorResponse.model_validate(prof) if prof else None,
            total_patients_count=len(patient_cards),
            total_invoices_count=sum(len(c.invoices) for c in patient_cards),
            total_revenue=round(tot_rev, 2),
            total_paid=round(tot_paid, 2),
            total_due=round(tot_due, 2),
            total_commission=round(tot_comm, 2),
            settled_commission=round(settled_comm, 2),
            pending_commission=round(pending_comm, 2),
            departmental_totals=DepartmentBreakdown(**{k: round(v, 2) for k, v in dept_totals.items()}),
            patients=patient_cards,
            settlements=[ReferralSettlementResponse.model_validate(s) for s in doctor_settlements],
        )

    # ─────────────────────────────────────────────────────────────
    # Doctor Profile Management & Settlements
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    async def create_or_update_doctor_profile(
        db: AsyncSession, tenant_id: uuid.UUID, data: ReferringDoctorCreate
    ) -> ReferringDoctorResponse:
        stmt = select(ReferringDoctor).where(
            ReferringDoctor.tenant_id == tenant_id,
            func.lower(ReferringDoctor.name) == data.name.strip().lower()
        )
        res = await db.execute(stmt)
        existing = res.scalar_one_or_none()

        if not existing:
            existing = ReferringDoctor(
                tenant_id=tenant_id,
                name=data.name.strip(),
                clinic_name=data.clinic_name,
                specialty=data.specialty,
                phone=data.phone,
                email=data.email,
                address=data.address,
                bank_name=data.bank_name,
                account_number=data.account_number,
                ifsc_code=data.ifsc_code,
                upi_id=data.upi_id,
                pan_number=data.pan_number,
                custom_commission_pct=data.custom_commission_pct,
                notes=data.notes,
                is_active=data.is_active,
            )
            db.add(existing)
        else:
            existing.clinic_name = data.clinic_name
            existing.specialty = data.specialty
            existing.phone = data.phone
            existing.email = data.email
            existing.address = data.address
            existing.bank_name = data.bank_name
            existing.account_number = data.account_number
            existing.ifsc_code = data.ifsc_code
            existing.upi_id = data.upi_id
            existing.pan_number = data.pan_number
            existing.custom_commission_pct = data.custom_commission_pct
            existing.notes = data.notes
            existing.is_active = data.is_active
            existing.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(existing)
        return ReferringDoctorResponse.model_validate(existing)

    @staticmethod
    async def create_settlement(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: ReferralSettlementCreate,
    ) -> ReferralSettlementResponse:
        # Generate settlement number
        today_str = date.today().strftime("%Y%m%d")
        rand_suffix = str(uuid.uuid4().hex[:4]).upper()
        set_num = f"REF-SET-{today_str}-{rand_suffix}"

        # Link doctor_id if profile exists
        doc_prof_stmt = select(ReferringDoctor).where(
            ReferringDoctor.tenant_id == tenant_id,
            func.lower(ReferringDoctor.name) == payload.doctor_name.strip().lower()
        )
        doc_res = await db.execute(doc_prof_stmt)
        prof = doc_res.scalar_one_or_none()

        settlement = ReferralSettlement(
            settlement_number=set_num,
            tenant_id=tenant_id,
            doctor_name=payload.doctor_name.strip(),
            doctor_id=prof.id if prof else None,
            amount_paid=payload.amount_paid,
            payment_method=payload.payment_method,
            reference_number=payload.reference_number,
            settlement_date=payload.settlement_date or date.today(),
            notes=payload.notes,
            invoice_ids=payload.invoice_ids,
            created_by=user_id,
        )
        db.add(settlement)
        await db.commit()
        await db.refresh(settlement)
        return ReferralSettlementResponse.model_validate(settlement)

    @staticmethod
    async def get_settlements(
        db: AsyncSession, tenant_id: uuid.UUID, doctor_name: Optional[str] = None
    ) -> List[ReferralSettlementResponse]:
        query = select(ReferralSettlement).where(ReferralSettlement.tenant_id == tenant_id)
        if doctor_name:
            query = query.where(func.lower(ReferralSettlement.doctor_name) == doctor_name.strip().lower())
        query = query.order_by(ReferralSettlement.settlement_date.desc())
        res = await db.execute(query)
        rows = res.scalars().all()
        return [ReferralSettlementResponse.model_validate(r) for r in rows]
