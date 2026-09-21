# GCP Cloud Run CI/CD Deployment & Secrets Setup Guide

> [!NOTE]
> All GCP infrastructure, Artifact Registry repositories, service accounts, IAM bindings, GCS buckets, Cloud DNS records, and **GCP Secret Manager secrets** have been **automatically generated and configured**. 
> Thanks to our **GCP Secret Manager integration**, your deployment is now **100% developer-friendly**: you only need to add **ONE secret (`GCP_CREDENTIALS`)** to GitHub!

---

## 1. Verified Infrastructure Matrix

| Parameter | Development (`dev`) | Production (`prod`) | Status |
| :--- | :--- | :--- | :--- |
| **GCP Project ID** | `vaidya-hms-dev` | `vaidya-hms-prod` | Active & Verified |
| **Project Number** | `1062509658389` | `242898387149` | Active & Verified |
| **Region** | `asia-south1` (Mumbai) | `asia-south1` (Mumbai) | Active & Verified |
| **Cloud Run Backend** | `hms-backend` | `hms-backend` | Configured with Secret Manager |
| **Cloud Run Frontend** | `hms-web` | `hms-web` | Configured with Custom Domains |
| **Artifact Registry** | `asia-south1-docker.pkg.dev/vaidya-hms-dev/hms-repo` | `asia-south1-docker.pkg.dev/vaidya-hms-prod/hms-repo` | Created & Verified |
| **Cloud SQL Instance** | `vaidya-hms-dev:asia-south1:hms-db-dev` | `vaidya-hms-prod:asia-south1:hms-db-prod` | Created & Verified |
| **GCS Uploads Bucket** | `gs://vaidya-hms-dev-uploads` | `gs://vaidya-hms-prod-uploads` | Configured with `roles/storage.objectAdmin` |
| **Service Account** | `github-actions@vaidya-hms-dev.iam.gserviceaccount.com` | `github-actions@vaidya-hms-prod.iam.gserviceaccount.com` | Key Generated in `.secrets/` |
| **Database Migrations** | **Manual only** | **Manual only** | Excluded from CI/CD pipeline |

---

## 2. GCP Secret Manager Integration (Developer Friendly)

All runtime backend configuration is safely stored in **Google Cloud Secret Manager** and automatically mounted into Cloud Run via `--set-secrets`. 

> [!TIP]
> **Why is this developer-friendly?**
> 1. **Zero Secret Fatigue**: You don't need to copy/paste 8 different secrets into GitHub settings.
> 2. **Instant Rotation**: If you rotate the database password or add a new domain to `CORS_ORIGINS`, simply add a new version in Google Cloud Console Secret Manager — no need to redeploy code or touch GitHub repositories!
> 3. **Auditable & Secure**: Secrets never appear in GitHub logs or runner disk files.

### Secrets Configured in Secret Manager:
| Secret Name | Managed In Project | Purpose |
| :--- | :--- | :--- |
| `hms-database-url` | `vaidya-hms-dev` & `vaidya-hms-prod` | Cloud SQL asyncpg connection URL |
| `hms-jwt-secret` | `vaidya-hms-dev` & `vaidya-hms-prod` | JWT signing secret |
| `hms-cors-origins` | `vaidya-hms-dev` & `vaidya-hms-prod` | Allowed CORS origins JSON array |
| `hms-gcs-bucket` | `vaidya-hms-dev` & `vaidya-hms-prod` | File upload storage bucket name |
| `hms-db-password` | `vaidya-hms-dev` & `vaidya-hms-prod` | Cloud SQL password |

---

## 3. Step 1: Create GitHub Environments

In **both** GitHub repositories:
- **Backend Repo**: [https://github.com/vaidyahealth9-arch/VaidyaMD_HMS_Backend/settings/environments](https://github.com/vaidyahealth9-arch/VaidyaMD_HMS_Backend/settings/environments)
- **Frontend Repo**: [https://github.com/vaidyahealth9-arch/VaidyaMD_HMS_Frontend/settings/environments](https://github.com/vaidyahealth9-arch/VaidyaMD_HMS_Frontend/settings/environments)

1. Click **New environment**.
2. Name the first environment: `dev` and save.
3. Click **New environment**.
4. Name the second environment: `prod` and save.
   - Under **Deployment branches**, select **Selected branches** -> **Add deployment branch rule** -> Type `main` -> Click **Add rule**.

---

## 4. Step 2: Add Secrets to GitHub

Because Secret Manager and automated domain defaults handle all configuration, you only need to add **`GCP_CREDENTIALS`**!

### A. Backend Repository
Navigate to: [https://github.com/vaidyahealth9-arch/VaidyaMD_HMS_Backend/settings/environments](https://github.com/vaidyahealth9-arch/VaidyaMD_HMS_Backend/settings/environments)

1. Under **`dev`** environment -> Click **Add secret**:
   - **Secret Name**: `GCP_CREDENTIALS`
   - **Value**: Content of `.secrets/dev-key.json`
   - *Quick PowerShell copy*:
     ```powershell
     Get-Content 'c:\Users\ranju\OneDrive\Documents\GitHub\Halelabs(Vaidya)\limsAndPhr\VaidyaMD_HMS\new\.secrets\dev-key.json' -Raw | Set-Clipboard
     ```
2. Under **`prod`** environment -> Click **Add secret**:
   - **Secret Name**: `GCP_CREDENTIALS`
   - **Value**: Content of `.secrets/prod-key.json`
   - *Quick PowerShell copy*:
     ```powershell
     Get-Content 'c:\Users\ranju\OneDrive\Documents\GitHub\Halelabs(Vaidya)\limsAndPhr\VaidyaMD_HMS\new\.secrets\prod-key.json' -Raw | Set-Clipboard
     ```

### B. Frontend Repository
Navigate to: [https://github.com/vaidyahealth9-arch/VaidyaMD_HMS_Frontend/settings/environments](https://github.com/vaidyahealth9-arch/VaidyaMD_HMS_Frontend/settings/environments)

1. Under **`dev`** environment -> Click **Add secret**:
   - **Secret Name**: `GCP_CREDENTIALS` (Content of `.secrets/dev-key.json`)
2. Under **`prod`** environment -> Click **Add secret**:
   - **Secret Name**: `GCP_CREDENTIALS` (Content of `.secrets/prod-key.json`)

*(Optional: If you want to override the default custom API domain `https://dev-api.vaidyamd.vaidyahealth.com`, you can optionally add `NEXT_PUBLIC_API_URL` as an environment secret, but it is not required!)*

---

## 5. Step 3: Trigger Deployments via GitHub Actions

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
