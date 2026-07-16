"""
Seed the database with demo data on first start.
Demo account: sara@siraj.sa / password123
"""
import uuid
from datetime import date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.app.models.user import User
from backend.app.models.transaction import Transaction
from backend.app.models.budget import Budget
from backend.app.models.savings import SavingsGoal
from backend.app.models.goal import FinancialGoal
from backend.app.services.auth_service import hash_password


DEMO_EMAIL = "sara@siraj.sa"


async def seed_data(session: AsyncSession) -> None:
    """Create demo user and sample financial data if they don't already exist."""
    result = await session.execute(select(User).where(User.email == DEMO_EMAIL))
    if result.scalar_one_or_none() is not None:
        return  # Already seeded

    # ── Demo user ──────────────────────────────────────────────────────────
    user = User(
        id=uuid.uuid4(),
        email=DEMO_EMAIL,
        full_name="سارة الأحمدي",
        hashed_password=hash_password("password123"),
        currency="SAR",
        created_at=datetime.utcnow(),
    )
    session.add(user)
    await session.flush()  # get user.id before adding children

    today = date.today()

    # ── Transactions ───────────────────────────────────────────────────────
    transactions = [
        # Income
        Transaction(user_id=user.id, amount=12000, category="راتب", type="income",
                    description="راتب شهر يونيو", transaction_date=today.replace(day=1)),
        Transaction(user_id=user.id, amount=1500, category="عمل حر", type="income",
                    description="مشروع تصميم جرافيك", transaction_date=today - timedelta(days=5)),
        # Expenses
        Transaction(user_id=user.id, amount=3200, category="إيجار", type="expense",
                    description="إيجار الشقة", transaction_date=today.replace(day=2)),
        Transaction(user_id=user.id, amount=850, category="مواد غذائية", type="expense",
                    description="مشتريات السوبرماركت", transaction_date=today - timedelta(days=3)),
        Transaction(user_id=user.id, amount=450, category="مطاعم", type="expense",
                    description="وجبات خارجية", transaction_date=today - timedelta(days=4)),
        Transaction(user_id=user.id, amount=320, category="مواصلات", type="expense",
                    description="وقود ورسوم", transaction_date=today - timedelta(days=2)),
        Transaction(user_id=user.id, amount=200, category="ترفيه", type="expense",
                    description="اشتراكات ونزهات", transaction_date=today - timedelta(days=6)),
        Transaction(user_id=user.id, amount=150, category="صحة", type="expense",
                    description="صيدلية وطبيب", transaction_date=today - timedelta(days=7)),
        Transaction(user_id=user.id, amount=500, category="ملابس", type="expense",
                    description="تسوق الملابس", transaction_date=today - timedelta(days=10)),
    ]
    session.add_all(transactions)

    # ── Budgets ────────────────────────────────────────────────────────────
    budgets = [
        Budget(user_id=user.id, category="مواد غذائية", limit_amount=1000, period="monthly"),
        Budget(user_id=user.id, category="مطاعم", limit_amount=500, period="monthly"),
        Budget(user_id=user.id, category="مواصلات", limit_amount=400, period="monthly"),
        Budget(user_id=user.id, category="ترفيه", limit_amount=300, period="monthly"),
        Budget(user_id=user.id, category="ملابس", limit_amount=600, period="monthly"),
    ]
    session.add_all(budgets)

    # ── Savings goals ──────────────────────────────────────────────────────
    savings_goals = [
        SavingsGoal(
            user_id=user.id,
            goal_name="صندوق الطوارئ",
            target_amount=20000,
            current_amount=8500,
            target_date=today + timedelta(days=180),
            monthly_contribution=1500,
            status="active",
        ),
        SavingsGoal(
            user_id=user.id,
            goal_name="رحلة العمرة",
            target_amount=5000,
            current_amount=1200,
            target_date=today + timedelta(days=90),
            monthly_contribution=600,
            status="active",
        ),
    ]
    session.add_all(savings_goals)

    # ── Financial goals ────────────────────────────────────────────────────
    financial_goals = [
        FinancialGoal(
            user_id=user.id,
            goal_type="hajj",
            title="فريضة الحج",
            target_amount=25000,
            saved_amount=5000,
            target_date=today + timedelta(days=365),
            plan_details={
                "monthly_target": 1667,
                "ai_recommendations": [
                    "ادخر 1667 ريال شهرياً لتحقيق هدف الحج خلال 12 شهراً.",
                    "استثمر جزءاً من المبلغ في صكوك حكومية قصيرة الأجل.",
                ],
                "milestones": [
                    {"title": "البداية", "amount": 0, "achieved": True},
                    {"title": "ربع الطريق", "amount": 6250, "achieved": False},
                    {"title": "منتصف الطريق", "amount": 12500, "achieved": False},
                    {"title": "تحقيق الحلم", "amount": 25000, "achieved": False},
                ],
            },
            status="active",
        )
    ]
    session.add_all(financial_goals)

    await session.commit()
    print("✅ Demo data seeded successfully (sara@siraj.sa / password123)")
