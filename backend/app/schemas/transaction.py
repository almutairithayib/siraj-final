import uuid
from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, Field


class TransactionCreate(BaseModel):
    amount: float = Field(..., gt=0)
    category: str
    type: Literal["income", "expense"]
    description: str | None = None
    transaction_date: date = Field(default_factory=date.today)


class TransactionResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    amount: float
    category: str
    type: str
    description: str | None = None
    transaction_date: date
    created_at: datetime

    class Config:
        from_attributes = True
