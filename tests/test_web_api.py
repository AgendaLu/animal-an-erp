"""REST API 整合測試 — FastAPI TestClient + 每測試獨立暫存 DB。

`client` fixture 見 conftest.py:先 monkeypatch `web.app.DB_PATH` 到 tmp_path,
確保絕不觸碰 data/animal_an.db 正式資料庫。
"""
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import web.app as webapp  # noqa: E402
from models import db_manager  # noqa: E402
from models.accounting import TaxRecord, FilingStatus  # noqa: E402


class TestDbPathResolution:
    """打包(frozen)與環境變數下的 DB 路徑決議 — 規格 §7 執行檔與 .db 分離。"""

    def test_env_var_wins(self, monkeypatch):
        monkeypatch.setenv("ANIMAL_AN_DB", "/somewhere/custom.db")
        assert webapp._default_db_path() == Path("/somewhere/custom.db")

    def test_frozen_uses_executable_dir(self, monkeypatch, tmp_path):
        monkeypatch.delenv("ANIMAL_AN_DB", raising=False)
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", str(tmp_path / "animal-an-erp"))
        assert webapp._default_db_path() == tmp_path / "data" / "animal_an.db"

    def test_dev_uses_project_data_dir(self, monkeypatch):
        monkeypatch.delenv("ANIMAL_AN_DB", raising=False)
        p = webapp._default_db_path()
        assert p.name == "animal_an.db"
        assert p.parent.name == "data"


# ------------------------------------------------------------------ helpers

SALES_HEADER = dict(invoice_number="INV-0001", customer_code="CUST-001",
                    customer_name="永春牧場", invoice_date="2026-06-01",
                    due_date="2026-07-01")
SALES_LINE = dict(product_code="PROD-001", product_name="維A 100ml",
                  quantity=10, unit="瓶", unit_price=500,
                  tax_rate=5.0, cost_per_unit=300)
PURCHASE_HEADER = dict(invoice_number="SUP-INV-01", supplier_code="SUP-001",
                       supplier_name="原廠A", invoice_date="2026-06-02",
                       due_date="2026-07-02")
PURCHASE_LINE = dict(bulk_item_code="BULK-001", bulk_item_name="維A原裝桶",
                     bulk_batch_number="B-001", quantity=2, unit="桶",
                     unit_price=10000, tax_rate=5.0)


def post_sales_invoice(client, number="INV-0001", **line_overrides):
    header = {**SALES_HEADER, "invoice_number": number}
    line = {**SALES_LINE, **line_overrides}
    r = client.post("/api/accounting/sales-invoices",
                    json={"header": header, "lines": [line]})
    assert r.status_code == 200, r.text
    return r.json()


def post_purchase_invoice(client, number="SUP-INV-01"):
    header = {**PURCHASE_HEADER, "invoice_number": number}
    r = client.post("/api/accounting/purchase-invoices",
                    json={"header": header, "lines": [PURCHASE_LINE]})
    assert r.status_code == 200, r.text
    return r.json()


def create_entity(client, entity, payload):
    r = client.post(f"/api/{entity}", json=payload)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def seed_inventory(client, expiry_days=365, po_qty=2, unit_cost=10000,
                   units_per_bulk=10):
    """供應商 → 原物料 → 進貨 → 產品(含換算率),回傳各 id。"""
    supplier_id = create_entity(client, "suppliers", dict(
        code="SUP-001", name="原廠A", supplier_type="MANUFACTURER"))
    create_entity(client, "bulk-items", dict(
        code="BULK-001", name="維A原裝桶", unit="桶"))
    expiry = (datetime.now() + timedelta(days=expiry_days)).strftime("%Y-%m-%d")
    r = client.post("/api/purchase-orders", json=dict(
        supplier_id=supplier_id, bulk_code="BULK-001", batch_number="B-001",
        quantity=po_qty, unit_cost=unit_cost, expiry_date=expiry))
    assert r.status_code == 200, r.text
    batches = client.get("/api/bulk-batches").json()
    assert len(batches) == 1
    bulk_item_id = client.get("/api/bulk-items").json()[0]["id"]
    product_id = create_entity(client, "products", dict(
        code="PROD-001", name="維A 100ml", unit="瓶",
        bulk_item_id=bulk_item_id, units_per_bulk=units_per_bulk,
        selling_price=500))
    customer_id = create_entity(client, "customers", dict(
        code="CUST-001", name="永春牧場", customer_type="PIG_FARM"))
    return dict(supplier_id=supplier_id, bulk_batch_id=batches[0]["id"],
                product_id=product_id, customer_id=customer_id,
                po_message=r.json()["message"], expiry=expiry)


# ------------------------------------------------------------------ 會計發票

class TestAccountingInvoiceAPI:
    def test_create_sales_invoice_returns_totals(self, client):
        body = post_sales_invoice(client)
        assert body["invoice_number"] == "INV-0001"
        assert body["total_amount_with_tax"] == 5250

        ars = client.get("/api/accounting/receivables").json()
        assert len(ars) == 1
        assert ars[0]["invoice_number"] == "INV-0001"
        assert ars[0]["outstanding_amount"] == 5250

    def test_create_purchase_invoice_creates_payable(self, client):
        body = post_purchase_invoice(client)
        assert body["total_amount_with_tax"] == 21000
        aps = client.get("/api/accounting/payables").json()
        assert len(aps) == 1 and aps[0]["outstanding_amount"] == 21000

    def test_empty_lines_rejected(self, client):
        r = client.post("/api/accounting/sales-invoices",
                        json={"header": SALES_HEADER, "lines": []})
        assert r.status_code == 400
        assert "至少" in r.json()["detail"]

    @pytest.mark.xfail(strict=False,
                       reason="重複發票號目前回 500(IntegrityError 未攔),應為 4xx")
    def test_duplicate_invoice_number_client_error(self, client):
        post_sales_invoice(client)
        r = client.post("/api/accounting/sales-invoices",
                        json={"header": SALES_HEADER, "lines": [SALES_LINE]})
        assert r.status_code == 400


# ------------------------------------------------------------------ 收付款

class TestPaymentAPI:
    def test_receipt_partial_then_full(self, client):
        inv = post_sales_invoice(client)
        r = client.post("/api/accounting/payments", json=dict(
            payment_number="PAY-0001", payment_type="RECEIPT_FROM_CUSTOMER",
            transaction_date="2026-06-10", reference_id=inv["id"],
            amount=2000, payment_method="TRANSFER"))
        assert r.status_code == 200, r.text
        ars = client.get("/api/accounting/receivables").json()
        assert ars[0]["outstanding_amount"] == 3250

        r = client.post("/api/accounting/payments", json=dict(
            payment_number="PAY-0002", payment_type="RECEIPT_FROM_CUSTOMER",
            reference_id=inv["id"], amount=3250))
        assert r.status_code == 200, r.text
        assert client.get("/api/accounting/receivables").json() == []
        all_ars = client.get(
            "/api/accounting/receivables?outstanding_only=false").json()
        assert len(all_ars) == 1 and all_ars[0]["outstanding_amount"] == 0

    def test_supplier_payment_clears_payable(self, client):
        inv = post_purchase_invoice(client)
        r = client.post("/api/accounting/payments", json=dict(
            payment_number="PAY-0003", payment_type="PAYMENT_TO_SUPPLIER",
            reference_id=inv["id"], amount=21000))
        assert r.status_code == 200, r.text
        assert client.get("/api/accounting/payables").json() == []

    def test_overpayment_rejected(self, client):
        inv = post_sales_invoice(client)
        r = client.post("/api/accounting/payments", json=dict(
            payment_number="PAY-0004", payment_type="RECEIPT_FROM_CUSTOMER",
            reference_id=inv["id"], amount=99999))
        assert r.status_code == 400
        assert "超過未結餘額" in r.json()["detail"]

    def test_missing_amount_rejected(self, client):
        inv = post_sales_invoice(client)
        r = client.post("/api/accounting/payments", json=dict(
            payment_number="PAY-0005", payment_type="RECEIPT_FROM_CUSTOMER",
            reference_id=inv["id"]))
        assert r.status_code == 400

    def test_unknown_invoice_rejected(self, client):
        r = client.post("/api/accounting/payments", json=dict(
            payment_number="PAY-0006", payment_type="RECEIPT_FROM_CUSTOMER",
            reference_id=999, amount=100))
        assert r.status_code == 400
        assert "找不到" in r.json()["detail"]


# ------------------------------------------------------------------ 報表

class TestReportAPI:
    def test_daily_sales_report(self, client):
        post_sales_invoice(client, "INV-0001")
        post_sales_invoice(client, "INV-0002", quantity=2, unit_price=4000,
                           cost_per_unit=2500)
        rpt = client.get(
            "/api/accounting/reports/daily-sales?report_date=2026-06-01").json()
        assert rpt["totals"]["invoice_count"] == 2
        assert rpt["totals"]["total_withtax"] == 13650
        assert rpt["totals"]["gross_profit"] == 5000

    def test_tax_report_save_and_filed_lock(self, client):
        post_sales_invoice(client)      # 銷項稅 250
        post_purchase_invoice(client)   # 進項稅 1000
        r = client.get("/api/accounting/reports/tax?period=2026-06&save=true")
        assert r.status_code == 200
        assert r.json()["net_tax_payable"] == -750

        s = db_manager.get_session()
        try:
            rec = s.query(TaxRecord).one()
            rec.filing_status = FilingStatus.FILED
            s.commit()
        finally:
            s.close()

        # 已申報:save=true 拒絕,純查詢仍可
        r = client.get("/api/accounting/reports/tax?period=2026-06&save=true")
        assert r.status_code == 400 and "已申報" in r.json()["detail"]
        r = client.get("/api/accounting/reports/tax?period=2026-06")
        assert r.status_code == 200

    @pytest.mark.xfail(strict=False,
                       reason="無效日期參數目前回 500(ValueError 未攔),應為 4xx")
    def test_invalid_report_date_client_error(self, client):
        r = client.get("/api/accounting/reports/daily-sales?report_date=garbage")
        assert r.status_code == 400


# ------------------------------------------------------------------ 通用 CRUD

class TestGenericCrudAPI:
    def test_create_list_update_supplier(self, client):
        sid = create_entity(client, "suppliers", dict(
            code="SUP-001", name="原廠A", supplier_type="MANUFACTURER",
            phone="02-1234"))
        rows = client.get("/api/suppliers").json()
        assert len(rows) == 1
        assert rows[0]["supplier_type"] == "MANUFACTURER"  # enum 以名稱序列化
        assert rows[0]["phone"] == "02-1234"

        r = client.put(f"/api/suppliers/{sid}", json={"phone": "02-9999"})
        assert r.status_code == 200
        assert client.get("/api/suppliers").json()[0]["phone"] == "02-9999"

    def test_missing_code_or_name_rejected(self, client):
        r = client.post("/api/suppliers", json={"name": "無代號"})
        assert r.status_code == 400
        assert "必填" in r.json()["detail"]

    def test_unknown_entity_404(self, client):
        assert client.get("/api/widgets").status_code == 404
        assert client.post("/api/widgets", json={}).status_code == 404

    def test_update_nonexistent_404(self, client):
        r = client.put("/api/suppliers/9999", json={"phone": "x"})
        assert r.status_code == 404

    def test_bulk_item_enum_roundtrip(self, client):
        create_entity(client, "bulk-items", dict(
            code="BULK-X", name="冷藏藥桶", unit="桶",
            product_type="MEDICINE", storage_type="REFRIGERATED"))
        row = client.get("/api/bulk-items").json()[0]
        assert row["product_type"] == "MEDICINE"
        assert row["storage_type"] == "REFRIGERATED"


# ------------------------------------------------------------------ 進銷存流程

class TestInventoryFlowAPI:
    def test_full_purchase_repack_sales_flow(self, client):
        ids = seed_inventory(client)
        assert re.search(r"PO\d{8}-001", ids["po_message"])

        pos = client.get("/api/purchase-orders").json()
        assert len(pos) == 1 and pos[0]["total_amount"] == 20000

        # 分裝 1 桶 → 10 瓶
        r = client.post("/api/repack", json=dict(
            bulk_batch_id=ids["bulk_batch_id"], product_id=ids["product_id"],
            bulk_qty=1, output_batch_number="P-B001",
            expiry_date=ids["expiry"]))
        assert r.status_code == 200, r.text
        assert client.get("/api/bulk-batches").json()[0]["quantity"] == 1
        sellable = client.get("/api/sellable-batches").json()
        assert len(sellable) == 1 and sellable[0]["quantity"] == 10

        # FEFO 銷貨 4 瓶
        r = client.post("/api/sales-orders", json=dict(
            customer_id=ids["customer_id"], product_code="PROD-001",
            quantity=4))
        assert r.status_code == 200, r.text
        sos = client.get("/api/sales-orders").json()
        assert len(sos) == 1 and sos[0]["total_amount"] == 2000  # 標準售價 500
        assert client.get("/api/sellable-batches").json()[0]["quantity"] == 6

        val = client.get("/api/valuation").json()
        assert val["bulk_value"] == 10000  # 剩 1 桶 × 10000
        assert val["total_value"] == pytest.approx(
            val["bulk_value"] + val["sellable_value"])

    def test_po_missing_fields_rejected(self, client):
        sid = create_entity(client, "suppliers", dict(
            code="SUP-001", name="原廠A"))
        r = client.post("/api/purchase-orders", json=dict(
            supplier_id=sid, bulk_code="BULK-001", batch_number="B-001",
            quantity=2))
        assert r.status_code == 400
        assert "unit_cost" in r.json()["detail"]
        assert "expiry_date" in r.json()["detail"]

    def test_po_number_sequence(self, client):
        ids = seed_inventory(client)
        expiry = ids["expiry"]
        r = client.post("/api/purchase-orders", json=dict(
            supplier_id=ids["supplier_id"], bulk_code="BULK-001",
            batch_number="B-002", quantity=1, unit_cost=9000,
            expiry_date=expiry))
        assert r.status_code == 200
        assert re.search(r"PO\d{8}-002", r.json()["message"])

    def test_so_unknown_product_rejected(self, client):
        ids = seed_inventory(client)
        r = client.post("/api/sales-orders", json=dict(
            customer_id=ids["customer_id"], product_code="NOPE", quantity=1))
        assert r.status_code == 400
        assert "不存在" in r.json()["detail"]

    def test_so_insufficient_stock_rejected(self, client):
        ids = seed_inventory(client)
        client.post("/api/repack", json=dict(
            bulk_batch_id=ids["bulk_batch_id"], product_id=ids["product_id"],
            bulk_qty=1, output_batch_number="P-B001",
            expiry_date=ids["expiry"]))
        r = client.post("/api/sales-orders", json=dict(
            customer_id=ids["customer_id"], product_code="PROD-001",
            quantity=999))
        assert r.status_code == 400

    def test_adjust_validates_and_applies(self, client):
        ids = seed_inventory(client)
        r = client.post("/api/adjust", json=dict(
            bulk_batch_id=ids["bulk_batch_id"], quantity_delta=-999,
            reason="盤虧"))
        assert r.status_code == 400  # 不可調成負庫存

        r = client.post("/api/adjust", json=dict(
            bulk_batch_id=ids["bulk_batch_id"], quantity_delta=3,
            reason="盤盈"))
        assert r.status_code == 200
        assert client.get("/api/bulk-batches").json()[0]["quantity"] == 5

    def test_low_stock_alert(self, client):
        create_entity(client, "bulk-items", dict(
            code="BULK-LOW", name="快斷貨", unit="桶", min_quantity=5))
        rows = client.get("/api/low-stock").json()
        assert any(r["code"] == "BULK-LOW" for r in rows)

    def test_expiring_batches_within_window(self, client):
        seed_inventory(client, expiry_days=30)
        rows = client.get("/api/expiring").json()
        assert len(rows) == 1
        assert rows[0]["batch_number"] == "B-001"
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", rows[0]["expiry_date"])

    def test_expiring_excludes_far_future(self, client):
        seed_inventory(client, expiry_days=365)
        assert client.get("/api/expiring").json() == []
