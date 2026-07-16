import uuid
from datetime import datetime, date
from sqlalchemy import String, Numeric, DateTime, Date, ForeignKey, JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.database import Base

class FinancialGoal(Base):
    __tablename__ = "financial_goals"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    goal_type: Mapped[str] = mapped_column(String(50), nullable=False)  # hajj, umrah, marriage, travel, ramadan, eid, school
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    target_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    saved_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0, nullable=False)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    plan_details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)  # stores AI-generated details, milestones, etc.
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)  # active, achieved, paused
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="financial_goals")
