import uuid
from datetime import datetime
from sqlalchemy import String, Numeric, DateTime, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.database import Base

class InvestmentRequest(Base):
    __tablename__ = "investment_requests"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    product_name: Mapped[str] = mapped_column(String(100), nullable=False)
    product_type: Mapped[str] = mapped_column(String(50), nullable=False)  # fund, sukuk, ipo
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)  # low, medium, high
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)  # pending, completed, active
    expected_return: Mapped[float] = mapped_column(Numeric(5, 2), nullable=True)  # annual percentage return, e.g., 5.50
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="investment_requests")
