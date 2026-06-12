from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, Float, DateTime, Enum, ForeignKey, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, SpecMixin
from .enums import ProductType, StorageType, PackageType

class Product(Base, TimestampMixin, SpecMixin):
    """分裝品 (sellable SKU) — repacked from a BulkItem; carries spec and selling price.

    One BulkItem can map to many Product SKUs (一對多規格決議).
    """
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    product_type: Mapped[ProductType] = mapped_column(Enum(ProductType))
    storage_type: Mapped[StorageType] = mapped_column(Enum(StorageType))
    package_type: Mapped[PackageType] = mapped_column(Enum(PackageType))
    unit: Mapped[str] = mapped_column(String(20))  # 售賣單位（瓶/支/包）
    min_temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reorder_point: Mapped[float] = mapped_column(Float)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    manufacturer: Mapped[str] = mapped_column(String(100))
    registration_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    shelf_life_months: Mapped[int] = mapped_column(Integer)

    # 分裝來源與換算（nullable so legacy products still load）
    bulk_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("materials.id"), nullable=True)
    units_per_bulk: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 每 1 原裝單位分裝出的售賣單位數

    # 售價（單一標準售價決議）
    selling_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Relationships
    bulk_item: Mapped[Optional["BulkItem"]] = relationship(back_populates="products")
    batches: Mapped[List["Batch"]] = relationship(back_populates="product")
    supplier_products: Mapped[List["SupplierProduct"]] = relationship(back_populates="product")

    def __repr__(self) -> str:
        return f"<Product(code={self.code}, name={self.name})>"

class Batch(Base):
    """分裝品批號 (sellable batch) — expiry is required at repack intake (決議)."""
    __tablename__ = "batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    batch_number: Mapped[str] = mapped_column(String(50))
    manufacture_date: Mapped[datetime] = mapped_column(DateTime)
    expiry_date: Mapped[datetime] = mapped_column(DateTime)
    quantity: Mapped[float] = mapped_column(Float)
    unit_cost: Mapped[float] = mapped_column(Float)  # 分攤後成本（依來源批次成本）
    current_temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quality_check_status: Mapped[str] = mapped_column(String(20))
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 預留：完整批號追溯（僅扣帳決議下不啟用，nullable）
    parent_bulk_batch_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("material_batches.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # Relationships
    product: Mapped["Product"] = relationship(back_populates="batches")

    def __repr__(self) -> str:
        return f"<Batch(number={self.batch_number}, product_id={self.product_id})>"
