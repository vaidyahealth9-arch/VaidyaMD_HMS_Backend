# GCP Cloud Run CI/CD Deployment & Secrets Setup Guide

> [!NOTE]
> All GCP infrastructure, Artifact Registry repositories, service accounts, IAM bindings, GCS buckets, and service account keys have been **automatically generated and configured**. 
> The **ONLY remaining step** is adding the secrets listed below into your GitHub repository settings.

---

## 1. Verified Infrastructure Matrix

| Parameter | Development (`dev`) | Production (`prod`) | Status |
| :--- | :--- | :--- | :--- |
| **GCP Project ID** | `vaidya-hms-dev` | `vaidya-hms-prod` | Active & Verified |
| **Project Number** | `1062509658389` | `242898387149` | Active & Verified |
| **Region** | `asia-south1` (Mumbai) | `asia-south1` (Mumbai) | Active & Verified |
| **Cloud Run Backend** | `hms-backend` | `hms-backend` | Configured |
| **Cloud Run Frontend** | `hms-web` | `hms-web` | Configured |
| **Artifact Registry** | `asia-south1-docker.pkg.dev/vaidya-hms-dev/hms-repo` | `asia-south1-docker.pkg.dev/vaidya-hms-prod/hms-repo` | Created & Verified |
| **Cloud SQL Instance** | `vaidya-hms-dev:asia-south1:hms-db-dev` | `vaidya-hms-prod:asia-south1:hms-db-prod` | Created & Verified |
| **Cloud SQL DB / User** | `vaidya_md_db` / `vaidya_md_admin` | `vaidya_md_db` / `vaidya_md_admin` | Created & Verified |
| **GCS Uploads Bucket** | `gs://vaidya-hms-dev-uploads` | `gs://vaidya-hms-prod-uploads` | Configured with `roles/storage.objectAdmin` |
| **Service Account** | `github-actions@vaidya-hms-dev.iam.gserviceaccount.com` | `github-actions@vaidya-hms-prod.iam.gserviceaccount.com` | Key Generated in `.secrets/` |
| **Database Migrations** | **Manual only** | **Manual only** | Excluded from CI/CD pipeline |

---

## 2. Step 1: Create GitHub Environments

In **both** GitHub repositories:
- **Backend Repo**: [https://github.com/vaidyahealth9-arch/VaidyaMD_HMS_Backend/settings/environments](https://github.com/vaidyahealth9-arch/VaidyaMD_HMS_Backend/settings/environments)
- **Frontend Repo**: [https://github.com/vaidyahealth9-arch/VaidyaMD_HMS_Frontend/settings/environments](https://github.com/vaidyahealth9-arch/VaidyaMD_HMS_Frontend/settings/environments)

1. Click **New environment**.
2. Name the first environment: `dev` and save.
3. Click **New environment**.
4. Name the second environment: `prod` and save.
   - Under **Deployment branches**, select **Selected branches** -> **Add deployment branch rule** -> Type `main` -> Click **Add rule**.

---

## 3. Step 2: Add Secrets to Backend Repository

Navigate to: [https://github.com/vaidyahealth9-arch/VaidyaMD_HMS_Backend/settings/environments](https://github.com/vaidyahealth9-arch/VaidyaMD_HMS_Backend/settings/environments)

### A. Under `dev` Environment (Click "Add environment secret"):

| Secret Name | Exact Value to Copy & Paste | Description / Quick Copy |
| :--- | :--- | :--- |
| **`GCP_CREDENTIALS`** | Content of `.secrets/dev-key.json` | Run in PowerShell to copy to clipboard:<br>`Get-Content 'c:\Users\ranju\OneDrive\Documents\GitHub\Halelabs(Vaidya)\limsAndPhr\VaidyaMD_HMS\new\.secrets\dev-key.json' -Raw \| Set-Clipboard` |
| **`DATABASE_URL`** | `postgresql+asyncpg://vaidya_md_admin:vaidya_md_secret_2026@/vaidya_md_db?host=/cloudsql/vaidya-hms-dev:asia-south1:hms-db-dev` | Cloud SQL asyncpg connection for Dev |
| **`JWT_SECRET_KEY`** | `vaidya_md_jwt_secret_dev_2026_super_secure_antigravity_token` | Dev JWT token signing secret |
| **`CORS_ORIGINS`** | `["http://localhost:3000","https://hms-web-1062509658389.asia-south1.run.app","https://lrmtc5jt-3000.inc1.devtunnels.ms"]` | JSON array of permitted dev origins |

---

### B. Under `prod` Environment (Click "Add environment secret"):

| Secret Name | Exact Value to Copy & Paste | Description / Quick Copy |
| :--- | :--- | :--- |
| **`GCP_CREDENTIALS`** | Content of `.secrets/prod-key.json` | Run in PowerShell to copy to clipboard:<br>`Get-Content 'c:\Users\ranju\OneDrive\Documents\GitHub\Halelabs(Vaidya)\limsAndPhr\VaidyaMD_HMS\new\.secrets\prod-key.json' -Raw \| Set-Clipboard` |
| **`DATABASE_URL`** | `postgresql+asyncpg://vaidya_md_admin:vaidya_md_prod_secret_DuT9xNYMITQLcE2WSQUE3g@/vaidya_md_db?host=/cloudsql/vaidya-hms-prod:asia-south1:hms-db-prod` | Cloud SQL asyncpg connection for Prod |
| **`JWT_SECRET_KEY`** | `SUP8Dvig537pdINog1_IrMIvtdcGaE_F8WwXzJdwyE9jz4imrsmIzgjORo0xO4W0` | Production high-entropy JWT secret |
| **`CORS_ORIGINS`** | `["https://hms-web-242898387149.asia-south1.run.app","https://app.vaidyamd.com","https://vaidyamd.com"]` | JSON array of permitted prod origins |

---

## 4. Step 3: Add Secrets to Frontend Repository

Navigate to: [https://github.com/vaidyahealth9-arch/VaidyaMD_HMS_Frontend/settings/environments](https://github.com/vaidyahealth9-arch/VaidyaMD_HMS_Frontend/settings/environments)

### A. Under `dev` Environment (Click "Add environment secret"):

| Secret Name | Exact Value to Copy & Paste | Description / Quick Copy |
| :--- | :--- | :--- |
| **`GCP_CREDENTIALS`** | Content of `.secrets/dev-key.json` | Run in PowerShell to copy to clipboard:<br>`Get-Content 'c:\Users\ranju\OneDrive\Documents\GitHub\Halelabs(Vaidya)\limsAndPhr\VaidyaMD_HMS\new\.secrets\dev-key.json' -Raw \| Set-Clipboard` |
| **`NEXT_PUBLIC_API_URL`** | `https://hms-backend-1062509658389.asia-south1.run.app/api` | Dev Cloud Run backend API endpoint |
| **`NEXT_PUBLIC_WS_URL`** | `wss://hms-backend-1062509658389.asia-south1.run.app/ws` | Dev Cloud Run WebSocket endpoint |

---

### B. Under `prod` Environment (Click "Add environment secret"):

| Secret Name | Exact Value to Copy & Paste | Description / Quick Copy |
| :--- | :--- | :--- |
| **`GCP_CREDENTIALS`** | Content of `.secrets/prod-key.json` | Run in PowerShell to copy to clipboard:<br>`Get-Content 'c:\Users\ranju\OneDrive\Documents\GitHub\Halelabs(Vaidya)\limsAndPhr\VaidyaMD_HMS\new\.secrets\prod-key.json' -Raw \| Set-Clipboard` |
| **`NEXT_PUBLIC_API_URL`** | `https://hms-backend-242898387149.asia-south1.run.app/api` | Prod Cloud Run backend API endpoint (or custom domain if configured) |
| **`NEXT_PUBLIC_WS_URL`** | `wss://hms-backend-242898387149.asia-south1.run.app/ws` | Prod Cloud Run WebSocket endpoint |

---

## 5. Step 4: Running Deployments via GitHub Actions

1. Go to the **Actions** tab in either repository:
   - [Backend Actions](https://github.com/vaidyahealth9-arch/VaidyaMD_HMS_Backend/actions)
   - [Frontend Actions](https://github.com/vaidyahealth9-arch/VaidyaMD_HMS_Frontend/actions)
2. Select the workflow:
   - **Deploy Backend to GCP Cloud Run** or **Deploy Frontend to GCP Cloud Run**.
3. Click the **Run workflow** dropdown on the right:
   - **Target Environment**: Select `dev` or `prod`.
   - **confirm_prod**: Leave blank for `dev`. If deploying to `prod`, type `DEPLOY-PROD`.
   - **Branch**: Select `development` or `main` (Note: `prod` strictly requires `main`).
4. Click the green **Run workflow** button.

---

## 6. How Database Migrations Work

As per your specification, **automated database migrations are excluded from the CI/CD pipeline**. 

Whenever you need to apply schema migrations to Cloud SQL:
1. Start Cloud SQL Proxy locally:
   ```bash
   # For Dev:
   cloud-sql-proxy vaidya-hms-dev:asia-south1:hms-db-dev --port=5434

   # For Prod:
   cloud-sql-proxy vaidya-hms-prod:asia-south1:hms-db-prod --port=5434
   ```
2. Run your migration scripts or psql pointing to `127.0.0.1:5434`.
