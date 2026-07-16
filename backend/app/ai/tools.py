import uuid
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, func

from backend.app.models.transaction import Transaction
from backend.app.models.budget import Budget
from backend.app.models.savings import SavingsGoal
from backend.app.models.financing import FinancingRequest
from backend.app.models.investment import InvestmentRequest
from backend.app.models.goal import FinancialGoal
from backend.app.models.alert import Alert

from backend.app.services.financial_service import (
    get_financial_summary as service_summary,
    get_category_breakdown as service_breakdown,
    get_budget_vs_actual as service_budget_analysis,
    get_recurring_charges as service_recurring
)
from backend.app.services.alert_engine import (
    check_budget_breach,
    check_spending_spike,
    check_goal_milestones
)

class SirajTools:
    def __init__(self, user_id: uuid.UUID, db: AsyncSession):
        self.user_id = user_id
        self.db = db

    def __deepcopy__(self, memo):
        import copy
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        result.user_id = copy.deepcopy(self.user_id, memo)
        result.db = self.db  # Keep the same db session reference
        return result

    async def get_transactions(self, start_date: str = None, category: str = None, transaction_type: str = None) -> list:
        """
        Retrieves a list of the user's transactions.
        
        Args:
            start_date: Optional ISO date string (YYYY-MM-DD) to filter transactions from.
            category: Optional category name in Arabic (e.g. 'الغذاء والبقالة').
            transaction_type: Optional transaction type ('income' or 'expense').
        """
        query = select(Transaction).where(Transaction.user_id == self.user_id)
        filters = []
        if start_date:
            try:
                dt = date.fromisoformat(start_date)
                filters.append(Transaction.transaction_date >= dt)
            except ValueError:
                pass
        if category:
            filters.append(Transaction.category == category)
        if transaction_type:
            filters.append(Transaction.type == transaction_type)
            
        if filters:
            query = query.where(and_(*filters))
            
        query = query.order_by(Transaction.transaction_date.desc()).limit(30)
        result = await self.db.execute(query)
        txs = result.scalars().all()
        
        return [
            {
                "id": str(t.id),
                "amount": float(t.amount),
                "category": t.category,
                "type": t.type,
                "description": t.description,
                "transaction_date": t.transaction_date.isoformat()
            }
            for t in txs
        ]

    async def get_financial_summary(self) -> dict:
        """
        Retrieves the financial summary of income, expenses, savings, and savings rate.
        """
        return await service_summary(self.user_id, self.db)

    async def get_category_breakdown(self) -> list:
        """
        Retrieves the expense category breakdown with percentages.
        """
        return await service_breakdown(self.user_id, self.db)

    async def get_budget_analysis(self) -> list:
        """
        Retrieves budget analysis (budget limits, actual spent, remaining, and percentage).
        """
        return await service_budget_analysis(self.user_id, self.db)

    async def get_recurring_charges(self) -> list:
        """
        Detects recurring subscriptions or bills (STC, electricity, water, etc.) in the user's transactions.
        """
        res = await service_recurring(self.user_id, self.db)
        # Format date objects for JSON serialization
        for r in res:
            if isinstance(r.get("last_date"), (date, datetime)):
                r["last_date"] = r["last_date"].isoformat()
        return res

    async def add_transaction(self, amount: float, category: str, transaction_type: str, description: str, transaction_date: str = None) -> dict:
        """
        Adds a new transaction (income or expense) to the user's account.
        
        Args:
            amount: The transaction amount in SAR.
            category: Category in Arabic (e.g. 'الغذاء والبقالة', 'الترفيه والمطاعم', 'الراتب').
            transaction_type: Must be 'income' or 'expense'.
            description: Description/name of the transaction (e.g. 'ستاربكس', 'بنده').
            transaction_date: Optional ISO date string (YYYY-MM-DD), defaults to today.
        """
        t_date = date.today()
        if transaction_date:
            try:
                t_date = date.fromisoformat(transaction_date)
            except ValueError:
                pass
                
        new_txn = Transaction(
            user_id=self.user_id,
            amount=amount,
            category=category,
            type=transaction_type,
            description=description,
            transaction_date=t_date
        )
        self.db.add(new_txn)
        await self.db.commit()
        await self.db.refresh(new_txn)

        # Trigger proactive alert checking
        try:
            await check_budget_breach(self.user_id, category, self.db)
            await check_spending_spike(self.user_id, new_txn, self.db)
        except Exception as e:
            print(f"Error executing proactive alert checks: {e}")

        return {
            "status": "success",
            "message": f"تمت إضافة المعاملة بنجاح: {description} بمبلغ {amount} ر.س",
            "transaction_id": str(new_txn.id)
        }

    async def set_budget(self, category: str, limit_amount: float, period: str = "monthly") -> dict:
        """
        Sets or updates a monthly budget for a specific category.
        
        Args:
            category: The spending category in Arabic (e.g. 'الترفيه والمطاعم', 'التسوق والمستلزمات').
            limit_amount: The monthly spending limit in SAR.
            period: The period of the budget, typically 'monthly'.
        """
        # Check if budget exists
        result = await self.db.execute(
            select(Budget).where(
                and_(Budget.user_id == self.user_id, Budget.category == category)
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            existing.limit_amount = limit_amount
            existing.period = period
            await self.db.commit()
            await self.db.refresh(existing)
            action = "تحديث"
        else:
            new_budget = Budget(
                user_id=self.user_id,
                category=category,
                limit_amount=limit_amount,
                period=period
            )
            self.db.add(new_budget)
            await self.db.commit()
            await self.db.refresh(new_budget)
            action = "إنشاء"

        return {
            "status": "success",
            "message": f"تم {action} ميزانية فئة '{category}' لتكون بحد أقصى {limit_amount} ر.س شهرياً."
        }

    async def create_savings_plan(self, goal_name: str, target_amount: float, current_amount: float = 0.0, months: int = 12) -> dict:
        """
        Creates a new savings goal (piggy bank / حصالة).
        
        Args:
            goal_name: The name of the savings plan in Arabic (e.g. 'سفرة الصيف', 'صندوق الطوارئ').
            target_amount: The target savings amount in SAR.
            current_amount: Optional initial deposit amount, defaults to 0.0.
            months: Suggested timeline in months to achieve the target, defaults to 12.
        """
        target_date_obj = date.today() + timedelta(days=months * 30)
        monthly_contrib = target_amount / months if months > 0 else target_amount
        
        new_plan = SavingsGoal(
            user_id=self.user_id,
            goal_name=goal_name,
            target_amount=target_amount,
            current_amount=current_amount,
            target_date=target_date_obj,
            monthly_contribution=round(monthly_contrib, 2),
            status="active"
        )
        self.db.add(new_plan)
        await self.db.commit()
        await self.db.refresh(new_plan)

        # Trigger milestone checking in case current_amount is set
        try:
            await check_goal_milestones(self.user_id, new_plan.id, self.db)
        except Exception as e:
            print(f"Error checking savings milestone: {e}")

        return {
            "status": "success",
            "message": f"تم إنشاء حصالة الادخار '{goal_name}' بنجاح بهدف {target_amount} ر.س ومساهمة شهرية مقترحة {new_plan.monthly_contribution} ر.س."
        }

    async def create_spending_alert(self, alert_type: str, category: str, threshold_amount: float, message: str) -> dict:
        """
        Creates a custom alert settings/threshold alert.
        
        Args:
            alert_type: Type of alert (e.g. 'budget_breach', 'spending_spike').
            category: Category in Arabic associated with the alert.
            threshold_amount: The amount threshold in SAR that triggers the alert.
            message: The alert warning message in Arabic.
        """
        new_alert = Alert(
            user_id=self.user_id,
            alert_type=alert_type,
            category=category,
            threshold_amount=threshold_amount,
            message=message,
            is_read=False,
            is_active=True
        )
        self.db.add(new_alert)
        await self.db.commit()
        return {
            "status": "success",
            "message": "تم إنشاء تنبيه مخصص مالي بنجاح."
        }

    async def simulate_scenario(self, monthly_savings_increase: float, months: int) -> dict:
        """
        Simulates how much money the user would save if they increase their monthly contribution.
        
        Args:
            monthly_savings_increase: Additional SAR to save each month.
            months: Duration of simulation in months.
        """
        summary = await service_summary(self.user_id, self.db)
        current_monthly_surplus = max(0.0, summary["total_income"] - summary["total_expense"])
        
        new_monthly_savings = current_monthly_surplus + monthly_savings_increase
        total_additional = monthly_savings_increase * months
        total_projected = new_monthly_savings * months

        return {
            "projected_additional_savings": total_additional,
            "projected_total_savings": total_projected,
            "message": f"في حال زيادة الادخار بمقدار {monthly_savings_increase} ر.س شهرياً لمدة {months} أشهر، ستدخر مبلغاً إضافياً وقدره {total_additional} ر.س. ليصبح إجمالي مدخراتك المتوقعة {total_projected} ر.س."
        }

    async def submit_financing_request(self, product_type: str, amount: float, term_months: int, notes: str = None) -> dict:
        """
        Submits a new financing (loan) request.
        
        Args:
            product_type: Product type ('personal', 'auto', 'home', 'education', 'business').
            amount: Financing amount requested in SAR.
            term_months: Repayment term in months.
            notes: Optional additional description/reason for financing.
        """
        new_request = FinancingRequest(
            user_id=self.user_id,
            product_type=product_type,
            amount=amount,
            term_months=term_months,
            notes=notes or f"طلب تمويل {product_type} بقيمة {amount} ر.س",
            status="pending"
        )
        self.db.add(new_request)
        await self.db.commit()
        await self.db.refresh(new_request)
        return {
            "status": "success",
            "message": f"تم تقديم طلب تمويل {product_type} بنجاح بقيمة {amount} ر.س وهو تحت المراجعة حالياً.",
            "request_id": str(new_request.id)
        }

    async def get_financing_status(self) -> list:
        """
        Retrieves all financing requests submitted by the user.
        """
        query = select(FinancingRequest).where(FinancingRequest.user_id == self.user_id)
        result = await self.db.execute(query)
        reqs = result.scalars().all()
        return [
            {
                "id": str(r.id),
                "product_type": r.product_type,
                "amount": float(r.amount),
                "term_months": r.term_months,
                "status": r.status,
                "notes": r.notes
            }
            for r in reqs
        ]

    async def get_investment_recommendations(self) -> list:
        """
        Retrieves recommended investment opportunities matching the user profile.
        """
        # For simplicity, returning seeded investment recommendations
        from backend.app.routers.investment import INVESTMENT_OPPORTUNITIES
        recommendations = [
            {
                "opportunity": INVESTMENT_OPPORTUNITIES[0], 
                "recommendation_score": 95,
                "rationale": "بناءً على تفضيلك للمخاطر المنخفضة ورغبتك في تحقيق عوائد ثابتة، فإن صكوك الإنماء العقارية توفر حماية ممتازة لرأس المال مع عائد سنوي مضمون بنسبة 6.25٪ متوافق مع الشريعة."
            },
            {
                "opportunity": INVESTMENT_OPPORTUNITIES[3], 
                "recommendation_score": 85,
                "rationale": "لزيادة تنويع محفظتك، يُنصح بالاستثمار في صندوق مشاعر ريت العقاري الذي يوفر دخلاً دورياً ناتجاً عن عقارات الضيافة في مكة والمدينة، وهو خيار رائع للأمان والاستقرار المالي."
            }
        ]
        return recommendations

    async def submit_investment_request(self, product_name: str, product_type: str, amount: float, risk_level: str, expected_return: float) -> dict:
        """
        Submits a request to invest in a specific opportunity (fund, sukuk, IPO).
        
        Args:
            product_name: The exact name of the investment opportunity.
            product_type: Type of investment ('fund', 'sukuk', 'ipo').
            amount: Investment amount in SAR.
            risk_level: Risk level ('low', 'medium', 'high').
            expected_return: Expected annual return rate percentage.
        """
        new_request = InvestmentRequest(
            user_id=self.user_id,
            product_name=product_name,
            product_type=product_type,
            amount=amount,
            risk_level=risk_level,
            expected_return=expected_return,
            status="pending"
        )
        self.db.add(new_request)
        await self.db.commit()
        await self.db.refresh(new_request)
        return {
            "status": "success",
            "message": f"تم تقديم طلب استثمار في '{product_name}' بنجاح بقيمة {amount} ر.س.",
            "request_id": str(new_request.id)
        }

    async def create_financial_goal(self, goal_type: str, title: str, target_amount: float, target_date: str, saved_amount: float = 0.0) -> dict:
        """
        Creates a seasonal financial goal (Hajj, Umrah, Marriage, Ramadan, Eid, etc.).
        
        Args:
            goal_type: Type ('hajj', 'umrah', 'marriage', 'travel', 'ramadan', 'eid', 'school', 'custom').
            title: Title description in Arabic (e.g. 'فريضة الحج للوالدة').
            target_amount: Total target budget amount in SAR.
            target_date: Target ISO date string (YYYY-MM-DD).
            saved_amount: Optional initial saved amount, defaults to 0.0.
        """
        t_date = date.today() + timedelta(days=365)
        if target_date:
            try:
                t_date = date.fromisoformat(target_date)
            except ValueError:
                pass
                
        # Basic milestones template
        milestones = [
            {"title": "حفظ 25% من الهدف", "amount": float(target_amount) * 0.25, "achieved": saved_amount >= target_amount * 0.25},
            {"title": "حفظ 50% من الهدف", "amount": float(target_amount) * 0.50, "achieved": saved_amount >= target_amount * 0.50},
            {"title": "تحقيق الهدف كاملاً", "amount": float(target_amount), "achieved": saved_amount >= target_amount}
        ]
        
        new_goal = FinancialGoal(
            user_id=self.user_id,
            goal_type=goal_type,
            title=title,
            target_amount=target_amount,
            saved_amount=saved_amount,
            target_date=t_date,
            plan_details={"milestones": milestones, "monthly_target": round(target_amount / 12, 2)},
            status="active"
        )
        self.db.add(new_goal)
        await self.db.commit()
        await self.db.refresh(new_goal)
        return {
            "status": "success",
            "message": f"تم إنشاء الهدف المالي '{title}' بنجاح بمبلغ مستهدف {target_amount} ر.س حتى تاريخ {t_date.isoformat()}.",
            "goal_id": str(new_goal.id)
        }
