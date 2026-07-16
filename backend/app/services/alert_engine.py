"""
Alert engine: creates in-app alerts for budget breaches, spending spikes,
and savings-goal milestones.
"""
import uuid
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.app.models.alert import Alert
from backend.app.models.budget import Budget
from backend.app.models.savings import SavingsGoal
from backend.app.models.transaction import Transaction


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

async def _alert_exists(
    user_id: uuid.UUID,
    alert_type: str,
    category: Optional[str],
    db: AsyncSession,
    within_days: int = 1,
) -> bool:
    """Avoid duplicate alerts within a short time window."""
    since = date.today() - timedelta(days=within_days)
    q = select(Alert).where(
        and_(
            Alert.user_id == user_id,
            Alert.alert_type == alert_type,
            Alert.created_at >= since,
        )
    )
    if category:
        q = q.where(Alert.category == category)
    result = await db.execute(q)
    return result.scalar_one_or_none() is not None


async def _create_alert(
    user_id: uuid.UUID,
    alert_type: str,
    message: str,
    db: AsyncSession,
    category: Optional[str] = None,
    threshold_amount: Optional[float] = None,
) -> None:
    alert = Alert(
        user_id=user_id,
        alert_type=alert_type,
        category=category,
        threshold_amount=threshold_amount,
        message=message,
        is_read=False,
        is_active=True,
    )
    db.add(alert)
    await db.commit()


# ---------------------------------------------------------------------------
# Public functions called from routers
# ---------------------------------------------------------------------------

async def check_budget_breach(
    user_id: uuid.UUID,
    category: str,
    db: AsyncSession,
) -> None:
    """Fire a budget_breach alert when spending exceeds the category limit."""
    budget_res = await db.execute(
        select(Budget).where(
            and_(Budget.user_id == user_id, Budget.category == category)
        )
    )
    budget = budget_res.scalar_one_or_none()
    if not budget:
        return

    today = date.today()
    start_of_month = date(today.year, today.month, 1)

    spent_res = await db.execute(
        select(func.sum(Transaction.amount)).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.category == category,
                Transaction.type == "expense",
                Transaction.transaction_date >= start_of_month,
            )
        )
    )
    spent = float(spent_res.scalar() or 0.0)
    limit = float(budget.limit_amount)

    if spent >= limit:
        if not await _alert_exists(user_id, "budget_breach", category, db):
            pct = round(spent / limit * 100)
            await _create_alert(
                user_id=user_id,
                alert_type="budget_breach",
                category=category,
                threshold_amount=limit,
                message=(
                    f"⚠️ تجاوزت ميزانية '{category}'! "
                    f"أنفقت {spent:,.0f} ر.س من أصل {limit:,.0f} ر.س ({pct}٪)."
                ),
                db=db,
            )
    elif spent >= limit * 0.85:
        if not await _alert_exists(user_id, "budget_breach", category, db):
            pct = round(spent / limit * 100)
            await _create_alert(
                user_id=user_id,
                alert_type="budget_breach",
                category=category,
                threshold_amount=limit,
                message=(
                    f"⚡ اقتربت من حد ميزانية '{category}'! "
                    f"أنفقت {pct}٪ من الميزانية الشهرية."
                ),
                db=db,
            )


async def check_spending_spike(
    user_id: uuid.UUID,
    transaction: Transaction,
    db: AsyncSession,
) -> None:
    """Fire a spending_spike alert when a single transaction is unusually large."""
    if transaction.type != "expense":
        return

    thirty_days_ago = date.today() - timedelta(days=30)
    avg_res = await db.execute(
        select(func.avg(Transaction.amount)).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.category == transaction.category,
                Transaction.type == "expense",
                Transaction.transaction_date >= thirty_days_ago,
                Transaction.id != transaction.id,
            )
        )
    )
    avg = float(avg_res.scalar() or 0.0)

    # Spike = more than 3× the 30-day average for that category
    if avg > 0 and float(transaction.amount) >= avg * 3:
        if not await _alert_exists(user_id, "spending_spike", transaction.category, db):
            await _create_alert(
                user_id=user_id,
                alert_type="spending_spike",
                category=transaction.category,
                threshold_amount=float(transaction.amount),
                message=(
                    f"🚨 إنفاق غير معتاد في '{transaction.category}'! "
                    f"المعاملة بقيمة {float(transaction.amount):,.0f} ر.س تتجاوز متوسطك المعتاد."
                ),
                db=db,
            )


async def check_goal_milestones(
    user_id: uuid.UUID,
    goal_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """Fire a goal_milestone alert at 25 %, 50 %, 75 %, and 100 % completion."""
    result = await db.execute(
        select(SavingsGoal).where(
            and_(SavingsGoal.id == goal_id, SavingsGoal.user_id == user_id)
        )
    )
    goal = result.scalar_one_or_none()
    if not goal or float(goal.target_amount) == 0:
        return

    pct = float(goal.current_amount) / float(goal.target_amount) * 100
    milestones = [25, 50, 75, 100]

    for milestone in milestones:
        if pct >= milestone:
            # Check if we already sent this milestone alert
            existing = await db.execute(
                select(Alert).where(
                    and_(
                        Alert.user_id == user_id,
                        Alert.alert_type == "goal_milestone",
                        Alert.category == goal.goal_name,
                        Alert.threshold_amount == float(milestone),
                    )
                )
            )
            if existing.scalar_one_or_none() is None:
                emoji = "🎉" if milestone == 100 else "🏆"
                await _create_alert(
                    user_id=user_id,
                    alert_type="goal_milestone",
                    category=goal.goal_name,
                    threshold_amount=float(milestone),
                    message=(
                        f"{emoji} وصلت إلى {milestone}٪ من هدفك '{goal.goal_name}'! "
                        f"استمر في التوفير لتحقيق حلمك."
                    ),
                    db=db,
                )
