"""FastAPI local web server — M3 management pages (spec v0.4).

完全離線：只綁 127.0.0.1，前端不引用任何 CDN／外部資源。
業務邏輯重用 M2 的 InventoryViewModel；本層只做 HTTP 與序列化。

Run:
    .venv/bin/python -m web.app
then open http://127.0.0.1:8000
"""
import os
import sys
from datetime import datetime, date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError

from models import db_manager
from models.inventory import BulkItem, BulkBatch, InventoryTransaction, RepackOrder
from models.product import Product, Batch
from models.partner import Supplier, Customer
from models.order import PurchaseOrder, SalesOrder, SalesOrderItem
from models.enums import (
    ProductType, StorageType, PackageType, OrderStatus, PaymentStatus,
    SupplierType, CustomerType,
)
from models.accounting import SalesInvoice, PurchaseInvoice, PaymentRecord
from viewmodels.inventory_vm import InventoryViewModel
from viewmodels.accounting_vm import AccountingViewModel
from viewmodels.report_vm import ReportViewModel

app = FastAPI(title="Animal-AN ERP", docs_url="/api/docs")

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

def _default_db_path() -> Path:
    """DB 路徑決議:env 覆寫 > 打包後執行檔同層 data/ > 開發時專案 data/。

    規格 §7:執行檔與 .db 分離,更新只換執行檔(data/ 不動)。
    """
    env = os.environ.get("ANIMAL_AN_DB")
    if env:
        return Path(env)
    if getattr(sys, "frozen", False):  # PyInstaller
        return Path(sys.executable).resolve().parent / "data" / "animal_an.db"
    return Path(__file__).resolve().parent.parent / "data" / "animal_an.db"


DB_PATH = _default_db_path()

ENUMS = {
    'ProductType': ProductType, 'StorageType': StorageType,
    'PackageType': PackageType, 'SupplierType': SupplierType,
    'CustomerType': CustomerType,
}


@app.on_event("startup")
def startup() -> None:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    db_manager.init_db(str(DB_PATH))


# ------------------------------------------------------------------ #
# Generic CRUD — field schema per entity: (name, kind, default-if-required)
# kind: str | float | int | bool | date | datetime | enum:<Name>
# ------------------------------------------------------------------ #
ENTITIES = {
    'bulk-items': (BulkItem, [
        ('code', 'str', None), ('name', 'str', None), ('unit', 'str', None),
        ('description', 'str', None),
        ('product_type', 'enum:ProductType', None),
        ('storage_type', 'enum:StorageType', None),
        ('quantity', 'float', 0), ('min_quantity', 'float', 0),
        ('min_temperature', 'float', None), ('max_temperature', 'float', None),
        ('shelf_life_months', 'int', None),
        ('registration_number', 'str', None),
        ('country_of_origin', 'str', None),
        ('is_active', 'bool', True),
    ]),
    'products': (Product, [
        ('code', 'str', None), ('name', 'str', None), ('unit', 'str', ''),
        ('product_type', 'enum:ProductType', ProductType.SUPPLEMENT),
        ('storage_type', 'enum:StorageType', StorageType.ROOM_TEMP),
        ('package_type', 'enum:PackageType', PackageType.BOTTLE),
        ('bulk_item_id', 'int', None), ('units_per_bulk', 'float', None),
        ('selling_price', 'float', None),
        ('spec', 'str', None), ('package_size', 'float', None),
        ('package_unit', 'str', None), ('units_per_package', 'float', None),
        ('dosage_form', 'str', None), ('concentration', 'str', None),
        ('active_ingredient', 'str', None), ('barcode', 'str', None),
        ('manufacturer', 'str', ''), ('registration_number', 'str', None),
        ('shelf_life_months', 'int', 0), ('reorder_point', 'float', 0),
        ('description', 'str', None), ('is_active', 'bool', True),
    ]),
    'suppliers': (Supplier, [
        ('code', 'str', None), ('name', 'str', None), ('short_name', 'str', None),
        ('supplier_type', 'enum:SupplierType', None), ('country', 'str', None),
        ('contact_person', 'str', ''), ('contact_title', 'str', None),
        ('phone', 'str', ''), ('mobile', 'str', None), ('fax', 'str', None),
        ('email', 'str', None), ('address', 'str', ''),
        ('tax_id', 'str', None), ('credit_term_days', 'int', 0),
        ('payment_method', 'str', None), ('currency', 'str', None),
        ('bank_name', 'str', None), ('bank_branch', 'str', None),
        ('bank_account', 'str', None), ('bank_swift', 'str', None),
        ('license_number', 'str', None), ('license_expiry', 'date', None),
        ('rating', 'str', None), ('notes', 'str', None),
        ('is_active', 'bool', True),
    ]),
    'customers': (Customer, [
        ('code', 'str', None), ('name', 'str', None), ('short_name', 'str', None),
        ('customer_type', 'enum:CustomerType', None),
        ('contact_person', 'str', ''), ('contact_title', 'str', None),
        ('phone', 'str', ''), ('mobile', 'str', None), ('fax', 'str', None),
        ('email', 'str', None), ('address', 'str', ''),
        ('billing_address', 'str', None), ('shipping_address', 'str', None),
        ('invoice_title', 'str', None), ('tax_id', 'str', None),
        ('credit_term_days', 'int', 0), ('credit_limit', 'float', 0),
        ('current_balance', 'float', 0), ('sales_rep', 'str', None),
        ('farm_license', 'str', None), ('notes', 'str', None),
        ('is_active', 'bool', True),
    ]),
}


def _dump(obj, fields):
    row = {'id': obj.id}
    for name, kind, _ in fields:
        v = getattr(obj, name)
        if v is None:
            row[name] = None
        elif kind.startswith('enum:'):
            row[name] = v.name
        elif kind in ('date', 'datetime'):
            row[name] = v.isoformat()[:10]
        else:
            row[name] = v
    return row


def _coerce(value, kind, default):
    if value in (None, ''):
        return default
    if kind == 'str':
        return str(value)
    if kind == 'float':
        return float(value)
    if kind == 'int':
        return int(value)
    if kind == 'bool':
        return bool(value)
    if kind == 'date':
        return date.fromisoformat(str(value)[:10])
    if kind == 'datetime':
        return datetime.fromisoformat(str(value))
    if kind.startswith('enum:'):
        cls = ENUMS[kind.split(':')[1]]
        return cls[value] if isinstance(value, str) else value
    return value


# ------------------------------------------------------------------ #
# 進貨單：PO header + 原裝入庫
# ------------------------------------------------------------------ #
def _next_number(s, model, col, prefix):
    last = s.query(model).filter(col.like(f"{prefix}%")).order_by(col.desc()).first()
    seq = int(getattr(last, col.key).rsplit('-', 1)[1]) + 1 if last else 1
    return f"{prefix}{seq:03d}"


@app.get("/api/purchase-orders")
def list_purchase_orders():
    s = db_manager.get_session()
    try:
        rows = []
        for po in s.query(PurchaseOrder).order_by(PurchaseOrder.id.desc()).limit(100):
            rows.append({
                'id': po.id, 'po_number': po.po_number,
                'supplier': po.supplier.name if po.supplier else '',
                'order_date': po.order_date.isoformat()[:10],
                'total_amount': po.total_amount,
                'status': po.status.name, 'notes': po.notes,
            })
        return rows
    finally:
        s.close()


@app.post("/api/purchase-orders")
def create_purchase_order(payload: dict = Body(...)):
    """建立進貨單：PO header + receive_bulk（效期/批次成本必填）"""
    s = db_manager.get_session()
    try:
        required = ['supplier_id', 'bulk_code', 'batch_number', 'quantity',
                    'unit_cost', 'expiry_date']
        missing = [k for k in required if payload.get(k) in (None, '')]
        if missing:
            raise HTTPException(400, f"缺少必填欄位: {', '.join(missing)}")

        qty = float(payload['quantity'])
        cost = float(payload['unit_cost'])
        po = PurchaseOrder(
            po_number=_next_number(
                s, PurchaseOrder, PurchaseOrder.po_number,
                f"PO{datetime.now():%Y%m%d}-"),
            supplier_id=int(payload['supplier_id']),
            order_date=datetime.now(),
            expected_delivery=datetime.now(),
            status=OrderStatus.DELIVERED,
            total_amount=qty * cost,
            payment_status=PaymentStatus.PENDING,
            notes=payload.get('notes'),
        )
        s.add(po)
        s.flush()

        vm = InventoryViewModel(s)
        ok, msg = vm.receive_bulk(
            bulk_code=payload['bulk_code'],
            batch_number=payload['batch_number'],
            quantity=qty,
            unit_cost=cost,
            expiry_date=datetime.fromisoformat(payload['expiry_date']),
            lot_number=payload.get('lot_number'),
            supplier_id=int(payload['supplier_id']),
            reference_id=po.id,
            notes=payload.get('notes'),
        )
        if not ok:
            s.rollback()
            raise HTTPException(400, msg)
        return {"message": f"進貨單 {po.po_number} 建立，{msg}"}
    except HTTPException:
        raise
    except Exception as e:
        s.rollback()
        raise HTTPException(400, f"進貨失敗: {e}")
    finally:
        s.close()


# ------------------------------------------------------------------ #
# 銷貨單：SO header + FEFO 出庫 + 明細
# ------------------------------------------------------------------ #
@app.get("/api/sales-orders")
def list_sales_orders():
    s = db_manager.get_session()
    try:
        rows = []
        for so in s.query(SalesOrder).order_by(SalesOrder.id.desc()).limit(100):
            rows.append({
                'id': so.id, 'so_number': so.so_number,
                'customer': so.customer.name if so.customer else '',
                'order_date': so.order_date.isoformat()[:10],
                'total_amount': so.total_amount,
                'status': so.status.name, 'notes': so.notes,
            })
        return rows
    finally:
        s.close()


@app.post("/api/sales-orders")
def create_sales_order(payload: dict = Body(...)):
    """建立銷貨單：SO header + FEFO 出庫 + 依分配建立明細"""
    s = db_manager.get_session()
    try:
        required = ['customer_id', 'product_code', 'quantity']
        missing = [k for k in required if payload.get(k) in (None, '')]
        if missing:
            raise HTTPException(400, f"缺少必填欄位: {', '.join(missing)}")

        product = s.query(Product).filter(
            Product.code == payload['product_code']).first()
        if not product:
            raise HTTPException(400, f"產品 {payload['product_code']} 不存在")

        qty = float(payload['quantity'])
        unit_price = float(payload.get('unit_price') or product.selling_price or 0)

        so = SalesOrder(
            so_number=_next_number(
                s, SalesOrder, SalesOrder.so_number,
                f"SO{datetime.now():%Y%m%d}-"),
            customer_id=int(payload['customer_id']),
            order_date=datetime.now(),
            delivery_date=datetime.now(),
            status=OrderStatus.SHIPPED,
            total_amount=qty * unit_price,
            payment_status=PaymentStatus.PENDING,
            notes=payload.get('notes'),
        )
        s.add(so)
        s.flush()

        vm = InventoryViewModel(s)
        ok, msg, allocations = vm.issue_sales(
            product_code=payload['product_code'],
            quantity=qty,
            reference_id=so.id,
            notes=payload.get('notes'),
        )
        if not ok:
            s.rollback()
            raise HTTPException(400, msg)

        for a in allocations:
            s.add(SalesOrderItem(
                so_id=so.id, product_id=product.id, batch_id=a['batch_id'],
                quantity=a['quantity'], unit_price=unit_price,
                total_price=a['quantity'] * unit_price,
                shipped_quantity=a['quantity'],
            ))
        s.commit()
        return {"message": f"銷貨單 {so.so_number} 建立，{msg}"}
    except HTTPException:
        raise
    except Exception as e:
        s.rollback()
        raise HTTPException(400, f"銷貨失敗: {e}")
    finally:
        s.close()


# ------------------------------------------------------------------ #
# 庫存：批號清單、調整、分裝
# ------------------------------------------------------------------ #
@app.get("/api/bulk-batches")
def list_bulk_batches():
    s = db_manager.get_session()
    try:
        rows = []
        for b in s.query(BulkBatch).order_by(BulkBatch.id.desc()).limit(200):
            rows.append({
                'id': b.id, 'item_code': b.bulk_item.code,
                'item_name': b.bulk_item.name,
                'batch_number': b.batch_number, 'lot_number': b.lot_number,
                'quantity': b.quantity, 'unit_cost': b.unit_cost,
                'expiry_date': b.expiry_date.isoformat()[:10] if b.expiry_date else None,
            })
        return rows
    finally:
        s.close()


@app.get("/api/sellable-batches")
def list_sellable_batches():
    s = db_manager.get_session()
    try:
        rows = []
        for b in s.query(Batch).order_by(Batch.id.desc()).limit(200):
            rows.append({
                'id': b.id, 'product_code': b.product.code,
                'product_name': b.product.name,
                'batch_number': b.batch_number,
                'quantity': b.quantity, 'unit_cost': b.unit_cost,
                'expiry_date': b.expiry_date.isoformat()[:10] if b.expiry_date else None,
            })
        return rows
    finally:
        s.close()


@app.post("/api/adjust")
def adjust(payload: dict = Body(...)):
    s = db_manager.get_session()
    try:
        ok, msg = InventoryViewModel(s).adjust_bulk(
            bulk_batch_id=int(payload['bulk_batch_id']),
            quantity_delta=float(payload['quantity_delta']),
            reason=payload.get('reason', '盤點調整'),
        )
        if not ok:
            raise HTTPException(400, msg)
        return {"message": msg}
    finally:
        s.close()


@app.post("/api/repack")
def repack(payload: dict = Body(...)):
    s = db_manager.get_session()
    try:
        required = ['bulk_batch_id', 'product_id', 'bulk_qty',
                    'output_batch_number', 'expiry_date']
        missing = [k for k in required if payload.get(k) in (None, '')]
        if missing:
            raise HTTPException(400, f"缺少必填欄位: {', '.join(missing)}")
        ok, msg, order = InventoryViewModel(s).repack(
            bulk_batch_id=int(payload['bulk_batch_id']),
            product_id=int(payload['product_id']),
            bulk_qty=float(payload['bulk_qty']),
            output_batch_number=payload['output_batch_number'],
            expiry_date=datetime.fromisoformat(payload['expiry_date']),
            operator=payload.get('operator'),
            notes=payload.get('notes'),
        )
        if not ok:
            raise HTTPException(400, msg)
        return {"message": msg}
    finally:
        s.close()


@app.get("/api/low-stock")
def low_stock():
    s = db_manager.get_session()
    try:
        return InventoryViewModel(s).check_low_stock()
    finally:
        s.close()


@app.get("/api/expiring")
def expiring(days: int = 90):
    s = db_manager.get_session()
    try:
        rows = InventoryViewModel(s).get_expiring_batches(days=days)
        for r in rows:
            r["expiry_date"] = r["expiry_date"].strftime("%Y-%m-%d")
        return rows
    finally:
        s.close()


@app.get("/api/valuation")
def valuation():
    s = db_manager.get_session()
    try:
        return InventoryViewModel(s).get_stock_valuation()
    finally:
        s.close()


# ------------------------------------------------------------------ #
# Accounting — invoices, payments, reports (AccountingViewModel)
# ------------------------------------------------------------------ #
_INVOICE_LINE_NUMERIC = ('quantity', 'unit_price', 'tax_rate', 'cost_per_unit')


def _coerce_invoice_lines(lines):
    """瀏覽器表單的數字常以字串送達，統一轉 float。"""
    out = []
    for ld in lines or []:
        ld = dict(ld)
        for k in _INVOICE_LINE_NUMERIC:
            if isinstance(ld.get(k), str) and ld[k] != '':
                ld[k] = float(ld[k])
        out.append(ld)
    return out


@app.post("/api/accounting/sales-invoices")
def create_sales_invoice(payload: dict = Body(...)):
    s = db_manager.get_session()
    try:
        header = dict(payload.get('header') or {})
        for k in ('invoice_date', 'due_date'):
            if isinstance(header.get(k), str):
                header[k] = date.fromisoformat(header[k])
        inv = AccountingViewModel(s).create_sales_invoice(
            header, _coerce_invoice_lines(payload.get('lines')))
        s.commit()
        return {"id": inv.id, "invoice_number": inv.invoice_number,
                "total_amount_with_tax": inv.total_amount_with_tax}
    except (ValueError, TypeError) as e:
        s.rollback()
        raise HTTPException(400, str(e))
    except IntegrityError as e:
        s.rollback()
        raise HTTPException(400, f"資料重複或違反完整性限制: {e.orig}")
    finally:
        s.close()


@app.post("/api/accounting/purchase-invoices")
def create_purchase_invoice(payload: dict = Body(...)):
    s = db_manager.get_session()
    try:
        header = dict(payload.get('header') or {})
        for k in ('invoice_date', 'due_date'):
            if isinstance(header.get(k), str):
                header[k] = date.fromisoformat(header[k])
        inv = AccountingViewModel(s).create_purchase_invoice(
            header, _coerce_invoice_lines(payload.get('lines')))
        s.commit()
        return {"id": inv.id, "invoice_number": inv.invoice_number,
                "total_amount_with_tax": inv.total_amount_with_tax}
    except (ValueError, TypeError) as e:
        s.rollback()
        raise HTTPException(400, str(e))
    except IntegrityError as e:
        s.rollback()
        raise HTTPException(400, f"資料重複或違反完整性限制: {e.orig}")
    finally:
        s.close()


@app.post("/api/accounting/payments")
def record_payment(payload: dict = Body(...)):
    s = db_manager.get_session()
    try:
        if isinstance(payload.get('transaction_date'), str):
            payload['transaction_date'] = date.fromisoformat(payload['transaction_date'])
        rec = AccountingViewModel(s).record_payment(payload)
        s.commit()
        return {"id": rec.id, "payment_number": rec.payment_number,
                "amount": rec.amount}
    except (ValueError, KeyError, TypeError) as e:
        s.rollback()
        raise HTTPException(400, str(e))
    except IntegrityError as e:
        s.rollback()
        raise HTTPException(400, f"資料重複或違反完整性限制: {e.orig}")
    finally:
        s.close()


@app.get("/api/accounting/sales-invoices")
def list_sales_invoices():
    s = db_manager.get_session()
    try:
        rows = []
        for inv in s.query(SalesInvoice).order_by(SalesInvoice.id.desc()).limit(200):
            rows.append({
                'id': inv.id, 'invoice_number': inv.invoice_number,
                'customer_code': inv.customer_code, 'customer_name': inv.customer_name,
                'invoice_date': inv.invoice_date.isoformat()[:10],
                'due_date': inv.due_date.isoformat()[:10],
                'total_amount_with_tax': inv.total_amount_with_tax,
                'payment_status': inv.payment_status.name,
                'remaining_balance': inv.remaining_balance,
            })
        return rows
    finally:
        s.close()


@app.get("/api/accounting/purchase-invoices")
def list_purchase_invoices():
    s = db_manager.get_session()
    try:
        rows = []
        for inv in s.query(PurchaseInvoice).order_by(PurchaseInvoice.id.desc()).limit(200):
            rows.append({
                'id': inv.id, 'invoice_number': inv.invoice_number,
                'supplier_code': inv.supplier_code, 'supplier_name': inv.supplier_name,
                'invoice_date': inv.invoice_date.isoformat()[:10],
                'due_date': inv.due_date.isoformat()[:10],
                'total_amount_with_tax': inv.total_amount_with_tax,
                'payment_status': inv.payment_status.name,
                'remaining_balance': inv.remaining_balance,
            })
        return rows
    finally:
        s.close()


@app.get("/api/accounting/payments")
def list_payments():
    s = db_manager.get_session()
    try:
        rows = []
        for p in s.query(PaymentRecord).order_by(PaymentRecord.id.desc()).limit(200):
            rows.append({
                'id': p.id, 'payment_number': p.payment_number,
                'payment_type': p.payment_type.name,
                'transaction_date': p.transaction_date.isoformat()[:10],
                'supplier_or_customer_name': p.supplier_or_customer_name,
                'amount': p.amount, 'payment_method': p.payment_method,
                'reference_id': p.reference_id,
            })
        return rows
    finally:
        s.close()


@app.get("/api/accounting/reports/daily-sales")
def daily_sales_report(report_date: str):
    s = db_manager.get_session()
    try:
        return AccountingViewModel(s).daily_sales_report(
            _parse_report_date(report_date, "report_date"))
    finally:
        s.close()


@app.get("/api/accounting/reports/tax")
def monthly_tax_report(period: str, save: bool = False):
    s = db_manager.get_session()
    try:
        summary = AccountingViewModel(s).monthly_tax_summary(period, save=save)
        if save:
            s.commit()
        return summary
    except ValueError as e:
        s.rollback()
        raise HTTPException(400, str(e))
    finally:
        s.close()


@app.get("/api/accounting/receivables")
def receivables(outstanding_only: bool = True):
    s = db_manager.get_session()
    try:
        return AccountingViewModel(s).receivables(outstanding_only=outstanding_only)
    finally:
        s.close()


@app.get("/api/accounting/payables")
def payables(outstanding_only: bool = True):
    s = db_manager.get_session()
    try:
        return AccountingViewModel(s).payables(outstanding_only=outstanding_only)
    finally:
        s.close()


# ------------------------------------------------------------------ #
# Reports — 規格書 §6 M5 報表 + 信用告警 (ReportViewModel)
# ------------------------------------------------------------------ #
def _parse_report_date(value: str, name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(400, f"{name} 日期格式錯誤,應為 YYYY-MM-DD: {value}")


@app.get("/api/reports/monthly-inventory")
def monthly_inventory_report(period: str):
    s = db_manager.get_session()
    try:
        return ReportViewModel(s).monthly_inventory_report(period)
    except ValueError:
        raise HTTPException(400, f"period 格式錯誤,應為 YYYY-MM: {period}")
    finally:
        s.close()


@app.get("/api/reports/stock-snapshot")
def stock_snapshot_report(expiry_days: int = 90):
    s = db_manager.get_session()
    try:
        return ReportViewModel(s).stock_snapshot(expiry_days=expiry_days)
    finally:
        s.close()


@app.get("/api/reports/sales-profit")
def sales_profit_report(start: str, end: str):
    s = db_manager.get_session()
    try:
        return ReportViewModel(s).sales_profit_report(
            _parse_report_date(start, "start"), _parse_report_date(end, "end"))
    finally:
        s.close()


@app.get("/api/reports/repack-output")
def repack_output_report(start: str, end: str):
    s = db_manager.get_session()
    try:
        return ReportViewModel(s).repack_output_report(
            _parse_report_date(start, "start"), _parse_report_date(end, "end"))
    finally:
        s.close()


@app.get("/api/reports/credit-alerts")
def credit_alerts_report(over_only: bool = False):
    s = db_manager.get_session()
    try:
        return ReportViewModel(s).credit_alerts(over_only=over_only)
    finally:
        s.close()


# ------------------------------------------------------------------ #
# Generic CRUD routes — registered last so specific /api/* paths win
# ------------------------------------------------------------------ #
@app.get("/api/{entity}")
def list_entity(entity: str):
    if entity not in ENTITIES:
        raise HTTPException(404, f"Unknown entity {entity}")
    model, fields = ENTITIES[entity]
    s = db_manager.get_session()
    try:
        return [_dump(o, fields) for o in s.query(model).order_by(model.id).all()]
    finally:
        s.close()


@app.post("/api/{entity}")
def create_entity(entity: str, payload: dict = Body(...)):
    if entity not in ENTITIES:
        raise HTTPException(404, f"Unknown entity {entity}")
    model, fields = ENTITIES[entity]
    s = db_manager.get_session()
    try:
        kwargs = {}
        for name, kind, default in fields:
            v = _coerce(payload.get(name), kind, default)
            if v is not None:
                kwargs[name] = v
        if not kwargs.get('code') or not kwargs.get('name'):
            raise HTTPException(400, "code 與 name 為必填")
        obj = model(**kwargs)
        s.add(obj)
        s.commit()
        return {"message": "建立成功", "id": obj.id}
    except HTTPException:
        s.rollback()
        raise
    except Exception as e:
        s.rollback()
        raise HTTPException(400, f"建立失敗: {e}")
    finally:
        s.close()


@app.put("/api/{entity}/{obj_id}")
def update_entity(entity: str, obj_id: int, payload: dict = Body(...)):
    if entity not in ENTITIES:
        raise HTTPException(404, f"Unknown entity {entity}")
    model, fields = ENTITIES[entity]
    s = db_manager.get_session()
    try:
        obj = s.get(model, obj_id)
        if not obj:
            raise HTTPException(404, "資料不存在")
        for name, kind, default in fields:
            if name in payload:
                setattr(obj, name, _coerce(payload.get(name), kind, default))
        s.commit()
        return {"message": "更新成功", "id": obj.id}
    except HTTPException:
        s.rollback()
        raise
    except Exception as e:
        s.rollback()
        raise HTTPException(400, f"更新失敗: {e}")
    finally:
        s.close()




# ------------------------------------------------------------------ #
# 前端（單頁應用，零外部資源）
# ------------------------------------------------------------------ #
PAGE = r"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>Animal-AN ERP</title>
<link rel="stylesheet" href="/static/css/tokens.css">
<style>
  /* Unite design language: light cool-gray canvas, white elevated cards,
     Inter, single blue accent. All values come from tokens.css. */
  * { box-sizing: border-box; }
  body { margin:0; }
  header { background:hsl(var(--bg-toolbar)); border-bottom:1px solid hsl(var(--border-default));
           padding:0 var(--space-6); display:flex; align-items:center; gap:var(--space-6);
           height:56px; }
  header h1 { margin:0; font-size:var(--fs-lg); font-weight:var(--fw-semibold);
              white-space:nowrap; color:hsl(var(--text-default)); }
  header img { height:28px; width:auto; }
  nav { display:flex; gap:2px; flex-wrap:wrap; }
  nav button { background:transparent; color:hsl(var(--text-muted)); border:none;
               padding:var(--space-2) var(--space-3); cursor:pointer;
               font-size:var(--fs-base); font-family:var(--font-sans);
               border-radius:var(--radius-md);
               transition:background var(--duration-fast) var(--ease-in-out); }
  nav button:hover { background:hsl(var(--bg-sidebar-active)); color:hsl(var(--text-default)); }
  nav button.active { background:hsl(var(--bg-sidebar-active)); color:hsl(var(--text-default));
                      font-weight:var(--fw-semibold); }
  main { padding:var(--space-6); max-width:1280px; margin:0 auto; }
  .cards { display:flex; gap:var(--space-4); flex-wrap:wrap; margin-bottom:var(--space-6); }
  .card { background:hsl(var(--bg-card)); border-radius:var(--radius-lg);
          padding:var(--space-4) var(--space-5); box-shadow:var(--shadow-figma-card);
          min-width:180px; flex:1; }
  .card .label { color:hsl(var(--text-muted)); font-size:var(--fs-sm); }
  .card .value { font-size:var(--fs-3xl); font-weight:var(--fw-bold); margin-top:2px; }
  h2 { font-size:var(--fs-xl); font-weight:var(--fw-bold);
       margin:var(--space-6) 0 var(--space-2); }
  table { width:100%; border-collapse:collapse; background:hsl(var(--bg-card));
          border-radius:var(--radius-lg); overflow:hidden; box-shadow:var(--shadow-figma-card); }
  th,td { padding:var(--space-2) var(--space-3); text-align:left;
          font-size:var(--fs-sm); border-bottom:1px solid hsl(var(--border-table)); }
  th { background:hsl(var(--bg-table)); color:hsl(var(--text-muted));
       font-weight:var(--fw-medium); white-space:nowrap; }
  tbody tr { transition:background var(--duration-fast) var(--ease-in-out); }
  tbody tr:hover { background:hsl(var(--bg-card-secondary)); cursor:pointer; }
  .form-card { background:hsl(var(--bg-card)); border-radius:var(--radius-lg);
               padding:var(--space-5); box-shadow:var(--shadow-figma-card);
               margin-bottom:var(--space-5); }
  .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(210px,1fr));
          gap:var(--space-3); }
  label { display:block; font-size:var(--fs-xs); color:hsl(var(--text-muted));
          margin-bottom:2px; }
  input,select,textarea { width:100%; height:var(--input-h);
          padding:0 var(--space-3); border:1px solid hsl(var(--border-default-darker));
          border-radius:var(--radius-md); font-size:var(--fs-base);
          font-family:var(--font-sans); background:hsl(var(--bg-card));
          color:hsl(var(--text-default)); }
  input:focus,select:focus,textarea:focus { outline:2px solid hsl(var(--color-primary));
          outline-offset:-1px; border-color:hsl(var(--color-primary)); }
  .req label::after { content:" *"; color:hsl(var(--color-danger)); }
  .actions { margin-top:var(--space-4); display:flex; gap:var(--space-2); align-items:center; }
  .btn { background:hsl(var(--color-primary)); color:#fff; border:none;
         border-radius:var(--radius-md); padding:0 var(--space-5); height:var(--input-h);
         font-size:var(--fs-base); font-family:var(--font-sans);
         font-weight:var(--fw-medium); cursor:pointer; box-shadow:var(--shadow-btn);
         transition:background var(--duration-fast) var(--ease-in-out); }
  .btn:hover { background:hsl(var(--color-primary-lighter)); }
  .btn:active { box-shadow:var(--shadow-btn-active); }
  .btn.gray { background:hsl(var(--btn-default-bg)); color:hsl(var(--text-default));
              border:1px solid hsl(var(--btn-default-border)); box-shadow:none; }
  .msg { font-size:var(--fs-sm); }
  .msg.ok { color:rgb(36,137,97); } .msg.err { color:hsl(var(--color-danger)); }
  .warn { color:hsl(var(--color-danger)); font-weight:var(--fw-semibold); }
  .empty { color:hsl(var(--text-muted)); padding:var(--space-3); }
  /* 系統架構圖：右下角懸浮鈕 + tooltip + 全螢幕彈窗 */
  #mapFab { position:fixed; right:20px; bottom:20px; z-index:50;
    width:44px; height:44px; border-radius:50%; border:1px solid hsl(var(--border-default-darker));
    background:hsl(var(--bg-card)); color:hsl(var(--text-muted)); cursor:pointer;
    display:flex; align-items:center; justify-content:center;
    box-shadow:0 2px 8px rgba(0,0,0,.14);
    transition:color var(--duration-fast) var(--ease-in-out); }
  #mapFab:hover { color:hsl(var(--color-primary)); }
  #mapFab::after { content:attr(data-tip); position:absolute; right:0; bottom:52px;
    background:hsl(var(--text-default)); color:#fff; font-size:var(--fs-xs);
    padding:4px 10px; border-radius:var(--radius-md); white-space:nowrap;
    opacity:0; pointer-events:none; transform:translateY(4px);
    transition:opacity var(--duration-fast) var(--ease-in-out),
               transform var(--duration-fast) var(--ease-in-out); }
  #mapFab:hover::after, #mapFab:focus-visible::after { opacity:1; transform:translateY(0); }
  #mapModal { position:fixed; inset:0; z-index:60; background:rgba(20,28,36,.45); }
  #mapModal[hidden] { display:none; }
  #mapModal .map-box { position:absolute; inset:3%; background:#EEF1EF;
    border-radius:var(--radius-lg); overflow:hidden; box-shadow:0 12px 40px rgba(0,0,0,.3); }
  #mapModal iframe { width:100%; height:100%; border:none; }
  #mapClose { position:absolute; top:calc(3% + 10px); right:calc(3% + 10px); z-index:61;
    width:32px; height:32px; border-radius:50%; border:1px solid hsl(var(--border-default-darker));
    background:hsl(var(--bg-card)); cursor:pointer; font-size:15px; line-height:1;
    color:hsl(var(--text-default)); box-shadow:0 1px 4px rgba(0,0,0,.18); }
</style>
</head>
<body>
<header>
  <img src="/static/logo.svg" alt="">
  <h1>Animal-AN 進銷存</h1>
  <nav id="nav"></nav>
</header>
<main id="main"></main>
<button id="mapFab" data-tip="系統架構圖" aria-label="系統架構圖">
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
       stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d="M9 4 3 6.5v13L9 17l6 2.5 6-2.5v-13L15 6.5 9 4z"/>
    <path d="M9 4v13M15 6.5v13"/>
  </svg>
</button>
<div id="mapModal" hidden>
  <div class="map-box"><iframe data-src="/static/system_map.html" title="系統架構圖"></iframe></div>
  <button id="mapClose" aria-label="關閉">✕</button>
</div>
<script>
// ------------------------- helpers -------------------------
const api = {
  get: p => fetch('/api/'+p).then(r=>r.json()),
  post: (p,b) => fetch('/api/'+p,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)})
        .then(async r=>{ const j=await r.json(); if(!r.ok) throw (j.detail||'錯誤'); return j; }),
  put: (p,b) => fetch('/api/'+p,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)})
        .then(async r=>{ const j=await r.json(); if(!r.ok) throw (j.detail||'錯誤'); return j; }),
};
const esc = s => (s==null?'':String(s)).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmt = n => n==null?'':new Intl.NumberFormat('zh-TW').format(n);

// ------------------------- enum options -------------------------
const OPTS = {
  ProductType: {MEDICINE:'藥品',VACCINE:'疫苗',MEDICATED_FEED:'藥物飼料',SUPPLEMENT:'營養補充',HYGIENE:'衛生用品'},
  StorageType: {ROOM_TEMP:'室溫',REFRIGERATED:'冷藏',FROZEN:'冷凍'},
  PackageType: {BULK:'散裝',BAG:'袋',BOTTLE:'瓶',VIAL:'小瓶',BOX:'盒',AMPOULE:'安瓿',SACHET:'小包'},
  SupplierType:{MANUFACTURER:'原廠',IMPORTER:'進口商',AGENT:'代理'},
  CustomerType:{PIG_FARM:'養豬場',VET_CLINIC:'動物醫院',FEED_MILL:'飼料廠',DISTRIBUTOR:'經銷',RETAIL:'零售'},
};

// ------------------------- entity configs -------------------------
const F = (k,label,type,extra) => Object.assign({k,label,type:type||'text'},extra||{});
const CONFIGS = {
  'bulk-items': { title:'原物料（原裝品）', api:'bulk-items',
    cols:['code','name','unit','quantity','min_quantity'],
    colNames:['料號','品名','單位','庫存','安全庫存'],
    fields:[ F('code','料號','text',{req:1}), F('name','品名','text',{req:1}),
      F('unit','原裝單位（棧板/桶/箱）','text',{req:1}),
      F('product_type','類型','enum:ProductType'), F('storage_type','儲存條件','enum:StorageType'),
      F('min_quantity','安全庫存','number'), F('shelf_life_months','保存期限(月)','number'),
      F('min_temperature','溫度下限','number'), F('max_temperature','溫度上限','number'),
      F('registration_number','許可證字號'), F('country_of_origin','原產地'),
      F('description','說明') ] },
  'products': { title:'產品（分裝品 SKU）', api:'products',
    cols:['code','name','spec','unit','selling_price','units_per_bulk'],
    colNames:['SKU','品名','規格','售賣單位','標準售價','每原裝換算'],
    fields:[ F('code','SKU 料號','text',{req:1}), F('name','品名','text',{req:1}),
      F('bulk_item_id','來源原裝品','ref:bulk-items'),
      F('units_per_bulk','每 1 原裝分裝數','number'),
      F('selling_price','標準售價','number'),
      F('spec','規格描述（如 100mL/瓶）'), F('unit','售賣單位（瓶/支/包）','text',{req:1}),
      F('product_type','類型','enum:ProductType'), F('storage_type','儲存條件','enum:StorageType'),
      F('package_type','包裝型式','enum:PackageType'),
      F('package_size','包裝容量','number'), F('package_unit','容量單位'),
      F('units_per_package','每包裝含數','number'),
      F('dosage_form','劑型'), F('concentration','濃度'),
      F('active_ingredient','主成分'), F('barcode','條碼'),
      F('manufacturer','製造廠'), F('registration_number','許可證字號'),
      F('shelf_life_months','保存期限(月)','number'), F('reorder_point','再訂購點','number') ] },
  'suppliers': { title:'供應商', api:'suppliers',
    cols:['code','name','supplier_type','contact_person','phone','credit_term_days'],
    colNames:['代號','名稱','類型','聯絡人','電話','付款天數'],
    fields:[ F('code','代號','text',{req:1}), F('name','名稱','text',{req:1}),
      F('short_name','簡稱'), F('supplier_type','類型','enum:SupplierType'),
      F('country','國家/地區'), F('contact_person','聯絡人'), F('contact_title','職稱'),
      F('phone','電話'), F('mobile','行動電話'), F('fax','傳真'), F('email','Email'),
      F('address','地址'), F('tax_id','統一編號'),
      F('credit_term_days','付款天數','number'), F('payment_method','付款方式'),
      F('currency','幣別'), F('bank_name','銀行'), F('bank_branch','分行'),
      F('bank_account','帳號'), F('bank_swift','SWIFT'),
      F('license_number','藥商許可證'), F('license_expiry','許可證效期','date'),
      F('rating','評等(A/B/C)'), F('notes','備註') ] },
  'customers': { title:'客戶', api:'customers',
    cols:['code','name','customer_type','contact_person','phone','credit_limit','current_balance'],
    colNames:['代號','名稱','類型','聯絡人','電話','信用額度','應收餘額'],
    fields:[ F('code','代號','text',{req:1}), F('name','名稱','text',{req:1}),
      F('short_name','簡稱'), F('customer_type','類型','enum:CustomerType'),
      F('contact_person','聯絡人'), F('contact_title','職稱'),
      F('phone','電話'), F('mobile','行動電話'), F('fax','傳真'), F('email','Email'),
      F('address','地址'), F('billing_address','帳單地址'), F('shipping_address','送貨地址'),
      F('invoice_title','發票抬頭'), F('tax_id','統一編號'),
      F('credit_term_days','收款天數','number'), F('credit_limit','信用額度','number'),
      F('sales_rep','負責業務'), F('farm_license','牧場登記證'), F('notes','備註') ] },
};

// ------------------------- generic CRUD page -------------------------
let refCache = {};
async function refOptions(entity){
  if(!refCache[entity]) refCache[entity] = await api.get(entity);
  return refCache[entity];
}
async function renderCrud(cfg){
  const rows = await api.get(cfg.api);
  refCache = {};
  let fieldHtml = '';
  for(const f of cfg.fields){
    let input;
    if(f.type.startsWith('enum:')){
      const opts = OPTS[f.type.split(':')[1]];
      input = `<select name="${f.k}"><option value="">--</option>` +
        Object.entries(opts).map(([k,v])=>`<option value="${k}">${v}</option>`).join('') + '</select>';
    } else if(f.type.startsWith('ref:')){
      const list = await refOptions(f.type.split(':')[1]);
      input = `<select name="${f.k}"><option value="">--</option>` +
        list.map(r=>`<option value="${r.id}">${esc(r.code)} ${esc(r.name)}</option>`).join('') + '</select>';
    } else {
      input = `<input name="${f.k}" type="${f.type==='number'?'number':f.type==='date'?'date':'text'}" ${f.type==='number'?'step="any"':''}>`;
    }
    fieldHtml += `<div class="${f.req?'req':''}"><label>${f.label}</label>${input}</div>`;
  }
  main.innerHTML = `
    <h2>${cfg.title}</h2>
    <div class="form-card">
      <form id="crudForm"><input type="hidden" name="id">
        <div class="grid">${fieldHtml}</div>
        <div class="actions">
          <button class="btn" type="submit" id="saveBtn">新增</button>
          <button class="btn gray" type="button" id="resetBtn">清空</button>
          <span class="msg" id="formMsg"></span>
        </div>
      </form>
    </div>
    <table><thead><tr>${cfg.colNames.map(c=>`<th>${c}</th>`).join('')}</tr></thead>
    <tbody>${rows.length ? rows.map(r=>
      `<tr data-id="${r.id}">${cfg.cols.map(c=>{
        let v = r[c];
        const f = cfg.fields.find(x=>x.k===c);
        if(f && f.type.startsWith('enum:') && v) v = OPTS[f.type.split(':')[1]][v]||v;
        return `<td>${esc(v)}</td>`;}).join('')}</tr>`).join('')
      : `<tr><td class="empty" colspan="${cfg.cols.length}">（無資料）</td></tr>`}</tbody></table>`;

  const form = document.getElementById('crudForm');
  const byId = Object.fromEntries(rows.map(r=>[String(r.id),r]));
  document.querySelectorAll('tbody tr[data-id]').forEach(tr=>{
    tr.onclick = ()=>{
      const r = byId[tr.dataset.id];
      form.id.value = r.id;
      for(const f of cfg.fields){
        const el = form.elements[f.k];
        if(el) el.value = r[f.k]==null?'':r[f.k];
      }
      saveBtn.textContent = '儲存修改 #'+r.id;
    };
  });
  resetBtn.onclick = ()=>{ form.reset(); form.id.value=''; saveBtn.textContent='新增'; formMsg.textContent=''; };
  form.onsubmit = async e=>{
    e.preventDefault();
    const body = {};
    for(const f of cfg.fields){
      const el = form.elements[f.k];
      if(el && el.value!=='') body[f.k] = el.value;
    }
    try{
      const id = form.id.value;
      const res = id ? await api.put(cfg.api+'/'+id, body) : await api.post(cfg.api, body);
      formMsg.className='msg ok'; formMsg.textContent = res.message;
      setTimeout(()=>renderCrud(cfg), 500);
    }catch(err){ formMsg.className='msg err'; formMsg.textContent = err; }
  };
}

// ------------------------- 進貨單 -------------------------
async function renderPurchase(){
  const [suppliers, bulks, pos] = await Promise.all([
    api.get('suppliers'), api.get('bulk-items'), api.get('purchase-orders')]);
  main.innerHTML = `
    <h2>建立進貨單（原裝入庫）</h2>
    <div class="form-card"><form id="poForm"><div class="grid">
      <div class="req"><label>供應商</label><select name="supplier_id">
        ${suppliers.map(s=>`<option value="${s.id}">${esc(s.code)} ${esc(s.name)}</option>`).join('')||'<option value="">（請先建立供應商）</option>'}</select></div>
      <div class="req"><label>原物料</label><select name="bulk_code">
        ${bulks.map(b=>`<option value="${esc(b.code)}">${esc(b.code)} ${esc(b.name)}</option>`).join('')||'<option value="">（請先建立原物料）</option>'}</select></div>
      <div class="req"><label>批號</label><input name="batch_number"></div>
      <div><label>原廠批號</label><input name="lot_number"></div>
      <div class="req"><label>數量</label><input name="quantity" type="number" step="any"></div>
      <div class="req"><label>單位成本（批次成本）</label><input name="unit_cost" type="number" step="any"></div>
      <div class="req"><label>效期</label><input name="expiry_date" type="date"></div>
      <div><label>備註</label><input name="notes"></div>
    </div><div class="actions">
      <button class="btn" type="submit">建立進貨單</button><span class="msg" id="poMsg"></span>
    </div></form></div>
    <h2>進貨單紀錄</h2>
    <table><thead><tr><th>單號</th><th>供應商</th><th>日期</th><th>金額</th><th>備註</th></tr></thead>
    <tbody>${pos.length?pos.map(p=>`<tr><td>${esc(p.po_number)}</td><td>${esc(p.supplier)}</td><td>${p.order_date}</td><td>${fmt(p.total_amount)}</td><td>${esc(p.notes)}</td></tr>`).join('')
      :'<tr><td class="empty" colspan="5">（無資料）</td></tr>'}</tbody></table>`;
  poForm.onsubmit = async e=>{
    e.preventDefault();
    const body = Object.fromEntries(new FormData(poForm).entries());
    try{ const r = await api.post('purchase-orders', body);
      poMsg.className='msg ok'; poMsg.textContent=r.message;
      setTimeout(renderPurchase, 800);
    }catch(err){ poMsg.className='msg err'; poMsg.textContent=err; }
  };
}

// ------------------------- 銷貨單 -------------------------
async function renderSales(){
  const [customers, products, sos] = await Promise.all([
    api.get('customers'), api.get('products'), api.get('sales-orders')]);
  main.innerHTML = `
    <h2>建立銷貨單（FEFO 出庫）</h2>
    <div class="form-card"><form id="soForm"><div class="grid">
      <div class="req"><label>客戶</label><select name="customer_id">
        ${customers.map(c=>`<option value="${c.id}">${esc(c.code)} ${esc(c.name)}</option>`).join('')||'<option value="">（請先建立客戶）</option>'}</select></div>
      <div class="req"><label>產品</label><select name="product_code" id="soProduct">
        ${products.map(p=>`<option value="${esc(p.code)}" data-price="${p.selling_price||''}">${esc(p.code)} ${esc(p.name)} ${esc(p.spec||'')}</option>`).join('')||'<option value="">（請先建立產品）</option>'}</select></div>
      <div class="req"><label>數量</label><input name="quantity" type="number" step="any"></div>
      <div><label>售價（預設標準售價）</label><input name="unit_price" type="number" step="any" id="soPrice"></div>
      <div><label>備註</label><input name="notes"></div>
    </div><div class="actions">
      <button class="btn" type="submit">建立銷貨單</button><span class="msg" id="soMsg"></span>
    </div></form></div>
    <h2>銷貨單紀錄</h2>
    <table><thead><tr><th>單號</th><th>客戶</th><th>日期</th><th>金額</th><th>備註</th></tr></thead>
    <tbody>${sos.length?sos.map(p=>`<tr><td>${esc(p.so_number)}</td><td>${esc(p.customer)}</td><td>${p.order_date}</td><td>${fmt(p.total_amount)}</td><td>${esc(p.notes)}</td></tr>`).join('')
      :'<tr><td class="empty" colspan="5">（無資料）</td></tr>'}</tbody></table>`;
  const syncPrice = ()=>{ const o = soProduct.selectedOptions[0]; if(o) soPrice.value = o.dataset.price||''; };
  soProduct.onchange = syncPrice; syncPrice();
  soForm.onsubmit = async e=>{
    e.preventDefault();
    const body = Object.fromEntries(new FormData(soForm).entries());
    try{ const r = await api.post('sales-orders', body);
      soMsg.className='msg ok'; soMsg.textContent=r.message;
      setTimeout(renderSales, 800);
    }catch(err){ soMsg.className='msg err'; soMsg.textContent=err; }
  };
}

// ------------------------- 銷售發票 -------------------------
async function renderSalesInvoice(){
  const [customers, products, invoices] = await Promise.all([
    api.get('customers'), api.get('products'), api.get('accounting/sales-invoices')]);
  const productOpts = products.map(p=>`<option value="${esc(p.code)}" data-name="${esc(p.name)}" data-unit="${esc(p.unit||'')}" data-price="${p.selling_price||''}">${esc(p.code)} ${esc(p.name)}</option>`).join('');
  const lineRow = ()=>`<div class="grid" style="grid-template-columns:2fr 1fr 1fr 1fr 1fr auto;align-items:end" data-line>
      <div><label>產品</label><select class="li-code">${productOpts||'<option value="">（請先建立產品）</option>'}</select></div>
      <div><label>數量</label><input class="li-qty" type="number" step="any"></div>
      <div><label>單位</label><input class="li-unit"></div>
      <div><label>單價</label><input class="li-price" type="number" step="any"></div>
      <div><label>稅率%</label><input class="li-tax" type="number" step="any" value="5"></div>
      <button type="button" class="btn gray li-remove">刪除</button>
    </div>`;
  main.innerHTML = `
    <h2>建立銷售發票</h2>
    <div class="form-card"><form id="siForm"><div class="grid">
      <div class="req"><label>客戶</label><select name="customer_code">
        ${customers.map(c=>`<option value="${esc(c.code)}" data-name="${esc(c.name)}">${esc(c.code)} ${esc(c.name)}</option>`).join('')||'<option value="">（請先建立客戶）</option>'}</select></div>
      <div class="req"><label>發票號碼</label><input name="invoice_number"></div>
      <div class="req"><label>開立日期</label><input name="invoice_date" type="date"></div>
      <div class="req"><label>到期日</label><input name="due_date" type="date"></div>
      <div><label>備註</label><input name="notes"></div>
    </div>
    <h2 style="margin-top:var(--space-4)">明細</h2>
    <div id="siLines">${lineRow()}</div>
    <div class="actions"><button type="button" class="btn gray" id="siAddLine">+ 新增一列</button></div>
    <div class="actions">
      <button class="btn" type="submit">建立銷售發票</button><span class="msg" id="siMsg"></span>
    </div></form></div>
    <h2>銷售發票紀錄</h2>
    <table><thead><tr><th>單號</th><th>客戶</th><th>開立日期</th><th>含稅金額</th><th>付款狀態</th><th>未結餘額</th></tr></thead>
    <tbody>${invoices.length?invoices.map(i=>`<tr><td>${esc(i.invoice_number)}</td><td>${esc(i.customer_name)}</td><td>${i.invoice_date}</td><td>${fmt(i.total_amount_with_tax)}</td><td>${esc(i.payment_status)}</td><td>${fmt(i.remaining_balance)}</td></tr>`).join('')
      :'<tr><td class="empty" colspan="6">（無資料）</td></tr>'}</tbody></table>`;
  siLines.addEventListener('change', e=>{
    if(e.target.classList.contains('li-code')){
      const row = e.target.closest('[data-line]'); const o = e.target.selectedOptions[0];
      if(o){ row.querySelector('.li-unit').value = o.dataset.unit||''; row.querySelector('.li-price').value = o.dataset.price||''; }
    }
  });
  siLines.addEventListener('click', e=>{
    if(e.target.classList.contains('li-remove')) e.target.closest('[data-line]').remove();
  });
  siAddLine.onclick = ()=>{ siLines.insertAdjacentHTML('beforeend', lineRow()); };
  siForm.onsubmit = async e=>{
    e.preventDefault();
    const custOpt = siForm.customer_code.selectedOptions[0];
    const header = {
      customer_code: siForm.customer_code.value, customer_name: custOpt?custOpt.dataset.name:'',
      invoice_number: siForm.invoice_number.value, invoice_date: siForm.invoice_date.value,
      due_date: siForm.due_date.value, notes: siForm.notes.value||undefined,
    };
    const lines = [...siLines.querySelectorAll('[data-line]')].map(row=>{
      const o = row.querySelector('.li-code').selectedOptions[0];
      return { product_code: row.querySelector('.li-code').value, product_name: o?o.dataset.name:'',
        quantity: +row.querySelector('.li-qty').value, unit: row.querySelector('.li-unit').value,
        unit_price: +row.querySelector('.li-price').value, tax_rate: +row.querySelector('.li-tax').value||0 };
    }).filter(l=>l.product_code && l.quantity);
    try{ const r = await api.post('accounting/sales-invoices', {header, lines});
      siMsg.className='msg ok'; siMsg.textContent=`發票 ${r.invoice_number} 已建立，含稅金額 ${fmt(r.total_amount_with_tax)}`;
      setTimeout(renderSalesInvoice, 800);
    }catch(err){ siMsg.className='msg err'; siMsg.textContent=err; }
  };
}

// ------------------------- 採購發票 -------------------------
async function renderPurchaseInvoice(){
  const [suppliers, bulks, invoices] = await Promise.all([
    api.get('suppliers'), api.get('bulk-items'), api.get('accounting/purchase-invoices')]);
  const bulkOpts = bulks.map(b=>`<option value="${esc(b.code)}" data-name="${esc(b.name)}" data-unit="${esc(b.unit||'')}">${esc(b.code)} ${esc(b.name)}</option>`).join('');
  const lineRow = ()=>`<div class="grid" style="grid-template-columns:2fr 1fr 1fr 1fr 1fr 1fr auto;align-items:end" data-line>
      <div><label>原物料</label><select class="li-code">${bulkOpts||'<option value="">（請先建立原物料）</option>'}</select></div>
      <div class="req"><label>批號</label><input class="li-batch"></div>
      <div><label>數量</label><input class="li-qty" type="number" step="any"></div>
      <div><label>單位</label><input class="li-unit"></div>
      <div><label>單價</label><input class="li-price" type="number" step="any"></div>
      <div><label>稅率%</label><input class="li-tax" type="number" step="any" value="5"></div>
      <button type="button" class="btn gray li-remove">刪除</button>
    </div>`;
  main.innerHTML = `
    <h2>建立採購發票</h2>
    <div class="form-card"><form id="piForm"><div class="grid">
      <div class="req"><label>供應商</label><select name="supplier_code">
        ${suppliers.map(s=>`<option value="${esc(s.code)}" data-name="${esc(s.name)}">${esc(s.code)} ${esc(s.name)}</option>`).join('')||'<option value="">（請先建立供應商）</option>'}</select></div>
      <div class="req"><label>發票號碼</label><input name="invoice_number"></div>
      <div class="req"><label>開立日期</label><input name="invoice_date" type="date"></div>
      <div class="req"><label>到期日</label><input name="due_date" type="date"></div>
    </div>
    <h2 style="margin-top:var(--space-4)">明細</h2>
    <div id="piLines">${lineRow()}</div>
    <div class="actions"><button type="button" class="btn gray" id="piAddLine">+ 新增一列</button></div>
    <div class="actions">
      <button class="btn" type="submit">建立採購發票</button><span class="msg" id="piMsg"></span>
    </div></form></div>
    <h2>採購發票紀錄</h2>
    <table><thead><tr><th>單號</th><th>供應商</th><th>開立日期</th><th>含稅金額</th><th>付款狀態</th><th>未結餘額</th></tr></thead>
    <tbody>${invoices.length?invoices.map(i=>`<tr><td>${esc(i.invoice_number)}</td><td>${esc(i.supplier_name)}</td><td>${i.invoice_date}</td><td>${fmt(i.total_amount_with_tax)}</td><td>${esc(i.payment_status)}</td><td>${fmt(i.remaining_balance)}</td></tr>`).join('')
      :'<tr><td class="empty" colspan="6">（無資料）</td></tr>'}</tbody></table>`;
  piLines.addEventListener('change', e=>{
    if(e.target.classList.contains('li-code')){
      const row = e.target.closest('[data-line]'); const o = e.target.selectedOptions[0];
      if(o){ row.querySelector('.li-unit').value = o.dataset.unit||''; }
    }
  });
  piLines.addEventListener('click', e=>{
    if(e.target.classList.contains('li-remove')) e.target.closest('[data-line]').remove();
  });
  piAddLine.onclick = ()=>{ piLines.insertAdjacentHTML('beforeend', lineRow()); };
  piForm.onsubmit = async e=>{
    e.preventDefault();
    const supOpt = piForm.supplier_code.selectedOptions[0];
    const header = {
      supplier_code: piForm.supplier_code.value, supplier_name: supOpt?supOpt.dataset.name:'',
      invoice_number: piForm.invoice_number.value, invoice_date: piForm.invoice_date.value,
      due_date: piForm.due_date.value,
    };
    const lines = [...piLines.querySelectorAll('[data-line]')].map(row=>{
      const o = row.querySelector('.li-code').selectedOptions[0];
      return { bulk_item_code: row.querySelector('.li-code').value, bulk_item_name: o?o.dataset.name:'',
        bulk_batch_number: row.querySelector('.li-batch').value,
        quantity: +row.querySelector('.li-qty').value, unit: row.querySelector('.li-unit').value,
        unit_price: +row.querySelector('.li-price').value, tax_rate: +row.querySelector('.li-tax').value||0 };
    }).filter(l=>l.bulk_item_code && l.quantity);
    try{ const r = await api.post('accounting/purchase-invoices', {header, lines});
      piMsg.className='msg ok'; piMsg.textContent=`發票 ${r.invoice_number} 已建立，含稅金額 ${fmt(r.total_amount_with_tax)}`;
      setTimeout(renderPurchaseInvoice, 800);
    }catch(err){ piMsg.className='msg err'; piMsg.textContent=err; }
  };
}

// ------------------------- 收付款 -------------------------
async function renderPayment(){
  const [salesInv, purchInv, payments] = await Promise.all([
    api.get('accounting/sales-invoices'), api.get('accounting/purchase-invoices'), api.get('accounting/payments')]);
  const unpaidSales = salesInv.filter(i=>i.remaining_balance>0);
  const unpaidPurch = purchInv.filter(i=>i.remaining_balance>0);
  const invOpts = type => (type==='RECEIPT_FROM_CUSTOMER'?unpaidSales:unpaidPurch)
    .map(i=>`<option value="${i.id}" data-balance="${i.remaining_balance}">${esc(i.invoice_number)}（未結 ${fmt(i.remaining_balance)}）</option>`).join('');
  main.innerHTML = `
    <h2>建立收付款</h2>
    <div class="form-card"><form id="payForm"><div class="grid">
      <div class="req"><label>類型</label><select name="payment_type" id="payType">
        <option value="RECEIPT_FROM_CUSTOMER">收款（客戶）</option>
        <option value="PAYMENT_TO_SUPPLIER">付款（供應商）</option></select></div>
      <div class="req"><label>發票</label><select name="reference_id" id="payInvoice">${invOpts('RECEIPT_FROM_CUSTOMER')||'<option value="">（無未結發票）</option>'}</select></div>
      <div class="req"><label>付款單號</label><input name="payment_number"></div>
      <div class="req"><label>金額</label><input name="amount" type="number" step="any" id="payAmount"></div>
      <div><label>付款方式</label><select name="payment_method">
        <option value="TRANSFER">轉帳</option><option value="CHECK">支票</option><option value="CASH">現金</option></select></div>
      <div class="req"><label>交易日期</label><input name="transaction_date" type="date"></div>
      <div><label>備註</label><input name="notes"></div>
    </div><div class="actions">
      <button class="btn" type="submit">建立收付款</button><span class="msg" id="payMsg"></span>
    </div></form></div>
    <h2>收付款紀錄</h2>
    <table><thead><tr><th>單號</th><th>類型</th><th>日期</th><th>對象</th><th>金額</th><th>方式</th></tr></thead>
    <tbody>${payments.length?payments.map(p=>`<tr><td>${esc(p.payment_number)}</td><td>${p.payment_type==='RECEIPT_FROM_CUSTOMER'?'收款':'付款'}</td><td>${p.transaction_date}</td><td>${esc(p.supplier_or_customer_name)}</td><td>${fmt(p.amount)}</td><td>${esc(p.payment_method)}</td></tr>`).join('')
      :'<tr><td class="empty" colspan="6">（無資料）</td></tr>'}</tbody></table>`;
  const syncAmount = ()=>{ const o = payInvoice.selectedOptions[0]; if(o) payAmount.value = o.dataset.balance||''; };
  payType.onchange = ()=>{ payInvoice.innerHTML = invOpts(payType.value)||'<option value="">（無未結發票）</option>'; syncAmount(); };
  payInvoice.onchange = syncAmount; syncAmount();
  payForm.onsubmit = async e=>{
    e.preventDefault();
    const body = Object.fromEntries(new FormData(payForm).entries());
    try{ const r = await api.post('accounting/payments', body);
      payMsg.className='msg ok'; payMsg.textContent=`付款 ${r.payment_number} 已建立，金額 ${fmt(r.amount)}`;
      setTimeout(renderPayment, 800);
    }catch(err){ payMsg.className='msg err'; payMsg.textContent=err; }
  };
}

// ------------------------- 庫存 -------------------------
async function renderInventory(){
  const [bulkBatches, sellBatches, products] = await Promise.all([
    api.get('bulk-batches'), api.get('sellable-batches'), api.get('products')]);
  main.innerHTML = `
    <h2>分裝作業（原裝 → 分裝品）</h2>
    <div class="form-card"><form id="rpForm"><div class="grid">
      <div class="req"><label>原裝批號</label><select name="bulk_batch_id">
        ${bulkBatches.filter(b=>b.quantity>0).map(b=>`<option value="${b.id}">${esc(b.item_code)} / ${esc(b.batch_number)}（存 ${b.quantity}）</option>`).join('')||'<option value="">（無可分裝批號）</option>'}</select></div>
      <div class="req"><label>分裝產品</label><select name="product_id">
        ${products.filter(p=>p.units_per_bulk).map(p=>`<option value="${p.id}">${esc(p.code)} ${esc(p.name)}（×${p.units_per_bulk}）</option>`).join('')||'<option value="">（請先建立含換算率的產品）</option>'}</select></div>
      <div class="req"><label>耗用原裝數量</label><input name="bulk_qty" type="number" step="any"></div>
      <div class="req"><label>產出批號</label><input name="output_batch_number"></div>
      <div class="req"><label>產出效期</label><input name="expiry_date" type="date"></div>
      <div><label>操作人</label><input name="operator"></div>
    </div><div class="actions">
      <button class="btn" type="submit">執行分裝</button><span class="msg" id="rpMsg"></span>
    </div></form></div>

    <h2>庫存調整（盤盈虧，原裝批號）</h2>
    <div class="form-card"><form id="adjForm"><div class="grid">
      <div class="req"><label>原裝批號</label><select name="bulk_batch_id">
        ${bulkBatches.map(b=>`<option value="${b.id}">${esc(b.item_code)} / ${esc(b.batch_number)}（存 ${b.quantity}）</option>`).join('')||'<option value="">（無批號）</option>'}</select></div>
      <div class="req"><label>調整量（+盤盈 / −盤虧）</label><input name="quantity_delta" type="number" step="any"></div>
      <div class="req"><label>原因</label><input name="reason"></div>
    </div><div class="actions">
      <button class="btn" type="submit">調整</button><span class="msg" id="adjMsg"></span>
    </div></form></div>

    <h2>原裝批號庫存</h2>
    <table><thead><tr><th>料號</th><th>品名</th><th>批號</th><th>原廠批號</th><th>數量</th><th>批次成本</th><th>效期</th></tr></thead>
    <tbody>${bulkBatches.length?bulkBatches.map(b=>`<tr><td>${esc(b.item_code)}</td><td>${esc(b.item_name)}</td><td>${esc(b.batch_number)}</td><td>${esc(b.lot_number)}</td><td>${b.quantity}</td><td>${fmt(b.unit_cost)}</td><td>${b.expiry_date||''}</td></tr>`).join('')
      :'<tr><td class="empty" colspan="7">（無資料）</td></tr>'}</tbody></table>
    <h2>分裝品批號庫存</h2>
    <table><thead><tr><th>SKU</th><th>品名</th><th>批號</th><th>數量</th><th>單位成本</th><th>效期</th></tr></thead>
    <tbody>${sellBatches.length?sellBatches.map(b=>`<tr><td>${esc(b.product_code)}</td><td>${esc(b.product_name)}</td><td>${esc(b.batch_number)}</td><td>${b.quantity}</td><td>${fmt(b.unit_cost)}</td><td>${b.expiry_date||''}</td></tr>`).join('')
      :'<tr><td class="empty" colspan="6">（無資料）</td></tr>'}</tbody></table>`;
  rpForm.onsubmit = async e=>{
    e.preventDefault();
    const body = Object.fromEntries(new FormData(rpForm).entries());
    try{ const r = await api.post('repack', body);
      rpMsg.className='msg ok'; rpMsg.textContent=r.message;
      setTimeout(renderInventory, 800);
    }catch(err){ rpMsg.className='msg err'; rpMsg.textContent=err; }
  };
  adjForm.onsubmit = async e=>{
    e.preventDefault();
    const body = Object.fromEntries(new FormData(adjForm).entries());
    try{ const r = await api.post('adjust', body);
      adjMsg.className='msg ok'; adjMsg.textContent=r.message;
      setTimeout(renderInventory, 800);
    }catch(err){ adjMsg.className='msg err'; adjMsg.textContent=err; }
  };
}

// ------------------------- 儀表板 -------------------------
async function renderDashboard(){
  const [val, bulk, low, exp] = await Promise.all([
    api.get('valuation'), api.get('bulk-items'), api.get('low-stock'), api.get('expiring')]);
  main.innerHTML = `
    <div class="cards">
      <div class="card"><div class="label">原裝庫存金額</div><div class="value">${fmt(Math.round(val.bulk_value))}</div></div>
      <div class="card"><div class="label">分裝庫存金額</div><div class="value">${fmt(Math.round(val.sellable_value))}</div></div>
      <div class="card"><div class="label">庫存總額</div><div class="value">${fmt(Math.round(val.total_value))}</div></div>
    </div>
    <h2>低庫存告警</h2>
    <table><thead><tr><th>料號</th><th>品名</th><th>現量</th><th>安全庫存</th></tr></thead>
    <tbody>${low.length?low.map(r=>`<tr class="warn"><td>${esc(r.code)}</td><td>${esc(r.name)}</td><td>${r.current_quantity}</td><td>${r.min_quantity}</td></tr>`).join('')
      :'<tr><td class="empty" colspan="4">（無告警）</td></tr>'}</tbody></table>
    <h2>近效期批號（90 天內）</h2>
    <table><thead><tr><th>類別</th><th>料號</th><th>品名</th><th>批號</th><th>效期</th><th>數量</th></tr></thead>
    <tbody>${exp.length?exp.map(r=>`<tr><td>${r.kind==='bulk'?'原裝':'分裝'}</td><td>${esc(r.item_code)}</td><td>${esc(r.item_name)}</td><td>${esc(r.batch_number)}</td><td>${r.expiry_date}</td><td>${r.quantity}</td></tr>`).join('')
      :'<tr><td class="empty" colspan="6">（無資料）</td></tr>'}</tbody></table>`;
}

// ------------------------- 報表 -------------------------
const csvExport = (filename, headers, rows) => {
  const cell = c => '"' + String(c==null?'':c).replace(/"/g,'""') + '"';
  const csv = [headers, ...rows].map(r=>r.map(cell).join(',')).join('\r\n');
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob(['\ufeff'+csv], {type:'text/csv;charset=utf-8'}));
  a.download = filename; a.click(); URL.revokeObjectURL(a.href);
};
const rptTable = (headers, rows, foot) =>
  `<table><thead><tr>${headers.map(h=>'<th>'+h+'</th>').join('')}</tr></thead><tbody>` +
  (rows.length ? rows.map(r=>`<tr${r.cls?' class="'+r.cls+'"':''}>`+r.cells.map(c=>'<td>'+c+'</td>').join('')+'</tr>').join('')
   : `<tr><td class="empty" colspan="${headers.length}">（無資料）</td></tr>`) +
  '</tbody>' + (foot ? `<tfoot><tr>${foot.map(c=>'<th>'+c+'</th>').join('')}</tr></tfoot>` : '') + '</table>';

const RPT_TABS = [
  ['monthly','進銷存月報'], ['snapshot','庫存即時表'], ['profit','銷售毛利'],
  ['repack','分裝產出'], ['ar','應收／信用'], ['ap','應付帳款'],
  ['tax','稅務彙總'], ['dailysales','日銷售'],
];

async function renderReports(tab){
  tab = tab || 'monthly';
  const today = new Date().toISOString().slice(0,10);
  const ym = today.slice(0,7);
  main.innerHTML = `
    <h2>報表</h2>
    <div class="form-card">
      <nav>${RPT_TABS.map(([k,l])=>`<button class="${k===tab?'active':''}" data-rpt="${k}">${l}</button>`).join('')}</nav>
      <div class="actions" id="rptCtl"></div>
    </div>
    <div id="rptBody"></div>`;
  document.querySelectorAll('[data-rpt]').forEach(b=>{ b.onclick = ()=>renderReports(b.dataset.rpt); });
  const ctl = document.getElementById('rptCtl');
  const body = document.getElementById('rptBody');
  let exportData = null;

  const addExport = name => {
    const b = document.createElement('button');
    b.className = 'btn gray'; b.type = 'button'; b.textContent = '匯出 CSV';
    b.onclick = () => { if(exportData) csvExport(name+'.csv', exportData[0], exportData[1]); };
    ctl.appendChild(b);
  };
  const addBtn = (label, fn, cls) => {
    const b = document.createElement('button');
    b.className = cls||'btn'; b.type = 'button'; b.textContent = label;
    b.onclick = fn; ctl.appendChild(b); return b;
  };
  const addInput = (label, type, value, id) => {
    const w = document.createElement('div');
    w.style.minWidth = '160px';
    w.innerHTML = `<label>${label}</label><input type="${type}" id="${id}" value="${value}">`;
    ctl.appendChild(w); return () => document.getElementById(id).value;
  };

  if(tab === 'monthly'){
    const getP = addInput('月份','month',ym,'rptP');
    const load = async () => {
      const d = await api.get('reports/monthly-inventory?period='+getP());
      if(d.detail){ body.innerHTML = `<p class="msg err">${esc(d.detail)}</p>`; return; }
      const H = ['SKU','品名','規格','期初量','期初金額','本期進','進金額','本期銷','銷金額','調整','期末量','期末金額'];
      body.innerHTML = rptTable(H, d.rows.map(r=>({cells:[
        esc(r.product_code), esc(r.product_name), esc(r.spec),
        r.open_qty, fmt(r.open_amount), r.in_qty, fmt(r.in_amount),
        r.out_qty, fmt(r.out_amount), r.adjust_qty, r.closing_qty, fmt(r.closing_amount)]})),
        ['合計','','','',fmt(d.totals.open_amount),'',fmt(d.totals.in_amount),'',
         fmt(d.totals.out_amount),'','',fmt(d.totals.closing_amount)]);
      exportData = [H, d.rows.map(r=>[r.product_code,r.product_name,r.spec,r.open_qty,r.open_amount,
        r.in_qty,r.in_amount,r.out_qty,r.out_amount,r.adjust_qty,r.closing_qty,r.closing_amount])];
    };
    addBtn('查詢', load); addExport('進銷存月報'); load();

  } else if(tab === 'snapshot'){
    const H = ['SKU','品名','規格','現量','批號數','庫存金額','近效期批號','再訂購點','狀態'];
    const rows = await api.get('reports/stock-snapshot');
    body.innerHTML = rptTable(H, rows.map(r=>({
      cls: r.below_reorder ? 'warn' : '',
      cells: [esc(r.product_code), esc(r.product_name), esc(r.spec), r.quantity,
        r.batch_count, fmt(r.stock_value), esc(r.near_expiry_batches.join(' / ')),
        r.reorder_point, r.below_reorder ? '⚠ 低於再訂購點' : '']})));
    exportData = [H, rows.map(r=>[r.product_code,r.product_name,r.spec,r.quantity,r.batch_count,
      r.stock_value,r.near_expiry_batches.join(' / '),r.reorder_point,r.below_reorder?'低於再訂購點':''])];
    addExport('庫存即時表');

  } else if(tab === 'profit'){
    const getS = addInput('起日','date',ym+'-01','rptS');
    const getE = addInput('迄日','date',today,'rptE');
    const load = async () => {
      const d = await api.get(`reports/sales-profit?start=${getS()}&end=${getE()}`);
      if(d.detail){ body.innerHTML = `<p class="msg err">${esc(d.detail)}</p>`; return; }
      const H = ['客戶','客戶名稱','SKU','品名','銷量','收入','成本','毛利','毛利率%'];
      body.innerHTML = rptTable(H, d.rows.map(r=>({cells:[
        esc(r.customer_code), esc(r.customer_name), esc(r.product_code), esc(r.product_name),
        r.quantity, fmt(r.revenue), fmt(r.cost), fmt(r.gross_profit), r.margin_pct]})),
        ['合計','','','',d.totals.quantity,fmt(d.totals.revenue),fmt(d.totals.cost),
         fmt(d.totals.gross_profit),d.totals.margin_pct]);
      exportData = [H, d.rows.map(r=>[r.customer_code,r.customer_name,r.product_code,r.product_name,
        r.quantity,r.revenue,r.cost,r.gross_profit,r.margin_pct])];
    };
    addBtn('查詢', load); addExport('銷售毛利'); load();

  } else if(tab === 'repack'){
    const getS = addInput('起日','date',ym+'-01','rptS');
    const getE = addInput('迄日','date',today,'rptE');
    const load = async () => {
      const rows = await api.get(`reports/repack-output?start=${getS()}&end=${getE()}`);
      if(rows.detail){ body.innerHTML = `<p class="msg err">${esc(rows.detail)}</p>`; return; }
      const H = ['日期','分裝單號','原裝料號','原裝批號','耗用','預期產出','實際產出','差異','產出批號','原裝成本','產出成本','操作人'];
      body.innerHTML = rptTable(H, rows.map(r=>({
        cls: r.variance ? 'warn' : '',
        cells: [r.repack_date, esc(r.repack_number), esc(r.bulk_code), esc(r.bulk_batch_number),
          r.bulk_qty_consumed, r.expected_output, r.output_qty, r.variance,
          esc(r.output_batch_number), fmt(r.bulk_cost), fmt(r.output_value), esc(r.operator)]})));
      exportData = [H, rows.map(r=>[r.repack_date,r.repack_number,r.bulk_code,r.bulk_batch_number,
        r.bulk_qty_consumed,r.expected_output,r.output_qty,r.variance,r.output_batch_number,
        r.bulk_cost,r.output_value,r.operator])];
    };
    addBtn('查詢', load); addExport('分裝產出'); load();

  } else if(tab === 'ar'){
    const [alerts, ars] = await Promise.all([
      api.get('reports/credit-alerts'), api.get('accounting/receivables')]);
    const H1 = ['客戶','客戶名稱','信用額度','應收餘額','可用額度','狀態'];
    const H2 = ['客戶','發票號碼','原始金額','已收','未收','到期日','逾期天數','狀態'];
    body.innerHTML = '<h2>信用控管</h2>' + rptTable(H1, alerts.map(r=>({
        cls: r.over_limit ? 'warn' : '',
        cells: [esc(r.customer_code), esc(r.customer_name), fmt(r.credit_limit),
          fmt(r.outstanding), r.available==null?'—':fmt(r.available),
          r.over_limit ? '⚠ 超過信用額度' : 'OK']}))) +
      '<h2>未結應收帳款</h2>' + rptTable(H2, ars.map(r=>({
        cls: r.overdue_status==='OVERDUE' ? 'warn' : '',
        cells: [esc(r.customer_code), esc(r.invoice_number), fmt(r.original_amount),
          fmt(r.paid_amount), fmt(r.outstanding_amount), r.due_date,
          r.days_overdue, r.overdue_status==='OVERDUE'?'逾期':'未到期']})));
    exportData = [H2, ars.map(r=>[r.customer_code,r.invoice_number,r.original_amount,
      r.paid_amount,r.outstanding_amount,r.due_date,r.days_overdue,r.overdue_status])];
    addExport('應收帳款');

  } else if(tab === 'ap'){
    const aps = await api.get('accounting/payables');
    const H = ['供應商','發票號碼','原始金額','已付','未付','到期日','逾期天數','狀態'];
    body.innerHTML = rptTable(H, aps.map(r=>({
      cls: r.overdue_status==='OVERDUE' ? 'warn' : '',
      cells: [esc(r.supplier_code), esc(r.invoice_number), fmt(r.original_amount),
        fmt(r.paid_amount), fmt(r.outstanding_amount), r.due_date,
        r.days_overdue, r.overdue_status==='OVERDUE'?'逾期':'未到期']})));
    exportData = [H, aps.map(r=>[r.supplier_code,r.invoice_number,r.original_amount,
      r.paid_amount,r.outstanding_amount,r.due_date,r.days_overdue,r.overdue_status])];
    addExport('應付帳款');

  } else if(tab === 'tax'){
    const getP = addInput('期別','month',ym,'rptP');
    const msg = document.createElement('span'); msg.className = 'msg';
    const show = d => {
      body.innerHTML = `<div class="cards">
        <div class="card"><div class="label">銷項稅（${d.sales_invoice_count} 張發票）</div><div class="value">${fmt(d.total_sales_tax)}</div></div>
        <div class="card"><div class="label">進項稅（${d.purchase_invoice_count} 張發票）</div><div class="value">${fmt(d.total_purchase_tax)}</div></div>
        <div class="card"><div class="label">應納稅額（銷項 − 進項）</div><div class="value">${fmt(d.net_tax_payable)}</div></div>
      </div>` + rptTable(['項目','金額'], [
        {cells:['銷售額（未稅）', fmt(d.total_sales_amount)]},
        {cells:['銷項稅', fmt(d.total_sales_tax)]},
        {cells:['進貨額（未稅）', fmt(d.total_purchase_amount)]},
        {cells:['進項稅', fmt(d.total_purchase_tax)]},
        {cells:['應納稅額', fmt(d.net_tax_payable)]}]);
    };
    const load = async save => {
      const d = await api.get(`accounting/reports/tax?period=${getP()}${save?'&save=true':''}`);
      if(d.detail){ msg.className='msg err'; msg.textContent = d.detail; return; }
      msg.className='msg ok'; msg.textContent = save ? '已存為申報草稿' : '';
      show(d);
    };
    addBtn('查詢', ()=>load(false));
    addBtn('存為申報草稿', ()=>load(true), 'btn gray');
    ctl.appendChild(msg);
    load(false);

  } else if(tab === 'dailysales'){
    const getD = addInput('日期','date',today,'rptD');
    const load = async () => {
      const d = await api.get('accounting/reports/daily-sales?report_date='+getD());
      if(d.detail){ body.innerHTML = `<p class="msg err">${esc(d.detail)}</p>`; return; }
      const H = ['發票號碼','客戶','客戶名稱','品項數','未稅','稅額','含稅','毛利','付款狀態'];
      body.innerHTML = rptTable(H, d.rows.map(r=>({cells:[
        esc(r.invoice_number), esc(r.customer_code), esc(r.customer_name), r.item_count,
        fmt(r.total_pretax), fmt(r.total_tax), fmt(r.total_withtax), fmt(r.gross_profit),
        r.payment_status]})),
        [`合計 ${d.totals.invoice_count} 張`,'','','',fmt(d.totals.total_pretax),
         fmt(d.totals.total_tax),fmt(d.totals.total_withtax),fmt(d.totals.gross_profit),'']);
      exportData = [H, d.rows.map(r=>[r.invoice_number,r.customer_code,r.customer_name,r.item_count,
        r.total_pretax,r.total_tax,r.total_withtax,r.gross_profit,r.payment_status])];
    };
    addBtn('查詢', load); addExport('日銷售報表'); load();
  }
}

// ------------------------- nav -------------------------
const PAGES = [
  ['dashboard','儀表板',renderDashboard],
  ['purchase','建立進貨單',renderPurchase],
  ['inventory','庫存/分裝',renderInventory],
  ['bulk-items','原物料',()=>renderCrud(CONFIGS['bulk-items'])],
  ['products','產品',()=>renderCrud(CONFIGS['products'])],
  ['sales','建立銷貨單',renderSales],
  ['suppliers','供應商',()=>renderCrud(CONFIGS['suppliers'])],
  ['customers','客戶',()=>renderCrud(CONFIGS['customers'])],
  ['sales-invoice','銷售發票',renderSalesInvoice],
  ['purchase-invoice','採購發票',renderPurchaseInvoice],
  ['payment','收付款',renderPayment],
  ['reports','報表',()=>renderReports()],
];
const nav = document.getElementById('nav');
const main = document.getElementById('main');
let currentPage = 'dashboard';

// ------------------------- 系統架構圖彈窗 -------------------------
const mapModal = document.getElementById('mapModal');
const mapFrame = mapModal.querySelector('iframe');
const sendMapFocus = ()=>{
  try{ mapFrame.contentWindow.postMessage({type:'focus', page: currentPage}, '*'); }catch(e){}
};
document.getElementById('mapFab').onclick = ()=>{
  if(!mapFrame.src){
    mapFrame.src = mapFrame.dataset.src;  // 首次開啟才載入
    mapFrame.addEventListener('load', sendMapFocus, {once:true});
  }else{
    sendMapFocus();
  }
  mapModal.hidden = false;
};
document.getElementById('mapClose').onclick = ()=>{ mapModal.hidden = true; };
mapModal.addEventListener('click', e=>{ if(e.target===mapModal) mapModal.hidden = true; });
document.addEventListener('keydown', e=>{ if(e.key==='Escape') mapModal.hidden = true; });
PAGES.forEach(([key,label,fn],i)=>{
  const b = document.createElement('button');
  b.textContent = label;
  b.onclick = ()=>{ currentPage = key;
                    document.querySelectorAll('nav button').forEach(x=>x.classList.remove('active'));
                    b.classList.add('active'); fn(); };
  if(i===0) b.classList.add('active');
  nav.appendChild(b);
});
renderDashboard();
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def index():
    return PAGE


def main() -> None:
    """Console entry point (animal-an-web) — host/port/reload 由 config.environments 依 ANIMAL_AN_ENV 決定"""
    import uvicorn
    from config.environments import current_config as cfg
    uvicorn.run("web.app:app", host=cfg.API_HOST, port=cfg.API_PORT, reload=cfg.API_RELOAD)


if __name__ == "__main__":
    main()
