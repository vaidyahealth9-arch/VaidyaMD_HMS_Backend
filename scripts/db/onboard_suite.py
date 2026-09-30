"""
VaidyaMD HMS — End-to-End Hospital Onboarding Suite Orchestrator
Modular, multi-domain CLI engine for provisioning Hospital Infrastructure, Staff Users,
IPD Beds, Treatment Cycles, Billing Service Items & Packages, Pharmacy Formulary & Vendors,
Clinical Stimulation Protocols, Clinical Templates & Order Sets, LIMS Test Directory,
Cryo Infrastructure, CosGyn Treatment Catalog, and Bulk Patients.

Usage:
  # Execute full E2E suite across all 13 domains:
  python scripts/db/onboard_suite.py --env local --all --force-upsert

  # Execute a single domain:
  python scripts/db/onboard_suite.py --env local --domain service_catalog
  python scripts/db/onboard_suite.py --env local --domain treatment_cycles
  python scripts/db/onboard_suite.py --env local --domain lims
  python scripts/db/onboard_suite.py --env local --domain cryo

  # Dry-run validation (no DB writes):
  python scripts/db/onboard_suite.py --env local --all --dry-run
"""

import sys
import os
import csv
import json
import uuid
import argparse
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, date

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Workspace paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = BASE_DIR / "VaidyaMD_HMS_Backend"
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BASE_DIR))

from sqlalchemy import select, func, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# Import Backend Models
from app.core.database import Base
from app.core.models.tenant import Hospital
from app.core.models.branch import Branch
from app.core.models.permission_profile import PermissionProfile
from app.core.models.user import User, UserRole
from app.core.security import hash_password, encrypt_pii

from app.modules.ipd.model import Ward, Bed
from app.modules.billing.model import TreatmentPackage, ServiceItem
from app.modules.pharmacy.model import InventoryBatch, PharmacyVendor
from app.modules.templates.model import ProtocolTemplate, ProtocolDrugRule, ClinicalTemplate
from app.modules.patients.model import Patient, RegistrationType, Gender
from app.plugins.fertility.models import TreatmentCycleType
from app.plugins.cosgyn.models import CosgynTreatment

from scripts.db.env_resolver import create_env_engine, resolve_database_url
from scripts.db.onboard_hospital import STANDARD_PROFILES


# =====================================================================
# Safe Value Helper
# =====================================================================
def s_get(row: Dict[str, Any], key: str, default: str = "") -> str:
    """Safely extracts a string value from a CSV row dictionary without crashing on None or whitespace in header."""
    val = row.get(key)
    if val is None:
        for k, v in row.items():
            if k and k.strip() == key:
                val = v
                break
    return str(val).strip() if val is not None else default


def resolve_conflict(record_desc: str, mode: str) -> str:
    """Returns 'overwrite', 'skip', or 'abort'."""
    if mode == "force-upsert":
        return "overwrite"
    if mode == "skip-existing":
        return "skip"

    print(f"\n⚠️  [CONFLICT] Record already exists: {record_desc}")
    while True:
        choice = input("   Choose action — [O]verwrite / [S]kip / [A]bort [O]: ").strip().lower()
        if choice in ("", "o", "overwrite"):
            return "overwrite"
        elif choice in ("s", "skip"):
            return "skip"
        elif choice in ("a", "abort"):
            print("🛑 Aborted by user.")
            sys.exit(1)
        else:
            print("   Please enter 'o', 's', or 'a'.")


ROLE_PROFILE_MAP = {
    UserRole.ADMIN: "Hospital Administrator",
    UserRole.DOCTOR: "Doctor / Clinician",
    UserRole.NURSE: "Fertility Nurse",
    UserRole.RECEPTIONIST: "Front Desk / Receptionist",
    UserRole.EMBRYOLOGIST: "Senior Embryologist",
    UserRole.ANDROLOGIST: "Senior Embryologist",
    UserRole.PHARMA: "Pharmacy Executive",
    UserRole.MANAGER: "Hospital Administrator",
    UserRole.ACCOUNTS: "Billing / Cashier",
    UserRole.SCANNING: "Doctor / Clinician",
    UserRole.COUNSELLOR: "Patient Counselor",
}


# =====================================================================
# Domain 01 & 02: Core (Hospital Tenant, Branches, Profiles, Staff Users)
# =====================================================================
async def run_domain_core(
    session: AsyncSession,
    hosp_filepath: Path,
    staff_filepath: Optional[Path],
    dry_run: bool,
    conflict_mode: str,
) -> Tuple[Hospital, Dict[str, Branch], Dict[str, int]]:
    print(f"\n🏢 [DOMAIN 01] Hospital Organization & Branches — {hosp_filepath.name}")
    stats = {"created": 0, "updated": 0, "skipped": 0}
    hospital: Optional[Hospital] = None
    branch_map: Dict[str, Branch] = {}
    profile_id_map: Dict[str, uuid.UUID] = {}

    with open(hosp_filepath, mode="r", encoding="utf-8-sig") as f:
        reader = list(csv.DictReader(f))

    # 1. Hospital Tenant
    hosp_rows = [r for r in reader if s_get(r, "record_type").upper() == "HOSPITAL"]
    if not hosp_rows:
        # If no explicit record_type, maybe whole file is hospital row
        hosp_rows = reader[:1]
    if not hosp_rows:
        raise ValueError(f"{hosp_filepath.name} must contain at least one HOSPITAL row.")
    h_row = hosp_rows[0]
    h_code = s_get(h_row, "code").upper()

    q_h = select(Hospital).where(Hospital.code == h_code)
    res_h = await session.execute(q_h)
    existing_h = res_h.scalar_one_or_none()

    active_plugins = [p.strip() for p in s_get(h_row, "active_plugins").split(",") if p.strip()]

    if existing_h:
        action = resolve_conflict(f"Hospital '{existing_h.name}' ({h_code})", conflict_mode)
        if action == "overwrite":
            existing_h.name = s_get(h_row, "name")
            existing_h.email = s_get(h_row, "email")
            existing_h.phone = s_get(h_row, "phone")
            existing_h.address = s_get(h_row, "address")
            existing_h.logo_url = s_get(h_row, "logo_url") or existing_h.logo_url
            if active_plugins:
                existing_h.active_plugins = active_plugins
            hospital = existing_h
            stats["updated"] += 1
            print(f"   🔄 Updated Hospital Tenant: {hospital.name} ({h_code})")
        else:
            hospital = existing_h
            stats["skipped"] += 1
            print(f"   ⏭️  Skipped existing Hospital Tenant: {hospital.name} ({h_code})")
    else:
        hospital = Hospital(
            code=h_code,
            name=s_get(h_row, "name"),
            email=s_get(h_row, "email"),
            phone=s_get(h_row, "phone"),
            address=s_get(h_row, "address"),
            logo_url=s_get(h_row, "logo_url"),
            active_plugins=active_plugins or ["fertility", "opd", "ipd", "pharmacy", "lims", "cosgyn"],
            is_active=True,
        )
        session.add(hospital)
        await session.flush()
        stats["created"] += 1
        print(f"   ✨ Created Hospital Tenant: {hospital.name} ({h_code})")

    # 2. Standard Permission Profiles
    for prof in STANDARD_PROFILES:
        q_p = select(PermissionProfile).where(
            PermissionProfile.hospital_id == hospital.id,
            PermissionProfile.name == prof["name"]
        )
        res_p = await session.execute(q_p)
        existing_p = res_p.scalar_one_or_none()
        if not existing_p:
            p_obj = PermissionProfile(
                hospital_id=hospital.id,
                name=prof["name"],
                description=prof["description"],
                menu_permissions=prof["menu_permissions"],
                is_active=True
            )
            session.add(p_obj)
            await session.flush()
            profile_id_map[prof["name"].lower()] = p_obj.id
        else:
            profile_id_map[existing_p.name.lower()] = existing_p.id

    # 3. Branches
    branch_rows = [r for r in reader if s_get(r, "record_type").upper() == "BRANCH"]
    for b_row in branch_rows:
        b_code = s_get(b_row, "code").upper()
        q_b = select(Branch).where(Branch.hospital_id == hospital.id, Branch.code == b_code)
        res_b = await session.execute(q_b)
        existing_b = res_b.scalar_one_or_none()

        is_main = s_get(b_row, "is_main_branch").lower() in ("true", "1", "yes")
        gstin_val = s_get(b_row, "gstin")
        ip_raw = s_get(b_row, "ip_whitelist")
        ip_list = [x.strip() for x in ip_raw.split(",") if x.strip()] if ip_raw else []

        receipt_hdr = {
            "reg_number": s_get(b_row, "receipt_reg_number") or s_get(h_row, "receipt_reg_number"),
            "art_reg_number": s_get(b_row, "receipt_art_reg_number") or s_get(h_row, "receipt_art_reg_number"),
            "tagline": s_get(b_row, "receipt_tagline") or s_get(h_row, "receipt_tagline"),
            "logo_url": s_get(b_row, "logo_url") or s_get(h_row, "logo_url"),
            "gstin": gstin_val,
            "address": s_get(b_row, "address"),
            "phone": s_get(b_row, "phone"),
            "email": s_get(b_row, "email"),
        }

        if existing_b:
            action = resolve_conflict(f"Branch '{existing_b.name}' ({b_code})", conflict_mode)
            if action == "overwrite":
                existing_b.name = s_get(b_row, "name")
                existing_b.email = s_get(b_row, "email")
                existing_b.phone = s_get(b_row, "phone")
                existing_b.address = s_get(b_row, "address")
                existing_b.is_main_branch = is_main
                existing_b.gstin = gstin_val
                existing_b.receipt_header = receipt_hdr
                existing_b.ip_whitelist = ip_list
                branch_map[b_code] = existing_b
                stats["updated"] += 1
                print(f"   🔄 Updated Branch: {existing_b.name} [{b_code}]")
            else:
                branch_map[b_code] = existing_b
                stats["skipped"] += 1
                print(f"   ⏭️  Skipped Branch: {existing_b.name} [{b_code}]")
        else:
            new_b = Branch(
                hospital_id=hospital.id,
                code=b_code,
                name=s_get(b_row, "name"),
                email=s_get(b_row, "email"),
                phone=s_get(b_row, "phone"),
                address=s_get(b_row, "address"),
                is_main_branch=is_main,
                gstin=gstin_val,
                receipt_header=receipt_hdr,
                ip_whitelist=ip_list,
                is_active=True
            )
            session.add(new_b)
            await session.flush()
            branch_map[b_code] = new_b
            stats["created"] += 1
            print(f"   ✨ Created Branch: {new_b.name} [{b_code}] (Main: {is_main})")

    # If no branches found, ensure at least one default MAIN branch
    if not branch_map:
        q_def_b = select(Branch).where(Branch.hospital_id == hospital.id)
        res_def_b = await session.execute(q_def_b)
        first_b = res_def_b.scalar_one_or_none()
        if not first_b:
            first_b = Branch(
                hospital_id=hospital.id,
                code="MAIN",
                name=f"{hospital.name} Main Branch",
                address=hospital.address,
                phone=hospital.phone,
                email=hospital.email,
                is_main_branch=True,
                is_active=True
            )
            session.add(first_b)
            await session.flush()
        branch_map[first_b.code] = first_b

    # 4. Staff Users
    staff_rows: List[Dict[str, Any]] = []
    if staff_filepath and staff_filepath.exists():
        print(f"\n👩‍⚕️ [DOMAIN 02] Staff User Roster — {staff_filepath.name}")
        with open(staff_filepath, mode="r", encoding="utf-8-sig") as sf:
            staff_rows = list(csv.DictReader(sf))
    else:
        # Check if reader has STAFF rows (legacy 01_core.csv format)
        staff_rows = [r for r in reader if s_get(r, "record_type").upper() == "STAFF"]
        if staff_rows:
            print(f"\n👩‍⚕️ [DOMAIN 02] Staff Users extracted from {hosp_filepath.name}")

    for s_row in staff_rows:
        email = s_get(s_row, "email").lower()
        q_u = select(User).where(User.email == email)
        res_u = await session.execute(q_u)
        existing_u = res_u.scalar_one_or_none()

        role_str = s_get(s_row, "role", "doctor").upper()
        role_enum = getattr(UserRole, role_str, UserRole.DOCTOR)
        is_doc = s_get(s_row, "is_doctor").lower() in ("true", "1", "yes")
        b_code = s_get(s_row, "branch_code").upper()
        staff_branch = branch_map.get(b_code) or list(branch_map.values())[0]

        temp_pwd = s_get(s_row, "temp_password") or "ApexPass2026!"
        pwd_hash = hash_password(temp_pwd)

        # Department JSON parsing
        dept_str = s_get(s_row, "departments")
        try:
            departments = json.loads(dept_str) if dept_str else []
        except Exception:
            departments = [d.strip() for d in dept_str.split(",") if d.strip()]

        qualification = s_get(s_row, "qualification")
        reg_number = s_get(s_row, "reg_number")
        specialization = s_get(s_row, "specialization")

        # Map role to permission profile
        prof_name = ROLE_PROFILE_MAP.get(role_enum, "Doctor / Clinician")
        profile_id = profile_id_map.get(prof_name.lower())

        if existing_u:
            action = resolve_conflict(f"Staff '{existing_u.name}' ({email})", conflict_mode)
            if action == "overwrite":
                existing_u.name = s_get(s_row, "name")
                existing_u.phone = s_get(s_row, "phone")
                existing_u.role = role_enum
                existing_u.is_doctor = is_doc
                existing_u.specialization = specialization
                existing_u.qualification = qualification
                existing_u.reg_number = reg_number
                existing_u.departments = departments
                existing_u.branch_id = staff_branch.id
                if profile_id:
                    existing_u.permission_profile_id = profile_id
                existing_u.password_hash = pwd_hash
                stats["updated"] += 1
                print(f"   🔄 Updated Staff: {existing_u.name} ({email}) [{role_str}]")
            else:
                stats["skipped"] += 1
                print(f"   ⏭️  Skipped Staff: {existing_u.name} ({email})")
        else:
            new_u = User(
                tenant_id=hospital.id,
                branch_id=staff_branch.id,
                email=email,
                name=s_get(s_row, "name"),
                phone=s_get(s_row, "phone"),
                role=role_enum,
                is_doctor=is_doc,
                specialization=specialization,
                qualification=qualification,
                reg_number=reg_number,
                departments=departments,
                permission_profile_id=profile_id,
                password_hash=pwd_hash,
                is_active=True,
            )
            session.add(new_u)
            stats["created"] += 1
            print(f"   ✨ Created Staff: {new_u.name} ({email}) [{role_str}] - {qualification}")

    await session.flush()
    print(f"   📊 Core Summary: Created={stats['created']} | Updated={stats['updated']} | Skipped={stats['skipped']}")
    return hospital, branch_map, stats


# =====================================================================
# Domain 03: IPD Infrastructure (Wards & Beds)
# =====================================================================
async def run_domain_ipd(
    session: AsyncSession, hospital: Hospital, branch_map: Dict[str, Branch], filepath: Path, dry_run: bool, conflict_mode: str
) -> Dict[str, int]:
    print(f"\n🛏️  [DOMAIN 03] IPD Wards & Beds — {filepath.name}")
    stats = {"created": 0, "updated": 0, "skipped": 0}
    ward_map: Dict[str, Ward] = {}

    with open(filepath, mode="r", encoding="utf-8-sig") as f:
        reader = list(csv.DictReader(f))

    # 1. Wards
    ward_rows = [r for r in reader if s_get(r, "record_type").upper() == "WARD"]
    for r in ward_rows:
        w_code = s_get(r, "ward_code").upper()
        b_code = s_get(r, "branch_code").upper()
        target_branch = branch_map.get(b_code) or list(branch_map.values())[0]

        q_w = select(Ward).where(Ward.tenant_id == hospital.id, Ward.code == w_code)
        res_w = await session.execute(q_w)
        existing_w = res_w.scalar_one_or_none()

        base_rate = float(s_get(r, "base_charge_per_day") or 2500.0)

        if existing_w:
            action = resolve_conflict(f"Ward '{existing_w.name}' [{w_code}]", conflict_mode)
            if action == "overwrite":
                existing_w.name = s_get(r, "ward_name")
                existing_w.department = s_get(r, "department")
                existing_w.base_charge_per_day = base_rate
                existing_w.branch_id = target_branch.id
                ward_map[w_code] = existing_w
                stats["updated"] += 1
                print(f"   🔄 Updated Ward: {existing_w.name} [{w_code}]")
            else:
                ward_map[w_code] = existing_w
                stats["skipped"] += 1
                print(f"   ⏭️  Skipped Ward: {existing_w.name} [{w_code}]")
        else:
            w_obj = Ward(
                tenant_id=hospital.id,
                branch_id=target_branch.id,
                code=w_code,
                name=s_get(r, "ward_name"),
                department=s_get(r, "department"),
                base_charge_per_day=base_rate,
                total_beds=0,
                is_active=True
            )
            session.add(w_obj)
            await session.flush()
            ward_map[w_code] = w_obj
            stats["created"] += 1
            print(f"   ✨ Created Ward: {w_obj.name} [{w_code}] (₹{base_rate}/day)")

    # 2. Beds
    bed_rows = [r for r in reader if s_get(r, "record_type").upper() == "BED"]
    for r in bed_rows:
        w_code = s_get(r, "ward_code").upper()
        ward = ward_map.get(w_code)
        if not ward:
            res_w = await session.execute(select(Ward).where(Ward.tenant_id == hospital.id, Ward.code == w_code))
            ward = res_w.scalar_one_or_none()
            if not ward:
                print(f"   ⚠️  Ward '{w_code}' not found for Bed '{s_get(r, 'bed_number')}'. Skipping.")
                continue
            ward_map[w_code] = ward

        b_num = s_get(r, "bed_number")
        q_b = select(Bed).where(Bed.ward_id == ward.id, Bed.bed_number == b_num)
        res_b = await session.execute(q_b)
        existing_b = res_b.scalar_one_or_none()

        rate = float(s_get(r, "daily_rate") or ward.base_charge_per_day)
        raw_st = s_get(r, "status", "Vacant")
        bed_status = "Vacant" if raw_st.lower() in ("available", "vacant") else raw_st

        if existing_b:
            action = resolve_conflict(f"Bed '{b_num}' in Ward '{ward.code}'", conflict_mode)
            if action == "overwrite":
                existing_b.bed_type = s_get(r, "bed_type", "standard_manual")
                existing_b.daily_rate = rate
                existing_b.status = bed_status
                stats["updated"] += 1
                print(f"   🔄 Updated Bed: {b_num} ({existing_b.bed_type}) [₹{rate}/day]")
            else:
                stats["skipped"] += 1
                print(f"   ⏭️  Skipped Bed: {b_num}")
        else:
            bed_obj = Bed(
                tenant_id=hospital.id,
                branch_id=ward.branch_id,
                ward_id=ward.id,
                bed_number=b_num,
                bed_type=s_get(r, "bed_type", "standard_manual"),
                status=bed_status,
                daily_rate=rate,
            )
            session.add(bed_obj)
            stats["created"] += 1
            print(f"   ✨ Created Bed: {b_num} in {ward.name} [₹{rate}/day]")

    await session.flush()
    # Synchronize ward.total_beds
    for w in ward_map.values():
        b_cnt = await session.scalar(select(func.count(Bed.id)).where(Bed.ward_id == w.id))
        w.total_beds = b_cnt or 0
    await session.flush()
    print(f"   📊 IPD Summary: Created={stats['created']} | Updated={stats['updated']} | Skipped={stats['skipped']}")
    return stats


# =====================================================================
# Domain 04: Treatment Cycle Types (ART Clinical Types)
# =====================================================================
async def run_domain_treatment_cycles(
    session: AsyncSession, hospital: Hospital, branch_map: Dict[str, Branch], filepath: Path, dry_run: bool, conflict_mode: str
) -> Dict[str, int]:
    print(f"\n🧬 [DOMAIN 04] Treatment Cycle Types (ART Taxonomy) — {filepath.name}")
    stats = {"created": 0, "updated": 0, "skipped": 0}

    with open(filepath, mode="r", encoding="utf-8-sig") as f:
        reader = list(csv.DictReader(f))

    for r in reader:
        name = s_get(r, "name")
        cat = s_get(r, "category")
        disp_order = int(s_get(r, "display_order") or 0)
        is_act = s_get(r, "is_active", "true").lower() in ("true", "1", "yes")
        b_code = s_get(r, "branch_code").upper()
        target_branch = branch_map.get(b_code) or (list(branch_map.values())[0] if branch_map else None)

        q = select(TreatmentCycleType).where(
            TreatmentCycleType.tenant_id == hospital.id,
            TreatmentCycleType.name == name
        )
        res = await session.execute(q)
        existing = res.scalar_one_or_none()

        if existing:
            action = resolve_conflict(f"Treatment Cycle Type '{name}'", conflict_mode)
            if action == "overwrite":
                existing.category = cat
                existing.display_order = disp_order
                existing.is_active = is_act
                existing.branch_id = target_branch.id if target_branch else None
                stats["updated"] += 1
                print(f"   🔄 Updated Cycle Type: {name} ({cat})")
            else:
                stats["skipped"] += 1
                print(f"   ⏭️  Skipped Cycle Type: {name}")
        else:
            obj = TreatmentCycleType(
                tenant_id=hospital.id,
                branch_id=target_branch.id if target_branch else None,
                name=name,
                category=cat,
                display_order=disp_order,
                is_active=is_act
            )
            session.add(obj)
            stats["created"] += 1
            print(f"   ✨ Created Cycle Type: {name} ({cat}, Order: {disp_order})")

    await session.flush()
    print(f"   📊 Cycle Types Summary: Created={stats['created']} | Updated={stats['updated']} | Skipped={stats['skipped']}")
    return stats


# =====================================================================
# Domain 05: Billing Service Catalog & Tariffs
# =====================================================================
async def run_domain_service_catalog(
    session: AsyncSession, hospital: Hospital, branch_map: Dict[str, Branch], filepath: Path, dry_run: bool, conflict_mode: str
) -> Dict[str, int]:
    print(f"\n🏷️  [DOMAIN 05] Billing Service Catalog & Tariffs — {filepath.name}")
    stats = {"created": 0, "updated": 0, "skipped": 0}

    with open(filepath, mode="r", encoding="utf-8-sig") as f:
        reader = list(csv.DictReader(f))

    for r in reader:
        code = s_get(r, "code").upper()
        name = s_get(r, "name")
        cat = s_get(r, "category", "OP")
        price = float(s_get(r, "base_price") or 0.0)
        hsn_sac = s_get(r, "hsn_sac")
        gst = float(s_get(r, "gst_rate") or 0.0)
        b_code = s_get(r, "branch_code").upper()
        target_branch = branch_map.get(b_code) or (list(branch_map.values())[0] if branch_map else None)

        q = select(ServiceItem).where(
            ServiceItem.tenant_id == hospital.id,
            ServiceItem.code == code
        )
        res = await session.execute(q)
        existing = res.scalar_one_or_none()

        if existing:
            action = resolve_conflict(f"Service Item '{code} - {name}'", conflict_mode)
            if action == "overwrite":
                existing.name = name
                existing.category = cat
                existing.base_price = price
                existing.hsn_sac = hsn_sac
                existing.gst_rate = gst
                existing.branch_id = target_branch.id if target_branch else None
                stats["updated"] += 1
                print(f"   🔄 Updated Service: {code} - {name} [₹{price:,.2f}]")
            else:
                stats["skipped"] += 1
                print(f"   ⏭️  Skipped Service: {code}")
        else:
            obj = ServiceItem(
                tenant_id=hospital.id,
                branch_id=target_branch.id if target_branch else None,
                code=code,
                name=name,
                category=cat,
                base_price=price,
                hsn_sac=hsn_sac,
                gst_rate=gst,
                is_active=True
            )
            session.add(obj)
            stats["created"] += 1
            print(f"   ✨ Created Service: {code} - {name} ({cat}, ₹{price:,.2f})")

    await session.flush()
    print(f"   📊 Service Catalog Summary: Created={stats['created']} | Updated={stats['updated']} | Skipped={stats['skipped']}")
    return stats


# =====================================================================
# Domain 06: Billing Packages & Itemized IVF Bundles
# =====================================================================
async def run_domain_billing_packages(
    session: AsyncSession, hospital: Hospital, branch_map: Dict[str, Branch], filepath: Path, dry_run: bool, conflict_mode: str
) -> Dict[str, int]:
    print(f"\n💳 [DOMAIN 06] Billing Packages & Bundles — {filepath.name}")
    stats = {"created": 0, "updated": 0, "skipped": 0}

    with open(filepath, mode="r", encoding="utf-8-sig") as f:
        reader = list(csv.DictReader(f))

    for r in reader:
        pkg_name = s_get(r, "name")
        b_code = s_get(r, "branch_code").upper()
        target_branch = branch_map.get(b_code) or list(branch_map.values())[0]

        q_p = select(TreatmentPackage).where(
            TreatmentPackage.tenant_id == hospital.id,
            TreatmentPackage.name == pkg_name
        )
        res_p = await session.execute(q_p)
        existing_p = res_p.scalar_one_or_none()

        try:
            items_data = json.loads(s_get(r, "items_json") or "[]")
        except Exception:
            items_data = []

        base_price = float(s_get(r, "base_price") or 0.0)

        if existing_p:
            action = resolve_conflict(f"Treatment Package '{pkg_name}'", conflict_mode)
            if action == "overwrite":
                existing_p.description = s_get(r, "description")
                existing_p.plugin_id = s_get(r, "plugin_id", "fertility")
                existing_p.base_price = base_price
                existing_p.items = items_data
                existing_p.branch_id = target_branch.id
                stats["updated"] += 1
                print(f"   🔄 Updated Package: {pkg_name} [₹{base_price:,.2f}]")
            else:
                stats["skipped"] += 1
                print(f"   ⏭️  Skipped Package: {pkg_name}")
        else:
            p_obj = TreatmentPackage(
                tenant_id=hospital.id,
                branch_id=target_branch.id,
                name=pkg_name,
                description=s_get(r, "description"),
                plugin_id=s_get(r, "plugin_id", "fertility"),
                base_price=base_price,
                items=items_data,
                is_active=True
            )
            session.add(p_obj)
            stats["created"] += 1
            print(f"   ✨ Created Package: {pkg_name} ({len(items_data)} items, ₹{base_price:,.2f})")

    await session.flush()
    print(f"   📊 Billing Packages Summary: Created={stats['created']} | Updated={stats['updated']} | Skipped={stats['skipped']}")
    return stats


# =====================================================================
# Domain 07: Clinical Stimulation Protocols & Drug Rules
# =====================================================================
async def run_domain_protocols(
    session: AsyncSession, hospital: Hospital, branch_map: Dict[str, Branch], filepath: Path, dry_run: bool, conflict_mode: str
) -> Dict[str, int]:
    print(f"\n📋 [DOMAIN 07] Stimulation Protocols & Drug Rules — {filepath.name}")
    stats = {"created": 0, "updated": 0, "skipped": 0}
    protocol_map: Dict[str, ProtocolTemplate] = {}

    res_u = await session.execute(select(User.id).where(User.tenant_id == hospital.id).limit(1))
    author_id = res_u.scalar() or hospital.id

    with open(filepath, mode="r", encoding="utf-8-sig") as f:
        reader = list(csv.DictReader(f))

    # 1. Protocols
    prot_rows = [r for r in reader if s_get(r, "record_type").upper() == "PROTOCOL"]
    for r in prot_rows:
        p_name = s_get(r, "protocol_name")
        b_code = s_get(r, "branch_code").upper()
        target_branch = branch_map.get(b_code) or list(branch_map.values())[0]

        q_p = select(ProtocolTemplate).where(
            ProtocolTemplate.tenant_id == hospital.id,
            ProtocolTemplate.name == p_name
        )
        res_p = await session.execute(q_p)
        existing_p = res_p.scalar_one_or_none()

        cat = s_get(r, "category", "antagonist")
        desc_val = s_get(r, "description")
        timeline_raw = s_get(r, "timeline_events")
        timeline_val = []
        if timeline_raw:
            try:
                timeline_val = json.loads(timeline_raw)
            except Exception:
                timeline_val = []

        if existing_p:
            action = resolve_conflict(f"Protocol '{p_name}'", conflict_mode)
            if action == "overwrite":
                existing_p.category = cat
                existing_p.description = desc_val
                existing_p.branch_id = target_branch.id
                existing_p.timeline_events = timeline_val
                existing_p.is_active = True
                protocol_map[p_name] = existing_p
                stats["updated"] += 1
                print(f"   🔄 Updated Protocol: {p_name}")
            else:
                protocol_map[p_name] = existing_p
                stats["skipped"] += 1
                print(f"   ⏭️  Skipped Protocol: {p_name}")
        else:
            p_obj = ProtocolTemplate(
                tenant_id=hospital.id,
                hospital_id=hospital.id,
                branch_id=target_branch.id,
                name=p_name,
                category=cat,
                description=desc_val,
                timeline_events=timeline_val,
                created_by=author_id,
                is_active=True
            )
            session.add(p_obj)
            await session.flush()
            protocol_map[p_name] = p_obj
            stats["created"] += 1
            print(f"   ✨ Created Protocol: {p_name} ({cat})")

    # Excel-only rule: Deactivate any older protocols not present in the current template
    if conflict_mode in ["overwrite", "force-upsert"]:
        active_names = [s_get(r, "protocol_name") for r in prot_rows]
        res_old = await session.execute(
            select(ProtocolTemplate).where(
                ProtocolTemplate.tenant_id == hospital.id,
                ProtocolTemplate.name.notin_(active_names),
                ProtocolTemplate.is_active == True
            )
        )
        for old_p in res_old.scalars().all():
            old_p.is_active = False
            print(f"   🗑️  Deactivated non-Excel Protocol: {old_p.name}")

    # 2. Drug Rules
    rule_rows = [r for r in reader if s_get(r, "record_type").upper() == "DRUG_RULE"]
    for idx, r in enumerate(rule_rows):
        p_name = s_get(r, "protocol_name")
        protocol = protocol_map.get(p_name)
        if not protocol:
            res_p = await session.execute(
                select(ProtocolTemplate).where(ProtocolTemplate.tenant_id == hospital.id, ProtocolTemplate.name == p_name)
            )
            protocol = res_p.scalar_one_or_none()
            if not protocol:
                continue
            protocol_map[p_name] = protocol

        d_name = s_get(r, "drug_name")
        start_off = int(s_get(r, "day_start_offset") or 1)
        end_off = int(s_get(r, "day_end_offset") or start_off)

        q_r = select(ProtocolDrugRule).where(
            ProtocolDrugRule.protocol_template_id == protocol.id,
            ProtocolDrugRule.drug_name == d_name,
            ProtocolDrugRule.day_start_offset == start_off
        )
        res_r = await session.execute(q_r)
        existing_r = res_r.scalar_one_or_none()

        if existing_r:
            existing_r.dose = s_get(r, "dose")
            existing_r.route = s_get(r, "route")
            existing_r.frequency = s_get(r, "frequency")
            existing_r.day_end_offset = end_off
            existing_r.sentinel_anchor = s_get(r, "sentinel_anchor", "stim_start")
            existing_r.instructions = s_get(r, "instructions")
            stats["updated"] += 1
        else:
            rule_obj = ProtocolDrugRule(
                tenant_id=hospital.id,
                branch_id=protocol.branch_id,
                protocol_template_id=protocol.id,
                drug_name=d_name,
                dose=s_get(r, "dose"),
                route=s_get(r, "route"),
                frequency=s_get(r, "frequency"),
                sentinel_anchor=s_get(r, "sentinel_anchor", "stim_start"),
                day_start_offset=start_off,
                day_end_offset=end_off,
                instructions=s_get(r, "instructions"),
                sort_order=idx + 1
            )
            session.add(rule_obj)
            stats["created"] += 1
            print(f"      💊 Rule: {d_name} {rule_obj.dose} (Days {rule_obj.day_start_offset}-{rule_obj.day_end_offset})")

    await session.flush()
    print(f"   📊 Protocols Summary: Created={stats['created']} | Updated={stats['updated']} | Skipped={stats['skipped']}")
    return stats


# =====================================================================
# Domain 08: Clinical Proforma, Order Sets & Rx Templates
# =====================================================================
async def run_domain_clinical_templates(
    session: AsyncSession, hospital: Hospital, branch_map: Dict[str, Branch], filepath: Path, dry_run: bool, conflict_mode: str
) -> Dict[str, int]:
    print(f"\n📝 [DOMAIN 08] Clinical Proforma, Order Sets & Rx Templates — {filepath.name}")
    stats = {"created": 0, "updated": 0, "skipped": 0}

    res_u = await session.execute(select(User.id).where(User.tenant_id == hospital.id).limit(1))
    author_id = res_u.scalar() or hospital.id

    with open(filepath, mode="r", encoding="utf-8-sig") as f:
        reader = list(csv.DictReader(f))

    for r in reader:
        t_name = s_get(r, "title")
        rec_type = s_get(r, "record_type")
        plugin_id = s_get(r, "plugin_id", "fertility")
        b_code = s_get(r, "branch_code").upper()
        target_branch = branch_map.get(b_code) or list(branch_map.values())[0]

        q_t = select(ClinicalTemplate).where(
            ClinicalTemplate.record_type == rec_type
        )
        res_t = await session.execute(q_t)
        existing_t = res_t.scalar_one_or_none()

        try:
            fields_data = json.loads(s_get(r, "schema_json") or "{}")
        except Exception:
            fields_data = {}

        if existing_t:
            action = resolve_conflict(f"Clinical Template '{t_name}' [{rec_type}]", conflict_mode)
            if action == "overwrite":
                existing_t.title = t_name
                existing_t.plugin_id = plugin_id
                existing_t.description = s_get(r, "description")
                existing_t.schema_json = fields_data
                existing_t.branch_id = target_branch.id
                existing_t.tenant_id = hospital.id
                stats["updated"] += 1
                print(f"   🔄 Updated Clinical Template: {t_name} [{plugin_id}]")
            else:
                stats["skipped"] += 1
                print(f"   ⏭️  Skipped Clinical Template: {t_name}")
        else:
            t_obj = ClinicalTemplate(
                tenant_id=hospital.id,
                branch_id=target_branch.id,
                title=t_name,
                record_type=rec_type,
                plugin_id=plugin_id,
                description=s_get(r, "description"),
                schema_json=fields_data,
                created_by=author_id,
                is_active=True
            )
            session.add(t_obj)
            stats["created"] += 1
            print(f"   ✨ Created Clinical Template: {t_name} [{rec_type}] ({plugin_id})")

    await session.flush()
    print(f"   📊 Clinical Templates Summary: Created={stats['created']} | Updated={stats['updated']} | Skipped={stats['skipped']}")
    return stats


# =====================================================================
# Domain 09: LIMS Test Directory & Parameters
# =====================================================================
async def run_domain_lims(
    session: AsyncSession, hospital: Hospital, branch_map: Dict[str, Branch], filepath: Path, dry_run: bool, conflict_mode: str
) -> Dict[str, int]:
    print(f"\n🔬 [DOMAIN 09] LIMS Test Directory & Quantitative Parameters — {filepath.name}")
    stats = {"created": 0, "updated": 0, "skipped": 0}

    res_u = await session.execute(select(User.id).where(User.tenant_id == hospital.id).limit(1))
    author_id = res_u.scalar() or hospital.id

    with open(filepath, mode="r", encoding="utf-8-sig") as f:
        reader = list(csv.DictReader(f))

    for r in reader:
        code = s_get(r, "test_code").upper()
        name = s_get(r, "test_name")
        cat = s_get(r, "category")
        sample = s_get(r, "sample_type")
        tat = int(s_get(r, "tat_hours") or 4)
        b_code = s_get(r, "branch_code").upper()
        target_branch = branch_map.get(b_code) or (list(branch_map.values())[0] if branch_map else None)

        try:
            params_data = json.loads(s_get(r, "parameters_json") or "[]")
        except Exception:
            params_data = []

        rec_type = f"lims_{code.lower().replace('-', '_')}"
        schema_data = {
            "test_code": code,
            "test_name": name,
            "category": cat,
            "sample_type": sample,
            "tat_hours": tat,
            "parameters": params_data,
        }

        q = select(ClinicalTemplate).where(
            ClinicalTemplate.tenant_id == hospital.id,
            ClinicalTemplate.record_type == rec_type
        )
        res = await session.execute(q)
        existing = res.scalar_one_or_none()

        desc = f"{cat} | Sample: {sample} | TAT: {tat}h | Code: {code}"

        if existing:
            action = resolve_conflict(f"LIMS Panel '{name}' [{code}]", conflict_mode)
            if action == "overwrite":
                existing.title = name
                existing.plugin_id = "lims"
                existing.description = desc
                existing.schema_json = schema_data
                existing.branch_id = target_branch.id if target_branch else None
                stats["updated"] += 1
                print(f"   🔄 Updated LIMS Panel: {name} [{code}]")
            else:
                stats["skipped"] += 1
                print(f"   ⏭️  Skipped LIMS Panel: {name}")
        else:
            t_obj = ClinicalTemplate(
                tenant_id=hospital.id,
                branch_id=target_branch.id if target_branch else None,
                title=name,
                record_type=rec_type,
                plugin_id="lims",
                description=desc,
                schema_json=schema_data,
                created_by=author_id,
                is_active=True
            )
            session.add(t_obj)
            stats["created"] += 1
            print(f"   ✨ Created LIMS Panel: {name} [{code}] ({len(params_data)} parameters)")

    await session.flush()
    print(f"   📊 LIMS Directory Summary: Created={stats['created']} | Updated={stats['updated']} | Skipped={stats['skipped']}")
    return stats


# =====================================================================
# Domain 10: Cryobank Physical Infrastructure (Tanks & Canisters)
# =====================================================================
async def run_domain_cryo(
    session: AsyncSession, hospital: Hospital, branch_map: Dict[str, Branch], filepath: Path, dry_run: bool, conflict_mode: str
) -> Dict[str, int]:
    print(f"\n❄️  [DOMAIN 10] Cryobank Physical Infrastructure — {filepath.name}")
    stats = {"created": 0, "updated": 0, "skipped": 0}

    res_u = await session.execute(select(User.id).where(User.tenant_id == hospital.id).limit(1))
    author_id = res_u.scalar() or hospital.id

    with open(filepath, mode="r", encoding="utf-8-sig") as f:
        reader = list(csv.DictReader(f))

    for r in reader:
        tank_code = s_get(r, "tank_code").upper()
        tank_name = s_get(r, "tank_name")
        tank_type = s_get(r, "tank_type")
        cap = float(s_get(r, "capacity_litres") or 0.0)
        loc = s_get(r, "location")
        can_count = int(s_get(r, "canister_count") or 6)
        b_code = s_get(r, "branch_code").upper()
        target_branch = branch_map.get(b_code) or (list(branch_map.values())[0] if branch_map else None)

        try:
            colours = json.loads(s_get(r, "canister_colours_json") or "[]")
        except Exception:
            colours = []

        dev_types = [d.strip() for d in s_get(r, "supported_device_types").split(",") if d.strip()]

        rec_type = f"cryo_{tank_code.lower().replace('-', '_')}"
        schema_data = {
            "tank_code": tank_code,
            "tank_name": tank_name,
            "tank_type": tank_type,
            "capacity_litres": cap,
            "location": loc,
            "canister_count": can_count,
            "canister_colours": colours,
            "supported_device_types": dev_types,
        }

        q = select(ClinicalTemplate).where(
            ClinicalTemplate.tenant_id == hospital.id,
            ClinicalTemplate.record_type == rec_type
        )
        res = await session.execute(q)
        existing = res.scalar_one_or_none()

        desc = f"{tank_type} | {cap}L | {loc} | {can_count} Canisters"

        if existing:
            action = resolve_conflict(f"Cryo Tank '{tank_name}' [{tank_code}]", conflict_mode)
            if action == "overwrite":
                existing.title = tank_name
                existing.plugin_id = "fertility_cryo"
                existing.description = desc
                existing.schema_json = schema_data
                existing.branch_id = target_branch.id if target_branch else None
                stats["updated"] += 1
                print(f"   🔄 Updated Cryo Tank: {tank_name} [{tank_code}]")
            else:
                stats["skipped"] += 1
                print(f"   ⏭️  Skipped Cryo Tank: {tank_name}")
        else:
            t_obj = ClinicalTemplate(
                tenant_id=hospital.id,
                branch_id=target_branch.id if target_branch else None,
                title=tank_name,
                record_type=rec_type,
                plugin_id="fertility_cryo",
                description=desc,
                schema_json=schema_data,
                created_by=author_id,
                is_active=True
            )
            session.add(t_obj)
            stats["created"] += 1
            print(f"   ✨ Created Cryo Tank: {tank_name} [{tank_code}] ({can_count} canisters, {cap}L)")

    await session.flush()
    print(f"   📊 Cryo Summary: Created={stats['created']} | Updated={stats['updated']} | Skipped={stats['skipped']}")
    return stats


# =====================================================================
# Domain 11a: Pharmacy Vendors Directory
# =====================================================================
async def run_domain_pharmacy_vendors(
    session: AsyncSession, hospital: Hospital, branch_map: Dict[str, Branch], filepath: Path, dry_run: bool, conflict_mode: str
) -> Dict[str, int]:
    print(f"\n🏢 [DOMAIN 11a] Pharmacy Vendors Directory — {filepath.name}")
    stats = {"created": 0, "updated": 0, "skipped": 0}

    with open(filepath, mode="r", encoding="utf-8-sig") as f:
        reader = list(csv.DictReader(f))

    for r in reader:
        v_name = s_get(r, "name") or s_get(r, "vendor_name")
        if not v_name:
            continue
        v_gst = s_get(r, "gst_number") or s_get(r, "vendor_gst")
        v_contact = s_get(r, "contact_phone") or s_get(r, "vendor_contact")
        v_email = s_get(r, "contact_email")
        v_addr = s_get(r, "address")
        b_code = s_get(r, "branch_code").upper()
        target_branch = branch_map.get(b_code) or list(branch_map.values())[0]

        q_v = select(PharmacyVendor).where(
            PharmacyVendor.tenant_id == hospital.id,
            PharmacyVendor.name == v_name
        )
        res_v = await session.execute(q_v)
        existing_v = res_v.scalar_one_or_none()

        if existing_v:
            action = resolve_conflict(f"Pharmacy Vendor '{v_name}'", conflict_mode)
            if action == "overwrite":
                existing_v.gst_number = v_gst
                existing_v.contact_phone = v_contact
                if hasattr(existing_v, "contact_email") and v_email:
                    existing_v.contact_email = v_email
                if hasattr(existing_v, "address") and v_addr:
                    existing_v.address = v_addr
                existing_v.branch_id = target_branch.id
                stats["updated"] += 1
                print(f"   🔄 Updated Vendor: {v_name}")
            else:
                stats["skipped"] += 1
                print(f"   ⏭️  Skipped Vendor: {v_name}")
        else:
            v_obj = PharmacyVendor(
                tenant_id=hospital.id,
                branch_id=target_branch.id,
                name=v_name,
                gst_number=v_gst,
                contact_phone=v_contact,
                contact_email=v_email or None,
                address=v_addr or None,
                is_active=True
            )
            session.add(v_obj)
            stats["created"] += 1
            print(f"   ✨ Created Vendor: {v_name} (GST: {v_gst})")

    await session.flush()
    print(f"   📊 Pharmacy Vendors Summary: Created={stats['created']} | Updated={stats['updated']} | Skipped={stats['skipped']}")
    return stats


# =====================================================================
# Domain 11b: Pharmacy Formulary & Stock Batches
# =====================================================================
async def run_domain_pharmacy_stock(
    session: AsyncSession, hospital: Hospital, branch_map: Dict[str, Branch], filepath: Path, dry_run: bool, conflict_mode: str
) -> Dict[str, int]:
    print(f"\n💊 [DOMAIN 11b] Pharmacy Stock & Batches — {filepath.name}")
    stats = {"created": 0, "updated": 0, "skipped": 0}

    with open(filepath, mode="r", encoding="utf-8-sig") as f:
        reader = list(csv.DictReader(f))

    for r in reader:
        item_code = s_get(r, "item_code").upper()
        batch_num = s_get(r, "batch_number").upper()
        if not item_code or not batch_num:
            continue

        b_code = s_get(r, "branch_code").upper()
        target_branch = branch_map.get(b_code) or list(branch_map.values())[0]

        q_b = select(InventoryBatch).where(
            InventoryBatch.tenant_id == hospital.id,
            InventoryBatch.item_code == item_code,
            InventoryBatch.batch_number == batch_num
        )
        res_b = await session.execute(q_b)
        existing_b = res_b.scalar_one_or_none()

        expiry_str = s_get(r, "expiry_date")
        expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date() if expiry_str else datetime.utcnow().date()
        qty = int(s_get(r, "quantity_available") or s_get(r, "quantity_received") or 100)
        p_rate = float(s_get(r, "purchase_rate") or 0.0)
        mrp = float(s_get(r, "mrp") or 0.0)
        s_price = float(s_get(r, "selling_price") or mrp)

        if existing_b:
            action = resolve_conflict(f"Batch '{batch_num}' for '{s_get(r, 'item_name')}'", conflict_mode)
            if action == "overwrite":
                existing_b.item_name = s_get(r, "item_name")
                existing_b.generic_name = s_get(r, "generic_name")
                existing_b.category = s_get(r, "category")
                existing_b.expiry_date = expiry
                existing_b.quantity_received = int(s_get(r, "quantity_received") or qty)
                existing_b.quantity_available = qty
                existing_b.purchase_rate = p_rate
                existing_b.mrp = mrp
                existing_b.selling_price = s_price
                existing_b.rack_location = s_get(r, "rack_location")
                existing_b.branch_id = target_branch.id
                stats["updated"] += 1
                print(f"   🔄 Updated Batch: {item_code} #{batch_num} ({qty} units)")
            else:
                stats["skipped"] += 1
                print(f"   ⏭️  Skipped Batch: {item_code} #{batch_num}")
        else:
            b_obj = InventoryBatch(
                tenant_id=hospital.id,
                branch_id=target_branch.id,
                item_code=item_code,
                item_name=s_get(r, "item_name"),
                generic_name=s_get(r, "generic_name"),
                category=s_get(r, "category"),
                batch_number=batch_num,
                expiry_date=expiry,
                quantity_received=int(s_get(r, "quantity_received") or qty),
                quantity_available=qty,
                purchase_rate=p_rate,
                mrp=mrp,
                selling_price=s_price,
                rack_location=s_get(r, "rack_location"),
                is_active=True
            )
            session.add(b_obj)
            stats["created"] += 1
            print(f"   ✨ Created Batch: {b_obj.item_name} [{item_code}] #{batch_num} ({qty} units, Exp: {expiry})")

    await session.flush()
    print(f"   📊 Pharmacy Stock Summary: Created={stats['created']} | Updated={stats['updated']} | Skipped={stats['skipped']}")
    return stats


# Backward compatible dispatcher for single pharmacy file or legacy file
async def run_domain_pharmacy(
    session: AsyncSession, hospital: Hospital, branch_map: Dict[str, Branch], filepath: Path, dry_run: bool, conflict_mode: str
) -> Dict[str, int]:
    with open(filepath, mode="r", encoding="utf-8-sig") as f:
        reader = list(csv.DictReader(f))
    if not reader:
        return {"created": 0, "updated": 0, "skipped": 0}
    first_row = reader[0]
    # Check if vendors only
    if ("gst_number" in first_row or "vendor_gst" in first_row) and "batch_number" not in first_row:
        return await run_domain_pharmacy_vendors(session, hospital, branch_map, filepath, dry_run, conflict_mode)
    # Check if stock only
    if "batch_number" in first_row and "record_type" not in first_row:
        return await run_domain_pharmacy_stock(session, hospital, branch_map, filepath, dry_run, conflict_mode)

    # Legacy combined fallback
    print(f"\n💊 [DOMAIN 11] Pharmacy Combined (Legacy) — {filepath.name}")
    v_stats = await run_domain_pharmacy_vendors(session, hospital, branch_map, filepath, dry_run, conflict_mode)
    s_stats = await run_domain_pharmacy_stock(session, hospital, branch_map, filepath, dry_run, conflict_mode)
    return {
        "created": v_stats["created"] + s_stats["created"],
        "updated": v_stats["updated"] + s_stats["updated"],
        "skipped": v_stats["skipped"] + s_stats["skipped"],
    }


# =====================================================================
# Domain 12: Bulk Patients & Couple Linking
# =====================================================================
async def generate_vid(session: AsyncSession, hospital_code: str) -> str:
    code = (hospital_code or "VMD")[:3].upper().ljust(3, "X")
    result = await session.execute(select(func.count(Patient.id)))
    count = result.scalar() or 0
    base_num = count + 1
    for attempt in range(200):
        candidate = f"VH-{code}-{(base_num + attempt):07d}"
        existing = await session.execute(select(Patient.id).where(Patient.vid == candidate))
        if not existing.scalar_one_or_none():
            return candidate
    return f"VH-{code}-{base_num:07d}-{uuid.uuid4().hex[:3]}"


async def run_domain_patients(
    session: AsyncSession, hospital: Hospital, branch_map: Dict[str, Branch], filepath: Path, dry_run: bool, conflict_mode: str
) -> Dict[str, int]:
    print(f"\n👥 [DOMAIN 12] Bulk Patients & Couple Linking — {filepath.name}")
    stats = {"created": 0, "updated": 0, "skipped": 0}
    couple_tracker: Dict[str, List[Patient]] = {}

    with open(filepath, mode="r", encoding="utf-8-sig") as f:
        reader = list(csv.DictReader(f))

    for r in reader:
        phone = s_get(r, "phone")
        p_name = s_get(r, "name")
        b_code = s_get(r, "branch_code").upper()
        target_branch = branch_map.get(b_code) or list(branch_map.values())[0]

        # Check existing by phone or email
        q_p = select(Patient).where(
            Patient.tenant_id == hospital.id,
            or_(Patient.phone == phone, Patient.email == (s_get(r, "email") or "dummy@none"))
        )
        res_p = await session.execute(q_p)
        existing_p = res_p.scalar_one_or_none()

        gender_str = s_get(r, "gender", "female").lower()
        gender_enum = getattr(Gender, gender_str.upper(), Gender.FEMALE)
        dob_val = datetime.strptime(s_get(r, "dob"), "%Y-%m-%d").date() if s_get(r, "dob") else None
        age_str = s_get(r, "age")
        age_val = int(age_str) if age_str and age_str.isdigit() else None

        c_code = s_get(r, "couple_code").upper()

        if existing_p:
            action = resolve_conflict(f"Patient '{existing_p.name}' ({phone})", conflict_mode)
            if action == "overwrite":
                existing_p.title = s_get(r, "title")
                existing_p.name = p_name
                existing_p.surname = s_get(r, "surname")
                existing_p.gender = gender_enum
                existing_p.age = age_val
                existing_p.dob = dob_val
                existing_p.blood_group = s_get(r, "blood_group")
                existing_p.marital_status = s_get(r, "marital_status", "married")
                existing_p.email = s_get(r, "email") or None
                existing_p.address = s_get(r, "address")
                existing_p.area = s_get(r, "area")
                existing_p.branch_id = target_branch.id
                existing_p.financial_type = s_get(r, "financial_type", "self_pay")
                existing_p.referring_doctor = s_get(r, "referring_doctor")
                existing_p.marketing_person_name = s_get(r, "marketing_person_name")
                if c_code:
                    couple_tracker.setdefault(c_code, []).append(existing_p)
                stats["updated"] += 1
                print(f"   🔄 Updated Patient: {existing_p.name} [{existing_p.vid}] ({phone})")
            else:
                if c_code:
                    couple_tracker.setdefault(c_code, []).append(existing_p)
                stats["skipped"] += 1
                print(f"   ⏭️  Skipped Patient: {existing_p.name} [{existing_p.vid}]")
        else:
            vid = await generate_vid(session, hospital.code)
            p_obj = Patient(
                tenant_id=hospital.id,
                branch_id=target_branch.id,
                vid=vid,
                registration_type=RegistrationType.PATIENT,
                title=s_get(r, "title"),
                name=p_name,
                surname=s_get(r, "surname"),
                gender=gender_enum,
                age=age_val,
                dob=dob_val,
                phone=phone,
                blood_group=s_get(r, "blood_group"),
                marital_status=s_get(r, "marital_status", "married"),
                identity_type="aadhaar",
                aadhaar_encrypted=encrypt_pii(s_get(r, "aadhaar_number")),
                email=s_get(r, "email") or None,
                address=s_get(r, "address"),
                area=s_get(r, "area"),
                financial_type=s_get(r, "financial_type", "self_pay"),
                referring_doctor=s_get(r, "referring_doctor"),
                marketing_person_name=s_get(r, "marketing_person_name"),
                tags=["Bulk Onboarded"],
            )
            session.add(p_obj)
            await session.flush()
            if c_code:
                couple_tracker.setdefault(c_code, []).append(p_obj)
            stats["created"] += 1
            print(f"   ✨ Created Patient: {p_name} ({p_obj.gender.value}) VID: {vid} (Branch: {target_branch.code})")

    # Establish Bidirectional Couple Links
    for c_code, members in couple_tracker.items():
        if len(members) >= 2:
            p1 = members[0]
            p2 = members[1]
            p1.partner_id = p2.id
            p2.partner_id = p1.id
            print(f"   💞 Linked Couple [{c_code}]: {p1.name} ({p1.vid}) ↔ {p2.name} ({p2.vid})")

    await session.flush()
    print(f"   📊 Patients Summary: Created={stats['created']} | Updated={stats['updated']} | Skipped={stats['skipped']}")
    return stats


# =====================================================================
# Domain 13: Cosmetic Gynaecology Procedures
# =====================================================================
async def run_domain_cosgyn(
    session: AsyncSession, hospital: Hospital, branch_map: Dict[str, Branch], filepath: Path, dry_run: bool, conflict_mode: str
) -> Dict[str, int]:
    print(f"\n🌸 [DOMAIN 13] Cosmetic Gynaecology Treatment Catalogs — {filepath.name}")
    stats = {"created": 0, "updated": 0, "skipped": 0}

    with open(filepath, mode="r", encoding="utf-8-sig") as f:
        reader = list(csv.DictReader(f))

    for r in reader:
        t_name = s_get(r, "name")
        b_code = s_get(r, "branch_code").upper()
        target_branch = branch_map.get(b_code) or list(branch_map.values())[0]

        q_c = select(CosgynTreatment).where(
            CosgynTreatment.name == t_name
        )
        res_c = await session.execute(q_c)
        existing_c = res_c.scalar_one_or_none()

        price = float(s_get(r, "price") or 0.0)

        if existing_c:
            action = resolve_conflict(f"CosGyn Treatment '{t_name}'", conflict_mode)
            if action == "overwrite":
                existing_c.package_combo = s_get(r, "package_combo")
                existing_c.jet_plasma_sessions = int(s_get(r, "jet_plasma_sessions") or 0)
                existing_c.jet_plasma_duration_mins = int(s_get(r, "jet_plasma_duration_mins") or 0)
                existing_c.tesla_chair_sessions = int(s_get(r, "tesla_chair_sessions") or 0)
                existing_c.tesla_chair_duration_mins = int(s_get(r, "tesla_chair_duration_mins") or 0)
                existing_c.prp_sessions = int(s_get(r, "prp_sessions") or 0)
                existing_c.price = price
                existing_c.tenant_id = hospital.id
                existing_c.branch_id = target_branch.id
                stats["updated"] += 1
                print(f"   🔄 Updated CosGyn Treatment: {t_name} [₹{price:,.2f}]")
            else:
                stats["skipped"] += 1
                print(f"   ⏭️  Skipped CosGyn Treatment: {t_name}")
        else:
            c_obj = CosgynTreatment(
                tenant_id=hospital.id,
                branch_id=target_branch.id,
                name=t_name,
                package_combo=s_get(r, "package_combo"),
                jet_plasma_sessions=int(s_get(r, "jet_plasma_sessions") or 0),
                jet_plasma_duration_mins=int(s_get(r, "jet_plasma_duration_mins") or 0),
                tesla_chair_sessions=int(s_get(r, "tesla_chair_sessions") or 0),
                tesla_chair_duration_mins=int(s_get(r, "tesla_chair_duration_mins") or 0),
                prp_sessions=int(s_get(r, "prp_sessions") or 0),
                price=price
            )
            session.add(c_obj)
            stats["created"] += 1
            print(f"   ✨ Created CosGyn Treatment: {t_name} [₹{price:,.2f}]")

    await session.flush()
    print(f"   📊 CosGyn Summary: Created={stats['created']} | Updated={stats['updated']} | Skipped={stats['skipped']}")
    return stats


# =====================================================================
# CLI Runner Entry Point
# =====================================================================
async def main_async():
    parser = argparse.ArgumentParser(
        description="VaidyaMD HMS — End-to-End Modular Multi-Domain Onboarding Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--env", choices=["local", "dev", "prod"], default="local", help="Target environment (default: local)")
    parser.add_argument("--database-url", type=str, default=None, help="Explicit database URL override")
    parser.add_argument("--all", action="store_true", help="Execute all 13 domains in sequence")
    parser.add_argument(
        "--domain",
        choices=[
            "core", "hospitals", "staff", "ipd", "treatment_cycles", "service_catalog",
            "billing", "packages", "protocols", "templates", "lims", "cryo",
            "pharmacy", "pharmacy_vendors", "pharmacy_stock", "patients", "cosgyn"
        ],
        help="Execute single domain"
    )
    parser.add_argument("--file", type=str, default=None, help="Custom CSV path override for the selected domain")
    parser.add_argument("--exclude-patients", action="store_true", help="Omit patient data onboarding (Domain 12)")
    parser.add_argument("--dry-run", action="store_true", help="Validate templates and dependencies without committing")
    parser.add_argument("--force-upsert", action="store_true", help="Automatically overwrite existing records without prompt")
    parser.add_argument("--skip-existing", action="store_true", help="Automatically skip existing records without prompt")
    parser.add_argument("--yes", action="store_true", help="Assume yes to all prompts (same as force-upsert)")

    args = parser.parse_args()

    if not args.all and not args.domain:
        print("❌ Error: Specify either '--all' to run all domains, or '--domain <name>' to run a single domain.")
        sys.exit(1)

    conflict_mode = "prompt"
    if args.force_upsert or args.yes:
        conflict_mode = "force-upsert"
    elif args.skip_existing:
        conflict_mode = "skip-existing"

    db_url = resolve_database_url(args.env, explicit_url=args.database_url, auto_confirm=True)
    engine = create_env_engine(args.env, explicit_url=args.database_url, auto_confirm=True)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    print("=" * 76)
    print("🏥  VaidyaMD HMS — End-to-End Hospital Onboarding Suite")
    print(f"🎯  Target Environment : {args.env.upper()}")
    print(f"🔗  Database Host      : {db_url.split('@')[-1] if '@' in db_url else db_url}")
    print(f"🛡️   Execution Mode     : {'DRY RUN (Simulated)' if args.dry_run else 'LIVE COMMIT'}")
    print(f"⚡  Conflict Handling  : {conflict_mode.upper()}")
    print("=" * 76)

    # Template file mapping helper
    def resolve_template(canonical_name: str) -> Path:
        if args.file:
            return Path(args.file)
        return TEMPLATES_DIR / canonical_name

    async with async_session() as session:
        try:
            # 1 & 2. Core (Hospitals & Staff)
            hosp_file = resolve_template("01_hospitals_and_branches.csv")
            staff_file = TEMPLATES_DIR / "02_staff_users.csv"
            if not staff_file.exists():
                staff_file = None

            hospital, branch_map, _ = await run_domain_core(session, hosp_file, staff_file, args.dry_run, conflict_mode)

            if args.domain in ("core", "hospitals", "staff"):
                if not args.dry_run:
                    await session.commit()
                print("\n✅ Core Domain completed successfully.")
                return

            # Domain 03: IPD
            if args.all or args.domain == "ipd":
                ipd_f = resolve_template("03_ipd_infrastructure.csv")
                await run_domain_ipd(session, hospital, branch_map, ipd_f, args.dry_run, conflict_mode)

            # Domain 04: Treatment Cycle Types
            if args.all or args.domain == "treatment_cycles":
                tc_f = resolve_template("04_treatment_cycle_types.csv")
                await run_domain_treatment_cycles(session, hospital, branch_map, tc_f, args.dry_run, conflict_mode)

            # Domain 05: Billing Service Catalog
            if args.all or args.domain == "service_catalog":
                sc_f = resolve_template("05_service_catalog.csv")
                await run_domain_service_catalog(session, hospital, branch_map, sc_f, args.dry_run, conflict_mode)

            # Domain 06: Billing Packages
            if args.all or args.domain in ("billing", "packages"):
                pkg_f = resolve_template("06_billing_packages.csv")
                await run_domain_billing_packages(session, hospital, branch_map, pkg_f, args.dry_run, conflict_mode)

            # Domain 07: Clinical Protocols
            if args.all or args.domain == "protocols":
                proto_f = resolve_template("07_clinical_protocols.csv")
                await run_domain_protocols(session, hospital, branch_map, proto_f, args.dry_run, conflict_mode)

            # Domain 08: Clinical Templates & Order Sets
            if args.all or args.domain == "templates":
                tmpl_f = resolve_template("08_clinical_templates.csv")
                await run_domain_clinical_templates(session, hospital, branch_map, tmpl_f, args.dry_run, conflict_mode)

            # Domain 09: LIMS Test Directory
            if args.all or args.domain == "lims":
                lims_f = resolve_template("09_lims_test_directory.csv")
                await run_domain_lims(session, hospital, branch_map, lims_f, args.dry_run, conflict_mode)

            # Domain 10: Cryo Infrastructure
            if args.all or args.domain == "cryo":
                cryo_f = resolve_template("10_cryo_infrastructure.csv")
                await run_domain_cryo(session, hospital, branch_map, cryo_f, args.dry_run, conflict_mode)

            # Domain 11: Pharmacy Formulary, Batches & Vendors (Separated 11a Vendors & 11b Stock)
            if args.all or args.domain in ("pharmacy", "pharmacy_vendors", "pharmacy_stock"):
                if args.domain == "pharmacy_vendors":
                    v_f = resolve_template("11a_pharmacy_vendors.csv")
                    await run_domain_pharmacy_vendors(session, hospital, branch_map, v_f, args.dry_run, conflict_mode)
                elif args.domain == "pharmacy_stock":
                    s_f = resolve_template("11b_pharmacy_stock.csv")
                    await run_domain_pharmacy_stock(session, hospital, branch_map, s_f, args.dry_run, conflict_mode)
                else:
                    v_f = resolve_template("11a_pharmacy_vendors.csv")
                    s_f = resolve_template("11b_pharmacy_stock.csv")
                    legacy_f = resolve_template("11_pharmacy_inventory.csv")
                    if args.file:
                        await run_domain_pharmacy(session, hospital, branch_map, Path(args.file), args.dry_run, conflict_mode)
                    else:
                        if v_f.exists():
                            await run_domain_pharmacy_vendors(session, hospital, branch_map, v_f, args.dry_run, conflict_mode)
                        if s_f.exists():
                            await run_domain_pharmacy_stock(session, hospital, branch_map, s_f, args.dry_run, conflict_mode)
                        if not v_f.exists() and not s_f.exists() and legacy_f.exists():
                            await run_domain_pharmacy(session, hospital, branch_map, legacy_f, args.dry_run, conflict_mode)

            # Domain 12: Patients Bulk
            if (args.all and not args.exclude_patients) or (args.domain == "patients" and not args.exclude_patients):
                pat_f = resolve_template("12_patients_bulk.csv")
                await run_domain_patients(session, hospital, branch_map, pat_f, args.dry_run, conflict_mode)
            elif args.exclude_patients and (args.all or args.domain == "patients"):
                print("\n" + "-" * 76)
                print("👥  Domain 12: Patients Bulk — SKIPPED (--exclude-patients specified)")
                print("-" * 76)

            # Domain 13: CosGyn
            if args.all or args.domain == "cosgyn":
                cosgyn_f = resolve_template("13_cosgyn_procedures.csv")
                await run_domain_cosgyn(session, hospital, branch_map, cosgyn_f, args.dry_run, conflict_mode)

            if args.dry_run:
                print("\n🔍 [DRY RUN] All domain templates validated successfully. No changes committed.")
                await session.rollback()
            else:
                await session.commit()
                print("\n" + "=" * 76)
                print("🎉  End-to-End Hospital Onboarding Suite Completed Successfully!")
                print(f"🏥  Tenant Active       : {hospital.name} ({hospital.code})")
                print(f"🏢  Branches Configured : {len(branch_map)} branches ({', '.join(branch_map.keys())})")
                print("=" * 76)

        except Exception as e:
            await session.rollback()
            print(f"\n❌ [ERROR] Onboarding failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
