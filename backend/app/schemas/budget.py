import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class BudgetBase(BaseModel):
    category: str
    limit_amount: float = Field(..., gt=0)
    period: str = "monthly"

class BudgetCreate(BudgetBase):
    pass

class BudgetResponse(BudgetBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True

class BudgetAnalysisResponse(BaseModel):
    category: str
    limit_amount: float
    spent_amount: float
    remaining_amount: float
    percentage_spent: float
    period: str
