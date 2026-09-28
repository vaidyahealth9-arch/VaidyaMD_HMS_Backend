#!/usr/bin/env bash
set -e
echo "▶️ Resuming development Cloud SQL instance (hms-db-dev)..."
gcloud sql instances patch hms-db-dev --activation-policy=ALWAYS --project=vaidya-hms-dev --quiet
echo "✅ hms-db-dev successfully resumed and ready for connections."
