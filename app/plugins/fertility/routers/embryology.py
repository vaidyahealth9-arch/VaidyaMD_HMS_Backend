"""
VaidyaMD HMS — Embryology Lab & Dual-Witnessing Gate Router
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel
from typing import Optional, Any, List

from app.core.database import get_db
from app.core.models import OocyteRecord, EmbryologyWitness, TreatmentCycle, User

router = APIRouter(prefix="/embryology", tags=["Fertility — Embryology Lab"])


# --- Schemas ---
class OocyteBatchCreate(BaseModel):
    treatment_cycle_id: UUID
    count: int = 10
    procedure_type: str = "ICSI"
    default_maturity: str = "MII"


class OocyteDayUpdate(BaseModel):
    oocyte_id: UUID
    day_number: int  # 1 to 7
    day_data: dict[str, Any]
    fert_check: Optional[str] = None
    disposition: Optional[dict[str, Any]] = None


class WitnessSignoffRequest(BaseModel):
    treatment_cycle_id: UUID
    day_number: int  # 0 to 7
    checked_by_id: UUID
    witnessed_by_id: UUID
    notes: Optional[str] = None


@router.post("/oocytes/batch", status_code=201)
async def batch_create_oocytes(payload: OocyteBatchCreate, db: AsyncSession = Depends(get_db)):
    """Create initial batch of oocyte rows at OPU (Day 0)."""
    cycle = await db.get(TreatmentCycle, payload.treatment_cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Treatment cycle not found")

    created_oocytes = []
    for i in range(1, payload.count + 1):
        oocyte = OocyteRecord(
            treatment_cycle_id=payload.treatment_cycle_id,
            oocyte_number=i,
            procedure_type=payload.procedure_type,
            maturity_day0=payload.default_maturity,
            quality_day0="Good",
        )
        db.add(oocyte)
        created_oocytes.append(oocyte)

    await db.flush()
    return {"message": f"Created {len(created_oocytes)} oocyte records for Day 0", "count": len(created_oocytes)}


@router.get("/oocytes")
async def get_cycle_oocytes(cycle_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get all oocyte records for a treatment cycle (Day 0 through Day 7)."""
    result = await db.execute(
        select(OocyteRecord)
        .where(OocyteRecord.treatment_cycle_id == cycle_id)
        .order_by(OocyteRecord.oocyte_number)
    )
    return result.scalars().all()


@router.patch("/oocytes/update-day")
async def update_oocyte_day(payload: OocyteDayUpdate, db: AsyncSession = Depends(get_db)):
    """
    Update Day N data for an oocyte.
    ENFORCEMENT: Verifies that Day N-1 witness sign-off is completed before allowing Day N data entry.
    """
    oocyte = await db.get(OocyteRecord, payload.oocyte_id)
    if not oocyte:
        raise HTTPException(status_code=404, detail="Oocyte record not found")

    # Hard Witness Gate: If updating Day 1+, verify Day N-1 has a witness record
    if payload.day_number > 0:
        prev_day = payload.day_number - 1
        witness_res = await db.execute(
            select(EmbryologyWitness).where(
                EmbryologyWitness.treatment_cycle_id == oocyte.treatment_cycle_id,
                EmbryologyWitness.day_number == prev_day,
                EmbryologyWitness.is_verified == True,
            )
        )
        witness_record = witness_res.scalar_one_or_none()
        if not witness_record:
            raise HTTPException(
                status_code=422,
                detail=f"MANDATORY DUAL-WITNESSING GATE: Day {prev_day} must be verified and signed off by a secondary witness before recording Day {payload.day_number} embryo data."
            )

    # Apply Day Data update
    if payload.day_number == 1:
        oocyte.day1_data = {**(oocyte.day1_data or {}), **payload.day_data}
        if payload.fert_check:
            oocyte.fert_check_day1 = payload.fert_check
    elif payload.day_number == 2:
        oocyte.day2_data = {**(oocyte.day2_data or {}), **payload.day_data}
    elif payload.day_number == 3:
        oocyte.day3_data = {**(oocyte.day3_data or {}), **payload.day_data}
    elif payload.day_number == 4:
        oocyte.day4_data = {**(oocyte.day4_data or {}), **payload.day_data}
    elif payload.day_number == 5:
        oocyte.day5_data = {**(oocyte.day5_data or {}), **payload.day_data}
    elif payload.day_number == 6:
        oocyte.day6_data = {**(oocyte.day6_data or {}), **payload.day_data}
    elif payload.day_number == 7:
        oocyte.day7_data = {**(oocyte.day7_data or {}), **payload.day_data}

    if payload.disposition:
        oocyte.disposition = payload.disposition

    await db.flush()
    await db.refresh(oocyte)
    return oocyte


@router.post("/witnesses", status_code=201)
async def signoff_witness(payload: WitnessSignoffRequest, db: AsyncSession = Depends(get_db)):
    """
    Record Dual-Witnessing Signoff for a Day.
    STRICT RULE: Primary checked_by_id CANNOT be the same as secondary witnessed_by_id.
    """
    if payload.checked_by_id == payload.witnessed_by_id:
        raise HTTPException(
            status_code=422,
            detail="Dual-witnessing requires TWO distinct users. The primary embryologist and secondary witness cannot be the same user."
        )

    # Check if already signed off
    existing_res = await db.execute(
        select(EmbryologyWitness).where(
            EmbryologyWitness.treatment_cycle_id == payload.treatment_cycle_id,
            EmbryologyWitness.day_number == payload.day_number,
        )
    )
    existing = existing_res.scalar_one_or_none()
    if existing:
        existing.checked_by_id = payload.checked_by_id
        existing.witnessed_by_id = payload.witnessed_by_id
        existing.witnessed_at = datetime.utcnow()
        existing.notes = payload.notes
        await db.flush()
        return {"message": f"Updated witness record for Day {payload.day_number}", "record": existing}

    witness = EmbryologyWitness(
        treatment_cycle_id=payload.treatment_cycle_id,
        day_number=payload.day_number,
        checked_by_id=payload.checked_by_id,
        witnessed_by_id=payload.witnessed_by_id,
        checked_at=datetime.utcnow(),
        witnessed_at=datetime.utcnow(),
        is_verified=True,
        notes=payload.notes,
    )
    db.add(witness)
    await db.flush()
    await db.refresh(witness)
    return {"message": f"Day {payload.day_number} dual-witnessing successfully verified", "record": witness}


@router.get("/witnesses")
async def get_cycle_witnesses(cycle_id: UUID, db: AsyncSession = Depends(get_db)):
    """Fetch all witness audit records for a cycle."""
    result = await db.execute(
        select(EmbryologyWitness)
        .where(EmbryologyWitness.treatment_cycle_id == cycle_id)
        .order_by(EmbryologyWitness.day_number)
    )
    return result.scalars().all()


@router.get("/cycles/{cycle_id}/kpis")
async def calculate_cycle_kpis(cycle_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Calculate and return computed Embryology KPIs:
    - Fertilization Rate = (2PN count) / (total MII count) * 100
    - Cleavage Rate = (Day-2 cleaved) / (2PN count) * 100
    - Blastocyst Rate = (Day-5 blastocysts) / (Day-3 embryos) * 100
    - Utilization Rate = (Transferred + Frozen) / (Total Fertilized) * 100
    """
    result = await db.execute(
        select(OocyteRecord).where(OocyteRecord.treatment_cycle_id == cycle_id)
    )
    oocytes = result.scalars().all()

    total_oocytes = len(oocytes)
    mii_count = sum(1 for o in oocytes if o.maturity_day0 == "MII")
    fert_2pn = sum(1 for o in oocytes if o.fert_check_day1 == "2PN")
    cleaved_d2 = sum(1 for o in oocytes if (o.day2_data or {}).get("cells", 0) >= 2)
    d3_count = sum(1 for o in oocytes if (o.day3_data or {}).get("cells", 0) >= 4)
    blast_d5 = sum(1 for o in oocytes if (o.day5_data or {}).get("stage") == "Blastocyst" or (o.day5_data or {}).get("gardner"))
    
    transferred = sum(1 for o in oocytes if (o.disposition or {}).get("status") == "Transferred")
    frozen = sum(1 for o in oocytes if (o.disposition or {}).get("status") == "Frozen")

    fert_rate = round((fert_2pn / mii_count * 100), 1) if mii_count > 0 else 0.0
    cleavage_rate = round((cleaved_d2 / fert_2pn * 100), 1) if fert_2pn > 0 else 0.0
    blast_rate = round((blast_d5 / d3_count * 100), 1) if d3_count > 0 else 0.0
    utilization_rate = round(((transferred + frozen) / fert_2pn * 100), 1) if fert_2pn > 0 else 0.0

    return {
        "cycle_id": cycle_id,
        "counts": {
            "total_oocytes": total_oocytes,
            "mii_count": mii_count,
            "fert_2pn": fert_2pn,
            "cleaved_d2": cleaved_d2,
            "d3_count": d3_count,
            "blast_d5": blast_d5,
            "transferred": transferred,
            "frozen": frozen,
        },
        "kpis": {
            "fertilization_rate_pct": fert_rate,
            "cleavage_rate_pct": cleavage_rate,
            "blastocyst_rate_pct": blast_rate,
            "utilization_rate_pct": utilization_rate,
        }
    }
