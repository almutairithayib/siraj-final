import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class InvestmentOpportunityResponse(BaseModel):
    id: str
    name: str
    product_type: str  # fund, sukuk, ipo
    risk_level: str    # low, medium, high
    expected_return: float
    min_investment: float
    description: str


class InvestmentRequestCreate(BaseModel):
    product_name: str
    product_type: str
    amount: float = Field(..., gt=0)
    risk_level: str
    expected_return: Optional[float] = None


class InvestmentRequestResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    product_name: str
    product_type: str
    amount: float
    risk_level: str
    expected_return: Optional[float] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class InvestmentRecommendation(BaseModel):
    opportunity_id: str
    name: str
    product_type: str
    risk_level: str
    expected_return: float
    min_investment: float
    description: str
    suitability_reason: str
