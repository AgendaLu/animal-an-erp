from datetime import datetime
from typing import Optional
from sqlalchemy import String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

class InventoryTransaction(Base):
    """Inventory movement tracking"""
    __tablename__ = "inventory_transactions"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"))
    transaction_type: Mapped[str] = mapped_column(String(20))  # IN/OUT
    quantity: Mapped[float] = mapped_column(Float)
    reference_type: Mapped[str] = mapped_column(String(20))  # PO/SO
    reference_id: Mapped[int] = mapped_column(ForeignKey("batches.id"))
    transaction_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    batch: Mapped["Batch"] = relationship(back_populates="inventory_transactions")

    def __repr__(self) -> str:
        return (
            f"<InventoryTransaction("
            f"batch_id={self.batch_id}, "
            f"type={self.transaction_type}, "
            f"quantity={self.quantity})>"
        )
