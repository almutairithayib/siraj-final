"""
Financial summary and category breakdown helpers used by the dashboard router.
"""
import uuid
from datetime import date, timedelta
from typing import Any, Dict

from sqlalchemy import and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.app.models.transaction import Transaction
from backend.app.models.savings import SavingsGoal


async def get_financial_summary(user_id: uuid.UUID, db: AsyncSession) -> Dict[str, Any]:
    """Return total income, expense, savings and savings rate for the current month."""
    today = date.today()
    start_of_month = date(today.year, today.month, 1)

    income_res = await db.execute(
        select(func.sum(Transaction.amount)).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.type == "income",
                Transaction.transaction_date >= start_of_month,
            )
        )
    )
    expense_res = await db.execute(
        select(func.sum(Transaction.amount)).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.type == "expense",
                Transaction.transaction_date >= start_of_month,
            )
        )
    )

    total_income = float(income_res.scalar() or 0.0)
    total_expense = float(expense_res.scalar() or 0.0)
    total_savings = max(0.0, total_income - total_expense)
    savings_rate = (total_savings / total_income * 100) if total_income > 0 else 0.0

    return {
        "total_income": total_income,
        "total_expense": total_expense,
        "total_savings": total_savings,
        "savings_rate": round(savings_rate, 2),
    }


async def get_category_breakdown(user_id: uuid.UUID, db: AsyncSession) -> list:
    """Return spending grouped by category for the current month."""
    today = date.today()
    start_of_month = date(today.year, today.month, 1)

    result = await db.execute(
        select(Transaction.category, func.sum(Transaction.amount).label("total"))
        .where(
            and_(
                Transaction.user_id == user_id,
                Transaction.type == "expense",
                Transaction.transaction_date >= start_of_month,
            )
        )
        .group_by(Transaction.category)
        .order_by(func.sum(Transaction.amount).desc())
    )
    rows = result.all()

    grand_total = sum(float(r.total) for r in rows) or 1.0
    return [
        {
            "category": r.category,
            "amount": float(r.total),
            "percentage": round(float(r.total) / grand_total * 100, 2),
        }
        for r in rows
    ]


async def get_recurring_charges(user_id: uuid.UUID, db: AsyncSession) -> list:
    """Detect likely recurring charges by finding transactions with the same description
    appearing more than once in the last 60 days."""
    from sqlalchemy import text  # noqa: PLC0415

    sixty_days_ago = date.today() - timedelta(days=60)

    result = await db.execute(
        select(
            Transaction.description,
            Transaction.category,
            func.count(Transaction.id).label("occurrences"),
            func.avg(Transaction.amount).label("avg_amount"),
        )
        .where(
            and_(
                Transaction.user_id == user_id,
                Transaction.type == "expense",
                Transaction.transaction_date >= sixty_days_ago,
                Transaction.description.isnot(None),
            )
        )
        .group_by(Transaction.description, Transaction.category)
        .having(func.count(Transaction.id) > 1)
        .order_by(func.avg(Transaction.amount).desc())
    )
    rows = result.all()
    return [
        {
            "description": r.description,
            "category": r.category,
            "occurrences": r.occurrences,
            "avg_amount": round(float(r.avg_amount), 2),
        }
        for r in rows
    ]


async def get_budget_vs_actual(user_id: uuid.UUID, db: AsyncSession) -> list:
    """Return budget vs actual spending per category for the current month."""
    from backend.app.models.budget import Budget  # noqa: PLC0415

    today = date.today()
    start_of_month = date(today.year, today.month, 1)

    budgets_res = await db.execute(select(Budget).where(Budget.user_id == user_id))
    budgets = budgets_res.scalars().all()

    output = []
    for b in budgets:
        spent_res = await db.execute(
            select(func.sum(Transaction.amount)).where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.category == b.category,
                    Transaction.type == "expense",
                    Transaction.transaction_date >= start_of_month,
                )
            )
        )
        spent = float(spent_res.scalar() or 0.0)
        output.append(
            {
                "category": b.category,
                "budget": float(b.limit_amount),
                "actual": spent,
                "variance": float(b.limit_amount) - spent,
            }
        )
    return output
