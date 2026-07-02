"""AccountingViewModel 單元測試 — 發票/收付款/報表流程。"""
import sys
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models import Base  # noqa: E402
from models.accounting import (  # noqa: E402
    InvoicePaymentStatus, PaymentType, FilingStatus, TaxRecord, TaxType,
)
from viewmodels.accounting_vm import AccountingViewModel  # noqa: E402


@pytest.fixture()
def vm():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield AccountingViewModel(s)
    s.close()


def sales_header(n="INV-0001", d=date(2026, 6, 1)):
    return dict(invoice_number=n, customer_code="CUST-001",
                customer_name="永春牧場", invoice_date=d,
                due_date=date(2026, 7, 1))


def sales_line(qty=10, price=500, cost=300):
    return dict(product_code="PROD-001", product_name="維A 100ml",
                quantity=qty, unit="瓶", unit_price=price,
                tax_rate=5.0, cost_per_unit=cost)


def purchase_header(n="SUP-INV-01", d=date(2026, 6, 2)):
    return dict(invoice_number=n, supplier_code="SUP-001",
                supplier_name="原廠A", invoice_date=d,
                due_date=date(2026, 7, 2))


def purchase_line(qty=2, price=10000):
    return dict(bulk_item_code="BULK-001", bulk_item_name="維A原裝桶",
                bulk_batch_number="B-001", quantity=qty, unit="桶",
                unit_price=price, tax_rate=5.0)


class TestInvoiceCreation:
    def test_sales_invoice_creates_receivable(self, vm):
        inv = vm.create_sales_invoice(sales_header(), [sales_line()])
        assert inv.total_amount_with_tax == 5250
        assert inv.receivable.outstanding_amount == 5250
        assert inv.receivable.overdue_status in ("ON_TIME", "OVERDUE")

    def test_purchase_invoice_creates_payable(self, vm):
        inv = vm.create_purchase_invoice(purchase_header(), [purchase_line()])
        assert inv.total_amount_with_tax == 21000
        assert inv.payable.outstanding_amount == 21000

    def test_empty_lines_rejected(self, vm):
        with pytest.raises(ValueError):
            vm.create_sales_invoice(sales_header(), [])


class TestPayments:
    def test_partial_then_full_receipt(self, vm):
        inv = vm.create_sales_invoice(sales_header(), [sales_line()])
        vm.record_payment(dict(
            payment_number="PAY-0001",
            payment_type=PaymentType.RECEIPT_FROM_CUSTOMER,
            transaction_date=date(2026, 6, 10),
            reference_id=inv.id, amount=2000, payment_method="TRANSFER"))
        assert inv.payment_status == InvoicePaymentStatus.PARTIAL
        assert inv.receivable.outstanding_amount == 3250

        vm.record_payment(dict(
            payment_number="PAY-0002", payment_type="RECEIPT_FROM_CUSTOMER",
            reference_id=inv.id, amount=3250))
        assert inv.payment_status == InvoicePaymentStatus.PAID
        assert inv.receivable.outstanding_amount == 0

    def test_overpayment_rejected(self, vm):
        inv = vm.create_sales_invoice(sales_header(), [sales_line()])
        with pytest.raises(ValueError, match="超過未結餘額"):
            vm.record_payment(dict(
                payment_number="PAY-0003",
                payment_type=PaymentType.RECEIPT_FROM_CUSTOMER,
                reference_id=inv.id, amount=99999))

    def test_supplier_payment_updates_payable(self, vm):
        inv = vm.create_purchase_invoice(purchase_header(), [purchase_line()])
        vm.record_payment(dict(
            payment_number="PAY-0004",
            payment_type=PaymentType.PAYMENT_TO_SUPPLIER,
            reference_id=inv.id, amount=21000))
        assert inv.payment_status == InvoicePaymentStatus.PAID
        assert inv.payable.outstanding_amount == 0


class TestReports:
    def test_daily_sales_report(self, vm):
        vm.create_sales_invoice(sales_header("INV-0001"), [sales_line()])
        vm.create_sales_invoice(sales_header("INV-0002"), [sales_line(qty=2, price=4000, cost=2500)])
        vm.create_sales_invoice(
            sales_header("INV-0003", d=date(2026, 6, 2)), [sales_line()])  # 不同日，排除

        rpt = vm.daily_sales_report(date(2026, 6, 1))
        assert rpt["totals"]["invoice_count"] == 2
        assert rpt["totals"]["total_pretax"] == 13000
        assert rpt["totals"]["total_tax"] == 650
        assert rpt["totals"]["total_withtax"] == 13650
        assert rpt["totals"]["gross_profit"] == 5000

    def test_monthly_tax_summary_and_save(self, vm):
        vm.create_sales_invoice(sales_header(), [sales_line()])          # 銷項稅 250
        vm.create_purchase_invoice(purchase_header(), [purchase_line()])  # 進項稅 1000
        summary = vm.monthly_tax_summary("2026-06", save=True)
        assert summary["total_sales_tax"] == 250
        assert summary["total_purchase_tax"] == 1000
        assert summary["net_tax_payable"] == -750

        # 再存一次 = 更新同一筆 DRAFT
        vm.monthly_tax_summary("2026-06", save=True)
        recs = vm.session.query(TaxRecord).all()
        assert len(recs) == 1

        # 已申報就不可覆寫
        recs[0].filing_status = FilingStatus.FILED
        with pytest.raises(ValueError, match="已申報"):
            vm.monthly_tax_summary("2026-06", save=True)

    def test_ar_ap_lists(self, vm):
        inv = vm.create_sales_invoice(sales_header(), [sales_line()])
        vm.create_purchase_invoice(purchase_header(), [purchase_line()])
        ars = vm.receivables()
        aps = vm.payables()
        assert len(ars) == 1 and ars[0]["outstanding_amount"] == 5250
        assert len(aps) == 1 and aps[0]["outstanding_amount"] == 21000

        vm.record_payment(dict(
            payment_number="PAY-0005",
            payment_type=PaymentType.RECEIPT_FROM_CUSTOMER,
            reference_id=inv.id, amount=5250))
        assert vm.receivables() == []  # 已結清
        assert len(vm.receivables(outstanding_only=False)) == 1
