import uuid
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_

from backend.app.models.user import User
from backend.app.models.savings import SavingsGoal
from backend.app.models.financing import FinancingRequest
from backend.app.models.investment import InvestmentRequest
from backend.app.models.goal import FinancialGoal
from backend.app.models.alert import Alert
from backend.app.services.financial_service import (
    get_financial_summary,
    get_category_breakdown,
    get_budget_vs_actual
)

async def build_context(user_id: uuid.UUID, db: AsyncSession) -> str:
    # 1. User Profile
    user_res = await db.execute(select(User).where(User.id == user_id))
    user = user_res.scalar_one_or_none()
    if not user:
        return "لا توجد بيانات مستخدم متوفرة."

    # 2. Financial Summary
    summary = await get_financial_summary(user_id, db)
    
    # 3. Category Breakdown
    breakdown = await get_category_breakdown(user_id, db)
    
    # 4. Budget Status
    budgets = await get_budget_vs_actual(user_id, db)

    # 5. Savings Goals
    savings_res = await db.execute(
        select(SavingsGoal).where(
            and_(SavingsGoal.user_id == user_id, SavingsGoal.status == "active")
        )
    )
    savings_list = savings_res.scalars().all()

    # 6. Financing Requests
    financing_res = await db.execute(
        select(FinancingRequest).where(FinancingRequest.user_id == user_id)
    )
    financing_list = financing_res.scalars().all()

    # 7. Investment Requests
    investment_res = await db.execute(
        select(InvestmentRequest).where(InvestmentRequest.user_id == user_id)
    )
    investment_list = investment_res.scalars().all()

    # 8. Financial Goals
    goals_res = await db.execute(
        select(FinancialGoal).where(and_(FinancialGoal.user_id == user_id, FinancialGoal.status == "active"))
    )
    goals_list = goals_res.scalars().all()

    # 9. Active Alerts
    alerts_res = await db.execute(
        select(Alert).where(and_(Alert.user_id == user_id, Alert.is_read == False))
    )
    alerts_list = alerts_res.scalars().all()

    # Build the context string in Arabic
    lines = []
    lines.append(f"تاريخ اليوم: {date.today().isoformat()}")
    lines.append(f"اسم المستخدم: {user.full_name}")
    lines.append(f"البريد الإلكتروني: {user.email}")
    lines.append(f"العملة الأساسية: {user.currency}")
    lines.append("")
    
    lines.append("--- الملخص المالي لهذا الشهر ---")
    lines.append(f"إجمالي الدخل: {summary['total_income']:,} {user.currency}")
    lines.append(f"إجمالي المصروفات: {summary['total_expense']:,} {user.currency}")
    lines.append(f"إجمالي المدخرات: {summary['total_savings']:,} {user.currency}")
    lines.append(f"نسبة الادخار: {summary['savings_rate']}%")
    lines.append("")

    lines.append("--- الإنفاق حسب الفئات هذا الشهر ---")
    if breakdown:
        for item in breakdown:
            lines.append(f"- {item['category']}: {item['amount']:,} {user.currency} ({item['percentage']}%)")
    else:
        lines.append("لا توجد مصروفات مسجلة لهذا الشهر.")
    lines.append("")

    lines.append("--- الميزانيات المحددة والالتزام بها ---")
    if budgets:
        for b in budgets:
            status_txt = "متجاوزة ⚠️" if b['percentage_spent'] > 100 else "تحت السيطرة ✅"
            lines.append(f"- ميزانية {b['category']}: الحد {b['limit_amount']:,}، المصروف {b['spent_amount']:,} ({b['percentage_spent']}% من الحد) - {status_txt}")
    else:
        lines.append("لا توجد ميزانيات محددة.")
    lines.append("")

    lines.append("--- حصالات الادخار النشطة ---")
    if savings_list:
        for s in savings_list:
            pct = (float(s.current_amount) / float(s.target_amount) * 100) if s.target_amount > 0 else 0
            lines.append(f"- {s.goal_name}: الهدف {s.target_amount:,.2f}، الحالي {s.current_amount:,.2f} ({pct:.1f}%)، المساهمة الشهرية: {s.monthly_contribution:,.2f}، تاريخ الانتهاء: {s.target_date}")
    else:
        lines.append("لا توجد حصالات ادخار نشطة.")
    lines.append("")

    lines.append("--- الأهداف الموسمية والمالية ---")
    if goals_list:
        for g in goals_list:
            pct = (float(g.saved_amount) / float(g.target_amount) * 100) if g.target_amount > 0 else 0
            lines.append(f"- {g.title} ({g.goal_type}): الهدف {g.target_amount:,.2f}، المدخر {g.saved_amount:,.2f} ({pct:.1f}%)، التاريخ المستهدف: {g.target_date}")
    else:
        lines.append("لا توجد أهداف مالية أو موسمية محددة.")
    lines.append("")

    lines.append("--- طلبات التمويل الحالية ---")
    if financing_list:
        for f in financing_list:
            lines.append(f"- تمويل {f.product_type}: المبلغ {f.amount:,.2f}، المدة {f.term_months} شهر، الحالة: {f.status}")
    else:
        lines.append("لا توجد طلبات تمويل مقدمة.")
    lines.append("")

    lines.append("--- المحفظة والطلبات الاستثمارية ---")
    if investment_list:
        for inv in investment_list:
            lines.append(f"- استثمار {inv.product_name} ({inv.product_type}): المبلغ {inv.amount:,.2f}، العائد المتوقع {inv.expected_return}%، المخاطر: {inv.risk_level}، الحالة: {inv.status}")
    else:
        lines.append("لا توجد استثمارات نشطة أو طلبات معلقة.")
    lines.append("")

    lines.append("--- التنبيهات غير المقروءة ---")
    if alerts_list:
        for alert in alerts_list:
            lines.append(f"- [{alert.alert_type}] {alert.message}")
    else:
        lines.append("لا توجد تنبيهات جديدة غير مقروءة.")

    return "\n".join(lines)
