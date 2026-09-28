"""
VaidyaMD HMS — Zero-Downtime Multi-Tenant Hospital Onboarding Engine
Reads hospital, branch, and staff records from a standardized CSV and securely
provisions them into the target database environment.

Usage:
  python scripts/db/onboard_hospital.py --env local --file scripts/db/templates/hospital_onboarding_template.csv
  python scripts/db/onboard_hospital.py --env dev --file /path/to/hospital.csv
  python scripts/db/onboard_hospital.py --env prod --file /path/to/hospital.csv --yes
  python scripts/db/onboard_hospital.py --env local --dry-run
"""

import sys
import os
import csv
import argparse
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Setup sys.path so scripts can be executed from workspace root or scripts/ folder
BASE_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = BASE_DIR / "VaidyaMD_HMS_Backend"
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BASE_DIR))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# Import backend domain models & security
from app.core.database import Base
from app.core.models.tenant import Hospital
from app.core.models.branch import Branch
from app.core.models.permission_profile import PermissionProfile
from app.core.models.user import User, UserRole
from app.core.security import hash_password
from scripts.db.env_resolver import create_env_engine, resolve_database_url


# Standard RBAC Permission Profiles with fine-grained menu permissions
STANDARD_PROFILES = [
    {
        "name": "Administrator / Medical Director",
        "description": "Full clinical, administrative, lab, and financial permissions",
        "menu_permissions": {
            "patients": True, "patient_register": True, "patient_360": True,
            "treatment_cycles": True, "ivf_lab": True, "cryopreservation": True,
            "billing": True, "wallet": True, "analytics": True, "pharmacy": True, "settings": True,
            "appointments": True, "counseling": True, "ipd": True, "lims": True, "cosgyn": True
        },
        "role_matches": ["admin"]
    },
    {
        "name": "Doctor / Consultant",
        "description": "Full clinical, ultrasound, cycle wizard, and patient EMR access",
        "menu_permissions": {
            "patients": True, "patient_register": True, "patient_360": True,
            "treatment_cycles": True, "ivf_lab": True, "cryopreservation": True,
            "billing": True, "wallet": True, "analytics": True, "pharmacy": True, "settings": False,
            "appointments": True, "counseling": True, "ipd": True, "lims": True, "cosgyn": True
        },
        "role_matches": ["doctor"]
    },
    {
        "name": "Clinical Embryologist",
        "description": "IVF Lab culture matrix, dual-witnessing gates, CASA, and cryobank coordinates",
        "menu_permissions": {
            "patients": True, "patient_register": False, "patient_360": True,
            "treatment_cycles": True, "ivf_lab": True, "cryopreservation": True,
            "billing": False, "wallet": False, "analytics": True, "pharmacy": False, "settings": False,
            "appointments": True, "counseling": False, "ipd": False, "lims": True, "cosgyn": False
        },
        "role_matches": ["embryologist", "andrologist"]
    },
    {
        "name": "Fertility Nurse / Coordinator",
        "description": "Patient intake, medication schedule administration, and vitals",
        "menu_permissions": {
            "patients": True, "patient_register": True, "patient_360": True,
            "treatment_cycles": True, "ivf_lab": False, "cryopreservation": False,
            "billing": False, "wallet": False, "analytics": False, "pharmacy": True, "settings": False,
            "appointments": True, "counseling": True, "ipd": True, "lims": False, "cosgyn": True
        },
        "role_matches": ["nurse", "scanning"]
    },
    {
        "name": "Clinical Counsellor",
        "description": "Psychological counseling, couple therapy, and fertility treatment consent walkthroughs",
        "menu_permissions": {
            "patients": True, "patient_register": True, "patient_360": True,
            "treatment_cycles": True, "ivf_lab": False, "cryopreservation": False,
            "billing": False, "wallet": False, "analytics": False, "pharmacy": False, "settings": False,
            "appointments": True, "counseling": True, "ipd": False, "lims": False, "cosgyn": False
        },
        "role_matches": ["counsellor"]
    },
    {
        "name": "Billing & Accounts Desk",
        "description": "Multi-source invoicing, advance wallets, receipts, and payment settlements",
        "menu_permissions": {
            "patients": True, "patient_register": True, "patient_360": True,
            "treatment_cycles": False, "ivf_lab": False, "cryopreservation": False,
            "billing": True, "wallet": True, "analytics": True, "pharmacy": False, "settings": False,
            "appointments": True, "counseling": False, "ipd": True, "lims": False, "cosgyn": True
        },
        "role_matches": ["accounts", "manager"]
    },
    {
        "name": "Front Desk Receptionist",
        "description": "Patient registration, appointment scheduling, and front-desk visitor flow",
        "menu_permissions": {
            "patients": True, "patient_register": True, "patient_360": True,
            "treatment_cycles": False, "ivf_lab": False, "cryopreservation": False,
            "billing": True, "wallet": False, "analytics": False, "pharmacy": False, "settings": False,
            "appointments": True, "counseling": False, "ipd": True, "lims": False, "cosgyn": True
        },
        "role_matches": ["receptionist"]
    },
    {
        "name": "Lead Pharmacist",
        "description": "Formulary management, dispensing, batch control, and inventory levels",
        "menu_permissions": {
            "patients": True, "patient_register": False, "patient_360": False,
            "treatment_cycles": False, "ivf_lab": False, "cryopreservation": False,
            "billing": False, "wallet": False, "analytics": False, "pharmacy": True, "settings": False,
            "appointments": False, "counseling": False, "ipd": False, "lims": False, "cosgyn": False
        },
        "role_matches": ["pharma"]
    }
]


def parse_csv_file(csv_path: Path) -> List[Dict[str, str]]:
    """Reads and validates the CSV structure."""
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found at: {csv_path}")

    records = []
    with open(csv_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        required_headers = {"record_type", "name", "email"}
        if not required_headers.issubset(set(reader.fieldnames or [])):
            raise ValueError(
                f"CSV must contain headers: {required_headers}. Found: {reader.fieldnames}"
            )
        for row in reader:
            # Strip whitespace
            clean_row = {k.strip(): (v.strip() if v else "") for k, v in row.items() if k}
            if clean_row.get("record_type"):
                records.append(clean_row)

    return records


async def onboard_tenant(
    env_name: str,
    csv_path: Path,
    explicit_url: Optional[str] = None,
    auto_confirm: bool = False,
    dry_run: bool = False,
):
    resolved_url = resolve_database_url(env_name, explicit_url, auto_confirm)
    
    # Mask password for display
    display_url = resolved_url
    if "@" in display_url and ":" in display_url.split("@")[0]:
        parts = display_url.split("@")
        prefix = parts[0]
        user_part = prefix.split("://")[1].split(":")[0]
        display_url = f"{prefix.split('://')[0]}://{user_part}:****@{parts[1]}"

    print("\n" + "=" * 80)
    print("🏥  VaidyaMD HMS — Hospital & Tenant Onboarding Engine")
    print(f"🎯 Target Environment : {env_name.upper()}")
    print(f"🔗 Target Database    : {display_url}")
    print(f"📄 Input CSV File     : {csv_path}")
    print(f"🔍 Dry Run Mode       : {'YES (Simulation only)' if dry_run else 'NO (Live Execution)'}")
    print("=" * 80)

    records = parse_csv_file(csv_path)
    hospital_records = [r for r in records if r["record_type"].upper() == "HOSPITAL"]
    branch_records = [r for r in records if r["record_type"].upper() == "BRANCH"]
    staff_records = [r for r in records if r["record_type"].upper() == "STAFF"]

    if not hospital_records:
        raise ValueError("No HOSPITAL record found in CSV. At least one HOSPITAL is required.")

    print(f"\n📋 Parsed CSV Summary:")
    print(f"  • Hospitals to onboard : {len(hospital_records)}")
    print(f"  • Branches to register : {len(branch_records)}")
    print(f"  • Staff users to seed  : {len(staff_records)}")

    if dry_run:
        print("\n[DRY RUN] Inspection:")
        for h in hospital_records:
            print(f"  [HOSPITAL] {h.get('name')} (Code: {h.get('code')}, Email: {h.get('email')})")
        for b in branch_records:
            print(f"  [BRANCH]   {b.get('name')} (Code: {b.get('code')}, Main: {b.get('is_main_branch')})")
        for s in staff_records:
            print(f"  [STAFF]    {s.get('name')} (Email: {s.get('email')}, Role: {s.get('role')}, Branch: {s.get('branch_code')})")
        print("\n✅ Dry run completed successfully. No changes made to database.")
        return

    engine = create_env_engine(env_name, explicit_url, auto_confirm)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    try:
        async with session_factory() as session:
            # 1. Process Hospitals
            hospital_map = {}  # code -> Hospital object
            for h_row in hospital_records:
                h_name = h_row.get("name")
                h_code = h_row.get("code")
                h_email = h_row.get("email")
                h_phone = h_row.get("phone")
                h_address = h_row.get("address")
                plugins_raw = h_row.get("active_plugins", "fertility,opd")
                active_plugins = [p.strip() for p in plugins_raw.split(",") if p.strip()]

                res = await session.execute(select(Hospital).where(Hospital.code == h_code))
                hospital = res.scalar_one_or_none()

                if hospital:
                    print(f"  ℹ️ Hospital with code '{h_code}' already exists: {hospital.name} ({hospital.id})")
                else:
                    hospital = Hospital(
                        name=h_name,
                        code=h_code,
                        email=h_email,
                        phone=h_phone,
                        address=h_address,
                        active_plugins=active_plugins,
                        is_active=True
                    )
                    session.add(hospital)
                    await session.flush()
                    print(f"  ✅ Created Hospital: {hospital.name} [ID: {hospital.id}, Code: {hospital.code}]")

                hospital_map[h_code] = hospital

            # Primary hospital for branch and staff associations
            primary_hospital = list(hospital_map.values())[0]

            # 2. Ensure Standard Permission Profiles for the Hospital
            profile_map = {}  # role_str -> profile_id
            for p_def in STANDARD_PROFILES:
                res = await session.execute(
                    select(PermissionProfile).where(
                        PermissionProfile.hospital_id == primary_hospital.id,
                        PermissionProfile.name == p_def["name"]
                    )
                )
                profile = res.scalar_one_or_none()
                if not profile:
                    profile = PermissionProfile(
                        hospital_id=primary_hospital.id,
                        name=p_def["name"],
                        description=p_def["description"],
                        menu_permissions=p_def["menu_permissions"],
                        is_active=True
                    )
                    session.add(profile)
                    await session.flush()
                    print(f"  🛡️  Created Permission Profile: {profile.name}")
                else:
                    print(f"  🛡️  Found Existing Permission Profile: {profile.name}")

                for role_match in p_def["role_matches"]:
                    profile_map[role_match] = profile.id

            # 3. Process Branches
            branch_map = {}  # code -> Branch object
            for b_row in branch_records:
                b_name = b_row.get("name")
                b_code = b_row.get("code")
                b_email = b_row.get("email")
                b_phone = b_row.get("phone")
                b_address = b_row.get("address")
                is_main = str(b_row.get("is_main_branch", "")).strip().lower() in ["true", "1", "yes"]

                res = await session.execute(
                    select(Branch).where(
                        Branch.hospital_id == primary_hospital.id,
                        Branch.code == b_code
                    )
                )
                branch = res.scalar_one_or_none()

                if branch:
                    print(f"  ℹ️ Branch with code '{b_code}' already exists: {branch.name} ({branch.id})")
                else:
                    branch = Branch(
                        hospital_id=primary_hospital.id,
                        name=b_name,
                        code=b_code,
                        email=b_email,
                        phone=b_phone,
                        address=b_address,
                        is_main_branch=is_main,
                        ip_whitelist=["0.0.0.0/0"],
                        is_active=True
                    )
                    session.add(branch)
                    await session.flush()
                    print(f"  🏢 Created Branch: {branch.name} [Code: {branch.code}, Main: {is_main}]")

                branch_map[b_code] = branch

            # Fallback main branch if none defined
            main_branch_id = None
            if branch_map:
                for b in branch_map.values():
                    if b.is_main_branch:
                        main_branch_id = b.id
                        break
                if not main_branch_id:
                    main_branch_id = list(branch_map.values())[0].id

            # 4. Process Staff Users
            created_users_count = 0
            for s_row in staff_records:
                s_name = s_row.get("name")
                s_email = s_row.get("email")
                s_role_raw = s_row.get("role", "doctor").lower().strip()
                s_spec = s_row.get("specialization", "")
                s_phone = s_row.get("phone", "")
                s_is_doc = str(s_row.get("is_doctor", "")).strip().lower() in ["true", "1", "yes"]
                s_bcode = s_row.get("branch_code", "")
                s_pwd = s_row.get("temp_password") or "VaidyaTemp2026!"

                # Role parsing
                try:
                    user_role = UserRole(s_role_raw)
                except ValueError:
                    user_role = UserRole.DOCTOR

                # Branch assignment
                assigned_branch_id = main_branch_id
                if s_bcode and s_bcode in branch_map:
                    assigned_branch_id = branch_map[s_bcode].id

                # Profile assignment
                profile_id = profile_map.get(s_role_raw)

                # Check existing user
                res = await session.execute(select(User).where(User.email == s_email))
                user = res.scalar_one_or_none()

                if user:
                    print(f"  ℹ️ User with email '{s_email}' already exists. Skipping.")
                else:
                    pwd_hash = hash_password(s_pwd)
                    user = User(
                        tenant_id=primary_hospital.id,
                        branch_id=assigned_branch_id,
                        permission_profile_id=profile_id,
                        name=s_name,
                        email=s_email,
                        password_hash=pwd_hash,
                        role=user_role,
                        is_doctor=s_is_doc,
                        specialization=s_spec,
                        phone=s_phone,
                        is_active=True
                    )
                    session.add(user)
                    created_users_count += 1
                    print(f"  👤 Created User: {user.name} ({user.email}) -> Role: {user.role.value}")

            # Commit all additions
            await session.commit()

        print("\n" + "=" * 80)
        print("🎉 ONBOARDING COMPLETED SUCCESSFULLY!")
        print(f"  • Hospital   : {primary_hospital.name} ({primary_hospital.code})")
        print(f"  • Branches   : {len(branch_map)} active branches")
        print(f"  • New Users  : {created_users_count} credentials created")
        print("=" * 80 + "\n")

    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="VaidyaMD HMS — Hospital & Staff Onboarding Tool")
    parser.add_argument(
        "--env",
        choices=["local", "dev", "prod"],
        default="local",
        help="Target environment (default: local)",
    )
    parser.add_argument(
        "--file",
        default=str(BASE_DIR / "scripts" / "db" / "templates" / "01_hospitals_and_branches.csv"),
        help="Path to hospital onboarding CSV file",
    )
    parser.add_argument(
        "--database-url",
        dest="database_url",
        default=None,
        help="Explicit database connection URL override",
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Bypass interactive confirmation prompt when targeting prod",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate CSV without executing database transactions",
    )

    args = parser.parse_args()
    csv_path = Path(args.file).resolve()

    asyncio.run(
        onboard_tenant(
            env_name=args.env,
            csv_path=csv_path,
            explicit_url=args.database_url,
            auto_confirm=args.yes,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
