"""
Constants for the ERP system
"""
from enum import Enum

class MaterialConstants:
    """Material related constants"""
    # Code format
    CODE_PREFIX = "M"
    CODE_LENGTH = 8  # M + 7 digits
    CODE_FORMAT = "M1234567"
    CODE_REGEX = r'^M\d{7}$'
    
    # Field constraints
    NAME_MIN_LENGTH = 2
    NAME_MAX_LENGTH = 100
    DESCRIPTION_MAX_LENGTH = 500
    UNIT_MAX_LENGTH = 20
    
    # Quantity constraints
    MAX_QUANTITY = 1000000
    MIN_QUANTITY = 0
    QUANTITY_DECIMALS = 2
    
    # Temperature constraints
    MIN_TEMP = -50
    MAX_TEMP = 50
    DEFAULT_TEMP = 25
    
    # UI constants
    DIALOG_MIN_WIDTH = 400
    TABLE_PAGE_SIZE = 50

class BatchConstants:
    """Batch related constants"""
    # Batch number format
    BATCH_PREFIX = "B"
    BATCH_FORMAT = "BYYYYMMDDXXX"  # B + date + 3 digits sequence
    BATCH_REGEX = r'^B\d{11}$'
    
    # Expiry constraints
    MIN_EXPIRY_DAYS = 1
    MAX_EXPIRY_YEARS = 5

class OrderConstants:
    """Order related constants"""
    # Order number format
    PO_PREFIX = "PO"  # Purchase Order
    SO_PREFIX = "SO"  # Sales Order
    ORDER_NUMBER_LENGTH = 12
    PO_FORMAT = "POYYYYMMXXXX"  # PO + year + month + 4 digits sequence
    SO_FORMAT = "SOYYYYMMXXXX"  # SO + year + month + 4 digits sequence

class StorageLocation(Enum):
    """Storage location types"""
    NORMAL = "NORMAL"      # 常溫儲存
    REFRIGERATED = "COOL"  # 冷藏儲存
    FROZEN = "FROZEN"      # 冷凍儲存

class TransactionType(Enum):
    """Inventory transaction types"""
    PURCHASE = "PO"        # 採購入庫
    SALES = "SO"          # 銷售出庫
    RETURN_IN = "RI"      # 退貨入庫
    RETURN_OUT = "RO"     # 退貨出庫
    ADJUSTMENT = "ADJ"     # 庫存調整
    MANUFACTURING = "MFG"  # 生產作業
    TRANSFER = "TRF"      # 庫存轉移

class UnitOfMeasure:
    """Standard units of measure"""
    WEIGHT = ["kg", "g", "mg"]           # 重量單位
    VOLUME = ["l", "ml"]                 # 體積單位
    QUANTITY = ["pcs", "box", "carton"]  # 數量單位
    
    @classmethod
    def get_all_units(cls) -> list:
        """Get all available units"""
        return cls.WEIGHT + cls.VOLUME + cls.QUANTITY

class ValidationMessages:
    """Validation error messages"""
    INVALID_CODE = "無效的物料代碼格式，必須為 M 開頭加上7位數字"
    INVALID_BATCH = "無效的批號格式，必須為 B 開頭加上日期及3位序號"
    INVALID_QUANTITY = "數量必須大於等於0"
    INVALID_TEMPERATURE = "溫度超出允許範圍"
    NAME_TOO_SHORT = "名稱長度不足"
    NAME_TOO_LONG = "名稱超出長度限制"
    REQUIRED_FIELD = "此欄位為必填"
    DUPLICATE_CODE = "物料代碼重複"
    INVALID_UNIT = "無效的單位"

class UIConstants:
    """UI related constants"""
    # Window sizes
    MIN_WINDOW_WIDTH = 1024
    MIN_WINDOW_HEIGHT = 768
    
    # Font sizes
    TITLE_FONT_SIZE = 24
    HEADER_FONT_SIZE = 18
    NORMAL_FONT_SIZE = 14
    SMALL_FONT_SIZE = 12
    
    # Colors (in hex)
    PRIMARY_COLOR = "#2c3e50"
    SECONDARY_COLOR = "#34495e"
    HIGHLIGHT_COLOR = "#3498db"
    WARNING_COLOR = "#e74c3c"
    SUCCESS_COLOR = "#2ecc71"
    
    # Margins and spacing
    MARGIN = 20
    SPACING = 10
    
    # Grid settings
    GRID_COLUMNS = 3
    CARD_MIN_WIDTH = 150
    CARD_MIN_HEIGHT = 120

class DateTimeFormats:
    """Date and time formats"""
    DATE_FORMAT = "%Y-%m-%d"
    TIME_FORMAT = "%H:%M:%S"
    DATETIME_FORMAT = f"{DATE_FORMAT} {TIME_FORMAT}"
    BATCH_DATE_FORMAT = "%Y%m%d"