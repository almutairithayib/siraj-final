import uuid
from datetime import date
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.savings import SavingsGoal
from backend.app.schemas.savings import SavingsGoalCreate, SavingsGoalUpdate, SavingsGoalResponse, SavingsGoalProgressResponse
from backend.app.services.auth_service import get_current_user
from backend.app.services.alert_engine import check_goal_milestones

router = APIRouter(prefix="/savings", tags=["Savings"])

@router.get("/plans", response_model=List[SavingsGoalResponse])
async def list_savings_plans(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(SavingsGoal).where(SavingsGoal.user_id == current_user.id))
    return result.scalars().all()

@router.post("/plans", response_model=SavingsGoalResponse, status_code=status.HTTP_201_CREATED)
async def create_savings_plan(
    plan_in: SavingsGoalCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    new_plan = SavingsGoal(
        user_id=current_user.id,
        goal_name=plan_in.goal_name,
        target_amount=plan_in.target_amount,
        current_amount=plan_in.current_amount,
        target_date=plan_in.target_date,
        monthly_contribution=plan_in.monthly_contribution,
        status=plan_in.status
    )
    db.add(new_plan)
    await db.commit()
    await db.refresh(new_plan)
    try:
        await check_goal_milestones(current_user.id, new_plan.id, db)
    except Exception as e:
        print(f"Error checking milestones: {e}")
    return new_plan

@router.put("/plans/{plan_id}", response_model=SavingsGoalResponse)
async def update_savings_plan(
    plan_id: uuid.UUID,
    plan_update: SavingsGoalUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(SavingsGoal).where(
            and_(SavingsGoal.id == plan_id, SavingsGoal.user_id == current_user.id)
        )
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="خطة الادخار غير موجودة"  # "Savings plan not found"
        )
    
    if plan_update.current_amount is not None:
        plan.current_amount = plan_update.current_amount
    if plan_update.status is not None:
        plan.status = plan_update.status
    if plan_update.monthly_contribution is not None:
        plan.monthly_contribution = plan_update.monthly_contribution
        
    await db.commit()
    await db.refresh(plan)
    try:
        await check_goal_milestones(current_user.id, plan.id, db)
    except Exception as e:
        print(f"Error checking milestones: {e}")
    return plan

@router.get("/plans/{plan_id}/progress", response_model=SavingsGoalProgressResponse)
async def get_savings_progress(
    plan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(SavingsGoal).where(
            and_(SavingsGoal.id == plan_id, SavingsGoal.user_id == current_user.id)
        )
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="خطة الادخار غير موجودة"
        )
        
    target = float(plan.target_amount)
    current = float(plan.current_amount)
    remaining = max(0.0, target - current)
    percentage = (current / target) * 100 if target > 0 else 0
    
    # Calculate months remaining
    today = date.today()
    target_dt = plan.target_date
    months_diff = (target_dt.year - today.year) * 12 + (target_dt.month - today.month)
    months_remaining = max(0, months_diff)
    
    # Check if they are on track
    # On track if monthly_contribution * months_remaining >= remaining
    on_track = True
    if months_remaining > 0:
        required_monthly = remaining / months_remaining
        if float(plan.monthly_contribution) < required_monthly * 0.9:  # 10% buffer
            on_track = False
            
    return {
        "id": plan.id,
        "goal_name": plan.goal_name,
        "target_amount": target,
        "current_amount": current,
        "percentage_complete": round(percentage, 2),
        "remaining_amount": remaining,
        "months_remaining": months_remaining,
        "on_track": on_track
    }
