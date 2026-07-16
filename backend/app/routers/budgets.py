import uuid
from datetime import date
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, func

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.budget import Budget
from backend.app.models.transaction import Transaction
from backend.app.schemas.budget import BudgetCreate, BudgetResponse, BudgetAnalysisResponse
from backend.app.services.auth_service import get_current_user

router = APIRouter(prefix="/budgets", tags=["Budgets"])

@router.get("/", response_model=List[BudgetResponse])
async def list_budgets(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Budget).where(Budget.user_id == current_user.id))
    return result.scalars().all()

@router.post("/", response_model=BudgetResponse)
async def create_or_update_budget(
    budget_in: BudgetCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Check if budget already exists for this category
    result = await db.execute(
        select(Budget).where(
            and_(Budget.user_id == current_user.id, Budget.category == budget_in.category)
        )
    )
    existing_budget = result.scalar_one_or_none()
    
    if existing_budget:
        existing_budget.limit_amount = budget_in.limit_amount
        existing_budget.period = budget_in.period
        await db.commit()
        await db.refresh(existing_budget)
        return existing_budget
    else:
        new_budget = Budget(
            user_id=current_user.id,
            category=budget_in.category,
            limit_amount=budget_in.limit_amount,
            period=budget_in.period
        )
        db.add(new_budget)
        await db.commit()
        await db.refresh(new_budget)
        return new_budget

@router.get("/analysis", response_model=List[BudgetAnalysisResponse])
async def budget_analysis(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Fetch all budgets
    budgets_result = await db.execute(select(Budget).where(Budget.user_id == current_user.id))
    budgets = budgets_result.scalars().all()
    
    # Calculate spending for the current month
    today = date.today()
    start_of_month = date(today.year, today.month, 1)
    
    analysis = []
    for budget in budgets:
        # Sum transactions in this category for the current month
        txn_result = await db.execute(
            select(func.sum(Transaction.amount)).where(
                and_(
                    Transaction.user_id == current_user.id,
                    Transaction.category == budget.category,
                    Transaction.type == "expense",
                    Transaction.transaction_date >= start_of_month
                )
            )
        )
        spent = txn_result.scalar() or 0.0
        spent = float(spent)
        
        remaining = float(budget.limit_amount) - spent
        percentage = (spent / float(budget.limit_amount)) * 100 if budget.limit_amount > 0 else 0
        
        analysis.append({
            "category": budget.category,
            "limit_amount": float(budget.limit_amount),
            "spent_amount": spent,
            "remaining_amount": remaining,
            "percentage_spent": round(percentage, 2),
            "period": budget.period
        })
        
    return analysis
