"""
VaidyaMD HMS — Referral & Commission Plugin API Router
Comprehensive End-to-End Referral Management: Directory, Hierarchy, and Settlements.
"""

import io
import csv
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.database import get_db
from app.core.models.user import User
from app.core.dependencies import get_current_user, get_branch_context, require_active_plugin
from app.plugins.referrals.schemas import (
    DoctorDirectoryItem,
    DoctorHierarchyDetailResponse,
    ReferringDoctorCreate,
    ReferringDoctorResponse,
    ReferralSettlementCreate,
    ReferralSettlementResponse,
    ReferralInvoiceReportItem,
    ReferralSummaryResponse,
    HospitalReferralOverviewResponse,
    CommissionConfigSchema,
)
from app.plugins.referrals.service import ReferralsService

router = APIRouter(
    prefix="/referrals",
    tags=["referrals"],
    dependencies=[Depends(get_current_user), Depends(require_active_plugin("referrals"))],
)


@router.get("/overview", response_model=HospitalReferralOverviewResponse)
async def get_hospital_overview(
    branch_id: Optional[UUID] = Depends(get_branch_context),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Hospital-Level Executive Referral Overview: Total revenue, liability, conversion rates,
    departmental distribution, and doctor performance league table.
    """
    return await ReferralsService.get_hospital_overview(
        db=db,
        tenant_id=current_user.tenant_id,
        branch_id=branch_id,
    )


@router.get("/directory", response_model=List[DoctorDirectoryItem])
async def get_doctors_directory(
    search: Optional[str] = Query(None, description="Search doctor name, clinic, or phone"),
    filter_type: Optional[str] = Query(None, description="'all', 'unsettled', or 'settled'"),
    branch_id: Optional[UUID] = Depends(get_branch_context),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Level 1: Master Directory of Referring Doctors with patient counts, revenue, and settlement statuses.
    """
    return await ReferralsService.get_doctors_directory(
        db=db,
        tenant_id=current_user.tenant_id,
        search=search,
        filter_type=filter_type,
        branch_id=branch_id,
    )


@router.get("/doctor-detail", response_model=DoctorHierarchyDetailResponse)
async def get_doctor_hierarchy_detail(
    doctor_name: str = Query(..., description="Doctor or center name"),
    branch_id: Optional[UUID] = Depends(get_branch_context),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Level 2 & Level 3: Complete hierarchy for a selected doctor.
    Returns doctor profile, referred patients with treatment protocols & conversion badges,
    and all itemized bills with departmental breakdowns and settlement flags.
    """
    return await ReferralsService.get_doctor_hierarchy_detail(
        db=db,
        tenant_id=current_user.tenant_id,
        doctor_name=doctor_name,
        branch_id=branch_id,
    )


@router.post("/doctor-profile", response_model=ReferringDoctorResponse)
async def save_doctor_profile(
    payload: ReferringDoctorCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Save or update a referring doctor's profile, contact details, bank info, and custom commission override %.
    """
    return await ReferralsService.create_or_update_doctor_profile(
        db=db, tenant_id=current_user.tenant_id, data=payload
    )


@router.post("/settle", response_model=ReferralSettlementResponse)
async def record_commission_settlement(
    payload: ReferralSettlementCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Record a batch or individual commission settlement payment to a referring doctor.
    """
    return await ReferralsService.create_settlement(
        db=db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        payload=payload,
    )


@router.get("/settlements", response_model=List[ReferralSettlementResponse])
async def get_settlements_history(
    doctor_name: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get past commission settlement payouts history.
    """
    return await ReferralsService.get_settlements(
        db=db, tenant_id=current_user.tenant_id, doctor_name=doctor_name
    )


@router.get("/commission-settings", response_model=CommissionConfigSchema)
async def get_commission_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get hospital-wide default commission percentages per department.
    """
    return await ReferralsService.get_commission_config(db, current_user.tenant_id)


@router.post("/commission-settings", response_model=CommissionConfigSchema)
async def save_commission_settings(
    payload: CommissionConfigSchema,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update hospital-wide default commission percentages.
    """
    return await ReferralsService.save_commission_config(db, current_user.tenant_id, payload)


@router.get("/export")
async def export_doctor_ledger_csv(
    doctor_name: Optional[str] = Query(None),
    branch_id: Optional[UUID] = Depends(get_branch_context),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Export hierarchical doctor referral ledger to CSV.
    """
    if doctor_name:
        detail = await ReferralsService.get_doctor_hierarchy_detail(
            db=db, tenant_id=current_user.tenant_id, doctor_name=doctor_name, branch_id=branch_id
        )
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Referring Doctor",
            "Patient Name",
            "Patient VID",
            "Treatment Protocol",
            "Conversion Status",
            "Invoice #",
            "Date",
            "OPD (INR)",
            "Rx (INR)",
            "IUI (INR)",
            "IVF / Embryo (INR)",
            "LIMS (INR)",
            "IPD (INR)",
            "Net Bill (INR)",
            "Paid (INR)",
            "Commission (INR)",
            "Settlement Status",
        ])

        for p in detail.patients:
            for inv in p.invoices:
                writer.writerow([
                    detail.doctor_name,
                    p.patient_name,
                    p.patient_vid or "",
                    p.treatment_protocol,
                    p.conversion_badge,
                    inv.invoice_number,
                    inv.invoice_date.strftime("%Y-%m-%d"),
                    f"{inv.subsections.opd:.2f}",
                    f"{inv.subsections.pharmacy:.2f}",
                    f"{inv.subsections.iui:.2f}",
                    f"{inv.subsections.embryology:.2f}",
                    f"{inv.subsections.lims:.2f}",
                    f"{inv.subsections.ipd:.2f}",
                    f"{inv.net_total:.2f}",
                    f"{inv.paid_amount:.2f}",
                    f"{inv.commission_amount:.2f}",
                    "SETTLED" if inv.is_settled else "UNSETTLED",
                ])

        output.seek(0)
        filename = f"referral_ledger_{doctor_name.replace(' ', '_')}_{date.today().strftime('%Y%m%d')}.csv"
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    else:
        directory = await ReferralsService.get_doctors_directory(
            db=db, tenant_id=current_user.tenant_id, branch_id=branch_id
        )
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Doctor / Center Name",
            "Clinic / Center",
            "Phone",
            "Referred Patients",
            "Total Invoices",
            "Total Billed (INR)",
            "Total Paid (INR)",
            "Total Commission (INR)",
            "Settled Commission (INR)",
            "Pending Payout (INR)",
        ])
        for d in directory:
            writer.writerow([
                d.doctor_name,
                d.doctor_profile.clinic_name if d.doctor_profile else "",
                d.doctor_profile.phone if d.doctor_profile else "",
                d.patient_count,
                d.invoice_count,
                f"{d.total_revenue:.2f}",
                f"{d.total_paid:.2f}",
                f"{d.total_commission:.2f}",
                f"{d.settled_commission:.2f}",
                f"{d.pending_commission:.2f}",
            ])
        output.seek(0)
        filename = f"referrals_directory_{date.today().strftime('%Y%m%d')}.csv"
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
