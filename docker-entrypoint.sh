#!/bin/sh
set -e

echo "🚀 VaidyaMD HMS Backend Container Initializing..."

# Check if conditional seeding is requested
if [ "$SEED_DB" = "true" ] || [ "$SEED_DB" = "1" ] || [ "$SEED_DB" = "yes" ]; then
    SEED_MODE_VAL="${SEED_MODE:-demo}"
    echo "🌱 SEED_DB flag detected (Mode: $SEED_MODE_VAL). Running database seeder..."
    python -m app.core.seed --mode "$SEED_MODE_VAL"
else
    echo "🔒 Skipping database seed (SEED_DB=false). Database data is preserved."
fi

# Execute the primary container command
exec "$@"
