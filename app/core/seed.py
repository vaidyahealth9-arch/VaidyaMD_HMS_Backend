"""
VaidyaMD HMS — Dual-Mode Production & Demonstration Database Seeder

Usage:
  Production Base Seed (Hospital, Branches, Users, Protocols, Packages - ZERO patients):
    python -m app.core.seed --mode base
    (or FORCE_DROP_DB=true python -m app.core.seed --mode base)

  Development Demo Seed (Base data + 5 Full Fertility Couples, Cycles, Lab & Billing):
    python -m app.core.seed --mode demo
    (or FORCE_DROP_DB=true python -m app.core.seed --mode demo)
"""

import asyncio
import os
import sys
import argparse
import uuid
from decimal import Decimal
from datetime import datetime, date, timedelta
from app.config import settings
from app.core.security import hash_password
from app.core.database import engine, Base, AsyncSessionLocal
from app.core.models import (
    Hospital, Branch, PermissionProfile, User, UserRole,
    Patient, Gender, RegistrationType,
    Appointment, AppointmentStatus, Invoice, InvoiceStatus,
    TreatmentPackage, Notification, NotificationType,
    ClinicalRecord, ClinicalTemplate,
    TreatmentCycle, TreatmentCycleStatus,
    TreatmentCycleType,
    ProtocolTemplate, ProtocolDrugRule,
    OocyteRecord, EmbryologyWitness,
    CryoSample, CryoSampleStatus,
    PatientWallet, WalletTransaction, WalletTxType,
)


async def seed_base(db):
    """
    Seeds production-ready hospital-level metadata:
    - Hospital / Tenant
    - Clinic Branches
    - Dynamic Permission Profiles (RBAC)
    - Staff Directory Users
    - Protocol Templates & Medication Rules Engine
    - Treatment Packages Catalog
    - Standard System Templates
    (ZERO patient data)
    """
    print("  [1/2] Seeding clinic & hospital level base infrastructure...")

    # 1. Hospital / Tenant
    hospital = Hospital(
        name="VaidyaMD Fertility & ART Centre",
        code="VMD01",
        address="Plot 123, Road No. 36, Jubilee Hills, Hyderabad, Telangana - 500033",
        phone="+91-40-23456789",
        email="admin@vaidyamd.com",
        logo_url="https://vaidyamd.com/logo.png",
        active_plugins=["fertility", "opd"],
        is_active=True,
    )
    db.add(hospital)
    await db.flush()

    # 2. Clinic Branches
    main_branch = Branch(
        hospital_id=hospital.id,
        name="Jubilee Hills Main Clinic",
        code="MAIN",
        address="Plot 123, Road 36, Jubilee Hills, Hyderabad",
        phone="+91-40-23456789",
        email="jubilee@vaidyamd.com",
        ip_whitelist=["0.0.0.0/0", "::/0", "127.0.0.1", "192.168.1.0/24", "10.0.0.0/16"],
        is_main_branch=True,
        is_active=True,
    )
    satellite_branch = Branch(
        hospital_id=hospital.id,
        name="HITEC City Satellite Clinic",
        code="HITEC",
        address="Cyber Towers Area, HITEC City, Hyderabad",
        phone="+91-40-87654321",
        email="hitec@vaidyamd.com",
        ip_whitelist=["0.0.0.0/0", "::/0", "127.0.0.1", "192.168.2.0/24"],
        is_main_branch=False,
        is_active=True,
    )
    gachibowli_branch = Branch(
        hospital_id=hospital.id,
        name="Gachibowli ART Centre",
        code="GACH",
        address="Financial District, Gachibowli, Hyderabad",
        phone="+91-40-99887766",
        email="gachibowli@vaidyamd.com",
        ip_whitelist=["0.0.0.0/0", "::/0", "127.0.0.1", "10.50.0.0/16"],
        is_main_branch=False,
        is_active=True,
    )
    db.add_all([main_branch, satellite_branch, gachibowli_branch])
    await db.flush()

    # 3. Dynamic RBAC Permission Profiles
    admin_profile = PermissionProfile(
        hospital_id=hospital.id,
        name="Administrator / Medical Director",
        description="Full clinical, administrative, lab, and financial permissions",
        menu_permissions={
            "patients": True, "patient_register": True, "patient_360": True,
            "treatment_cycles": True, "ivf_lab": True, "cryopreservation": True,
            "billing": True, "wallet": True, "analytics": True, "pharmacy": True, "settings": True
        },
        is_active=True,
    )
    doctor_profile = PermissionProfile(
        hospital_id=hospital.id,
        name="Senior Reproductive Consultant",
        description="Full clinical, ultrasound, cycle wizard, and patient EMR access",
        menu_permissions={
            "patients": True, "patient_register": True, "patient_360": True,
            "treatment_cycles": True, "ivf_lab": True, "cryopreservation": True,
            "billing": True, "wallet": True, "analytics": True, "pharmacy": True, "settings": False
        },
        is_active=True,
    )
    embryologist_profile = PermissionProfile(
        hospital_id=hospital.id,
        name="Senior Clinical Embryologist",
        description="IVF Lab culture matrix, dual-witnessing gates, CASA, and cryobank coordinates",
        menu_permissions={
            "patients": True, "patient_register": False, "patient_360": True,
            "treatment_cycles": True, "ivf_lab": True, "cryopreservation": True,
            "billing": False, "wallet": False, "analytics": True, "pharmacy": False, "settings": False
        },
        is_active=True,
    )
    nurse_profile = PermissionProfile(
        hospital_id=hospital.id,
        name="Fertility Nurse / Coordinator",
        description="Patient intake, medication schedule administration, and vitals",
        menu_permissions={
            "patients": True, "patient_register": True, "patient_360": True,
            "treatment_cycles": True, "ivf_lab": False, "cryopreservation": False,
            "billing": False, "wallet": False, "analytics": False, "pharmacy": True, "settings": False
        },
        is_active=True,
    )
    accounts_profile = PermissionProfile(
        hospital_id=hospital.id,
        name="Billing & Accounts Desk",
        description="Multi-source invoicing, advance wallets, receipts, and payment settlements",
        menu_permissions={
            "patients": True, "patient_register": True, "patient_360": True,
            "treatment_cycles": False, "ivf_lab": False, "cryopreservation": False,
            "billing": True, "wallet": True, "analytics": True, "pharmacy": False, "settings": False
        },
        is_active=True,
    )
    db.add_all([admin_profile, doctor_profile, embryologist_profile, nurse_profile, accounts_profile])
    await db.flush()

    # 4. Staff Directory Users
    default_pwd_hash = hash_password("vaidya_md_2026")

    users = [
        User(
            email="admin@vaidyamd.com",
            name="Dr. Vikram Vaidya",
            role=UserRole.ADMIN,
            password_hash=default_pwd_hash,
            specialization="Medical Director & Senior Fertility Specialist",
            is_doctor=True,
            is_active=True,
            tenant_id=hospital.id,
            branch_id=main_branch.id,
            permission_profile_id=admin_profile.id,
        ),
        User(
            email="meera.reddy@vaidyamd.com",
            name="Dr. Meera Reddy",
            role=UserRole.DOCTOR,
            password_hash=default_pwd_hash,
            specialization="Senior Reproductive Endocrinologist & ART Specialist",
            is_doctor=True,
            is_active=True,
            tenant_id=hospital.id,
            branch_id=main_branch.id,
            permission_profile_id=doctor_profile.id,
        ),
        User(
            email="anand.kumar@vaidyamd.com",
            name="Dr. Anand Kumar",
            role=UserRole.DOCTOR,
            password_hash=default_pwd_hash,
            specialization="Clinical Andrologist & Male Fertility Specialist",
            is_doctor=True,
            is_active=True,
            tenant_id=hospital.id,
            branch_id=main_branch.id,
            permission_profile_id=doctor_profile.id,
        ),
        User(
            email="rahul.nair@vaidyamd.com",
            name="Dr. Rahul Nair",
            role=UserRole.EMBRYOLOGIST,
            password_hash=default_pwd_hash,
            specialization="Senior Clinical Embryologist",
            is_doctor=False,
            is_active=True,
            tenant_id=hospital.id,
            branch_id=main_branch.id,
            permission_profile_id=embryologist_profile.id,
        ),
        User(
            email="pooja.sharma@vaidyamd.com",
            name="Dr. Pooja Sharma (Embryologist 2)",
            role=UserRole.EMBRYOLOGIST,
            password_hash=default_pwd_hash,
            specialization="Clinical Embryologist & Witness Specialist",
            is_doctor=False,
            is_active=True,
            tenant_id=hospital.id,
            branch_id=main_branch.id,
            permission_profile_id=embryologist_profile.id,
        ),
        User(
            email="nurse.sunita@vaidyamd.com",
            name="Sunita Rao",
            role=UserRole.NURSE,
            password_hash=default_pwd_hash,
            specialization="Senior ART Coordinator Nurse",
            is_doctor=False,
            is_active=True,
            tenant_id=hospital.id,
            branch_id=main_branch.id,
            permission_profile_id=nurse_profile.id,
        ),
        User(
            email="accounts@vaidyamd.com",
            name="Ramesh Gupta",
            role=UserRole.RECEPTIONIST,
            password_hash=default_pwd_hash,
            specialization="Front Desk & Financial Accounts Lead",
            is_doctor=False,
            is_active=True,
            tenant_id=hospital.id,
            branch_id=main_branch.id,
            permission_profile_id=accounts_profile.id,
        ),
        User(
            email="pharmacy@vaidyamd.com",
            name="Priya Nair",
            role=UserRole.PHARMA,
            password_hash=default_pwd_hash,
            specialization="Chief Pharmacist & Supply Chain In-Charge",
            is_doctor=False,
            is_active=True,
            tenant_id=hospital.id,
            branch_id=main_branch.id,
            permission_profile_id=accounts_profile.id,
        ),
        User(
            email="admin.ops@vaidyamd.com",
            name="Suresh Kumar",
            role=UserRole.ADMIN,
            password_hash=default_pwd_hash,
            specialization="Hospital Operations & IT Administrator",
            is_doctor=False,
            is_active=True,
            tenant_id=hospital.id,
            branch_id=main_branch.id,
            permission_profile_id=admin_profile.id,
        ),
        User(
            email="counsellor@vaidyamd.com",
            name="Ananya Sen",
            role=UserRole.COUNSELLOR,
            password_hash=default_pwd_hash,
            specialization="Lead Fertility & Pre-ART Clinical Counselor",
            is_doctor=False,
            is_active=True,
            tenant_id=hospital.id,
            branch_id=main_branch.id,
            permission_profile_id=nurse_profile.id,
        ),
    ]
    db.add_all(users)
    await db.flush()

    doc_meera = users[1]

    # 5. Protocol Library Templates & Drug Rules
    # --- Protocol: Antag ---
    antag_proto = ProtocolTemplate(
        hospital_id=hospital.id,
        name="Antag",
        category="stimulation",
        description="Auto-imported protocol from Excel",
        is_active=True,
        created_by=doc_meera.id,
    )
    db.add(antag_proto)
    await db.flush()
    db.add(ProtocolDrugRule(protocol_template_id=antag_proto.id, drug_name="Follisurge", dose="175 IU", frequency="OD", sentinel_anchor="stim_start", day_start_offset=2, day_end_offset=12, sort_order=1))
    db.add(ProtocolDrugRule(protocol_template_id=antag_proto.id, drug_name="Cetrolix", dose="0.25 mg", frequency="OD", sentinel_anchor="stim_start", day_start_offset=7, day_end_offset=11, sort_order=2))
    db.add(ProtocolDrugRule(protocol_template_id=antag_proto.id, drug_name="Coriosurge", dose="10000 IU", frequency="OD", sentinel_anchor="stim_start", day_start_offset=12, day_end_offset=31, sort_order=3))
    db.add(ProtocolDrugRule(protocol_template_id=antag_proto.id, drug_name="Cetrotide", dose="0.25 mg", frequency="OD", sentinel_anchor="stim_start", day_start_offset=12, day_end_offset=12, sort_order=4))
    db.add(ProtocolDrugRule(protocol_template_id=antag_proto.id, drug_name="Dubagest", dose="400 mg", frequency="BD", sentinel_anchor="stim_start", day_start_offset=14, day_end_offset=31, sort_order=5))
    db.add(ProtocolDrugRule(protocol_template_id=antag_proto.id, drug_name="DUPHASTON", dose="10 mg", frequency="TDS", sentinel_anchor="stim_start", day_start_offset=14, day_end_offset=31, sort_order=6))
    db.add(ProtocolDrugRule(protocol_template_id=antag_proto.id, drug_name="INJ PROLUTON DEPOT", dose="500 mg", frequency="OD", sentinel_anchor="stim_start", day_start_offset=17, day_end_offset=31, sort_order=7))
    db.add(ProtocolDrugRule(protocol_template_id=antag_proto.id, drug_name="Decapeptyl", dose="0.1 mg", frequency="BD", sentinel_anchor="stim_start", day_start_offset=17, day_end_offset=17, sort_order=8))
    db.add(ProtocolDrugRule(protocol_template_id=antag_proto.id, drug_name="Gestone", dose="100 mg", frequency="OD", sentinel_anchor="stim_start", day_start_offset=18, day_end_offset=31, sort_order=9))
    # --- Protocol: 21 day  HRT FET ---
    day_21_hrt_fet_proto = ProtocolTemplate(
        hospital_id=hospital.id,
        name="21 day  HRT FET",
        category="fet",
        description="Auto-imported protocol from Excel",
        is_active=True,
        created_by=doc_meera.id,
    )
    db.add(day_21_hrt_fet_proto)
    await db.flush()
    db.add(ProtocolDrugRule(protocol_template_id=day_21_hrt_fet_proto.id, drug_name="Enrifol 2 mg", dose="2 mg", frequency="BD", sentinel_anchor="stim_start", day_start_offset=1, day_end_offset=5, sort_order=1))
    db.add(ProtocolDrugRule(protocol_template_id=day_21_hrt_fet_proto.id, drug_name="Endokine", dose="6 IU", frequency="OD", sentinel_anchor="stim_start", day_start_offset=2, day_end_offset=31, sort_order=2))
    db.add(ProtocolDrugRule(protocol_template_id=day_21_hrt_fet_proto.id, drug_name="Enrifol 2 mg", dose="2 mg", frequency="TDS", sentinel_anchor="stim_start", day_start_offset=6, day_end_offset=31, sort_order=3))
    db.add(ProtocolDrugRule(protocol_template_id=day_21_hrt_fet_proto.id, drug_name="Dubagest", dose="400 mg", frequency="BD", sentinel_anchor="stim_start", day_start_offset=14, day_end_offset=31, sort_order=4))
    db.add(ProtocolDrugRule(protocol_template_id=day_21_hrt_fet_proto.id, drug_name="DUPHASTON", dose="10 mg", frequency="TDS", sentinel_anchor="stim_start", day_start_offset=14, day_end_offset=31, sort_order=5))
    db.add(ProtocolDrugRule(protocol_template_id=day_21_hrt_fet_proto.id, drug_name="Coriosurge", dose="10000 IU", frequency="OD", sentinel_anchor="stim_start", day_start_offset=17, day_end_offset=31, sort_order=6))
    db.add(ProtocolDrugRule(protocol_template_id=day_21_hrt_fet_proto.id, drug_name="INJ PROLUTON DEPOT", dose="500 mg", frequency="OD", sentinel_anchor="stim_start", day_start_offset=17, day_end_offset=31, sort_order=7))
    db.add(ProtocolDrugRule(protocol_template_id=day_21_hrt_fet_proto.id, drug_name="Decapeptyl", dose="0.1 mg", frequency="BD", sentinel_anchor="stim_start", day_start_offset=17, day_end_offset=17, sort_order=8))
    # --- Protocol: DAY 21 LDR ANTAG ---
    day_21_ldr_antag_proto = ProtocolTemplate(
        hospital_id=hospital.id,
        name="DAY 21 LDR ANTAG",
        category="stimulation",
        description="Auto-imported protocol from Excel",
        is_active=True,
        created_by=doc_meera.id,
    )
    db.add(day_21_ldr_antag_proto)
    await db.flush()
    db.add(ProtocolDrugRule(protocol_template_id=day_21_ldr_antag_proto.id, drug_name="Follisurge", dose="175 IU", frequency="OD", sentinel_anchor="stim_start", day_start_offset=2, day_end_offset=12, sort_order=1))
    db.add(ProtocolDrugRule(protocol_template_id=day_21_ldr_antag_proto.id, drug_name="MENOTAS XP", dose="75 IU", frequency="OD", sentinel_anchor="stim_start", day_start_offset=2, day_end_offset=12, sort_order=2))
    db.add(ProtocolDrugRule(protocol_template_id=day_21_ldr_antag_proto.id, drug_name="Cetrolix", dose="0.25 mg", frequency="OD", sentinel_anchor="stim_start", day_start_offset=8, day_end_offset=11, sort_order=3))
    db.add(ProtocolDrugRule(protocol_template_id=day_21_ldr_antag_proto.id, drug_name="Coriosurge", dose="10000 IU", frequency="OD", sentinel_anchor="stim_start", day_start_offset=12, day_end_offset=24, sort_order=4))
    db.add(ProtocolDrugRule(protocol_template_id=day_21_ldr_antag_proto.id, drug_name="Cetrotide", dose="0.25 mg", frequency="OD", sentinel_anchor="stim_start", day_start_offset=12, day_end_offset=12, sort_order=5))
    db.add(ProtocolDrugRule(protocol_template_id=day_21_ldr_antag_proto.id, drug_name="DUPHASTON", dose="10 mg", frequency="TDS", sentinel_anchor="stim_start", day_start_offset=14, day_end_offset=32, sort_order=6))
    db.add(ProtocolDrugRule(protocol_template_id=day_21_ldr_antag_proto.id, drug_name="Dubagest", dose="400 mg", frequency="BD", sentinel_anchor="stim_start", day_start_offset=14, day_end_offset=32, sort_order=7))
    db.add(ProtocolDrugRule(protocol_template_id=day_21_ldr_antag_proto.id, drug_name="Decapeptyl", dose="0.1 mg", frequency="BD", sentinel_anchor="stim_start", day_start_offset=17, day_end_offset=17, sort_order=8))
    db.add(ProtocolDrugRule(protocol_template_id=day_21_ldr_antag_proto.id, drug_name="INJ PROLUTON DEPOT", dose="500 mg", frequency="OD", sentinel_anchor="stim_start", day_start_offset=17, day_end_offset=24, sort_order=9))
    # --- Protocol: DAY 21 LDR MICROFLARE ---
    day_21_ldr_microflare_proto = ProtocolTemplate(
        hospital_id=hospital.id,
        name="DAY 21 LDR MICROFLARE",
        category="stimulation",
        description="Auto-imported protocol from Excel",
        is_active=True,
        created_by=doc_meera.id,
    )
    db.add(day_21_ldr_microflare_proto)
    await db.flush()
    db.add(ProtocolDrugRule(protocol_template_id=day_21_ldr_microflare_proto.id, drug_name="Coriosurge", dose="10000 IU", frequency="OD", sentinel_anchor="stim_start", day_start_offset=12, day_end_offset=26, sort_order=1))
    db.add(ProtocolDrugRule(protocol_template_id=day_21_ldr_microflare_proto.id, drug_name="DUPHASTON", dose="10 mg", frequency="BD", sentinel_anchor="stim_start", day_start_offset=14, day_end_offset=34, sort_order=2))
    db.add(ProtocolDrugRule(protocol_template_id=day_21_ldr_microflare_proto.id, drug_name="Dubagest", dose="400 mg", frequency="BD", sentinel_anchor="stim_start", day_start_offset=14, day_end_offset=34, sort_order=3))
    db.add(ProtocolDrugRule(protocol_template_id=day_21_ldr_microflare_proto.id, drug_name="R-HUCOG 6500", dose="500 mg", frequency="OD", sentinel_anchor="stim_start", day_start_offset=19, day_end_offset=33, sort_order=4))
    # --- Protocol: HRT FET ---
    hrt_fet_proto = ProtocolTemplate(
        hospital_id=hospital.id,
        name="HRT FET",
        category="fet",
        description="Auto-imported protocol from Excel",
        is_active=True,
        created_by=doc_meera.id,
    )
    db.add(hrt_fet_proto)
    await db.flush()
    db.add(ProtocolDrugRule(protocol_template_id=hrt_fet_proto.id, drug_name="Enrifol 2 mg", dose="2 mg", frequency="BD", sentinel_anchor="stim_start", day_start_offset=1, day_end_offset=5, sort_order=1))
    db.add(ProtocolDrugRule(protocol_template_id=hrt_fet_proto.id, drug_name="DEXONA", dose="5 mg", frequency="OD", sentinel_anchor="stim_start", day_start_offset=1, day_end_offset=31, sort_order=2))
    db.add(ProtocolDrugRule(protocol_template_id=hrt_fet_proto.id, drug_name="Endokine", dose="6 IU", frequency="OD", sentinel_anchor="stim_start", day_start_offset=1, day_end_offset=31, sort_order=3))
    db.add(ProtocolDrugRule(protocol_template_id=hrt_fet_proto.id, drug_name="Enrifol 2 mg", dose="2 mg", frequency="TDS", sentinel_anchor="stim_start", day_start_offset=6, day_end_offset=31, sort_order=4))
    db.add(ProtocolDrugRule(protocol_template_id=hrt_fet_proto.id, drug_name="Dubagest", dose="400 mg", frequency="BD", sentinel_anchor="stim_start", day_start_offset=14, day_end_offset=31, sort_order=5))
    db.add(ProtocolDrugRule(protocol_template_id=hrt_fet_proto.id, drug_name="DUPHASTON", dose="10 mg", frequency="BD", sentinel_anchor="stim_start", day_start_offset=14, day_end_offset=31, sort_order=6))
    db.add(ProtocolDrugRule(protocol_template_id=hrt_fet_proto.id, drug_name="Coriosurge", dose="10000 IU", frequency="OD", sentinel_anchor="stim_start", day_start_offset=17, day_end_offset=31, sort_order=7))
    db.add(ProtocolDrugRule(protocol_template_id=hrt_fet_proto.id, drug_name="INJ PROLUTON DEPOT", dose="500 mg", frequency="OD", sentinel_anchor="stim_start", day_start_offset=17, day_end_offset=31, sort_order=8))
    db.add(ProtocolDrugRule(protocol_template_id=hrt_fet_proto.id, drug_name="Decapeptyl", dose="0.1 mg", frequency="BD", sentinel_anchor="stim_start", day_start_offset=17, day_end_offset=17, sort_order=9))
    db.add(ProtocolDrugRule(protocol_template_id=hrt_fet_proto.id, drug_name="Gestone", dose="100 mg", frequency="OD", sentinel_anchor="stim_start", day_start_offset=17, day_end_offset=31, sort_order=10))
    # --- Protocol: IUI-D ---
    iui_d_proto = ProtocolTemplate(
        hospital_id=hospital.id,
        name="IUI-D",
        category="iui",
        description="Auto-imported protocol from Excel",
        is_active=True,
        created_by=doc_meera.id,
    )
    db.add(iui_d_proto)
    await db.flush()
    db.add(ProtocolDrugRule(protocol_template_id=iui_d_proto.id, drug_name="Follisurge", dose="100 IU", frequency="OD", sentinel_anchor="stim_start", day_start_offset=3, day_end_offset=5, sort_order=1))
    db.add(ProtocolDrugRule(protocol_template_id=iui_d_proto.id, drug_name="Coriosurge", dose="10000 IU", frequency="OD", sentinel_anchor="stim_start", day_start_offset=12, day_end_offset=21, sort_order=2))
    db.add(ProtocolDrugRule(protocol_template_id=iui_d_proto.id, drug_name="PROLUTON DEPOT", dose="500 mg", frequency="OD", sentinel_anchor="stim_start", day_start_offset=15, day_end_offset=28, sort_order=3))
    # --- Protocol: IUI-H ---
    iui_h_proto = ProtocolTemplate(
        hospital_id=hospital.id,
        name="IUI-H",
        category="iui",
        description="Auto-imported protocol from Excel",
        is_active=True,
        created_by=doc_meera.id,
    )
    db.add(iui_h_proto)
    await db.flush()
    db.add(ProtocolDrugRule(protocol_template_id=iui_h_proto.id, drug_name="Follisurge", dose="100 IU", frequency="OD", sentinel_anchor="stim_start", day_start_offset=3, day_end_offset=5, sort_order=1))
    db.add(ProtocolDrugRule(protocol_template_id=iui_h_proto.id, drug_name="OVACARE LZ", dose="2.5 mg", frequency="BD", sentinel_anchor="stim_start", day_start_offset=5, day_end_offset=12, sort_order=2))
    db.add(ProtocolDrugRule(protocol_template_id=iui_h_proto.id, drug_name="Coriosurge", dose="10000 IU", frequency="OD", sentinel_anchor="stim_start", day_start_offset=12, day_end_offset=21, sort_order=3))
    db.add(ProtocolDrugRule(protocol_template_id=iui_h_proto.id, drug_name="Naturogest Vaginal Pessary", dose="400 mg", frequency="BD", sentinel_anchor="stim_start", day_start_offset=14, day_end_offset=33, sort_order=4))
    db.add(ProtocolDrugRule(protocol_template_id=iui_h_proto.id, drug_name="PROLUTON DEPOT", dose="500 mg", frequency="OD", sentinel_anchor="stim_start", day_start_offset=14, day_end_offset=28, sort_order=5))
    # --- Protocol: Microflare ---
    microflare_proto = ProtocolTemplate(
        hospital_id=hospital.id,
        name="Microflare",
        category="stimulation",
        description="Auto-imported protocol from Excel",
        is_active=True,
        created_by=doc_meera.id,
    )
    db.add(microflare_proto)
    await db.flush()
    db.add(ProtocolDrugRule(protocol_template_id=microflare_proto.id, drug_name="Buserelin", dose="0.2 mg", frequency="OD", sentinel_anchor="stim_start", day_start_offset=3, day_end_offset=12, sort_order=1))
    db.add(ProtocolDrugRule(protocol_template_id=microflare_proto.id, drug_name="Beserelin", dose="0.2 ml", frequency="OD", sentinel_anchor="stim_start", day_start_offset=3, day_end_offset=12, sort_order=2))
    db.add(ProtocolDrugRule(protocol_template_id=microflare_proto.id, drug_name="Menopur", dose="150 IU", frequency="OD", sentinel_anchor="stim_start", day_start_offset=3, day_end_offset=12, sort_order=3))
    db.add(ProtocolDrugRule(protocol_template_id=microflare_proto.id, drug_name="Coriosurge", dose="10000 IU", frequency="OD", sentinel_anchor="stim_start", day_start_offset=12, day_end_offset=33, sort_order=4))
    db.add(ProtocolDrugRule(protocol_template_id=microflare_proto.id, drug_name="Dubagest", dose="400 mg", frequency="BD", sentinel_anchor="stim_start", day_start_offset=14, day_end_offset=34, sort_order=5))
    db.add(ProtocolDrugRule(protocol_template_id=microflare_proto.id, drug_name="DUPHASTON", dose="10 mg", frequency="BD", sentinel_anchor="stim_start", day_start_offset=14, day_end_offset=34, sort_order=6))
    # --- Protocol: Natural Cycle ---
    natural_cycle_proto = ProtocolTemplate(
        hospital_id=hospital.id,
        name="Natural Cycle",
        category="stimulation",
        description="Auto-imported protocol from Excel",
        is_active=True,
        created_by=doc_meera.id,
    )
    db.add(natural_cycle_proto)
    await db.flush()
    db.add(ProtocolDrugRule(protocol_template_id=natural_cycle_proto.id, drug_name="Spinbarkeit", dose="1 mg", frequency="BD", sentinel_anchor="stim_start", day_start_offset=8, day_end_offset=12, sort_order=1))
    db.add(ProtocolDrugRule(protocol_template_id=natural_cycle_proto.id, drug_name="VPh", dose="1 mg", frequency="BD", sentinel_anchor="stim_start", day_start_offset=8, day_end_offset=14, sort_order=2))
    db.add(ProtocolDrugRule(protocol_template_id=natural_cycle_proto.id, drug_name="Coriosurge", dose="10000 IU", frequency="OD", sentinel_anchor="stim_start", day_start_offset=12, day_end_offset=12, sort_order=3))
    db.add(ProtocolDrugRule(protocol_template_id=natural_cycle_proto.id, drug_name="Dubagest", dose="400 mg", frequency="BD", sentinel_anchor="stim_start", day_start_offset=14, day_end_offset=33, sort_order=4))
    # --- Protocol: Ovulation Induction ---
    ovulation_induction_proto = ProtocolTemplate(
        hospital_id=hospital.id,
        name="Ovulation Induction",
        category="stimulation",
        description="Auto-imported protocol from Excel",
        is_active=True,
        created_by=doc_meera.id,
    )
    db.add(ovulation_induction_proto)
    await db.flush()
    db.add(ProtocolDrugRule(protocol_template_id=ovulation_induction_proto.id, drug_name="Follisurge", dose="100 IU", frequency="OD", sentinel_anchor="stim_start", day_start_offset=2, day_end_offset=4, sort_order=1))
    db.add(ProtocolDrugRule(protocol_template_id=ovulation_induction_proto.id, drug_name="OVACARE LZ", dose="2.5 mg", frequency="BD", sentinel_anchor="stim_start", day_start_offset=3, day_end_offset=12, sort_order=2))
    db.add(ProtocolDrugRule(protocol_template_id=ovulation_induction_proto.id, drug_name="Spinbarkeit", dose="1 mg", frequency="BD", sentinel_anchor="stim_start", day_start_offset=8, day_end_offset=12, sort_order=3))
    db.add(ProtocolDrugRule(protocol_template_id=ovulation_induction_proto.id, drug_name="Coriosurge", dose="10000 IU", frequency="OD", sentinel_anchor="stim_start", day_start_offset=12, day_end_offset=12, sort_order=4))
    db.add(ProtocolDrugRule(protocol_template_id=ovulation_induction_proto.id, drug_name="NATUROGEST SR TABLET", dose="400 mg/ml", frequency="BD", sentinel_anchor="stim_start", day_start_offset=15, day_end_offset=33, sort_order=5))
    await db.flush()
    return {
        "hospital": hospital,
        "main_branch": main_branch,
        "users": users,
        "protocols": {
            "antagonist": antag_proto,
            "fet": hrt_fet_proto,
            "iui": iui_d_proto,
        },
    }


async def seed_cosgyn(db):
    """Seed standard Cosmetic Gynecology packages and protocols."""
    from app.core.models.cosgyn import CosgynTreatment
    from sqlalchemy import select

    treatments_data = [
        {
            "name": "Cervical Erosion/ Recurrent white discharge",
            "package_combo": "Jet Plasma",
            "jet_plasma_sessions": 3,
            "jet_plasma_duration_mins": 16,
            "tesla_chair_sessions": 0,
            "tesla_chair_duration_mins": 0,
            "prp_sessions": 0,
            "price": 20000.0,
        },
        {
            "name": "Urge Incontinence",
            "package_combo": "Jet Plasma + Tesla Chair",
            "jet_plasma_sessions": 4,
            "jet_plasma_duration_mins": 40,
            "tesla_chair_sessions": 10,
            "tesla_chair_duration_mins": 30,
            "prp_sessions": 0,
            "price": 86400.0,
        },
        {
            "name": "SUI (Stress Urinary Incontinence)",
            "package_combo": "Jet Plasma + Tesla Chair",
            "jet_plasma_sessions": 4,
            "jet_plasma_duration_mins": 40,
            "tesla_chair_sessions": 10,
            "tesla_chair_duration_mins": 30,
            "prp_sessions": 0,
            "price": 86400.0,
        },
        {
            "name": "Vaginal Laxity",
            "package_combo": "Jet Plasma + Tesla Chair",
            "jet_plasma_sessions": 4,
            "jet_plasma_duration_mins": 40,
            "tesla_chair_sessions": 10,
            "tesla_chair_duration_mins": 30,
            "prp_sessions": 0,
            "price": 86400.0,
        },
        {
            "name": "Vaginal Laxity Advanced",
            "package_combo": "Jet Plasma + Tesla Chair + PRP",
            "jet_plasma_sessions": 4,
            "jet_plasma_duration_mins": 40,
            "tesla_chair_sessions": 10,
            "tesla_chair_duration_mins": 30,
            "prp_sessions": 4,
            "price": 115200.0,
        },
        {
            "name": "Vaginal Dryness",
            "package_combo": "Jet Plasma",
            "jet_plasma_sessions": 4,
            "jet_plasma_duration_mins": 40,
            "tesla_chair_sessions": 0,
            "tesla_chair_duration_mins": 0,
            "prp_sessions": 0,
            "price": 38400.0,
        },
        {
            "name": "Vaginal Dryness Advanced",
            "package_combo": "Jet Plasma + PRP",
            "jet_plasma_sessions": 4,
            "jet_plasma_duration_mins": 40,
            "tesla_chair_sessions": 0,
            "tesla_chair_duration_mins": 0,
            "prp_sessions": 4,
            "price": 67200.0,
        },
        {
            "name": "Lichen Intensive Program (2 Months)",
            "package_combo": "Jet Plasma + PRP",
            "jet_plasma_sessions": 6,
            "jet_plasma_duration_mins": 20,
            "tesla_chair_sessions": 0,
            "tesla_chair_duration_mins": 0,
            "prp_sessions": 4,
            "price": 64800.0,
        },
        {
            "name": "Lichen Maintenance Program (10 Months)",
            "package_combo": "Jet Plasma",
            "jet_plasma_sessions": 10,
            "jet_plasma_duration_mins": 30,
            "tesla_chair_sessions": 0,
            "tesla_chair_duration_mins": 0,
            "prp_sessions": 10,
            "price": 132000.0,
        },
        {
            "name": "Complete Lichen 1-Year Program",
            "package_combo": "Jet Plasma + PRP",
            "jet_plasma_sessions": 16,
            "jet_plasma_duration_mins": 30,
            "tesla_chair_sessions": 0,
            "tesla_chair_duration_mins": 0,
            "prp_sessions": 14,
            "price": 196800.0,
        },
        {
            "name": "Vulval Rejuvenation / Plumping",
            "package_combo": "Jet Plasma",
            "jet_plasma_sessions": 3,
            "jet_plasma_duration_mins": 15,
            "tesla_chair_sessions": 0,
            "tesla_chair_duration_mins": 0,
            "prp_sessions": 0,
            "price": 20000.0,
        },
        {
            "name": "Kama sutra shot",
            "package_combo": "PRP",
            "jet_plasma_sessions": 0,
            "jet_plasma_duration_mins": 0,
            "tesla_chair_sessions": 0,
            "tesla_chair_duration_mins": 0,
            "prp_sessions": 1,
            "price": 16000.0,
        },
        {
            "name": "Post Partum Rehab",
            "package_combo": "Tesla Chair",
            "jet_plasma_sessions": 0,
            "jet_plasma_duration_mins": 0,
            "tesla_chair_sessions": 10,
            "tesla_chair_duration_mins": 30,
            "prp_sessions": 0,
            "price": 48000.0,
        },
        {
            "name": "Uterine Prolaps",
            "package_combo": "Tesla Chair",
            "jet_plasma_sessions": 0,
            "jet_plasma_duration_mins": 0,
            "tesla_chair_sessions": 10,
            "tesla_chair_duration_mins": 30,
            "prp_sessions": 0,
            "price": 48000.0,
        },
        {
            "name": "Lower back ache",
            "package_combo": "Tesla Chair",
            "jet_plasma_sessions": 0,
            "jet_plasma_duration_mins": 0,
            "tesla_chair_sessions": 10,
            "tesla_chair_duration_mins": 30,
            "prp_sessions": 0,
            "price": 48000.0,
        },
        {
            "name": "Urine Leakage- >45 yrs",
            "package_combo": "Tesla Chair",
            "jet_plasma_sessions": 0,
            "jet_plasma_duration_mins": 0,
            "tesla_chair_sessions": 10,
            "tesla_chair_duration_mins": 30,
            "prp_sessions": 0,
            "price": 48000.0,
        },
        {
            "name": "Urine Leakage- <45 yrs",
            "package_combo": "Tesla Chair",
            "jet_plasma_sessions": 0,
            "jet_plasma_duration_mins": 0,
            "tesla_chair_sessions": 12,
            "tesla_chair_duration_mins": 30,
            "prp_sessions": 0,
            "price": 60000.0,
        },
        {
            "name": "Diastasis recti/ core strengthening/ belly fat reduction",
            "package_combo": "Tesla Chair",
            "jet_plasma_sessions": 0,
            "jet_plasma_duration_mins": 0,
            "tesla_chair_sessions": 10,
            "tesla_chair_duration_mins": 30,
            "prp_sessions": 0,
            "price": 48000.0,
        },
        {
            "name": "Nocturia",
            "package_combo": "Tesla Chair",
            "jet_plasma_sessions": 0,
            "jet_plasma_duration_mins": 0,
            "tesla_chair_sessions": 10,
            "tesla_chair_duration_mins": 30,
            "prp_sessions": 0,
            "price": 48000.0,
        },
        {
            "name": "Erectile dysfunction",
            "package_combo": "Tesla Chair",
            "jet_plasma_sessions": 0,
            "jet_plasma_duration_mins": 0,
            "tesla_chair_sessions": 10,
            "tesla_chair_duration_mins": 30,
            "prp_sessions": 0,
            "price": 48000.0,
        },
        {
            "name": "Premature ejaculation",
            "package_combo": "Tesla Chair",
            "jet_plasma_sessions": 0,
            "jet_plasma_duration_mins": 0,
            "tesla_chair_sessions": 10,
            "tesla_chair_duration_mins": 30,
            "prp_sessions": 0,
            "price": 48000.0,
        },
    ]

    res = await db.execute(select(CosgynTreatment))
    existing_map = {t.name: t for t in res.scalars().all()}

    for t_data in treatments_data:
        if t_data["name"] in existing_map:
            t = existing_map[t_data["name"]]
            t.package_combo = t_data["package_combo"]
            t.jet_plasma_sessions = t_data["jet_plasma_sessions"]
            t.jet_plasma_duration_mins = t_data["jet_plasma_duration_mins"]
            t.tesla_chair_sessions = t_data["tesla_chair_sessions"]
            t.tesla_chair_duration_mins = t_data["tesla_chair_duration_mins"]
            t.prp_sessions = t_data["prp_sessions"]
            t.price = t_data["price"]
        else:
            new_t = CosgynTreatment(**t_data)
            db.add(new_t)

    await db.flush()
    print(f"  [+] Seeded/upserted {len(treatments_data)} Cosmetic Gynecology treatment packages.")


async def seed_pharmacy(db):
    """Seed standard IVF & fertility medications for FEFO inventory and POS dispensing."""
    from app.modules.pharmacy.model import InventoryBatch
    from sqlalchemy import select
    from datetime import date, timedelta

    res = await db.execute(select(InventoryBatch))
    existing = res.scalars().all()
    if len(existing) == 0:
        today = date.today()
        batches = [
            InventoryBatch(
                item_code="GONAL-F-450",
                item_name="Gonal-F 450 IU (Follitropin Alfa)",
                generic_name="Recombinant Human FSH",
                category="Fertility / Injectables",
                batch_number="GF2026-A1",
                expiry_date=today + timedelta(days=45),
                quantity_received=30,
                quantity_available=28,
                purchase_rate=4200.0,
                mrp=5800.0,
                selling_price=5800.0,
                rack_location="Cold Chain Fridge 1",
            ),
            InventoryBatch(
                item_code="GONAL-F-450",
                item_name="Gonal-F 450 IU (Follitropin Alfa)",
                generic_name="Recombinant Human FSH",
                category="Fertility / Injectables",
                batch_number="GF2026-B2",
                expiry_date=today + timedelta(days=240),
                quantity_received=50,
                quantity_available=50,
                purchase_rate=4200.0,
                mrp=5800.0,
                selling_price=5800.0,
                rack_location="Cold Chain Fridge 1",
            ),
            InventoryBatch(
                item_code="CETROTIDE-025",
                item_name="Cetrotide 0.25mg (Cetrorelix)",
                generic_name="GnRH Antagonist",
                category="Fertility / Injectables",
                batch_number="CT9021-X",
                expiry_date=today + timedelta(days=180),
                quantity_received=40,
                quantity_available=36,
                purchase_rate=1450.0,
                mrp=2100.0,
                selling_price=2100.0,
                rack_location="Cold Chain Fridge 2",
            ),
            InventoryBatch(
                item_code="MENOPUR-75",
                item_name="Menopur 75 IU (Menotrophin HP)",
                generic_name="Highly Purified HMG",
                category="Fertility / Injectables",
                batch_number="MN4432-P",
                expiry_date=today + timedelta(days=120),
                quantity_received=60,
                quantity_available=54,
                purchase_rate=980.0,
                mrp=1550.0,
                selling_price=1550.0,
                rack_location="Cold Chain Fridge 2",
            ),
            InventoryBatch(
                item_code="SUSTEN-SR-400",
                item_name="Susten SR 400mg (Micronized Progesterone)",
                generic_name="Natural Micronized Progesterone",
                category="Luteal Support / Tablets",
                batch_number="ST8821-M",
                expiry_date=today + timedelta(days=365),
                quantity_received=100,
                quantity_available=95,
                purchase_rate=320.0,
                mrp=480.0,
                selling_price=480.0,
                rack_location="Main Rack A3",
            ),
            InventoryBatch(
                item_code="ESTRABET-2",
                item_name="Estrabet 2mg (Estradiol Valerate)",
                generic_name="Estradiol Valerate",
                category="Endometrial Prep / Tablets",
                batch_number="EB1019-Q",
                expiry_date=today + timedelta(days=400),
                quantity_received=80,
                quantity_available=78,
                purchase_rate=190.0,
                mrp=290.0,
                selling_price=290.0,
                rack_location="Main Rack B1",
            ),
            InventoryBatch(
                item_code="CABER-05",
                item_name="Caberlin 0.5mg (Cabergoline)",
                generic_name="Dopamine Agonist",
                category="Hyperprolactinemia / Tablets",
                batch_number="CB7712-C",
                expiry_date=today + timedelta(days=500),
                quantity_received=50,
                quantity_available=45,
                purchase_rate=240.0,
                mrp=360.0,
                selling_price=360.0,
                rack_location="Main Rack A1",
            ),
            InventoryBatch(
                item_code="FOLVITE-5",
                item_name="Folvite 5mg (Folic Acid)",
                generic_name="Folic Acid Vitamin B9",
                category="Antenatal Care / Tablets",
                batch_number="FV9923-D",
                expiry_date=today + timedelta(days=600),
                quantity_received=200,
                quantity_available=192,
                purchase_rate=25.0,
                mrp=45.0,
                selling_price=45.0,
                rack_location="Main Rack C2",
            ),
        ]
        db.add_all(batches)
        await db.flush()
        print("  [+] Pharmacy inventory batches seeded (FEFO enabled).")


async def seed_demo_patients(db, base_data):
    """
    Seeds comprehensive demonstration fertility data:
    - 5 Full Couples across ICSI, FET, IUI, TESA, and Donor Bank pathways
    - ART Donors
    - Treatment Cycles & Day 0-7 Embryology Matrix
    - Dual-Witnessing Signoff Audit Logs
    - Cryobank Physical Tank Coordinates
    - Advance Wallets & Multi-Source Billing Invoices
    - Clinical Scans (TVS, SIS, CASA, DFI Halosperm, Early Pregnancy)
    """
    print("  [2/2] Seeding comprehensive development/demo patient datasets...")

    hospital = base_data["hospital"]
    main_branch = base_data["main_branch"]
    users = base_data["users"]
    protocols = base_data["protocols"]

    doc_meera = users[1]
    doc_anand = users[2]
    emb_rahul = users[3]
    emb_pooja = users[4]
    accounts_user = users[6]

    # 1. 5 Detailed Fertility Couples
    couples_data = [
        # Couple 1: Sunita & Rajesh Verma (ICSI + Antagonist + Day 5 Blastocysts)
        {
            "wife": {
                "vid": "VH-VMD01-00001", "name": "Sunita Verma", "surname": "Verma", "gender": Gender.FEMALE, "age": 31,
                "phone": "+91-9876543210", "email": "sunita.verma@example.com", "blood_group": "B+ve", "area": "Jubilee Hills, Hyderabad",
                "aadhaar_number": "9876-5432-1098", "abha_number": "91-9876-5432-1098", "referred_by_type": "doctor", "referred_by_name": "Dr. Ananya Rao",
                "treating_doctor_id": doc_meera.id,
                "alert_notes": ["High AMH (5.8 ng/mL) — Mild OHSS Risk", "Serology Non-Reactive (Verified 10-Aug-2026)"],
                "clinical_notes": ["Primary Infertility 4 years.", "Day 8 scan: Bilateral follicles 16-18mm.", "OPU completed with 10 MII oocytes."],
            },
            "husband": {
                "vid": "VH-VMD01-00002", "name": "Rajesh Verma", "surname": "Verma", "gender": Gender.MALE, "age": 34,
                "phone": "+91-9876543211", "email": "rajesh.verma@example.com", "blood_group": "O+ve", "area": "Jubilee Hills, Hyderabad",
                "aadhaar_number": "9876-5432-1099", "abha_number": "91-9876-5432-1099", "referred_by_type": "doctor", "referred_by_name": "Dr. Ananya Rao",
                "treating_doctor_id": doc_anand.id,
                "alert_notes": ["Mild Asthenozoospermia (Motility 38%)"],
                "clinical_notes": ["CASA: PR Motility 38%, Conc 42 M/mL.", "Halosperm DFI: 18% (Good Potential)."],
            },
        },
        # Couple 2: Kavita & Manoj Joshi (Freeze-All + FET + Early Pregnancy Scan)
        {
            "wife": {
                "vid": "VH-VMD01-00003", "name": "Kavita Joshi", "surname": "Joshi", "gender": Gender.FEMALE, "age": 29,
                "phone": "+91-9811122233", "email": "kavita.joshi@example.com", "blood_group": "A+ve", "area": "Banjara Hills, Hyderabad",
                "referred_by_type": "marketing_person", "referred_by_name": "Camp Banjara",
                "treating_doctor_id": doc_meera.id,
                "alert_notes": ["Early Pregnancy Positive (Beta-hCG 1420 mIU/mL)"],
                "clinical_notes": ["FET completed on 20-Jul-2026.", "Viability Scan: Single intrauterine gestational sac with FHR 128 bpm."],
            },
            "husband": {
                "vid": "VH-VMD01-00004", "name": "Manoj Joshi", "surname": "Joshi", "gender": Gender.MALE, "age": 33,
                "phone": "+91-9811122234", "email": "manoj.joshi@example.com", "blood_group": "AB+ve", "area": "Banjara Hills, Hyderabad",
                "referred_by_type": "marketing_person", "referred_by_name": "Camp Banjara",
                "treating_doctor_id": doc_anand.id,
                "alert_notes": [],
                "clinical_notes": ["Normozoospermic partner."],
            },
        },
        # Couple 3: Priya & Rahul Menon (IUI-Husband Pathway)
        {
            "wife": {
                "vid": "VH-VMD01-00005", "name": "Priya Menon", "surname": "Menon", "gender": Gender.FEMALE, "age": 27,
                "phone": "+91-9822233344", "email": "priya.menon@example.com", "blood_group": "O+ve", "area": "Gachibowli, Hyderabad",
                "referred_by_type": "walk_in", "referred_by_name": "Self / Website",
                "treating_doctor_id": doc_meera.id,
                "alert_notes": ["Bilateral Patent Fallopian Tubes (SIS Confirmed)"],
                "clinical_notes": ["Unexplained Infertility 2.5 yrs.", "IUI-H cycle with single dominant follicle 20mm on Day 12."],
            },
            "husband": {
                "vid": "VH-VMD01-00006", "name": "Rahul Menon", "surname": "Menon", "gender": Gender.MALE, "age": 30,
                "phone": "+91-9822233345", "email": "rahul.menon@example.com", "blood_group": "B+ve", "area": "Gachibowli, Hyderabad",
                "referred_by_type": "walk_in", "referred_by_name": "Self / Website",
                "treating_doctor_id": doc_anand.id,
                "alert_notes": [],
                "clinical_notes": ["Semen Prep: Post-wash motile count 18.5 Million."],
            },
        },
        # Couple 4: Anita & Suresh Deshmukh (Severe Male Factor + Surgical TESA)
        {
            "wife": {
                "vid": "VH-VMD01-00007", "name": "Anita Deshmukh", "surname": "Deshmukh", "gender": Gender.FEMALE, "age": 33,
                "phone": "+91-9833344455", "email": "anita.deshmukh@example.com", "blood_group": "A-ve", "area": "Madhapur, Hyderabad",
                "referred_by_type": "doctor", "referred_by_name": "Dr. V. K. Murthy",
                "treating_doctor_id": doc_meera.id,
                "alert_notes": ["Rh Negative Mother (Anti-D counseled)"],
                "clinical_notes": ["Commissioning ICSI cycle with partner surgical sperm."],
            },
            "husband": {
                "vid": "VH-VMD01-00008", "name": "Suresh Deshmukh", "surname": "Deshmukh", "gender": Gender.MALE, "age": 36,
                "phone": "+91-9833344456", "email": "suresh.deshmukh@example.com", "blood_group": "O+ve", "area": "Madhapur, Hyderabad",
                "referred_by_type": "doctor", "referred_by_name": "Dr. V. K. Murthy",
                "treating_doctor_id": doc_anand.id,
                "alert_notes": ["Non-Obstructive Azoospermia (TESA candidate)"],
                "clinical_notes": ["Bilateral TESA performed: Motile testicular spermatozoa recovered and frozen."],
            },
        },
        # Couple 5: Sneha & Vikram Patil (Poor Ovarian Reserve + Donor Bank Form 23 + PGT-A)
        {
            "wife": {
                "vid": "VH-VMD01-00009", "name": "Sneha Patil", "surname": "Patil", "gender": Gender.FEMALE, "age": 41,
                "phone": "+91-9844455566", "email": "sneha.patil@example.com", "blood_group": "B+ve", "area": "Kondapur, Hyderabad",
                "referred_by_type": "doctor", "referred_by_name": "Dr. R. C. Rao",
                "treating_doctor_id": doc_meera.id,
                "alert_notes": ["Diminished Ovarian Reserve (AMH 0.4 ng/mL)", "ART Bank Form 23 Consent Verified"],
                "clinical_notes": ["Donor Oocyte Cycle initiated.", "PGT-A screening selected for all day 5 blastocysts."],
            },
            "husband": {
                "vid": "VH-VMD01-00010", "name": "Vikram Patil", "surname": "Patil", "gender": Gender.MALE, "age": 44,
                "phone": "+91-9844455567", "email": "vikram.patil@example.com", "blood_group": "O+ve", "area": "Kondapur, Hyderabad",
                "referred_by_type": "doctor", "referred_by_name": "Dr. R. C. Rao",
                "treating_doctor_id": doc_anand.id,
                "alert_notes": [],
                "clinical_notes": ["Partner semen prepared for donor oocyte ICSI."],
            },
        },
    ]

    # Donors
    donors = [
        Patient(
            tenant_id=hospital.id, branch_id=main_branch.id, vid="VH-DONOR-00001",
            name="Donor Oocyte Bank #44", gender=Gender.FEMALE, age=25, phone="+91-9900011122",
            registration_type=RegistrationType.DONOR_BANK, area="ART Bank Registry",
            clinical_notes=["Form 23 National ART Bank Cleared. Serology Negative. Karyotype 46,XX."],
        ),
        Patient(
            tenant_id=hospital.id, branch_id=main_branch.id, vid="VH-DONOR-00002",
            name="Donor Sperm Bank #108", gender=Gender.MALE, age=27, phone="+91-9900011133",
            registration_type=RegistrationType.DONOR_BANK, area="ART Bank Registry",
            clinical_notes=["Form 23 Donor Sperm Cryovial. CMV Negative. Karyotype 46,XY."],
        ),
    ]
    db.add_all(donors)
    await db.flush()

    created_couples = []
    for c in couples_data:
        w_pat = Patient(
            tenant_id=hospital.id, branch_id=main_branch.id,
            vid=c["wife"]["vid"], name=c["wife"]["name"], surname=c["wife"]["surname"],
            gender=c["wife"]["gender"], age=c["wife"]["age"], phone=c["wife"]["phone"],
            email=c["wife"]["email"], blood_group=c["wife"]["blood_group"], area=c["wife"]["area"],
            identity_type="aadhaar", aadhaar_encrypted=c["wife"].get("aadhaar_number"), abha_number=c["wife"].get("abha_number"),
            referred_by_type=c["wife"]["referred_by_type"], referred_by_name=c["wife"]["referred_by_name"],
            treating_doctor_id=c["wife"]["treating_doctor_id"],
            alert_notes=c["wife"]["alert_notes"], clinical_notes=c["wife"]["clinical_notes"],
            registration_type=RegistrationType.PATIENT,
        )
        db.add(w_pat)
        await db.flush()

        h_pat = Patient(
            tenant_id=hospital.id, branch_id=main_branch.id,
            vid=c["husband"]["vid"], name=c["husband"]["name"], surname=c["husband"]["surname"],
            gender=c["husband"]["gender"], age=c["husband"]["age"], phone=c["husband"]["phone"],
            email=c["husband"]["email"], blood_group=c["husband"]["blood_group"], area=c["husband"]["area"],
            identity_type="aadhaar", aadhaar_encrypted=c["husband"].get("aadhaar_number"), abha_number=c["husband"].get("abha_number"),
            referred_by_type=c["husband"]["referred_by_type"], referred_by_name=c["husband"]["referred_by_name"],
            treating_doctor_id=c["husband"]["treating_doctor_id"],
            alert_notes=c["husband"]["alert_notes"], clinical_notes=c["husband"]["clinical_notes"],
            registration_type=RegistrationType.PATIENT,
            partner_id=w_pat.id,
        )
        db.add(h_pat)
        await db.flush()

        # Link bidirectional
        w_pat.partner_id = h_pat.id
        await db.flush()
        created_couples.append((w_pat, h_pat))

    sunita, rajesh = created_couples[0]
    kavita, manoj = created_couples[1]
    priya, rahul = created_couples[2]
    anita, suresh = created_couples[3]
    sneha, vikram = created_couples[4]

    # 2. Treatment Cycles
    cycle1 = TreatmentCycle(
        tenant_id=hospital.id,
        cycle_id="TC-2026-0001", patient_id=sunita.id, partner_id=rajesh.id,
        treating_doctor_id=doc_meera.id, treatment_type="ICSI", attempt_number=1,
        female_factors=["PCOS", "High AFC"], male_factors=["Asthenozoospermia"],
        status=TreatmentCycleStatus.RUNNING, protocol_template_id=protocols["antagonist"].id,
        sentinel_dates={
            "lmp_day1": (date.today() - timedelta(days=12)).isoformat(),
            "baseline_scan": (date.today() - timedelta(days=11)).isoformat(),
            "stim_start": (date.today() - timedelta(days=10)).isoformat(),
            "trigger": (date.today() - timedelta(days=2)).isoformat(),
            "opu": (date.today()).isoformat(),
            "et": (date.today() + timedelta(days=5)).isoformat(),
        },
        gametes_source={"oocyte": "self", "sperm": "partner"},
        pgs_pgd_data={"indicated": False},
        endometrial_monitoring=[
            {"date": (date.today() - timedelta(days=4)).isoformat(), "day_of_cycle": 8, "thickness_mm": 8.2, "pattern": "Trilaminar", "vascularity": "Zone 3"},
            {"date": (date.today() - timedelta(days=2)).isoformat(), "day_of_cycle": 10, "thickness_mm": 10.1, "pattern": "Trilaminar Type A", "vascularity": "Zone 4"},
        ],
        start_date=date.today() - timedelta(days=10),
        remarks="Excellent stimulation response. 10 MII oocytes retrieved at OPU.",
        created_by=doc_meera.id,
    )

    cycle2 = TreatmentCycle(
        tenant_id=hospital.id,
        cycle_id="TC-2026-0002", patient_id=kavita.id, partner_id=manoj.id,
        treating_doctor_id=doc_meera.id, treatment_type="FET", attempt_number=1,
        female_factors=["Tubal Factor"], male_factors=["Normal"],
        status=TreatmentCycleStatus.COMPLETED, protocol_template_id=protocols["fet"].id,
        sentinel_dates={
            "lmp_day1": (date.today() - timedelta(days=45)).isoformat(),
            "stim_start": (date.today() - timedelta(days=43)).isoformat(),
            "et": (date.today() - timedelta(days=25)).isoformat(),
        },
        gametes_source={"oocyte": "self", "sperm": "partner"},
        start_date=date.today() - timedelta(days=45),
        end_date=date.today() - timedelta(days=25),
        remarks="Single blastocyst (4AA) transferred under USG guidance. Beta-hCG 1420 mIU/mL. Clinical Pregnancy Confirmed.",
        created_by=doc_meera.id,
    )

    cycle3 = TreatmentCycle(
        tenant_id=hospital.id,
        cycle_id="TC-2026-0003", patient_id=priya.id, partner_id=rahul.id,
        treating_doctor_id=doc_meera.id, treatment_type="IUI_H", attempt_number=1,
        female_factors=["Unexplained"], male_factors=["Normal"],
        status=TreatmentCycleStatus.RUNNING, protocol_template_id=protocols["iui"].id,
        sentinel_dates={
            "lmp_day1": (date.today() - timedelta(days=10)).isoformat(),
            "stim_start": (date.today() - timedelta(days=8)).isoformat(),
            "trigger": (date.today() - timedelta(days=1)).isoformat(),
            "iui": (date.today() + timedelta(days=1)).isoformat(),
        },
        gametes_source={"oocyte": "self", "sperm": "partner"},
        start_date=date.today() - timedelta(days=8),
        remarks="Single follicle 19.5mm on right ovary. hCG trigger given.",
        created_by=doc_meera.id,
    )
    db.add_all([cycle1, cycle2, cycle3])
    await db.flush()

    # 3. Embryology Oocytes & Dual-Witnessing Signoff
    oocytes_list = []
    for i in range(1, 11):
        is_mature = i <= 8
        fert = "2PN" if i <= 7 else ("1PN" if i == 8 else "0PN")
        d5_data = {"stage": "Blastocyst", "expansion": 4, "icm": "A", "te": "A", "gardner": "4AA", "sart": "Good"} if i <= 4 else ({"stage": "Early Blast", "gardner": "3BB"} if i <= 6 else {"stage": "Arrested"})
        disp = {"status": "Frozen", "straw_no": "STR-VMD-001"} if i <= 4 else ({"status": "Transferred"} if i == 5 else {"status": "Discarded"})
        ooc = OocyteRecord(
            treatment_cycle_id=cycle1.id,
            oocyte_number=i,
            procedure_type="ICSI",
            maturity_day0="MII" if is_mature else "MI",
            fert_check_day1=fert,
            day1_data={"pn_details": "2PN & 2PB normal fertilization" if fert == "2PN" else "Abnormal"},
            day2_data={"cells": 4, "fragmentation_pct": 5, "grade": "Grade 1"} if fert == "2PN" else {},
            day3_data={"cells": 8, "fragmentation_pct": 5, "grade": "Grade 1"} if fert == "2PN" else {},
            day5_data=d5_data if fert == "2PN" else {},
            disposition=disp,
        )
        oocytes_list.append(ooc)
    db.add_all(oocytes_list)
    await db.flush()

    witnesses = [
        EmbryologyWitness(
            treatment_cycle_id=cycle1.id, day_number=0,
            checked_by_id=emb_rahul.id,
            witnessed_by_id=emb_pooja.id,
            is_verified=True, notes="Day 0 OPU dish & ICSI sperm identification verified by dual embryologists.",
        ),
        EmbryologyWitness(
            treatment_cycle_id=cycle1.id, day_number=1,
            checked_by_id=emb_rahul.id,
            witnessed_by_id=emb_pooja.id,
            is_verified=True, notes="Day 1 2PN fertilization double check verified.",
        ),
        EmbryologyWitness(
            treatment_cycle_id=cycle1.id, day_number=5,
            checked_by_id=emb_rahul.id,
            witnessed_by_id=emb_pooja.id,
            is_verified=True, notes="Day 5 Gardner 4AA vitrification double witness signed.",
        ),
    ]
    db.add_all(witnesses)
    await db.flush()

    # 4. Cryobank Tank Inventory
    cryo_samples = [
        CryoSample(
            tenant_id=hospital.id,
            patient_id=sunita.id, partner_id=rajesh.id, treatment_cycle_id=cycle1.id,
            sample_type="embryo", straw_number="STR-VMD-001",
            tank_number="Tank-1 (Liquid LN2)", canister_number="Canister-1",
            canister_colour="Blue", goblet_colour="Yellow", cryo_device_colour="Green",
            no_of_embryos=2, embryo_details=[{"embryo_no": 1, "grade": "4AA"}, {"embryo_no": 2, "grade": "4AA"}],
            status=CryoSampleStatus.AVAILABLE,
            freezing_datetime=datetime.utcnow(),
            expiry_date=date.today() + timedelta(days=365 * 5),
            consent_form_reference="ART Act 2021 Form 15 Ref #8821",
            embryologist_id=emb_rahul.id,
        ),
        CryoSample(
            tenant_id=hospital.id,
            patient_id=kavita.id, partner_id=manoj.id, treatment_cycle_id=cycle2.id,
            sample_type="embryo", straw_number="STR-VMD-042",
            tank_number="Tank-1 (Liquid LN2)", canister_number="Canister-2",
            canister_colour="Red", goblet_colour="Pink", cryo_device_colour="White",
            no_of_embryos=1, embryo_details=[{"embryo_no": 1, "grade": "4AA"}],
            status=CryoSampleStatus.WARMED,
            freezing_datetime=datetime.utcnow() - timedelta(days=120),
            expiry_date=date.today() + timedelta(days=365 * 5),
            thaw_event={
                "thaw_date": (date.today() - timedelta(days=25)).isoformat(),
                "embryos_warmed": 1, "embryos_survived": 1, "survival_rate_pct": 100.0,
                "disposition": "Transferred", "witness_id": str(emb_pooja.id),
            },
            embryologist_id=emb_rahul.id,
        ),
        CryoSample(
            tenant_id=hospital.id,
            patient_id=sunita.id, partner_id=rajesh.id,
            sample_type="semen", straw_number="STR-VMD-099",
            tank_number="Tank-2 (Semen Cryocan)", canister_number="Canister-3",
            canister_colour="Green", goblet_colour="White", cryo_device_colour="Blue",
            no_of_embryos=1,
            status=CryoSampleStatus.AVAILABLE,
            freezing_datetime=datetime.utcnow() - timedelta(days=350),
            expiry_date=date.today() + timedelta(days=15),
            consent_form_reference="ART Act 2021 Form 15 Ref #7011",
            embryologist_id=emb_rahul.id,
        ),
    ]
    db.add_all(cryo_samples)
    await db.flush()

    # 5. Wallets & Invoices
    wallets = [
        PatientWallet(patient_id=sunita.id, tenant_id=hospital.id, balance=Decimal("25000.00")),
        PatientWallet(patient_id=kavita.id, tenant_id=hospital.id, balance=Decimal("15000.00")),
    ]
    db.add_all(wallets)
    await db.flush()

    w_tx1 = WalletTransaction(
        wallet_id=wallets[0].id, transaction_type=WalletTxType.DEPOSIT, amount=Decimal("50000.00"),
        payment_mode="upi", notes="Initial package advance deposit via UPI (GPay)", created_by=accounts_user.id,
    )
    w_tx2 = WalletTransaction(
        wallet_id=wallets[0].id, transaction_type=WalletTxType.INVOICE_DEBIT, amount=Decimal("25000.00"),
        notes="Debited against OPU Procedure Invoice VMD-INV-00001", created_by=accounts_user.id,
    )
    db.add_all([w_tx1, w_tx2])
    await db.flush()

    invoices = [
        Invoice(
            tenant_id=hospital.id, branch_id=main_branch.id, patient_id=sunita.id, invoice_number="VMD-INV-00001",
            appointment_source="IVF-Theatre", reason_for_attendance="OPU Ovum Pick-Up Procedure & ICSI Insemination",
            items=[
                {"description": "OPU Theatre Procedure Fee", "quantity": 1, "unit_price": 45000.0, "total": 45000.0},
                {"description": "ICSI Injection Fee", "quantity": 1, "unit_price": 40000.0, "total": 40000.0},
            ],
            subtotal=Decimal("85000.00"), discount=Decimal("5000.00"), tax=Decimal("0.00"),
            total_amount=Decimal("80000.00"), paid_amount=Decimal("38000.00"), wallet_amount_used=Decimal("25000.00"),
            status=InvoiceStatus.PARTIALLY_PAID, payment_method="upi", upi_pay_mode="GPay",
            created_by=accounts_user.id,
        ),
        Invoice(
            tenant_id=hospital.id, branch_id=main_branch.id, patient_id=rajesh.id, invoice_number="VMD-INV-00002",
            appointment_source="Andrology/Embryology", reason_for_attendance="CASA Semen Analysis & Halosperm DFI",
            items=[
                {"description": "CASA Semen Analysis (WHO 6th)", "quantity": 1, "unit_price": 2000.0, "total": 2000.0},
                {"description": "Sperm DFI Halosperm Assay", "quantity": 1, "unit_price": 4500.0, "total": 4500.0},
            ],
            subtotal=Decimal("6500.00"), discount=Decimal("500.00"), tax=Decimal("0.00"),
            total_amount=Decimal("6000.00"), paid_amount=Decimal("6000.00"),
            status=InvoiceStatus.PAID, payment_method="card",
            created_by=accounts_user.id,
        ),
        Invoice(
            tenant_id=hospital.id, branch_id=main_branch.id, patient_id=kavita.id, invoice_number="VMD-INV-00003",
            appointment_source="Package", reason_for_attendance="FET Treatment Package",
            items=[{"description": "Frozen Embryo Transfer Package", "quantity": 1, "unit_price": 55000.0, "total": 55000.0}],
            subtotal=Decimal("55000.00"), discount=Decimal("0.00"), tax=Decimal("0.00"),
            total_amount=Decimal("55000.00"), paid_amount=Decimal("55000.00"),
            status=InvoiceStatus.PAID, payment_method="bank_transfer",
            created_by=accounts_user.id,
        ),
    ]
    db.add_all(invoices)
    await db.flush()

    # 6. Clinical Records
    clinical_records = [
        ClinicalRecord(
            patient_id=sunita.id, plugin_id="fertility", record_type="follicular_scan",
            data={
                "scan_date": (date.today() - timedelta(days=11)).isoformat(),
                "uterus_length_mm": 76.0, "endometrial_thickness_mm": 4.8, "endometrial_pattern": "trilaminar",
                "right_ovary_afc": 11, "left_ovary_afc": 10, "total_afc": 21,
                "sonographer_name": doc_meera.name, "impression": "Polycystic ovarian morphology with high antral follicle count.",
            },
            created_by=doc_meera.id,
        ),
        ClinicalRecord(
            patient_id=sunita.id, plugin_id="fertility", record_type="sonohysterogram",
            data={
                "procedure_date": (date.today() - timedelta(days=20)).isoformat(),
                "saline_volume_ml": 12.0, "cavity_contour": "regular_normal",
                "right_tube_patency": "patent", "left_tube_patency": "patent",
                "sis_impression": "Normal uterine cavity with bilateral free peritoneal spillage.",
            },
            created_by=doc_meera.id,
        ),
        ClinicalRecord(
            patient_id=rajesh.id, plugin_id="fertility", record_type="casa_semen_analysis",
            data={
                "collection_date": (date.today() - timedelta(days=10)).isoformat(),
                "abstinence_days": 3, "volume_ml": 3.2, "ph": 7.5, "liquefaction_time_min": 20,
                "pre_conc_million_ml": 42.0, "total_motility_pct": 58.0, "progressive_motility_pct": 38.0,
                "immotile_pct": 42.0, "normal_forms_pct": 4.0, "vcl_um_s": 46.0, "vsl_um_s": 26.0,
                "vitality_live_pct": 72.0, "analyst_name": emb_rahul.name,
                "impression": "Mild Asthenozoospermia (WHO 6th Edition).",
            },
            created_by=emb_rahul.id,
        ),
        ClinicalRecord(
            patient_id=rajesh.id, plugin_id="fertility", record_type="sperm_dfi",
            data={
                "test_date": (date.today() - timedelta(days=10)).isoformat(),
                "method_used": "scd_halosperm",
                "big_halo_pct": 58.0, "medium_halo_pct": 24.0, "small_halo_pct": 10.0,
                "without_halo_pct": 6.0, "degraded_pct": 2.0, "total_dfi_pct": 18.0,
                "dfi_interpretation": "good", "analyst_name": emb_rahul.name,
            },
            created_by=emb_rahul.id,
        ),
        ClinicalRecord(
            patient_id=kavita.id, plugin_id="fertility", record_type="early_pregnancy_scan",
            data={
                "scan_date": (date.today() - timedelta(days=5)).isoformat(),
                "gestational_age_weeks": "6w 4d", "number_of_sacs": 1, "sac_location": "intrauterine",
                "crl_mm": 7.2, "fhr_bpm": 128, "cardiac_activity": "present_regular", "yolk_sac_mm": 4.1,
                "sonographer_name": doc_meera.name,
                "impression": "Single live intrauterine pregnancy corresponding to 6 weeks 4 days. Excellent cardiac activity.",
            },
            created_by=doc_meera.id,
        ),
        ClinicalRecord(
            patient_id=anita.id, plugin_id="fertility", record_type="opd_consultation",
            data={
                "consultation_date": (date.today() - timedelta(days=2)).isoformat(),
                "chief_complaint": "Primary infertility 3 years. Severe male factor evaluation.",
                "investigations_ordered": "Serum AMH & Day 2 FSH/LH Hormonal Profile, Pelvic Doppler TVS",
                "provisional_diagnosis": "Male factor azoospermia; planned for surgical sperm retrieval (TESA)",
            },
            created_by=doc_meera.id,
        ),
    ]
    db.add_all(clinical_records)
    await db.flush()

    # 7. Appointments
    appointments = [
        Appointment(
            tenant_id=hospital.id,
            patient_id=sunita.id, doctor_id=doc_meera.id, department="fertility",
            scheduled_at=datetime.utcnow() + timedelta(hours=2),
            visit_type="procedure", status=AppointmentStatus.SCHEDULED,
            notes="Day 10 follicular tracking TVS scan",
        ),
        Appointment(
            tenant_id=hospital.id,
            patient_id=kavita.id, doctor_id=doc_meera.id, department="fertility",
            scheduled_at=datetime.utcnow() + timedelta(hours=3),
            visit_type="consultation", status=AppointmentStatus.SCHEDULED,
            notes="Early pregnancy review & progesterone prescription refill",
        ),
        Appointment(
            tenant_id=hospital.id,
            patient_id=priya.id, doctor_id=doc_meera.id, department="fertility",
            scheduled_at=datetime.utcnow() + timedelta(days=1, hours=4),
            visit_type="procedure", status=AppointmentStatus.SCHEDULED,
            notes="Insemination planned 36 hours post-trigger",
        ),
        Appointment(
            tenant_id=hospital.id,
            patient_id=anita.id, doctor_id=doc_meera.id, department="fertility",
            scheduled_at=datetime.utcnow() - timedelta(days=2),
            visit_type="consultation", status=AppointmentStatus.NO_SHOW,
            notes="Patient requested morning slot; did not check in.",
        ),
    ]
    db.add_all(appointments)
    await db.flush()


async def main():
    parser = argparse.ArgumentParser(description="VaidyaMD HMS Database Seeder")
    parser.add_argument(
        "--mode",
        choices=["base", "demo"],
        default=os.getenv("SEED_MODE", "demo"),
        help="Seeding mode: 'base' (production clean clinic infrastructure only) or 'demo' (base + 5 full demo couples and lab data)",
    )
    parser.add_argument(
        "--force-drop",
        action="store_true",
        default=os.getenv("FORCE_DROP_DB", "false").lower() in ("true", "1", "yes"),
        help="Force drop all existing tables prior to seeding",
    )
    args = parser.parse_args()

    print("=" * 60)
    print(f"🌱 VaidyaMD HMS — Database Seeder")
    print(f"   Mode: {args.mode.upper()} {'(PRODUCTION CLEAN)' if args.mode == 'base' else '(DEVELOPMENT DEMO)'}")
    print(f"   Force Drop Tables: {args.force_drop}")
    print("=" * 60)

    async with engine.begin() as conn:
        if args.force_drop:
            print("⚠️ Dropping existing tables (FORCE_DROP_DB=true)...")
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        base_data = await seed_base(db)
        await seed_cosgyn(db)
        await seed_pharmacy(db)
        if args.mode == "demo":
            await seed_demo_patients(db, base_data)
        await db.commit()

    print("=" * 60)
    if args.mode == "base":
        print("✅ Production Base Infrastructure Seeded Successfully! (0 Patients, Clean for Clinic Launch)")
    else:
        print("🎉 Development Demo Dataset Seeded Successfully! (5 Couples, Active Cycles, Lab & Billing)")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
