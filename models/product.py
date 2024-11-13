from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, Float, DateTime, Enum, ForeignKey, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin
from .enums import ProductType, StorageType, PackageType

class Product(Base, TimestampMixin):
    """Product model for medicines, vaccines, feeds, and supplements"""
    __tablename__ = "products"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    product_type: Mapped[ProductType] = mapped_column(Enum(ProductType))
    storage_type: Mapped[StorageType] = mapped_column(Enum(StorageType))
    package_type: Mapped[PackageType] = mapped_column(Enum(PackageType))
    unit: Mapped[str] = mapped_column(String(20))
    min_temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reorder_point: Mapped[float] = mapped_column(Float)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    manufacturer: Mapped[str] = mapped_column(String(100))
    registration_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    shelf_life_months: Mapped[int] = mapped_column(Integer)

    # Relationships
    batches: Mapped[List["Batch"]] = relationship(back_populates="product")
    supplier_products: Mapped[List["SupplierProduct"]] = relationship(back_populates="product")

    def __repr__(self) -> str:
        return f"<Product(code={self.code}, name={self.name})>"

class Batch(Base):
    """Batch tracking for inventory"""
    __tablename__ = "batches"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    batch_number: Mapped[str] = mapped_column(String(50))
    manufacture_date: Mapped[datetime] = mapped_column(DateTime)
    expiry_date: Mapped[datetime] = mapped_column(DateTime)
    quantity: Mapped[float] = mapped_column(Float)
    unit_cost: Mapped[float] = mapped_column(Float)
    current_temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quality_check_status: Mapped[str] = mapped_column(String(20))
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # Relationships
    product: Mapped["Product"] = relationship(back_populates="batches")
    inventory_transactions: Mapped[List["InventoryTransaction"]] = relationship(back_populates="batch")

    def __repr__(self) -> str:
        return f"<Batch(number={self.batch_number}, product_id={self.product_id})>"
