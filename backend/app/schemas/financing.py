import uuid
from datetime import datetime
from pydantic import BaseModel, Field

class FinancingProductResponse(BaseModel):
    id: str
    name: str
    product_type: str  # personal, auto, home, education, business
    profit_rate: float  # e.g. 2.99 %
    min_amount: float
    max_amount: float
    min_term_months: int
    max_term_months: int
    description: str

class FinancingRequestCreate(BaseModel):
    product_type: str
    amount: float = Field(..., gt=0)
    term_months: int = Field(..., gt=0)
    notes: str | None = None

class FinancingRequestResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    product_type: str
    amount: float
    term_months: int
    status: str
    notes: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True
