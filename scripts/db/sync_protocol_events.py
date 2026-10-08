"""
Sync Clinical Protocol Timeline Events from 07_clinical_protocols.csv to Database.
"""
import asyncio
import csv
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import text
from app.core.database import AsyncSessionLocal

CSV_PATH = Path(__file__).resolve().parent / "templates" / "07_clinical_protocols.csv"

async def sync_events():
    if not CSV_PATH.exists():
        print(f"Error: CSV file not found at {CSV_PATH}")
        return

    with open(CSV_PATH, mode="r", encoding="utf-8-sig") as f:
        reader = list(csv.DictReader(f))

    prot_events = {}
    for r in reader:
        if (r.get("record_type") or "").strip().upper() == "PROTOCOL":
            p_name = (r.get("protocol_name") or "").strip()
            raw_ev = r.get("timeline_events")
            if raw_ev:
                try:
                    events = json.loads(raw_ev)
                    prot_events[p_name] = events
                except Exception as e:
                    print(f"Failed to parse JSON for {p_name}: {e}")

    print(f"Parsed {len(prot_events)} protocols with timeline events from CSV.")

    async with AsyncSessionLocal() as session:
        for p_name, events in prot_events.items():
            ev_json = json.dumps(events)
            query = text("""
                UPDATE protocol_templates
                SET timeline_events = CAST(:events AS jsonb)
                WHERE LOWER(name) = LOWER(:p_name);
            """)
            await session.execute(query, {"events": ev_json, "p_name": p_name})
            print(f"[OK] Updated '{p_name}': {len(events)} events synced.")

        await session.commit()

        # Verify
        check_q = text("SELECT name, jsonb_array_length(timeline_events) FROM protocol_templates WHERE timeline_events IS NOT NULL;")
        res = await session.execute(check_q)
        print("\n--- Current Protocol Event Counts in Database ---")
        for row in res.fetchall():
            print(f"  * {row[0]}: {row[1]} events")

if __name__ == "__main__":
    asyncio.run(sync_events())
