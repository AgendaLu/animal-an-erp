from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Float
from datetime import datetime
from typing import Optional

class Base(DeclarativeBase):
    """Base class for all models"""
    pass

class TimestampMixin:
    """Mixin to add timestamp fields"""
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now,
        onupdate=datetime.now
    )

class SpecMixin:
    """規格欄位 (product specification fields), shared by sellable products"""
    spec: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)            # e.g. "100 mL/瓶"
    package_size: Mapped[Optional[float]] = mapped_column(Float, nullable=True)        # 單一包裝容量
    package_unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)     # mL / g / 劑
    units_per_package: Mapped[Optional[float]] = mapped_column(Float, nullable=True)   # 每包裝內含數
    dosage_form: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)      # 劑型
    concentration: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)    # 濃度
    active_ingredient: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    barcode: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

class ContactMixin:
    """共用聯絡資訊欄位 for Supplier / Customer"""
    contact_title: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    fax: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    mobile: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
