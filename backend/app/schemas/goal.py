import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class GoalTemplateResponse(BaseModel):
    id: str
    goal_type: str
    title: str
    default_target_amount: float
    description: str
    suggested_timeline_months: int


class FinancialGoalCreate(BaseModel):
    goal_type: str
    title: str
    target_amount: float = Field(..., gt=0)
    saved_amount: float = 0.0
    target_date: date
    plan_details: Dict[str, Any] = Field(default_factory=dict)
    status: str = "active"


class FinancialGoalUpdate(BaseModel):
    saved_amount: Optional[float] = None
    status: Optional[str] = None
    plan_details: Optional[Dict[str, Any]] = None


class FinancialGoalResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    goal_type: str
    title: str
    target_amount: float
    saved_amount: float
    target_date: date
    plan_details: Dict[str, Any]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
