#!/bin/sh
set -e

echo "🚀 VaidyaMD HMS Backend Initializing (Zero-State Engine)..."
# In true zero-state architecture, database schema & tenant onboarding are run independently.
exec "$@"
