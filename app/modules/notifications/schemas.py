from pydantic import BaseModel
from typing import Optional, Any
from uuid import UUID
from datetime import datetime

class NotificationResponse(BaseModel):
    id: UUID
    type: str
    title: str
    message: str
    is_read: bool
    metadata: dict[str, Any]
    created_at: datetime
    
    class Config:
        from_attributes = True
