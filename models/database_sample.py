"""
database.py: Core database models and connection management
Updated with provider and material management
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import enum
from pathlib import Path

Base = declarative_base()

class ItemType(enum.Enum):
    """商品類型列舉"""
    MATERIAL = "原料"  # 原料
    PRODUCT = "商品"   # 成品
    SUPPLY = "耗材"    # 耗材

class Provider(Base):
    """供應商資料表"""
    __tablename__ = 'providers'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, comment='供應商名稱')
    contact = Column(String(100), comment='聯絡人')
    phone = Column(String(20), comment='電話')
    email = Column(String(100), comment='Email')
    address = Column(String(200), comment='地址')
    notes = Column(String(500), comment='備註')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 關聯
    materials = relationship("Material", back_populates="provider")

class Material(Base):
    """原料資料表"""
    __tablename__ = 'materials'
    
    id = Column(Integer, primary_key=True)
    sku = Column(String(50), unique=True, nullable=False, comment='料號')
    name = Column(String(100), nullable=False, comment='品名')
    unit = Column(String(20), nullable=False, comment='單位')
    amount = Column(Float, default=0, comment='數量')
    min_amount = Column(Float, default=0, comment='最小安全存量')
    provider_id = Column(Integer, ForeignKey('providers.id'), comment='供應商ID')
    notes = Column(String(500), comment='備註')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 關聯
    provider = relationship("Provider", back_populates="materials")
    inventory_logs = relationship("MaterialLog", back_populates="material")

class MaterialLog(Base):
    """原料異動記錄表"""
    __tablename__ = 'material_logs'
    
    id = Column(Integer, primary_key=True)
    material_id = Column(Integer, ForeignKey('materials.id'), comment='原料ID')
    action_type = Column(String(20), nullable=False, comment='異動類型(入庫/出庫)')
    amount_change = Column(Float, nullable=False, comment='異動數量')
    amount_after = Column(Float, nullable=False, comment='異動後數量')
    notes = Column(String(500), comment='備註')
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(50), comment='建立者')
    
    # 關聯
    material = relationship("Material", back_populates="inventory_logs")

def get_db_path():
    """取得資料庫檔案路徑"""
    project_dir = Path(__file__).parent.parent
    data_dir = project_dir / "data"
    data_dir.mkdir(exist_ok=True)
    return data_dir / "inventory.db"

def init_db():
    """初始化資料庫連線和表格"""
    db_path = get_db_path()
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()