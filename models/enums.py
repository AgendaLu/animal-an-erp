from enum import Enum

class ProductType(Enum):
    MEDICINE = "medicine"
    VACCINE = "vaccine"
    MEDICATED_FEED = "medicated_feed"
    SUPPLEMENT = "supplement"

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
