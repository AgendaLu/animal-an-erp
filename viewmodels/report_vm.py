"""報表 ViewModel — 規格書 §6(M5)報表與 §5.6 信用控管告警。

全部由本地 SQLite 彙總,以規格(SKU)為列:
- 進銷存月報:期初/本期進(分裝產出)/本期銷/調整/期末,量與成本金額
- 庫存即時表:各 SKU 現量、近效期批號、低於再訂購點標記
- 銷售毛利:依客戶×SKU 之銷量、收入、批次分攤成本、毛利
- 分裝產出:原裝耗用 vs 產出、換算差異、成本守恆檢查
- 信用告警:客戶應收餘額(AR 未結)超過信用額度

金額口徑:月報與即時表以批次成本計價;毛利報表另列售價收入。
"""
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from models.enums import ItemKind
from models.inventory import (
    InventoryTransaction, TransactionType, RepackOrder, BulkBatch,
)
from models.product import Product, Batch
from models.partner import Customer
from models.order import SalesOrder, SalesOrderItem
from models.accounting import AccountsReceivable


def _signed(txn_type: TransactionType, qty: float) -> float:
    """帳本慣例:IN/OUT 記正數(方向看 type),ADJUST 記 ± 值。"""
    return -qty if txn_type == TransactionType.OUT else qty


def _month_bounds(period: str) -> tuple:
    year, month = (int(x) for x in period.split("-"))
    start = datetime(year, month, 1)
    end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    return start, end


class ReportViewModel:
    def __init__(self, session: Session):
        self.session = session

    # ------------------------------------------------------- 進銷存月報

    def monthly_inventory_report(self, period: str) -> dict:
        """SKU 為列:期初/本期進(含分裝產出)/本期銷/調整/期末。period=YYYY-MM"""
        start, end = _month_bounds(period)

        txns = self.session.execute(
            select(InventoryTransaction, Batch.product_id)
            .join(Batch, InventoryTransaction.batch_id == Batch.id)
            .where(InventoryTransaction.item_kind == ItemKind.SELLABLE,
                   InventoryTransaction.transaction_date < end)
        ).all()

        buckets: dict = {}
        for txn, product_id in txns:
            b = buckets.setdefault(product_id, {
                "open_qty": 0.0, "open_amount": 0.0,
                "in_qty": 0.0, "in_amount": 0.0,
                "out_qty": 0.0, "out_amount": 0.0,
                "adjust_qty": 0.0, "adjust_amount": 0.0,
            })
            qty = txn.quantity
            amount = qty * (txn.unit_cost or 0)
            if txn.transaction_date < start:
                b["open_qty"] += _signed(txn.transaction_type, qty)
                b["open_amount"] += _signed(txn.transaction_type, amount)
            elif txn.transaction_type == TransactionType.IN:
                b["in_qty"] += qty
                b["in_amount"] += amount
            elif txn.transaction_type == TransactionType.OUT:
                b["out_qty"] += qty
                b["out_amount"] += amount
            else:  # ADJUST:qty 已含正負
                b["adjust_qty"] += qty
                b["adjust_amount"] += amount

        products = {
            p.id: p for p in self.session.scalars(
                select(Product).where(Product.id.in_(buckets.keys()))
            )
        } if buckets else {}

        rows = []
        for pid, b in buckets.items():
            p = products.get(pid)
            closing_qty = b["open_qty"] + b["in_qty"] - b["out_qty"] + b["adjust_qty"]
            closing_amount = (b["open_amount"] + b["in_amount"]
                              - b["out_amount"] + b["adjust_amount"])
            rows.append({
                "product_code": p.code if p else f"#{pid}",
                "product_name": p.name if p else "",
                "spec": (p.spec if p else None) or "",
                "unit": p.unit if p else "",
                **{k: round(v, 2) for k, v in b.items()},
                "closing_qty": round(closing_qty, 2),
                "closing_amount": round(closing_amount, 2),
            })
        rows.sort(key=lambda r: r["product_code"])

        totals = {k: round(sum(r[k] for r in rows), 2)
                  for k in ("open_amount", "in_amount", "out_amount",
                            "adjust_amount", "closing_amount")}
        return {"period": period, "rows": rows, "totals": totals}

    # ------------------------------------------------------- 庫存即時表

    def stock_snapshot(self, expiry_days: int = 90) -> list:
        """各 SKU 現量、庫存金額、近效期批號、低於再訂購點標記。"""
        cutoff = datetime.now() + timedelta(days=expiry_days)
        products = self.session.scalars(
            select(Product)
            .options(joinedload(Product.batches))
            .where(Product.is_active == True)  # noqa: E712
            .order_by(Product.code)
        ).unique().all()

        rows = []
        for p in products:
            live = [b for b in p.batches if b.quantity > 0]
            qty = sum(b.quantity for b in live)
            value = sum(b.quantity * (b.unit_cost or 0) for b in live)
            near = [b.batch_number for b in live
                    if b.expiry_date and b.expiry_date <= cutoff]
            rows.append({
                "product_code": p.code,
                "product_name": p.name,
                "spec": p.spec or "",
                "unit": p.unit,
                "quantity": round(qty, 2),
                "stock_value": round(value, 2),
                "batch_count": len(live),
                "near_expiry_batches": near,
                "reorder_point": p.reorder_point,
                "below_reorder": bool(p.reorder_point and qty < p.reorder_point),
            })
        return rows

    # ------------------------------------------------------- 銷售毛利

    def sales_profit_report(self, start: date, end: date) -> dict:
        """依客戶×SKU:銷量、收入、批次分攤成本、毛利。日期含頭尾。"""
        s = datetime.combine(start, datetime.min.time())
        e = datetime.combine(end + timedelta(days=1), datetime.min.time())

        items = self.session.execute(
            select(SalesOrderItem, SalesOrder, Product, Batch)
            .join(SalesOrder, SalesOrderItem.so_id == SalesOrder.id)
            .join(Product, SalesOrderItem.product_id == Product.id)
            .join(Batch, SalesOrderItem.batch_id == Batch.id)
            .options(joinedload(SalesOrder.customer))
            .where(SalesOrder.order_date >= s, SalesOrder.order_date < e)
        ).all()

        grouped: dict = {}
        for item, so, product, batch in items:
            customer = so.customer
            key = (customer.code if customer else "?", product.code)
            g = grouped.setdefault(key, {
                "customer_code": customer.code if customer else "?",
                "customer_name": customer.name if customer else "",
                "product_code": product.code,
                "product_name": product.name,
                "unit": product.unit,
                "quantity": 0.0, "revenue": 0.0, "cost": 0.0,
            })
            g["quantity"] += item.quantity
            g["revenue"] += item.total_price
            g["cost"] += item.quantity * (batch.unit_cost or 0)

        rows = []
        for g in grouped.values():
            gross = g["revenue"] - g["cost"]
            rows.append({
                **{k: (round(v, 2) if isinstance(v, float) else v)
                   for k, v in g.items()},
                "gross_profit": round(gross, 2),
                "margin_pct": round(gross / g["revenue"] * 100, 1)
                              if g["revenue"] else 0.0,
            })
        rows.sort(key=lambda r: (r["customer_code"], r["product_code"]))

        totals = {k: round(sum(r[k] for r in rows), 2)
                  for k in ("quantity", "revenue", "cost", "gross_profit")}
        totals["margin_pct"] = (round(totals["gross_profit"] / totals["revenue"] * 100, 1)
                                if totals.get("revenue") else 0.0)
        return {"start": start.isoformat(), "end": end.isoformat(),
                "rows": rows, "totals": totals}

    # ------------------------------------------------------- 分裝產出

    def repack_output_report(self, start: date, end: date) -> list:
        """每張分裝單:原裝耗用、預期/實際產出、換算差異、成本守恆。"""
        s = datetime.combine(start, datetime.min.time())
        e = datetime.combine(end + timedelta(days=1), datetime.min.time())

        orders = self.session.scalars(
            select(RepackOrder)
            .options(joinedload(RepackOrder.bulk_batch)
                     .joinedload(BulkBatch.bulk_item))
            .where(RepackOrder.repack_date >= s, RepackOrder.repack_date < e)
            .order_by(RepackOrder.repack_date, RepackOrder.id)
        ).all()

        rows = []
        for o in orders:
            product = self.session.get(Product, o.product_id)
            out_batch = (self.session.get(Batch, o.output_batch_id)
                         if o.output_batch_id else None)
            expected = o.bulk_qty_consumed * (product.units_per_bulk or 0) if product else 0
            bulk_cost = o.bulk_qty_consumed * (o.bulk_batch.unit_cost or 0)
            output_value = o.output_qty * (out_batch.unit_cost or 0) if out_batch else 0
            rows.append({
                "repack_number": o.repack_number,
                "repack_date": o.repack_date.isoformat()[:10],
                "bulk_code": o.bulk_batch.bulk_item.code,
                "bulk_batch_number": o.bulk_batch.batch_number,
                "bulk_qty_consumed": o.bulk_qty_consumed,
                "product_code": product.code if product else f"#{o.product_id}",
                "output_batch_number": out_batch.batch_number if out_batch else "",
                "expected_output": round(expected, 2),
                "output_qty": o.output_qty,
                "variance": round(o.output_qty - expected, 2),
                "bulk_cost": round(bulk_cost, 2),
                "output_value": round(output_value, 2),
                "operator": o.operator or "",
            })
        return rows

    # ------------------------------------------------------- 信用告警

    def credit_alerts(self, over_only: bool = False) -> list:
        """客戶應收餘額(AR 未結彙總)對信用額度;超額標記告警。"""
        outstanding = dict(self.session.execute(
            select(AccountsReceivable.customer_code,
                   func.sum(AccountsReceivable.outstanding_amount))
            .group_by(AccountsReceivable.customer_code)
        ).all())

        customers = self.session.scalars(
            select(Customer).where(Customer.is_active == True)  # noqa: E712
            .order_by(Customer.code)
        ).all()

        rows = []
        for c in customers:
            balance = round(outstanding.get(c.code, 0) or 0, 2)
            limit = c.credit_limit or 0
            over = bool(limit and balance > limit)
            if over_only and not over:
                continue
            rows.append({
                "customer_code": c.code,
                "customer_name": c.name,
                "credit_limit": limit,
                "outstanding": balance,
                "available": round(limit - balance, 2) if limit else None,
                "over_limit": over,
            })
        return rows
