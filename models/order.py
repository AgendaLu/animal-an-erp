from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, Float, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin
from .enums import OrderStatus, PaymentStatus

class PurchaseOrder(Base, TimestampMixin):
    """Purchase order management"""
    __tablename__ = "purchase_orders"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    po_number: Mapped[str] = mapped_column(String(20), unique=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    order_date: Mapped[datetime] = mapped_column(DateTime)
    expected_delivery: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus))
    total_amount: Mapped[float] = mapped_column(Float)
    payment_status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus))
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    supplier: Mapped["Supplier"] = relationship(back_populates="purchase_orders")
    po_items: Mapped[List["PurchaseOrderItem"]] = relationship(back_populates="purchase_order")

    def __repr__(self) -> str:
        return f"<PurchaseOrder(number={self.po_number}, supplier_id={self.supplier_id})>"

class PurchaseOrderItem(Base):
    """Purchase order line items"""
    __tablename__ = "purchase_order_items"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    po_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[float] = mapped_column(Float)
    unit_price: Mapped[float] = mapped_column(Float)
    total_price: Mapped[float] = mapped_column(Float)
    received_quantity: Mapped[float] = mapped_column(Float, default=0)
    
    # Relationships
    purchase_order: Mapped["PurchaseOrder"] = relationship(back_populates="po_items")
    product: Mapped["Product"] = relationship()

class SalesOrder(Base, TimestampMixin):
    """Sales order management"""
    __tablename__ = "sales_orders"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    so_number: Mapped[str] = mapped_column(String(20), unique=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    order_date: Mapped[datetime] = mapped_column(DateTime)
    delivery_date: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus))
    total_amount: Mapped[float] = mapped_column(Float)
    payment_status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus))
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    customer: Mapped["Customer"] = relationship(back_populates="sales_orders")
    so_items: Mapped[List["SalesOrderItem"]] = relationship(back_populates="sales_order")

    def __repr__(self) -> str:
        return f"<SalesOrder(number={self.so_number}, customer_id={self.customer_id})>"

class SalesOrderItem(Base):
    """Sales order line items"""
    __tablename__ = "sales_order_items"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    so_id: Mapped[int] = mapped_column(ForeignKey("sales_orders.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"))
    quantity: Mapped[float] = mapped_column(Float)
    unit_price: Mapped[float] = mapped_column(Float)
    total_price: Mapped[float] = mapped_column(Float)
    shipped_quantity: Mapped[float] = mapped_column(Float, default=0)
    
    # Relationships
    sales_order: Mapped["SalesOrder"] = relationship(back_populates="so_items")
    product: Mapped["Product"] = relationship()
    batch: Mapped["Batch"] = relationship()
