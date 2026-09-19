# VaidyaMD HMS — Backend Service

Modular, enterprise-grade FastAPI backend service powering the **VaidyaMD Hospital Management System (HMS)**.

---

## 🏛️ Architecture Overview

The backend is built as a **Modular Monolith** using **FastAPI**, **SQLAlchemy 2.0 (Async)**, and **PostgreSQL 16**.

```
.
├── .github/workflows/          # CI/CD Workflows (Cloud Run deployment & automated tests)
├── app/
│   ├── core/                   # Shared foundations (database, security, base models, auth dependencies)
│   ├── modules/                # Core clinical/operational modules (auth, patients, opd, ipd, billing, etc.)
│   ├── plugins/                # Specialty plugins (fertility, cosgyn, pharmacy, etc.)
│   ├── config.py               # Application settings & environment parsing
│   └── main.py                 # FastAPI application factory and router registration
├── Dockerfile                  # Production container definition
├── docker-entrypoint.sh        # Seeding and startup entrypoint
├── requirements.txt            # Python dependencies
├── .env.example                # Environment configuration template
└── docker-compose.yml          # Standalone backend + Postgres local orchestration
```

---

## 🚀 Quick Start (Local Development)

### 1. Prerequisites
- Python 3.11+
- PostgreSQL 16 (or Docker)

### 2. Environment Setup
```bash
cp .env.example .env
```
Update `.env` with your database credentials and secret keys.

### 3. Install Dependencies
```bash
python -m venv .venv
# On Windows PowerShell:
.venv\Scripts\Activate.ps1
# On macOS/Linux:
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Run Development Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
API Documentation will be accessible at:
- **Swagger UI**: [http://localhost:8000/api/docs](http://localhost:8000/api/docs)
- **ReDoc**: [http://localhost:8000/api/redoc](http://localhost:8000/api/redoc)

---

## 🐳 Docker Deployment

### Run Standalone Backend Stack
```bash
docker compose up -d --build
```
This boots:
1. PostgreSQL 16 container (`vaidya_md_backend_postgres`) on port `5432`
2. FastAPI Backend container (`vaidya_md_backend`) on port `8000`

---

## 🧪 Testing & Validation

```bash
# Python compilation check
python -c "import compileall; res = compileall.compile_dir('app', force=True, quiet=1); import sys; sys.exit(0 if res else 1)"
```

---

## 🚢 CI/CD & Deployment
- Deployments to **Google Cloud Run** are handled automatically on pushes to `main` via `.github/workflows/deploy.yml`.
- Pull requests and commits are verified with syntax and compile checks in `.github/workflows/ci.yml`.
