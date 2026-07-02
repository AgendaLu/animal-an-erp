# Animal-AN-ERP System Technical Documentation

## Database Architecture

### SQLAlchemy Models & Data Types

#### 1. Product Management
```python
# Product Model
class Product(Base):
    __tablename__ = "products"
    
    id: Mapped[int]                    # Primary Key
    name: Mapped[str]                  # Product Name (100 chars)
    product_type: Mapped[ProductType]  # MEDICINE/VACCINE/MEDICATED_FEED/SUPPLEMENT
    storage_type: Mapped[StorageType]  # ROOM_TEMP/REFRIGERATED/FROZEN
    package_type: Mapped[PackageType]  # BULK/BAG/BOTTLE/VIAL
    unit: Mapped[str]                  # Unit of Measurement
    min_temperature: Mapped[float]     # Minimum Storage Temperature
    max_temperature: Mapped[float]     # Maximum Storage Temperature
    reorder_point: Mapped[float]       # Reorder Trigger Point
    created_at: Mapped[datetime]       # Creation Timestamp
```

#### 2. Inventory Management
```python
# Batch Model
class Batch(Base):
    __tablename__ = "batches"
    
    id: Mapped[int]                    # Primary Key
    product_id: Mapped[int]            # Foreign Key to Products
    batch_number: Mapped[str]          # Unique Batch Number
    manufacture_date: Mapped[datetime] # Manufacturing Date
    expiry_date: Mapped[datetime]     # Expiration Date
    quantity: Mapped[float]           # Current Quantity
    unit_cost: Mapped[float]          # Cost per Unit
```

#### 3. Transaction Records
```python
# Inventory Transaction Model
class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"
    
    id: Mapped[int]                    # Primary Key
    batch_id: Mapped[int]              # Foreign Key to Batches
    transaction_type: Mapped[str]      # IN/OUT
    quantity: Mapped[float]            # Transaction Quantity
    reference_type: Mapped[str]        # PO/SO Reference
    reference_id: Mapped[int]          # Reference Document ID
```

### Database Indexing Strategy
```sql
-- Primary Indices
CREATE INDEX idx_product_name ON products(name);
CREATE INDEX idx_batch_number ON batches(batch_number);
CREATE INDEX idx_transaction_date ON inventory_transactions(transaction_date);

-- Composite Indices
CREATE INDEX idx_batch_expiry ON batches(product_id, expiry_date);
CREATE INDEX idx_inventory_batch ON inventory_transactions(batch_id, transaction_type);
```

## System Architecture

### 1. Data Layer
```
models/
├── database.py      # Database connection management
├── product.py       # Product and batch models
├── inventory.py     # Inventory transaction models
├── customer.py      # Customer management models
└── finance.py       # Financial transaction models
```

### 2. Business Logic Layer
```
viewmodels/
├── product_vm.py    # Product management logic
├── inventory_vm.py  # Inventory control logic
├── order_vm.py      # Order processing logic
└── report_vm.py     # Reporting and analysis logic
```

### 3. Presentation Layer
```
views/
├── components/      # Reusable UI components
├── dialogs/         # Pop-up windows
├── pages/           # Main interface pages
└── main_window.py   # Main application window
```

## Performance Optimization

### 1. Database Configuration
```python
# config/database.py
ENGINE_CONFIG = {
    "pool_pre_ping": True,
    "pool_recycle": 3600,
    "pool_size": 5,
    "max_overflow": 10,
    "echo": False,
    "isolation_level": "READ COMMITTED"
}

SQLITE_PRAGMAS = {
    "journal_mode": "WAL",
    "cache_size": -64 * 1000,  # 64MB cache
    "foreign_keys": 1,
    "synchronous": 1,
}
```

### 2. Query Optimization
```python
# Example of optimized batch query
def get_expiring_batches(session: Session, days: int = 90) -> List[Batch]:
    return session.execute(
        select(Batch)
        .options(joinedload(Batch.product))
        .where(
            Batch.expiry_date <= datetime.now() + timedelta(days=days),
            Batch.quantity > 0
        )
        .order_by(Batch.expiry_date)
    ).scalars().all()
```

## Data Backup System

### 1. Backup Configuration
```python
# config/backup.py
BACKUP_CONFIG = {
    "backup_dir": "data/backups",
    "retention_days": 30,
    "compress": True,
    "max_backups": 100,
    "backup_on_startup": True
}
```

### 2. Backup Process
```python
def create_backup():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"data/backups/animal_an_{timestamp}.db"
    
    # Create backup with SQLite's backup API
    with sqlite3.connect(db_path) as src, \
         sqlite3.connect(backup_path) as dst:
        src.backup(dst)
    
    # Compress backup
    if BACKUP_CONFIG["compress"]:
        compress_backup(backup_path)
```

## Error Handling

### 1. Database Errors
```python
class DatabaseError(Exception):
    """Base class for database exceptions"""
    pass

class ConnectionError(DatabaseError):
    """Database connection errors"""
    pass

class IntegrityError(DatabaseError):
    """Data integrity violations"""
    pass
```

### 2. Error Logging
```python
# utils/logger.py
LOG_CONFIG = {
    "version": 1,
    "handlers": {
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "logs/app.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "formatter": "detailed"
        }
    }
}
```

## Transaction Management

### 1. Session Management
```python
from contextlib import contextmanager

@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()
```

### 2. Transaction Examples
```python
# Example of a complex transaction
def transfer_inventory(
    source_batch_id: int,
    target_batch_id: int,
    quantity: float
) -> None:
    with session_scope() as session:
        # Lock the batches
        source_batch = session.query(Batch).with_for_update().get(source_batch_id)
        target_batch = session.query(Batch).with_for_update().get(target_batch_id)
        
        # Validate
        if source_batch.quantity < quantity:
            raise ValueError("Insufficient quantity")
            
        # Update quantities
        source_batch.quantity -= quantity
        target_batch.quantity += quantity
        
        # Record transactions
        session.add(InventoryTransaction(
            batch_id=source_batch_id,
            transaction_type="OUT",
            quantity=quantity
        ))
        session.add(InventoryTransaction(
            batch_id=target_batch_id,
            transaction_type="IN",
            quantity=quantity
        ))
```

## Memory Management

### 1. Large Query Handling
```python
def iter_large_result(query, chunk_size=1000):
    """Iterator for handling large query results"""
    offset = 0
    while True:
        chunk = query.limit(chunk_size).offset(offset).all()
        if not chunk:
            break
        for item in chunk:
            yield item
        offset += chunk_size
```

### 2. Cache Configuration
```python
CACHE_CONFIG = {
    "product_cache_size": 1000,
    "batch_cache_size": 5000,
    "cache_ttl": 3600,  # 1 hour
}
```

## Performance Monitoring

### 1. Query Statistics
```python
class QueryStats:
    def __init__(self):
        self.query_count = 0
        self.slow_queries = []
        self.start_time = time.time()
        
    def log_query(self, query, duration):
        self.query_count += 1
        if duration > 1.0:  # Log queries taking more than 1 second
            self.slow_queries.append((query, duration))
```

Would you like me to:
1. Add more specific implementation details?
2. Create additional optimization strategies?
3. Add more error handling examples?
4. Expand the monitoring system?