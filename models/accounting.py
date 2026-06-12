"""會計核帳模組 ORM — 依 docs/accounting_database_design.md v1.0 實作。

9 張表：銷售發票/明細、採購發票/明細、付款記錄、庫存移動帳簿、
盤點表、稅務記錄、應收/應付帳款。
"""
from datetime import datetime, date
from typing import Optional, List
import enum

from sqlalchemy import (
    String, Float, Integer, Text, Date, DateTime, ForeignKey, Enum,
    Index, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


# ---------------------------------------------------------------- enums

class InvoicePaymentStatus(enum.Enum):
    UNPAID = "UNPAID"
    PARTIAL = "PARTIAL"
    PAID = "PAID"


class PaymentType(enum.Enum):
    PAYMENT_TO_SUPPLIER = "PAYMENT_TO_SUPPLIER"
    RECEIPT_FROM_CUSTOMER = "RECEIPT_FROM_CUSTOMER"


class TaxClassification(enum.Enum):
    DOMESTIC = "DOMESTIC"
    IMPORT = "IMPORT"
    EXPORT = "EXPORT"
    EXEMPT = "EXEMPT"


class MovementItemType(enum.Enum):
    BULK = "BULK"
    PRODUCT = "PRODUCT"


class MovementType(enum.Enum):
    IN = "IN"
    OUT = "OUT"
    ADJUST = "ADJUST"


class TaxType(enum.Enum):
    VAT = "VAT"
    BUSINESS_TAX = "BUSINESS_TAX"
    INCOME_TAX = "INCOME_TAX"


class FilingStatus(enum.Enum):
    DRAFT = "DRAFT"
    FILED = "FILED"
    CONFIRMED = "CONFIRMED"


# ------------------------------------------------------------- invoices

class SalesInvoice(Base):
    """銷售發票 — 一張發票對多筆銷售明細"""
    __tablename__ = "sales_invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    customer_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    customer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_amount_pretax: Mapped[float] = mapped_column(Float, default=0)
    total_tax_amount: Mapped[float] = mapped_column(Float, default=0)
    total_amount_with_tax: Mapped[float] = mapped_column(Float, default=0)
    payment_status: Mapped[InvoicePaymentStatus] = mapped_column(
        Enum(InvoicePaymentStatus), default=InvoicePaymentStatus.UNPAID, index=True)
    payment_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    paid_amount: Mapped[float] = mapped_column(Float, default=0)
    remaining_balance: Mapped[float] = mapped_column(Float, default=0)
    currency: Mapped[str] = mapped_column(String(10), default="TWD")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sales_order_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sales_orders.id"), nullable=True)
    tax_classification: Mapped[TaxClassification] = mapped_column(
        Enum(TaxClassification), default=TaxClassification.DOMESTIC)
    unified_invoice_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # 統一發票號碼
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    created_by: Mapped[str] = mapped_column(String(50), default="system")
    issued_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    lines: Mapped[List["SalesTransaction"]] = relationship(
        "SalesTransaction", back_populates="invoice", cascade="all, delete-orphan")
    receivable: Mapped[Optional["AccountsReceivable"]] = relationship(
        "AccountsReceivable", back_populates="invoice", uselist=False)

    def recalc_totals(self) -> None:
        """由明細彙總發票金額並更新付款狀態"""
        self.total_amount_pretax = round(sum(l.line_amount for l in self.lines), 2)
        self.total_tax_amount = round(sum(l.tax_amount for l in self.lines), 2)
        self.total_amount_with_tax = round(self.total_amount_pretax + self.total_tax_amount, 2)
        self.remaining_balance = round(self.total_amount_with_tax - (self.paid_amount or 0), 2)
        if self.paid_amount and self.remaining_balance <= 0:
            self.payment_status = InvoicePaymentStatus.PAID
        elif self.paid_amount:
            self.payment_status = InvoicePaymentStatus.PARTIAL
        else:
            self.payment_status = InvoicePaymentStatus.UNPAID

    def __repr__(self) -> str:
        return f"<SalesInvoice(number='{self.invoice_number}', total={self.total_amount_with_tax})>"


class SalesTransaction(Base):
    """銷售交易明細 — 一行 = 一個商品品項"""
    __tablename__ = "sales_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    sales_invoice_id: Mapped[int] = mapped_column(
        ForeignKey("sales_invoices.id"), nullable=False, index=True)
    product_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    product_name: Mapped[str] = mapped_column(String(100), nullable=False)
    product_batch_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    line_amount: Mapped[float] = mapped_column(Float, nullable=False)        # 稅前
    tax_rate: Mapped[float] = mapped_column(Float, default=5.0)              # %
    tax_amount: Mapped[float] = mapped_column(Float, default=0)
    line_total: Mapped[float] = mapped_column(Float, default=0)              # 稅後
    cost_per_unit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gross_profit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reference_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # SO / DIRECT
    reference_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)

    invoice: Mapped["SalesInvoice"] = relationship("SalesInvoice", back_populates="lines")

    def compute_amounts(self) -> None:
        """計算行小計、稅額、行合計與毛利"""
        self.line_amount = round(self.quantity * self.unit_price, 2)
        self.tax_amount = round(self.line_amount * (self.tax_rate or 0) / 100, 2)
        self.line_total = round(self.line_amount + self.tax_amount, 2)
        if self.cost_per_unit is not None:
            self.gross_profit = round((self.unit_price - self.cost_per_unit) * self.quantity, 2)

    def __repr__(self) -> str:
        return f"<SalesTransaction(product='{self.product_code}', qty={self.quantity})>"


class PurchaseInvoice(Base):
    """採購發票 — 供應商開立，發票號碼 + 供應商唯一"""
    __tablename__ = "purchase_invoices"
    __table_args__ = (
        UniqueConstraint("supplier_code", "invoice_number", name="uq_purchase_inv_supplier_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_number: Mapped[str] = mapped_column(String(50), nullable=False)
    supplier_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    supplier_name: Mapped[str] = mapped_column(String(100), nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_amount_pretax: Mapped[float] = mapped_column(Float, default=0)
    total_tax_amount: Mapped[float] = mapped_column(Float, default=0)        # 進項稅
    total_amount_with_tax: Mapped[float] = mapped_column(Float, default=0)
    payment_status: Mapped[InvoicePaymentStatus] = mapped_column(
        Enum(InvoicePaymentStatus), default=InvoicePaymentStatus.UNPAID, index=True)
    paid_amount: Mapped[float] = mapped_column(Float, default=0)
    remaining_balance: Mapped[float] = mapped_column(Float, default=0)
    payment_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="TWD")
    purchase_order_id: Mapped[Optional[int]] = mapped_column(ForeignKey("purchase_orders.id"), nullable=True)
    tax_classification: Mapped[TaxClassification] = mapped_column(
        Enum(TaxClassification), default=TaxClassification.DOMESTIC)
    vat_registration: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # 供應商統編
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    created_by: Mapped[str] = mapped_column(String(50), default="system")

    lines: Mapped[List["PurchaseTransaction"]] = relationship(
        "PurchaseTransaction", back_populates="invoice", cascade="all, delete-orphan")
    payable: Mapped[Optional["AccountsPayable"]] = relationship(
        "AccountsPayable", back_populates="invoice", uselist=False)

    def recalc_totals(self) -> None:
        self.total_amount_pretax = round(sum(l.line_amount for l in self.lines), 2)
        self.total_tax_amount = round(sum(l.tax_amount for l in self.lines), 2)
        self.total_amount_with_tax = round(self.total_amount_pretax + self.total_tax_amount, 2)
        self.remaining_balance = round(self.total_amount_with_tax - (self.paid_amount or 0), 2)
        if self.paid_amount and self.remaining_balance <= 0:
            self.payment_status = InvoicePaymentStatus.PAID
        elif self.paid_amount:
            self.payment_status = InvoicePaymentStatus.PARTIAL
        else:
            self.payment_status = InvoicePaymentStatus.UNPAID

    def __repr__(self) -> str:
        return f"<PurchaseInvoice(number='{self.invoice_number}', supplier='{self.supplier_code}')>"


class PurchaseTransaction(Base):
    """採購交易明細 — 一行 = 一個原裝品批次"""
    __tablename__ = "purchase_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_invoice_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_invoices.id"), nullable=False, index=True)
    bulk_item_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    bulk_item_name: Mapped[str] = mapped_column(String(100), nullable=False)
    bulk_batch_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    line_amount: Mapped[float] = mapped_column(Float, nullable=False)
    tax_rate: Mapped[float] = mapped_column(Float, default=5.0)
    tax_amount: Mapped[float] = mapped_column(Float, default=0)
    line_total: Mapped[float] = mapped_column(Float, default=0)
    manufacturing_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    lot_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reference_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # PO
    reference_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    received_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    received_qty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    qc_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # PASS/FAIL/PENDING
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)

    invoice: Mapped["PurchaseInvoice"] = relationship("PurchaseInvoice", back_populates="lines")

    def compute_amounts(self) -> None:
        self.line_amount = round(self.quantity * self.unit_price, 2)
        self.tax_amount = round(self.line_amount * (self.tax_rate or 0) / 100, 2)
        self.line_total = round(self.line_amount + self.tax_amount, 2)

    def __repr__(self) -> str:
        return f"<PurchaseTransaction(item='{self.bulk_item_code}', qty={self.quantity})>"


# ------------------------------------------------------------- payments

class PaymentRecord(Base):
    """付款記錄 — 採購付款與銷售收款共用一張表"""
    __tablename__ = "payment_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    payment_type: Mapped[PaymentType] = mapped_column(Enum(PaymentType), nullable=False, index=True)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    reference_type: Mapped[str] = mapped_column(String(20), nullable=False)  # INVOICE / PO
    reference_id: Mapped[int] = mapped_column(Integer, nullable=False)
    supplier_or_customer_code: Mapped[str] = mapped_column(String(20), nullable=False)
    supplier_or_customer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)  # 含稅
    currency: Mapped[str] = mapped_column(String(10), default="TWD")
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False)  # TRANSFER/CHECK/CASH
    bank_account_from: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    bank_account_to: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    check_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    transaction_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    created_by: Mapped[str] = mapped_column(String(50), default="system")
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    verified_by: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    __table_args__ = (
        Index("idx_payment_reference", "reference_type", "reference_id"),
    )

    def __repr__(self) -> str:
        return f"<PaymentRecord(number='{self.payment_number}', amount={self.amount})>"


# ------------------------------------------------------------ inventory

class InventoryMovement(Base):
    """庫存移動帳簿 — 進貨/銷售/損耗/盤差的完整流水帳"""
    __tablename__ = "inventory_movements"
    __table_args__ = (
        Index("idx_inv_mov_item", "item_code", "batch_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    movement_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    item_type: Mapped[MovementItemType] = mapped_column(Enum(MovementItemType), nullable=False)
    item_code: Mapped[str] = mapped_column(String(50), nullable=False)
    item_name: Mapped[str] = mapped_column(String(100), nullable=False)
    batch_number: Mapped[str] = mapped_column(String(50), nullable=False)
    movement_type: Mapped[MovementType] = mapped_column(Enum(MovementType), nullable=False, index=True)
    quantity_change: Mapped[float] = mapped_column(Float, nullable=False)  # ±值
    unit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    balance_before: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    balance_after: Mapped[float] = mapped_column(Float, nullable=False)
    reference_type: Mapped[str] = mapped_column(String(20), nullable=False)  # PO/SO/REPACK/INVENTORY_COUNT/ADJUSTMENT
    reference_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    created_by: Mapped[str] = mapped_column(String(50), default="system")

    def __repr__(self) -> str:
        return f"<InventoryMovement(item='{self.item_code}', change={self.quantity_change})>"


class InventoryCount(Base):
    """庫存盤點 — 物理盤點 vs 帳面餘額比對"""
    __tablename__ = "inventory_counts"

    id: Mapped[int] = mapped_column(primary_key=True)
    count_number: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    count_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    item_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    item_name: Mapped[str] = mapped_column(String(100), nullable=False)
    batch_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    account_balance: Mapped[float] = mapped_column(Float, nullable=False)
    physical_count: Mapped[float] = mapped_column(Float, nullable=False)
    variance: Mapped[float] = mapped_column(Float, nullable=False)  # physical - account
    variance_reason: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    unit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    variance_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    created_by: Mapped[str] = mapped_column(String(50), default="system")
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    verified_by: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    def compute_variance(self) -> None:
        self.variance = round(self.physical_count - self.account_balance, 4)
        if self.unit_price is not None:
            self.variance_amount = round(self.variance * self.unit_price, 2)

    def __repr__(self) -> str:
        return f"<InventoryCount(number='{self.count_number}', variance={self.variance})>"


# ------------------------------------------------------------------ tax

class TaxRecord(Base):
    """稅務記錄 — 月度彙總與申報追蹤；應納稅額 = 銷項稅 − 進項稅"""
    __tablename__ = "tax_records"
    __table_args__ = (
        UniqueConstraint("tax_period", "tax_type", name="uq_tax_period_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tax_period: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM
    tax_type: Mapped[TaxType] = mapped_column(Enum(TaxType), default=TaxType.VAT)
    total_sales_amount: Mapped[float] = mapped_column(Float, default=0)
    total_sales_tax: Mapped[float] = mapped_column(Float, default=0)
    total_purchase_amount: Mapped[float] = mapped_column(Float, default=0)
    total_purchase_tax: Mapped[float] = mapped_column(Float, default=0)
    net_tax_payable: Mapped[float] = mapped_column(Float, default=0)
    sales_invoice_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    purchase_invoice_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    filing_status: Mapped[FilingStatus] = mapped_column(
        Enum(FilingStatus), default=FilingStatus.DRAFT, index=True)
    filing_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    filing_reference_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    payment_due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    payment_status: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # UNPAID/PAID
    payment_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    created_by: Mapped[str] = mapped_column(String(50), default="system")

    def __repr__(self) -> str:
        return f"<TaxRecord(period='{self.tax_period}', net={self.net_tax_payable})>"


# ---------------------------------------------------------------- AR/AP

class AccountsReceivable(Base):
    """應收帳款 — 一張銷售發票對應一筆"""
    __tablename__ = "accounts_receivable"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    customer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    sales_invoice_id: Mapped[int] = mapped_column(
        ForeignKey("sales_invoices.id"), nullable=False, unique=True)
    invoice_number: Mapped[str] = mapped_column(String(30), nullable=False)
    original_amount: Mapped[float] = mapped_column(Float, nullable=False)  # 含稅
    paid_amount: Mapped[float] = mapped_column(Float, default=0)
    outstanding_amount: Mapped[float] = mapped_column(Float, nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    days_overdue: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    overdue_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # ON_TIME/OVERDUE
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_payment_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    invoice: Mapped["SalesInvoice"] = relationship("SalesInvoice", back_populates="receivable")

    def refresh_overdue(self, as_of: Optional[date] = None) -> None:
        as_of = as_of or date.today()
        if self.outstanding_amount > 0 and as_of > self.due_date:
            self.days_overdue = (as_of - self.due_date).days
            self.overdue_status = "OVERDUE"
        else:
            self.days_overdue = 0
            self.overdue_status = "ON_TIME"

    def __repr__(self) -> str:
        return f"<AccountsReceivable(invoice='{self.invoice_number}', outstanding={self.outstanding_amount})>"


class AccountsPayable(Base):
    """應付帳款 — 一張採購發票對應一筆"""
    __tablename__ = "accounts_payable"

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    supplier_name: Mapped[str] = mapped_column(String(100), nullable=False)
    purchase_invoice_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_invoices.id"), nullable=False, unique=True)
    invoice_number: Mapped[str] = mapped_column(String(50), nullable=False)
    original_amount: Mapped[float] = mapped_column(Float, nullable=False)
    paid_amount: Mapped[float] = mapped_column(Float, default=0)
    outstanding_amount: Mapped[float] = mapped_column(Float, nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    days_overdue: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    overdue_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_payment_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    invoice: Mapped["PurchaseInvoice"] = relationship("PurchaseInvoice", back_populates="payable")

    def refresh_overdue(self, as_of: Optional[date] = None) -> None:
        as_of = as_of or date.today()
        if self.outstanding_amount > 0 and as_of > self.due_date:
            self.days_overdue = (as_of - self.due_date).days
            self.overdue_status = "OVERDUE"
        else:
            self.days_overdue = 0
            self.overdue_status = "ON_TIME"

    def __repr__(self) -> str:
        return f"<AccountsPayable(invoice='{self.invoice_number}', outstanding={self.outstanding_amount})>"
