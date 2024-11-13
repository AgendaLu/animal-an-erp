from datetime import datetime
from typing import Optional
from sqlalchemy import String, Float, DateTime, Enum, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin
from .enums import PaymentStatus

class Payment(Base, TimestampMixin):
    """Payment tracking"""
    __tablename__ = "payments"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    reference_type: Mapped[str] = mapped_column(String(20))  # PO/SO
    reference_id: Mapped[int] = mapped_column(Integer)
    payment_date: Mapped[datetime] = mapped_column(DateTime)
    amount: Mapped[float] = mapped_column(Float)
    payment_method: Mapped[str] = mapped_column(String(50))
    payment_reference: Mapped[str] = mapped_column(String(100))
    status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus))
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<Payment("
            f"reference={self.reference_type}:{self.reference_id}, "
            f"amount={self.amount}, "
            f"status={self.status.value})>"
        )
