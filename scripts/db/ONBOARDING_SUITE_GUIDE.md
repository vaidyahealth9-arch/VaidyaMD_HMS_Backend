# 🏥 VaidyaMD HMS — End-to-End Database Onboarding Suite

The **End-to-End Onboarding Suite** provides a modular, domain-separated framework to onboard hospital tenants, physical infrastructure, billing catalogs, clinical protocols, clinical templates, pharmacy inventory, cosmetic gynaecology catalogs, and bulk patients into VaidyaMD HMS.

---

## 📂 Architecture & Template Structure

Templates are organized within `scripts/db/templates/`:

| Domain | File Name | Description | Key Models Populated |
| :--- | :--- | :--- | :--- |
| **01 Hospital** | `01_hospitals_and_branches.csv` | Tenant organization details, GSTIN, receipt headers, and branch locations | `Hospital`, `Branch` |
| **02 Staff** | `02_staff_users.csv` | Multi-branch staff roster, clinical qualifications, registration numbers, roles, and default credentials | `User`, `PermissionProfile` |
| **03 IPD** | `03_ipd_infrastructure.csv` | Inpatient infrastructure including Wards (Day Care, Deluxe, General, HDU) and Individual Bed numbers with daily tariffs | `Ward`, `Bed` |
| **04 Cycle Types** | `04_treatment_cycle_types.csv` | ART cycle types, ICSI, FET, IUI, Donor, PGT, and Cryo modalities | `TreatmentCycleType` |
| **05 Service Catalog** | `05_service_catalog.csv` | Master tariff directory for OPD consultations, ultrasounds, procedures, and lab tests | `ServiceItem` |
| **06 Billing** | `06_billing_packages.csv` | Clinical packages (IVF-ICSI, FET, IUI, Donor IUI, Hysteroscopy, TESA/PESA) with itemized fee breakdowns and HSN/SAC codes | `TreatmentPackage` |
| **07 Protocols** | `07_clinical_protocols.csv` | Clinical stimulation protocols (Antagonist, Microflare, PPOS, Long Agonist) and sequential drug administration rules with dosage & cycle offsets | `ProtocolTemplate`, `ProtocolDrugRule` |
| **08 Templates** | `08_clinical_templates.csv` | Clinical consultation proformas, order sets, Rx templates, and visit types with JSON schema fields | `ClinicalTemplate` |
| **09 LIMS** | `09_lims_test_directory.csv` | Complete laboratory test directory, reference ranges, turnaround times, and report parameters | `LimsTestDirectory` |
| **10 Cryo** | `10_cryo_infrastructure.csv` | Liquid nitrogen cryo tanks, canisters, goblet capacities, and location mapping | `CryoTank`, `CryoCanister` |
| **11a Vendors** | `11a_pharmacy_vendors.csv` | Approved pharmaceutical vendor and distributor directory with GSTIN and contact details | `PharmacyVendor` |
| **11b Pharmacy Stock** | `11b_pharmacy_stock.csv` | Pharmacy formulary drugs, SKU codes, batch numbers, manufacturer, expiry dates, MRP, purchase rates, and initial stock counts | `InventoryBatch` |
| **12 Patients** | `12_patients_bulk.csv` | Bulk patient registrations, demographics, Aadhaar PII encryption, institutional 7-digit VID generation (`VH-{HOSP_CODE}-XXXXXXX`), and bidirectional couple linking | `Patient` |
| **13 CosGyn** | `13_cosgyn_procedures.csv` | Cosmetic Gynaecology procedure catalog (HIFEM Chair, Jet Plasma Rejuvenation, O-Shot PRP, Labiaplasty, Laser Lightening) with session counts and tariffs | `CosgynTreatment` |

---

## 🚀 Usage & Commands

The CLI runner is located at `scripts/db/onboard_suite.py`.

### 1. Dry Run (Validate Without Committing)
To simulate the complete onboarding flow and check template formatting and data relationships without writing to the database:
```bash
python scripts/db/onboard_suite.py --env local --all --dry-run --force-upsert
```

### 2. Full Live Onboarding (`--all`)
To onboard all 14 domains sequentially:
```bash
python scripts/db/onboard_suite.py --env local --all --force-upsert
```

### 3. Running a Single Domain Independently
You can onboard any single domain without running the others. The suite automatically resolves the hospital tenant and branches first:
```bash
# Onboard hospital and branches
python scripts/db/onboard_suite.py --env local --domain hospitals --force-upsert

# Onboard staff users
python scripts/db/onboard_suite.py --env local --domain staff --force-upsert

# Onboard IPD wards and beds
python scripts/db/onboard_suite.py --env local --domain ipd --force-upsert

# Onboard treatment cycle types
python scripts/db/onboard_suite.py --env local --domain treatment_cycles --force-upsert

# Onboard service catalog / master tariffs
python scripts/db/onboard_suite.py --env local --domain service_catalog --force-upsert

# Onboard billing packages
python scripts/db/onboard_suite.py --env local --domain packages --force-upsert

# Onboard clinical stimulation protocols
python scripts/db/onboard_suite.py --env local --domain protocols --force-upsert

# Onboard clinical proforma and Rx templates
python scripts/db/onboard_suite.py --env local --domain templates --force-upsert

# Onboard LIMS lab test directory
python scripts/db/onboard_suite.py --env local --domain lims --force-upsert

# Onboard cryo tanks and canisters
python scripts/db/onboard_suite.py --env local --domain cryo --force-upsert

# Onboard pharmacy vendors directory (Domain 11a)
python scripts/db/onboard_suite.py --env local --domain pharmacy_vendors --force-upsert

# Onboard pharmacy items and inventory batches (Domain 11b)
python scripts/db/onboard_suite.py --env local --domain pharmacy_stock --force-upsert

# Or onboard all pharmacy data combined
python scripts/db/onboard_suite.py --env local --domain pharmacy --force-upsert

# Onboard bulk patients and couple linkages
python scripts/db/onboard_suite.py --env local --domain patients --force-upsert

# Onboard cosmetic gynaecology treatments
python scripts/db/onboard_suite.py --env local --domain cosgyn --force-upsert
```

### 4. Custom CSV Override
To supply a custom file for any domain:
```bash
python scripts/db/onboard_suite.py --env local --domain patients --file path/to/my_patients.csv --force-upsert
```

---

## 🛡️ Conflict Handling Modes

| Flag | Mode | Behavior |
| :--- | :--- | :--- |
| *(default)* | `prompt` | Interactively prompts `[O]verwrite / [S]kip / [A]bort` when a duplicate record is detected. |
| `--force-upsert` / `--yes` | `overwrite` | Automatically updates existing records with the latest data from the CSV. |
| `--skip-existing` | `skip` | Safely skips any record that already exists in the database. |

---

## 👥 Couple Linking & VID Standards

- **Couple Linking**: Patients with matching `couple_code` values (e.g. `CPL-001`, `CPL-002`) are automatically linked bidirectionally (`patient.partner_id` points to each other).
- **Institutional 7-Digit VID Format**: Patients receive auto-generated canonical hospital identity numbers conforming to:
  $$\text{VH-}\{\text{HOSP\_CODE}\}\text{-}\{\text{7-digit counter}\}$$
  *Example:* `VH-AFI-0000005`, `VH-AFI-0000006`.
