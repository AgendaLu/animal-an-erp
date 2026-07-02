"""會計模組 ORM 單元測試 — in-memory SQLite."""
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models import Base  # noqa: E402
from models.accounting import (  # noqa: E402
    SalesInvoice, SalesTransaction,
    PurchaseInvoice, PurchaseTransaction,
    PaymentRecord, InventoryMovement, InventoryCount,
    TaxRecord, AccountsReceivable, AccountsPayable,
    InvoicePaymentStatus, PaymentType, TaxType, FilingStatus,
    MovementItemType, MovementType,
)


@pytest.fixture()
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def make_sales_invoice(**overrides):
    defaults = dict(
        invoice_number="INV-2026-0001",
        customer_code="CUST-001",
        customer_name="永春牧場",
        invoice_date=date(2026, 6, 1),
        due_date=date(2026, 7, 1),
    )
    defaults.update(overrides)
    return SalesInvoice(**defaults)


class TestSalesInvoice:
    def test_line_amount_computation(self, session):
        inv = make_sales_invoice()
        line = SalesTransaction(
            product_code="PROD-001", product_name="維A 100ml",
            quantity=10, unit="瓶", unit_price=500, tax_rate=5.0,
            cost_per_unit=300, line_amount=0,
        )
        line.compute_amounts()
        assert line.line_amount == 5000
        assert line.tax_amount == 250
        assert line.line_total == 5250
        assert line.gross_profit == 2000

        inv.lines.append(line)
        inv.recalc_totals()
        session.add(inv)
        session.commit()
        assert inv.total_amount_with_tax == 5250
        assert inv.payment_status == InvoicePaymentStatus.UNPAID

    def test_payment_status_transitions(self, session):
        inv = make_sales_invoice()
        line = SalesTransaction(
            product_code="P", product_name="p", quantity=1, unit="瓶",
            unit_price=1000, tax_rate=5.0, line_amount=0)
        line.compute_amounts()
        inv.lines.append(line)

        inv.paid_amount = 500
        inv.recalc_totals()
        assert inv.payment_status == InvoicePaymentStatus.PARTIAL
        assert inv.remaining_balance == 550

        inv.paid_amount = 1050
        inv.recalc_totals()
        assert inv.payment_status == InvoicePaymentStatus.PAID
        assert inv.remaining_balance == 0

    def test_invoice_number_unique(self, session):
        session.add(make_sales_invoice())
        session.commit()
        session.add(make_sales_invoice())
        with pytest.raises(IntegrityError):
            session.commit()


class TestPurchaseInvoice:
    def test_supplier_invoice_unique_pair(self, session):
        kwargs = dict(
            invoice_number="SUP-INV-01", supplier_code="SUP-001",
            supplier_name="原廠A", invoice_date=date(2026, 6, 1),
            due_date=date(2026, 7, 1))
        session.add(PurchaseInvoice(**kwargs))
        session.commit()
        # 不同供應商同號碼可以
        session.add(PurchaseInvoice(**{**kwargs, "supplier_code": "SUP-002"}))
        session.commit()
        # 同供應商同號碼不行
        session.add(PurchaseInvoice(**kwargs))
        with pytest.raises(IntegrityError):
            session.commit()

    def test_recalc_totals(self, session):
        inv = PurchaseInvoice(
            invoice_number="SUP-INV-02", supplier_code="SUP-001",
            supplier_name="原廠A", invoice_date=date(2026, 6, 1),
            due_date=date(2026, 7, 1))
        line = PurchaseTransaction(
            bulk_item_code="BULK-001", bulk_item_name="維A原裝桶",
            bulk_batch_number="B-001", quantity=2, unit="桶",
            unit_price=10000, tax_rate=5.0, line_amount=0)
        line.compute_amounts()
        inv.lines.append(line)
        inv.recalc_totals()
        session.add(inv)
        session.commit()
        assert inv.total_amount_pretax == 20000
        assert inv.total_tax_amount == 1000
        assert inv.total_amount_with_tax == 21000


class TestPaymentRecord:
    def test_create_receipt(self, session):
        p = PaymentRecord(
            payment_number="PAY-0001",
            payment_type=PaymentType.RECEIPT_FROM_CUSTOMER,
            transaction_date=date(2026, 6, 10),
            reference_type="INVOICE", reference_id=1,
            supplier_or_customer_code="CUST-001",
            supplier_or_customer_name="永春牧場",
            amount=5250, payment_method="TRANSFER")
        session.add(p)
        session.commit()
        assert p.id is not None


class TestInventoryMovementAndCount:
    def test_movement_ledger(self, session):
        m = InventoryMovement(
            movement_date=date(2026, 6, 1),
            item_type=MovementItemType.PRODUCT,
            item_code="PROD-001", item_name="維A 100ml",
            batch_number="P-B001", movement_type=MovementType.OUT,
            quantity_change=-10, unit_price=300, amount=-3000,
            balance_before=100, balance_after=90,
            reference_type="SO", reference_id=7)
        session.add(m)
        session.commit()
        assert m.balance_after == 90

    def test_count_variance(self, session):
        c = InventoryCount(
            count_number="CNT-2026-06", count_date=date(2026, 6, 30),
            item_code="PROD-001", item_name="維A 100ml",
            account_balance=90, physical_count=88, variance=0,
            unit_price=300)
        c.compute_variance()
        session.add(c)
        session.commit()
        assert c.variance == -2
        assert c.variance_amount == -600


class TestTaxRecord:
    def test_period_type_unique(self, session):
        session.add(TaxRecord(tax_period="2026-06", tax_type=TaxType.VAT,
                              total_sales_tax=650, total_purchase_tax=1000,
                              net_tax_payable=-350))
        session.commit()
        session.add(TaxRecord(tax_period="2026-06", tax_type=TaxType.VAT))
        with pytest.raises(IntegrityError):
            session.commit()


class TestAccounts:
    def test_receivable_overdue(self, session):
        inv = make_sales_invoice()
        session.add(inv)
        session.flush()
        ar = AccountsReceivable(
            customer_code=inv.customer_code, customer_name=inv.customer_name,
            sales_invoice_id=inv.id, invoice_number=inv.invoice_number,
            original_amount=5250, paid_amount=0, outstanding_amount=5250,
            invoice_date=inv.invoice_date, due_date=inv.due_date)
        ar.refresh_overdue(as_of=date(2026, 7, 11))
        assert ar.overdue_status == "OVERDUE"
        assert ar.days_overdue == 10
        ar.refresh_overdue(as_of=date(2026, 6, 15))
        assert ar.overdue_status == "ON_TIME"
        session.add(ar)
        session.commit()
        assert inv.receivable is ar

    def test_payable_on_time_when_paid(self, session):
        inv = PurchaseInvoice(
            invoice_number="SUP-INV-03", supplier_code="SUP-001",
            supplier_name="原廠A", invoice_date=date(2026, 5, 1),
            due_date=date(2026, 5, 31))
        session.add(inv)
        session.flush()
        ap = AccountsPayable(
            supplier_code="SUP-001", supplier_name="原廠A",
            purchase_invoice_id=inv.id, invoice_number=inv.invoice_number,
            original_amount=21000, paid_amount=21000, outstanding_amount=0,
            invoice_date=inv.invoice_date, due_date=inv.due_date)
        ap.refresh_overdue(as_of=date(2026, 7, 1))  # 已付清就不算逾期
        assert ap.overdue_status == "ON_TIME"
        session.add(ap)
        session.commit()
