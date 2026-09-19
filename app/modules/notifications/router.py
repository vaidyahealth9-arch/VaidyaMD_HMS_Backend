from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional

from app.core.database import get_db
from app.core.models import User
from app.core.dependencies import get_current_user
from app.modules.notifications.service import NotificationService
from app.modules.notifications.schemas import NotificationResponse

router = APIRouter(prefix="/notifications", tags=["Notifications (Clean Architecture)"], dependencies=[Depends(get_current_user)])

def get_notification_service(db: AsyncSession = Depends(get_db)) -> NotificationService:
    return NotificationService(db)

@router.get("/")
async def get_notifications(
    user_id: Optional[UUID] = Query(None),
    unread_only: bool = Query(False),
    current_user: User = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
):
    target_id = user_id or current_user.id
    return await service.get_notifications(target_id, unread_only)

@router.patch("/{notification_id}/read")
@router.post("/{notification_id}/read")
async def mark_as_read(
    notification_id: UUID,
    service: NotificationService = Depends(get_notification_service),
):
    return await service.mark_as_read(notification_id)

@router.post("/mark-all-read")
@router.post("/mark-all-read/{user_id}")
async def mark_all_read(
    user_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
):
    target_id = user_id or current_user.id
    return await service.mark_all_read(target_id)
