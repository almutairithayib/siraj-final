import uuid
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


class SavingsGoalCreate(BaseModel):
    goal_name: str
    target_amount: float = Field(..., gt=0)
    current_amount: float = 0.0
    target_date: date
    monthly_contribution: float = 0.0
    status: str = "active"


class SavingsGoalUpdate(BaseModel):
    current_amount: Optional[float] = None
    monthly_contribution: Optional[float] = None
    status: Optional[str] = None


class SavingsGoalResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    goal_name: str
    target_amount: float
    current_amount: float
    target_date: date
    monthly_contribution: float
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class SavingsGoalProgressResponse(BaseModel):
    goal_id: uuid.UUID
    goal_name: str
    target_amount: float
    current_amount: float
    remaining_amount: float
    percentage_complete: float
    months_remaining: int
    is_on_track: bool
