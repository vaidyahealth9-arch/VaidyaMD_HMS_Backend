import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = BASE_DIR / "VaidyaMD_HMS_Backend"
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BASE_DIR))

import asyncio
from app.core.database import AsyncSessionLocal
from sqlalchemy import text

# Mapping of item_code to (pack_size, is_raw_qty_in_sheets)
PACK_SIZE_RULES = {
    # Oral strips originally entered as sheets
    "COHB03": (1, False),       # Sachet
    "SEEV01": (10, True),       # Evatone 10 tabs/sheet, was 30 sheets -> 300 tabs
    "SEME02": (10, True),       # Meprate 10 tabs/sheet, was 30 sheets -> 300 tabs
    "RXFE01": (10, True),       # Fertyl 10 tabs/sheet, was 5 sheets -> 50 tabs
    "MIDO02": (15, True),       # Dolo 650 15 tabs/sheet, was 12 sheets -> 180 tabs
    "MIDO20": (15, True),       # Dolo 500 15 tabs/sheet, was 10 sheets -> 150 tabs
    "ELCH01": (10, True),       # Chymoral Forte 10 tabs/sheet, was 10 sheets -> 100 tabs
    "NORE01": (10, True),       # Regestrone 10 tabs/sheet, was 10 sheets -> 100 tabs
    "UNCO05": (10, True),       # CoQ 10 caps/sheet, was 9 sheets -> 90 caps
    "LEFO01": (10, True),       # Folvite 10 tabs/sheet, was 32 sheets -> 320 tabs
    "GEDI01": (21, True),       # Diane 35 21 tabs/sheet, was 1 sheet -> 21 tabs
    "HELE02": (10, True),       # Levocet M 10 tabs/sheet, was 18 sheets -> 180 tabs
    "IPZE04": (10, True),       # Zerodol MR 10 tabs/sheet, was 10 sheets -> 100 tabs
    "GEPR02": (1, False),       # Proluton Depot Inj 1 vial
    "MENE08": (10, True),       # Neurobion Forte 10 tabs/sheet, was 30 sheets -> 300 tabs
    "EMEV05": (10, True),       # Evion LC 10 tabs/sheet, was 15 sheets -> 150 tabs
    "EMLI02": (15, True),       # Livogen Z 15 tabs/sheet, was 30 sheets -> 450 tabs
    "MANU12": (10, True),       # Nurokind LC 10 tabs/sheet, was 15 sheets -> 150 tabs
    "ORFE03": (21, True),       # Femilon 21 tabs/sheet, was 30 sheets -> 630 tabs
    "ORNO01": (21, True),       # Novelon 21 tabs/sheet, was 29 sheets -> 609 tabs
    "BOGL01": (10, True),       # Gluformin 500 10 tabs/sheet, was 15 sheets -> 150 tabs
    "SODU02": (10, True),       # Duphaston 10 tabs/sheet, was 12 sheets -> 120 tabs
    "SUSU01": (10, True),       # Susten 100mg 10 caps/sheet, was 5 sheets -> 50 caps
    "SUTR06": (10, True),       # Trapic MF 10 tabs/sheet, was 4 sheets -> 40 tabs
    "SUFE03": (10, True),       # Fertisure F 10 tabs/sheet, was 15 sheets -> 150 tabs
    "MOTR01": (10, True),       # Trenaxa 10 tabs/sheet, was 10 sheets -> 100 tabs
    "CIP184": (10, True),       # Cip-zox 10 tabs/sheet, was 10 sheets -> 100 tabs
    
    # Items already having loose unit counts
    "MED-ASP-013": (14, False), # Ecosprin 75mg tab (14/strip, 800 tabs)
    "MED-AUG-010": (10, False), # Augmentin 625 Duo (10/strip, 500 tabs)
    "MED-AZI-011": (5, False),  # Azithral 500 (5/strip, 300 tabs)
    "MED-CAB-014": (4, False),  # Caberlin 0.5 (4/strip, 150 tabs)
    "MED-CAN-026": (6, False),  # Candid V6 (6/strip, 150 tabs)
    "MED-CET-003": (1, False),  # Cetrotide Inj 1 vial
    "MED-CIP-027": (10, False), # Ciplox 500 (10/strip, 250 tabs)
    "MED-CLX-024": (1, False),  # Clexane Inj 1 syringe
    "MED-DEC-005": (1, False),  # Decapeptyl Inj 1 syringe
    "MED-DOX-022": (10, False), # Doxy-1 (10/strip, 200 caps)
    "MED-EMS-030": (10, False), # Emeset 4mg (10/strip, 200 tabs)
    "MED-GON-001": (1, False),  # Gonal-F Pen 1 pen
    "MED-LET-019": (5, False),  # Letroz 2.5mg (5/strip, 50 tabs)
    "MED-MEF-021": (10, False), # Meftal-spas (10/strip, 250 tabs)
    "MED-MEN-002": (1, False),  # Menopur 75 IU Inj 1 vial
    "MED-MTZ-025": (15, False), # Flagyl 400 (15/strip, 300 tabs)
    "MED-OVI-004": (1, False),  # Ovidrel PFS 1 syringe
    "MED-PAN-020": (15, False), # Pan-D (15/strip, 300 caps)
    "MED-SHL-023": (15, False), # Shelcal 500 (15/strip, 400 tabs)
    "MED-SUS-007": (10, False), # Susten 400 Vaginal Tab (10/strip, 300 tabs)
    "MED-THY-028": (100, False),# Thyronorm 50mcg (100/bottle, 200 tabs)
    "MED-VD3-029": (1, False),  # Calcirol Sachet 1 sachet
    "MED-VOV-031": (15, False), # Voveran 50mg (15/strip, 250 tabs)
}

async def migrate_batches():
    async with AsyncSessionLocal() as session:
        res = await session.execute(text("SELECT id, item_code, item_name, quantity_available, quantity_received FROM inventory_batches"))
        rows = res.fetchall()
        updated_count = 0
        for row in rows:
            b_id, item_code, item_name, qty_avail, qty_rec = row[0], row[1], row[2], row[3], row[4]
            rule = PACK_SIZE_RULES.get(item_code)
            if not rule:
                # Default heuristic: if 'TAB' or 'CAP' in name -> 10, else 1
                name_upper = (item_name or "").upper()
                p_sz = 10 if ("TAB" in name_upper or "CAP" in name_upper) else 1
                is_sheets = False
            else:
                p_sz, is_sheets = rule
            
            new_avail = (qty_avail * p_sz) if is_sheets else qty_avail
            new_rec = (qty_rec * p_sz) if is_sheets else qty_rec

            await session.execute(
                text("""
                    UPDATE inventory_batches
                    SET pack_size = :pack_size,
                        quantity_available = :qty_avail,
                        quantity_received = :qty_rec
                    WHERE id = :b_id
                """),
                {"pack_size": p_sz, "qty_avail": new_avail, "qty_rec": new_rec, "b_id": b_id}
            )
            updated_count += 1
        
        await session.commit()
        print(f"Successfully migrated {updated_count} batches with accurate pack_size and loose unit quantities!")

if __name__ == "__main__":
    asyncio.run(migrate_batches())

