import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Configure structured logging for Siraj AI modules
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
# Reduce noise from third-party libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)


from backend.app.database import async_session_maker
from backend.app.seed import seed_data
from backend.app.routers import (
    auth_router,
    dashboard_router,
    transactions_router,
    budgets_router,
    savings_router,
    financing_router,
    investment_router,
    alerts_router,
    goals_router,
    chat_router,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Migrations are applied by the workflow command before uvicorn starts:
    #   alembic upgrade head && uvicorn backend.app.main:app ...
    # Nothing to do here for schema management.

    # Seed database with demo data
    async with async_session_maker() as session:
        try:
            await seed_data(session)
        except Exception as e:
            print(f"Error seeding database: {e}")

    yield
    # Cleanup on shutdown (if any)

app = FastAPI(
    title="Siraj (سراج) API",
    description="Backend API Layer for Siraj Hackathon MVP - Smart Financial Advisor",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration to allow React frontend (Vite default is http://localhost:5173)
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "*",  # Wildcard for development ease
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers under /api/v1/
app.include_router(auth_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(transactions_router, prefix="/api/v1")
app.include_router(budgets_router, prefix="/api/v1")
app.include_router(savings_router, prefix="/api/v1")
app.include_router(financing_router, prefix="/api/v1")
app.include_router(investment_router, prefix="/api/v1")
app.include_router(alerts_router, prefix="/api/v1")
app.include_router(goals_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")

@app.get("/", tags=["Frontend"])
async def serve_frontend():
    """Serve the Siraj Arabic chat frontend."""
    index = Path(__file__).parent / "static" / "index.html"
    return FileResponse(str(index))

@app.get("/health", tags=["Health"])
async def health():
    return {
        "status": "online",
        "message": "Welcome to Siraj (سراج) API Layer. Everything is running smoothly!",
        "version": "1.0.0"
    }
