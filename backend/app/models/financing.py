import uuid
from datetime import datetime
from sqlalchemy import String, Numeric, DateTime, Integer, Text, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.database import Base

class FinancingRequest(Base):
    __tablename__ = "financing_requests"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    product_type: Mapped[str] = mapped_column(String(50), nullable=False)  # personal, auto, home
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    term_months: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)  # pending, approved, rejected
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="financing_requests")
