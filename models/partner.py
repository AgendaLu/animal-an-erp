from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import String, Integer, Float, DateTime, Date, Text, Boolean, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, ContactMixin
from .enums import SupplierType, CustomerType

class SupplierProduct(Base):
    """Supplier-specific product information"""
    __tablename__ = "supplier_products"

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    supplier_product_code: Mapped[str] = mapped_column(String(50))
    unit_price: Mapped[float] = mapped_column(Float)
    min_order_quantity: Mapped[float] = mapped_column(Float)
    lead_time_days: Mapped[int] = mapped_column(Integer)
    is_preferred: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    supplier: Mapped["Supplier"] = relationship(back_populates="supplier_products")
    product: Mapped["Product"] = relationship(back_populates="supplier_products")

class Supplier(Base, TimestampMixin, ContactMixin):
    """Supplier information — 原廠 / 進口商 / 代理"""
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    short_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    supplier_type: Mapped[Optional[SupplierType]] = mapped_column(Enum(SupplierType), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # 進口來源
    contact_person: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    address: Mapped[str] = mapped_column(Text)
    tax_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    credit_term_days: Mapped[int] = mapped_column(Integer)
    payment_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # 電匯/支票/月結
    currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)        # 結算幣別
    bank_account: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    bank_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    bank_branch: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    bank_swift: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    license_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # 藥商許可證
    license_expiry: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    rating: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)  # A/B/C
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    supplier_products: Mapped[List["SupplierProduct"]] = relationship(back_populates="supplier")
    purchase_orders: Mapped[List["PurchaseOrder"]] = relationship(back_populates="supplier")

    def __repr__(self) -> str:
        return f"<Supplier(code={self.code}, name={self.name})>"

class Customer(Base, TimestampMixin, ContactMixin):
    """Customer information — 主要為養豬場"""
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    short_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    customer_type: Mapped[Optional[CustomerType]] = mapped_column(Enum(CustomerType), nullable=True)
    contact_person: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    address: Mapped[str] = mapped_column(Text)
    billing_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    shipping_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    invoice_title: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tax_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    credit_term_days: Mapped[int] = mapped_column(Integer)
    credit_limit: Mapped[float] = mapped_column(Float)
    current_balance: Mapped[float] = mapped_column(Float, default=0)  # 即時應收餘額
    sales_rep: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    farm_license: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # 牧場/畜牧場登記
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    sales_orders: Mapped[List["SalesOrder"]] = relationship(back_populates="customer")

    def __repr__(self) -> str:
        return f"<Customer(code={self.code}, name={self.name})>"
