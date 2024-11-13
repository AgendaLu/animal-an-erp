"""
inventory.py: Inventory management functions
Handles material and inventory operations
"""

from typing import List, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime
from .database import Material, Provider, MaterialLog

class InventoryManager:
    def __init__(self, session: Session):
        """初始化庫存管理器"""
        self.session = session

    def add_material(self, 
                    sku: str,
                    name: str,
                    unit: str,
                    amount: float,
                    provider_id: int,
                    min_amount: float = 0,
                    notes: str = "") -> Tuple[bool, str, Optional[Material]]:
        """
        新增原料
        
        Args:
            sku: 料號
            name: 品名
            unit: 單位
            amount: 初始數量
            provider_id: 供應商ID
            min_amount: 最小安全存量
            notes: 備註
            
        Returns:
            (成功與否, 訊息, 原料物件)
        """
        try:
            # 檢查料號是否已存在
            existing = self.session.query(Material).filter_by(sku=sku).first()
            if existing:
                return False, "料號已存在", None

            # 檢查供應商是否存在
            provider = self.session.query(Provider).get(provider_id)
            if not provider:
                return False, "供應商不存在", None

            # 建立新原料
            material = Material(
                sku=sku,
                name=name,
                unit=unit,
                amount=amount,
                provider_id=provider_id,
                min_amount=min_amount,
                notes=notes
            )
            
            self.session.add(material)
            
            # 如果有初始數量，建立入庫記錄
            if amount > 0:
                log = MaterialLog(
                    material=material,
                    action_type="入庫",
                    amount_change=amount,
                    amount_after=amount,
                    notes="初始建立"
                )
                self.session.add(log)
            
            self.session.commit()
            return True, "新增成功", material
            
        except Exception as e:
            self.session.rollback()
            return False, f"新增失敗: {str(e)}", None

    def get_material(self, sku: str) -> Optional[Material]:
        """查詢原料"""
        return self.session.query(Material).filter_by(sku=sku).first()

    def get_all_providers(self) -> List[Provider]:
        """取得所有供應商列表"""
        return self.session.query(Provider).all()

    def add_provider(self, 
                    name: str,
                    contact: str = "",
                    phone: str = "",
                    email: str = "",
                    address: str = "",
                    notes: str = "") -> Tuple[bool, str, Optional[Provider]]:
        """新增供應商"""
        try:
            provider = Provider(
                name=name,
                contact=contact,
                phone=phone,
                email=email,
                address=address,
                notes=notes
            )
            self.session.add(provider)
            self.session.commit()
            return True, "新增成功", provider
        except Exception as e:
            self.session.rollback()
            return False, f"新增失敗: {str(e)}", None