"""M2 unit tests — InventoryViewModel against in-memory SQLite."""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models import Base  # noqa: E402
from models.product import Product, Batch  # noqa: E402
from models.inventory import (  # noqa: E402
    BulkItem, BulkBatch, InventoryTransaction, RepackOrder,
    TransactionType, ReferenceType,
)
from models.enums import (  # noqa: E402
    ItemKind, QCStatus, ProductType, StorageType, PackageType,
)
from viewmodels.inventory_vm import InventoryViewModel  # noqa: E402


@pytest.fixture()
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


@pytest.fixture()
def vm(session):
    return InventoryViewModel(session)


@pytest.fixture()
def bulk_item(vm):
    ok, msg, item = vm.create_bulk_item({
        'code': 'BLK-001', 'name': '豬瘟疫苗原裝桶', 'unit': '桶',
        'min_quantity': 2,
    })
    assert ok, msg
    return item


@pytest.fixture()
def product(session, bulk_item):
    p = Product(
        code='SKU-001', name='豬瘟疫苗 100mL/瓶',
        product_type=ProductType.VACCINE,
        storage_type=StorageType.REFRIGERATED,
        package_type=PackageType.BOTTLE,
        unit='瓶', reorder_point=10, manufacturer='原廠A',
        shelf_life_months=24,
        bulk_item_id=bulk_item.id, units_per_bulk=50,
        selling_price=350.0, spec='100 mL/瓶',
    )
    session.add(p)
    session.commit()
    return p


EXPIRY = datetime.now() + timedelta(days=365)


def receive(vm, qty=10, cost=1000.0, batch='B-2026-01', expiry=EXPIRY):
    return vm.receive_bulk(
        bulk_code='BLK-001', batch_number=batch,
        quantity=qty, unit_cost=cost, expiry_date=expiry,
    )


# ---------------------------------------------------------------- 進：入庫
class TestReceiveBulk:
    def test_receive_creates_batch_with_cost_and_expiry(self, vm, bulk_item, session):
        ok, msg = receive(vm)
        assert ok, msg
        batch = session.query(BulkBatch).one()
        assert batch.quantity == 10
        assert batch.unit_cost == 1000.0
        assert batch.expiry_date == EXPIRY
        assert bulk_item.quantity == 10  # 主檔彙總

    def test_receive_rejects_missing_expiry(self, vm, bulk_item):
        ok, msg = vm.receive_bulk('BLK-001', 'B-X', 10, 1000.0, expiry_date=None)
        assert not ok
        assert '效期' in msg or 'Expiry' in msg

    def test_receive_rejects_missing_cost(self, vm, bulk_item):
        ok, msg = vm.receive_bulk('BLK-001', 'B-X', 10, None, expiry_date=EXPIRY)
        assert not ok

    def test_receive_writes_ledger_with_balance(self, vm, bulk_item, session):
        receive(vm, qty=10)
        receive(vm, qty=5)  # same batch
        txns = session.query(InventoryTransaction).order_by(InventoryTransaction.id).all()
        assert [t.balance_after for t in txns] == [10, 15]
        assert all(t.item_kind == ItemKind.BULK for t in txns)
        assert all(t.reference_type == ReferenceType.PURCHASE_ORDER for t in txns)

    def test_receive_unknown_item_fails(self, vm):
        ok, msg = vm.receive_bulk('NOPE', 'B-1', 1, 1, EXPIRY)
        assert not ok


# ---------------------------------------------------------------- 分裝
class TestRepack:
    def test_repack_converts_and_allocates_cost(self, vm, bulk_item, product, session):
        receive(vm, qty=10, cost=1000.0)
        bulk_batch = session.query(BulkBatch).one()

        ok, msg, order = vm.repack(
            bulk_batch_id=bulk_batch.id, product_id=product.id,
            bulk_qty=2, output_batch_number='OUT-001', expiry_date=EXPIRY,
        )
        assert ok, msg
        # 數量 = 原裝 × 換算率
        assert order.output_qty == 100  # 2 × 50
        out_batch = session.get(Batch, order.output_batch_id)
        assert out_batch.quantity == 100
        # 成本分攤 = 1000 / 50
        assert out_batch.unit_cost == pytest.approx(20.0)
        # 原裝扣帳
        assert bulk_batch.quantity == 8
        assert bulk_item.quantity == 8

    def test_repack_writes_two_ledger_rows(self, vm, bulk_item, product, session):
        receive(vm)
        bulk_batch = session.query(BulkBatch).one()
        vm.repack(bulk_batch.id, product.id, 1, 'OUT-001', EXPIRY)
        txns = session.query(InventoryTransaction).filter(
            InventoryTransaction.reference_type == ReferenceType.REPACK
        ).all()
        kinds = {(t.item_kind, t.transaction_type) for t in txns}
        assert kinds == {
            (ItemKind.BULK, TransactionType.OUT),
            (ItemKind.SELLABLE, TransactionType.IN),
        }

    def test_repack_rejects_insufficient_bulk(self, vm, bulk_item, product, session):
        receive(vm, qty=1)
        bulk_batch = session.query(BulkBatch).one()
        ok, msg, _ = vm.repack(bulk_batch.id, product.id, 5, 'OUT-001', EXPIRY)
        assert not ok
        assert 'Insufficient' in msg

    def test_repack_rejects_missing_expiry(self, vm, bulk_item, product, session):
        receive(vm)
        bulk_batch = session.query(BulkBatch).one()
        ok, msg, _ = vm.repack(bulk_batch.id, product.id, 1, 'OUT-001', None)
        assert not ok

    def test_repack_rejects_foreign_product(self, vm, bulk_item, product, session):
        """Product belonging to another bulk item cannot consume this batch."""
        other = BulkItem(code='BLK-002', name='另一原裝', unit='桶')
        session.add(other)
        session.commit()
        receive(vm)
        bulk_batch = session.query(BulkBatch).one()
        product.bulk_item_id = other.id
        session.commit()
        ok, msg, _ = vm.repack(bulk_batch.id, product.id, 1, 'OUT-001', EXPIRY)
        assert not ok

    def test_repack_number_sequence(self, vm, bulk_item, product, session):
        receive(vm, qty=10)
        bulk_batch = session.query(BulkBatch).one()
        _, _, o1 = vm.repack(bulk_batch.id, product.id, 1, 'OUT-001', EXPIRY)
        _, _, o2 = vm.repack(bulk_batch.id, product.id, 1, 'OUT-002', EXPIRY)
        assert o1.repack_number.endswith('-001')
        assert o2.repack_number.endswith('-002')


# ---------------------------------------------------------------- 銷：FEFO
class TestIssueSalesFEFO:
    def _make_sellable_batches(self, session, product):
        near = Batch(product_id=product.id, batch_number='NEAR',
                     manufacture_date=datetime.now(),
                     expiry_date=datetime.now() + timedelta(days=30),
                     quantity=40, unit_cost=20.0,
                     quality_check_status=QCStatus.PASSED.value)
        far = Batch(product_id=product.id, batch_number='FAR',
                    manufacture_date=datetime.now(),
                    expiry_date=datetime.now() + timedelta(days=300),
                    quantity=100, unit_cost=22.0,
                    quality_check_status=QCStatus.PASSED.value)
        session.add_all([near, far])
        session.commit()
        return near, far

    def test_fefo_picks_nearest_expiry_first(self, vm, product, session):
        near, far = self._make_sellable_batches(session, product)
        ok, msg, alloc = vm.issue_sales('SKU-001', 60, reference_id=1)
        assert ok, msg
        assert [a['batch_number'] for a in alloc] == ['NEAR', 'FAR']
        assert [a['quantity'] for a in alloc] == [40, 20]
        assert near.quantity == 0
        assert far.quantity == 80

    def test_insufficient_stock_rejected_untouched(self, vm, product, session):
        near, far = self._make_sellable_batches(session, product)
        ok, msg, alloc = vm.issue_sales('SKU-001', 999)
        assert not ok
        assert near.quantity == 40 and far.quantity == 100
        assert session.query(InventoryTransaction).count() == 0

    def test_failed_qc_batches_excluded(self, vm, product, session):
        near, far = self._make_sellable_batches(session, product)
        near.quality_check_status = QCStatus.QUARANTINED.value
        session.commit()
        ok, _, alloc = vm.issue_sales('SKU-001', 50)
        assert ok
        assert [a['batch_number'] for a in alloc] == ['FAR']

    def test_ledger_rows_per_allocation(self, vm, product, session):
        self._make_sellable_batches(session, product)
        vm.issue_sales('SKU-001', 60, reference_id=7)
        txns = session.query(InventoryTransaction).all()
        assert len(txns) == 2
        assert all(t.item_kind == ItemKind.SELLABLE for t in txns)
        assert all(t.reference_type == ReferenceType.SALES_ORDER for t in txns)
        assert all(t.reference_id == 7 for t in txns)


# ---------------------------------------------------------------- 調整 / 查詢
class TestAdjustAndQueries:
    def test_adjust_bulk_positive_and_negative(self, vm, bulk_item, session):
        receive(vm, qty=10)
        batch = session.query(BulkBatch).one()
        ok, _ = vm.adjust_bulk(batch.id, -3, reason='盤虧')
        assert ok and batch.quantity == 7
        ok, _ = vm.adjust_bulk(batch.id, 1, reason='盤盈')
        assert ok and batch.quantity == 8
        ok, msg = vm.adjust_bulk(batch.id, -99, reason='過頭')
        assert not ok

    def test_low_stock_alert(self, vm, bulk_item):
        # min_quantity=2, no stock yet -> low
        assert vm.check_low_stock()[0]['code'] == 'BLK-001'
        receive(vm, qty=10)
        assert vm.check_low_stock() == []

    def test_expiring_batches_both_kinds(self, vm, bulk_item, product, session):
        soon = datetime.now() + timedelta(days=10)
        receive(vm, qty=5, expiry=soon)
        session.add(Batch(product_id=product.id, batch_number='S-1',
                          manufacture_date=datetime.now(), expiry_date=soon,
                          quantity=3, unit_cost=20.0,
                          quality_check_status=QCStatus.PASSED.value))
        session.commit()
        rows = vm.get_expiring_batches(days=30)
        assert {r['kind'] for r in rows} == {'bulk', 'sellable'}

    def test_stock_valuation(self, vm, bulk_item, product, session):
        receive(vm, qty=10, cost=1000.0)   # bulk value 10000
        bulk_batch = session.query(BulkBatch).one()
        vm.repack(bulk_batch.id, product.id, 2, 'OUT-001', EXPIRY)
        # bulk 8×1000 = 8000, sellable 100×20 = 2000, total unchanged
        v = vm.get_stock_valuation()
        assert v['bulk_value'] == pytest.approx(8000)
        assert v['sellable_value'] == pytest.approx(2000)
        assert v['total_value'] == pytest.approx(10000)

    def test_batch_transactions_filter(self, vm, bulk_item, session):
        receive(vm, qty=10)
        receive(vm, qty=5, batch='B-2026-02')
        txns = vm.get_batch_transactions('BLK-001', batch_number='B-2026-02')
        assert len(txns) == 1 and txns[0].quantity == 5


# ---------------------------------------------------------------- legacy
class TestLegacyCompat:
    def test_create_material_alias(self, vm):
        ok, msg, m = vm.create_material({'code': 'M-1', 'name': '舊介面', 'unit': 'kg'})
        assert ok
        assert vm.get_material('M-1').name == '舊介面'

    def test_duplicate_code_rejected(self, vm, bulk_item):
        ok, msg, _ = vm.create_bulk_item({'code': 'BLK-001', 'name': 'dup', 'unit': '桶'})
        assert not ok
