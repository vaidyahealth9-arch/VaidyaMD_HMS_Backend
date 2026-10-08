# 🏥 VaidyaMD HMS — End-to-End Database Onboarding Suite

The **End-to-End Onboarding Suite** provides a modular, domain-separated framework to onboard hospital tenants, physical infrastructure, billing catalogs, clinical protocols, clinical templates, pharmacy inventory, cosmetic gynaecology catalogs, and bulk patients into VaidyaMD HMS.

> **Suite Coverage:** 13 CSV domain handlers covering **15 numbered template slots** (Domain 11 is split into 11a Vendors + 11b Stock). All other models (Appointments, Wallets, TreatmentCycles, OocyteRecords, etc.) are **runtime-created** by clinical workflows — see §6 for the full model registry.

---

## 📂 Architecture & Template Structure

Templates are organized within `scripts/db/templates/`:

| Domain | File Name | Description | Key Models Populated |
| :--- | :--- | :--- | :--- |
| **01 Hospital** | `01_hospitals_and_branches.csv` | Tenant organization details, GSTIN, receipt headers, IP whitelist, branch locations with per-branch GSTIN and enabled plugin list | `Hospital`, `Branch` |
| **02 Staff** | `02_staff_users.csv` | Multi-branch staff roster, clinical qualifications, registration numbers, roles, and default credentials. **Note:** `PermissionProfile` records are auto-seeded from `STANDARD_PROFILES` per role — they are not driven by this CSV. | `User` *(PermissionProfile auto-seeded)* |
| **03 IPD** | `03_ipd_infrastructure.csv` | Inpatient infrastructure including Wards (Day Care, Deluxe, General, HDU) and individual bed numbers with daily tariffs and bed type | `Ward`, `Bed` |
| **04 Cycle Types** | `04_treatment_cycle_types.csv` | ART cycle types: ICSI, FET, IUI, Donor, PGT, Cryo, Egg Freezing, Surrogacy, OI modalities with display order | `TreatmentCycleType` |
| **05 Service Catalog** | `05_service_catalog.csv` | Master tariff directory for OPD consultations, ultrasounds, daycare procedures, lab tests. Includes HSN/SAC codes and GST rates | `ServiceItem` |
| **06 Billing Packages** | `06_billing_packages.csv` | Clinical packages (IVF-ICSI, FET, IUI, Donor IUI, Hysteroscopy, TESA/PESA) with itemized fee breakdowns, HSN/SAC codes, and plugin association | `TreatmentPackage` |
| **07 Protocols** | `07_clinical_protocols.csv` | Clinical stimulation protocols (Antagonist, Microflare, PPOS, Long Agonist) and sequential drug administration rules with dosage, route, frequency, sentinel anchor, and cycle day offsets | `ProtocolTemplate`, `ProtocolDrugRule` |
| **08 Templates** | `08_clinical_templates.csv` | Clinical consultation proformas, OPD smart order sets, doctor Rx templates, and visit types with full JSON schema field definitions | `ClinicalTemplate` |
| **09 LIMS** | `09_lims_test_directory.csv` | Complete laboratory test directory, sample types, turnaround times (TAT hours), reference ranges, and quantitative report parameters as JSON | `LimsTestDirectory` |
| **10 Cryo** | `10_cryo_infrastructure.csv` | Liquid nitrogen cryo tank assets, canister numbers with colour codes, goblet capacities, device types (Cryotop / CBS Straw), and room location mapping | `CryoTank`, `CryoCanister` |
| **11a Vendors** | `11a_pharmacy_vendors.csv` | Approved pharmaceutical vendor and distributor directory with GSTIN, contact phone/email, billing address | `PharmacyVendor` |
| **11b Pharmacy Stock** | `11b_pharmacy_stock.csv` | Pharmacy formulary drugs, item codes, generic names, batch numbers, manufacturer, expiry dates, MRP, purchase rates, selling price, rack location, HSN codes, and initial stock quantities | `InventoryBatch` |
| **12 Patients** | `12_patients_bulk.csv` | Bulk patient registrations, demographics (DOB, blood group, nationality, education, occupation), Aadhaar PII AES-256 encryption, institutional 7-digit VID generation (`VH-{HOSP_CODE}-XXXXXXX`), referral source tracking, and bidirectional couple linking via `couple_code` | `Patient` |
| **13 CosGyn** | `13_cosgyn_procedures.csv` | Cosmetic Gynaecology procedure catalog (HIFEM Tesla Chair, Jet Plasma Rejuvenation, O-Shot PRP, Labiaplasty, Laser Lightening) with session counts and tariffs | `CosgynTreatment` |

---

## 🚀 Usage & Commands

The CLI runner is located at `scripts/db/onboard_suite.py`.

### 1. Dry Run (Validate Without Committing)
To simulate the complete onboarding flow and check template formatting and data relationships without writing to the database:
```bash
python scripts/db/onboard_suite.py --env local --all --dry-run --force-upsert
```

### 2. Full Live Onboarding (`--all`)
To onboard all 13 domain handlers (Domains 01–13) sequentially:
```bash
python scripts/db/onboard_suite.py --env local --all --force-upsert
```

### 3. Full Onboarding — Excluding Bulk Patients
To onboard all infrastructure and catalogs while skipping bulk patient import (useful for new branch setup without migrating historical patients):
```bash
python scripts/db/onboard_suite.py --env local --all --force-upsert --exclude-patients
```

### 4. Running a Single Domain Independently
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

# Or onboard all pharmacy data combined (11a + 11b)
python scripts/db/onboard_suite.py --env local --domain pharmacy --force-upsert

# Onboard bulk patients and couple linkages
python scripts/db/onboard_suite.py --env local --domain patients --force-upsert

# Onboard cosmetic gynaecology treatments
python scripts/db/onboard_suite.py --env local --domain cosgyn --force-upsert
```

### 5. Custom CSV Override
To supply a custom file for any domain:
```bash
python scripts/db/onboard_suite.py --env local --domain patients --file path/to/my_patients.csv --force-upsert
```

---

## 🌐 Environment Targets (`--env`)

| Value | Target Database | Typical Use |
| :--- | :--- | :--- |
| `local` | `localhost` (Docker Compose) | Developer onboarding and schema testing |
| `staging` | Cloud staging instance | Pre-production validation with real tenant data |
| `production` | Production database | Live hospital go-live (use `--skip-existing` for safety) |

Use `--database-url` to supply an explicit connection string that overrides the environment default.

---

## 🛡️ Conflict Handling Modes

| Flag | Mode | Behavior |
| :--- | :--- | :--- |
| *(default)* | `prompt` | Interactively prompts `[O]verwrite / [S]kip / [A]bort` when a duplicate record is detected. |
| `--force-upsert` / `--yes` | `overwrite` | Automatically updates existing records with the latest data from the CSV. |
| `--skip-existing` | `skip` | Safely skips any record that already exists in the database. Best for production re-runs. |
| `--exclude-patients` | *(modifier)* | When used with `--all` or `--domain patients`, skips Domain 12 entirely. |
| `--dry-run` | *(modifier)* | Validates all CSV templates and simulates writes; rolls back at the end with no DB changes. |

---

## 🗂️ Domain Aliases (Short Names)

The `--domain` argument accepts canonical names **and** aliases:

| Alias | Resolves To |
| :--- | :--- |
| `hospital`, `branches`, `01` | `hospitals` |
| `users`, `02` | `staff` |
| `wards`, `beds`, `03` | `ipd` |
| `cycles`, `art_cycles`, `04` | `treatment_cycles` |
| `tariffs`, `services`, `05` | `service_catalog` |
| `billing`, `billing_packages`, `06` | `packages` |
| `stimulation_protocols`, `07` | `protocols` |
| `clinical_templates`, `08` | `templates` |
| `lims_directory`, `tests`, `09` | `lims` |
| `cryobank`, `tanks`, `10` | `cryo` |
| `vendors`, `11a` | `pharmacy_vendors` |
| `stock`, `pharmacy_inventory`, `11`, `11b` | `pharmacy_stock` |
| `couples`, `12` | `patients` |
| `cosmetic_gynae`, `13` | `cosgyn` |

---

## 🔑 Permission Profiles — Auto-Seeding

`PermissionProfile` records are **not driven by any CSV template**. They are automatically created during Domain 01 & 02 processing by `STANDARD_PROFILES` in `onboard_hospital.py`. Each role maps to a named profile:

| Role | Auto-assigned Profile |
| :--- | :--- |
| `admin`, `manager` | Hospital Administrator |
| `doctor`, `scanning` | Doctor / Clinician |
| `nurse` | Fertility Nurse |
| `receptionist` | Front Desk / Receptionist |
| `embryologist`, `andrologist` | Senior Embryologist |
| `pharma`, `pharmacist` | Pharmacy Executive |
| `accounts` | Billing / Cashier |
| `counsellor` | Patient Counselor |

To customize `menu_permissions` (JSONB module access flags) for a profile, edit the database directly or extend `STANDARD_PROFILES` in `scripts/db/onboard_hospital.py`.

---

## 👥 Couple Linking & VID Standards

- **Couple Linking**: Patients with matching `couple_code` values (e.g. `CPL-001`, `CPL-002`) are automatically linked bidirectionally (`patient.partner_id` ↔ `partner.partner_id`).
- **Institutional 7-Digit VID Format**: Patients receive auto-generated canonical hospital identity numbers conforming to:
  $$\text{VH-}\{\text{HOSP\_CODE}\}\text{-}\{\text{7-digit counter}\}$$
  *Example:* `VH-AFI-0000005`, `VH-AFI-0000006`.
- **Aadhaar Encryption**: Raw Aadhaar numbers in `12_patients_bulk.csv` column `aadhaar_raw` are AES-256 encrypted during ingestion and stored in `patient.aadhaar_encrypted`. The raw value is never persisted.
- **ABHA Integration**: The `abha_number` field (Ayushman Bharat Health Account) is supported as an optional column in the patients template.

---

## 🗄️ Full Model Registry — Onboarding vs Runtime

All SQLAlchemy models in the system and their onboarding status:

### Core System Models

| Model | Table | Onboarded By | Notes |
| :--- | :--- | :--- | :--- |
| `Hospital` | `hospitals` | Domain 01 | Tenant root entity |
| `Branch` | `branches` | Domain 01 | Multi-clinic branches per tenant |
| `PermissionProfile` | `permission_profiles` | Auto-seeded (Domain 01/02) | Created from `STANDARD_PROFILES` map, not CSV |
| `User` | `users` | Domain 02 | Staff roster with hashed passwords |
| `RefreshToken` | `refresh_tokens` | Runtime (Auth) | JWT refresh tokens, created at login |
| `ClinicalRecord` | `clinical_records` | **Runtime only** | OPD consultation records saved by doctors |
| `Document` | `documents` | **Runtime only** | Patient file registry: scans, consents, reports, prescriptions |

### Patient & Appointment Models

| Model | Table | Onboarded By | Notes |
| :--- | :--- | :--- | :--- |
| `Patient` | `patients` | Domain 12 | Supports bulk import + online registration |
| `Appointment` | `appointments` | **Runtime only** | Booked via appointments module; statuses: `scheduled`, `completed`, `no_show`, `cancelled` |
| `CounselingNote` | `counseling_notes` | **Runtime only** | 8-column structured counseling session notes per patient |

### Billing & Wallet Models

| Model | Table | Onboarded By | Notes |
| :--- | :--- | :--- | :--- |
| `ServiceItem` | `service_items` | Domain 05 | Master tariff catalog |
| `TreatmentPackage` | `treatment_packages` | Domain 06 | Clinical bundles (IVF-ICSI, FET, etc.) |
| `Invoice` | `invoices` | **Runtime only** | Generated per patient encounter; statuses: draft → pending → paid |
| `PatientPackage` | `patient_packages` | **Runtime only** | Patient-specific package enrollment linked to an invoice |
| `PatientWallet` | `patient_wallets` | **Runtime only** | Advance deposit wallet; auto-created on first deposit |
| `WalletTransaction` | `wallet_transactions` | **Runtime only** | Ledger of deposits, invoice debits, and refunds |

### IPD Models

| Model | Table | Onboarded By | Notes |
| :--- | :--- | :--- | :--- |
| `Ward` | `wards` | Domain 03 | Ward definitions with department and daily base charge |
| `Bed` | `beds` | Domain 03 | Individual bed numbers with type and daily rate |
| `IPDAdmission` | `ipd_admissions` | **Runtime only** | Admission records with diagnosis, package, and discharge date |
| `NursingTask` | `nursing_tasks` | **Runtime only** | Scheduled nursing tasks (vitals, medications) per bed/admission |

### Pharmacy Models

| Model | Table | Onboarded By | Notes |
| :--- | :--- | :--- | :--- |
| `PharmacyVendor` | `pharmacy_vendors` | Domain 11a | Approved suppliers with GSTIN |
| `InventoryBatch` | `inventory_batches` | Domain 11b | Formulary drug batches with stock quantities |
| `PharmacyIndent` | `pharmacy_indents` | **Runtime only** | Internal / inter-branch / vendor indent requests |
| `PurchaseOrder` | `purchase_orders` | **Runtime only** | Purchase orders raised to vendors |
| `GoodsReceivedNote` | `goods_received_notes` | **Runtime only** | GRN with OCR-parsed invoice data on goods receipt |

### Template & Protocol Models

| Model | Table | Onboarded By | Notes |
| :--- | :--- | :--- | :--- |
| `ProtocolTemplate` | `protocol_templates` | Domain 07 | Stimulation protocol definitions |
| `ProtocolDrugRule` | `protocol_drug_rules` | Domain 07 | Day-by-day drug rules per protocol |
| `ClinicalTemplate` | `clinical_templates` | Domain 08 | Proformas, order sets, Rx templates with JSON schema |

### Fertility Plugin Models

| Model | Table | Onboarded By | Notes |
| :--- | :--- | :--- | :--- |
| `TreatmentCycleType` | `treatment_cycle_types` | Domain 04 | ART modality catalog |
| `TreatmentCycle` | `treatment_cycles` | **Runtime only** | Active ART cycles with sentinel dates, gamete source, medication calendar |
| `OocyteRecord` | `oocyte_records` | **Runtime only** | Per-oocyte Day 0–7 embryology grading records (ICSI, fertilisation, cleavage, blastocyst) |
| `EmbryologyWitness` | `embryology_witnesses` | **Runtime only** | Dual-witness sign-off records per embryology procedure step |
| `CryoSample` | `cryo_samples` | **Runtime only** | Individual cryo straws with tank coordinates, embryo grade, thaw history |

### Cryo Infrastructure Models

| Model | Table | Onboarded By | Notes |
| :--- | :--- | :--- | :--- |
| `CryoTank` *(reference)* | *(via Domain 10 seed)* | Domain 10 | LN2 tank definitions with canister capacity |
| `CryoCanister` *(reference)* | *(via Domain 10 seed)* | Domain 10 | Canister colour codes and goblet slots per tank |

### CosGyn Plugin Models

| Model | Table | Onboarded By | Notes |
| :--- | :--- | :--- | :--- |
| `CosgynTreatment` | `cosgyn_treatments` | Domain 13 | Procedure catalog (HIFEM, Jet Plasma, O-Shot, etc.) |
| `CosgynPatientPlan` | `cosgyn_patient_plans` | **Runtime only** | Patient-specific booked treatment plan with scheduled dates |
| `CosgynSession` | `cosgyn_sessions` | **Runtime only** | Individual session records with equipment, status, and billing link |

### Notification Model

| Model | Table | Onboarded By | Notes |
| :--- | :--- | :--- | :--- |
| `Notification` | `notifications` | **Runtime only** | System, appointment, billing, lab result, and prescription alerts per user |

---

## ⚠️ Known Gaps / Domains Not Yet in Suite

The following data areas have live models but **no CSV onboarding template yet**. They require manual seed or API creation on first use:

| Gap | Model(s) | Impact | Recommended Action |
| :--- | :--- | :--- | :--- |
| **Referring Doctor Master** | *(free-text in `Patient`)* | Referral analytics depend on consistent `referred_by_name` values | Add a `14_referring_doctors.csv` domain to seed a canonical master list |
| **Initial Wallet Balances** | `PatientWallet`, `WalletTransaction` | Migrating hospitals with existing advance deposits have no bulk import path | Add a `15_patient_wallet_seed.csv` domain |
| **Notification Preferences** | `Notification` config | Per-user notification routing is not configurable via onboarding | Out-of-scope for current suite; configure via admin settings |
| **Custom Permission Profiles** | `PermissionProfile` | Tenants needing profiles beyond the 8 STANDARD_PROFILES cannot create them via CSV | Add a `16_permission_profiles.csv` domain or expose via admin API |
