# سِراج (Siraj) — AI Financial Advisor API

Smart personal finance backend for Saudi Arabia, built with FastAPI. Originally submitted as a hackathon project.

## How to run

The server starts automatically via the **Start application** workflow:

```
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

Port **8000** — console output mode (API only, no frontend).

## Interactive docs

Once running, open:
- **Swagger UI**: `https://<your-repl-domain>:8000/docs`
- **ReDoc**: `https://<your-repl-domain>:8000/redoc`

## Demo account (auto-created on first start)

| Field    | Value            |
|----------|------------------|
| Email    | sara@siraj.sa    |
| Password | password123      |

## Stack

| Layer       | Technology                         |
|-------------|------------------------------------|
| Framework   | FastAPI (Python 3.12)              |
| Database    | PostgreSQL via Replit (asyncpg)    |
| ORM         | SQLAlchemy 2 (async)               |
| Auth        | JWT (python-jose) + bcrypt         |
| AI          | Google Gemini (primary) — optional |

## AI chat feature

The `/api/v1/chat/` endpoints require a `GEMINI_API_KEY` secret. Without it, the chat router loads but requests will fail gracefully with an Arabic fallback message. All other endpoints (dashboard, transactions, budgets, savings, goals, etc.) work without any AI key.

To enable AI chat:
1. Add `GEMINI_API_KEY` as a Replit secret
2. Restart the workflow

## Project structure

```
backend/
└── app/
    ├── ai/           # Gemini agent loop, context builder, tools
    ├── models/       # SQLAlchemy ORM models
    ├── routers/      # FastAPI route handlers
    ├── schemas/      # Pydantic request/response schemas
    ├── services/     # auth_service, financial_service, alert_engine
    ├── config.py     # Settings (reads env vars / .env)
    ├── database.py   # Async engine + session factory
    ├── main.py       # App entry point & lifespan
    └── seed.py       # Demo data seeder
```

## User preferences

- Keep the existing FastAPI / SQLAlchemy stack — do not migrate to a different framework.
- Arabic UI strings should remain in Arabic.
