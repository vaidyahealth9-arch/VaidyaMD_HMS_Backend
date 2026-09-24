from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.modules.templates.model import ClinicalTemplate
from app.modules.templates.schemas import ClinicalTemplateCreate, ClinicalTemplateUpdate

class ClinicalTemplateService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_templates(self, plugin_id: str = None):
        query = select(ClinicalTemplate).where(ClinicalTemplate.is_active == True)
        if plugin_id:
            query = query.where(ClinicalTemplate.plugin_id == plugin_id)
        
        result = await self.db.execute(query.order_by(ClinicalTemplate.title.asc()))
        return result.scalars().all()

    async def get_template_by_type(self, record_type: str):
        query = select(ClinicalTemplate).where(
            ClinicalTemplate.record_type == record_type,
            ClinicalTemplate.is_active == True
        )
        result = await self.db.execute(query)
        template = result.scalars().first()
        if not template:
            raise ValueError(f"Template with record_type '{record_type}' not found")
        return template

    async def create_template(self, data: ClinicalTemplateCreate, tenant_id: UUID = None, branch_id: UUID = None):
        query = select(ClinicalTemplate).where(ClinicalTemplate.record_type == data.record_type)
        result = await self.db.execute(query)
        if result.scalars().first():
            raise ValueError(f"Template with record_type '{data.record_type}' already exists")

        resolved_tenant_id = tenant_id
        if not resolved_tenant_id:
            from app.core.models.hospital import Hospital
            h_res = await self.db.execute(select(Hospital.id).limit(1))
            resolved_tenant_id = h_res.scalar_one_or_none()

        template = ClinicalTemplate(
            tenant_id=resolved_tenant_id,
            branch_id=branch_id,
            plugin_id=data.plugin_id,
            record_type=data.record_type,
            title=data.title,
            description=data.description,
            schema_json=data.schema_json,
            created_by=data.created_by
        )
        self.db.add(template)
        await self.db.flush()
        await self.db.refresh(template)
        return template

    async def update_template(self, template_id: UUID, data: ClinicalTemplateUpdate):
        template = await self.db.get(ClinicalTemplate, template_id)
        if not template:
            raise ValueError("Template not found")

        if data.title is not None:
            template.title = data.title
        if data.description is not None:
            template.description = data.description
        if data.schema_json is not None:
            template.schema_json = data.schema_json
        if data.is_active is not None:
            template.is_active = data.is_active

        await self.db.flush()
        await self.db.refresh(template)
        return template

    async def delete_template(self, template_id: UUID):
        template = await self.db.get(ClinicalTemplate, template_id)
        if not template:
            raise ValueError("Template not found")
        template.is_active = False
        await self.db.flush()
        return {"status": "ok", "message": "Template deactivated"}
