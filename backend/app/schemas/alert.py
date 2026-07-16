import uuid
from datetime import datetime
from pydantic import BaseModel, Field

class AlertBase(BaseModel):
    alert_type: str  # budget_breach, spending_spike, bill_due, goal_milestone
    category: str | None = None
    threshold_amount: float | None = None
    message: str
    is_active: bool = True

class AlertCreate(AlertBase):
    pass

class AlertResponse(AlertBase):
    id: uuid.UUID
    user_id: uuid.UUID
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True

class AlertUnreadCountResponse(BaseModel):
    unread_count: int
