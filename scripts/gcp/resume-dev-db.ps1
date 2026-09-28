<#
.SYNOPSIS
  Resumes the development Cloud SQL instance.
.DESCRIPTION
  Sets activationPolicy to ALWAYS. Resumes compute instance and allows connections.
#>
Write-Host "▶️ Resuming development Cloud SQL instance (hms-db-dev)..." -ForegroundColor Cyan
gcloud sql instances patch hms-db-dev --activation-policy=ALWAYS --project=vaidya-hms-dev --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ hms-db-dev successfully resumed and ready for connections." -ForegroundColor Green
} else {
    Write-Host "❌ Failed to resume hms-db-dev." -ForegroundColor Red
}
