from enum import Enum

class ProductType(Enum):
    MEDICINE = "medicine"
    VACCINE = "vaccine"
    MEDICATED_FEED = "medicated_feed"
    SUPPLEMENT = "supplement"
    HYGIENE = "hygiene"

class StorageType(Enum):
    ROOM_TEMP = "room_temperature"
    REFRIGERATED = "refrigerated"
    FROZEN = "frozen"

class PackageType(Enum):
    BULK = "bulk"
    BAG = "bag"
    BOTTLE = "bottle"
    VIAL = "vial"
    BOX = "box"
    AMPOULE = "ampoule"
    SACHET = "sachet"

class OrderStatus(Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

class PaymentStatus(Enum):
    PENDING = "pending"
    PARTIAL = "partial"
    PAID = "paid"
    OVERDUE = "overdue"

class QCStatus(Enum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    QUARANTINED = "quarantined"

class ItemKind(Enum):
    """Polymorphic key for the unified inventory ledger"""
    BULK = "bulk"          # 原裝品 (BulkBatch)
    SELLABLE = "sellable"  # 分裝品 (Batch)

class SupplierType(Enum):
    MANUFACTURER = "manufacturer"  # 原廠
    IMPORTER = "importer"          # 進口商
    AGENT = "agent"                # 代理

class CustomerType(Enum):
    PIG_FARM = "pig_farm"          # 養豬場
    VET_CLINIC = "vet_clinic"      # 動物醫院
    FEED_MILL = "feed_mill"        # 飼料廠
    DISTRIBUTOR = "distributor"    # 經銷
    RETAIL = "retail"              # 零售
