"""
database.py: Core database models and connection management
This module handles database initialization, connection, and defines base models.
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
    FOOD = "飼料"
    MEDICINE = "藥品"
    SUPPLIES = "用品"
    OTHER = "其他"

class Item(Base):
    """商品基本資料表"""
    __tablename__ = 'items'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, comment='商品名稱')
    type = Column(Enum(ItemType), nullable=False, comment='商品類型')
    description = Column(String(500), comment='商品描述')
    unit = Column(String(20), nullable=False, comment='單位')
    created_at = Column(DateTime, default=datetime.utcnow, comment='建立時間')
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新時間')

def get_db_path():
    """
    取得資料庫檔案路徑
    返回: Path物件，指向資料庫檔案位置
    """
    # 取得專案根目錄
    project_dir = Path(__file__).parent.parent
    
    # 建立data目錄
    data_dir = project_dir / "data"
    data_dir.mkdir(exist_ok=True)
    
    return data_dir / "inventory.db"

def init_db():
    """
    初始化資料庫連線和表格
    返回: SQLAlchemy session物件
    """
    db_path = get_db_path()
    db_url = f"sqlite:///{db_path}"
    
    # 建立資料庫引擎
    engine = create_engine(db_url)
    
    # 建立所有定義的表格
    Base.metadata.create_all(engine)
    
    # 建立並返回session
    Session = sessionmaker(bind=engine)
    return Session()