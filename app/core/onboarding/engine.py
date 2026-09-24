"""
VaidyaMD HMS — Onboarding Engine & Domain Builders
Clean, database-driven service to generate blank template headers, export live tenant
data as CSV, and ingest CSV files with conflict resolution (Overwrite vs Skip).
Zero demo data stored in this codebase.
"""

import io
import csv
import json
import logging
from uuid import UUID, uuid4
from datetime import date, datetime
from typing import Dict, Any, List, Optional
from sqlalchemy import select, or_, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

# Domain Models
from app.core.models.tenant import Hospital
from app.core.models.branch import Branch
from app.core.models.permission_profile import PermissionProfile
from app.core.models.user import User, UserRole
from app.modules.ipd.model import Ward, Bed
from app.modules.templates.model import ProtocolTemplate, ProtocolDrugRule, ClinicalTemplate
from app.modules.patients.model import Patient, Gender
from app.modules.billing.model import TreatmentPackage, ServiceItem
from app.modules.pharmacy.model import InventoryBatch, PharmacyVendor
from app.plugins.fertility.models import TreatmentCycleType
from app.plugins.cosgyn.models import CosgynTreatment
from app.core.security import hash_password, encrypt_pii, decrypt_pii

logger = logging.getLogger("vaidya.onboarding.engine")

# =====================================================================
# Canonical Domain Specifications (Schema Definitions)
# =====================================================================
DOMAIN_SPECS: Dict[str, Dict[str, Any]] = {
    "hospitals": {
        "index": 1,
        "slug": "01_hospitals_and_branches",
        "title": "Hospital Organization & Branches",
        "filename": "01_hospitals_and_branches.csv",
        "description": "Tenant legal identity, registration numbers, active branches, receipt headers, and IP whitelist.",
        "headers": [
            "record_type", "name", "code", "branch_name", "branch_code",
            "is_main_branch", "address", "city", "state", "pincode",
            "phone", "email", "gstin", "reg_number", "receipt_header", "ip_whitelist"
        ]
    },
    "staff": {
        "index": 2,
        "slug": "02_staff_users",
        "title": "Staff User Roster",
        "filename": "02_staff_users.csv",
        "description": "Medical, laboratory, nursing, and administrative staff roster with qualifications and licenses.",
        "headers": [
            "name", "email", "phone", "role", "branch_code",
            "qualification", "reg_number", "departments", "is_doctor"
        ]
    },
    "ipd": {
        "index": 3,
        "slug": "03_ipd_infrastructure",
        "title": "IPD Infrastructure (Wards & Beds)",
        "filename": "03_ipd_infrastructure.csv",
        "description": "Inpatient infrastructure including Wards (Daycare, General, Deluxe, HDU) and individual beds with daily tariffs.",
        "headers": [
            "record_type", "ward_code", "ward_name", "department",
            "base_charge_per_day", "bed_number", "bed_type", "daily_rate", "status", "branch_code"
        ]
    },
    "treatment_cycles": {
        "index": 4,
        "slug": "04_treatment_cycle_types",
        "title": "ART Treatment Cycle Modalities",
        "filename": "04_treatment_cycle_types.csv",
        "description": "Standard ART treatment cycle types, ICSI, FET, IUI, Third-Party, and Fertility Preservation modalities.",
        "headers": [
            "name", "category", "code", "description", "display_order", "is_active"
        ]
    },
    "service_catalog": {
        "index": 5,
        "slug": "05_service_catalog",
        "title": "Master Tariff / Service Catalog",
        "filename": "05_service_catalog.csv",
        "description": "Master billing catalog for OPD consultations, ultrasound scans, daycare procedures, and lab tariffs.",
        "headers": [
            "code", "name", "category", "base_price", "hsn_sac", "gst_rate", "branch_code"
        ]
    },
    "packages": {
        "index": 6,
        "slug": "06_billing_packages",
        "title": "Billing Packages & Bundles",
        "filename": "06_billing_packages.csv",
        "description": "Multi-disciplinary treatment packages (IVF-ICSI, FET, IUI, Hysteroscopy) with itemized fee breakdowns.",
        "headers": [
            "name", "plugin_id", "base_price", "description", "items_json", "branch_code"
        ]
    },
    "protocols": {
        "index": 7,
        "slug": "07_clinical_protocols",
        "title": "Stimulation Protocols & Drug Rules",
        "filename": "07_clinical_protocols.csv",
        "description": "Clinical stimulation protocols and sequential day-by-day drug administration rules with dosage and cycle offsets.",
        "headers": [
            "protocol_name", "category", "description", "drug_name", "dose",
            "route", "frequency", "sentinel_anchor", "day_start_offset",
            "day_end_offset", "instructions", "sort_order"
        ]
    },
    "templates": {
        "index": 8,
        "slug": "08_clinical_templates",
        "title": "Clinical Proformas, Order Sets & Rx Templates",
        "filename": "08_clinical_templates.csv",
        "description": "Clinical consultation proformas, OPD smart order sets, doctor Rx templates, and visit types with JSON schema fields.",
        "headers": [
            "title", "record_type", "plugin_id", "description", "schema_json", "branch_code"
        ]
    },
    "lims": {
        "index": 9,
        "slug": "09_lims_test_directory",
        "title": "LIMS Laboratory Test Directory",
        "filename": "09_lims_test_directory.csv",
        "description": "Complete diagnostic test panels, sample types, turnaround times, reference ranges, and quantitative report parameters.",
        "headers": [
            "test_code", "test_name", "category", "sample_type", "tat_hours", "parameters_json", "branch_code"
        ]
    },
    "cryo": {
        "index": 10,
        "slug": "10_cryo_infrastructure",
        "title": "Cryobank Physical Asset Infrastructure",
        "filename": "10_cryo_infrastructure.csv",
        "description": "Liquid nitrogen cryo tanks, canister numbers, color codes, goblet capacities, device types, and location mappings.",
        "headers": [
            "tank_code", "tank_name", "device_type", "total_canisters",
            "canister_capacity_goblets", "room_location", "canisters_json", "branch_code"
        ]
    },
    "pharmacy_vendors": {
        "index": 11,
        "slug": "11a_pharmacy_vendors",
        "title": "Pharmacy Approved Vendors",
        "filename": "11a_pharmacy_vendors.csv",
        "description": "Approved pharmaceutical distributors, manufacturers, GSTIN, contact numbers, email, and billing address.",
        "headers": [
            "name", "contact_phone", "contact_email", "gst_number", "address", "branch_code"
        ]
    },
    "pharmacy_stock": {
        "index": 11,
        "slug": "11b_pharmacy_stock",
        "title": "Pharmacy Formulary & Stock Batches",
        "filename": "11b_pharmacy_stock.csv",
        "description": "Formulary medicines, batch numbers, manufacturer, expiry dates, purchase rates, MRP, selling price, rack location, vendor name, and available quantities.",
        "headers": [
            "item_code", "item_name", "generic_name", "category", "batch_number", "manufacturer",
            "expiry_date", "purchase_rate", "mrp", "selling_price", "quantity_received", "quantity_available",
            "rack_location", "hsn_code", "vendor_name", "branch_code"
        ]
    },
    "patients": {
        "index": 12,
        "slug": "12_patients_bulk",
        "title": "Bulk Patients & Couple Linkages",
        "filename": "12_patients_bulk.csv",
        "description": "Bulk patient records, demographics, encrypted Aadhaar, 7-digit VID generation, and bidirectional couple linkages.",
        "headers": [
            "first_name", "last_name", "gender", "dob", "blood_group",
            "phone", "email", "aadhaar_raw", "city", "state", "pincode",
            "branch_code", "partner_email", "relationship_type"
        ]
    },
    "cosgyn": {
        "index": 13,
        "slug": "13_cosgyn_procedures",
        "title": "Cosmetic Gynaecology Catalogs",
        "filename": "13_cosgyn_procedures.csv",
        "description": "Cosmetic and functional gynaecology procedure directory with session counts and standard package tariffs.",
        "headers": [
            "treatment_name", "clinical_indication", "sessions_count", "price", "is_active"
        ]
    },
}

# Aliases to resolve domain keys easily (e.g. "billing" -> "packages", "service-catalog" -> "service_catalog")
DOMAIN_ALIASES: Dict[str, str] = {
    "01": "hospitals", "hospital": "hospitals", "branches": "hospitals",
    "02": "staff", "users": "staff",
    "03": "ipd", "wards": "ipd", "beds": "ipd",
    "04": "treatment_cycles", "cycles": "treatment_cycles", "art_cycles": "treatment_cycles",
    "05": "service_catalog", "tariffs": "service_catalog", "services": "service_catalog",
    "06": "packages", "billing": "packages", "billing_packages": "packages",
    "07": "protocols", "stimulation_protocols": "protocols",
    "08": "templates", "clinical_templates": "templates",
    "09": "lims", "lims_directory": "lims", "tests": "lims",
    "10": "cryo", "cryobank": "cryo", "tanks": "cryo",
    "11": "pharmacy_stock", "pharmacy": "pharmacy_stock", "pharmacy_inventory": "pharmacy_stock",
    "11a": "pharmacy_vendors", "vendors": "pharmacy_vendors", "pharmacy_vendors": "pharmacy_vendors",
    "11b": "pharmacy_stock", "stock": "pharmacy_stock", "pharmacy_stock": "pharmacy_stock",
    "12": "patients", "couples": "patients",
    "13": "cosgyn", "cosmetic_gynae": "cosgyn",
}


def normalize_domain_key(domain: str) -> str:
    """Normalize input domain key or alias to canonical domain spec key."""
    d = domain.lower().strip().replace("-", "_")
    if d in DOMAIN_SPECS:
        return d
    if d in DOMAIN_ALIASES:
        return DOMAIN_ALIASES[d]
    # Check if prefixed like '01_hospitals_and_branches'
    for k, spec in DOMAIN_SPECS.items():
        if spec["slug"] == d or spec["filename"].replace(".csv", "") == d or d.startswith(f"{spec['index']:02d}"):
            return k
    raise ValueError(f"Unknown domain: '{domain}'. Valid domains: {list(DOMAIN_SPECS.keys())}")


def get_blank_template_csv(domain: str) -> str:
    """Dynamically generate a clean, empty CSV with canonical headers for the domain."""
    d_key = normalize_domain_key(domain)
    spec = DOMAIN_SPECS[d_key]
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(spec["headers"])
    return out.getvalue()


# Helper to safely extract and strip string from dict row
def s_get(row: dict, key: str, default: str = "") -> str:
    val = row.get(key)
    if val is None:
        for k in row.keys():
            if k and k.strip().lower() == key.strip().lower():
                val = row[k]
                break
    if val is None:
        return default
    return str(val).strip()


# =====================================================================
# Live Data Exporters
# =====================================================================
async def export_domain_csv(session: AsyncSession, hospital_id: UUID, domain: str) -> str:
    """Query live PostgreSQL records for the specified hospital and format as canonical CSV."""
    d_key = normalize_domain_key(domain)
    spec = DOMAIN_SPECS[d_key]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=spec["headers"], lineterminator="\r\n")
    writer.writeheader()

    # Resolve branches map
    branches_res = await session.execute(select(Branch).where(Branch.hospital_id == hospital_id))
    branches = {b.id: b for b in branches_res.scalars().all()}
    branch_by_code = {b.code.upper(): b for b in branches.values()}

    if d_key == "hospitals":
        h_res = await session.execute(select(Hospital).where(Hospital.id == hospital_id))
        hosp = h_res.scalar_one_or_none()
        if hosp:
            for b in branches.values():
                b_hdr = b.receipt_header if isinstance(b.receipt_header, dict) else {}
                writer.writerow({
                    "record_type": "BRANCH",
                    "name": hosp.name,
                    "code": hosp.code,
                    "branch_name": b.name,
                    "branch_code": b.code,
                    "is_main_branch": "TRUE" if b.is_main_branch else "FALSE",
                    "address": b.address or "",
                    "city": getattr(b, "city", "") or b_hdr.get("city", "") or "",
                    "state": getattr(b, "state", "") or b_hdr.get("state", "") or "",
                    "pincode": getattr(b, "pincode", "") or b_hdr.get("pincode", "") or "",
                    "phone": b.phone or "",
                    "email": b.email or "",
                    "gstin": b.gstin or "",
                    "reg_number": getattr(b, "reg_number", "") or b_hdr.get("reg_number", "") or "",
                    "receipt_header": json.dumps(b.receipt_header) if b.receipt_header else "",
                    "ip_whitelist": ",".join(b.ip_whitelist or [])
                })

    elif d_key == "staff":
        u_res = await session.execute(select(User).where(User.tenant_id == hospital_id).order_by(User.name))
        users = u_res.scalars().all()
        for u in users:
            b_code = branches[u.branch_id].code if u.branch_id and u.branch_id in branches else "MAIN"
            writer.writerow({
                "name": u.name,
                "email": u.email,
                "phone": u.phone or "",
                "role": u.role.value if hasattr(u.role, "value") else str(u.role).upper(),
                "branch_code": b_code,
                "qualification": u.qualification or "",
                "reg_number": u.reg_number or "",
                "departments": ",".join(u.departments or []),
                "is_doctor": "TRUE" if u.is_doctor else "FALSE"
            })

    elif d_key == "ipd":
        w_res = await session.execute(select(Ward).where(Ward.tenant_id == hospital_id).order_by(Ward.code))
        wards = w_res.scalars().all()
        for w in wards:
            b_code = branches[w.branch_id].code if w.branch_id in branches else "MAIN"
            writer.writerow({
                "record_type": "WARD",
                "ward_code": w.code,
                "ward_name": w.name,
                "department": w.department,
                "base_charge_per_day": str(w.base_charge_per_day),
                "bed_number": "",
                "bed_type": "",
                "daily_rate": str(w.base_charge_per_day),
                "status": "available" if w.is_active else "inactive",
                "branch_code": b_code
            })
            b_res = await session.execute(select(Bed).where(Bed.ward_id == w.id).order_by(Bed.bed_number))
            beds = b_res.scalars().all()
            for bd in beds:
                writer.writerow({
                    "record_type": "BED",
                    "ward_code": w.code,
                    "ward_name": "",
                    "department": "",
                    "base_charge_per_day": "0",
                    "bed_number": bd.bed_number,
                    "bed_type": bd.bed_type,
                    "daily_rate": str(bd.daily_rate),
                    "status": bd.status,
                    "branch_code": b_code
                })

    elif d_key == "treatment_cycles":
        tc_res = await session.execute(
            select(TreatmentCycleType)
            .where(TreatmentCycleType.tenant_id == hospital_id)
            .order_by(TreatmentCycleType.display_order, TreatmentCycleType.name)
        )
        types = tc_res.scalars().all()
        for t in types:
            writer.writerow({
                "name": t.name,
                "category": getattr(t, "category", "General") or "General",
                "code": getattr(t, "code", "") or "",
                "description": getattr(t, "description", "") or "",
                "display_order": str(getattr(t, "display_order", 0) or 0),
                "is_active": "TRUE" if getattr(t, "is_active", True) else "FALSE"
            })

    elif d_key == "service_catalog":
        sc_res = await session.execute(
            select(ServiceItem)
            .where(ServiceItem.tenant_id == hospital_id)
            .order_by(ServiceItem.category, ServiceItem.name)
        )
        items = sc_res.scalars().all()
        for it in items:
            b_code = branches[it.branch_id].code if it.branch_id in branches else "MAIN"
            writer.writerow({
                "code": it.code,
                "name": it.name,
                "category": it.category,
                "base_price": str(it.base_price),
                "hsn_sac": it.hsn_sac or "",
                "gst_rate": str(it.gst_rate or 0.0),
                "branch_code": b_code
            })

    elif d_key == "packages":
        pkg_res = await session.execute(
            select(TreatmentPackage)
            .where(TreatmentPackage.tenant_id == hospital_id)
            .order_by(TreatmentPackage.name)
        )
        pkgs = pkg_res.scalars().all()
        for p in pkgs:
            b_code = branches[p.branch_id].code if p.branch_id in branches else "MAIN"
            writer.writerow({
                "name": p.name,
                "plugin_id": p.plugin_id or "fertility",
                "base_price": str(p.base_price),
                "description": p.description or "",
                "items_json": json.dumps(p.items) if p.items else "[]",
                "branch_code": b_code
            })

    elif d_key == "protocols":
        pt_res = await session.execute(
            select(ProtocolTemplate)
            .where(ProtocolTemplate.hospital_id == hospital_id)
            .order_by(ProtocolTemplate.name)
        )
        templates = pt_res.scalars().all()
        for t in templates:
            r_res = await session.execute(
                select(ProtocolDrugRule)
                .where(ProtocolDrugRule.protocol_template_id == t.id)
                .order_by(ProtocolDrugRule.sort_order)
            )
            rules = r_res.scalars().all()
            for r in rules:
                writer.writerow({
                    "protocol_name": t.name,
                    "category": t.category,
                    "description": t.description or "",
                    "drug_name": r.drug_name,
                    "dose": r.dose,
                    "route": r.route or "SC",
                    "frequency": r.frequency or "OD",
                    "sentinel_anchor": r.sentinel_anchor or "stim_start",
                    "day_start_offset": str(r.day_start_offset),
                    "day_end_offset": str(r.day_end_offset),
                    "instructions": r.instructions or "",
                    "sort_order": str(r.sort_order or 0)
                })

    elif d_key == "templates":
        ct_res = await session.execute(
            select(ClinicalTemplate)
            .where(ClinicalTemplate.tenant_id == hospital_id)
            .order_by(ClinicalTemplate.plugin_id, ClinicalTemplate.title)
        )
        templates = ct_res.scalars().all()
        for t in templates:
            b_code = branches[t.branch_id].code if t.branch_id in branches else "MAIN"
            writer.writerow({
                "title": t.title,
                "record_type": t.record_type,
                "plugin_id": t.plugin_id,
                "description": t.description or "",
                "schema_json": json.dumps(t.schema_json) if t.schema_json else "{}",
                "branch_code": b_code
            })

    elif d_key == "lims":
        ct_res = await session.execute(
            select(ClinicalTemplate)
            .where(ClinicalTemplate.tenant_id == hospital_id, ClinicalTemplate.plugin_id == "lims")
            .order_by(ClinicalTemplate.title)
        )
        panels = ct_res.scalars().all()
        for p in panels:
            s_data = p.schema_json or {}
            writer.writerow({
                "test_code": s_data.get("test_code", p.record_type),
                "test_name": p.title,
                "category": s_data.get("category", "General"),
                "sample_type": s_data.get("sample_type", "Serum"),
                "tat_hours": str(s_data.get("tat_hours", 4)),
                "parameters_json": json.dumps(s_data.get("parameters", [])),
                "branch_code": "MAIN"
            })

    elif d_key == "cryo":
        ct_res = await session.execute(
            select(ClinicalTemplate)
            .where(ClinicalTemplate.tenant_id == hospital_id, ClinicalTemplate.plugin_id == "fertility_cryo")
            .order_by(ClinicalTemplate.title)
        )
        tanks = ct_res.scalars().all()
        for t in tanks:
            s_data = t.schema_json or {}
            writer.writerow({
                "tank_code": s_data.get("tank_code", t.record_type),
                "tank_name": t.title,
                "device_type": s_data.get("device_type", "Vapor LN2 Tank"),
                "total_canisters": str(s_data.get("total_canisters", 6)),
                "canister_capacity_goblets": str(s_data.get("canister_capacity_goblets", 10)),
                "room_location": s_data.get("room_location", "Cryo Storage"),
                "canisters_json": json.dumps(s_data.get("canisters", [])),
                "branch_code": "MAIN"
            })

    elif d_key in ["pharmacy_vendors", "vendors"]:
        v_res = await session.execute(
            select(PharmacyVendor).where(PharmacyVendor.tenant_id == hospital_id)
        )
        vendors = v_res.scalars().all()
        for v in vendors:
            b_code = branches[v.branch_id].code if getattr(v, "branch_id", None) and v.branch_id in branches else "MAIN"
            writer.writerow({
                "name": v.name,
                "contact_phone": getattr(v, "contact_phone", "") or "",
                "contact_email": getattr(v, "contact_email", "") or "",
                "gst_number": getattr(v, "gst_number", "") or "",
                "address": getattr(v, "address", "") or "",
                "branch_code": b_code
            })

    elif d_key in ["pharmacy_stock", "pharmacy", "stock"]:
        b_res = await session.execute(
            select(InventoryBatch)
            .where(InventoryBatch.tenant_id == hospital_id)
            .order_by(InventoryBatch.batch_number)
        )
        batches = b_res.scalars().all()
        for b in batches:
            b_code = branches[b.branch_id].code if getattr(b, "branch_id", None) and b.branch_id in branches else "MAIN"
            writer.writerow({
                "item_code": getattr(b, "item_code", "") or getattr(b, "sku", "") or "",
                "item_name": getattr(b, "item_name", "") or "",
                "generic_name": getattr(b, "generic_name", "") or "",
                "category": getattr(b, "category", "") or "Pharmacy",
                "batch_number": b.batch_number,
                "manufacturer": getattr(b, "manufacturer", "") or "",
                "expiry_date": b.expiry_date.isoformat() if getattr(b, "expiry_date", None) else "",
                "purchase_rate": str(getattr(b, "purchase_rate", 0.0) or 0.0),
                "mrp": str(getattr(b, "mrp", 0.0) or 0.0),
                "selling_price": str(getattr(b, "selling_price", 0.0) or getattr(b, "mrp", 0.0) or 0.0),
                "quantity_received": str(getattr(b, "quantity_received", 0) or getattr(b, "quantity", 0) or 0),
                "quantity_available": str(getattr(b, "quantity_available", 0) or getattr(b, "quantity", 0) or 0),
                "rack_location": getattr(b, "rack_location", "") or "",
                "hsn_code": getattr(b, "hsn_code", "") or "3004",
                "vendor_name": getattr(b, "vendor_name", "") or "",
                "branch_code": b_code
            })

    elif d_key == "patients":
        p_res = await session.execute(
            select(Patient)
            .where(Patient.tenant_id == hospital_id)
            .order_by(Patient.created_at.desc())
        )
        patients = p_res.scalars().all()
        for p in patients:
            aadhaar_decrypted = ""
            if getattr(p, "aadhaar_encrypted", None):
                try:
                    aadhaar_decrypted = decrypt_pii(p.aadhaar_encrypted)
                except Exception:
                    aadhaar_decrypted = ""
            b_code = branches[p.branch_id].code if getattr(p, "branch_id", None) and p.branch_id in branches else "MAIN"
            p_first = getattr(p, "first_name", "") or getattr(p, "name", "")
            p_last = getattr(p, "last_name", "") or getattr(p, "surname", "") or ""
            p_gender = p.gender.value if hasattr(getattr(p, "gender", ""), "value") else str(getattr(p, "gender", ""))
            writer.writerow({
                "first_name": p_first,
                "last_name": p_last,
                "gender": p_gender,
                "dob": p.dob.isoformat() if getattr(p, "dob", None) else "",
                "blood_group": getattr(p, "blood_group", "") or "",
                "phone": getattr(p, "phone", "") or "",
                "email": getattr(p, "email", "") or "",
                "aadhaar_raw": aadhaar_decrypted,
                "city": getattr(p, "city", "") or getattr(p, "area", "") or "",
                "state": getattr(p, "state", "") or "",
                "pincode": getattr(p, "pincode", "") or "",
                "branch_code": b_code,
                "partner_email": "",
                "relationship_type": ""
            })

    elif d_key == "cosgyn":
        cg_res = await session.execute(
            select(CosgynTreatment)
            .where(CosgynTreatment.tenant_id == hospital_id)
            .order_by(getattr(CosgynTreatment, "name", CosgynTreatment.id))
        )
        treatments = cg_res.scalars().all()
        for t in treatments:
            writer.writerow({
                "treatment_name": getattr(t, "name", "") or getattr(t, "treatment_name", ""),
                "clinical_indication": getattr(t, "package_combo", "") or getattr(t, "clinical_indication", ""),
                "sessions_count": str(getattr(t, "jet_plasma_sessions", 1) or getattr(t, "sessions_count", 1)),
                "price": str(getattr(t, "price", 0.0) or 0.0),
                "is_active": "TRUE" if getattr(t, "is_active", True) else "FALSE"
            })

    return out.getvalue()


# =====================================================================
# In-App CSV Preview Engine (Conflict & Override Analysis)
# =====================================================================
async def preview_domain_csv(
    session: AsyncSession,
    hospital_id: UUID,
    domain: str,
    csv_content: str,
    conflict_mode: str = "overwrite"
) -> Dict[str, Any]:
    """Analyze uploaded CSV rows against live tenant database to detect new vs overriding rows."""
    d_key = normalize_domain_key(domain)
    conflict_mode = conflict_mode.lower().strip()
    if conflict_mode not in ["overwrite", "skip"]:
        conflict_mode = "overwrite"

    f = io.StringIO(csv_content.strip())
    reader = list(csv.DictReader(f))
    if not reader:
        return {
            "success": False,
            "error": "CSV file contains no data rows.",
            "total_rows": 0,
            "to_create": 0,
            "inserted": 0,
            "to_update": 0,
            "updated": 0,
            "to_skip": 0,
            "skipped": 0,
            "preview_rows": [],
            "errors": [],
        }

    existing_set: set = set()
    name_map: dict = {}

    try:
        if d_key == "hospitals":
            b_res = await session.execute(select(Branch.code, Branch.name).where(Branch.hospital_id == hospital_id))
            for b_c, b_n in b_res.all():
                if b_c:
                    code_key = b_c.upper().strip()
                    existing_set.add(code_key)
                    name_map[code_key] = b_n
        elif d_key == "staff":
            u_res = await session.execute(select(User.email, User.name).where(User.tenant_id == hospital_id))
            for em, nm in u_res.all():
                if em:
                    em_key = em.lower().strip()
                    existing_set.add(em_key)
                    name_map[em_key] = nm
        elif d_key == "ipd":
            w_res = await session.execute(select(Ward.code, Ward.name).where(Ward.tenant_id == hospital_id))
            for wc, wn in w_res.all():
                if wc:
                    w_k = f"WARD:{wc.upper().strip()}"
                    existing_set.add(w_k)
                    name_map[w_k] = wn
            bed_res = await session.execute(select(Bed.bed_number, Ward.code).join(Ward, Bed.ward_id == Ward.id).where(Ward.tenant_id == hospital_id))
            for bnum, wc in bed_res.all():
                if bnum:
                    b_k = f"BED:{bnum.strip().upper()}"
                    existing_set.add(b_k)
                    name_map[b_k] = f"Bed {bnum} ({wc})"
        elif d_key == "treatment_cycles":
            tc_res = await session.execute(select(TreatmentCycleType.name).where(TreatmentCycleType.tenant_id == hospital_id))
            for (t_name,) in tc_res.all():
                if t_name:
                    existing_set.add(t_name.lower().strip())
        elif d_key == "service_catalog":
            s_res = await session.execute(select(ServiceItem.code, ServiceItem.name).where(ServiceItem.tenant_id == hospital_id))
            for sc, sn in s_res.all():
                if sc:
                    existing_set.add(sc.lower().strip())
                    name_map[sc.lower().strip()] = sn
        elif d_key == "packages":
            p_res = await session.execute(select(TreatmentPackage.code, TreatmentPackage.name).where(TreatmentPackage.tenant_id == hospital_id))
            for pc, pn in p_res.all():
                if pc:
                    existing_set.add(pc.lower().strip())
                    name_map[pc.lower().strip()] = pn
        elif d_key == "protocols":
            pr_res = await session.execute(select(ProtocolTemplate.name).where(ProtocolTemplate.tenant_id == hospital_id))
            for (pr_name,) in pr_res.all():
                if pr_name:
                    existing_set.add(pr_name.lower().strip())
        elif d_key in ["templates", "lims", "cryo"]:
            t_res = await session.execute(select(ClinicalTemplate.record_type, ClinicalTemplate.title).where(ClinicalTemplate.tenant_id == hospital_id))
            for rt, tt in t_res.all():
                if rt:
                    existing_set.add(rt.lower().strip())
                    name_map[rt.lower().strip()] = tt
        elif d_key in ["pharmacy_vendors", "vendors"]:
            v_res = await session.execute(select(PharmacyVendor.name).where(PharmacyVendor.tenant_id == hospital_id))
            for (vn,) in v_res.all():
                if vn:
                    existing_set.add(vn.lower().strip())
        elif d_key in ["pharmacy_stock", "pharmacy", "stock"]:
            st_res = await session.execute(select(InventoryBatch.batch_number, InventoryBatch.item_name).where(InventoryBatch.tenant_id == hospital_id))
            for bn, iname in st_res.all():
                if bn:
                    existing_set.add(bn.lower().strip())
                    name_map[bn.lower().strip()] = iname
        elif d_key == "patients":
            pt_res = await session.execute(select(Patient.phone, Patient.name).where(Patient.tenant_id == hospital_id))
            for p_phone, p_name in pt_res.all():
                if p_phone:
                    existing_set.add(p_phone.lower().strip())
                    name_map[p_phone.lower().strip()] = p_name
        elif d_key == "cosgyn":
            cg_res = await session.execute(select(CosgynTreatment.treatment_name).where(CosgynTreatment.tenant_id == hospital_id))
            for (tn,) in cg_res.all():
                if tn:
                    existing_set.add(tn.lower().strip())
    except Exception as query_err:
        logger.warning("Could not pre-fetch existing records for domain %s: %s", d_key, query_err)

    preview_rows = []
    to_create = 0
    to_update = 0
    to_skip = 0

    for idx, r in enumerate(reader):
        row_num = idx + 1
        ident = ""
        display_name = ""
        is_override = False

        if d_key == "hospitals":
            b_code = s_get(r, "branch_code").upper() or "MAIN"
            ident = b_code
            display_name = s_get(r, "branch_name") or s_get(r, "name") or b_code
            is_override = b_code in existing_set
        elif d_key == "staff":
            email = s_get(r, "email").lower().strip()
            ident = email
            display_name = s_get(r, "name") or email
            is_override = email in existing_set
        elif d_key == "ipd":
            rec_type = s_get(r, "record_type").upper()
            w_code = s_get(r, "ward_code").upper()
            bed_num = s_get(r, "bed_number")
            if rec_type == "BED" or bed_num:
                ident = f"Bed {bed_num}"
                display_name = f"Bed {bed_num} ({w_code})"
                is_override = f"BED:{bed_num.strip().upper()}" in existing_set
            else:
                ident = w_code
                display_name = s_get(r, "ward_name") or w_code
                is_override = f"WARD:{w_code.strip().upper()}" in existing_set
        elif d_key == "treatment_cycles":
            name = s_get(r, "name")
            ident = s_get(r, "code") or name
            display_name = name
            is_override = name.lower().strip() in existing_set
        elif d_key == "service_catalog":
            code = s_get(r, "code") or s_get(r, "service_code")
            ident = code
            display_name = s_get(r, "name") or s_get(r, "service_name") or code
            is_override = code.lower().strip() in existing_set
        elif d_key == "packages":
            code = s_get(r, "code") or s_get(r, "package_code")
            ident = code
            display_name = s_get(r, "name") or s_get(r, "package_name") or code
            is_override = code.lower().strip() in existing_set
        elif d_key == "protocols":
            name = s_get(r, "name") or s_get(r, "protocol_name")
            ident = name
            display_name = name
            is_override = name.lower().strip() in existing_set
        elif d_key in ["templates", "lims", "cryo"]:
            rec_type = s_get(r, "record_type") or s_get(r, "test_code") or s_get(r, "tank_code")
            title = s_get(r, "title") or s_get(r, "test_name") or s_get(r, "tank_name") or rec_type
            ident = rec_type
            display_name = title
            is_override = rec_type.lower().strip() in existing_set
        elif d_key in ["pharmacy_vendors", "vendors"]:
            v_name = s_get(r, "name") or s_get(r, "vendor_name")
            ident = v_name
            display_name = v_name
            is_override = v_name.lower().strip() in existing_set
        elif d_key in ["pharmacy_stock", "pharmacy", "stock"]:
            b_num = s_get(r, "batch_number")
            sku = s_get(r, "item_code") or s_get(r, "item_name") or b_num
            ident = f"Batch {b_num}"
            display_name = f"{sku} (Qty: {s_get(r, 'quantity_available') or s_get(r, 'quantity') or 0})"
            is_override = b_num.lower().strip() in existing_set
        elif d_key == "patients":
            p_phone = s_get(r, "phone").strip()
            p_name = f"{s_get(r, 'first_name')} {s_get(r, 'last_name')}".strip() or s_get(r, "name") or p_phone
            ident = p_phone or p_name
            display_name = f"{p_name} ({p_phone})" if p_phone else p_name
            is_override = p_phone.lower().strip() in existing_set if p_phone else False
        elif d_key == "cosgyn":
            name = s_get(r, "treatment_name")
            ident = name
            display_name = name
            is_override = name.lower().strip() in existing_set
        else:
            first_val = list(r.values())[0] if r else str(row_num)
            second_val = list(r.values())[1] if len(r) > 1 else ""
            ident = first_val
            display_name = second_val or first_val
            is_override = False

        if is_override:
            if conflict_mode == "overwrite":
                action = "update"
                to_update += 1
                details = f"Existing record '{name_map.get(ident.lower(), ident)}' found in database. Will be overwritten/updated."
            else:
                action = "skip"
                to_skip += 1
                details = f"Existing record '{name_map.get(ident.lower(), ident)}' found in database. Will be preserved (skipped)."
        else:
            action = "create"
            to_create += 1
            details = "New record. Will be inserted."

        preview_rows.append({
            "row_index": row_num,
            "identifier": ident,
            "name": display_name,
            "action": action,
            "is_override": is_override,
            "details": details,
            "raw": dict(r)
        })

    return {
        "success": True,
        "domain": d_key,
        "total_rows": len(reader),
        "to_create": to_create,
        "inserted": to_create,
        "to_update": to_update,
        "updated": to_update,
        "to_skip": to_skip,
        "skipped": to_skip,
        "preview_rows": preview_rows,
        "errors": []
    }


# =====================================================================
# In-App CSV Ingestion Engine
# =====================================================================
async def import_domain_csv(
    session: AsyncSession,
    hospital_id: UUID,
    domain: str,
    csv_content: str,
    conflict_mode: str = "overwrite"
) -> Dict[str, Any]:
    """Parse, validate, and ingest uploaded CSV rows into the tenant's database."""
    d_key = normalize_domain_key(domain)
    conflict_mode = conflict_mode.lower().strip()
    if conflict_mode not in ["overwrite", "skip"]:
        conflict_mode = "overwrite"

    stats = {"domain": d_key, "created": 0, "inserted": 0, "updated": 0, "skipped": 0, "total_rows": 0, "errors": []}

    # Fetch Hospital
    h_res = await session.execute(select(Hospital).where(Hospital.id == hospital_id))
    hospital = h_res.scalar_one_or_none()
    if not hospital:
        return {"success": False, "error": f"Hospital ID {hospital_id} not found."}

    # Fetch branches
    b_res = await session.execute(select(Branch).where(Branch.hospital_id == hospital_id))
    branches = {b.code.upper(): b for b in b_res.scalars().all()}
    if not branches:
        # Auto-create default MAIN branch if completely missing
        main_b = Branch(
            hospital_id=hospital.id,
            name=f"{hospital.name} Main",
            code="MAIN",
            is_main_branch=True,
            is_active=True
        )
        session.add(main_b)
        await session.flush()
        branches["MAIN"] = main_b

    primary_branch = list(branches.values())[0]

    # Parse CSV content
    f = io.StringIO(csv_content.strip())
    reader = list(csv.DictReader(f))
    if not reader:
        return {"success": False, "error": "CSV file contains no data rows."}

    try:
        if d_key == "hospitals":
            for r in reader:
                rec_type = s_get(r, "record_type").upper()
                if rec_type in ["BRANCH", ""]:
                    b_code = s_get(r, "branch_code").upper() or "MAIN"
                    b_name = s_get(r, "branch_name") or f"{hospital.name} {b_code}"
                    existing_b = branches.get(b_code)
                    if existing_b:
                        if conflict_mode == "overwrite":
                            existing_b.name = b_name
                            existing_b.address = s_get(r, "address") or existing_b.address
                            existing_b.city = s_get(r, "city") or existing_b.city
                            existing_b.state = s_get(r, "state") or existing_b.state
                            existing_b.pincode = s_get(r, "pincode") or existing_b.pincode
                            existing_b.phone = s_get(r, "phone") or existing_b.phone
                            existing_b.email = s_get(r, "email") or existing_b.email
                            existing_b.gstin = s_get(r, "gstin") or existing_b.gstin
                            existing_b.reg_number = s_get(r, "reg_number") or existing_b.reg_number
                            raw_hdr = s_get(r, "receipt_header")
                            if raw_hdr:
                                try:
                                    existing_b.receipt_header = json.loads(raw_hdr)
                                except Exception:
                                    pass
                            raw_ips = s_get(r, "ip_whitelist")
                            if raw_ips:
                                existing_b.ip_whitelist = [x.strip() for x in raw_ips.split(",") if x.strip()]
                            stats["updated"] += 1
                        else:
                            stats["skipped"] += 1
                    else:
                        new_b = Branch(
                            hospital_id=hospital.id,
                            name=b_name,
                            code=b_code,
                            address=s_get(r, "address"),
                            city=s_get(r, "city"),
                            state=s_get(r, "state"),
                            pincode=s_get(r, "pincode"),
                            phone=s_get(r, "phone"),
                            email=s_get(r, "email"),
                            gstin=s_get(r, "gstin"),
                            reg_number=s_get(r, "reg_number"),
                            is_main_branch=s_get(r, "is_main_branch").upper() == "TRUE",
                            is_active=True
                        )
                        raw_hdr = s_get(r, "receipt_header")
                        if raw_hdr:
                            try:
                                new_b.receipt_header = json.loads(raw_hdr)
                            except Exception:
                                pass
                        raw_ips = s_get(r, "ip_whitelist")
                        if raw_ips:
                            new_b.ip_whitelist = [x.strip() for x in raw_ips.split(",") if x.strip()]
                        session.add(new_b)
                        branches[b_code] = new_b
                        stats["created"] += 1

        elif d_key == "staff":
            default_hash = hash_password("vaidya_md_2026")
            for r in reader:
                email = s_get(r, "email").lower()
                name = s_get(r, "name")
                if not email or not name:
                    continue
                role_str = s_get(r, "role").upper()
                try:
                    role_enum = UserRole[role_str]
                except KeyError:
                    role_enum = UserRole.DOCTOR if s_get(r, "is_doctor").upper() == "TRUE" else UserRole.ADMIN

                b_code = s_get(r, "branch_code").upper()
                target_b = branches.get(b_code) or primary_branch
                is_doc = s_get(r, "is_doctor").upper() == "TRUE" or role_enum in [UserRole.DOCTOR, UserRole.ANDROLOGIST, UserRole.EMBRYOLOGIST]

                u_res = await session.execute(select(User).where(User.email == email))
                existing_u = u_res.scalar_one_or_none()
                if existing_u:
                    if conflict_mode == "overwrite":
                        existing_u.name = name
                        existing_u.role = role_enum
                        existing_u.branch_id = target_b.id
                        existing_u.qualification = s_get(r, "qualification") or existing_u.qualification
                        existing_u.reg_number = s_get(r, "reg_number") or existing_u.reg_number
                        existing_u.phone = s_get(r, "phone") or existing_u.phone
                        existing_u.is_doctor = is_doc
                        stats["updated"] += 1
                    else:
                        stats["skipped"] += 1
                else:
                    new_u = User(
                        tenant_id=hospital.id,
                        branch_id=target_b.id,
                        email=email,
                        name=name,
                        hashed_password=default_hash,
                        role=role_enum,
                        is_doctor=is_doc,
                        qualification=s_get(r, "qualification"),
                        reg_number=s_get(r, "reg_number"),
                        phone=s_get(r, "phone"),
                        departments=[d.strip() for d in s_get(r, "departments").split(",") if d.strip()],
                        is_active=True
                    )
                    session.add(new_u)
                    stats["created"] += 1

        elif d_key == "ipd":
            ward_cache: dict[str, Ward] = {}
            for r in reader:
                rec_type = s_get(r, "record_type").upper()
                w_code = s_get(r, "ward_code").upper()
                if not w_code:
                    continue

                b_code = s_get(r, "branch_code").upper()
                target_b = branches.get(b_code) or primary_branch
                rate = float(s_get(r, "base_charge_per_day") or 2500)
                bed_rate = float(s_get(r, "daily_rate") or rate)
                w_name = s_get(r, "ward_name")
                bed_num = s_get(r, "bed_number")

                # If explicitly a WARD row, or has ward_name without bed_number
                if rec_type == "WARD" or (w_name and not bed_num):
                    w_res = await session.execute(select(Ward).where(Ward.tenant_id == hospital.id, Ward.code == w_code))
                    ward = w_res.scalar_one_or_none()
                    if not ward:
                        ward = Ward(
                            tenant_id=hospital.id,
                            branch_id=target_b.id,
                            name=w_name or w_code,
                            code=w_code,
                            department=s_get(r, "department") or "General IPD",
                            base_charge_per_day=rate,
                            total_beds=0,
                            is_active=True
                        )
                        session.add(ward)
                        await session.flush()
                        stats["created"] += 1
                    else:
                        if conflict_mode == "overwrite":
                            ward.name = w_name or ward.name
                            ward.department = s_get(r, "department") or ward.department
                            ward.base_charge_per_day = rate
                            ward.branch_id = target_b.id
                            stats["updated"] += 1
                        else:
                            stats["skipped"] += 1
                    ward_cache[w_code] = ward

                # If BED row or has bed_number
                if rec_type == "BED" or bed_num:
                    ward = ward_cache.get(w_code)
                    if not ward:
                        w_res = await session.execute(select(Ward).where(Ward.tenant_id == hospital.id, Ward.code == w_code))
                        ward = w_res.scalar_one_or_none()
                        if not ward and w_name:
                            ward = Ward(
                                tenant_id=hospital.id,
                                branch_id=target_b.id,
                                name=w_name,
                                code=w_code,
                                department=s_get(r, "department") or "General IPD",
                                base_charge_per_day=rate,
                                total_beds=0,
                                is_active=True
                            )
                            session.add(ward)
                            await session.flush()
                            stats["created"] += 1
                        if ward:
                            ward_cache[w_code] = ward

                    if ward and bed_num:
                        b_status = s_get(r, "status") or "Vacant"
                        if b_status.lower() in ("available", "vacant"):
                            b_status = "Vacant"
                        b_type = s_get(r, "bed_type") or "Standard"
                        b_res = await session.execute(select(Bed).where(Bed.ward_id == ward.id, Bed.bed_number == bed_num))
                        existing_bed = b_res.scalar_one_or_none()
                        if existing_bed:
                            if conflict_mode == "overwrite":
                                existing_bed.bed_type = b_type
                                existing_bed.daily_rate = bed_rate
                                existing_bed.status = b_status
                                stats["updated"] += 1
                            else:
                                stats["skipped"] += 1
                        else:
                            new_bed = Bed(
                                tenant_id=hospital.id,
                                branch_id=ward.branch_id,
                                ward_id=ward.id,
                                bed_number=bed_num,
                                bed_type=b_type,
                                daily_rate=bed_rate,
                                status=b_status,
                            )
                            session.add(new_bed)
                            ward.total_beds = (ward.total_beds or 0) + 1
                            stats["created"] += 1

        elif d_key == "treatment_cycles":
            for r in reader:
                name = s_get(r, "name")
                if not name:
                    continue
                cat = s_get(r, "category") or "General"
                q = select(TreatmentCycleType).where(TreatmentCycleType.tenant_id == hospital.id, TreatmentCycleType.name == name)
                res = await session.execute(q)
                existing = res.scalar_one_or_none()
                if existing:
                    if conflict_mode == "overwrite":
                        existing.category = cat
                        existing.code = s_get(r, "code") or existing.code
                        existing.description = s_get(r, "description") or existing.description
                        existing.display_order = int(s_get(r, "display_order") or 0)
                        existing.is_active = s_get(r, "is_active").upper() == "TRUE"
                        stats["updated"] += 1
                    else:
                        stats["skipped"] += 1
                else:
                    new_item = TreatmentCycleType(
                        tenant_id=hospital.id,
                        name=name,
                        category=cat,
                        code=s_get(r, "code") or None,
                        description=s_get(r, "description"),
                        display_order=int(s_get(r, "display_order") or 0),
                        is_active=s_get(r, "is_active").upper() != "FALSE"
                    )
                    session.add(new_item)
                    stats["created"] += 1

        elif d_key == "service_catalog":
            for r in reader:
                code = s_get(r, "code") or s_get(r, "service_code")
                name = s_get(r, "name") or s_get(r, "service_name")
                if not code or not name:
                    continue
                b_code = s_get(r, "branch_code").upper()
                target_b = branches.get(b_code) or primary_branch
                price = float(s_get(r, "base_price") or 0.0)
                category = s_get(r, "category") or s_get(r, "service_category") or "OP"

                q = select(ServiceItem).where(ServiceItem.tenant_id == hospital.id, ServiceItem.code == code)
                res = await session.execute(q)
                existing = res.scalar_one_or_none()
                if existing:
                    if conflict_mode == "overwrite":
                        existing.name = name
                        existing.category = category
                        existing.base_price = price
                        existing.hsn_sac = s_get(r, "hsn_sac")
                        existing.gst_rate = float(s_get(r, "gst_rate") or 0.0)
                        existing.branch_id = target_b.id if target_b else None
                        stats["updated"] += 1
                    else:
                        stats["skipped"] += 1
                else:
                    new_item = ServiceItem(
                        tenant_id=hospital.id,
                        branch_id=target_b.id if target_b else None,
                        code=code,
                        name=name,
                        category=category,
                        base_price=price,
                        hsn_sac=s_get(r, "hsn_sac"),
                        gst_rate=float(s_get(r, "gst_rate") or 0.0),
                        is_active=True
                    )
                    session.add(new_item)
                    stats["created"] += 1

        elif d_key == "packages":
            for r in reader:
                name = s_get(r, "name") or s_get(r, "package_name")
                if not name:
                    continue
                b_code = s_get(r, "branch_code").upper()
                target_b = branches.get(b_code) or primary_branch
                price = float(s_get(r, "base_price") or 0.0)
                raw_items = s_get(r, "items_json") or s_get(r, "inclusions_json") or "[]"
                try:
                    items_list = json.loads(raw_items)
                    if isinstance(items_list, dict):
                        items_list = [items_list]
                except Exception:
                    items_list = []

                q = select(TreatmentPackage).where(TreatmentPackage.tenant_id == hospital.id, TreatmentPackage.name == name)
                res = await session.execute(q)
                existing = res.scalar_one_or_none()
                if existing:
                    if conflict_mode == "overwrite":
                        existing.description = s_get(r, "description")
                        existing.plugin_id = s_get(r, "plugin_id") or "fertility"
                        existing.base_price = price
                        existing.items = items_list
                        existing.branch_id = target_b.id if target_b else None
                        stats["updated"] += 1
                    else:
                        stats["skipped"] += 1
                else:
                    new_pkg = TreatmentPackage(
                        tenant_id=hospital.id,
                        branch_id=target_b.id if target_b else None,
                        name=name,
                        description=s_get(r, "description"),
                        plugin_id=s_get(r, "plugin_id") or "fertility",
                        base_price=price,
                        items=items_list,
                        is_active=True
                    )
                    session.add(new_pkg)
                    stats["created"] += 1

        elif d_key == "protocols":
            for r in reader:
                p_name = s_get(r, "protocol_name")
                if not p_name:
                    continue
                q_p = select(ProtocolTemplate).where(ProtocolTemplate.hospital_id == hospital.id, ProtocolTemplate.name == p_name)
                res_p = await session.execute(q_p)
                p_obj = res_p.scalar_one_or_none()
                if not p_obj:
                    p_obj = ProtocolTemplate(
                        hospital_id=hospital.id,
                        name=p_name,
                        category=s_get(r, "category") or "stimulation",
                        description=s_get(r, "description"),
                        is_active=True
                    )
                    session.add(p_obj)
                    await session.flush()
                    stats["created"] += 1

                drug = s_get(r, "drug_name")
                if drug:
                    q_r = select(ProtocolDrugRule).where(
                        ProtocolDrugRule.protocol_template_id == p_obj.id,
                        ProtocolDrugRule.drug_name == drug
                    )
                    res_r = await session.execute(q_r)
                    existing_r = res_r.scalar_one_or_none()
                    if existing_r:
                        if conflict_mode == "overwrite":
                            existing_r.dose = s_get(r, "dose")
                            existing_r.route = s_get(r, "route") or "SC"
                            existing_r.frequency = s_get(r, "frequency") or "OD"
                            existing_r.sentinel_anchor = s_get(r, "sentinel_anchor") or "stim_start"
                            existing_r.day_start_offset = int(s_get(r, "day_start_offset") or 1)
                            existing_r.day_end_offset = int(s_get(r, "day_end_offset") or 10)
                            existing_r.instructions = s_get(r, "instructions")
                            stats["updated"] += 1
                        else:
                            stats["skipped"] += 1
                    else:
                        new_r = ProtocolDrugRule(
                            protocol_template_id=p_obj.id,
                            drug_name=drug,
                            dose=s_get(r, "dose"),
                            route=s_get(r, "route") or "SC",
                            frequency=s_get(r, "frequency") or "OD",
                            sentinel_anchor=s_get(r, "sentinel_anchor") or "stim_start",
                            day_start_offset=int(s_get(r, "day_start_offset") or 1),
                            day_end_offset=int(s_get(r, "day_end_offset") or 10),
                            instructions=s_get(r, "instructions"),
                            sort_order=int(s_get(r, "sort_order") or 0)
                        )
                        session.add(new_r)
                        stats["created"] += 1

        elif d_key in ["templates", "lims", "cryo"]:
            u_res = await session.execute(select(User.id).where(User.tenant_id == hospital.id).limit(1))
            author_id = u_res.scalar() or hospital.id

            for r in reader:
                t_title = s_get(r, "title") or s_get(r, "test_name") or s_get(r, "tank_name")
                rec_type = s_get(r, "record_type") or s_get(r, "test_code") or s_get(r, "tank_code")
                if not t_title or not rec_type:
                    continue

                plugin = s_get(r, "plugin_id") or ("lims" if d_key == "lims" else "fertility_cryo" if d_key == "cryo" else "opd")
                b_code = s_get(r, "branch_code").upper()
                target_b = branches.get(b_code) or primary_branch

                try:
                    fields_data = json.loads(s_get(r, "schema_json") or s_get(r, "parameters_json") or s_get(r, "canisters_json") or "{}")
                except Exception:
                    fields_data = {}

                q = select(ClinicalTemplate).where(ClinicalTemplate.tenant_id == hospital.id, ClinicalTemplate.record_type == rec_type)
                res = await session.execute(q)
                existing = res.scalar_one_or_none()
                if existing:
                    if conflict_mode == "overwrite":
                        existing.title = t_title
                        existing.plugin_id = plugin
                        existing.description = s_get(r, "description") or existing.description
                        existing.schema_json = fields_data
                        stats["updated"] += 1
                    else:
                        stats["skipped"] += 1
                else:
                    new_tmpl = ClinicalTemplate(
                        tenant_id=hospital.id,
                        branch_id=target_b.id,
                        title=t_title,
                        record_type=rec_type,
                        plugin_id=plugin,
                        description=s_get(r, "description"),
                        schema_json=fields_data,
                        created_by=author_id,
                        is_active=True
                    )
                    session.add(new_tmpl)
                    stats["created"] += 1

        elif d_key in ["pharmacy_vendors", "vendors"]:
            for r in reader:
                v_name = s_get(r, "name") or s_get(r, "vendor_name")
                if v_name:
                    b_code = s_get(r, "branch_code").upper()
                    target_b = branches.get(b_code) or primary_branch
                    q_v = select(PharmacyVendor).where(PharmacyVendor.tenant_id == hospital.id, PharmacyVendor.name == v_name)
                    res_v = await session.execute(q_v)
                    v_obj = res_v.scalar_one_or_none()
                    if v_obj:
                        if conflict_mode == "overwrite":
                            v_obj.contact_phone = s_get(r, "contact_phone") or s_get(r, "phone") or v_obj.contact_phone
                            v_obj.contact_email = s_get(r, "contact_email") or s_get(r, "email") or v_obj.contact_email
                            v_obj.gst_number = s_get(r, "gst_number") or s_get(r, "gstin") or v_obj.gst_number
                            v_obj.address = s_get(r, "address") or v_obj.address
                            stats["updated"] += 1
                        else:
                            stats["skipped"] += 1
                    else:
                        v_obj = PharmacyVendor(
                            tenant_id=hospital.id,
                            branch_id=target_b.id,
                            name=v_name,
                            contact_email=s_get(r, "contact_email") or s_get(r, "email"),
                            contact_phone=s_get(r, "contact_phone") or s_get(r, "phone"),
                            gst_number=s_get(r, "gst_number") or s_get(r, "gstin"),
                            address=s_get(r, "address"),
                            is_active=True
                        )
                        session.add(v_obj)
                        stats["created"] += 1

        elif d_key in ["pharmacy_stock", "pharmacy", "stock"]:
            for r in reader:
                rec_type = s_get(r, "record_type").upper()
                if rec_type in ["VENDOR"]:
                    v_name = s_get(r, "name") or s_get(r, "vendor_name")
                    if v_name:
                        b_code = s_get(r, "branch_code").upper()
                        target_b = branches.get(b_code) or primary_branch
                        q_v = select(PharmacyVendor).where(PharmacyVendor.tenant_id == hospital.id, PharmacyVendor.name == v_name)
                        res_v = await session.execute(q_v)
                        v_obj = res_v.scalar_one_or_none()
                        if not v_obj:
                            v_obj = PharmacyVendor(
                                tenant_id=hospital.id,
                                branch_id=target_b.id,
                                name=v_name,
                                contact_email=s_get(r, "email") or s_get(r, "contact_email"),
                                contact_phone=s_get(r, "phone") or s_get(r, "contact_phone"),
                                gst_number=s_get(r, "gst_number") or s_get(r, "gstin"),
                                address=s_get(r, "address"),
                                is_active=True
                            )
                            session.add(v_obj)
                            stats["created"] += 1
                else:
                    b_num = s_get(r, "batch_number")
                    i_code = s_get(r, "item_code") or s_get(r, "item_name") or f"MED-{b_num}"
                    i_name = s_get(r, "item_name") or s_get(r, "item_code") or b_num
                    if not b_num:
                        continue
                    b_code = s_get(r, "branch_code").upper()
                    target_b = branches.get(b_code) or primary_branch
                    q_b = select(InventoryBatch).where(InventoryBatch.tenant_id == hospital.id, InventoryBatch.batch_number == b_num)
                    res_b = await session.execute(q_b)
                    existing_b = res_b.scalar_one_or_none()
                    qty = int(float(s_get(r, "quantity_available") or s_get(r, "quantity") or s_get(r, "quantity_received") or 0))
                    purchase_rate = float(s_get(r, "purchase_rate") or 0.0)
                    mrp = float(s_get(r, "mrp") or 0.0)
                    selling_price = float(s_get(r, "selling_price") or mrp or 0.0)
                    if existing_b:
                        if conflict_mode == "overwrite":
                            existing_b.quantity_available = qty
                            existing_b.quantity_received = max(existing_b.quantity_received or 0, qty)
                            existing_b.mrp = mrp
                            existing_b.selling_price = selling_price
                            existing_b.purchase_rate = purchase_rate
                            if s_get(r, "generic_name"):
                                existing_b.generic_name = s_get(r, "generic_name")
                            if s_get(r, "category"):
                                existing_b.category = s_get(r, "category")
                            if s_get(r, "rack_location"):
                                existing_b.rack_location = s_get(r, "rack_location")
                            stats["updated"] += 1
                        else:
                            stats["skipped"] += 1
                    else:
                        exp_str = s_get(r, "expiry_date")
                        exp_date = None
                        if exp_str:
                            try:
                                exp_date = date.fromisoformat(exp_str[:10])
                            except Exception:
                                pass
                        new_batch = InventoryBatch(
                            tenant_id=hospital.id,
                            branch_id=target_b.id,
                            item_code=i_code,
                            item_name=i_name,
                            generic_name=s_get(r, "generic_name"),
                            category=s_get(r, "category") or "Fertility / Injectables",
                            batch_number=b_num,
                            expiry_date=exp_date or date(2027, 12, 31),
                            quantity_received=qty,
                            quantity_available=qty,
                            purchase_rate=purchase_rate,
                            mrp=mrp,
                            selling_price=selling_price,
                            rack_location=s_get(r, "rack_location") or "Cold Chain Fridge 1",
                            is_active=True
                        )
                        session.add(new_batch)
                        stats["created"] += 1

        elif d_key == "patients":
            hosp_code = (hospital.code or "VMD")[:3].upper().ljust(3, "X")
            p_count_res = await session.execute(select(Patient.id))
            base_count = len(p_count_res.all()) + 1

            for r in reader:
                phone = s_get(r, "phone").strip()
                f_name = s_get(r, "first_name") or s_get(r, "name")
                l_name = s_get(r, "last_name") or s_get(r, "surname") or ""
                full_name = f"{f_name} {l_name}".strip() if l_name else f_name
                if not phone and not full_name:
                    continue

                b_code = s_get(r, "branch_code").upper()
                target_b = branches.get(b_code) or primary_branch
                gender_str = s_get(r, "gender").lower()
                gender_enum = Gender.FEMALE if gender_str in ["female", "f"] else Gender.MALE if gender_str in ["male", "m"] else Gender.OTHER

                dob_val = None
                dob_str = s_get(r, "dob")
                if dob_str:
                    try:
                        dob_val = date.fromisoformat(dob_str[:10])
                    except Exception:
                        pass

                raw_aadhaar = s_get(r, "aadhaar_raw") or s_get(r, "aadhaar")
                enc_aadhaar = encrypt_pii(raw_aadhaar) if raw_aadhaar else None

                q_p = select(Patient).where(Patient.tenant_id == hospital.id, Patient.phone == phone) if phone else select(Patient).where(Patient.tenant_id == hospital.id, Patient.name == full_name)
                res_p = await session.execute(q_p)
                existing_p = res_p.scalar_one_or_none()

                if existing_p:
                    if conflict_mode == "overwrite":
                        existing_p.name = full_name or existing_p.name
                        existing_p.surname = l_name or existing_p.surname
                        existing_p.gender = gender_enum
                        if dob_val:
                            existing_p.dob = dob_val
                        if s_get(r, "blood_group"):
                            existing_p.blood_group = s_get(r, "blood_group")
                        if s_get(r, "email"):
                            existing_p.email = s_get(r, "email")
                        if s_get(r, "city"):
                            existing_p.area = s_get(r, "city")
                        if enc_aadhaar:
                            existing_p.aadhaar_encrypted = enc_aadhaar
                        existing_p.branch_id = target_b.id
                        stats["updated"] += 1
                    else:
                        stats["skipped"] += 1
                else:
                    vid = f"VH-{hosp_code}-{(base_count + stats['created']):07d}"
                    new_p = Patient(
                        tenant_id=hospital.id,
                        branch_id=target_b.id,
                        vid=vid,
                        name=full_name or "Unknown Patient",
                        surname=l_name,
                        gender=gender_enum,
                        dob=dob_val,
                        blood_group=s_get(r, "blood_group"),
                        phone=phone or f"999{base_count:07d}",
                        email=s_get(r, "email"),
                        area=s_get(r, "city"),
                        aadhaar_encrypted=enc_aadhaar,
                    )
                    session.add(new_p)
                    stats["created"] += 1

        elif d_key == "cosgyn":
            for r in reader:
                name = s_get(r, "treatment_name")
                if not name:
                    continue
                price = float(s_get(r, "price") or 0.0)
                sessions = int(s_get(r, "sessions_count") or 1)

                q = select(CosgynTreatment).where(CosgynTreatment.tenant_id == hospital.id, CosgynTreatment.treatment_name == name)
                res = await session.execute(q)
                existing = res.scalar_one_or_none()
                if existing:
                    if conflict_mode == "overwrite":
                        existing.clinical_indication = s_get(r, "clinical_indication")
                        existing.sessions_count = sessions
                        existing.price = price
                        stats["updated"] += 1
                    else:
                        stats["skipped"] += 1
                else:
                    new_item = CosgynTreatment(
                        tenant_id=hospital.id,
                        treatment_name=name,
                        clinical_indication=s_get(r, "clinical_indication"),
                        sessions_count=sessions,
                        price=price,
                        is_active=True
                    )
                    session.add(new_item)
                    stats["created"] += 1

        await session.commit()
        stats["success"] = True
        stats["inserted"] = stats["created"]
        stats["total_rows"] = len(reader)
        stats["message"] = f"Successfully imported {stats['created']} new records, updated {stats['updated']} records."
        return stats

    except Exception as e:
        await session.rollback()
        logger.exception("Failed importing CSV domain %s: %s", d_key, str(e))
        stats["success"] = False
        stats["error"] = str(e)
        stats["inserted"] = stats.get("created", 0)
        return {"success": False, "error": str(e), "stats": stats}
