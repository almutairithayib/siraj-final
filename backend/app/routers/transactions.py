import uuid
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.transaction import Transaction
from backend.app.schemas.transaction import TransactionCreate, TransactionResponse
from backend.app.services.auth_service import get_current_user
from backend.app.services.alert_engine import check_budget_breach, check_spending_spike

router = APIRouter(prefix="/transactions", tags=["Transactions"])

@router.get("/", response_model=List[TransactionResponse])
async def list_transactions(
    start_date: Optional[date] = Query(None, description="Start date for filter"),
    end_date: Optional[date] = Query(None, description="End date for filter"),
    category: Optional[str] = Query(None, description="Category filter"),
    transaction_type: Optional[str] = Query(None, alias="type", description="Type: income or expense"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Transaction).where(Transaction.user_id == current_user.id)
    
    filters = []
    if start_date:
        filters.append(Transaction.transaction_date >= start_date)
    if end_date:
        filters.append(Transaction.transaction_date <= end_date)
    if category:
        filters.append(Transaction.category == category)
    if transaction_type:
        filters.append(Transaction.type == transaction_type)
        
    if filters:
        query = query.where(and_(*filters))
        
    # Order by transaction date descending
    query = query.order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc())
    
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    transaction_in: TransactionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    new_txn = Transaction(
        user_id=current_user.id,
        amount=transaction_in.amount,
        category=transaction_in.category,
        type=transaction_in.type,
        description=transaction_in.description,
        transaction_date=transaction_in.transaction_date
    )
    db.add(new_txn)
    await db.commit()
    await db.refresh(new_txn)
    
    # Check for alerts in the background / inline
    try:
        await check_budget_breach(current_user.id, new_txn.category, db)
        await check_spending_spike(current_user.id, new_txn, db)
    except Exception as e:
        print(f"Error checking alerts: {e}")
        
    return new_txn

@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    transaction_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Transaction).where(
            and_(Transaction.id == transaction_id, Transaction.user_id == current_user.id)
        )
    )
    txn = result.scalar_one_or_none()
    if not txn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="المعاملة غير موجودة"  # "Transaction not found"
        )
    
    await db.delete(txn)
    await db.commit()
    return None
