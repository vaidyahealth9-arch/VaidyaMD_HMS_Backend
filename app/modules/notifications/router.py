from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.database import get_db
from app.modules.notifications.service import NotificationService
from app.modules.notifications.schemas import NotificationResponse

router = APIRouter(prefix="/notifications", tags=["Notifications (Clean Architecture)"])

def get_notification_service(db: AsyncSession = Depends(get_db)) -> NotificationService:
    return NotificationService(db)

@router.get("/")
async def get_notifications(
    user_id: UUID = Query(...),
    unread_only: bool = Query(False),
    service: NotificationService = Depends(get_notification_service),
):
    return await service.get_notifications(user_id, unread_only)

@router.patch("/{notification_id}/read")
async def mark_as_read(
    notification_id: UUID,
    service: NotificationService = Depends(get_notification_service),
):
    return await service.mark_as_read(notification_id)

@router.post("/mark-all-read")
async def mark_all_read(
    user_id: UUID = Query(...),
    service: NotificationService = Depends(get_notification_service),
):
    return await service.mark_all_read(user_id)
