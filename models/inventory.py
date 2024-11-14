from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Float, Date, DateTime, ForeignKey, Text, Column, Integer, Boolean, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base
import enum

class TransactionType(enum.Enum):
    IN = "IN"
    OUT = "OUT"

class ReferenceType(enum.Enum):
    PURCHASE_ORDER = "PO"
    SALES_ORDER = "SO"
    ADJUSTMENT = "ADJ"
    MANUFACTURING = "MFG"

class Material(Base):
    """Material model for inventory management"""
    __tablename__ = 'materials'

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, default=0)
    min_quantity: Mapped[float] = mapped_column(Float, default=0)
    storage_temp: Mapped[Optional[float]] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.now, 
        onupdate=datetime.now
    )
    
    # Relationships
    batches: Mapped[List["MaterialBatch"]] = relationship(
        "MaterialBatch", 
        back_populates="material", 
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Material(code='{self.code}', name='{self.name}')>"

class MaterialBatch(Base):
    """Material batch tracking model"""
    __tablename__ = 'material_batches'

    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey('materials.id'), nullable=False)
    batch_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    manufacturing_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    expiry_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    
    # Relationships
    material: Mapped["Material"] = relationship("Material", back_populates="batches")
    transactions: Mapped[List["InventoryTransaction"]] = relationship(
        "InventoryTransaction",
        back_populates="batch",
        foreign_keys="[InventoryTransaction.batch_id]"
    )

    def __repr__(self) -> str:
        return f"<MaterialBatch(batch_number='{self.batch_number}')>"

class InventoryTransaction(Base):
    """Inventory movement tracking"""
    __tablename__ = "inventory_transactions"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("material_batches.id"))
    transaction_type: Mapped[TransactionType] = mapped_column(Enum(TransactionType))
    quantity: Mapped[float] = mapped_column(Float)
    reference_type: Mapped[ReferenceType] = mapped_column(Enum(ReferenceType))
    reference_id: Mapped[int] = mapped_column(Integer)  # ID from PO/SO/etc tables
    transaction_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    # created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    
    # Relationships
    batch: Mapped["MaterialBatch"] = relationship(
        "MaterialBatch", 
        back_populates="transactions",
        foreign_keys=[batch_id]
    )

    def __repr__(self) -> str:
        return f"<InventoryTransaction(type={self.transaction_type.value}, quantity={self.quantity})>"