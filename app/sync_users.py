"""
VaidyaMD HMS — User Sync Script
================================
SAFE: Only touches the `users`, `permission_profiles`, and `hospitals`/`branches` tables.
      Does NOT read or modify any patient data.

Logic:
  - For each canonical user, checks if email already exists.
  - If missing  -> inserts it.
  - If present  -> skips (preserves existing passwords / profile changes).
  - Prints a clear diff summary at the end.
"""

import asyncio
import os
import sys
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.core.models import (
    Hospital, Branch, PermissionProfile, User, UserRole,
)
from sqlalchemy import select


# ---------------------------------------------------------------------------
# Canonical user list - mirrors seed.py but safe to re-run at any time
# ---------------------------------------------------------------------------
CANONICAL_USERS = [
    {
        "email": "admin@vaidyamd.com",
        "name": "Dr. Vikram Vaidya",
        "role": UserRole.ADMIN,
        "specialization": "Medical Director & Senior Fertility Specialist",
        "is_doctor": True,
        "branch_code": "MAIN",
        "profile_name": "Administrator / Medical Director",
    },
    {
        "email": "meera.reddy@vaidyamd.com",
        "name": "Dr. Meera Reddy",
        "role": UserRole.DOCTOR,
        "specialization": "Senior Reproductive Endocrinologist & ART Specialist",
        "is_doctor": True,
        "branch_code": "MAIN",
        "profile_name": "Senior Reproductive Consultant",
    },
    {
        "email": "anand.kumar@vaidyamd.com",
        "name": "Dr. Anand Kumar",
        "role": UserRole.DOCTOR,
        "specialization": "Clinical Andrologist & Male Fertility Specialist",
        "is_doctor": True,
        "branch_code": "MAIN",
        "profile_name": "Senior Reproductive Consultant",
    },
    {
        "email": "rahul.nair@vaidyamd.com",
        "name": "Dr. Rahul Nair",
        "role": UserRole.EMBRYOLOGIST,
        "specialization": "Senior Clinical Embryologist",
        "is_doctor": False,
        "branch_code": "MAIN",
        "profile_name": "Senior Clinical Embryologist",
    },
    {
        "email": "pooja.sharma@vaidyamd.com",
        "name": "Dr. Pooja Sharma (Embryologist 2)",
        "role": UserRole.EMBRYOLOGIST,
        "specialization": "Clinical Embryologist & Witness Specialist",
        "is_doctor": False,
        "branch_code": "MAIN",
        "profile_name": "Senior Clinical Embryologist",
    },
    {
        "email": "nurse.sunita@vaidyamd.com",
        "name": "Sunita Rao",
        "role": UserRole.NURSE,
        "specialization": "Senior ART Coordinator Nurse",
        "is_doctor": False,
        "branch_code": "MAIN",
        "profile_name": "Fertility Nurse / Coordinator",
    },
    {
        "email": "accounts@vaidyamd.com",
        "name": "Ramesh Gupta",
        "role": UserRole.RECEPTIONIST,
        "specialization": "Front Desk & Financial Accounts Lead",
        "is_doctor": False,
        "branch_code": "MAIN",
        "profile_name": "Billing & Accounts Desk",
    },
    {
        "email": "pharmacy@vaidyamd.com",
        "name": "Priya Nair",
        "role": UserRole.PHARMA,
        "specialization": "Chief Pharmacist & Supply Chain In-Charge",
        "is_doctor": False,
        "branch_code": "MAIN",
        "profile_name": "Billing & Accounts Desk",
    },
    {
        "email": "admin.ops@vaidyamd.com",
        "name": "Suresh Kumar",
        "role": UserRole.ADMIN,
        "specialization": "Hospital Operations & IT Administrator",
        "is_doctor": False,
        "branch_code": "MAIN",
        "profile_name": "Administrator / Medical Director",
    },
    {
        "email": "counsellor@vaidyamd.com",
        "name": "Ananya Sen",
        "role": UserRole.COUNSELLOR,
        "specialization": "Lead Fertility & Pre-ART Clinical Counselor",
        "is_doctor": False,
        "branch_code": "MAIN",
        "profile_name": "Fertility Nurse / Coordinator",
    },
]

DEFAULT_PASSWORD = os.getenv("DEFAULT_USER_PASSWORD", "vaidya_md_2026")


async def sync_users():
    print("=" * 60)
    print("  VaidyaMD HMS — User Sync (USERS ONLY, NO PATIENT DATA)")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        # Load hospital
        hospital_result = await db.execute(select(Hospital).limit(1))
        hospital = hospital_result.scalar_one_or_none()
        if not hospital:
            print("ERROR: No hospital found in database. Run base seed first.")
            sys.exit(1)
        print(f"\n  Hospital: {hospital.name} ({hospital.id})")

        # Load branches
        branch_result = await db.execute(
            select(Branch).where(Branch.hospital_id == hospital.id)
        )
        branches = {b.code: b for b in branch_result.scalars().all()}
        print(f"  Branches: {list(branches.keys())}")

        # Load permission profiles
        profile_result = await db.execute(
            select(PermissionProfile).where(PermissionProfile.hospital_id == hospital.id)
        )
        profiles = {p.name: p for p in profile_result.scalars().all()}
        print(f"  Permission Profiles: {list(profiles.keys())}")

        # Load existing users (by email)
        existing_result = await db.execute(
            select(User).where(User.tenant_id == hospital.id)
        )
        existing_users = {u.email: u for u in existing_result.scalars().all()}

        print(f"\n  Existing users in DB ({len(existing_users)}):")
        for email, u in existing_users.items():
            print(f"    CHECK  {u.name} <{email}>  [{u.role.value}]  active={u.is_active}")

        # Sync
        pwd_hash = hash_password(DEFAULT_PASSWORD)
        added = []
        skipped = []

        print(f"\n  Syncing {len(CANONICAL_USERS)} canonical users...")
        for spec in CANONICAL_USERS:
            email = spec["email"]
            if email in existing_users:
                skipped.append(email)
                print(f"    SKIP  {email}  (already exists)")
                continue

            branch = branches.get(spec["branch_code"])
            if not branch:
                print(f"    WARN  {email} - branch '{spec['branch_code']}' not found, using first available")
                branch = next(iter(branches.values()), None)

            profile = profiles.get(spec["profile_name"])
            if not profile:
                print(f"    WARN  {email} - profile '{spec['profile_name']}' not found, leaving null")

            new_user = User(
                email=email,
                name=spec["name"],
                role=spec["role"],
                password_hash=pwd_hash,
                specialization=spec["specialization"],
                is_doctor=spec["is_doctor"],
                is_active=True,
                tenant_id=hospital.id,
                branch_id=branch.id if branch else None,
                permission_profile_id=profile.id if profile else None,
            )
            db.add(new_user)
            added.append(email)
            print(f"    ADD   {spec['name']} <{email}>  [{spec['role'].value}]")

        await db.commit()

        print("\n" + "=" * 60)
        print(f"  DONE - Added: {len(added)}   Skipped (already present): {len(skipped)}")
        if added:
            print(f"  New users added with default password: {DEFAULT_PASSWORD!r}")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(sync_users())
