"""Inventory ViewModel — UI-free business logic for 進銷存 (spec v0.4 M2).

Core flows:
  進  receive_bulk()   原裝入庫 (IN/PO)  — expiry + per-batch cost required (決議)
  分裝 repack()         原裝 OUT/REPACK + 分裝品 IN/REPACK (僅扣帳決議)
  銷  issue_sales()    分裝品出庫, FEFO across batches (OUT/SO)
  調整 adjust_bulk()    盤盈虧 (ADJUST/ADJ)

This module must not import anything from views/ — it is the future REST API core.
"""
from typing import Optional, List, Tuple, Dict
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

from models.inventory import (
    BulkItem, BulkBatch, InventoryTransaction, RepackOrder,
    TransactionType, ReferenceType,
)
from models.product import Product, Batch
from models.enums import ItemKind, QCStatus
from utils.logger import get_logger

logger = get_logger(__name__)


class InventoryViewModel:
    """ViewModel for inventory management operations"""

    def __init__(self, session: Session):
        self.session = session
        self.logger = get_logger(__name__)

    # ------------------------------------------------------------------ #
    # 原裝品主檔
    # ------------------------------------------------------------------ #
    def create_bulk_item(self, data: Dict) -> Tuple[bool, str, Optional[BulkItem]]:
        """Create a new bulk item (原裝品)."""
        try:
            if not self._validate_bulk_item_data(data):
                return False, "Invalid bulk item data", None

            item = BulkItem(
                code=data['code'].strip(),
                name=data['name'].strip(),
                description=data.get('description', ''),
                unit=data['unit'],
                min_quantity=data.get('min_quantity', 0),
                storage_temp=data.get('storage_temp'),
                product_type=data.get('product_type'),
                storage_type=data.get('storage_type'),
                shelf_life_months=data.get('shelf_life_months'),
                default_supplier_id=data.get('default_supplier_id'),
                registration_number=data.get('registration_number'),
                country_of_origin=data.get('country_of_origin'),
            )
            self.session.add(item)
            self.session.commit()
            return True, "Bulk item created successfully", item

        except IntegrityError:
            self.session.rollback()
            return False, "Bulk item code already exists", None
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Error creating bulk item: {e}")
            return False, f"Error creating bulk item: {e}", None

    # Legacy name used by existing PyQt dialogs (deprecated UI layer)
    create_material = create_bulk_item

    def get_bulk_item(self, identifier: str) -> Optional[BulkItem]:
        """Get bulk item by code or ID."""
        try:
            item = self.session.query(BulkItem).filter(
                BulkItem.code == identifier
            ).first()
            if not item and str(identifier).isdigit():
                item = self.session.get(BulkItem, int(identifier))
            return item
        except Exception as e:
            self.logger.error(f"Error getting bulk item: {e}")
            return None

    get_material = get_bulk_item

    # ------------------------------------------------------------------ #
    # 進：原裝入庫
    # ------------------------------------------------------------------ #
    def receive_bulk(self,
                     bulk_code: str,
                     batch_number: str,
                     quantity: float,
                     unit_cost: float,
                     expiry_date: datetime,
                     manufacturing_date: Optional[datetime] = None,
                     lot_number: Optional[str] = None,
                     supplier_id: Optional[int] = None,
                     reference_id: int = 0,
                     transaction_date: Optional[datetime] = None,
                     notes: Optional[str] = None) -> Tuple[bool, str]:
        """原裝品採購入庫 — per-batch cost and expiry are mandatory (決議)."""
        if quantity is None or quantity <= 0:
            return False, "Quantity must be positive"
        if unit_cost is None or unit_cost < 0:
            return False, "Unit cost is required (批次成本)"
        if expiry_date is None:
            return False, "Expiry date is required (效期必填)"

        try:
            item = self.get_bulk_item(bulk_code)
            if not item:
                return False, f"Bulk item {bulk_code} not found"

            batch = self.session.query(BulkBatch).filter(
                BulkBatch.material_id == item.id,
                BulkBatch.batch_number == batch_number
            ).first()
            if batch is None:
                batch = BulkBatch(
                    material_id=item.id,
                    batch_number=batch_number,
                    quantity=0,
                    manufacturing_date=manufacturing_date,
                    expiry_date=expiry_date,
                    unit_cost=unit_cost,
                    lot_number=lot_number,
                    supplier_id=supplier_id,
                    quality_status=QCStatus.PASSED,
                )
                self.session.add(batch)
                self.session.flush()

            batch.quantity += quantity
            self._record_txn(
                item_kind=ItemKind.BULK,
                batch_id=batch.id,
                txn_type=TransactionType.IN,
                quantity=quantity,
                unit_cost=unit_cost,
                balance_after=batch.quantity,
                reference_type=ReferenceType.PURCHASE_ORDER,
                reference_id=reference_id,
                transaction_date=transaction_date,
                notes=notes,
            )
            self._refresh_bulk_quantity(item)
            self.session.commit()
            return True, f"Received {quantity} {item.unit}. Batch balance: {batch.quantity}"

        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Error receiving bulk: {e}")
            return False, f"Error receiving bulk: {e}"

    # ------------------------------------------------------------------ #
    # 分裝：原裝 → 分裝品
    # ------------------------------------------------------------------ #
    def repack(self,
               bulk_batch_id: int,
               product_id: int,
               bulk_qty: float,
               output_batch_number: str,
               expiry_date: datetime,
               operator: Optional[str] = None,
               transaction_date: Optional[datetime] = None,
               notes: Optional[str] = None) -> Tuple[bool, str, Optional[RepackOrder]]:
        """分裝轉換 (僅扣帳決議): bulk OUT/REPACK + sellable IN/REPACK.

        output_qty = bulk_qty × product.units_per_bulk
        sellable unit_cost = bulk unit_cost ÷ units_per_bulk (批次成本分攤)
        expiry_date 由操作者填入 (必填).
        """
        if bulk_qty is None or bulk_qty <= 0:
            return False, "Bulk quantity must be positive", None
        if expiry_date is None:
            return False, "Expiry date is required (效期必填)", None

        try:
            bulk_batch = self.session.get(BulkBatch, bulk_batch_id)
            if not bulk_batch:
                return False, f"Bulk batch {bulk_batch_id} not found", None
            product = self.session.get(Product, product_id)
            if not product:
                return False, f"Product {product_id} not found", None
            if product.bulk_item_id != bulk_batch.material_id:
                return False, "Product is not a SKU of this bulk item", None
            if not product.units_per_bulk or product.units_per_bulk <= 0:
                return False, "Product units_per_bulk is not set", None
            if bulk_batch.quantity < bulk_qty:
                return False, "Insufficient bulk stock", None
            if bulk_batch.unit_cost is None:
                return False, "Bulk batch has no unit cost (批次成本缺漏)", None

            output_qty = bulk_qty * product.units_per_bulk
            sellable_unit_cost = bulk_batch.unit_cost / product.units_per_bulk

            # 產出分裝品批號
            out_batch = Batch(
                product_id=product.id,
                batch_number=output_batch_number,
                manufacture_date=transaction_date or datetime.now(),
                expiry_date=expiry_date,
                quantity=output_qty,
                unit_cost=sellable_unit_cost,
                quality_check_status=QCStatus.PASSED.value,
            )
            self.session.add(out_batch)
            self.session.flush()

            repack_order = RepackOrder(
                repack_number=self._next_repack_number(),
                bulk_batch_id=bulk_batch.id,
                bulk_qty_consumed=bulk_qty,
                product_id=product.id,
                output_batch_id=out_batch.id,
                output_qty=output_qty,
                repack_date=transaction_date or datetime.now(),
                operator=operator,
                notes=notes,
            )
            self.session.add(repack_order)
            self.session.flush()

            # 原裝扣帳
            bulk_batch.quantity -= bulk_qty
            self._record_txn(
                item_kind=ItemKind.BULK,
                batch_id=bulk_batch.id,
                txn_type=TransactionType.OUT,
                quantity=bulk_qty,
                unit_cost=bulk_batch.unit_cost,
                balance_after=bulk_batch.quantity,
                reference_type=ReferenceType.REPACK,
                reference_id=repack_order.id,
                transaction_date=transaction_date,
                notes=notes,
            )
            self._refresh_bulk_quantity(bulk_batch.bulk_item)

            # 分裝品入帳
            self._record_txn(
                item_kind=ItemKind.SELLABLE,
                batch_id=out_batch.id,
                txn_type=TransactionType.IN,
                quantity=output_qty,
                unit_cost=sellable_unit_cost,
                balance_after=out_batch.quantity,
                reference_type=ReferenceType.REPACK,
                reference_id=repack_order.id,
                transaction_date=transaction_date,
                notes=notes,
            )

            self.session.commit()
            return True, (
                f"Repacked {bulk_qty} bulk into {output_qty} {product.unit} "
                f"(batch {output_batch_number})"
            ), repack_order

        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Error repacking: {e}")
            return False, f"Error repacking: {e}", None

    # ------------------------------------------------------------------ #
    # 銷：分裝品出庫 (FEFO)
    # ------------------------------------------------------------------ #
    def issue_sales(self,
                    product_code: str,
                    quantity: float,
                    reference_id: int = 0,
                    transaction_date: Optional[datetime] = None,
                    notes: Optional[str] = None) -> Tuple[bool, str, List[Dict]]:
        """銷售出庫 — FEFO (先到期先出) across sellable batches.

        Returns (success, message, allocations) where each allocation is
        {batch_id, batch_number, quantity, unit_cost}.
        """
        if quantity is None or quantity <= 0:
            return False, "Quantity must be positive", []

        try:
            product = self.session.query(Product).filter(
                Product.code == product_code
            ).first()
            if not product:
                return False, f"Product {product_code} not found", []

            batches = self.session.query(Batch).filter(
                Batch.product_id == product.id,
                Batch.quantity > 0,
                Batch.quality_check_status == QCStatus.PASSED.value,
            ).order_by(Batch.expiry_date.asc()).all()

            available = sum(b.quantity for b in batches)
            if available < quantity:
                return False, (
                    f"Insufficient stock: need {quantity}, available {available}"
                ), []

            remaining = quantity
            allocations: List[Dict] = []
            for batch in batches:
                if remaining <= 0:
                    break
                take = min(batch.quantity, remaining)
                batch.quantity -= take
                remaining -= take
                self._record_txn(
                    item_kind=ItemKind.SELLABLE,
                    batch_id=batch.id,
                    txn_type=TransactionType.OUT,
                    quantity=take,
                    unit_cost=batch.unit_cost,
                    balance_after=batch.quantity,
                    reference_type=ReferenceType.SALES_ORDER,
                    reference_id=reference_id,
                    transaction_date=transaction_date,
                    notes=notes,
                )
                allocations.append({
                    'batch_id': batch.id,
                    'batch_number': batch.batch_number,
                    'quantity': take,
                    'unit_cost': batch.unit_cost,
                })

            self.session.commit()
            return True, f"Issued {quantity} {product.unit} across {len(allocations)} batch(es)", allocations

        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Error issuing sales: {e}")
            return False, f"Error issuing sales: {e}", []

    # ------------------------------------------------------------------ #
    # 調整：盤盈虧
    # ------------------------------------------------------------------ #
    def adjust_bulk(self,
                    bulk_batch_id: int,
                    quantity_delta: float,
                    reason: str,
                    transaction_date: Optional[datetime] = None) -> Tuple[bool, str]:
        """庫存調整 (ADJUST/ADJ) — positive delta 盤盈, negative 盤虧."""
        if not quantity_delta:
            return False, "Adjustment delta cannot be zero"
        try:
            batch = self.session.get(BulkBatch, bulk_batch_id)
            if not batch:
                return False, f"Bulk batch {bulk_batch_id} not found"
            if batch.quantity + quantity_delta < 0:
                return False, "Adjustment would make stock negative"

            batch.quantity += quantity_delta
            self._record_txn(
                item_kind=ItemKind.BULK,
                batch_id=batch.id,
                txn_type=TransactionType.ADJUST,
                quantity=quantity_delta,
                unit_cost=batch.unit_cost,
                balance_after=batch.quantity,
                reference_type=ReferenceType.ADJUSTMENT,
                reference_id=0,
                transaction_date=transaction_date,
                notes=reason,
            )
            self._refresh_bulk_quantity(batch.bulk_item)
            self.session.commit()
            return True, f"Adjusted by {quantity_delta}. New balance: {batch.quantity}"
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Error adjusting inventory: {e}")
            return False, f"Error adjusting inventory: {e}"

    # ------------------------------------------------------------------ #
    # 查詢 / 告警
    # ------------------------------------------------------------------ #
    def check_low_stock(self) -> List[Dict]:
        """Bulk items at or below min_quantity."""
        try:
            items = self.session.query(BulkItem).filter(
                BulkItem.is_active == True,  # noqa: E712
                BulkItem.quantity <= BulkItem.min_quantity
            ).all()
            return [{
                'code': i.code,
                'name': i.name,
                'current_quantity': i.quantity,
                'min_quantity': i.min_quantity,
            } for i in items]
        except Exception as e:
            self.logger.error(f"Error checking low stock: {e}")
            return []

    def get_expiring_batches(self, days: int = 90) -> List[Dict]:
        """Batches (bulk + sellable) expiring within N days, soonest first."""
        cutoff = datetime.now() + timedelta(days=days)
        result: List[Dict] = []
        try:
            bulk = self.session.execute(
                select(BulkBatch)
                .options(joinedload(BulkBatch.bulk_item))
                .where(BulkBatch.expiry_date != None,  # noqa: E711
                       BulkBatch.expiry_date <= cutoff,
                       BulkBatch.quantity > 0)
            ).scalars().all()
            for b in bulk:
                result.append({
                    'kind': ItemKind.BULK.value,
                    'item_code': b.bulk_item.code,
                    'item_name': b.bulk_item.name,
                    'batch_number': b.batch_number,
                    'expiry_date': b.expiry_date,
                    'quantity': b.quantity,
                })
            sellable = self.session.execute(
                select(Batch)
                .options(joinedload(Batch.product))
                .where(Batch.expiry_date <= cutoff, Batch.quantity > 0)
            ).scalars().all()
            for b in sellable:
                result.append({
                    'kind': ItemKind.SELLABLE.value,
                    'item_code': b.product.code,
                    'item_name': b.product.name,
                    'batch_number': b.batch_number,
                    'expiry_date': b.expiry_date,
                    'quantity': b.quantity,
                })
            result.sort(key=lambda r: r['expiry_date'])
            return result
        except Exception as e:
            self.logger.error(f"Error getting expiring batches: {e}")
            return []

    def get_stock_valuation(self) -> Dict:
        """庫存金額 Σ(qty × unit_cost), bulk and sellable listed separately."""
        try:
            bulk_value = sum(
                (b.quantity or 0) * (b.unit_cost or 0)
                for b in self.session.query(BulkBatch).filter(BulkBatch.quantity > 0)
            )
            sellable_value = sum(
                (b.quantity or 0) * (b.unit_cost or 0)
                for b in self.session.query(Batch).filter(Batch.quantity > 0)
            )
            return {
                'bulk_value': bulk_value,
                'sellable_value': sellable_value,
                'total_value': bulk_value + sellable_value,
            }
        except Exception as e:
            self.logger.error(f"Error computing valuation: {e}")
            return {'bulk_value': 0, 'sellable_value': 0, 'total_value': 0}

    def get_batch_transactions(self,
                               bulk_code: str,
                               batch_number: Optional[str] = None,
                               start_date: Optional[datetime] = None,
                               end_date: Optional[datetime] = None) -> List[InventoryTransaction]:
        """Transaction history for a bulk item / batch."""
        try:
            query = self.session.query(InventoryTransaction)\
                .join(BulkBatch, InventoryTransaction.batch_id == BulkBatch.id)\
                .join(BulkItem)\
                .filter(BulkItem.code == bulk_code,
                        InventoryTransaction.item_kind == ItemKind.BULK)
            if batch_number:
                query = query.filter(BulkBatch.batch_number == batch_number)
            if start_date:
                query = query.filter(InventoryTransaction.transaction_date >= start_date)
            if end_date:
                query = query.filter(InventoryTransaction.transaction_date <= end_date)
            return query.order_by(InventoryTransaction.transaction_date.desc()).all()
        except Exception as e:
            self.logger.error(f"Error getting transactions: {e}")
            return []

    # ------------------------------------------------------------------ #
    # internals
    # ------------------------------------------------------------------ #
    def _record_txn(self, *, item_kind, batch_id, txn_type, quantity, unit_cost,
                    balance_after, reference_type, reference_id,
                    transaction_date=None, notes=None) -> InventoryTransaction:
        txn = InventoryTransaction(
            item_kind=item_kind,
            batch_id=batch_id,
            transaction_type=txn_type,
            quantity=quantity,
            unit_cost=unit_cost,
            balance_after=balance_after,
            reference_type=reference_type,
            reference_id=reference_id,
            transaction_date=transaction_date or datetime.now(),
            notes=notes,
        )
        self.session.add(txn)
        return txn

    def _refresh_bulk_quantity(self, item: BulkItem) -> None:
        item.quantity = sum(b.quantity for b in item.batches)

    def _next_repack_number(self) -> str:
        today = datetime.now().strftime("%Y%m%d")
        prefix = f"RP{today}-"
        last = self.session.query(RepackOrder).filter(
            RepackOrder.repack_number.like(f"{prefix}%")
        ).order_by(RepackOrder.repack_number.desc()).first()
        seq = int(last.repack_number.rsplit('-', 1)[1]) + 1 if last else 1
        return f"{prefix}{seq:03d}"

    def _validate_bulk_item_data(self, data: Dict) -> bool:
        required_fields = ['code', 'name', 'unit']
        return all(data.get(field) for field in required_fields)

    _validate_material_data = _validate_bulk_item_data
