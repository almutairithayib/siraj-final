import uuid
from datetime import date
import random
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, func

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.models.transaction import Transaction
from backend.app.models.budget import Budget
from backend.app.models.savings import SavingsGoal
from backend.app.models.goal import FinancialGoal
from backend.app.models.alert import Alert
from backend.app.services.auth_service import get_current_user
from backend.app.services.financial_service import (
    get_financial_summary,
    get_category_breakdown,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

# Mock daily tips in Arabic
TIPS = [
    "تجنب الشراء الاندفاعي! انتظر 24 ساعة قبل شراء أي منتج غير ضروري لتتأكد من حاجتك الفعلية له.",
    "الادخار التلقائي هو سر النجاح: قم ببرمجة تحويل 10% من راتبك لحساب الادخار فور استلامه شهرياً.",
    "مراجعة الاشتراكات الشهرية قد توفر لك مئات الريالات. هل ما زلت بحاجة لكافة المنصات النشطة؟",
    "تذكر دائماً تخصيص صندوق للطوارئ يغطي مصاريف 3 إلى 6 أشهر لحمايتك من الظروف غير المتوقعة.",
    "تسوق المقاضي بقائمة مكتوبة مسبقاً وتجنب الذهاب للمتجر وأنت جائع لتقليل الشراء غير المخطط له.",
    "الاستثمار المبكر في الصكوك يمنحك نمواً آمناً لمدخراتك بفضل الفوائد المركبة والتوزيعات الدورية.",
    "تجهيز ميزانية رمضان قبل شهرين من حلوله يمنع الضغط المالي المفاجئ على محفظتك في المواسم."
]

@router.get("/overview")
async def get_overview(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    summary = await get_financial_summary(current_user.id, db)
    return {
        "total_income": summary["total_income"],
        "total_expense": summary["total_expense"],
        "total_savings": summary["total_savings"],
        "savings_rate": summary["savings_rate"],
        "currency": current_user.currency
    }

@router.get("/category-breakdown")
async def get_dashboard_category_breakdown(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await get_category_breakdown(current_user.id, db)


@router.get("/health-score")
async def get_health_score(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Rule-based Financial Health Score
    # Factors:
    # 1. Savings Rate (30 points)
    # 2. Budget adherence (40 points)
    # 3. Emergency Fund existence (30 points)
    
    today = date.today()
    start_of_month = date(today.year, today.month, 1)
    
    # 1. Savings Rate
    inc_res = await db.execute(
        select(func.sum(Transaction.amount)).where(
            and_(Transaction.user_id == current_user.id, Transaction.type == "income", Transaction.transaction_date >= start_of_month)
        )
    )
    exp_res = await db.execute(
        select(func.sum(Transaction.amount)).where(
            and_(Transaction.user_id == current_user.id, Transaction.type == "expense", Transaction.transaction_date >= start_of_month)
        )
    )
    inc = float(inc_res.scalar() or 0.0)
    exp = float(exp_res.scalar() or 0.0)
    
    savings_rate = 0.0
    if inc > 0:
        savings_rate = (inc - exp) / inc
        
    sr_points = 0.0
    if savings_rate >= 0.20:  # Saved 20% or more
        sr_points = 30.0
    elif savings_rate > 0:
        sr_points = savings_rate * 150.0  # proportional
        
    # 2. Budget Adherence
    # We look at budgets vs spending this month
    budgets_res = await db.execute(select(Budget).where(Budget.user_id == current_user.id))
    budgets = budgets_res.scalars().all()
    
    total_budgets = len(budgets)
    breached_budgets = 0
    
    for b in budgets:
        spent_res = await db.execute(
            select(func.sum(Transaction.amount)).where(
                and_(
                    Transaction.user_id == current_user.id,
                    Transaction.category == b.category,
                    Transaction.type == "expense",
                    Transaction.transaction_date >= start_of_month
                )
            )
        )
        spent = float(spent_res.scalar() or 0.0)
        if spent > float(b.limit_amount):
            breached_budgets += 1
            
    budget_points = 40.0
    if total_budgets > 0:
        adherence_ratio = (total_budgets - breached_budgets) / total_budgets
        budget_points = adherence_ratio * 40.0
        
    # 3. Emergency Fund
    # Check if there is an active goal containing "طوارئ" or "emergency"
    emergency_res = await db.execute(
        select(SavingsGoal).where(
            and_(
                SavingsGoal.user_id == current_user.id,
                SavingsGoal.goal_name.like("%طوارئ%")
            )
        )
    )
    emergency_goal = emergency_res.scalar_one_or_none()
    
    emergency_points = 0.0
    if emergency_goal:
        # Check if they saved anything
        saved = float(emergency_goal.current_amount)
        target = float(emergency_goal.target_amount)
        if target > 0:
            pct = saved / target
            emergency_points = min(30.0, pct * 30.0)
        else:
            emergency_points = 15.0
            
    # Calculate Total Score
    total_score = round(sr_points + budget_points + emergency_points)
    total_score = max(0, min(100, total_score))
    
    # Determine Grade and Arabic message
    if total_score >= 85:
        grade = "ممتاز"
        insights = "أداء مالي استثنائي! أنت تتحكم بميزانيتك بشكل رائع وتدخر بشكل مستمر ومدروس."
    elif total_score >= 70:
        grade = "جيد جداً"
        insights = "وضعك المالي مستقر وجيد. حاول تقليص المصاريف الكمالية لرفع نسبة ادخارك وضمان أهدافك."
    elif total_score >= 50:
        grade = "مقبول"
        insights = "هناك بعض التقدم ولكنك تواجه صعوبة في الالتزام بالميزانية. راجع فئات إنفاقك بدقة."
    else:
        grade = "ضعيف"
        insights = "تحذير: إنفاقك يفوق طاقتك الادخارية وهناك تجاوزات للميزانية. ننصحك بطلب المشورة من سراج لوضع خطة طوارئ عاجلة."
        
    return {
        "score": total_score,
        "grade": grade,
        "insights": insights,
        "savings_rate_points": round(sr_points, 1),
        "budget_adherence_points": round(budget_points, 1),
        "emergency_points": round(emergency_points, 1)
    }

@router.get("/daily-tip")
async def get_daily_tip(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        from google import genai
        from google.genai import types
        from backend.app.config import settings
        from backend.app.ai.context_builder import build_context
        
        if settings.GEMINI_API_KEY:
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            context = await build_context(current_user.id, db)
            prompt = (
                f"أنت سراج، مستشار مالي شخصي ذكي في السعودية.\n"
                f"بناءً على الوضع المالي للمستخدم أدناه:\n"
                f"{context}\n\n"
                f"قدم نصيحة مالية يومية قصيرة جداً ومفيدة ومخصصة باللهجة السعودية البيضاء الودية.\n"
                f"الشروط:\n"
                f"- سطر واحد فقط لا يزيد عن 15-20 كلمة.\n"
                f"- لا تضف أي عنوان مثل 'نصيحة اليوم:' أو غيره، ابدأ بالنصيحة مباشرة."
            )
            response = client.models.generate_content(
                model='gemini-3.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.7)
            )
            if response.text:
                return {"tip": response.text.strip()}
    except Exception as e:
        print(f"Error generating dynamic daily tip: {e}")

    # Select a deterministic or random tip
    random.seed(date.today().toordinal() + hash(current_user.id) % 10000)
    tip = random.choice(TIPS)
    return {"tip": tip}

@router.get("/alerts/active")
async def get_active_alerts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Alert).where(
            and_(
                Alert.user_id == current_user.id,
                Alert.is_read == False,
                Alert.is_active == True
            )
        )
    )
    return result.scalars().all()

@router.get("/goals/summary")
async def get_goals_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    goals_res = await db.execute(
        select(FinancialGoal).where(FinancialGoal.user_id == current_user.id)
    )
    goals = goals_res.scalars().all()
    
    savings_goals_res = await db.execute(
        select(SavingsGoal).where(SavingsGoal.user_id == current_user.id)
    )
    savings = savings_goals_res.scalars().all()
    
    total_target = 0.0
    total_saved = 0.0
    
    for g in goals:
        total_target += float(g.target_amount)
        total_saved += float(g.saved_amount)
        
    for s in savings:
        total_target += float(s.target_amount)
        total_saved += float(s.current_amount)
        
    overall_progress = 0.0
    if total_target > 0:
        overall_progress = round((total_saved / total_target) * 100, 2)
        
    return {
        "total_goals_count": len(goals) + len(savings),
        "total_target_amount": total_target,
        "total_saved_amount": total_saved,
        "overall_progress_percentage": overall_progress
    }
