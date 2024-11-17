from typing import Optional, List, Tuple, Dict
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from models.inventory import Material, MaterialBatch, InventoryTransaction, TransactionType, ReferenceType
from utils.validators import validate_code
from utils.logger import get_logger
from views.components.datetime_picker import DateTimePicker

logger = get_logger(__name__)

class InventoryViewModel:
    """ViewModel for inventory management operations"""
    
    def __init__(self, session: Session):
        self.session = session
        self.logger = get_logger(__name__)

    def create_material(self, data: Dict) -> Tuple[bool, str, Optional[Material]]:
        """
        Create a new material
        
        Args:
            data (Dict): Material data containing code, name, etc.
            
        Returns:
            Tuple[bool, str, Optional[Material]]: (success, message, material_object)
        """
        try:
            # Validate material data
            if not self._validate_material_data(data):
                return False, "Invalid material data", None

            # Create new material
            material = Material(
                code=data['code'].strip(),
                name=data['name'].strip(),
                description=data.get('description', ''),
                unit=data['unit'],
                min_quantity=data.get('min_quantity', 0),
                storage_temp=data.get('storage_temp')
            )
            
            self.session.add(material)
            self.session.commit()
            
            return True, "Material created successfully", material
            
        except IntegrityError:
            self.session.rollback()
            return False, "Material code already exists", None
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Error creating material: {str(e)}")
            return False, f"Error creating material: {str(e)}", None

    def get_material(self, identifier: str) -> Optional[Material]:
        """
        Get material by code or ID
        
        Args:
            identifier: Material code or ID
            
        Returns:
            Optional[Material]: Material object if found
        """
        try:
            # Try to find by code first
            material = self.session.query(Material).filter(
                Material.code == identifier
            ).first()
            
            # If not found, try to find by ID
            if not material and identifier.isdigit():
                material = self.session.query(Material).filter(
                    Material.id == int(identifier)
                ).first()
                
            return material
        except Exception as e:
            self.logger.error(f"Error getting material: {str(e)}")
            return None

    def adjust_inventory(self, 
                        material_code: str, 
                        quantity: float,
                        batch_number: str,
                        transaction_type: TransactionType,
                        reference_type: ReferenceType,
                        reference_id: int,
                        notes: str = None,
                        transaction_date: Optional[datetime] = None) -> Tuple[bool, str]:
        """
        Adjust inventory quantity (increase/decrease)
        
        Args:
            material_code: Material code
            quantity: Quantity to adjust
            batch_number: Batch number
            transaction_type: IN or OUT
            reference_type: Type of reference document (PO/SO)
            reference_id: ID of reference document
            notes: Additional notes
            transaction_date: Date and time of the transaction
            
        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            if transaction_date is None:
                transaction_date = select_datetime()

            material = self.get_material(material_code)
            if not material:
                return False, f"Material {material_code} not found"

            # Get or create batch
            batch = self._get_or_create_batch(material.id, batch_number)
            if not batch:
                return False, "Error managing batch"

            # Calculate new quantity
            new_quantity = batch.quantity
            if transaction_type == TransactionType.IN:
                new_quantity += quantity
            else:  # OUT
                if batch.quantity < quantity:
                    return False, "Insufficient stock"
                new_quantity -= quantity

            # Create transaction record
            transaction = InventoryTransaction(
                batch_id=batch.id,
                transaction_type=transaction_type,
                quantity=quantity,
                reference_type=reference_type,
                reference_id=reference_id,
                notes=notes,
                transaction_date=transaction_date
            )

            # Update batch quantity
            batch.quantity = new_quantity
            
            # Update material total quantity
            self._update_material_quantity(material)

            self.session.add(transaction)
            self.session.commit()

            return True, f"Inventory adjusted successfully. New quantity: {new_quantity}"

        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Error adjusting inventory: {str(e)}")
            return False, f"Error adjusting inventory: {str(e)}"

    def get_batch_transactions(self, 
                             material_code: str, 
                             batch_number: Optional[str] = None,
                             start_date: Optional[datetime] = None,
                             end_date: Optional[datetime] = None) -> List[InventoryTransaction]:
        """Get transaction history for a material/batch"""
        try:
            query = self.session.query(InventoryTransaction)\
                .join(MaterialBatch)\
                .join(Material)\
                .filter(Material.code == material_code)

            if batch_number:
                query = query.filter(MaterialBatch.batch_number == batch_number)
            if start_date:
                query = query.filter(InventoryTransaction.transaction_date >= start_date)
            if end_date:
                query = query.filter(InventoryTransaction.transaction_date <= end_date)

            return query.order_by(InventoryTransaction.transaction_date.desc()).all()
        except Exception as e:
            self.logger.error(f"Error getting transactions: {str(e)}")
            return []

    def _validate_material_data(self, data: Dict) -> bool:
        """Validate material data"""
        required_fields = ['code', 'name', 'unit']
        return all(data.get(field) for field in required_fields)

    def _get_or_create_batch(self, 
                            material_id: int, 
                            batch_number: str) -> Optional[MaterialBatch]:
        """Get existing batch or create new one"""
        batch = self.session.query(MaterialBatch).filter(
            MaterialBatch.material_id == material_id,
            MaterialBatch.batch_number == batch_number
        ).first()

        if not batch:
            batch = MaterialBatch(
                material_id=material_id,
                batch_number=batch_number,
                quantity=0
            )
            self.session.add(batch)

        return batch

    def _update_material_quantity(self, material: Material):
        """Update material total quantity based on batch quantities"""
        total_quantity = sum(batch.quantity for batch in material.batches)
        material.quantity = total_quantity

    def check_low_stock(self) -> List[Dict]:
        """Get list of materials with quantity below min_quantity"""
        try:
            low_stock = []
            materials = self.session.query(Material).filter(
                Material.is_active == True,
                Material.quantity <= Material.min_quantity
            ).all()

            for material in materials:
                low_stock.append({
                    'code': material.code,
                    'name': material.name,
                    'current_quantity': material.quantity,
                    'min_quantity': material.min_quantity
                })

            return low_stock
        except Exception as e:
            self.logger.error(f"Error checking low stock: {str(e)}")
            return []
