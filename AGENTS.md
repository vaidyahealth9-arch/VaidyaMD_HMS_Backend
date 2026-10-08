# 🏥 VaidyaMD HMS Backend — Agent & Copilot Instructions

> **Purpose:** This file is the single source of truth for any AI agent, copilot, or developer working on `VaidyaMD_HMS_Backend`.
> Read this fully before touching or adding any backend code.

---

## 1. Project Overview

**VaidyaMD HMS Backend** is a high-concurrency, multi-tenant enterprise backend for hospital management, IVF/fertility workflows, pharmacy inventory, LIMS, IPD/OPD, billing, and clinical documentation.

**Tech Stack:**
- **Framework:** FastAPI (Python 3.11+) with ASGI async runtime
- **ORM / Database:** SQLAlchemy 2.0 (AsyncSession) + asyncpg + PostgreSQL 15+
- **Data Validation:** Pydantic v2 (`BaseModel`, `ConfigDict(from_attributes=True)`)
- **Authentication & Security:** JWT tokens, Argon2/bcrypt password hashing, AES-256 PII encryption (`encrypt_pii`, `mask_pii`)
- **Multi-Tenancy:** Hospital & Branch contextual isolation via FastAPI dependency injection (`get_branch_context`, `get_current_user`)
- **Integration Protocols:** RESTful APIs, WebSockets (`/ws`), HL7 v2.x server (`hl7_server.py`) for lab analyzer bidirectional interfacing
- **Onboarding Suite:** Modular 13-domain CSV onboarding runner in `scripts/db/`

---

## 2. Repository Structure (Canonical)

```
VaidyaMD_HMS_Backend/
├── app/
│   ├── config.py                 # Pydantic Settings, environment configs
│   ├── main.py                   # FastAPI app factory, CORS, router mounting, lifecycle
│   ├── core/
│   │   ├── database.py           # async_sessionmaker, get_db session dependency
│   │   ├── dependencies.py       # get_current_user, get_branch_context, role guards
│   │   ├── security.py           # JWT creation/verification, encrypt_pii, mask_pii
│   │   ├── events.py             # App startup/shutdown event handlers
│   │   ├── websocket.py          # WebSocket connection manager
│   │   ├── hl7_server.py         # MLLP HL7 interface for LIMS analyzer feeds
│   │   └── models/               # Core shared SQLAlchemy models
│   │       ├── tenant.py         # Hospital (Tenant)
│   │       ├── branch.py         # Branch
│   │       ├── user.py           # User & credentials
│   │       ├── permission_profile.py # PermissionProfile & Role bindings
│   │       ├── clinical_record.py
│   │       ├── treatment_cycle.py
│   │       └── document.py
│   └── modules/                  # Clean Architecture domain modules
│       ├── ai_scribe/
│       ├── appointments/
│       ├── auth/
│       ├── billing/
│       ├── clinical_records/
│       ├── counseling/
│       ├── ipd/
│       ├── lims/
│       ├── notifications/
│       ├── patients/
│       ├── pharmacy/
│       ├── templates/
│       └── wallet/
├── scripts/
│   ├── db/                       # Database Onboarding Suite
│   │   ├── onboard_suite.py      # Master CLI runner
│   │   ├── ONBOARDING_SUITE_GUIDE.md
│   │   ├── templates/            # 15 domain CSV templates (01 to 13)
│   │   └── handlers/             # Modular domain ingestion handlers
└── docs/                         # Architecture and API documentation
```

---

## 3. Mandatory Architecture Rules (Modular Clean Architecture)

### 3.0 No Hardcoding Policy
> **CRITICAL:** ABSOLUTELY NO HARDCODING of clinical protocols, medical configurations, drugs, or data-driven logic. All protocols (e.g. Antagonist, Long Agonist, HRT FET) and configuration details must be database-driven and dynamically loaded. If you are adding a list of static templates or fallback drugs in code, **STOP** and move it to the database/config instead.

### 3.1 Domain Module Anatomy

Every module inside `app/modules/<domain>/` MUST follow this standardized layout:

```
app/modules/<domain>/
├── __init__.py           # Empty or exposes router
├── model.py              # Domain SQLAlchemy ORM models
├── schemas.py            # Pydantic v2 schemas (Create, Update, Response, ListResponse)
├── service.py            # Business logic class with async DB methods
├── router.py             # FastAPI APIRouter endpoints (thin controller)
└── exceptions.py         # Domain-specific custom exceptions
```

### 3.2 The Golden Layering Rule

> **Never place raw SQL or ORM queries inside `router.py`.**
> **Never bypass Pydantic validation schemas.**

Data and logic flow in one direction only:

```
HTTP Request
     ↓
router.py (validates request with Pydantic, calls service)
     ↓
service.py (business rules, transactions, VID generation, calculations)
     ↓
model.py / SQLAlchemy AsyncSession (DB execution)
     ↓
schemas.py (response serialization via response_model)
```

---

## 4. Multi-Tenant Isolation & Security Standards

### 4.1 Tenant & Branch Context Guard
Every protected route that accesses hospital or branch data MUST inject `get_current_user` and/or `get_branch_context`:

```python
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_branch_context
from app.core.models import User

router = APIRouter(prefix="/example", tags=["Example"])

@router.get("", response_model=ExampleListResponse)
async def list_items(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    branch_id: str = Depends(get_branch_context),
):
    service = ExampleService(db)
    return await service.list_by_branch(hospital_id=current_user.hospital_id, branch_id=branch_id)
```

### 4.2 PII Protection (Aadhaar & Medical Confidentiality)
- National IDs (Aadhaar, Passport) and confidential identifiers MUST be encrypted using `app.core.security.encrypt_pii()`.
- Public response schemas MUST only expose masked PII via `app.core.security.mask_pii()` (e.g. `XXXX-XXXX-1234`).
- NEVER log raw Aadhaar numbers or plaintext passwords in stdout or log files.

---

## 5. Pydantic v2 & SQLAlchemy 2.0 Best Practices

### 5.1 Response Models
Always configure `from_attributes = True` in Pydantic v2 schemas:

```python
from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime

class PatientResponse(BaseModel):
    id: UUID
    vid: str
    first_name: str
    last_name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

### 5.2 Async Query Execution
Always use SQLAlchemy 2.0 style `select()`, `execute()`, and `scalars()`:

```python
# CORRECT
stmt = select(Patient).where(Patient.hospital_id == hospital_id).order_by(desc(Patient.created_at))
result = await self.db.execute(stmt)
patients = result.scalars().all()

# For relationships, use selectinload or joinedload
from sqlalchemy.orm import selectinload
stmt = select(Patient).options(selectinload(Patient.appointments)).where(Patient.id == patient_id)
```

### 5.3 Collision-Resistant ID Generation
Use the standard 3-letter hospital code + 7-digit sequential format for human-facing identifiers:
- Patient VID: `VH-{HOSP_CODE}-XXXXXXX` (e.g., `VH-KMC-0000042`)
- Invoices: `INV-{HOSP_CODE}-{YYYY}-{SERIAL}`
- Lab Samples: `LAB-{DATE}-{SERIAL}`

---

## 6. Error Handling & Exceptions

1. Define domain exceptions in `app/modules/<domain>/exceptions.py` inheriting from a base domain error.
2. In `router.py`, catch domain exceptions and translate them to standard `HTTPException` with appropriate status codes (`404 NOT FOUND`, `409 CONFLICT`, `422 UNPROCESSABLE_ENTITY`).
3. Never let unhandled SQLAlchemy operational errors crash the server without a clean HTTP response.

```python
# exceptions.py
class PatientNotFoundError(Exception):
    def __init__(self, patient_id: str):
        super().__init__(f"Patient with ID {patient_id} not found.")

# router.py
try:
    return await service.get_patient(patient_id)
except PatientNotFoundError as e:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
```

---

## 7. Database Onboarding Suite (`scripts/db/`)

The repository includes a 13-domain modular database onboarding suite. Refer to `scripts/db/ONBOARDING_SUITE_GUIDE.md` for complete documentation.

| Domain | Template | Target Entity |
| :--- | :--- | :--- |
| **01** | `01_hospitals_and_branches.csv` | Tenant Hospital & Branches |
| **02** | `02_staff_users.csv` | Clinical & Admin User Accounts |
| **03** | `03_ipd_infrastructure.csv` | Wards and Beds |
| **04** | `04_treatment_cycle_types.csv` | ART Treatment Cycle Types |
| **05** | `05_service_catalog.csv` | OPD / Procedure / Lab Tariffs |
| **06** | `06_billing_packages.csv` | Bundled Clinical Packages |
| **07** | `07_clinical_protocols.csv` | Stimulation Protocols & Drug Rules |
| **08** | `08_clinical_templates.csv` | Proformas & Clinical Order Sets |
| **09** | `09_lims_test_directory.csv` | Lab Test Directory & TAT |
| **10** | `10_cryo_infrastructure.csv` | Tanks, Canisters & Goblets |
| **11a**| `11a_pharmacy_vendors.csv` | Approved Vendors |
| **11b**| `11b_pharmacy_stock.csv` | Initial Pharmacy Inventory Batches |
| **12** | `12_patients_bulk.csv` | Bulk Patient Demographics & Encrypted PII |
| **13** | `13_cosgyn_procedures.csv` | Cosmetic Gynaecology Catalogs |

**Execution Commands:**
```bash
# Dry run
python scripts/db/onboard_suite.py --env local --all --dry-run --force-upsert

# Live execution
python scripts/db/onboard_suite.py --env local --all --force-upsert
```

---

## 8. When Adding a New Backend Feature

Follow this checklist:
1. **Identify or create the module** inside `app/modules/<domain>/`.
2. **Define or extend ORM models** in `model.py` (or `app/core/models/` if shared across multiple domains).
3. **Define Pydantic v2 schemas** in `schemas.py` (`Create`, `Update`, `Response`).
4. **Implement business logic** inside `service.py` using `AsyncSession`.
5. **Create router endpoints** in `router.py` using typed FastAPI route decorators.
6. **Mount router in `app/main.py`** under the appropriate API version prefix (`/api/v1` or `/api`).
7. **Ensure multi-tenancy filters** (`hospital_id`, `branch_id`) are applied to every query.

---

## 9. Forbidden Patterns

| Pattern | Why Forbidden | Correct Alternative |
| :--- | :--- | :--- |
| Raw SQL queries in `router.py` | Violates Clean Architecture | Place in `service.py` using SQLAlchemy 2.0 ORM |
| Missing `hospital_id` in queries | Causes cross-tenant data leaks | Filter by `hospital_id` from `get_current_user` |
| Plaintext Aadhaar storage | Compliance & legal violation | Use `encrypt_pii()` and `mask_pii()` |
| Synchronous `def` route handlers for DB ops | Blocks FastAPI async event loop | Always use `async def` with `await session.execute()` |
| Catch-all `except Exception: pass` | Swallows critical database errors | Catch specific exceptions and log with context |
| Hardcoded DB credentials | Security risk | Load from `app.config.Settings` via `.env` |
