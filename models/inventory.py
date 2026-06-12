from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Float, DateTime, ForeignKey, Text, Integer, Boolean, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base
from .enums import ProductType, StorageType, QCStatus, ItemKind
import enum

class TransactionType(enum.Enum):
    IN = "IN"
    OUT = "OUT"
    ADJUST = "ADJUST"

class ReferenceType(enum.Enum):
    PURCHASE_ORDER = "PO"
    SALES_ORDER = "SO"
    ADJUSTMENT = "ADJ"
    MANUFACTURING = "MFG"
    REPACK = "REPACK"

class BulkItem(Base):
    """原裝品主檔 — imported bulk goods (pallet/drum/case) before repacking.

    Table name kept as 'materials' for backward compatibility with existing data.
    """
    __tablename__ = 'materials'

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    product_type: Mapped[Optional[ProductType]] = mapped_column(Enum(ProductType), nullable=True)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)  # 原裝計量單位（棧板/桶/箱）
    quantity: Mapped[float] = mapped_column(Float, default=0)
    min_quantity: Mapped[float] = mapped_column(Float, default=0)
    storage_type: Mapped[Optional[StorageType]] = mapped_column(Enum(StorageType), nullable=True)
    storage_temp: Mapped[Optional[float]] = mapped_column(Float)  # legacy single-temp field
    min_temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    shelf_life_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    default_supplier_id: Mapped[Optional[int]] = mapped_column(ForeignKey('suppliers.id'), nullable=True)
    registration_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    country_of_origin: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now
    )

    # Relationships
    batches: Mapped[List["BulkBatch"]] = relationship(
        "BulkBatch",
        back_populates="bulk_item",
        cascade="all, delete-orphan"
    )
    products: Mapped[List["Product"]] = relationship(  # 一原裝品對多分裝 SKU
        "Product",
        back_populates="bulk_item"
    )

    def __repr__(self) -> str:
        return f"<BulkItem(code='{self.code}', name='{self.name}')>"

class BulkBatch(Base):
    """原裝品批號 — per-batch cost (批次成本) and expiry are required at intake.

    Table name kept as 'material_batches' for backward compatibility.
    Expiry/cost requiredness is enforced at the ViewModel layer so legacy rows load.
    """
    __tablename__ = 'material_batches'

    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey('materials.id'), nullable=False)
    batch_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    lot_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # 原廠批號
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    manufacturing_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    expiry_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    unit_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 該批進貨成本（批次成本計價）
    supplier_id: Mapped[Optional[int]] = mapped_column(ForeignKey('suppliers.id'), nullable=True)
    quality_status: Mapped[Optional[QCStatus]] = mapped_column(Enum(QCStatus), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # Relationships
    bulk_item: Mapped["BulkItem"] = relationship("BulkItem", back_populates="batches")
    transactions: Mapped[List["InventoryTransaction"]] = relationship(
        "InventoryTransaction",
        back_populates="batch",
        foreign_keys="[InventoryTransaction.batch_id]"
    )

    @property
    def material(self) -> "BulkItem":
        """Legacy accessor — old code reads batch.material"""
        return self.bulk_item

    def __repr__(self) -> str:
        return f"<BulkBatch(batch_number='{self.batch_number}')>"

class InventoryTransaction(Base):
    """統一庫存帳本 — single ledger for both bulk and sellable movements.

    item_kind decides which batch table batch_id points to:
      BULK -> material_batches, SELLABLE -> batches.
    The FK below stays on material_batches for legacy rows; SELLABLE rows are
    resolved at the ViewModel layer (僅扣帳決議, no cross-table FK in SQLite).
    """
    __tablename__ = "inventory_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_kind: Mapped[ItemKind] = mapped_column(Enum(ItemKind), default=ItemKind.BULK)
    batch_id: Mapped[int] = mapped_column(ForeignKey("material_batches.id"))
    transaction_type: Mapped[TransactionType] = mapped_column(Enum(TransactionType))
    quantity: Mapped[float] = mapped_column(Float)
    unit_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    balance_after: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reference_type: Mapped[ReferenceType] = mapped_column(Enum(ReferenceType))
    reference_id: Mapped[int] = mapped_column(Integer)  # ID from PO/SO/REPACK/etc tables
    transaction_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    # created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))

    # Relationships
    batch: Mapped["BulkBatch"] = relationship(
        "BulkBatch",
        back_populates="transactions",
        foreign_keys=[batch_id]
    )

    def __repr__(self) -> str:
        return f"<InventoryTransaction(type={self.transaction_type.value}, quantity={self.quantity})>"

class RepackOrder(Base):
    """分裝單 — consumes a bulk batch and produces sellable units (僅扣帳)."""
    __tablename__ = "repack_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    repack_number: Mapped[str] = mapped_column(String(20), unique=True)
    bulk_batch_id: Mapped[int] = mapped_column(ForeignKey("material_batches.id"))
    bulk_qty_consumed: Mapped[float] = mapped_column(Float)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    output_batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("batches.id"), nullable=True)
    output_qty: Mapped[float] = mapped_column(Float)  # = bulk_qty_consumed × units_per_bulk
    repack_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    operator: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # Relationships
    bulk_batch: Mapped["BulkBatch"] = relationship("BulkBatch")

    def __repr__(self) -> str:
        return f"<RepackOrder(number='{self.repack_number}', output_qty={self.output_qty})>"

# Backward-compatible aliases — existing views/viewmodels import these names.
Material = BulkItem
MaterialBatch = BulkBatch
