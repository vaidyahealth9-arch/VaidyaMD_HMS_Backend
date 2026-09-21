# GCP Cloud Run CI/CD Deployment & Secrets Setup Guide

This guide details how to configure GitHub Actions environments and secrets to enable manual deployments (`workflow_dispatch`) to Google Cloud Run in `asia-south1` (Mumbai).

---

## 1. Architecture Overview

| Parameter | Development (`dev`) | Production (`prod`) |
| :--- | :--- | :--- |
| **GCP Project ID** | `vaidya-hms-dev` | `vaidya-hms-prod` |
| **Region** | `asia-south1` (Mumbai) | `asia-south1` (Mumbai) |
| **Cloud Run Backend** | `hms-backend` | `hms-backend` |
| **Cloud Run Frontend** | `hms-web` | `hms-web` |
| **Artifact Registry** | `asia-south1-docker.pkg.dev/vaidya-hms-dev/hms-repo` | `asia-south1-docker.pkg.dev/vaidya-hms-prod/hms-repo` |
| **Cloud SQL Instance** | `vaidya-hms-dev:asia-south1:hms-db-dev` | `vaidya-hms-prod:asia-south1:hms-db-prod` |
| **GCS Uploads Bucket** | `gs://vaidya-hms-dev-uploads` | `gs://vaidya-hms-prod-uploads` |
| **Branch Safety** | Any branch (`development`, `main`, etc.) | **Strictly locked to `main` branch** |
| **Database Migrations** | **Manual only** (excluded from CI/CD) | **Manual only** (excluded from CI/CD) |

---

## 2. Generating Service Account Keys (GCP)

To allow GitHub Actions to build Docker containers and deploy to Cloud Run, generate JSON service account keys:

### Development Service Account Key
```bash
gcloud iam service-accounts keys create dev-key.json \
  --iam-account=github-actions@vaidya-hms-dev.iam.gserviceaccount.com \
  --project=vaidya-hms-dev
```

### Production Service Account Key
```bash
gcloud iam service-accounts keys create prod-key.json \
  --iam-account=github-actions@vaidya-hms-prod.iam.gserviceaccount.com \
  --project=vaidya-hms-prod
```

> [!WARNING]
> Keep `dev-key.json` and `prod-key.json` secure. Do NOT commit them to git repositories. After copying the contents to GitHub Secrets, delete the local JSON files.

---

## 3. GitHub Environments & Secrets Setup

In both GitHub repositories:
- **Backend Repo**: `https://github.com/vaidyahealth9-arch/VaidyaMD_HMS_Backend/settings/environments`
- **Frontend Repo**: `https://github.com/vaidyahealth9-arch/VaidyaMD_HMS_Frontend/settings/environments`

Create two environments:
1. `dev`
2. `prod` (Configure Deployment branch rule: Selected branches -> `main` only)

---

### Backend Secrets (`VaidyaMD_HMS_Backend`)

Configure the following secrets in **both** `dev` and `prod` environments:

| Secret Name | `dev` Environment Value | `prod` Environment Value |
| :--- | :--- | :--- |
| `GCP_CREDENTIALS` | Contents of `dev-key.json` | Contents of `prod-key.json` |
| `DATABASE_URL` | `postgresql+asyncpg://<dev_user>:<dev_pass>@/<db_name>?host=/cloudsql/vaidya-hms-dev:asia-south1:hms-db-dev` | `postgresql+asyncpg://<prod_user>:<prod_pass>@/<db_name>?host=/cloudsql/vaidya-hms-prod:asia-south1:hms-db-prod` |
| `JWT_SECRET_KEY` | Development JWT secret string | High-entropy production JWT secret string |
| `CORS_ORIGINS` | `["http://localhost:3000","https://dev.vaidyamd.com","https://hms-web-...run.app"]` | `["https://app.vaidyamd.com"]` |

---

### Frontend Secrets (`VaidyaMD_HMS_Frontend`)

Configure the following secrets in **both** `dev` and `prod` environments:

| Secret Name | `dev` Environment Value | `prod` Environment Value |
| :--- | :--- | :--- |
| `GCP_CREDENTIALS` | Contents of `dev-key.json` | Contents of `prod-key.json` |
| `NEXT_PUBLIC_API_URL` | E.g. `https://hms-backend-...run.app/api` or `https://api.dev.vaidyamd.com/api` | E.g. `https://api.vaidyamd.com/api` |
| `NEXT_PUBLIC_WS_URL` | E.g. `wss://hms-backend-...run.app/ws` or `wss://api.dev.vaidyamd.com/ws` | E.g. `wss://api.vaidyamd.com/ws` |

---

## 4. How to Trigger Deployment

1. Navigate to the repository on GitHub (`VaidyaMD_HMS_Backend` or `VaidyaMD_HMS_Frontend`).
2. Go to the **Actions** tab.
3. Select **Deploy Backend to GCP Cloud Run** (or **Deploy Frontend to GCP Cloud Run**).
4. Click the **Run workflow** dropdown on the right:
   - **Target Environment**: Select `dev` or `prod`.
   - **confirm_prod**: If `prod` is selected, type `DEPLOY-PROD`.
   - Select the branch (`main` for prod, any branch for dev).
5. Click **Run workflow**.

---

## 5. Purpose-Based Uploads Folder Taxonomy in GCS

Uploads to Google Cloud Storage (`gs://vaidya-hms-{env}-uploads`) are automatically organized into purpose-based folders:

```text
gs://vaidya-hms-{dev|prod}-uploads/
├── branding/
│   └── {tenant_id}/
│       └── logo_{uuid}.png
├── patients/
│   └── {patient_id}/
│       ├── profile/
│       │   └── photo_{uuid}.jpg
│       ├── identity/
│       │   └── aadhaar_{uuid}.pdf
│       ├── scans/
│       │   └── tvs_usg_{uuid}.jpg
│       ├── lab_reports/
│       │   └── semen_analysis_{uuid}.pdf
│       ├── consents/
│       │   └── art_form_8_{uuid}.pdf
│       └── prescriptions/
│           └── outside_rx_{uuid}.pdf
├── pharmacy/
│   └── invoices/
│       └── {tenant_id}/
│           └── {YYYY-MM}/
│               └── vendor_inv_{uuid}.pdf
└── imports/
    └── csv/
        └── {tenant_id}/
            └── {domain}_{timestamp}.csv
```
