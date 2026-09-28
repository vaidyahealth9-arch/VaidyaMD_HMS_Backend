#!/usr/bin/env bash
set -e
echo "⏸️ Pausing development Cloud SQL instance (hms-db-dev)..."
gcloud sql instances patch hms-db-dev --activation-policy=NEVER --project=vaidya-hms-dev --quiet
echo "✅ hms-db-dev successfully paused. Compute billing is now stopped."
