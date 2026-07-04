"""報表測試 — ReportViewModel 單元 + /api/reports/* 整合(規格 §6 M5)。"""
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models import Base  # noqa: E402
from models.enums import (  # noqa: E402
    ProductType, StorageType, PackageType, OrderStatus, PaymentStatus,
)
from models.inventory import BulkItem, BulkBatch  # noqa: E402
from models.product import Product  # noqa: E402
from models.partner import Customer  # noqa: E402
from models.order import SalesOrder, SalesOrderItem  # noqa: E402
from viewmodels.inventory_vm import InventoryViewModel  # noqa: E402
from viewmodels.accounting_vm import AccountingViewModel  # noqa: E402
from viewmodels.report_vm import ReportViewModel  # noqa: E402


@pytest.fixture()
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


@pytest.fixture()
def seeded(session):
    """原裝 2 桶 @10000(效期近)→ 6 月分裝 1 桶 → 7 月分裝 1 桶、售出 4 瓶。

    產品換算率 10 瓶/桶 → 分裝品成本 1000/瓶;售價 1500/瓶。
    """
    ivm = InventoryViewModel(session)

    bulk = BulkItem(code="BULK-001", name="維A原裝桶", unit="桶")
    session.add(bulk)
    session.flush()
    product = Product(
        code="PROD-001", name="維A 100ml", unit="瓶",
        product_type=ProductType.SUPPLEMENT, storage_type=StorageType.ROOM_TEMP,
        package_type=PackageType.BOTTLE, bulk_item_id=bulk.id,
        units_per_bulk=10, selling_price=1500, reorder_point=20,
        manufacturer="", shelf_life_months=0)
    customer = Customer(
        code="CUST-001", name="永春牧場", contact_person="", phone="",
        address="", credit_term_days=0, credit_limit=5000)
    session.add_all([product, customer])
    session.flush()

    ok, _ = ivm.receive_bulk(
        bulk_code="BULK-001", batch_number="B-001", quantity=2,
        unit_cost=10000, expiry_date=datetime(2026, 8, 1),
        transaction_date=datetime(2026, 6, 5))
    assert ok
    batch = session.query(BulkBatch).one()

    ok, _, _ = ivm.repack(
        bulk_batch_id=batch.id, product_id=product.id, bulk_qty=1,
        output_batch_number="P-B001", expiry_date=datetime(2026, 8, 1),
        transaction_date=datetime(2026, 6, 15))
    assert ok
    ok, _, _ = ivm.repack(
        bulk_batch_id=batch.id, product_id=product.id, bulk_qty=1,
        output_batch_number="P-B002", expiry_date=datetime(2026, 8, 1),
        transaction_date=datetime(2026, 7, 5))
    assert ok

    so = SalesOrder(
        so_number="SO-0001", customer_id=customer.id,
        order_date=datetime(2026, 7, 10), delivery_date=datetime(2026, 7, 10),
        status=OrderStatus.SHIPPED, total_amount=6000,
        payment_status=PaymentStatus.PENDING)
    session.add(so)
    session.flush()
    ok, _, allocations = ivm.issue_sales(
        product_code="PROD-001", quantity=4, reference_id=so.id,
        transaction_date=datetime(2026, 7, 10))
    assert ok
    for a in allocations:
        session.add(SalesOrderItem(
            so_id=so.id, product_id=product.id, batch_id=a["batch_id"],
            quantity=a["quantity"], unit_price=1500,
            total_price=a["quantity"] * 1500, shipped_quantity=a["quantity"]))
    session.commit()
    return dict(session=session, product=product, customer=customer)


class TestMonthlyInventoryReport:
    def test_current_month_buckets(self, seeded):
        rpt = ReportViewModel(seeded["session"]).monthly_inventory_report("2026-07")
        assert len(rpt["rows"]) == 1
        r = rpt["rows"][0]
        assert r["product_code"] == "PROD-001"
        assert r["open_qty"] == 10            # 6 月分裝產出
        assert r["open_amount"] == 10000
        assert r["in_qty"] == 10              # 7 月分裝產出
        assert r["in_amount"] == 10000
        assert r["out_qty"] == 4              # 7 月銷貨
        assert r["out_amount"] == 4000        # 成本計價
        assert r["closing_qty"] == 16
        assert r["closing_amount"] == 16000
        assert rpt["totals"]["closing_amount"] == 16000

    def test_prior_month_has_no_opening(self, seeded):
        r = ReportViewModel(seeded["session"]).monthly_inventory_report("2026-06")["rows"][0]
        assert r["open_qty"] == 0
        assert r["in_qty"] == 10
        assert r["closing_qty"] == 10

    def test_bad_period_raises(self, session):
        with pytest.raises(ValueError):
            ReportViewModel(session).monthly_inventory_report("garbage")


class TestStockSnapshot:
    def test_flags_and_values(self, seeded):
        rows = ReportViewModel(seeded["session"]).stock_snapshot()
        assert len(rows) == 1
        r = rows[0]
        assert r["quantity"] == 16
        assert r["stock_value"] == 16000
        assert r["batch_count"] == 2
        assert r["below_reorder"] is True     # 16 < 再訂購點 20
        assert set(r["near_expiry_batches"]) == {"P-B001", "P-B002"}  # 效期 2026-08-01

    def test_zero_reorder_point_not_flagged(self, seeded):
        seeded["product"].reorder_point = 0
        seeded["session"].flush()
        r = ReportViewModel(seeded["session"]).stock_snapshot()[0]
        assert r["below_reorder"] is False


class TestSalesProfitReport:
    def test_customer_sku_grouping_and_margin(self, seeded):
        rpt = ReportViewModel(seeded["session"]).sales_profit_report(
            date(2026, 7, 1), date(2026, 7, 31))
        assert len(rpt["rows"]) == 1
        r = rpt["rows"][0]
        assert (r["customer_code"], r["product_code"]) == ("CUST-001", "PROD-001")
        assert r["quantity"] == 4
        assert r["revenue"] == 6000           # 4 × 1500
        assert r["cost"] == 4000              # 4 × 1000(批次分攤)
        assert r["gross_profit"] == 2000
        assert r["margin_pct"] == 33.3
        assert rpt["totals"]["gross_profit"] == 2000

    def test_range_excludes_other_months(self, seeded):
        rpt = ReportViewModel(seeded["session"]).sales_profit_report(
            date(2026, 6, 1), date(2026, 6, 30))
        assert rpt["rows"] == []


class TestRepackOutputReport:
    def test_variance_and_cost_conservation(self, seeded):
        rows = ReportViewModel(seeded["session"]).repack_output_report(
            date(2026, 1, 1), date(2026, 12, 31))
        assert len(rows) == 2
        for r in rows:
            assert r["bulk_qty_consumed"] == 1
            assert r["expected_output"] == 10
            assert r["output_qty"] == 10
            assert r["variance"] == 0
            assert r["bulk_cost"] == 10000
            assert r["output_value"] == 10000  # 成本守恆(規格 §5.5)


class TestCreditAlerts:
    def test_over_limit_flagged(self, seeded):
        s = seeded["session"]
        # 開發票 5250 > 信用額度 5000
        AccountingViewModel(s).create_sales_invoice(
            dict(invoice_number="INV-0001", customer_code="CUST-001",
                 customer_name="永春牧場", invoice_date=date(2026, 7, 1),
                 due_date=date(2026, 8, 1)),
            [dict(product_code="PROD-001", product_name="維A 100ml",
                  quantity=10, unit="瓶", unit_price=500, tax_rate=5.0)])
        rows = ReportViewModel(s).credit_alerts()
        assert len(rows) == 1
        r = rows[0]
        assert r["outstanding"] == 5250
        assert r["over_limit"] is True
        assert r["available"] == -250

    def test_no_limit_never_flagged(self, seeded):
        s = seeded["session"]
        s.add(Customer(code="CUST-002", name="無額度客戶", contact_person="",
                       phone="", address="", credit_term_days=0, credit_limit=0))
        s.flush()
        rows = ReportViewModel(s).credit_alerts()
        by_code = {r["customer_code"]: r for r in rows}
        assert by_code["CUST-002"]["over_limit"] is False
        assert by_code["CUST-002"]["available"] is None
        # over_only 過濾:兩位客戶都未超額 → 空
        assert ReportViewModel(s).credit_alerts(over_only=True) == []


# ------------------------------------------------------------------ API 層

def seed_via_api(client):
    """走 API 流程:供應商→原物料→進貨→產品→分裝→客戶→銷貨。"""
    sid = client.post("/api/suppliers", json=dict(
        code="SUP-001", name="原廠A")).json()["id"]
    client.post("/api/bulk-items", json=dict(
        code="BULK-001", name="維A原裝桶", unit="桶"))
    expiry = (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d")
    client.post("/api/purchase-orders", json=dict(
        supplier_id=sid, bulk_code="BULK-001", batch_number="B-001",
        quantity=2, unit_cost=10000, expiry_date=expiry))
    bulk_item_id = client.get("/api/bulk-items").json()[0]["id"]
    pid = client.post("/api/products", json=dict(
        code="PROD-001", name="維A 100ml", unit="瓶", bulk_item_id=bulk_item_id,
        units_per_bulk=10, selling_price=1500)).json()["id"]
    batch_id = client.get("/api/bulk-batches").json()[0]["id"]
    client.post("/api/repack", json=dict(
        bulk_batch_id=batch_id, product_id=pid, bulk_qty=1,
        output_batch_number="P-B001", expiry_date=expiry))
    cid = client.post("/api/customers", json=dict(
        code="CUST-001", name="永春牧場")).json()["id"]
    client.post("/api/sales-orders", json=dict(
        customer_id=cid, product_code="PROD-001", quantity=4))


class TestReportEndpoints:
    def test_all_report_endpoints_return_data(self, client):
        seed_via_api(client)
        period = datetime.now().strftime("%Y-%m")
        today = date.today().isoformat()

        monthly = client.get(
            f"/api/reports/monthly-inventory?period={period}").json()
        assert monthly["rows"][0]["closing_qty"] == 6  # 產出 10 − 銷 4

        snapshot = client.get("/api/reports/stock-snapshot").json()
        assert snapshot[0]["quantity"] == 6
        assert snapshot[0]["near_expiry_batches"] == ["P-B001"]  # 60 天效期

        profit = client.get(
            f"/api/reports/sales-profit?start={today}&end={today}").json()
        assert profit["totals"]["revenue"] == 6000
        assert profit["totals"]["gross_profit"] == 2000

        repack = client.get(
            f"/api/reports/repack-output?start={today}&end={today}").json()
        assert len(repack) == 1 and repack[0]["variance"] == 0

        alerts = client.get("/api/reports/credit-alerts").json()
        assert alerts[0]["customer_code"] == "CUST-001"

    def test_invalid_params_return_400(self, client):
        assert client.get(
            "/api/reports/monthly-inventory?period=garbage").status_code == 400
        assert client.get(
            "/api/reports/sales-profit?start=bad&end=2026-07-31").status_code == 400
        assert client.get(
            "/api/reports/repack-output?start=2026-07-01&end=bad").status_code == 400
