from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, Float, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

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

class Supplier(Base, TimestampMixin):
    """Supplier information"""
    __tablename__ = "suppliers"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    contact_person: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    address: Mapped[str] = mapped_column(Text)
    tax_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    credit_term_days: Mapped[int] = mapped_column(Integer)
    bank_account: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationships
    supplier_products: Mapped[List["SupplierProduct"]] = relationship(back_populates="supplier")
    purchase_orders: Mapped[List["PurchaseOrder"]] = relationship(back_populates="supplier")

    def __repr__(self) -> str:
        return f"<Supplier(code={self.code}, name={self.name})>"

class Customer(Base, TimestampMixin):
    """Customer information"""
    __tablename__ = "customers"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    customer_type: Mapped[str] = mapped_column(String(20))  # Veterinary, Farm, Retail
    contact_person: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    address: Mapped[str] = mapped_column(Text)
    tax_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    credit_term_days: Mapped[int] = mapped_column(Integer)
    credit_limit: Mapped[float] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationships
    sales_orders: Mapped[List["SalesOrder"]] = relationship(back_populates="customer")

    def __repr__(self) -> str:
        return f"<Customer(code={self.code}, name={self.name})>"
