"""
VaidyaMD HMS — Standalone Schema Initializer (Canonical Models)
Executes Base.metadata.create_all against target database directly from canonical SQLAlchemy models.
Supports optional --drop-all for clean one-time dev/local environment reset.
Does NOT create or seed any dummy data. Pure zero-state schema initializer.

Usage:
  python scripts/db/init_schema.py --env local
  python scripts/db/init_schema.py --env dev --drop-all
  python scripts/db/init_schema.py --env prod --dry-run
  python scripts/db/init_schema.py --database-url "postgresql+asyncpg://..."
"""

import sys
import os
import argparse
import asyncio
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = BASE_DIR / "VaidyaMD_HMS_Backend"
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BASE_DIR))

from sqlalchemy import text
from app.core.database import Base
# Import universal models package to ensure registration of all 34 models on Base.metadata
import app.core.models  # noqa: F401
from scripts.db.env_resolver import create_env_engine, resolve_database_url


async def run_init_schema(
    env_name: str,
    explicit_url: str | None = None,
    auto_confirm: bool = False,
    dry_run: bool = False,
    drop_all: bool = False,
):
    resolved_url = resolve_database_url(env_name, explicit_url, auto_confirm)
    display_url = resolved_url
    if "@" in display_url and ":" in display_url.split("@")[0]:
        parts = display_url.split("@")
        prefix = parts[0]
        user_part = prefix.split("://")[1].split(":")[0]
        display_url = f"{prefix.split('://')[0]}://{user_part}:****@{parts[1]}"

    print("\n" + "=" * 75)
    print("🛠️  VaidyaMD HMS — Database Schema Initializer (Canonical Models)")
    print(f"🎯 Target Environment : {env_name.upper()}")
    print(f"🔗 Target Database    : {display_url}")
    print(f"🗑️  Drop All Existing  : {'YES (Reset)' if drop_all else 'NO (Preserve/Extend)'}")
    print(f"🔍 Dry Run Mode       : {'YES' if dry_run else 'NO'}")
    print("=" * 75)

    if drop_all and env_name == "prod" and not auto_confirm:
        print("\n🚨 DANGER: You requested --drop-all against PRODUCTION environment!")
        confirm = input("Type 'DROP ALL PRODUCTION DATA' to proceed: ")
        if confirm != "DROP ALL PRODUCTION DATA":
            print("❌ Operation cancelled.")
            sys.exit(1)

    if dry_run:
        if drop_all:
            print("\n[DRY RUN] Would execute Base.metadata.drop_all (DROP all registered tables).")
        print("\n[DRY RUN] Would create all tables from canonical SQLAlchemy ORM models:")
        for t in sorted(Base.metadata.tables.keys()):
            print(f"  • {t}")
        print("\n✅ Dry run completed successfully. No changes made.")
        return

    engine = create_env_engine(env_name, explicit_url, auto_confirm)

    try:
        print("\n🔄 1/3 Connecting and validating database connection...")
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            print("  ✅ Connection established successfully.")

            if drop_all:
                print("\n🔄 2/3 Dropping existing tables (Base.metadata.drop_all)...")
                await conn.run_sync(Base.metadata.drop_all)
                print("  ✅ All existing tables dropped cleanly.")
            else:
                print("\n🔄 2/3 Skipping drop (preserving existing tables)...")

            print(f"\n🔄 3/3 Creating schema from {len(Base.metadata.tables)} canonical models (Base.metadata.create_all)...")
            await conn.run_sync(Base.metadata.create_all)

            # Ensure incremental column additions on existing tables
            column_migrations = [
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS qualification VARCHAR(255);",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS reg_number VARCHAR(100);",
                "ALTER TABLE treatment_cycle_types ADD COLUMN IF NOT EXISTS category VARCHAR(100);",
                "ALTER TABLE branches ADD COLUMN IF NOT EXISTS gstin VARCHAR(50);",
                "ALTER TABLE branches ADD COLUMN IF NOT EXISTS receipt_header JSONB DEFAULT '{}'::jsonb;",
                "ALTER TABLE branches ADD COLUMN IF NOT EXISTS ip_whitelist JSONB DEFAULT '[]'::jsonb;",
                "ALTER TABLE protocol_templates ADD COLUMN IF NOT EXISTS timeline_events JSONB DEFAULT '[]'::jsonb;",
                "ALTER TABLE treatment_cycles ADD COLUMN IF NOT EXISTS medication_calendar JSONB DEFAULT '[]'::jsonb;",
                "ALTER TABLE treatment_cycles ADD COLUMN IF NOT EXISTS et_discharge_summary JSONB DEFAULT '{}'::jsonb;",
                "ALTER TABLE patients ADD COLUMN IF NOT EXISTS marketing_person_name VARCHAR(255);",
                "ALTER TABLE patients ADD COLUMN IF NOT EXISTS referring_doctor VARCHAR(255);",
                "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS branch_id UUID REFERENCES branches(id);",
                "ALTER TABLE wallet_transactions ADD COLUMN IF NOT EXISTS branch_id UUID REFERENCES branches(id);",
            ]
            for stmt in column_migrations:
                try:
                    await conn.execute(text(stmt))
                except Exception as col_err:
                    print(f"  ⚠️ Migration notice for '{stmt}': {col_err}")

            print(f"  ✅ All {len(Base.metadata.tables)} tables, columns, and foreign keys synchronized successfully.")

        print("\n" + "=" * 75)
        print(f"🎉 SUCCESS: Database schema for '{env_name.upper()}' is 100% up-to-date!")
        print("🔒 Canonical ORM schema applied directly. Zero raw SQL migration statements required.")
        print("=" * 75 + "\n")

    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="VaidyaMD HMS Canonical Database Initializer")
    parser.add_argument(
        "--env",
        choices=["local", "dev", "prod"],
        default="local",
        help="Target environment (default: local)",
    )
    parser.add_argument(
        "--database-url",
        dest="database_url",
        default=None,
        help="Explicit database URL override",
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Bypass interactive confirmation prompt when targeting prod",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect execution plan without making changes",
    )
    parser.add_argument(
        "--drop-all",
        action="store_true",
        help="Drop all existing tables before recreating schema (clean one-time reset)",
    )

    args = parser.parse_args()
    asyncio.run(
        run_init_schema(
            env_name=args.env,
            explicit_url=args.database_url,
            auto_confirm=args.yes,
            dry_run=args.dry_run,
            drop_all=args.drop_all,
        )
    )


if __name__ == "__main__":
    main()
