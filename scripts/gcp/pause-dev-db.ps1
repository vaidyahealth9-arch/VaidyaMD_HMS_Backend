<#
.SYNOPSIS
  Pauses the development Cloud SQL instance to eliminate vCPU and RAM billing.
.DESCRIPTION
  Sets activationPolicy to NEVER. While paused, only 10GB disk storage is billed (~$0.40/month).
#>
Write-Host "⏸️ Pausing development Cloud SQL instance (hms-db-dev)..." -ForegroundColor Yellow
gcloud sql instances patch hms-db-dev --activation-policy=NEVER --project=vaidya-hms-dev --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ hms-db-dev successfully paused. Compute billing is now stopped." -ForegroundColor Green
} else {
    Write-Host "❌ Failed to pause hms-db-dev." -ForegroundColor Red
}
