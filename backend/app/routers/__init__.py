from backend.app.routers.auth import router as auth_router
from backend.app.routers.dashboard import router as dashboard_router
from backend.app.routers.transactions import router as transactions_router
from backend.app.routers.budgets import router as budgets_router
from backend.app.routers.savings import router as savings_router
from backend.app.routers.financing import router as financing_router
from backend.app.routers.investment import router as investment_router
from backend.app.routers.alerts import router as alerts_router
from backend.app.routers.goals import router as goals_router
from backend.app.routers.chat import router as chat_router

__all__ = [
    "auth_router",
    "dashboard_router",
    "transactions_router",
    "budgets_router",
    "savings_router",
    "financing_router",
    "investment_router",
    "alerts_router",
    "goals_router",
    "chat_router",
]
