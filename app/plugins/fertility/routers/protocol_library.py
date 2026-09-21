"""
VaidyaMD HMS — Protocol Library Master Router
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from uuid import UUID
from pydantic import BaseModel
from typing import Optional, Any, List, Union

from app.core.database import get_db
from app.core.models import ProtocolTemplate, ProtocolDrugRule, Hospital, User
from app.plugins.fertility.rules_engine import generate_medication_calendar

router = APIRouter(prefix="/protocols", tags=["Fertility — Protocol Library"])


class RuleCreate(BaseModel):
    drug_name: str
    dose: str
    route: str = "SC"
    frequency: str = "OD"
    sentinel_anchor: str = "stim_start"
    day_start_offset: int = 1
    day_end_offset: int = 10
    instructions: Optional[str] = None
    sort_order: int = 0


class ProtocolCreate(BaseModel):
    name: str
    description: Optional[str] = None
    category: str = "stimulation"
    rules: Optional[List[RuleCreate]] = []
    created_by: UUID


class CalendarPreviewRequest(BaseModel):
    protocol_template_id: Optional[Union[UUID, str]] = None
    custom_rules: Optional[List[RuleCreate]] = None
    sentinel_dates: dict[str, Any]


@router.get("/")
async def list_protocols(category: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """List all protocol templates with their drug rules."""
    query = select(ProtocolTemplate).where(ProtocolTemplate.is_active == True).order_by(ProtocolTemplate.name)
    if category:
        query = query.where(ProtocolTemplate.category == category)

    result = await db.execute(query)
    protocols = result.scalars().all()

    response = []
    for p in protocols:
        rules_res = await db.execute(
            select(ProtocolDrugRule)
            .where(ProtocolDrugRule.protocol_template_id == p.id)
            .order_by(ProtocolDrugRule.sort_order)
        )
        rules = rules_res.scalars().all()
        response.append({
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "category": p.category,
            "is_active": p.is_active,
            "rules": [
                {
                    "id": r.id,
                    "drug_name": r.drug_name,
                    "dose": r.dose,
                    "route": r.route,
                    "frequency": r.frequency,
                    "sentinel_anchor": r.sentinel_anchor,
                    "day_start_offset": r.day_start_offset,
                    "day_end_offset": r.day_end_offset,
                    "instructions": r.instructions,
                    "sort_order": r.sort_order,
                }
                for r in rules
            ]
        })
    return response


@router.post("/", status_code=201)
async def create_protocol(payload: ProtocolCreate, db: AsyncSession = Depends(get_db)):
    """Create a new protocol template with rules."""
    result = await db.execute(select(Hospital).limit(1))
    hospital = result.scalar_one_or_none()
    if not hospital:
        raise HTTPException(status_code=500, detail="No hospital configured")

    template = ProtocolTemplate(
        hospital_id=hospital.id,
        name=payload.name,
        description=payload.description,
        category=payload.category,
        is_active=True,
        created_by=payload.created_by,
    )
    db.add(template)
    await db.flush()

    for idx, r in enumerate(payload.rules or []):
        rule = ProtocolDrugRule(
            protocol_template_id=template.id,
            drug_name=r.drug_name,
            dose=r.dose,
            route=r.route,
            frequency=r.frequency,
            sentinel_anchor=r.sentinel_anchor,
            day_start_offset=r.day_start_offset,
            day_end_offset=r.day_end_offset,
            instructions=r.instructions,
            sort_order=r.sort_order or idx,
        )
        db.add(rule)

    await db.flush()
    await db.refresh(template)
    return {"id": template.id, "name": template.name, "message": "Protocol created successfully"}


@router.post("/preview-calendar")
async def preview_calendar(payload: CalendarPreviewRequest, db: AsyncSession = Depends(get_db)):
    """Dry-run calendar preview given protocol rules and sentinel dates."""
    rules_data = []
    if payload.protocol_template_id:
        proto_id = None
        try:
            proto_id = UUID(str(payload.protocol_template_id))
        except (ValueError, TypeError):
            proto_q = await db.execute(
                select(ProtocolTemplate)
                .where(ProtocolTemplate.name.ilike(f"%{payload.protocol_template_id}%"))
                .limit(1)
            )
            found_p = proto_q.scalar_one_or_none()
            if found_p:
                proto_id = found_p.id

        if proto_id:
            result = await db.execute(
                select(ProtocolDrugRule)
                .where(ProtocolDrugRule.protocol_template_id == proto_id)
                .order_by(ProtocolDrugRule.sort_order)
            )
            rules = result.scalars().all()
            for r in rules:
                rules_data.append({
                    "drug_name": r.drug_name,
                    "dose": r.dose,
                    "route": r.route,
                    "frequency": r.frequency,
                    "sentinel_anchor": r.sentinel_anchor,
                    "day_start_offset": r.day_start_offset,
                    "day_end_offset": r.day_end_offset,
                    "instructions": r.instructions,
                })
    elif payload.custom_rules:
        rules_data = [r.dict() for r in payload.custom_rules]

    return generate_medication_calendar(
        rules=rules_data,
        sentinel_dates=payload.sentinel_dates or {},
        total_days=21,
    )


class ProtocolUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None
    rules: Optional[List[RuleCreate]] = None


@router.put("/{protocol_id}")
async def update_protocol(protocol_id: UUID, payload: ProtocolUpdate, db: AsyncSession = Depends(get_db)):
    template = await db.get(ProtocolTemplate, protocol_id)
    if not template:
        raise HTTPException(status_code=404, detail="Protocol not found")
    if payload.name is not None:
        template.name = payload.name
    if payload.description is not None:
        template.description = payload.description
    if payload.category is not None:
        template.category = payload.category
    if payload.is_active is not None:
        template.is_active = payload.is_active

    if payload.rules is not None:
        existing_rules = (await db.execute(
            select(ProtocolDrugRule).where(ProtocolDrugRule.protocol_template_id == protocol_id)
        )).scalars().all()
        for er in existing_rules:
            await db.delete(er)

        for idx, r in enumerate(payload.rules):
            rule = ProtocolDrugRule(
                protocol_template_id=template.id,
                drug_name=r.drug_name,
                dose=r.dose,
                route=r.route,
                frequency=r.frequency,
                sentinel_anchor=r.sentinel_anchor,
                day_start_offset=r.day_start_offset,
                day_end_offset=r.day_end_offset,
                instructions=r.instructions,
                sort_order=r.sort_order or idx,
            )
            db.add(rule)

    await db.commit()
    await db.refresh(template)
    return {"id": template.id, "name": template.name, "message": "Protocol updated successfully"}


@router.delete("/{protocol_id}")
async def delete_protocol(protocol_id: UUID, db: AsyncSession = Depends(get_db)):
    template = await db.get(ProtocolTemplate, protocol_id)
    if not template:
        raise HTTPException(status_code=404, detail="Protocol not found")
    template.is_active = False
    await db.commit()
    return {"status": "success", "message": "Protocol deleted successfully"}


# Alias router for frontend /protocol-library/templates compatibility
templates_router = APIRouter(prefix="/protocol-library/templates", tags=["Fertility — Protocol Library (Alias)"])
templates_router.add_api_route("", list_protocols, methods=["GET"])
templates_router.add_api_route("/", list_protocols, methods=["GET"])
templates_router.add_api_route("", create_protocol, methods=["POST"], status_code=201)
templates_router.add_api_route("/", create_protocol, methods=["POST"], status_code=201)
templates_router.add_api_route("/{protocol_id}", update_protocol, methods=["PUT"])
templates_router.add_api_route("/{protocol_id}", delete_protocol, methods=["DELETE"])
templates_router.add_api_route("/preview-calendar", preview_calendar, methods=["POST"])

