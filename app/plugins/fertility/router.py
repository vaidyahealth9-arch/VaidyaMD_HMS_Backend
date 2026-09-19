"""
VaidyaMD HMS — Fertility Plugin Main Router
Aggregates Treatment Cycles, Protocol Library, Embryology, Andrology, Cryobank, and Analytics.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from pydantic import BaseModel
from typing import Optional, Any
from app.core.database import get_db
from app.core.models import ClinicalRecord, Patient, Invoice
from app.core.dependencies import get_current_user

# Import fertility sub-routers
from app.plugins.fertility.routers.treatment_cycles import router as treatment_cycles_router
from app.plugins.fertility.routers.protocol_library import router as protocol_library_router, templates_router as protocol_templates_router
from app.plugins.fertility.routers.embryology import router as embryology_router
from app.plugins.fertility.routers.andrology import router as andrology_router
from app.plugins.fertility.routers.cryo import router as cryo_router
from app.plugins.fertility.routers.analytics import router as analytics_router
from app.plugins.fertility.routers.qc import router as qc_router

from app.plugins.fertility.schemas import (
    FEMALE_HISTORY_SCHEMA,
    MALE_HISTORY_SCHEMA,
    FOLLICULAR_SCAN_SCHEMA,
    PELVIC_ORGAN_USG_SCHEMA,
    SONOHYSTEROGRAM_SCHEMA,
    ENDOMETRIAL_ASSESSMENT_SCHEMA,
    EARLY_PREGNANCY_SCAN_SCHEMA,
    CASA_SEMEN_ANALYSIS_SCHEMA,
    SPERM_DFI_SCHEMA,
    SPERM_PREPARATION_SCHEMA,
    SEMEN_FREEZING_SCHEMA,
    SURGICAL_SPERM_RETRIEVAL_SCHEMA,
    IUI_PROCEDURE_SCHEMA,
    RX_GROUP_SCHEMA,
    FERTILITY_CONSULTATION_SCHEMA,
    CYCLE_WORKFLOW_CONFIGS,
    CHECKLIST_TEMPLATES,
    DIAGNOSTICS_SCAN_TAGS,
)

router = APIRouter(prefix="/fertility", tags=["Fertility Plugin"], dependencies=[Depends(get_current_user)])


# Mount Sub-Routers
router.include_router(treatment_cycles_router)
router.include_router(protocol_library_router)
router.include_router(protocol_templates_router)
router.include_router(embryology_router)
router.include_router(andrology_router)
router.include_router(cryo_router)
router.include_router(analytics_router)
router.include_router(qc_router)




@router.get("/schemas")
async def get_all_schemas():
    """Return all Fertility plugin form schemas."""
    return {
        "plugin_id": "fertility",
        "schemas": {
            "female_history": FEMALE_HISTORY_SCHEMA,
            "male_history": MALE_HISTORY_SCHEMA,
            "follicular_scan": FOLLICULAR_SCAN_SCHEMA,
            "pelvic_organ_usg": PELVIC_ORGAN_USG_SCHEMA,
            "sonohysterogram": SONOHYSTEROGRAM_SCHEMA,
            "endometrial_assessment": ENDOMETRIAL_ASSESSMENT_SCHEMA,
            "early_pregnancy_scan": EARLY_PREGNANCY_SCAN_SCHEMA,
            "casa_semen_analysis": CASA_SEMEN_ANALYSIS_SCHEMA,
            "sperm_dfi": SPERM_DFI_SCHEMA,
            "sperm_preparation": SPERM_PREPARATION_SCHEMA,
            "semen_freezing": SEMEN_FREEZING_SCHEMA,
            "surgical_sperm_retrieval": SURGICAL_SPERM_RETRIEVAL_SCHEMA,
            "iui_procedure": IUI_PROCEDURE_SCHEMA,
            "rx_group": RX_GROUP_SCHEMA,
            "fertility_consultation": FERTILITY_CONSULTATION_SCHEMA,
        },
        "cycle_workflows": CYCLE_WORKFLOW_CONFIGS,
        "checklist_templates": CHECKLIST_TEMPLATES,
        "scan_tags": DIAGNOSTICS_SCAN_TAGS,
    }


@router.get("/schemas/{record_type}")
async def get_schema(record_type: str):
    """Return a specific Fertility plugin schema by record type."""
    schemas = {
        "female_history": FEMALE_HISTORY_SCHEMA,
        "male_history": MALE_HISTORY_SCHEMA,
        "follicular_scan": FOLLICULAR_SCAN_SCHEMA,
        "pelvic_organ_usg": PELVIC_ORGAN_USG_SCHEMA,
        "sonohysterogram": SONOHYSTEROGRAM_SCHEMA,
        "endometrial_assessment": ENDOMETRIAL_ASSESSMENT_SCHEMA,
        "early_pregnancy_scan": EARLY_PREGNANCY_SCAN_SCHEMA,
        "casa_semen_analysis": CASA_SEMEN_ANALYSIS_SCHEMA,
        "sperm_dfi": SPERM_DFI_SCHEMA,
        "sperm_preparation": SPERM_PREPARATION_SCHEMA,
        "semen_freezing": SEMEN_FREEZING_SCHEMA,
        "surgical_sperm_retrieval": SURGICAL_SPERM_RETRIEVAL_SCHEMA,
        "iui_procedure": IUI_PROCEDURE_SCHEMA,
        "rx_group": RX_GROUP_SCHEMA,
        "fertility_consultation": FERTILITY_CONSULTATION_SCHEMA,
    }
    if record_type not in schemas:
        raise HTTPException(status_code=404, detail=f"Schema '{record_type}' not found")
    return schemas[record_type]



async def get_couple_dues(patient_id: UUID, db: AsyncSession = Depends(get_db)):
    """Calculate outstanding dues for a patient and their linked partner."""
    patient = await db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    async def calculate_dues(pid: UUID) -> float:
        query = select(Invoice).where(
            Invoice.patient_id == pid,
            Invoice.status != "paid"
        )
        res = await db.execute(query)
        invoices = res.scalars().all()
        return sum(float(inv.total_amount - inv.paid_amount) for inv in invoices)

    patient_due = await calculate_dues(patient.id)
    partner_due = 0.0
    partner_name = None

    if patient.partner_id:
        partner = await db.get(Patient, patient.partner_id)
        if partner:
            partner_due = await calculate_dues(partner.id)
            partner_name = partner.name

    return {
        "patient_name": patient.name,
        "patient_due": patient_due,
        "partner_name": partner_name,
        "partner_due": partner_due,
        "total_due": patient_due + partner_due,
    }
