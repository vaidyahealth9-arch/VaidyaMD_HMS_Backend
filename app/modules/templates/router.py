from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional

from app.core.models import User
from app.core.dependencies import get_current_user
from app.core.database import get_db
from app.modules.templates.service import ClinicalTemplateService
from app.modules.templates.schemas import ClinicalTemplateCreate, ClinicalTemplateUpdate, ClinicalTemplateResponse

router = APIRouter(prefix="/templates", tags=["Clinical Templates (Clean Architecture)"])

def get_template_service(db: AsyncSession = Depends(get_db)) -> ClinicalTemplateService:
    return ClinicalTemplateService(db)

@router.get("/", response_model=list[ClinicalTemplateResponse])
async def get_templates(
    plugin_id: Optional[str] = None,
    service: ClinicalTemplateService = Depends(get_template_service)
):
    return await service.get_templates(plugin_id)

@router.get("/{record_type}", response_model=ClinicalTemplateResponse)
async def get_template_by_type(
    record_type: str,
    service: ClinicalTemplateService = Depends(get_template_service)
):
    try:
        return await service.get_template_by_type(record_type)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.post("/", response_model=ClinicalTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    data: ClinicalTemplateCreate,
    current_user: User = Depends(get_current_user),
    service: ClinicalTemplateService = Depends(get_template_service)
):
    try:
        if not data.created_by:
            data.created_by = current_user.id
        return await service.create_template(data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.put("/{template_id}", response_model=ClinicalTemplateResponse)
async def update_template(
    template_id: UUID,
    data: ClinicalTemplateUpdate,
    service: ClinicalTemplateService = Depends(get_template_service)
):
    try:
        return await service.update_template(template_id, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.delete("/{template_id}")
async def delete_template(
    template_id: UUID,
    service: ClinicalTemplateService = Depends(get_template_service)
):
    try:
        return await service.delete_template(template_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
