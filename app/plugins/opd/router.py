"""
VaidyaMD HMS — General OPD Plugin Router with Ambient AI Scribe & Smart Order Sets
"""

import asyncio
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from pydantic import BaseModel
from typing import Optional, Any, List
from app.core.database import get_db
from app.core.models import ClinicalRecord, Patient, User
from app.plugins.opd.schemas import OPD_CONSULTATION_SCHEMA

router = APIRouter(prefix="/opd", tags=["OPD Plugin"])

@router.get("/schemas")
async def get_opd_schemas():
    """Return all OPD plugin form schemas."""
    return {
        "plugin_id": "opd",
        "schemas": {
            "opd_consultation": OPD_CONSULTATION_SCHEMA,
        }
    }

@router.get("/schemas/{record_type}")
async def get_opd_schema(record_type: str):
    """Return a specific OPD plugin schema by record type."""
    schemas = {
        "opd_consultation": OPD_CONSULTATION_SCHEMA,
    }
    if record_type not in schemas:
        raise HTTPException(status_code=404, detail=f"Schema '{record_type}' not found")
    return schemas[record_type]
