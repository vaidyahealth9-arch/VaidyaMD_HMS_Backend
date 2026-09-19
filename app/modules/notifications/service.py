from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from uuid import UUID
from datetime import datetime

from app.modules.notifications.model import Notification

class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_notifications(self, user_id: UUID, unread_only: bool = False):
        query = select(Notification).where(Notification.recipient_id == user_id)
        if unread_only:
            query = query.where(Notification.is_read == False)
        query = query.order_by(Notification.created_at.desc()).limit(50)

        result = await self.db.execute(query)
        notifications = result.scalars().all()

        return [
            {
                "id": str(n.id),
                "type": n.type.value if hasattr(n.type, 'value') else str(n.type),
                "title": n.title,
                "message": n.message,
                "is_read": n.is_read,
                "metadata": n.metadata_,
                "created_at": n.created_at.isoformat(),
            }
            for n in notifications
        ]

    async def mark_as_read(self, notification_id: UUID):
        notification = await self.db.get(Notification, notification_id)
        if notification:
            notification.is_read = True
            await self.db.flush()
        return {"status": "ok"}

    async def mark_all_read(self, user_id: UUID):
        await self.db.execute(
            update(Notification)
            .where(Notification.recipient_id == user_id, Notification.is_read == False)
            .values(is_read=True)
        )
        return {"status": "ok"}
