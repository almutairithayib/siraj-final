import uuid
from datetime import datetime, date
from sqlalchemy import String, Numeric, DateTime, Date, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.database import Base

class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)  # Map Numeric to float/Decimal
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # income or expense
    description: Mapped[str] = mapped_column(String(255), nullable=True)
    transaction_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="transactions")
