"""
VaidyaMD HMS — Database Schema Migration for VMD-001 - VMD-007
Applies non-destructive schema additions for:
- Doctor attribution on invoices (doctor_id, referring_doctor)
- Vendor attribution on inventory batches (vendor_id, vendor_name)
- Pharmacy Purchase Returns & Debit Notes table (pharmacy_purchase_returns)

Usage:
  python scripts/db/migrate_vmd_enhancements.py --env local
  python scripts/db/migrate_vmd_enhancements.py --env dev
  python scripts/db/migrate_vmd_enhancements.py --env prod
"""

import sys
import argparse
import asyncio
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from sqlalchemy import text
from scripts.db.env_resolver import create_env_engine, resolve_database_url


async def run_migration(env_name: str, explicit_url: str | None = None, auto_confirm: bool = False):
    resolved_url = resolve_database_url(env_name, explicit_url, auto_confirm)
    engine = create_env_engine(explicit_url=resolved_url)

    sql_path = Path(__file__).parent / "migrate_vmd_enhancements.sql"
    with open(sql_path, "r", encoding="utf-8") as f:
        sql_content = f.read()

    print(f"\n🚀 Running VMD schema enhancements on [{env_name}]...")
    async with engine.begin() as conn:
        for statement in sql_content.split(";"):
            stmt = statement.strip()
            if stmt:
                await conn.execute(text(stmt))

    await engine.dispose()
    print("✅ Migration executed successfully!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VaidyaMD HMS VMD Schema Migration")
    parser.add_argument("--env", default="local", choices=["local", "dev", "staging", "prod"])
    parser.add_argument("--database-url", dest="database_url", default=None)
    parser.add_argument("-y", "--yes", action="store_true", help="Auto-confirm prompt")
    args = parser.parse_args()

    asyncio.run(run_migration(args.env, args.database_url, args.yes))
